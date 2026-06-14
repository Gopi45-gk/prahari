import sys
import os
import time
import base64
import json
import cv2
import numpy as np
import torch
import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add prahari to path
prahari_path = r"g:\My Drive\prahari\src"
if prahari_path not in sys.path:
    sys.path.append(prahari_path)

from prahari.detection.face_detector import FaceDetector
from prahari.detection.feature_extractor import FeatureExtractor
from prahari.models.fatigue_cnn import FatigueCNNInference
from prahari.models.temporal_lstm import TemporalLSTMInference
from prahari.models.fusion_engine import FusionEngine

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize models
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print("Loading FaceDetector & FeatureExtractor...")
face_detector = FaceDetector(min_detection_confidence=0.5, min_tracking_confidence=0.5, roi_size=224)
feature_extractor = FeatureExtractor(fps=1) # We're receiving ~1 fps from websocket

print("Loading FatigueCNN...")
cnn = FatigueCNNInference(device=device)

print("Loading TemporalLSTM...")
lstm = TemporalLSTMInference(device=device)

print("Loading FusionEngine...")
fusion = FusionEngine()

class LiveState:
    def __init__(self):
        self.running = False
        self.start_time = time.time()
        self.alerts = []
        self.last_result = {
            "fatigue_class": "ALERT",
            "fatigue_score": 0,
            "microsleep_probability": 0.0,
            "trend": "STABLE",
            "cai": 0,
            "risk_level": "NORMAL",
            "blink_rate": 0,
            "microsleep_events": 0,
            "hrv": 0,
            "posture_sway": "Normal",
            "duty_duration": "00h 00m",
            "continuous_driving": "00h 00m",
            "alerts": [],
            "image": None
        }

state = LiveState()

@app.websocket("/api/fatigue/stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    state.running = True
    try:
        while True:
            data = await websocket.receive_text()
            if not state.running:
                await websocket.send_json({"status": "stopped"})
                continue
                
            result = process_frame(data)
            await websocket.send_json(result)
    except WebSocketDisconnect:
        print("Client disconnected")

def process_frame(base64_str: str):
    if base64_str.startswith("data:image"):
        base64_str = base64_str.split(",")[1]
    
    img_data = base64.b64decode(base64_str)
    nparr = np.frombuffer(img_data, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    if frame is None:
        return state.last_result
        
    # ── Stage 1: Face Detection ─────────────────────────────
    detection = face_detector.detect(frame)
    
    # ── Stage 2: Feature Extraction ─────────────────────────
    features = feature_extractor.extract(detection)
    
    class_name = "ALERT"
    fatigue_score = 0.0
    probs = np.array([1.0, 0.0, 0.0, 0.0, 0.0])
    
    if detection.detected and detection.face_roi is not None:
        # Run CNN
        class_name, confidence, probs = cnn.classify(detection.face_roi)
        fatigue_score = cnn.get_fatigue_score(probs)
        
    # Temporal LSTM
    lstm.add_observation(features.to_array())
    trend, trend_conf, ms_prob, attn = lstm.predict()
    
    if ms_prob > 0.7:
        state.last_result["microsleep_events"] += 1
        
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
        detection_confidence=detection.confidence
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
    
    # Convert overlay to base64
    _, buffer = cv2.imencode('.jpg', overlay, [cv2.IMWRITE_JPEG_QUALITY, 60])
    overlay_b64 = "data:image/jpeg;base64," + base64.b64encode(buffer).decode('utf-8')
    
    # Time formats
    elapsed_seconds = int(time.time() - state.start_time)
    hours = elapsed_seconds // 3600
    minutes = (elapsed_seconds % 3600) // 60
    
    # Add dummy 8 hours for realism
    duty_dur = f"{(hours + 8):02d}h {(minutes + 54):02d}m"
    cont_dur = f"{(hours + 2):02d}h {(minutes + 18):02d}m"
    
    current_time_str = datetime.datetime.now().strftime("%H:%M:%S")
    
    # Alerts Logic based on real features
    if features.eyes_closed and (len(state.alerts) == 0 or state.alerts[0]["t"] != "Extended eye closure detected"):
        state.alerts.insert(0, {"t": "Extended eye closure detected", "time": current_time_str, "tone": "critical"})
    elif features.is_yawning and (len(state.alerts) == 0 or state.alerts[0]["t"] != "Yawning sequence observed"):
        state.alerts.insert(0, {"t": "Yawning sequence observed", "time": current_time_str, "tone": "warning"})
    elif features.head_drooping and (len(state.alerts) == 0 or state.alerts[0]["t"] != "Head drooping detected"):
        state.alerts.insert(0, {"t": "Head drooping detected", "time": current_time_str, "tone": "critical"})
        
    if len(state.alerts) > 4:
        state.alerts = state.alerts[:4]
        
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
        "microsleep_events": state.last_result["microsleep_events"],
        "hrv": 18,
        "posture_sway": posture,
        "duty_duration": duty_dur,
        "continuous_driving": cont_dur,
        "alerts": state.alerts,
        "image": overlay_b64
    }
    
    state.last_result.update(result)
    return result

if __name__ == "__main__":
    # Start Uvicorn server
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
