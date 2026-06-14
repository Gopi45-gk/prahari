"""
PRAHARI — Model Evaluation & Metrics

Computes all target metrics for trained models:
  - Accuracy, Precision, Recall, F1 (per-class & macro)
  - ROC AUC (one-vs-rest)
  - Confusion matrix visualization
  - Classification report
  - Inference latency benchmarking

Usage:
    python -m prahari.training.evaluate --model models/fatigue_cnn_best.pt --data data/val
"""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader

from prahari.models.fatigue_cnn import FatigueCNN
from prahari.training.dataset import FatigueImageDataset, get_val_transforms

logger = logging.getLogger("prahari.training.evaluate")

CLASS_NAMES = ["ALERT", "SLIGHTLY_FATIGUED", "FATIGUED", "SEVERE_FATIGUE", "MICROSLEEP"]


@torch.no_grad()
def evaluate_model(
    model_path: str,
    data_dir: str,
    batch_size: int = 32,
    input_size: int = 224,
    num_classes: int = 5,
    benchmark_iterations: int = 100,
) -> dict:
    """
    Comprehensive model evaluation.

    Returns dict with all metrics.
    """
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    logger.info("=" * 60)
    logger.info("  PRAHARI — Model Evaluation")
    logger.info("  Device: %s", device)
    logger.info("=" * 60)

    # Load model
    model = FatigueCNN(num_classes=num_classes)
    checkpoint = torch.load(model_path, map_location=device, weights_only=True)
    if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
        model.load_state_dict(checkpoint["model_state_dict"])
    else:
        model.load_state_dict(checkpoint)
    model.to(device)
    model.eval()

    # Dataset
    dataset = FatigueImageDataset(
        root_dir=data_dir,
        transform=get_val_transforms(input_size),
    )

    if len(dataset) == 0:
        logger.error("No validation samples found in %s", data_dir)
        return {}

    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False, num_workers=2)

    # Collect predictions
    all_preds = []
    all_labels = []
    all_probs = []

    for images, labels in loader:
        images = images.to(device)
        outputs = model(images)
        probs = torch.softmax(outputs, dim=1)

        _, preds = torch.max(outputs, 1)
        all_preds.extend(preds.cpu().numpy())
        all_labels.extend(labels.numpy())
        all_probs.extend(probs.cpu().numpy())

    all_preds = np.array(all_preds)
    all_labels = np.array(all_labels)
    all_probs = np.array(all_probs)

    # ── Compute Metrics ─────────────────────────────────────────
    from sklearn.metrics import (
        accuracy_score,
        classification_report,
        confusion_matrix,
        f1_score,
        precision_score,
        recall_score,
        roc_auc_score,
    )

    accuracy = accuracy_score(all_labels, all_preds)
    precision = precision_score(all_labels, all_preds, average="macro", zero_division=0)
    recall = recall_score(all_labels, all_preds, average="macro", zero_division=0)
    f1 = f1_score(all_labels, all_preds, average="macro", zero_division=0)

    # ROC AUC (one-vs-rest)
    try:
        roc_auc = roc_auc_score(all_labels, all_probs, multi_class="ovr", average="macro")
    except ValueError:
        roc_auc = 0.0

    # False positive rate (overall)
    cm = confusion_matrix(all_labels, all_preds, labels=list(range(num_classes)))
    fp_total = cm.sum(axis=0) - np.diag(cm)
    tn_total = cm.sum() - (cm.sum(axis=1) + cm.sum(axis=0) - np.diag(cm))
    fpr = np.mean(fp_total / (fp_total + tn_total + 1e-10))

    # Classification report
    report = classification_report(all_labels, all_preds, target_names=CLASS_NAMES, zero_division=0)

    # ── Print Results ───────────────────────────────────────────
    logger.info("\n" + "=" * 60)
    logger.info("  EVALUATION RESULTS")
    logger.info("=" * 60)
    logger.info("  Accuracy:        %.4f (target: >0.95)", accuracy)
    logger.info("  Precision:       %.4f (target: >0.95)", precision)
    logger.info("  Recall:          %.4f (target: >0.97)", recall)
    logger.info("  F1 Score:        %.4f", f1)
    logger.info("  ROC AUC:         %.4f", roc_auc)
    logger.info("  False Pos Rate:  %.4f (target: <0.03)", fpr)
    logger.info("\n%s", report)
    logger.info("Confusion Matrix:\n%s", cm)

    # ── Inference Latency Benchmark ─────────────────────────────
    dummy = torch.randn(1, 3, input_size, input_size).to(device)

    # Warmup
    for _ in range(10):
        model(dummy)

    if device.type == "cuda":
        torch.cuda.synchronize()

    latencies = []
    for _ in range(benchmark_iterations):
        start = time.perf_counter()
        model(dummy)
        if device.type == "cuda":
            torch.cuda.synchronize()
        latencies.append((time.perf_counter() - start) * 1000)

    avg_latency = np.mean(latencies)
    p95_latency = np.percentile(latencies, 95)
    p99_latency = np.percentile(latencies, 99)

    logger.info("\n  Inference Latency (%d iterations):", benchmark_iterations)
    logger.info("  Average:  %.2f ms (target: <50ms)", avg_latency)
    logger.info("  P95:      %.2f ms", p95_latency)
    logger.info("  P99:      %.2f ms", p99_latency)
    logger.info("  Max FPS:  %.0f", 1000 / avg_latency)

    # ── Save Metrics ────────────────────────────────────────────
    metrics = {
        "accuracy": float(accuracy),
        "precision": float(precision),
        "recall": float(recall),
        "f1_score": float(f1),
        "roc_auc": float(roc_auc),
        "false_positive_rate": float(fpr),
        "avg_latency_ms": float(avg_latency),
        "p95_latency_ms": float(p95_latency),
        "confusion_matrix": cm.tolist(),
    }

    # Check targets
    logger.info("\n  TARGET CHECK:")
    checks = [
        ("Accuracy > 95%", accuracy > 0.95),
        ("Recall > 97%", recall > 0.97),
        ("Precision > 95%", precision > 0.95),
        ("FPR < 3%", fpr < 0.03),
        ("Latency < 50ms", avg_latency < 50),
    ]
    for name, passed in checks:
        logger.info("  %s  %s", "✅" if passed else "❌", name)

    return metrics


def main():
    parser = argparse.ArgumentParser(description="PRAHARI — Evaluate FatigueCNN")
    parser.add_argument("--model", type=str, required=True, help="Path to model checkpoint")
    parser.add_argument("--data", type=str, required=True, help="Validation data directory")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--benchmark", type=int, default=100, help="Latency benchmark iterations")

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s │ %(levelname)-8s │ %(message)s")

    evaluate_model(
        model_path=args.model,
        data_dir=args.data,
        batch_size=args.batch_size,
        benchmark_iterations=args.benchmark,
    )


if __name__ == "__main__":
    main()
