"""
PRAHARI Configuration Loader

Loads settings from config/settings.yaml with environment variable overrides
and automatic GPU/CPU device detection.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import torch
import yaml

logger = logging.getLogger("prahari.config")

# Project root — two levels up from this file (src/prahari/config.py → prahari/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "settings.yaml"


@dataclass
class CrewConfig:
    id: str = "LP001"
    name: str = "Default Loco Pilot"
    division: str = "Northern Railway"


@dataclass
class CameraConfig:
    source: int | str = 0
    width: int = 640
    height: int = 480
    fps: int = 30


@dataclass
class DeviceConfig:
    mode: str = "auto"
    fp16: bool = True

    @property
    def resolved_device(self) -> torch.device:
        """Resolve the actual torch device based on mode and availability."""
        if self.mode == "auto":
            if torch.cuda.is_available():
                logger.info("CUDA detected — using GPU: %s", torch.cuda.get_device_name(0))
                return torch.device("cuda")
            else:
                logger.warning("No CUDA GPU detected — falling back to CPU")
                return torch.device("cpu")
        elif self.mode == "cuda":
            if not torch.cuda.is_available():
                raise RuntimeError("CUDA requested but not available")
            return torch.device("cuda")
        else:
            return torch.device("cpu")

    @property
    def use_fp16(self) -> bool:
        """FP16 is only useful on GPU."""
        return self.fp16 and self.mode != "cpu" and torch.cuda.is_available()


@dataclass
class ModelPaths:
    yolo_face: str = "models/yolov8n-face.pt"
    fatigue_cnn: str = "models/fatigue_cnn.onnx"
    temporal_lstm: str = "models/temporal_lstm.pt"

    def resolve(self, root: Path) -> None:
        """Convert relative paths to absolute using project root."""
        self.yolo_face = str(root / self.yolo_face)
        self.fatigue_cnn = str(root / self.fatigue_cnn)
        self.temporal_lstm = str(root / self.temporal_lstm)


@dataclass
class DetectionConfig:
    min_detection_confidence: float = 0.5
    min_tracking_confidence: float = 0.5
    yolo_confidence: float = 0.4
    clahe_clip_limit: float = 2.0
    clahe_grid_size: int = 8


@dataclass
class FeatureConfig:
    ear_threshold: float = 0.21
    ear_consec_frames: int = 3
    mar_threshold: float = 0.65
    mar_consec_frames: int = 10
    perclos_window: int = 60
    perclos_alert_threshold: float = 0.20
    blink_min_duration: float = 0.1
    blink_max_duration: float = 0.4
    head_pitch_threshold: float = 15.0
    head_yaw_threshold: float = 30.0
    head_droop_duration: float = 2.0
    blink_rate_window: int = 60
    yawn_rate_window: int = 300


@dataclass
class ClassifierConfig:
    input_size: int = 224
    num_classes: int = 5
    class_names: list[str] = field(default_factory=lambda: [
        "ALERT", "SLIGHTLY_FATIGUED", "FATIGUED", "SEVERE_FATIGUE", "MICROSLEEP"
    ])


@dataclass
class TemporalConfig:
    sequence_length: int = 60
    sample_rate: float = 1.0
    hidden_size: int = 64
    num_layers: int = 2


@dataclass
class FusionWeights:
    cnn_classification: float = 0.25
    perclos: float = 0.20
    ear: float = 0.10
    mar: float = 0.08
    blink_pattern: float = 0.07
    head_pose: float = 0.10
    temporal_trend: float = 0.12
    microsleep_prob: float = 0.08


@dataclass
class FusionConfig:
    weights: FusionWeights = field(default_factory=FusionWeights)
    ema_alpha: float = 0.3


@dataclass
class RiskConfig:
    low_max: int = 40
    medium_max: int = 70
    high_max: int = 85
    critical_min: int = 86
    microsleep_eye_closed_seconds: float = 2.0
    face_absent_seconds: float = 10.0
    emergency_cai_threshold: int = 95
    emergency_duration_seconds: int = 5


@dataclass
class AlertConfig:
    cooldown_seconds: int = 30
    audio_enabled: bool = True
    audio_file: str = "assets/alert_tone.wav"
    visual_enabled: bool = True
    api_enabled: bool = False
    api_endpoint: str = "http://localhost:9000/api/v1/fatigue-alert"
    api_timeout: int = 5


@dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8000
    open_browser: bool = True


@dataclass
class MonitoringConfig:
    prometheus_enabled: bool = True
    prometheus_port: int = 9090
    log_level: str = "INFO"


@dataclass
class Settings:
    """Root configuration container for the entire PRAHARI system."""

    crew: CrewConfig = field(default_factory=CrewConfig)
    camera: CameraConfig = field(default_factory=CameraConfig)
    device: DeviceConfig = field(default_factory=DeviceConfig)
    models: ModelPaths = field(default_factory=ModelPaths)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    features: FeatureConfig = field(default_factory=FeatureConfig)
    classifier: ClassifierConfig = field(default_factory=ClassifierConfig)
    temporal: TemporalConfig = field(default_factory=TemporalConfig)
    fusion: FusionConfig = field(default_factory=FusionConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    alerts: AlertConfig = field(default_factory=AlertConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)

    @classmethod
    def from_yaml(cls, path: Path | str | None = None) -> "Settings":
        """Load settings from a YAML file, falling back to defaults."""
        path = Path(path) if path else CONFIG_PATH

        if path.exists():
            logger.info("Loading configuration from %s", path)
            with open(path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
        else:
            logger.warning("Config file not found at %s — using defaults", path)
            raw = {}

        return cls._from_dict(raw)

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> "Settings":
        """Recursively populate dataclass fields from a dict."""
        settings = cls()

        mapping = {
            "crew": (CrewConfig, settings.crew),
            "camera": (CameraConfig, settings.camera),
            "device": (DeviceConfig, settings.device),
            "models": (ModelPaths, settings.models),
            "detection": (DetectionConfig, settings.detection),
            "features": (FeatureConfig, settings.features),
            "classifier": (ClassifierConfig, settings.classifier),
            "temporal": (TemporalConfig, settings.temporal),
            "risk": (RiskConfig, settings.risk),
            "alerts": (AlertConfig, settings.alerts),
            "server": (ServerConfig, settings.server),
            "monitoring": (MonitoringConfig, settings.monitoring),
        }

        for key, (dc_cls, default_instance) in mapping.items():
            section = data.get(key, {})
            if isinstance(section, dict):
                obj = dc_cls(**{
                    k: v for k, v in section.items()
                    if k in dc_cls.__dataclass_fields__
                })
                setattr(settings, key, obj)

        # Handle nested fusion config
        fusion_data = data.get("fusion", {})
        if fusion_data:
            weights_data = fusion_data.get("weights", {})
            weights = FusionWeights(**{
                k: v for k, v in weights_data.items()
                if k in FusionWeights.__dataclass_fields__
            }) if weights_data else FusionWeights()
            settings.fusion = FusionConfig(
                weights=weights,
                ema_alpha=fusion_data.get("ema_alpha", 0.3),
            )

        # Apply environment variable overrides
        settings._apply_env_overrides()

        return settings

    def _apply_env_overrides(self) -> None:
        """Override settings with PRAHARI_* environment variables."""
        env_map = {
            "PRAHARI_CREW_ID": lambda v: setattr(self.crew, "id", v),
            "PRAHARI_CAMERA_SOURCE": lambda v: setattr(
                self.camera, "source", int(v) if v.isdigit() else v
            ),
            "PRAHARI_DEVICE_MODE": lambda v: setattr(self.device, "mode", v),
            "PRAHARI_SERVER_PORT": lambda v: setattr(self.server, "port", int(v)),
            "PRAHARI_LOG_LEVEL": lambda v: setattr(self.monitoring, "log_level", v),
        }
        for env_key, setter in env_map.items():
            val = os.environ.get(env_key)
            if val is not None:
                logger.info("Environment override: %s = %s", env_key, val)
                setter(val)


# ─── Singleton accessor ──────────────────────────────────────────────
_settings: Settings | None = None


def get_settings(config_path: Path | str | None = None) -> Settings:
    """Get or initialize the global settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings.from_yaml(config_path)
    return _settings


def reset_settings() -> None:
    """Reset the settings singleton (for testing)."""
    global _settings
    _settings = None
