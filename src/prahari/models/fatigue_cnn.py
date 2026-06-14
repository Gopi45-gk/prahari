"""
PRAHARI — Stage 3: CNN Fatigue Classifier

Custom Convolutional Neural Network for classifying facial fatigue levels
from cropped face ROIs (224×224).

5 Classes:
  0 = ALERT
  1 = SLIGHTLY_FATIGUED
  2 = FATIGUED
  3 = SEVERE_FATIGUE
  4 = MICROSLEEP

Architecture:
  4 dual-conv blocks with BatchNorm + ReLU + MaxPool + Dropout
  → Global Average Pooling → Dense(128) → Dense(64) → Softmax(5)

Supports FP16 inference and ONNX export for production deployment.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger("prahari.models.fatigue_cnn")


class ConvBlock(nn.Module):
    """Dual convolution block: Conv → BN → ReLU → Conv → BN → ReLU → MaxPool → Dropout."""

    def __init__(self, in_channels: int, out_channels: int, dropout: float = 0.25):
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=2, stride=2),
            nn.Dropout2d(p=dropout),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.block(x)


class FatigueCNN(nn.Module):
    """
    Custom CNN for fatigue classification from facial ROI images.

    Input:  (B, 3, 224, 224) — RGB face crop
    Output: (B, 5) — class probabilities [Alert, Slight, Fatigued, Severe, Microsleep]
    """

    CLASS_NAMES = ["ALERT", "SLIGHTLY_FATIGUED", "FATIGUED", "SEVERE_FATIGUE", "MICROSLEEP"]

    def __init__(self, num_classes: int = 5, dropout_dense: float = 0.5):
        super().__init__()
        self.num_classes = num_classes

        # Feature extraction blocks
        # Input: 224×224 → 112 → 56 → 28 → 14
        self.features = nn.Sequential(
            ConvBlock(3, 32, dropout=0.25),     # → 32 × 112 × 112
            ConvBlock(32, 64, dropout=0.25),    # → 64 × 56 × 56
            ConvBlock(64, 128, dropout=0.25),   # → 128 × 28 × 28
            ConvBlock(128, 256, dropout=0.30),  # → 256 × 14 × 14
        )

        # Global Average Pooling → (B, 256, 1, 1)
        self.global_pool = nn.AdaptiveAvgPool2d(1)

        # Dense classification head
        self.classifier = nn.Sequential(
            nn.Linear(256, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout_dense),

            nn.Linear(128, 64),
            nn.BatchNorm1d(64),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout_dense),

            nn.Linear(64, num_classes),
        )

        # Initialize weights
        self._initialize_weights()

        logger.info(
            "FatigueCNN initialized — %d classes, %.1fM parameters",
            num_classes,
            sum(p.numel() for p in self.parameters()) / 1e6,
        )

    def _initialize_weights(self) -> None:
        """Kaiming initialization for conv layers, Xavier for linear."""
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode="fan_out", nonlinearity="relu")
            elif isinstance(m, nn.BatchNorm2d) or isinstance(m, nn.BatchNorm1d):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.

        Args:
            x: (B, 3, 224, 224) input tensor

        Returns:
            (B, num_classes) logits (apply softmax externally for probabilities)
        """
        x = self.features(x)
        x = self.global_pool(x)
        x = x.view(x.size(0), -1)  # Flatten: (B, 256)
        x = self.classifier(x)
        return x

    def predict(self, x: torch.Tensor) -> tuple[int, np.ndarray]:
        """
        Single-image prediction with probabilities.

        Args:
            x: (1, 3, 224, 224) input tensor

        Returns:
            (predicted_class_index, probabilities_array)
        """
        self.eval()
        with torch.no_grad():
            logits = self.forward(x)
            probs = F.softmax(logits, dim=1)
            pred_class = torch.argmax(probs, dim=1).item()
            probs_np = probs.cpu().numpy().flatten()
        return pred_class, probs_np

    def predict_class_name(self, x: torch.Tensor) -> tuple[str, float, np.ndarray]:
        """
        Predict with human-readable class name.

        Returns:
            (class_name, confidence, all_probabilities)
        """
        pred_idx, probs = self.predict(x)
        class_name = self.CLASS_NAMES[pred_idx]
        confidence = float(probs[pred_idx])
        return class_name, confidence, probs

    def export_onnx(self, save_path: str | Path, opset_version: int = 17) -> None:
        """
        Export model to ONNX format for production inference.

        Args:
            save_path: Output .onnx file path
            opset_version: ONNX opset version
        """
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)

        self.eval()
        dummy_input = torch.randn(1, 3, 224, 224)

        if next(self.parameters()).is_cuda:
            dummy_input = dummy_input.cuda()

        torch.onnx.export(
            self,
            dummy_input,
            str(save_path),
            opset_version=opset_version,
            input_names=["face_roi"],
            output_names=["fatigue_logits"],
            dynamic_axes={
                "face_roi": {0: "batch_size"},
                "fatigue_logits": {0: "batch_size"},
            },
        )
        logger.info("FatigueCNN exported to ONNX: %s", save_path)


