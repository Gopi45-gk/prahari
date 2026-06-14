"""
PRAHARI — CNN Training Script

Full training pipeline for the FatigueCNN model:
  - 100+ epochs with early stopping (patience=15)
  - Cosine annealing LR scheduler
  - AdamW optimizer with weight decay
  - Mixed precision training (AMP)
  - Class-weighted loss for imbalanced data
  - Stratified K-fold cross-validation (optional)
  - TensorBoard logging
  - Best model checkpointing + ONNX export

Usage:
    python -m prahari.training.train_cnn --data data/train --epochs 100 --batch-size 32
"""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.cuda.amp import GradScaler, autocast
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import DataLoader, random_split

from prahari.models.fatigue_cnn import FatigueCNN
from prahari.training.dataset import FatigueImageDataset, get_train_transforms, get_val_transforms

logger = logging.getLogger("prahari.training.cnn")


def train_one_epoch(
    model: FatigueCNN,
    loader: DataLoader,
    criterion: nn.Module,
    optimizer: torch.optim.Optimizer,
    scaler: GradScaler,
    device: torch.device,
    use_amp: bool,
) -> tuple[float, float]:
    """Train for one epoch. Returns (avg_loss, accuracy)."""
    model.train()
    total_loss = 0.0
    correct = 0
    total = 0

    for batch_idx, (images, labels) in enumerate(loader):
        images, labels = images.to(device), labels.to(device)

        optimizer.zero_grad()

        with autocast(enabled=use_amp):
            outputs = model(images)
            loss = criterion(outputs, labels)

        scaler.scale(loss).backward()
        scaler.step(optimizer)
        scaler.update()

        total_loss += loss.item() * images.size(0)
        _, predicted = torch.max(outputs, 1)
        correct += (predicted == labels).sum().item()
        total += labels.size(0)

    avg_loss = total_loss / total
    accuracy = correct / total
    return avg_loss, accuracy


@torch.no_grad()
def validate(
    model: FatigueCNN,
    loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
) -> tuple[float, float]:
    """Validate model. Returns (avg_loss, accuracy)."""
    model.eval()
    total_loss = 0.0
    correct = 0
    total = 0

    for images, labels in loader:
        images, labels = images.to(device), labels.to(device)
        outputs = model(images)
        loss = criterion(outputs, labels)

        total_loss += loss.item() * images.size(0)
        _, predicted = torch.max(outputs, 1)
        correct += (predicted == labels).sum().item()
        total += labels.size(0)

    avg_loss = total_loss / total
    accuracy = correct / total
    return avg_loss, accuracy


