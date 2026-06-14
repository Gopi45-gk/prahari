"""
PRAHARI Unified Command Gateway
================================
Single FastAPI backend that merges:
  1. Crew Alertness AI  (FaceDetector → CNN → LSTM → FusionEngine)
  2. Railway Intelligence (Track RF model + Cyber Isolation Forest)
  3. Convergence Risk Engine (multi-domain CCRS fusion)

Run:
    python main.py          # starts on port 8001
    # or
    uvicorn main:app --reload --host 0.0.0.0 --port 8001
"""

import sys
import os
import time
import base64
import json
import asyncio
import datetime
from typing import Optional, List, Dict, Any

import cv2
import numpy as np
try:
    import torch
    import pandas as pd
    import joblib
    ml_deps_available = True
except Exception as e:
    print(f"Failed to load ML dependencies: {e}")
    ml_deps_available = False
    torch = None
    pd = None
    joblib = None
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Path setup — import prahari ML package
# ---------------------------------------------------------------------------
PRAHARI_SRC = r"g:\My Drive\prahari\src"
if PRAHARI_SRC not in sys.path:
    sys.path.insert(0, PRAHARI_SRC)

RAILWAY_BACKEND = r"c:\Users\gopik\prahari-backend\api"

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="PRAHARI Unified Gateway",
    description="AI-Powered Convergence Risk Intelligence — Crew + Infrastructure + Cyber",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ═══════════════════════════════════════════════════════════════════════════
# SECTION A — Crew Alertness AI (from prahari-command/backend/main.py)
# ═══════════════════════════════════════════════════════════════════════════

try:
    from prahari.detection.face_detector import FaceDetector
    from prahari.detection.feature_extractor import FeatureExtractor
    from prahari.models.fatigue_cnn import FatigueCNNInference
    from prahari.models.temporal_lstm import TemporalLSTMInference
    from prahari.models.fusion_engine import FusionEngine

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[PRAHARI] Device: {device}")

    print("[PRAHARI] Loading FaceDetector & FeatureExtractor...")
    face_detector = FaceDetector(
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
        roi_size=224,
    )
    feature_extractor = FeatureExtractor(fps=1)

    print("[PRAHARI] Loading FatigueCNN...")
    cnn = FatigueCNNInference(device=device)

    print("[PRAHARI] Loading TemporalLSTM...")
    lstm = TemporalLSTMInference(device=device)

    print("[PRAHARI] Loading FusionEngine...")
    fusion = FusionEngine()
    
    ml_available = True
except Exception as e:
    print(f"[PRAHARI] Warning: Failed to load ML models due to memory/DLL issues. Running in degraded mode. Error: {e}")
    ml_available = False


class CrewLiveState:
    """Mutable session state for the crew alertness pipeline."""

    def __init__(self):
        self.running = False
        self.start_time = time.time()
        self.alerts: list = []
        self.last_result: dict = {
            "fatigue_class": "ALERT",
            "fatigue_score": 0,
            "microsleep_probability": 0.0,
            "trend": "STABLE",
            "cai": 0,
            "risk_level": "NORMAL",
            "blink_rate": 0,
            "perclos": 0,
            "microsleep_events": 0,
            "hrv": 0,
            "posture_sway": "Normal",
            "duty_duration": "00h 00m",
            "continuous_driving": "00h 00m",
            "alerts": [],
            "image": None,
        }


crew_state = CrewLiveState()


