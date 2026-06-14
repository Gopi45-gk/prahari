"""
PRAHARI — Dataset Loaders & Augmentation

Provides PyTorch Dataset classes for:
  1. FatigueImageDataset — image-based fatigue classification (CNN training)
  2. TemporalFatigueDataset — sequence-based temporal analysis (LSTM training)

Includes comprehensive data augmentation pipeline for robustness:
brightness, contrast, rotation, blur, occlusion, glasses simulation,
low-light, and motion blur.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

import numpy as np
import torch
from PIL import Image
from torch.utils.data import Dataset

logger = logging.getLogger("prahari.training.dataset")


# ─── Custom Augmentation Transforms ────────────────────────────

class MotionBlur:
    """Simulate motion blur from train vibration."""

    def __init__(self, kernel_size: int = 7, p: float = 0.3):
        self.kernel_size = kernel_size
        self.p = p

    def __call__(self, img):
        if np.random.random() > self.p:
            return img

        import cv2
        img_np = np.array(img)

        # Horizontal motion blur
        kernel = np.zeros((self.kernel_size, self.kernel_size))
        kernel[self.kernel_size // 2, :] = 1.0 / self.kernel_size
        blurred = cv2.filter2D(img_np, -1, kernel)

        return Image.fromarray(blurred)


class SimulateGlasses:
    """Simulate spectacles reflection/glare."""

    def __init__(self, p: float = 0.15):
        self.p = p

    def __call__(self, img):
        if np.random.random() > self.p:
            return img

        img_np = np.array(img).copy()
        h, w = img_np.shape[:2]

        # Add semi-transparent rectangles near eye region
        eye_y = int(h * 0.3)
        eye_h = int(h * 0.15)

        alpha = np.random.uniform(0.1, 0.3)
        overlay = img_np.copy()

        # Left eye region
        x1, x2 = int(w * 0.15), int(w * 0.45)
        overlay[eye_y:eye_y + eye_h, x1:x2] = (
            overlay[eye_y:eye_y + eye_h, x1:x2] * (1 - alpha) + 255 * alpha
        ).astype(np.uint8)

        # Right eye region
        x1, x2 = int(w * 0.55), int(w * 0.85)
        overlay[eye_y:eye_y + eye_h, x1:x2] = (
            overlay[eye_y:eye_y + eye_h, x1:x2] * (1 - alpha) + 255 * alpha
        ).astype(np.uint8)

        return Image.fromarray(overlay)


class LowLightSimulation:
    """Simulate low cabin lighting conditions."""

    def __init__(self, p: float = 0.2, gamma_range: tuple = (1.5, 3.0)):
        self.p = p
        self.gamma_range = gamma_range

    def __call__(self, img):
        if np.random.random() > self.p:
            return img

        img_np = np.array(img).astype(np.float32) / 255.0
        gamma = np.random.uniform(*self.gamma_range)
        darkened = np.power(img_np, gamma) * 255.0
        return Image.fromarray(darkened.astype(np.uint8))


def get_train_transforms(input_size: int = 224):
    """Get the full training augmentation pipeline."""
    from torchvision import transforms

    return transforms.Compose([
        transforms.Resize((input_size, input_size)),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomRotation(degrees=15),
        transforms.ColorJitter(
            brightness=0.4,
            contrast=0.4,
            saturation=0.2,
            hue=0.1,
        ),
        transforms.RandomGrayscale(p=0.05),
        MotionBlur(kernel_size=7, p=0.3),
        SimulateGlasses(p=0.15),
        LowLightSimulation(p=0.2),
        transforms.GaussianBlur(kernel_size=5, sigma=(0.1, 2.0)),
        transforms.RandomErasing(p=0.2, scale=(0.02, 0.15)),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225],
        ),
    ])


def get_val_transforms(input_size: int = 224):
    """Get the validation/test transform pipeline (no augmentation)."""
    from torchvision import transforms

    return transforms.Compose([
        transforms.Resize((input_size, input_size)),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225],
        ),
    ])


# ─── Image Dataset ─────────────────────────────────────────────

class FatigueImageDataset(Dataset):
    """
    Image dataset for fatigue classification.

    Expected directory structure:
        data/
        ├── train/
        │   ├── 0_alert/
        │   ├── 1_slightly_fatigued/
        │   ├── 2_fatigued/
        │   ├── 3_severe_fatigue/
        │   └── 4_microsleep/
        └── val/
            └── (same structure)
    """

    CLASS_MAP = {
        "0_alert": 0,
        "1_slightly_fatigued": 1,
        "2_fatigued": 2,
        "3_severe_fatigue": 3,
        "4_microsleep": 4,
    }

    def __init__(
        self,
        root_dir: str | Path,
        transform=None,
        class_map: Optional[dict] = None,
    ):
        self.root_dir = Path(root_dir)
        self.transform = transform
        self.class_map = class_map or self.CLASS_MAP

        self.samples: list[tuple[Path, int]] = []
        self._load_samples()

        logger.info(
            "FatigueImageDataset: %d samples from %s (%d classes)",
            len(self.samples),
            self.root_dir,
            len(self.class_map),
        )

    def _load_samples(self) -> None:
        """Scan directories and build sample list."""
        for class_name, class_idx in self.class_map.items():
            class_dir = self.root_dir / class_name
            if not class_dir.exists():
                logger.warning("Class directory not found: %s", class_dir)
                continue

            for img_path in sorted(class_dir.iterdir()):
                if img_path.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp"):
                    self.samples.append((img_path, class_idx))

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, int]:
        img_path, label = self.samples[idx]

        img = Image.open(img_path).convert("RGB")

        if self.transform:
            img = self.transform(img)
        else:
            from torchvision import transforms
            img = transforms.ToTensor()(img)

        return img, label

    def get_class_counts(self) -> dict[int, int]:
        """Get number of samples per class."""
        counts = {}
        for _, label in self.samples:
            counts[label] = counts.get(label, 0) + 1
        return counts

    def get_class_weights(self) -> torch.Tensor:
        """Compute inverse frequency class weights for imbalanced data."""
        counts = self.get_class_counts()
        total = len(self.samples)
        n_classes = len(self.class_map)
        weights = torch.zeros(n_classes)
        for cls_idx, count in counts.items():
            weights[cls_idx] = total / (n_classes * count)
        return weights


# ─── Temporal Dataset ──────────────────────────────────────────

class TemporalFatigueDataset(Dataset):
    """
    Sequence dataset for temporal fatigue analysis (LSTM training).

    Loads pre-extracted feature sequences (.npz files) with structure:
        features: (seq_len, 16) float array
        trend_label: int (0=Improving, 1=Stable, 2=Degrading)
        microsleep_label: float (0.0-1.0)
    """

    def __init__(
        self,
        root_dir: str | Path,
        sequence_length: int = 60,
    ):
        self.root_dir = Path(root_dir)
        self.sequence_length = sequence_length
        self.samples: list[Path] = []

        # Scan for .npz files
        if self.root_dir.exists():
            self.samples = sorted(self.root_dir.glob("*.npz"))

        logger.info("TemporalFatigueDataset: %d sequences from %s", len(self.samples), root_dir)

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, int, float]:
        data = np.load(self.samples[idx])
        features = data["features"].astype(np.float32)
        trend_label = int(data["trend_label"])
        microsleep_label = float(data["microsleep_label"])

        # Pad or truncate
        if len(features) < self.sequence_length:
            padding = np.zeros((self.sequence_length - len(features), features.shape[1]), dtype=np.float32)
            features = np.concatenate([padding, features], axis=0)
        elif len(features) > self.sequence_length:
            features = features[-self.sequence_length:]

        return (
            torch.from_numpy(features),
            trend_label,
            microsleep_label,
        )
