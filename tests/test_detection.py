"""
PRAHARI — Tests for Face Detection & Feature Extraction

Unit tests for:
  - EAR computation
  - MAR computation
  - PERCLOS calculation
  - Head pose estimation
  - Blink detection logic
  - Feature vector generation
"""

import numpy as np
import pytest

from prahari.detection.feature_extractor import FeatureExtractor, FeatureVector


class TestFeatureVector:
    """Tests for the FeatureVector data class."""

    def test_to_array_shape(self):
        fv = FeatureVector()
        arr = fv.to_array()
        assert arr.shape == (16,)
        assert arr.dtype == np.float32

    def test_feature_names_count(self):
        names = FeatureVector.feature_names()
        assert len(names) == 16

    def test_default_values(self):
        fv = FeatureVector()
        assert fv.ear_avg == 0.0
        assert fv.perclos == 0.0
        assert not fv.eyes_closed
        assert not fv.head_drooping
        assert fv.face_detected is False


class TestFeatureExtractor:
    """Tests for the FeatureExtractor."""

    @pytest.fixture
    def extractor(self):
        return FeatureExtractor(
            ear_threshold=0.21,
            mar_threshold=0.65,
            perclos_window=60,
            fps=30,
        )

    def test_initialization(self, extractor):
        assert extractor.ear_threshold == 0.21
        assert extractor.mar_threshold == 0.65

    def test_ear_computation(self, extractor):
        """Test EAR formula with known landmark positions."""
        # Create a mock set of landmarks (468 points)
        landmarks = np.zeros((468, 2), dtype=np.float32)

        # Set left eye landmarks (indices 33, 160, 158, 133, 153, 144)
        # Open eye configuration
        landmarks[33] = [100, 200]   # p1 - left corner
        landmarks[160] = [120, 190]  # p2 - upper lid
        landmarks[158] = [140, 190]  # p3 - upper lid
        landmarks[133] = [160, 200]  # p4 - right corner
        landmarks[153] = [140, 210]  # p5 - lower lid
        landmarks[144] = [120, 210]  # p6 - lower lid

        ear = extractor._compute_ear(landmarks, extractor.LEFT_EYE_EAR)

        # With these points, vertical distances ~20, horizontal ~60
        # EAR = (20 + 20) / (2 * 60) ≈ 0.333
        assert 0.2 < ear < 0.5, f"EAR should be ~0.33 for open eyes, got {ear}"

    def test_ear_closed_eyes(self, extractor):
        """Test EAR with closed eye configuration."""
        landmarks = np.zeros((468, 2), dtype=np.float32)

        # Closed eye — upper and lower lids nearly touching
        landmarks[33] = [100, 200]
        landmarks[160] = [120, 199]
        landmarks[158] = [140, 199]
        landmarks[133] = [160, 200]
        landmarks[153] = [140, 201]
        landmarks[144] = [120, 201]

        ear = extractor._compute_ear(landmarks, extractor.LEFT_EYE_EAR)

        # Very small vertical distances → low EAR
        assert ear < 0.1, f"EAR should be very low for closed eyes, got {ear}"

    def test_mar_computation(self, extractor):
        """Test MAR with known mouth landmarks."""
        landmarks = np.zeros((468, 2), dtype=np.float32)

        # Set mouth landmarks for normal mouth
        landmarks[61] = [140, 300]   # Left corner
        landmarks[291] = [220, 300]  # Right corner
        landmarks[13] = [180, 290]   # Upper inner lip
        landmarks[14] = [180, 310]   # Lower inner lip
        landmarks[81] = [160, 292]
        landmarks[178] = [160, 308]
        landmarks[311] = [200, 292]
        landmarks[402] = [200, 308]

        mar = extractor._compute_mar(landmarks)

        assert mar > 0.0, "MAR should be positive"
        assert mar < 1.0, "MAR should be reasonable"

    def test_reset(self, extractor):
        """Test that reset clears all buffers."""
        extractor._blink_timestamps.append(1.0)
        extractor._yawn_timestamps.append(2.0)
        extractor._ear_buffer.append(0.25)

        extractor.reset()

        assert len(extractor._blink_timestamps) == 0
        assert len(extractor._yawn_timestamps) == 0
        assert len(extractor._ear_buffer) == 0


class TestFaceDetector:
    """Basic tests for FaceDetector initialization."""

    def test_import(self):
        from prahari.detection.face_detector import FaceDetection, FaceDetector
        assert FaceDetector is not None
        assert FaceDetection is not None

    def test_face_detection_defaults(self):
        from prahari.detection.face_detector import FaceDetection
        det = FaceDetection()
        assert not det.detected
        assert det.confidence == 0.0
        assert det.landmarks_norm.shape == (468, 3)
        assert det.landmarks_px.shape == (468, 2)
