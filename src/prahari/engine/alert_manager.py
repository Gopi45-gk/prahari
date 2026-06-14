"""
PRAHARI — Alert Manager

Dispatches alerts based on risk assessments:
  - Visual alerts via WebSocket to the dashboard
  - Audio alerts via system playback
  - REST API notifications to external control room systems

Includes cooldown management, alert escalation, and notification history.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import aiohttp

from prahari.engine.risk_engine import RiskAssessment, RiskLevel

logger = logging.getLogger("prahari.engine.alerts")


@dataclass
class AlertEvent:
    """Record of an alert that was dispatched."""

    risk_level: RiskLevel
    cai: float
    alertness_score: float
    trigger_reasons: list[str]
    timestamp: float
    datetime_iso: str
    alert_types: list[str]  # ["visual", "audio", "api"]
    crew_id: str = "LP001"


class AlertManager:
    """
    Manages alert dispatch with cooldown, escalation, and multi-channel delivery.
    """

    def __init__(
        self,
        crew_id: str = "LP001",
        cooldown_seconds: int = 30,
        audio_enabled: bool = True,
        visual_enabled: bool = True,
        api_enabled: bool = False,
        api_endpoint: str = "http://localhost:9000/api/v1/fatigue-alert",
        api_timeout: int = 5,
    ):
        self.crew_id = crew_id
        self.cooldown_seconds = cooldown_seconds
        self.audio_enabled = audio_enabled
        self.visual_enabled = visual_enabled
        self.api_enabled = api_enabled
        self.api_endpoint = api_endpoint
        self.api_timeout = api_timeout

        # Cooldown tracking per risk level
        self._last_alert_time: dict[RiskLevel, float] = {}

        # Alert history (last 1 hour)
        self._history: deque[AlertEvent] = deque(maxlen=1000)

        # Stats
        self._total_alerts: int = 0

        logger.info(
            "AlertManager initialized — crew=%s, cooldown=%ds, audio=%s, api=%s",
            crew_id, cooldown_seconds, audio_enabled, api_enabled,
        )



    def _is_cooled_down(self, level: RiskLevel) -> bool:
        """Check if enough time has passed since the last alert of this level."""
        last = self._last_alert_time.get(level)
        if last is None:
            return True
        return (time.time() - last) >= self.cooldown_seconds

    def should_alert(self, assessment: RiskAssessment) -> bool:
        """
        Determine if an alert should fire based on risk level and cooldown.

        Only alerts for HIGH and CRITICAL levels.
        CRITICAL with emergency bypass cooldown.
        """
        if assessment.risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM):
            return False

        if assessment.should_emergency_intervene:
            return True  # Emergency bypasses cooldown

        return self._is_cooled_down(assessment.risk_level)

    async def dispatch(self, assessment: RiskAssessment) -> Optional[AlertEvent]:
        """
        Dispatch alerts based on the risk assessment.

        Args:
            assessment: RiskAssessment from the RiskEngine

        Returns:
            AlertEvent if an alert was dispatched, None otherwise
        """
        if not self.should_alert(assessment):
            return None

        now = time.time()
        dt = datetime.now(timezone.utc)
        alert_types: list[str] = []

        # Create alert event
        event = AlertEvent(
            risk_level=assessment.risk_level,
            cai=assessment.cai_smoothed,
            alertness_score=assessment.alertness_score,
            trigger_reasons=assessment.trigger_reasons,
            timestamp=now,
            datetime_iso=dt.isoformat(),
            alert_types=[],
            crew_id=self.crew_id,
        )

        # Visual alert via console
        if self.visual_enabled:
            logger.warning("🚨 VISUAL ALERT: %s", assessment.risk_level.value)
            alert_types.append("visual")

        # Audio alert
        if self.audio_enabled and assessment.should_alert_operator:
            self._trigger_audio_alert(assessment)
            alert_types.append("audio")

        # API notification
        if self.api_enabled and assessment.should_alert_control_room:
            await self._send_api_alert(assessment, event)
            alert_types.append("api")

        event.alert_types = alert_types
        self._history.append(event)
        self._last_alert_time[assessment.risk_level] = now
        self._total_alerts += 1

        logger.warning(
            "🚨 ALERT [%s] CAI=%.1f — %s — via %s",
            assessment.risk_level.value,
            assessment.cai_smoothed,
            "; ".join(assessment.trigger_reasons) or "threshold exceeded",
            ", ".join(alert_types),
        )

        return event



    def _trigger_audio_alert(self, assessment: RiskAssessment) -> None:
        """
        Trigger an audio alert. Uses winsound beep on Windows for distinct alerts.
        """
        try:
            import platform
            is_windows = platform.system() == "Windows"
            
            if is_windows:
                import winsound
                
            if assessment.should_emergency_intervene:
                logger.critical("🔊 EMERGENCY AUDIO ALERT — CRITICAL FATIGUE")
                if is_windows:
                    for _ in range(5):
                        winsound.Beep(2000, 200)
                        time.sleep(0.05)
                else:
                    print("\a", end="", flush=True)
            elif assessment.risk_level == RiskLevel.CRITICAL:
                logger.error("🔊 AUDIO ALERT — CRITICAL")
                if is_windows:
                    for _ in range(3):
                        winsound.Beep(1500, 300)
                        time.sleep(0.1)
                else:
                    print("\a", end="", flush=True)
            else:
                logger.warning("🔊 AUDIO ALERT — HIGH RISK")
                if is_windows:
                    winsound.Beep(1000, 500)
                else:
                    print("\a", end="", flush=True)
        except Exception as e:
            logger.error("Audio alert failed: %s", e)

    async def _send_api_alert(
        self, assessment: RiskAssessment, event: AlertEvent
    ) -> None:
        """Send alert to external control room API endpoint."""
        payload = {
            "crew_id": self.crew_id,
            "alertness_score": round(assessment.alertness_score),
            "fatigue_score": round(assessment.cai_smoothed),
            "risk_level": assessment.risk_level.value,
            "timestamp": event.datetime_iso,
            "trigger_reasons": assessment.trigger_reasons,
            "emergency": assessment.should_emergency_intervene,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_endpoint,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.api_timeout),
                ) as response:
                    if response.status == 200:
                        logger.info("API alert sent successfully to %s", self.api_endpoint)
                    else:
                        logger.error(
                            "API alert failed — status %d: %s",
                            response.status,
                            await response.text(),
                        )
        except Exception as e:
            logger.error("API alert dispatch failed: %s", e)



    def get_history(self, limit: int = 100) -> list[dict]:
        """Get recent alert history as serializable dicts."""
        history = list(self._history)[-limit:]
        return [
            {
                "risk_level": e.risk_level.value,
                "cai": round(e.cai, 1),
                "alertness_score": round(e.alertness_score, 1),
                "trigger_reasons": e.trigger_reasons,
                "timestamp": e.datetime_iso,
                "alert_types": e.alert_types,
                "crew_id": e.crew_id,
            }
            for e in history
        ]

    @property
    def total_alerts(self) -> int:
        return self._total_alerts

    def reset(self) -> None:
        """Reset alert state."""
        self._last_alert_time.clear()
        self._history.clear()
        self._total_alerts = 0
        logger.info("AlertManager reset")