class FatigueCNNInference:
    """
    Production inference wrapper for FatigueCNN.
    Handles preprocessing, device management, and optional ONNX runtime.
    """

    # ImageNet normalization stats
    MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

    def __init__(
        self,
        model_path: Optional[str] = None,
        device: torch.device = torch.device("cpu"),
        use_fp16: bool = False,
    ):
        self.device = device
        self.use_fp16 = use_fp16 and device.type == "cuda"
        self._model: Optional[FatigueCNN] = None
        self._onnx_session = None

        if model_path and Path(model_path).exists():
            if model_path.endswith(".onnx"):
                self._load_onnx(model_path)
            else:
                self._load_pytorch(model_path)
        else:
            # Initialize untrained model (for demo/development)
            logger.warning("No model weights found — using untrained FatigueCNN")
            self._model = FatigueCNN().to(device)
            self._model.eval()
            self.is_untrained = True

            if self.use_fp16:
                self._model.half()

    def _load_pytorch(self, path: str) -> None:
        """Load PyTorch model weights."""
        self._model = FatigueCNN()
        checkpoint = torch.load(path, map_location=self.device, weights_only=True)

        if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
            self._model.load_state_dict(checkpoint["model_state_dict"])
        else:
            self._model.load_state_dict(checkpoint)

        self._model.to(self.device)
        self._model.eval()

        if self.use_fp16:
            self._model.half()

        logger.info("FatigueCNN loaded from %s (device=%s, fp16=%s)", path, self.device, self.use_fp16)

    def _load_onnx(self, path: str) -> None:
        """Load ONNX model for optimized inference."""
        try:
            import onnxruntime as ort

            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
            self._onnx_session = ort.InferenceSession(path, providers=providers)
            logger.info("FatigueCNN loaded from ONNX: %s", path)
        except ImportError:
            logger.warning("onnxruntime not installed — falling back to PyTorch")
            self._model = FatigueCNN().to(self.device)
            self._model.eval()

    def preprocess(self, face_roi_bgr: np.ndarray) -> torch.Tensor:
        """
        Preprocess a BGR face ROI (224×224×3) into a model-ready tensor.

        Args:
            face_roi_bgr: (224, 224, 3) BGR uint8 image

        Returns:
            (1, 3, 224, 224) normalized float tensor
        """
        import cv2

        # BGR → RGB
        rgb = cv2.cvtColor(face_roi_bgr, cv2.COLOR_BGR2RGB)

        # Normalize to [0, 1] then ImageNet stats
        img = rgb.astype(np.float32) / 255.0
        img = (img - self.MEAN) / self.STD

        # HWC → CHW → add batch dim
        tensor = torch.from_numpy(img.transpose(2, 0, 1)).unsqueeze(0)

        if self.use_fp16:
            tensor = tensor.half()

        return tensor.to(self.device)

    def classify(self, face_roi_bgr: np.ndarray) -> tuple[str, float, np.ndarray]:
        """
        Classify a face ROI image.

        Args:
            face_roi_bgr: (224, 224, 3) BGR uint8 image

        Returns:
            (class_name, confidence, probabilities)
        """
        input_tensor = self.preprocess(face_roi_bgr)

        if self._onnx_session is not None:
            # ONNX inference
            input_name = self._onnx_session.get_inputs()[0].name
            logits = self._onnx_session.run(None, {input_name: input_tensor.cpu().numpy()})[0]
            probs = np.exp(logits) / np.sum(np.exp(logits), axis=1, keepdims=True)
            probs = probs.flatten()
            pred_idx = int(np.argmax(probs))
        else:
            # PyTorch inference
            pred_idx, probs = self._model.predict(input_tensor)

        class_name = FatigueCNN.CLASS_NAMES[pred_idx]
        confidence = float(probs[pred_idx])

        return class_name, confidence, probs

    def get_fatigue_score(self, probs: np.ndarray) -> float:
        """
        Convert class probabilities to a 0–100 fatigue score.

        Weighted sum: ALERT=0, SLIGHT=25, FATIGUED=50, SEVERE=75, MICROSLEEP=100
        """
        weights = np.array([0.0, 25.0, 50.0, 75.0, 100.0])
        return float(np.dot(probs, weights))
