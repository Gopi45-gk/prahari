"""
PRAHARI — Fatigue Detection System (Standalone Mode)

Initializes the inference pipeline and manages application lifecycle.
"""

from __future__ import annotations

import logging
import time

from prahari.config import get_settings
from prahari.engine.alert_manager import AlertManager
from prahari.engine.pipeline import FatiguePipeline

# ── Logging Setup ───────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-8s │ %(name)-30s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("prahari.main")


def run():
    """CLI entry point for standalone prahari execution."""
    logger.info("=" * 60)
    logger.info("  PRAHARI — Loco Pilot Fatigue Detection System")
    logger.info("  Starting up (Standalone Mode)...")
    logger.info("=" * 60)

    settings = get_settings()

    # Configure logging level from settings
    logging.getLogger("prahari").setLevel(
        getattr(logging, settings.monitoring.log_level, logging.INFO)
    )

    # Initialize alert manager
    alert_manager = AlertManager(
        crew_id=settings.crew.id,
        cooldown_seconds=settings.alerts.cooldown_seconds,
        audio_enabled=settings.alerts.audio_enabled,
        visual_enabled=settings.alerts.visual_enabled,
        api_enabled=settings.alerts.api_enabled,
        api_endpoint=settings.alerts.api_endpoint,
        api_timeout=settings.alerts.api_timeout,
    )

    # Initialize pipeline
    pipeline = FatiguePipeline(settings=settings, alert_manager=alert_manager)

    # Start the pipeline thread
    pipeline.start()

    logger.info("Pipeline started. Press 'q' or 'Esc' in the video window, or Ctrl+C here to stop.")

    try:
        # Keep the main thread alive while the background pipeline thread processes frames
        while pipeline.is_running:
            time.sleep(0.5)
    except KeyboardInterrupt:
        logger.info("Interrupt received, shutting down...")
    finally:
        pipeline.stop()
        logger.info("PRAHARI shutdown complete")


if __name__ == "__main__":
    run()
