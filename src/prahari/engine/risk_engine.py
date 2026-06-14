"""
PRAHARI — Stage 6: Risk Classification Engine

Classifies the Crew Alertness Index (CAI) into discrete risk levels
and manages trigger conditions for alerts and emergency interventions.

Risk Levels:
  LOW (0–40)      → Green  → Normal monitoring
  MEDIUM (41–70)  → Yellow → Increased monitoring
  HIGH (71–85)    → Orange → Audible alert to operator
  CRITICAL (86+)  → Red    → Control room alert + emergency

Special Triggers:
  - CAI > 95 for > 5 seconds → Emergency intervention
  - Microsleep (eyes closed > 2s) → Immediate CRITICAL
  - No face for > 10s → CRITICAL (pilot absent/incapacitated)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger("prahari.engine.risk")


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class RiskAssessment:
    """Complete risk assessment output."""

    risk_level: RiskLevel = RiskLevel.LOW
    cai: float = 0.0
    cai_smoothed: float = 0.0
    alertness_score: float = 100.0

    # Alert flags
    should_alert_operator: bool = False
    should_alert_control_room: bool = False
    should_emergency_intervene: bool = False

    # Trigger reasons
    trigger_reasons: list[str] = field(default_factory=list)

    # Timing
    timestamp: float = 0.0
    time_at_current_level: float = 0.0
    time_in_critical: float = 0.0

    # Colors for UI
    @property
    def color_hex(self) -> str:
        return {
            RiskLevel.LOW: "#22c55e",       # Green
            RiskLevel.MEDIUM: "#eab308",    # Yellow
            RiskLevel.HIGH: "#f97316",      # Orange
            RiskLevel.CRITICAL: "#ef4444",  # Red
        }[self.risk_level]

    @property
    def color_name(self) -> str:
        return {
            RiskLevel.LOW: "green",
            RiskLevel.MEDIUM: "yellow",
            RiskLevel.HIGH: "orange",
            RiskLevel.CRITICAL: "red",
        }[self.risk_level]


class RiskEngine:
    """
    Classifies fatigue severity and determines alert actions
    based on CAI thresholds and special trigger conditions.
    """

    def __init__(
        self,
        low_max: int = 40,
        medium_max: int = 70,
        high_max: int = 85,
        critical_min: int = 86,
        microsleep_eye_closed_seconds: float = 2.0,
        face_absent_seconds: float = 10.0,
        emergency_cai_threshold: int = 95,
        emergency_duration_seconds: int = 5,
    ):
        self.low_max = low_max
        self.medium_max = medium_max
        self.high_max = high_max
        self.critical_min = critical_min
        self.microsleep_eye_closed_seconds = microsleep_eye_closed_seconds
        self.face_absent_seconds = face_absent_seconds
        self.emergency_cai_threshold = emergency_cai_threshold
        self.emergency_duration_seconds = emergency_duration_seconds

        # State tracking
        self._current_level: RiskLevel = RiskLevel.LOW
        self._level_start_time: float = time.time()
        self._critical_start_time: Optional[float] = None
        self._last_assessment: Optional[RiskAssessment] = None

        # Event counters (rolling)
        self._microsleep_count: int = 0
        self._total_assessments: int = 0

        logger.info(
            "RiskEngine initialized — thresholds: LOW≤%d, MED≤%d, HIGH≤%d, CRIT≥%d",
            low_max, medium_max, high_max, critical_min,
        )

    def _classify_level(self, cai: float) -> RiskLevel:
        """Map CAI value to risk level."""
        if cai <= self.low_max:
            return RiskLevel.LOW
        elif cai <= self.medium_max:
            return RiskLevel.MEDIUM
        elif cai <= self.high_max:
            return RiskLevel.HIGH
        else:
            return RiskLevel.CRITICAL

    def assess(
        self,
        cai: float,
        cai_smoothed: float,
        current_closure_duration: float = 0.0,
        face_absent_duration: float = 0.0,
        microsleep_prob: float = 0.0,
        head_drooping: bool = False,
    ) -> RiskAssessment:
        """
        Perform a complete risk assessment.

        Args:
            cai: Raw Crew Alertness Index (0–100)
            cai_smoothed: EMA-smoothed CAI
            current_closure_duration: How long eyes have been closed (seconds)
            face_absent_duration: How long face has been missing (seconds)
            microsleep_prob: LSTM microsleep probability (0–1)
            head_drooping: Whether head droop is detected

        Returns:
            RiskAssessment with level, alerts, and trigger reasons.
        """
        now = time.time()
        self._total_assessments += 1

        assessment = RiskAssessment(
            cai=cai,
            cai_smoothed=cai_smoothed,
            alertness_score=100.0 - cai_smoothed,
            timestamp=now,
        )

        # ── Base classification from CAI ────────────────────────
        base_level = self._classify_level(cai_smoothed)
        triggers: list[str] = []

        # ── Special trigger overrides ───────────────────────────

        # Microsleep: eyes closed > threshold
        if current_closure_duration > self.microsleep_eye_closed_seconds:
            base_level = RiskLevel.CRITICAL
            self._microsleep_count += 1
            triggers.append(
                f"MICROSLEEP: Eyes closed for {current_closure_duration:.1f}s"
            )

        # Face absent: pilot may be incapacitated
        if face_absent_duration > self.face_absent_seconds:
            base_level = RiskLevel.CRITICAL
            triggers.append(
                f"FACE ABSENT: No face detected for {face_absent_duration:.1f}s"
            )

        # Helper for risk level severity comparison
        def risk_severity(level: RiskLevel) -> int:
            return {
                RiskLevel.LOW: 0,
                RiskLevel.MEDIUM: 1,
                RiskLevel.HIGH: 2,
                RiskLevel.CRITICAL: 3,
            }[level]

        # High microsleep probability from LSTM
        if microsleep_prob > 0.7:
            if risk_severity(base_level) < risk_severity(RiskLevel.HIGH):
                base_level = RiskLevel.HIGH
            triggers.append(
                f"MICROSLEEP RISK: {microsleep_prob:.0%} probability"
            )

        # Head drooping
        if head_drooping:
            if risk_severity(base_level) < risk_severity(RiskLevel.HIGH):
                base_level = RiskLevel.HIGH
            triggers.append("HEAD DROOP: Sustained downward head tilt")

        # ── Track level transitions ─────────────────────────────
        if base_level != self._current_level:
            self._current_level = base_level
            self._level_start_time = now

        assessment.risk_level = base_level
        assessment.time_at_current_level = now - self._level_start_time
        assessment.trigger_reasons = triggers

        # ── Determine alert actions ─────────────────────────────

        # HIGH → alert operator (audible)
        if base_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            assessment.should_alert_operator = True

        # CRITICAL → alert control room
        if base_level == RiskLevel.CRITICAL:
            assessment.should_alert_control_room = True
            if self._critical_start_time is None:
                self._critical_start_time = now
            assessment.time_in_critical = now - self._critical_start_time
        else:
            self._critical_start_time = None
            assessment.time_in_critical = 0.0

        # Emergency intervention: CRITICAL + CAI>95 for > N seconds
        if (
            base_level == RiskLevel.CRITICAL
            and cai_smoothed > self.emergency_cai_threshold
            and assessment.time_in_critical > self.emergency_duration_seconds
        ):
            assessment.should_emergency_intervene = True
            triggers.append(
                f"EMERGENCY: CAI>{self.emergency_cai_threshold} for "
                f"{assessment.time_in_critical:.0f}s"
            )

        self._last_assessment = assessment
        return assessment

    @property
    def microsleep_count(self) -> int:
        """Total microsleep events detected in this session."""
        return self._microsleep_count

    @property
    def current_level(self) -> RiskLevel:
        return self._current_level

    def reset(self) -> None:
        """Reset all state."""
        self._current_level = RiskLevel.LOW
        self._level_start_time = time.time()
        self._critical_start_time = None
        self._microsleep_count = 0
        self._total_assessments = 0
        logger.info("RiskEngine reset")