def process_frame(base64_str: str) -> dict:
    """Run the full Crew AI pipeline on a single base64-encoded frame."""
    if base64_str.startswith("data:image"):
        base64_str = base64_str.split(",")[1]

    img_data = base64.b64decode(base64_str)
    nparr = np.frombuffer(img_data, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if frame is None:
        return crew_state.last_result

    # Stage 1: Face Detection
    detection = face_detector.detect(frame)

    # Stage 2: Feature Extraction
    features = feature_extractor.extract(detection)

    class_name = "ALERT"
    fatigue_score = 0.0
    probs = np.array([1.0, 0.0, 0.0, 0.0, 0.0])

    if detection.detected and detection.face_roi is not None:
        class_name, confidence, probs = cnn.classify(detection.face_roi)
        fatigue_score = cnn.get_fatigue_score(probs)

    # Temporal LSTM
    lstm.add_observation(features.to_array())
    trend, trend_conf, ms_prob, attn = lstm.predict()

    if ms_prob > 0.7:
        crew_state.last_result["microsleep_events"] += 1

    # Fusion Engine
    fusion_res = fusion.fuse(
        cnn_probs=probs,
        perclos=features.perclos,
        ear_avg=features.ear_avg,
        mar=features.mar,
        is_yawning=features.is_yawning,
        blink_rate=features.blink_rate,
        avg_blink_duration=features.avg_blink_duration,
        head_pitch=features.head_pitch,
        head_yaw=features.head_yaw,
        head_drooping=features.head_drooping,
        temporal_trend=trend,
        temporal_confidence=trend_conf,
        microsleep_prob=ms_prob,
        face_detected=detection.detected,
        detection_confidence=detection.confidence,
    )

    cai = fusion_res.cai_smoothed

    if cai > 80:
        risk = "CRITICAL"
    elif cai > 60:
        risk = "HIGH"
    else:
        risk = "NORMAL"

    # Encode frame with overlay
    overlay = face_detector.draw_overlay(frame, detection)
    _, buffer = cv2.imencode(".jpg", overlay, [cv2.IMWRITE_JPEG_QUALITY, 60])
    overlay_b64 = "data:image/jpeg;base64," + base64.b64encode(buffer).decode("utf-8")

    # Time formats
    elapsed_seconds = int(time.time() - crew_state.start_time)
    hours = elapsed_seconds // 3600
    minutes = (elapsed_seconds % 3600) // 60

    duty_dur = f"{(hours + 8):02d}h {(minutes + 54):02d}m"
    cont_dur = f"{(hours + 2):02d}h {(minutes + 18):02d}m"

    current_time_str = datetime.datetime.now().strftime("%H:%M:%S")

    # Alerts logic
    if features.eyes_closed and (
        len(crew_state.alerts) == 0
        or crew_state.alerts[0]["t"] != "Extended eye closure detected"
    ):
        crew_state.alerts.insert(
            0,
            {"t": "Extended eye closure detected", "time": current_time_str, "tone": "critical"},
        )
    elif features.is_yawning and (
        len(crew_state.alerts) == 0
        or crew_state.alerts[0]["t"] != "Yawning sequence observed"
    ):
        crew_state.alerts.insert(
            0,
            {"t": "Yawning sequence observed", "time": current_time_str, "tone": "warning"},
        )
    elif features.head_drooping and (
        len(crew_state.alerts) == 0
        or crew_state.alerts[0]["t"] != "Head drooping detected"
    ):
        crew_state.alerts.insert(
            0,
            {"t": "Head drooping detected", "time": current_time_str, "tone": "critical"},
        )

    if len(crew_state.alerts) > 4:
        crew_state.alerts = crew_state.alerts[:4]

    posture = "Normal"
    if features.head_pitch > 15 or features.head_roll > 15:
        posture = "High"

    result = {
        "fatigue_class": class_name,
        "fatigue_score": int(fatigue_score),
        "microsleep_probability": float(ms_prob),
        "trend": trend,
        "cai": int(cai),
        "risk_level": risk,
        "blink_rate": int(features.blink_rate),
        "perclos": round(float(features.perclos) * 100, 1),
        "microsleep_events": crew_state.last_result["microsleep_events"],
        "hrv": 18,
        "posture_sway": posture,
        "duty_duration": duty_dur,
        "continuous_driving": cont_dur,
        "alerts": crew_state.alerts,
        "image": overlay_b64,
    }

    crew_state.last_result.update(result)
    return result


# ═══════════════════════════════════════════════════════════════════════════
# SECTION B — Railway Intelligence (from prahari-backend/api/main.py)
# ═══════════════════════════════════════════════════════════════════════════

print("[PRAHARI] Loading Track & Cyber ML models...")
track_df = pd.read_csv(os.path.join(RAILWAY_BACKEND, "data", "track_dataset.csv"))
cyber_bundle = joblib.load(os.path.join(RAILWAY_BACKEND, "models", "cyber_anomaly_model.pkl"))
track_bundle = joblib.load(os.path.join(RAILWAY_BACKEND, "models", "track_defect_model.pkl"))

cyber_model = cyber_bundle["model"]
cyber_encoders = cyber_bundle["encoders"]
cyber_features = cyber_bundle["feature_cols"]

track_model = track_bundle["model"]
track_features_cols = track_bundle["feature_cols"]

# In-memory citizen reports store
reports_db: List[dict] = []
_report_id_counter = 1


# ── Pydantic Schemas ──────────────────────────────────────────────────────

class CitizenReport(BaseModel):
    train_no: Optional[str] = Field(None, example="12627")
    issue_type: str = Field(..., example="Track Damage")
    location: str = Field(..., example="KM 142/3, Arakkonam")
    description: Optional[str] = Field(None, example="Visible crack near track joint")
    reporter_name: Optional[str] = Field(None, example="Anonymous")


class CyberLogEntry(BaseModel):
    asset_id: str = Field(..., example="SIG-014")
    duration: float = 0
    protocol_type: str = Field(..., example="tcp")
    service: str = Field(..., example="http")
    flag: str = Field(..., example="SF")
    src_bytes: float = 0
    dst_bytes: float = 0
    wrong_fragment: float = 0
    urgent: float = 0
    hot: float = 0
    num_failed_logins: float = 0
    logged_in: float = 1
    num_compromised: float = 0
    count: float = 1
    srv_count: float = 1
    serror_rate: float = 0
    srv_serror_rate: float = 0
    same_srv_rate: float = 1
    diff_srv_rate: float = 0
    dst_host_count: float = 1
    dst_host_srv_count: float = 1
    dst_host_same_srv_rate: float = 1
    dst_host_serror_rate: float = 0


class SimulateRequest(BaseModel):
    infra_risk_score: float = Field(30.0, ge=0, le=100)
    cyber_risk_score: float = Field(20.0, ge=0, le=100)
    signal_delay_score: float = Field(10.0, ge=0, le=100)
    crew_fatigue_index: float = Field(20.0, ge=0, le=100)


# ── Cyber scoring helper ──────────────────────────────────────────────────

def score_cyber_log(entry: CyberLogEntry) -> dict:
    row = entry.dict()
    row.pop("asset_id")
    df_row = pd.DataFrame([row])

    for col, le in cyber_encoders.items():
        val = df_row.at[0, col]
        if val in le.classes_:
            df_row[col] = le.transform([val])[0]
        else:
            df_row[col] = -1

    df_row = df_row[cyber_features]

    raw_score = cyber_model.decision_function(df_row)[0]
    is_anomaly = cyber_model.predict(df_row)[0] == -1
    risk_score = float(np.clip((0.5 - raw_score) * 100, 0, 100))

    return {
        "asset_id": entry.asset_id,
        "is_anomaly": bool(is_anomaly),
        "cyber_risk_score": round(risk_score, 1),
        "raw_decision_score": round(float(raw_score), 4),
    }


# ── CCRS computation ─────────────────────────────────────────────────────

DEMO_TRAIN_IDS = ["12627", "12651", "12711", "16317", "12621", "12609", "16723", "12693"]


def compute_risk_score(train_id: str) -> dict:
    """Compute composite CCRS for a given train_id."""
    routes = track_df["route"].unique()
    route = routes[hash(train_id) % len(routes)]

    route_segments = track_df[track_df["route"] == route]
    infra_risk = float(route_segments["infra_risk_score"].mean())

    sample_log = CyberLogEntry(
        asset_id=f"SIG-{(hash(train_id) % 50) + 1:03d}",
        protocol_type="tcp", service="http", flag="SF",
        duration=0, src_bytes=200, dst_bytes=200, count=5, srv_count=5,
        same_srv_rate=1, dst_host_count=10, dst_host_srv_count=10,
        dst_host_same_srv_rate=1,
    )
    cyber_result = score_cyber_log(sample_log)

    train_reports = [
        r for r in reports_db
        if r.get("train_no") == train_id and r["status"] != "Resolved"
    ]
    report_risk = min(len(train_reports) * 15, 100)

    # Include crew fatigue in CCRS if available
    crew_risk = crew_state.last_result.get("cai", 0)

    # Unified 4-factor CCRS
    ccrs = round(
        crew_risk * 0.35
        + infra_risk * 0.30
        + cyber_result["cyber_risk_score"] * 0.20
        + report_risk * 0.15,
        1,
    )

    if ccrs >= 75:
        level = "Critical"
        action = (
            "Impose advisory speed restriction (40 km/h). "
            "Alert relief crew point at next station. "
            "Flag section for priority inspection."
        )
    elif ccrs >= 55:
        level = "High"
        action = (
            "Increase monitoring frequency. "
            "Notify loco pilot and station master. "
            "Schedule inspection within 24 hours."
        )
    elif ccrs >= 30:
        level = "Warning"
        action = "Continue normal operations with routine monitoring."
    else:
        level = "Safe"
        action = "No action required."

    total = ccrs if ccrs > 0 else 1
    return {
        "train_id": train_id,
        "route": route,
        "ccrs": ccrs,
        "risk_level": level,
        "recommended_action": action,
        "breakdown": {
            "crew_fatigue": round(crew_risk * 0.35, 1),
            "infra_risk_score": round(infra_risk * 0.30, 1),
            "cyber_risk_score": round(cyber_result["cyber_risk_score"] * 0.20, 1),
            "public_report_risk": round(report_risk * 0.15, 1),
        },
        "contribution_percent": {
            "crew_fatigue": round((crew_risk * 0.35 / total) * 100, 1) if total > 0 else 0,
            "infra_risk": round((infra_risk * 0.30 / total) * 100, 1) if total > 0 else 0,
            "cyber_risk": round((cyber_result["cyber_risk_score"] * 0.20 / total) * 100, 1) if total > 0 else 0,
            "operational": round((report_risk * 0.15 / total) * 100, 1) if total > 0 else 0,
        },
        "active_reports": len(train_reports),
    }


# ═══════════════════════════════════════════════════════════════════════════
# SECTION C — REST Endpoints
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/")
def root():
    return {
        "service": "PRAHARI Unified Gateway",
        "status": "online",
        "version": "2.0.0",
    }


# ── Crew REST ─────────────────────────────────────────────────────────────

@app.get("/api/crew/live")
def crew_live():
    """Latest crew telemetry snapshot (polling fallback)."""
    r = dict(crew_state.last_result)
    r.pop("image", None)  # Don't send base64 image over REST
    return r


# ── Track / Infrastructure REST ───────────────────────────────────────────

@app.get("/api/tracks")
def get_tracks(route: Optional[str] = None, risk_level: Optional[str] = None, limit: int = 100):
    df = track_df
    if route:
        df = df[df["route"] == route]
    if risk_level:
        df = df[df["risk_level"] == risk_level]
    return df.head(limit).to_dict(orient="records")


@app.get("/api/tracks/{segment_id}")
def get_track_segment(segment_id: str):
    row = track_df[track_df["segment_id"] == segment_id]
    if row.empty:
        raise HTTPException(status_code=404, detail="Segment not found")
    record = row.iloc[0].to_dict()
    X = row[track_features_cols]
    defect_prob = track_model.predict_proba(X)[0][1]
    record["predicted_defect_probability"] = round(float(defect_prob), 3)
    return record


# ── Cyber REST ────────────────────────────────────────────────────────────

@app.post("/api/cyber-check")
def cyber_check(entry: CyberLogEntry):
    return score_cyber_log(entry)


# ── Reports REST ──────────────────────────────────────────────────────────

@app.post("/api/reports")
def create_report(report: CitizenReport):
    global _report_id_counter
    record = report.dict()
    record["report_id"] = f"RPT-{_report_id_counter:05d}"
    record["timestamp"] = datetime.datetime.utcnow().isoformat()
    record["status"] = "Pending Verification"
    _report_id_counter += 1
    reports_db.append(record)
    return record


@app.get("/api/reports")
def list_reports(status: Optional[str] = None, limit: int = 50):
    data = reports_db
    if status:
        data = [r for r in data if r["status"] == status]
    return data[-limit:][::-1]


# ── CCRS / Risk REST ─────────────────────────────────────────────────────

@app.get("/api/risk-score/{train_id}")
def get_risk_score(train_id: str):
    return compute_risk_score(train_id)


@app.get("/api/trains")
def list_trains(limit: int = 20):
    results = [compute_risk_score(tid) for tid in DEMO_TRAIN_IDS[:limit]]
    results.sort(key=lambda r: r["ccrs"], reverse=True)
    return results


@app.get("/api/dashboard-summary")
def dashboard_summary():
    train_scores = [compute_risk_score(tid) for tid in DEMO_TRAIN_IDS]

    active_trains = len(train_scores)
    high_risk_trains = sum(1 for t in train_scores if t["risk_level"] in ("High", "Critical"))
    critical_alerts = sum(1 for t in train_scores if t["risk_level"] == "Critical")
    open_reports = sum(1 for r in reports_db if r["status"] != "Resolved")
    critical_segments = int((track_df["risk_level"] == "Critical").sum())

    # Aggregate sub-scores for the executive dashboard bars
    avg_infra = float(track_df["infra_risk_score"].mean())
    avg_ccrs = round(sum(t["ccrs"] for t in train_scores) / max(len(train_scores), 1), 1)
    crew_cai = crew_state.last_result.get("cai", 0)

    # Sample cyber score for fleet overview
    sample_cyber = score_cyber_log(CyberLogEntry(
        asset_id="SIG-FLEET", protocol_type="tcp", service="http", flag="SF",
        duration=0, src_bytes=200, dst_bytes=200, count=5, srv_count=5,
        same_srv_rate=1, dst_host_count=10, dst_host_srv_count=10,
        dst_host_same_srv_rate=1,
    ))

    return {
        "active_trains": active_trains,
        "high_risk_trains": high_risk_trains,
        "critical_alerts": critical_alerts,
        "open_reports": open_reports,
        "critical_track_segments": critical_segments,
        "avg_ccrs": avg_ccrs,
        "crew_fatigue_risk": crew_cai,
        "avg_infra_risk": round(avg_infra, 1),
        "cyber_threat_level": round(sample_cyber["cyber_risk_score"], 1),
        "track_sensor_health": round(100 - avg_infra, 1),
        "trains": train_scores,
    }


@app.post("/api/simulate")
def simulate_ccrs(req: SimulateRequest):
    weights = {
        "crew_fatigue_index": 0.35,
        "signal_delay_score": 0.30,
        "infra_risk_score": 0.20,
        "cyber_risk_score": 0.15,
    }
    values = {
        "crew_fatigue_index": req.crew_fatigue_index,
        "signal_delay_score": req.signal_delay_score,
        "infra_risk_score": req.infra_risk_score,
        "cyber_risk_score": req.cyber_risk_score,
    }

    ccrs = round(sum(values[k] * weights[k] for k in weights), 1)

    if ccrs >= 75:
        level, action = "Critical", (
            "Impose advisory speed restriction (40 km/h). "
            "Alert relief crew point at next station. "
            "Flag section for priority inspection."
        )
    elif ccrs >= 55:
        level, action = "High", (
            "Increase monitoring frequency. "
            "Notify loco pilot and station master. "
            "Schedule inspection within 24 hours."
        )
    elif ccrs >= 30:
        level, action = "Warning", "Continue normal operations with routine monitoring."
    else:
        level, action = "Safe", "No action required."

    breakdown_pct = {
        k: round((values[k] * weights[k] / ccrs * 100) if ccrs > 0 else 0, 1)
        for k in weights
    }

    return {
        "ccrs": ccrs,
        "risk_level": level,
        "recommended_action": action,
        "inputs": values,
        "weights": weights,
        "contribution_percent": breakdown_pct,
    }


# ── Infrastructure summary for WebSocket ──────────────────────────────────

def _build_infra_snapshot() -> dict:
    """Build a snapshot of track, cyber, and CCRS data for the infra WS."""
    # Track summary
    total_segments = len(track_df)
    critical_count = int((track_df["risk_level"] == "Critical").sum())
    warning_count = int((track_df["risk_level"] == "Warning").sum())
    safe_count = int((track_df["risk_level"] == "Safe").sum())
    avg_infra_risk = round(float(track_df["infra_risk_score"].mean()), 1)

    # Sample track stats
    avg_vibration = round(float(track_df["vibration_level"].mean()), 2)
    avg_temp = round(float(track_df["rail_temperature_c"].mean()), 1)
    avg_stress = round(float(track_df["track_stress_nm"].mean()), 1)
    avg_wear = round(float(track_df["wear_index_min"].mean()), 1)

    # Cyber summary — run a batch of sample assets
    cyber_results = []
    for i in range(5):
        entry = CyberLogEntry(
            asset_id=f"SIG-{i+1:03d}",
            protocol_type="tcp", service="http", flag="SF",
            duration=0, src_bytes=200 + i * 50, dst_bytes=200 + i * 30,
            count=5 + i, srv_count=5,
            same_srv_rate=1, dst_host_count=10 + i, dst_host_srv_count=10,
            dst_host_same_srv_rate=1,
        )
        cyber_results.append(score_cyber_log(entry))

    anomaly_count = sum(1 for c in cyber_results if c["is_anomaly"])
    avg_cyber_risk = round(sum(c["cyber_risk_score"] for c in cyber_results) / max(len(cyber_results), 1), 1)

    # CCRS for fleet
    train_scores = [compute_risk_score(tid) for tid in DEMO_TRAIN_IDS]
    avg_ccrs = round(sum(t["ccrs"] for t in train_scores) / max(len(train_scores), 1), 1)

    return {
        "timestamp": datetime.datetime.now().isoformat(),
        "track": {
            "total_segments": total_segments,
            "critical_segments": critical_count,
            "warning_segments": warning_count,
            "safe_segments": safe_count,
            "avg_infra_risk": avg_infra_risk,
            "track_health_score": round(100 - avg_infra_risk, 1),
            "avg_vibration": avg_vibration,
            "avg_temperature": avg_temp,
            "avg_stress": avg_stress,
            "avg_wear": avg_wear,
        },
        "cyber": {
            "total_assets_scanned": len(cyber_results),
            "anomalies_detected": anomaly_count,
            "avg_cyber_risk": avg_cyber_risk,
            "threat_level": "HIGH" if avg_cyber_risk > 60 else "MEDIUM" if avg_cyber_risk > 30 else "LOW",
            "network_health": round(100 - avg_cyber_risk, 1),
            "assets": cyber_results,
        },
        "ccrs": {
            "avg_ccrs": avg_ccrs,
            "trains": train_scores,
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
# SECTION D — WebSocket Endpoints
# ═══════════════════════════════════════════════════════════════════════════

@app.websocket("/ws/crew")
async def ws_crew(websocket: WebSocket):
    await websocket.accept()
    if not ml_available:
        try:
            while True:
                await websocket.receive_text()
                # Mock response if ML is not available
                await websocket.send_json({
                    "cai": 85,
                    "fatigue_score": 15,
                    "microsleep_events": 0,
                    "blink_rate": 18,
                    "hrv": 45,
                    "posture_sway": "Normal",
                    "duty_duration": "04h 30m",
                    "continuous_driving": "02h 15m",
                    "risk_level": "NORMAL",
                    "alerts": []
                })
                await asyncio.sleep(1)
        except Exception:
            pass
        return

    crew_state.running = True
    try:
        while True:
            data = await websocket.receive_text()
            if not crew_state.running:
                await websocket.send_json({"status": "stopped"})
                continue
            result = process_frame(data)
            await websocket.send_json(result)
    except WebSocketDisconnect:
        print("[WS/crew] Client disconnected")


@app.websocket("/ws/infrastructure")
async def ws_infrastructure(websocket: WebSocket):
    """Infrastructure stream — pushes Track + Cyber + CCRS data every 5 seconds."""
    await websocket.accept()
    try:
        while True:
            snapshot = _build_infra_snapshot()
            await websocket.send_json(snapshot)
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        print("[WS/infrastructure] Client disconnected")


# Also keep backward-compat endpoint for crew.tsx
@app.websocket("/api/fatigue/stream")
async def ws_crew_legacy(websocket: WebSocket):
    """Legacy crew endpoint for backward compatibility."""
    await ws_crew(websocket)


# ═══════════════════════════════════════════════════════════════════════════
# SECTION E — AI Copilot Proxy
# ═══════════════════════════════════════════════════════════════════════════
from fastapi.responses import StreamingResponse
from fastapi import Request
import json
from openai import AsyncOpenAI

client = AsyncOpenAI(
  base_url="https://integrate.api.nvidia.com/v1",
  api_key="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"
)

@app.post("/api/copilot")
async def proxy_copilot(request: Request):
    """Proxies request to NVIDIA API using OpenAI SDK"""
    data = await request.json()
    
    async def stream_generator():
        try:
            completion = await client.chat.completions.create(
                model="nvidia/nemotron-3-ultra-550b-a55b",
                messages=data.get("messages", []),
                temperature=data.get("temperature", 1),
                top_p=data.get("top_p", 0.95),
                max_tokens=data.get("max_tokens", 16384),
                extra_body={"chat_template_kwargs": {"enable_thinking": True}, "reasoning_budget": 16384},
                stream=True
            )
            
            async for chunk in completion:
                if not chunk.choices:
                    continue
                
                delta = chunk.choices[0].delta
                reasoning = getattr(delta, "reasoning_content", None)
                content = getattr(delta, "content", None)
                
                # We yield JSON strings mimicking the structure expected by the frontend
                response_obj = {
                    "choices": [{
                        "delta": {
                            "reasoning_content": reasoning or "",
                            "content": content or ""
                        }
                    }]
                }
                yield f"data: {json.dumps(response_obj)}\n\n"
            
            yield "data: [DONE]\n\n"
        except Exception as e:
            print(f"[Copilot Proxy Error]: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(stream_generator(), media_type="text/event-stream")

# ═══════════════════════════════════════════════════════════════════════════
# SECTION F — Startup
# ═══════════════════════════════════════════════════════════════════════════

from auth import auth_router

# Mount Auth router
app.include_router(auth_router, prefix="/api")

print("[PRAHARI] Unified Gateway ready.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=False)
