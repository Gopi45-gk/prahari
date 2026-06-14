"""
PRAHARI — Inference Pipeline Orchestrator

End-to-end real-time processing pipeline that orchestrates all 6 stages:
  1. Camera capture → frame acquisition
  2. Face detection → MediaPipe FaceMesh
  3. Feature extraction → EAR, MAR, PERCLOS, head pose
  4. CNN classification → fatigue level
  5. Temporal analysis → LSTM trend + microsleep prediction
  6. Fusion + Risk → CAI score + risk level + alerts

Runs in a background thread with frame timing and graceful degradation.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import cv2
import numpy as np
import torch

from prahari.config import Settings
from prahari.detection.face_detector import FaceDetection, FaceDetector
from prahari.detection.feature_extractor import FeatureExtractor, FeatureVector
from prahari.engine.alert_manager import AlertManager
from prahari.engine.risk_engine import RiskAssessment, RiskEngine, RiskLevel
from prahari.models.fatigue_cnn import FatigueCNNInference
from prahari.models.fusion_engine import FusionEngine, FusionResult
from prahari.models.temporal_lstm import TemporalLSTMInference

logger = logging.getLogger("prahari.engine.pipeline")


@dataclass
class PipelineState:
    """Snapshot of the pipeline's current state — pushed to dashboard each frame."""

    # Timing
    timestamp: float = 0.0
    fps: float = 0.0
    latency_ms: float = 0.0

    # Detection
    face_detected: bool = False
    detection_confidence: float = 0.0

    # Features
    ear_avg: float = 0.0
    mar: float = 0.0
    perclos: float = 0.0
    blink_rate: float = 0.0
    avg_blink_duration: float = 0.0
    current_closure_duration: float = 0.0
    yawn_count: int = 0
    head_pitch: float = 0.0
    head_yaw: float = 0.0
    head_roll: float = 0.0
    head_drooping: bool = False

    # Classification
    cnn_class: str = "ALERT"
    cnn_confidence: float = 0.0
    cnn_probs: list[float] = field(default_factory=lambda: [1.0, 0.0, 0.0, 0.0, 0.0])

    # Temporal
    temporal_trend: str = "STABLE"
    temporal_confidence: float = 0.5
    microsleep_prob: float = 0.0

    # Fusion
    cai: float = 0.0
    cai_smoothed: float = 0.0
    alertness_score: float = 100.0
    fusion_confidence: float = 0.0

    # Risk
    risk_level: str = "LOW"
    risk_color: str = "#22c55e"
    microsleep_events: int = 0



    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON transmission."""
        return {
            "timestamp": float(self.timestamp),
            "fps": round(float(self.fps), 1),
            "latency_ms": round(float(self.latency_ms), 1),
            "face_detected": bool(self.face_detected),
            "detection_confidence": round(float(self.detection_confidence), 3),
            "ear_avg": round(float(self.ear_avg), 4),
            "mar": round(float(self.mar), 4),
            "perclos": round(float(self.perclos), 4),
            "blink_rate": round(float(self.blink_rate), 1),
            "avg_blink_duration": round(float(self.avg_blink_duration), 3),
            "current_closure_duration": round(float(self.current_closure_duration), 2),
            "yawn_count": int(self.yawn_count),
            "head_pitch": round(float(self.head_pitch), 1),
            "head_yaw": round(float(self.head_yaw), 1),
            "head_roll": round(float(self.head_roll), 1),
            "head_drooping": bool(self.head_drooping),
            "cnn_class": str(self.cnn_class),
            "cnn_confidence": round(float(self.cnn_confidence), 3),
            "cnn_probs": [round(float(p), 4) for p in self.cnn_probs],
            "temporal_trend": str(self.temporal_trend),
            "temporal_confidence": round(float(self.temporal_confidence), 3),
            "microsleep_prob": round(float(self.microsleep_prob), 4),
            "cai": round(float(self.cai), 1),
            "cai_smoothed": round(float(self.cai_smoothed), 1),
            "alertness_score": round(float(self.alertness_score), 1),
            "fusion_confidence": round(float(self.fusion_confidence), 3),
            "risk_level": self.risk_level,
            "risk_color": self.risk_color,
            "microsleep_events": self.microsleep_events,
        }


class FatiguePipeline:
    """
    Main inference pipeline — orchestrates all 6 stages in real-time.
    Runs as a background thread, pushing state updates via the AlertManager.
    """

    def __init__(self, settings: Settings, alert_manager: AlertManager):
        self.settings = settings
        self.alert_manager = alert_manager

        # Resolve device
        self.device = settings.device.resolved_device
        self.use_fp16 = settings.device.use_fp16
        logger.info("Pipeline device: %s (FP16=%s)", self.device, self.use_fp16)

        # ── Initialize all stages ───────────────────────────────

        # Stage 1: Face Detector
        self.face_detector = FaceDetector(
            min_detection_confidence=settings.detection.min_detection_confidence,
            min_tracking_confidence=settings.detection.min_tracking_confidence,
            clahe_clip_limit=settings.detection.clahe_clip_limit,
            clahe_grid_size=settings.detection.clahe_grid_size,
            roi_size=settings.classifier.input_size,
        )

        # Stage 2: Feature Extractor
        self.feature_extractor = FeatureExtractor(
            ear_threshold=settings.features.ear_threshold,
            ear_consec_frames=settings.features.ear_consec_frames,
            mar_threshold=settings.features.mar_threshold,
            mar_consec_frames=settings.features.mar_consec_frames,
            perclos_window=settings.features.perclos_window,
            blink_min_duration=settings.features.blink_min_duration,
            blink_max_duration=settings.features.blink_max_duration,
            head_pitch_threshold=settings.features.head_pitch_threshold,
            head_yaw_threshold=settings.features.head_yaw_threshold,
            head_droop_duration=settings.features.head_droop_duration,
            blink_rate_window=settings.features.blink_rate_window,
            yawn_rate_window=settings.features.yawn_rate_window,
            fps=settings.camera.fps,
        )

        # Stage 3: CNN Fatigue Classifier
        self.cnn_inference = FatigueCNNInference(
            model_path=settings.models.fatigue_cnn,
            device=self.device,
            use_fp16=self.use_fp16,
        )

        # Stage 4: Temporal LSTM
        self.temporal_inference = TemporalLSTMInference(
            model_path=settings.models.temporal_lstm,
            device=self.device,
            sequence_length=settings.temporal.sequence_length,
            input_size=16,
            hidden_size=settings.temporal.hidden_size,
            num_layers=settings.temporal.num_layers,
        )

        # Stage 5: Fusion Engine
        fusion_weights = {
            "cnn_classification": settings.fusion.weights.cnn_classification,
            "perclos": settings.fusion.weights.perclos,
            "ear": settings.fusion.weights.ear,
            "mar": settings.fusion.weights.mar,
            "blink_pattern": settings.fusion.weights.blink_pattern,
            "head_pose": settings.fusion.weights.head_pose,
            "temporal_trend": settings.fusion.weights.temporal_trend,
            "microsleep_prob": settings.fusion.weights.microsleep_prob,
        }
        self.fusion_engine = FusionEngine(
            weights=fusion_weights,
            ema_alpha=settings.fusion.ema_alpha,
        )

        # Stage 6: Risk Engine
        self.risk_engine = RiskEngine(
            low_max=settings.risk.low_max,
            medium_max=settings.risk.medium_max,
            high_max=settings.risk.high_max,
            critical_min=settings.risk.critical_min,
            microsleep_eye_closed_seconds=settings.risk.microsleep_eye_closed_seconds,
            face_absent_seconds=settings.risk.face_absent_seconds,
            emergency_cai_threshold=settings.risk.emergency_cai_threshold,
            emergency_duration_seconds=settings.risk.emergency_duration_seconds,
        )

        # ── Camera ──────────────────────────────────────────────
        self._cap: Optional[cv2.VideoCapture] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # ── State ───────────────────────────────────────────────
        self._current_state = PipelineState()
        self._frame_count = 0
        self._fps_counter_start = time.time()
        self._fps_frame_count = 0

        # Temporal observation sample timer (1 Hz)
        self._last_temporal_sample = 0.0

        logger.info("FatiguePipeline fully initialized")

    def _open_camera(self) -> bool:
        """Open the video capture source."""
        source = self.settings.camera.source
        logger.info("Opening camera source: %s", source)

        self._cap = cv2.VideoCapture(source)

        if not self._cap.isOpened():
            logger.error("Failed to open camera source: %s", source)
            return False

        # Set camera properties
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.settings.camera.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.settings.camera.height)
        self._cap.set(cv2.CAP_PROP_FPS, self.settings.camera.fps)

        actual_w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = self._cap.get(cv2.CAP_PROP_FPS)

        logger.info("Camera opened: %dx%d @ %.0f FPS", actual_w, actual_h, actual_fps)
        return True



    def _compute_fps(self) -> float:
        """Compute rolling FPS."""
        self._fps_frame_count += 1
        elapsed = time.time() - self._fps_counter_start
        if elapsed >= 1.0:
            fps = self._fps_frame_count / elapsed
            self._fps_frame_count = 0
            self._fps_counter_start = time.time()
            return fps
        return self._current_state.fps  # Return last known

    def _process_frame(self, frame: np.ndarray) -> PipelineState:
        """
        Process a single frame through all 6 pipeline stages.

        Args:
            frame: BGR image from camera

        Returns:
            PipelineState with all computed metrics
        """
        t_start = time.time()
        state = PipelineState(timestamp=t_start)

        # ── Stage 1: Face Detection ─────────────────────────────
        detection: FaceDetection = self.face_detector.detect(frame)
        state.face_detected = detection.detected
        state.detection_confidence = detection.confidence

        # ── Stage 2: Feature Extraction ─────────────────────────
        features: FeatureVector = self.feature_extractor.extract(detection)
        state.ear_avg = features.ear_avg
        state.mar = features.mar
        state.perclos = features.perclos
        state.blink_rate = features.blink_rate
        state.avg_blink_duration = features.avg_blink_duration
        state.current_closure_duration = features.current_closure_duration
        state.yawn_count = features.yawn_count
        state.head_pitch = features.head_pitch
        state.head_yaw = features.head_yaw
        state.head_roll = features.head_roll
        state.head_drooping = features.head_drooping

        # ── Stage 3: CNN Classification ─────────────────────────
        cnn_class = "ALERT"
        cnn_confidence = 0.0
        cnn_probs = np.array([1.0, 0.0, 0.0, 0.0, 0.0])

        if detection.detected and detection.face_roi is not None:
            try:
                cnn_class, cnn_confidence, cnn_probs = self.cnn_inference.classify(
                    detection.face_roi
                )

            except Exception as e:
                logger.debug("CNN inference failed: %s", e)

        state.cnn_class = cnn_class
        state.cnn_confidence = cnn_confidence
        state.cnn_probs = cnn_probs.tolist()

        # ── Stage 4: Temporal Analysis ──────────────────────────
        # Sample at 1 Hz for LSTM
        now = time.time()
        if now - self._last_temporal_sample >= 1.0:
            feature_array = features.to_array()
            self.temporal_inference.add_observation(feature_array)
            self._last_temporal_sample = now

        trend = "STABLE"
        trend_conf = 0.5
        ms_prob = 0.0

        if self.temporal_inference.is_ready():
            try:
                trend, trend_conf, ms_prob, _ = self.temporal_inference.predict()

            except Exception as e:
                logger.debug("Temporal inference failed: %s", e)

        state.temporal_trend = trend
        state.temporal_confidence = trend_conf
        state.microsleep_prob = ms_prob

        # ── Stage 5: Fusion ─────────────────────────────────────
        fusion: FusionResult = self.fusion_engine.fuse(
            cnn_probs=cnn_probs,
            perclos=features.perclos,
            ear_avg=features.ear_avg,
            mar=features.mar,
            is_yawning=features.is_yawning,
            blink_rate=features.blink_rate,
            avg_blink_duration=features.avg_blink_duration,
            current_closure_duration=features.current_closure_duration,
            head_pitch=features.head_pitch,
            head_yaw=features.head_yaw,
            head_drooping=features.head_drooping,
            temporal_trend=trend,
            temporal_confidence=trend_conf,
            microsleep_prob=ms_prob,
            face_detected=features.face_detected or features.face_absent_duration < 1.0,
            detection_confidence=features.detection_confidence,
        )

        state.cai = fusion.cai
        state.cai_smoothed = fusion.cai_smoothed
        state.alertness_score = fusion.alertness_score
        state.fusion_confidence = fusion.confidence

        # ── Stage 6: Risk Assessment ────────────────────────────
        risk: RiskAssessment = self.risk_engine.assess(
            cai=fusion.cai,
            cai_smoothed=fusion.cai_smoothed,
            current_closure_duration=features.current_closure_duration,
            face_absent_duration=features.face_absent_duration,
            microsleep_prob=ms_prob,
            head_drooping=features.head_drooping,
        )

        state.risk_level = risk.risk_level.value
        state.risk_color = risk.color_hex
        state.microsleep_events = self.risk_engine.microsleep_count

        # ── Encode frame with overlay ───────────────────────────
        overlay = self.face_detector.draw_overlay(frame, detection)

        # Draw CAI gauge on overlay
        self._draw_hud(overlay, state)

        # ── Timing ──────────────────────────────────────────────
        state.latency_ms = (time.time() - t_start) * 1000.0
        state.fps = self._compute_fps()

        return state, risk, overlay

    def _draw_hud(self, frame: np.ndarray, state: PipelineState) -> None:
        """Draw heads-up display on the frame overlay."""
        h, w = frame.shape[:2]

        # Semi-transparent background bar at top
        overlay_bar = frame.copy()
        cv2.rectangle(overlay_bar, (0, 0), (w, 50), (0, 0, 0), -1)
        cv2.addWeighted(overlay_bar, 0.5, frame, 0.5, 0, frame)

        # Risk level text
        color = {
            "LOW": (0, 200, 0),
            "MEDIUM": (0, 200, 200),
            "HIGH": (0, 128, 255),
            "CRITICAL": (0, 0, 255),
        }.get(state.risk_level, (255, 255, 255))

        cv2.putText(
            frame,
            f"PRAHARI | CAI: {state.cai_smoothed:.0f} | {state.risk_level}",
            (10, 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            color,
            2,
        )

        # Metrics in bottom-left
        y_offset = h - 120
        metrics = [
            f"EAR: {state.ear_avg:.3f}",
            f"PERCLOS: {state.perclos:.2%}",
            f"Blinks/min: {state.blink_rate:.0f}",
            f"Head Pitch: {state.head_pitch:.1f}°",
            f"FPS: {state.fps:.0f} | Lat: {state.latency_ms:.0f}ms",
        ]

        for i, text in enumerate(metrics):
            cv2.putText(
                frame,
                text,
                (10, y_offset + i * 22),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (200, 200, 200),
                1,
            )

    def _run_loop(self) -> None:
        """Main processing loop — runs in a background thread."""
        logger.info("Pipeline loop started")
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        if not self._open_camera():
            logger.error("Cannot start pipeline — camera failed to open")
            self._running = False
            return

        target_interval = 1.0 / self.settings.camera.fps

        while self._running:
            t_frame_start = time.time()

            ret, frame = self._cap.read()
            if not ret:
                logger.warning("Failed to read frame — retrying")
                time.sleep(0.01)
                continue

            self._frame_count += 1

            # Process the frame
            try:
                state, risk, overlay = self._process_frame(frame)
                self._current_state = state

                # Show frame locally
                cv2.imshow("PRAHARI - ML Fatigue Detection", overlay)
                if cv2.waitKey(1) & 0xFF in (ord('q'), 27):
                    logger.info("Quit signal received from keyboard")
                    self._running = False
                    break

                # Dispatch alerts
                self._loop.run_until_complete(
                    self._async_dispatch(state, risk)
                )

            except Exception as e:
                logger.error("Pipeline processing error: %s", e, exc_info=True)

            # Frame timing — sleep to maintain target FPS
            elapsed = time.time() - t_frame_start
            sleep_time = target_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        # Cleanup
        if self._cap is not None:
            self._cap.release()
        self.face_detector.release()
        cv2.destroyAllWindows()
        logger.info("Pipeline loop stopped after %d frames", self._frame_count)

    async def _async_dispatch(self, state: PipelineState, risk: RiskAssessment) -> None:
        """Dispatch alerts asynchronously."""
        # Dispatch alerts if needed
        await self.alert_manager.dispatch(risk)

    def start(self) -> None:
        """Start the pipeline in a background thread."""
        if self._running:
            logger.warning("Pipeline already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="prahari-pipeline")
        self._thread.start()
        logger.info("Pipeline started in background thread")

    def stop(self) -> None:
        """Stop the pipeline gracefully."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=5)
        logger.info("Pipeline stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def current_state(self) -> PipelineState:
        return self._current_state

    @property
    def frame_count(self) -> int:
        return self._frame_count
