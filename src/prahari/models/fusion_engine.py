"""
PRAHARI — Stage 5: Multi-Modal Fusion Engine

Combines all signal sources with configurable weights to produce the
Crew Alertness Index (CAI): 0 (fully alert) → 100 (critical fatigue).

Signal sources:
  - CNN classification probabilities
  - PERCLOS
  - EAR (inverted)
  - MAR (yawn indicator)
  - Blink pattern abnormality score
  - Head pose deviation
  - Temporal trend from LSTM
  - Microsleep probability from LSTM

Uses Exponential Moving Average (EMA) for smooth transitions.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass
from typing import Optional

import numpy as np

logger = logging.getLogger("prahari.models.fusion")


@dataclass
class FusionResult:
    """Output of the multi-modal fusion engine."""

    # Crew Alertness Index: 0 = fully alert, 100 = critical fatigue
    cai: float = 0.0
    # Smoothed CAI after EMA
    cai_smoothed: float = 0.0
    # Inverted score: 100 = fully alert, 0 = critical
    alertness_score: float = 100.0
    # Confidence in the fusion result (0–1)
    confidence: float = 0.0
    # Timestamp
    timestamp: float = 0.0

    # Individual component scores (0–100 scale, for dashboard)
    component_scores: dict[str, float] = None

    def __post_init__(self):
        if self.component_scores is None:
            self.component_scores = {}


class FusionEngine:
    """
    Multi-modal fusion engine that combines all fatigue signals
    into a single Crew Alertness Index (CAI).
    """

    # Normal ranges for baseline comparison
    NORMAL_BLINK_RATE = (15, 20)  # blinks/minute
    NORMAL_EAR = (0.25, 0.35)
    NORMAL_HEAD_PITCH = (-10, 10)  # degrees

    def __init__(
        self,
        weights: Optional[dict[str, float]] = None,
        ema_alpha: float = 0.3,
        history_size: int = 300,  # 5 minutes at 1 Hz
    ):
        # Fusion weights — must sum to ~1.0
        self.weights = weights or {
            "cnn_classification": 0.25,
            "perclos": 0.20,
            "ear": 0.10,
            "mar": 0.08,
            "blink_pattern": 0.07,
            "head_pose": 0.10,
            "temporal_trend": 0.12,
            "microsleep_prob": 0.08,
        }

        total_weight = sum(self.weights.values())
        if abs(total_weight - 1.0) > 0.01:
            logger.warning("Fusion weights sum to %.3f, normalizing to 1.0", total_weight)
            self.weights = {k: v / total_weight for k, v in self.weights.items()}

        self.ema_alpha = ema_alpha
        self._smoothed_cai: Optional[float] = None

        # History for trend analysis
        self._cai_history: deque[tuple[float, float]] = deque(maxlen=history_size)

        logger.info("FusionEngine initialized — weights=%s, ema_alpha=%.2f", self.weights, ema_alpha)

    def _score_cnn(self, cnn_probs: np.ndarray) -> float:
        """
        Convert CNN class probabilities to 0–100 score.
        Weighted: ALERT=0, SLIGHT=25, FATIGUED=50, SEVERE=75, MICROSLEEP=100
        """
        if cnn_probs is None or len(cnn_probs) < 5:
            return 0.0
        class_weights = np.array([0.0, 25.0, 50.0, 75.0, 100.0])
        return float(np.clip(np.dot(cnn_probs, class_weights), 0, 100))

    def _score_perclos(self, perclos: float) -> float:
        """
        Convert PERCLOS to 0–100 score.
        Normal: <0.15, Drowsy: 0.15–0.30, Severe: >0.30
        """
        if perclos <= 0.10:
            return 0.0
        elif perclos <= 0.20:
            return (perclos - 0.10) / 0.10 * 50.0  # Linear 0–50
        elif perclos <= 0.40:
            return 50.0 + (perclos - 0.20) / 0.20 * 40.0  # 50–90
        else:
            return 90.0 + min((perclos - 0.40) / 0.20 * 10.0, 10.0)  # 90–100

    def _score_ear(self, ear: float) -> float:
        """
        Convert EAR to 0–100 score (inverted — lower EAR = higher fatigue).
        Normal EAR ~0.25–0.35
        """
        if ear >= 0.30:
            return 0.0
        elif ear >= 0.20:
            return (0.30 - ear) / 0.10 * 60.0  # 0–60
        elif ear >= 0.10:
            return 60.0 + (0.20 - ear) / 0.10 * 30.0  # 60–90
        else:
            return 90.0 + min((0.10 - ear) / 0.10 * 10.0, 10.0)  # 90–100

    def _score_mar(self, mar: float, is_yawning: bool) -> float:
        """
        Convert MAR / yawn state to 0–100 score.
        """
        if is_yawning:
            return min(70.0 + mar * 30.0, 100.0)
        elif mar > 0.5:
            return mar * 40.0
        return 0.0

    def _score_blink_pattern(
        self, blink_rate: float, avg_duration: float, closure_duration: float
    ) -> float:
        """
        Score blink pattern abnormality (0–100).
        Abnormal: very low (<10/min) or very high (>25/min) blink rate,
        long blinks, or extended eye closure.
        """
        score = 0.0

        # Blink rate abnormality
        if blink_rate < 10:
            score += (10 - blink_rate) * 3.0  # Low blink rate → fatigue
        elif blink_rate > 25:
            score += (blink_rate - 25) * 2.0  # Very high rate → fighting drowsiness

        # Long blink duration
        if avg_duration > 0.3:
            score += (avg_duration - 0.3) * 100.0

        # Extended eye closure (not a normal blink)
        if closure_duration > 0.5:
            score += min(closure_duration * 30.0, 50.0)

        return float(np.clip(score, 0, 100))

    def _score_head_pose(
        self, pitch: float, yaw: float, head_drooping: bool
    ) -> float:
        """
        Score head pose deviation (0–100).
        """
        score = 0.0

        # Head drooping is a strong signal
        if head_drooping:
            score += 70.0

        # Pitch deviation (looking down)
        if abs(pitch) > 10:
            score += min((abs(pitch) - 10) * 2.0, 30.0)

        # Yaw deviation (looking away — distraction)
        if abs(yaw) > 20:
            score += min((abs(yaw) - 20) * 1.5, 20.0)

        return float(np.clip(score, 0, 100))

    def _score_temporal_trend(
        self, trend_name: str, trend_confidence: float
    ) -> float:
        """
        Score temporal trend (0–100).
        DEGRADING trend with high confidence → high score.
        """
        if trend_name == "IMPROVING":
            return max(0.0, 20.0 - trend_confidence * 20.0)
        elif trend_name == "STABLE":
            return 30.0
        else:  # DEGRADING
            return 50.0 + trend_confidence * 50.0

    def _score_microsleep(self, microsleep_prob: float) -> float:
        """
        Convert microsleep probability to 0–100 score.
        This is the most critical signal.
        """
        return float(np.clip(microsleep_prob * 100.0, 0, 100))

    def fuse(
        self,
        cnn_probs: Optional[np.ndarray] = None,
        perclos: float = 0.0,
        ear_avg: float = 0.3,
        mar: float = 0.0,
        is_yawning: bool = False,
        blink_rate: float = 15.0,
        avg_blink_duration: float = 0.15,
        current_closure_duration: float = 0.0,
        head_pitch: float = 0.0,
        head_yaw: float = 0.0,
        head_drooping: bool = False,
        temporal_trend: str = "STABLE",
        temporal_confidence: float = 0.5,
        microsleep_prob: float = 0.0,
        face_detected: bool = True,
        detection_confidence: float = 1.0,
    ) -> FusionResult:
        """
        Fuse all signal sources into a single Crew Alertness Index.

        Returns:
            FusionResult with CAI score, smoothed CAI, and component breakdown.
        """
        now = time.time()

        # Compute individual component scores
        scores = {
            "cnn_classification": self._score_cnn(cnn_probs),
            "perclos": self._score_perclos(perclos),
            "ear": self._score_ear(ear_avg),
            "mar": self._score_mar(mar, is_yawning),
            "blink_pattern": self._score_blink_pattern(
                blink_rate, avg_blink_duration, current_closure_duration
            ),
            "head_pose": self._score_head_pose(head_pitch, head_yaw, head_drooping),
            "temporal_trend": self._score_temporal_trend(temporal_trend, temporal_confidence),
            "microsleep_prob": self._score_microsleep(microsleep_prob),
        }

        # Weighted sum → raw CAI
        raw_cai = sum(
            scores[key] * self.weights.get(key, 0.0) for key in scores
        )

        # Override: if face not detected, escalate
        if not face_detected:
            raw_cai = max(raw_cai, 80.0)

        # Override: if extended eye closure > 2s, force critical
        if current_closure_duration > 2.0:
            raw_cai = max(raw_cai, 95.0)

        raw_cai = float(np.clip(raw_cai, 0, 100))

        # Apply EMA smoothing
        if self._smoothed_cai is None:
            smoothed = raw_cai
        else:
            smoothed = self.ema_alpha * raw_cai + (1 - self.ema_alpha) * self._smoothed_cai

        self._smoothed_cai = smoothed

        # Confidence based on face detection and signal quality
        confidence = detection_confidence * (0.5 + 0.5 * face_detected)

        # Store in history
        self._cai_history.append((now, smoothed))

        result = FusionResult(
            cai=raw_cai,
            cai_smoothed=smoothed,
            alertness_score=100.0 - smoothed,
            confidence=confidence,
            timestamp=now,
            component_scores=scores,
        )

        return result

    def get_trend(self, window_seconds: float = 60.0) -> str:
        """
        Get the CAI trend over the last N seconds from history.

        Returns: "IMPROVING", "STABLE", or "DEGRADING"
        """
        if len(self._cai_history) < 10:
            return "STABLE"

        now = time.time()
        cutoff = now - window_seconds
        recent = [(t, v) for t, v in self._cai_history if t > cutoff]

        if len(recent) < 5:
            return "STABLE"

        # Simple linear regression on CAI values
        times = np.array([t - recent[0][0] for t, _ in recent])
        values = np.array([v for _, v in recent])

        if len(times) > 1:
            slope = np.polyfit(times, values, 1)[0]
            if slope > 0.5:
                return "DEGRADING"
            elif slope < -0.5:
                return "IMPROVING"

        return "STABLE"

    def reset(self) -> None:
        """Reset smoothing and history."""
        self._smoothed_cai = None
        self._cai_history.clear()
        logger.info("FusionEngine reset")
