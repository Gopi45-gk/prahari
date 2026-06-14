"""
PRAHARI — LSTM Training Script

Training pipeline for the TemporalLSTM model:
  - Dual-head loss (trend classification + microsleep regression)
  - AdamW with cosine annealing
  - Mixed precision training
  - Early stopping + best checkpoint

Usage:
    python -m prahari.training.train_lstm --data data/temporal --epochs 80
"""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

import torch
import torch.nn as nn
from torch.cuda.amp import GradScaler, autocast
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import DataLoader, random_split

from prahari.models.temporal_lstm import TemporalLSTM
from prahari.training.dataset import TemporalFatigueDataset

logger = logging.getLogger("prahari.training.lstm")


def train(
    data_dir: str,
    output_dir: str = "models",
    epochs: int = 80,
    batch_size: int = 64,
    learning_rate: float = 5e-4,
    weight_decay: float = 1e-4,
    patience: int = 20,
    val_split: float = 0.2,
    sequence_length: int = 60,
    hidden_size: int = 64,
    num_layers: int = 2,
) -> None:
    """Full LSTM training pipeline."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    use_amp = device.type == "cuda"
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("  PRAHARI — TemporalLSTM Training")
    logger.info("  Device: %s | Sequence: %d | Hidden: %d", device, sequence_length, hidden_size)
    logger.info("=" * 60)

    # Dataset
    dataset = TemporalFatigueDataset(root_dir=data_dir, sequence_length=sequence_length)

    if len(dataset) == 0:
        logger.error("No temporal sequences found in %s", data_dir)
        logger.info("Expected .npz files with keys: features, trend_label, microsleep_label")
        return

    val_size = int(len(dataset) * val_split)
    train_size = len(dataset) - val_size
    train_set, val_set = random_split(dataset, [train_size, val_size])

    train_loader = DataLoader(train_set, batch_size=batch_size, shuffle=True, num_workers=2, pin_memory=True)
    val_loader = DataLoader(val_set, batch_size=batch_size, shuffle=False, num_workers=2, pin_memory=True)

    logger.info("Train: %d | Val: %d sequences", train_size, val_size)

    # Model
    model = TemporalLSTM(
        input_size=16,
        hidden_size=hidden_size,
        num_layers=num_layers,
    ).to(device)

    # Loss functions (dual head)
    trend_criterion = nn.CrossEntropyLoss()
    microsleep_criterion = nn.BCELoss()

    optimizer = AdamW(model.parameters(), lr=learning_rate, weight_decay=weight_decay)
    scheduler = CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-6)
    scaler = GradScaler(enabled=use_amp)

    best_val_loss = float("inf")
    patience_counter = 0

    for epoch in range(1, epochs + 1):
        t_start = time.time()

        # Train
        model.train()
        train_loss = 0.0
        for features, trend_labels, ms_labels in train_loader:
            features = features.to(device)
            trend_labels = trend_labels.to(device)
            ms_labels = ms_labels.float().unsqueeze(1).to(device)

            optimizer.zero_grad()
            with autocast(enabled=use_amp):
                trend_logits, ms_prob, _ = model(features)
                loss_trend = trend_criterion(trend_logits, trend_labels)
                loss_ms = microsleep_criterion(ms_prob, ms_labels)
                loss = loss_trend + 0.5 * loss_ms

            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            train_loss += loss.item() * features.size(0)

        train_loss /= train_size

        # Validate
        model.eval()
        val_loss = 0.0
        trend_correct = 0
        val_total = 0
        with torch.no_grad():
            for features, trend_labels, ms_labels in val_loader:
                features = features.to(device)
                trend_labels = trend_labels.to(device)
                ms_labels = ms_labels.float().unsqueeze(1).to(device)

                trend_logits, ms_prob, _ = model(features)
                loss_trend = trend_criterion(trend_logits, trend_labels)
                loss_ms = microsleep_criterion(ms_prob, ms_labels)
                loss = loss_trend + 0.5 * loss_ms

                val_loss += loss.item() * features.size(0)
                _, pred = torch.max(trend_logits, 1)
                trend_correct += (pred == trend_labels).sum().item()
                val_total += trend_labels.size(0)

        val_loss /= val_size
        val_acc = trend_correct / max(val_total, 1)

        scheduler.step()
        elapsed = time.time() - t_start

        logger.info(
            "Epoch %3d/%d │ Train Loss: %.4f │ Val Loss: %.4f │ Trend Acc: %.4f │ %.1fs",
            epoch, epochs, train_loss, val_loss, val_acc, elapsed,
        )

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "val_loss": val_loss,
                "val_acc": val_acc,
            }, output_path / "temporal_lstm.pt")
            logger.info("  ✓ Best model saved (val_loss=%.4f)", val_loss)
        else:
            patience_counter += 1

        if patience_counter >= patience:
            logger.info("Early stopping at epoch %d", epoch)
            break

    logger.info("LSTM Training complete — best val_loss=%.4f", best_val_loss)


def main():
    parser = argparse.ArgumentParser(description="PRAHARI — Train TemporalLSTM")
    parser.add_argument("--data", type=str, default="data/temporal", help="Temporal data directory")
    parser.add_argument("--output", type=str, default="models", help="Output directory")
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=5e-4)
    parser.add_argument("--patience", type=int, default=20)

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s │ %(levelname)-8s │ %(message)s")

    train(
        data_dir=args.data,
        output_dir=args.output,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        patience=args.patience,
    )


if __name__ == "__main__":
    main()
