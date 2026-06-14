"""
PRAHARI — Tests for Deep Learning Models

Tests for model architectures, forward pass shapes, and inference wrappers.
"""

import numpy as np
import pytest
import torch


class TestFatigueCNN:
    """Tests for the FatigueCNN model."""

    @pytest.fixture
    def model(self):
        from prahari.models.fatigue_cnn import FatigueCNN
        return FatigueCNN(num_classes=5)

    def test_forward_shape(self, model):
        x = torch.randn(2, 3, 224, 224)
        output = model(x)
        assert output.shape == (2, 5), f"Expected (2,5), got {output.shape}"

    def test_single_prediction(self, model):
        x = torch.randn(1, 3, 224, 224)
        pred_idx, probs = model.predict(x)
        assert 0 <= pred_idx <= 4
        assert probs.shape == (5,)
        assert abs(probs.sum() - 1.0) < 1e-5, "Probabilities should sum to 1"

    def test_class_name_prediction(self, model):
        x = torch.randn(1, 3, 224, 224)
        name, conf, probs = model.predict_class_name(x)
        assert name in model.CLASS_NAMES
        assert 0.0 <= conf <= 1.0
        assert probs.shape == (5,)

    def test_parameter_count(self, model):
        total = sum(p.numel() for p in model.parameters())
        # Should be reasonable — not too large for real-time
        assert total < 10_000_000, f"Model too large: {total} params"
        assert total > 100_000, f"Model too small: {total} params"

    def test_gradient_flow(self, model):
        x = torch.randn(2, 3, 224, 224)
        labels = torch.tensor([0, 3])
        output = model(x)
        loss = torch.nn.functional.cross_entropy(output, labels)
        loss.backward()
        # Check gradients exist
        for name, param in model.named_parameters():
            if param.requires_grad:
                assert param.grad is not None, f"No gradient for {name}"


class TestFatigueCNNInference:
    """Tests for the production inference wrapper."""

    def test_preprocess(self):
        from prahari.models.fatigue_cnn import FatigueCNNInference
        inference = FatigueCNNInference(model_path=None)

        # Create a fake BGR face ROI
        face = np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8)
        tensor = inference.preprocess(face)

        assert tensor.shape == (1, 3, 224, 224)
        assert tensor.dtype == torch.float32

    def test_classify(self):
        from prahari.models.fatigue_cnn import FatigueCNNInference
        inference = FatigueCNNInference(model_path=None)

        face = np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8)
        name, conf, probs = inference.classify(face)

        assert name in ["ALERT", "SLIGHTLY_FATIGUED", "FATIGUED", "SEVERE_FATIGUE", "MICROSLEEP"]
        assert 0.0 <= conf <= 1.0
        assert len(probs) == 5

    def test_fatigue_score(self):
        from prahari.models.fatigue_cnn import FatigueCNNInference
        inference = FatigueCNNInference()

        # Full alert
        alert_probs = np.array([1.0, 0.0, 0.0, 0.0, 0.0])
        assert inference.get_fatigue_score(alert_probs) == 0.0

        # Full microsleep
        ms_probs = np.array([0.0, 0.0, 0.0, 0.0, 1.0])
        assert inference.get_fatigue_score(ms_probs) == 100.0


class TestTemporalLSTM:
    """Tests for the TemporalLSTM model."""

    @pytest.fixture
    def model(self):
        from prahari.models.temporal_lstm import TemporalLSTM
        return TemporalLSTM(input_size=16, hidden_size=64, num_layers=2)

    def test_forward_shape(self, model):
        x = torch.randn(4, 60, 16)
        trend, ms_prob, attn = model(x)
        assert trend.shape == (4, 3)
        assert ms_prob.shape == (4, 1)
        assert attn.shape == (4, 60)

    def test_microsleep_sigmoid(self, model):
        x = torch.randn(2, 60, 16)
        _, ms_prob, _ = model(x)
        assert (ms_prob >= 0).all() and (ms_prob <= 1).all()

    def test_attention_softmax(self, model):
        x = torch.randn(2, 60, 16)
        _, _, attn = model(x)
        sums = attn.sum(dim=1)
        assert torch.allclose(sums, torch.ones_like(sums), atol=1e-5)

    def test_predict(self, model):
        x = torch.randn(1, 60, 16)
        trend, conf, ms_prob, attn = model.predict(x)
        assert trend in ["IMPROVING", "STABLE", "DEGRADING"]
        assert 0.0 <= conf <= 1.0
        assert 0.0 <= ms_prob <= 1.0


class TestFusionEngine:
    """Tests for the multi-modal fusion engine."""

    @pytest.fixture
    def engine(self):
        from prahari.models.fusion_engine import FusionEngine
        return FusionEngine()

    def test_alert_state(self, engine):
        result = engine.fuse(
            cnn_probs=np.array([1.0, 0.0, 0.0, 0.0, 0.0]),
            perclos=0.05,
            ear_avg=0.30,
            blink_rate=15,
        )
        assert result.cai < 30, "Alert state should have low CAI"
        assert result.alertness_score > 70

    def test_critical_state(self, engine):
        result = engine.fuse(
            cnn_probs=np.array([0.0, 0.0, 0.0, 0.1, 0.9]),
            perclos=0.45,
            ear_avg=0.10,
            blink_rate=5,
            current_closure_duration=3.0,
            head_drooping=True,
            microsleep_prob=0.9,
            temporal_trend="DEGRADING",
            temporal_confidence=0.95,
        )
        assert result.cai > 80, "Critical state should have high CAI"

    def test_eye_closure_override(self, engine):
        result = engine.fuse(current_closure_duration=3.0)
        assert result.cai >= 95, "Extended eye closure should force CAI >= 95"

    def test_face_absent_override(self, engine):
        result = engine.fuse(face_detected=False)
        assert result.cai >= 80, "Missing face should force CAI >= 80"

    def test_ema_smoothing(self, engine):
        engine.fuse(perclos=0.0, ear_avg=0.35)  # Low
        result = engine.fuse(perclos=0.5, ear_avg=0.05)  # Suddenly high
        # Smoothed value should be less than raw
        assert result.cai_smoothed <= result.cai + 5
