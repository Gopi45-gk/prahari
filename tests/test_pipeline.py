"""
PRAHARI — Tests for Pipeline & Risk Engine

Integration tests for the risk engine and API schemas.
"""

import time

import numpy as np
import pytest

from prahari.engine.risk_engine import RiskAssessment, RiskEngine, RiskLevel


class TestRiskEngine:
    """Tests for the risk classification engine."""

    @pytest.fixture
    def engine(self):
        return RiskEngine(
            low_max=40,
            medium_max=70,
            high_max=85,
            microsleep_eye_closed_seconds=2.0,
            face_absent_seconds=10.0,
        )

    def test_low_risk(self, engine):
        result = engine.assess(cai=20, cai_smoothed=20)
        assert result.risk_level == RiskLevel.LOW
        assert not result.should_alert_operator
        assert not result.should_alert_control_room

    def test_medium_risk(self, engine):
        result = engine.assess(cai=55, cai_smoothed=55)
        assert result.risk_level == RiskLevel.MEDIUM
        assert not result.should_alert_operator

    def test_high_risk(self, engine):
        result = engine.assess(cai=75, cai_smoothed=75)
        assert result.risk_level == RiskLevel.HIGH
        assert result.should_alert_operator
        assert not result.should_alert_control_room

    def test_critical_risk(self, engine):
        result = engine.assess(cai=90, cai_smoothed=90)
        assert result.risk_level == RiskLevel.CRITICAL
        assert result.should_alert_operator
        assert result.should_alert_control_room

    def test_microsleep_override(self, engine):
        result = engine.assess(
            cai=30,  # Low CAI
            cai_smoothed=30,
            current_closure_duration=3.0,  # But eyes closed 3s
        )
        assert result.risk_level == RiskLevel.CRITICAL
        assert "MICROSLEEP" in result.trigger_reasons[0]

    def test_face_absent_override(self, engine):
        result = engine.assess(
            cai=20,
            cai_smoothed=20,
            face_absent_duration=15.0,
        )
        assert result.risk_level == RiskLevel.CRITICAL
        assert "FACE ABSENT" in result.trigger_reasons[0]

    def test_head_droop_override(self, engine):
        result = engine.assess(
            cai=30,
            cai_smoothed=30,
            head_drooping=True,
        )
        assert result.risk_level == RiskLevel.HIGH
        assert "HEAD DROOP" in result.trigger_reasons[0]

    def test_microsleep_count(self, engine):
        assert engine.microsleep_count == 0
        engine.assess(cai=90, cai_smoothed=90, current_closure_duration=3.0)
        assert engine.microsleep_count == 1

    def test_color_properties(self, engine):
        result = engine.assess(cai=20, cai_smoothed=20)
        assert result.color_hex == "#22c55e"
        assert result.color_name == "green"

        result = engine.assess(cai=90, cai_smoothed=90)
        assert result.color_hex == "#ef4444"
        assert result.color_name == "red"


class TestRiskAssessment:
    """Tests for RiskAssessment data class."""

    def test_default_values(self):
        ra = RiskAssessment()
        assert ra.risk_level == RiskLevel.LOW
        assert ra.cai == 0.0
        assert not ra.should_alert_operator
        assert not ra.should_emergency_intervene

    def test_color_mapping(self):
        for level, expected_color in [
            (RiskLevel.LOW, "#22c55e"),
            (RiskLevel.MEDIUM, "#eab308"),
            (RiskLevel.HIGH, "#f97316"),
            (RiskLevel.CRITICAL, "#ef4444"),
        ]:
            ra = RiskAssessment(risk_level=level)
            assert ra.color_hex == expected_color


class TestAPISchemas:
    """Tests for API Pydantic schemas."""

    def test_fatigue_alert_schema(self):
        from prahari.api.schemas import FatigueAlert
        alert = FatigueAlert(
            crew_id="LP001",
            alertness_score=18,
            fatigue_score=92,
            risk_level="CRITICAL",
            timestamp="2026-06-12T10:00:00Z",
        )
        assert alert.crew_id == "LP001"
        assert alert.fatigue_score == 92
        assert alert.risk_level == "CRITICAL"

    def test_status_response(self):
        from prahari.api.schemas import StatusResponse
        # Verify the model accepts all required fields
        status = StatusResponse(
            crew_id="LP001",
            timestamp="2026-06-12T10:00:00Z",
            fps=30.0,
            latency_ms=25.0,
            face_detected=True,
            detection_confidence=0.95,
            ear_avg=0.28,
            mar=0.15,
            perclos=0.08,
            blink_rate=16.0,
            current_closure_duration=0.0,
            yawn_count=0,
            head_pitch=-2.0,
            head_yaw=1.5,
            head_roll=0.0,
            head_drooping=False,
            cnn_class="ALERT",
            cnn_confidence=0.92,
            temporal_trend="STABLE",
            microsleep_prob=0.02,
            cai=12.0,
            cai_smoothed=11.5,
            alertness_score=88.5,
            risk_level="LOW",
            risk_color="#22c55e",
            microsleep_events=0,
        )
        assert status.risk_level == "LOW"


class TestConfig:
    """Tests for configuration loading."""

    def test_default_settings(self):
        from prahari.config import Settings
        settings = Settings()
        assert settings.crew.id == "LP001"
        assert settings.camera.fps == 30
        assert settings.risk.low_max == 40
        assert settings.fusion.ema_alpha == 0.3

    def test_classifier_classes(self):
        from prahari.config import Settings
        settings = Settings()
        assert len(settings.classifier.class_names) == 5
        assert settings.classifier.class_names[0] == "ALERT"
        assert settings.classifier.class_names[4] == "MICROSLEEP"
