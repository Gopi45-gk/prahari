"""
PRAHARI — Stage 4: Temporal Sequence Analysis (BiLSTM)

Bidirectional LSTM with self-attention for detecting fatigue progression
over time. Processes sequences of feature vectors from the last 60 seconds
to predict:

  1. Fatigue trend: Improving / Stable / Degrading
  2. Microsleep probability: 0–1 risk of imminent microsleep

Architecture:
  Input (batch, seq_len=60, features=16)
  → BiLSTM(16→64, 2 layers, dropout=0.3)
  → Self-Attention over time steps
  → Dense(128→64) → ReLU → Dropout
  → Dual output heads (trend classification + microsleep regression)
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger("prahari.models.temporal_lstm")


class TemporalAttention(nn.Module):
    """Self-attention layer over temporal sequence for weighting important time steps."""

    def __init__(self, hidden_size: int):
        super().__init__()
        self.attention = nn.Sequential(
            nn.Linear(hidden_size, hidden_size // 2),
            nn.Tanh(),
            nn.Linear(hidden_size // 2, 1),
        )

    def forward(self, lstm_output: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            lstm_output: (batch, seq_len, hidden_size)

        Returns:
            context: (batch, hidden_size) — attention-weighted representation
            weights: (batch, seq_len) — attention weights for interpretability
        """
        # Compute attention scores
        scores = self.attention(lstm_output).squeeze(-1)  # (batch, seq_len)
        weights = F.softmax(scores, dim=1)  # (batch, seq_len)

        # Weighted sum
        context = torch.bmm(weights.unsqueeze(1), lstm_output).squeeze(1)  # (batch, hidden_size)

        return context, weights