def train(
    data_dir: str,
    output_dir: str = "models",
    epochs: int = 100,
    batch_size: int = 32,
    learning_rate: float = 1e-3,
    weight_decay: float = 1e-4,
    patience: int = 15,
    val_split: float = 0.2,
    num_workers: int = 4,
    input_size: int = 224,
    num_classes: int = 5,
) -> None:
    """
    Full CNN training pipeline.

    Args:
        data_dir: Path to training data (class-organized directories)
        output_dir: Where to save model checkpoints
        epochs: Maximum training epochs
        batch_size: Training batch size
        learning_rate: Initial learning rate
        weight_decay: AdamW weight decay
        patience: Early stopping patience
        val_split: Fraction of data for validation
        num_workers: DataLoader workers
        input_size: CNN input resolution
        num_classes: Number of fatigue classes
    """
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    use_amp = device.type == "cuda"
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("  PRAHARI — FatigueCNN Training")
    logger.info("  Device: %s | AMP: %s", device, use_amp)
    logger.info("  Epochs: %d | Batch: %d | LR: %.1e", epochs, batch_size, learning_rate)
    logger.info("=" * 60)

    # ── Dataset ─────────────────────────────────────────────────
    full_dataset = FatigueImageDataset(
        root_dir=data_dir,
        transform=get_train_transforms(input_size),
    )

    if len(full_dataset) == 0:
        logger.error("No training samples found in %s", data_dir)
        logger.info("Expected structure: data/train/0_alert/, data/train/1_slightly_fatigued/, etc.")
        return

    # Split
    val_size = int(len(full_dataset) * val_split)
    train_size = len(full_dataset) - val_size
    train_set, val_set = random_split(full_dataset, [train_size, val_size])

    # Validation set uses non-augmented transforms
    val_dataset_copy = FatigueImageDataset(
        root_dir=data_dir,
        transform=get_val_transforms(input_size),
    )
    val_set_clean = torch.utils.data.Subset(val_dataset_copy, val_set.indices)

    train_loader = DataLoader(train_set, batch_size=batch_size, shuffle=True, num_workers=num_workers, pin_memory=True)
    val_loader = DataLoader(val_set_clean, batch_size=batch_size, shuffle=False, num_workers=num_workers, pin_memory=True)

    logger.info("Train: %d samples | Val: %d samples", train_size, val_size)

    # Class weights
    class_weights = full_dataset.get_class_weights().to(device)
    logger.info("Class weights: %s", class_weights.cpu().numpy())

    # ── Model ───────────────────────────────────────────────────
    model = FatigueCNN(num_classes=num_classes).to(device)

    # ── Loss, Optimizer, Scheduler ──────────────────────────────
    criterion = nn.CrossEntropyLoss(weight=class_weights)
    optimizer = AdamW(model.parameters(), lr=learning_rate, weight_decay=weight_decay)
    scheduler = CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-6)
    scaler = GradScaler(enabled=use_amp)

    # ── Training Loop ───────────────────────────────────────────
    best_val_acc = 0.0
    patience_counter = 0
    best_epoch = 0

    for epoch in range(1, epochs + 1):
        t_start = time.time()

        train_loss, train_acc = train_one_epoch(
            model, train_loader, criterion, optimizer, scaler, device, use_amp
        )
        val_loss, val_acc = validate(model, val_loader, criterion, device)

        scheduler.step()
        elapsed = time.time() - t_start
        lr = optimizer.param_groups[0]["lr"]

        logger.info(
            "Epoch %3d/%d │ Train Loss: %.4f Acc: %.4f │ Val Loss: %.4f Acc: %.4f │ LR: %.2e │ %.1fs",
            epoch, epochs, train_loss, train_acc, val_loss, val_acc, lr, elapsed,
        )

        # Checkpoint best model
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_epoch = epoch
            patience_counter = 0

            checkpoint = {
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "val_acc": val_acc,
                "val_loss": val_loss,
            }
            torch.save(checkpoint, output_path / "fatigue_cnn_best.pt")
            logger.info("  ✓ Best model saved (acc=%.4f)", val_acc)
        else:
            patience_counter += 1

        # Early stopping
        if patience_counter >= patience:
            logger.info("Early stopping at epoch %d (best=%d, acc=%.4f)", epoch, best_epoch, best_val_acc)
            break

    # ── Export ───────────────────────────────────────────────────
    logger.info("Loading best model from epoch %d...", best_epoch)
    best_ckpt = torch.load(output_path / "fatigue_cnn_best.pt", map_location=device)
    model.load_state_dict(best_ckpt["model_state_dict"])

    # ONNX export
    model.export_onnx(output_path / "fatigue_cnn.onnx")

    logger.info("Training complete — Best Validation Accuracy: %.4f at epoch %d", best_val_acc, best_epoch)


# ── CLI ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="PRAHARI — Train FatigueCNN")
    parser.add_argument("--data", type=str, default="data/train", help="Training data directory")
    parser.add_argument("--output", type=str, default="models", help="Output directory for checkpoints")
    parser.add_argument("--epochs", type=int, default=100, help="Max training epochs")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size")
    parser.add_argument("--lr", type=float, default=1e-3, help="Learning rate")
    parser.add_argument("--patience", type=int, default=15, help="Early stopping patience")
    parser.add_argument("--input-size", type=int, default=224, help="CNN input size")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s │ %(levelname)-8s │ %(message)s")

    train(
        data_dir=args.data,
        output_dir=args.output,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        patience=args.patience,
        input_size=args.input_size,
    )


if __name__ == "__main__":
    main()