class TemporalLSTM(nn.Module):
    """
    Bidirectional LSTM with attention for fatigue trend prediction
    and microsleep onset detection.

    Input:  (batch, seq_len, 16) — sequence of feature vectors
    Output: (trend_logits, microsleep_probability)
             trend_logits: (batch, 3) — [Improving, Stable, Degrading]
             microsleep_prob: (batch, 1) — [0.0 ... 1.0]
    """

    TREND_NAMES = ["IMPROVING", "STABLE", "DEGRADING"]

    def __init__(
        self,
        input_size: int = 16,
        hidden_size: int = 64,
        num_layers: int = 2,
        dropout: float = 0.3,
        num_trend_classes: int = 3,
    ):
        super().__init__()
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.num_layers = num_layers

        # Input normalization
        self.input_norm = nn.LayerNorm(input_size)

        # Bidirectional LSTM
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
            bidirectional=True,
        )

        # Self-attention over time steps
        # BiLSTM output is 2×hidden_size
        self.attention = TemporalAttention(hidden_size * 2)

        # Shared feature layer
        self.shared = nn.Sequential(
            nn.Linear(hidden_size * 2, 128),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
            nn.Linear(128, 64),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
        )

        # Head 1: Fatigue trend classification
        self.trend_head = nn.Linear(64, num_trend_classes)

        # Head 2: Microsleep probability regression
        self.microsleep_head = nn.Sequential(
            nn.Linear(64, 1),
            nn.Sigmoid(),
        )

        # Initialize weights
        self._initialize_weights()

        param_count = sum(p.numel() for p in self.parameters())
        logger.info(
            "TemporalLSTM initialized — input=%d, hidden=%d, layers=%d, params=%.1fK",
            input_size, hidden_size, num_layers, param_count / 1e3,
        )

    def _initialize_weights(self) -> None:
        """Orthogonal init for LSTM, Xavier for linear layers."""
        for name, param in self.lstm.named_parameters():
            if "weight_ih" in name:
                nn.init.xavier_uniform_(param)
            elif "weight_hh" in name:
                nn.init.orthogonal_(param)
            elif "bias" in name:
                nn.init.zeros_(param)
                # Set forget gate bias to 1 for better gradient flow
                n = param.size(0)
                param.data[n // 4 : n // 2].fill_(1.0)

        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)

    def forward(
        self, x: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Forward pass.

        Args:
            x: (batch, seq_len, input_size) feature sequences

        Returns:
            trend_logits: (batch, 3)
            microsleep_prob: (batch, 1)
            attention_weights: (batch, seq_len) — for interpretability
        """
        # Normalize input features
        x = self.input_norm(x)

        # BiLSTM
        lstm_out, _ = self.lstm(x)  # (batch, seq_len, hidden*2)

        # Attention-weighted context
        context, attn_weights = self.attention(lstm_out)  # (batch, hidden*2)

        # Shared representation
        shared_feat = self.shared(context)  # (batch, 64)

        # Dual heads
        trend_logits = self.trend_head(shared_feat)  # (batch, 3)
        microsleep_prob = self.microsleep_head(shared_feat)  # (batch, 1)

        return trend_logits, microsleep_prob, attn_weights

    def predict(
        self, x: torch.Tensor
    ) -> tuple[str, float, float, np.ndarray]:
        """
        Single sequence prediction.

        Args:
            x: (1, seq_len, input_size) input sequence

        Returns:
            (trend_name, trend_confidence, microsleep_probability, attention_weights)
        """
        self.eval()
        with torch.no_grad():
            trend_logits, microsleep_prob, attn_weights = self.forward(x)

            trend_probs = F.softmax(trend_logits, dim=1).cpu().numpy().flatten()
            trend_idx = int(np.argmax(trend_probs))
            trend_name = self.TREND_NAMES[trend_idx]
            trend_conf = float(trend_probs[trend_idx])

            ms_prob = float(microsleep_prob.cpu().item())
            attn = attn_weights.cpu().numpy().flatten()

        return trend_name, trend_conf, ms_prob, attn


class TemporalLSTMInference:
    """
    Production inference wrapper for the temporal model.
    Manages the rolling feature buffer and provides predictions.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        device: torch.device = torch.device("cpu"),
        sequence_length: int = 60,
        input_size: int = 16,
        hidden_size: int = 64,
        num_layers: int = 2,
    ):
        self.device = device
        self.sequence_length = sequence_length
        self.input_size = input_size

        # Rolling feature buffer
        self._buffer: list[np.ndarray] = []

        # Load or create model
        self._model = TemporalLSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
        )

        if model_path and __import__("pathlib").Path(model_path).exists():
            checkpoint = torch.load(model_path, map_location=device, weights_only=True)
            if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
                self._model.load_state_dict(checkpoint["model_state_dict"])
            else:
                self._model.load_state_dict(checkpoint)
            logger.info("TemporalLSTM loaded from %s", model_path)
        else:
            logger.warning("No temporal model weights — using untrained TemporalLSTM")
            self.is_untrained = True

        self._model.to(device)
        self._model.eval()

    def add_observation(self, feature_vector: np.ndarray) -> None:
        """
        Add a feature vector observation to the rolling buffer.

        Args:
            feature_vector: (16,) float array from FeatureVector.to_array()
        """
        self._buffer.append(feature_vector.copy())
        # Keep only the last sequence_length observations
        if len(self._buffer) > self.sequence_length:
            self._buffer = self._buffer[-self.sequence_length :]

    def is_ready(self) -> bool:
        """Check if enough observations have accumulated for prediction."""
        return len(self._buffer) >= 10  # Minimum 10 seconds of data

    def predict(self) -> tuple[str, float, float, Optional[np.ndarray]]:
        """
        Run temporal prediction on the accumulated buffer.

        Returns:
            (trend_name, trend_confidence, microsleep_probability, attention_weights)
            Returns ("STABLE", 0.5, 0.0, None) if insufficient data.
        """
        if not self.is_ready():
            return "STABLE", 0.5, 0.0, None

        # Pad or truncate to sequence_length
        buffer_arr = np.array(self._buffer, dtype=np.float32)
        if len(buffer_arr) < self.sequence_length:
            # Pad with zeros at the beginning
            padding = np.zeros(
                (self.sequence_length - len(buffer_arr), self.input_size),
                dtype=np.float32,
            )
            buffer_arr = np.concatenate([padding, buffer_arr], axis=0)

        # Shape: (1, seq_len, input_size)
        x = torch.from_numpy(buffer_arr).unsqueeze(0).to(self.device)

        return self._model.predict(x)

    def reset(self) -> None:
        """Clear the observation buffer."""
        self._buffer.clear()
        logger.info("TemporalLSTM buffer reset")
