"""
PRAHARI — Stage 2: Facial Feature Extraction

Extracts fatigue-related biometric features from facial landmarks:
- Eye Aspect Ratio (EAR)
- Mouth Aspect Ratio (MAR)
- Blink detection (frequency, duration)
- PERCLOS (percentage of eye closure)
- Head pose estimation (pitch, yaw, roll)
- Yawning detection
- Eye closure duration tracking

All features are computed in real-time with sliding window buffers
for temporal context.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np
from scipy.spatial import distance as dist

from prahari.detection.face_detector import FaceDetection

logger = logging.getLogger("prahari.detection.features")


@dataclass
class FeatureVector:
    """Complete feature vector extracted from a single frame observation."""

    timestamp: float = 0.0

    # Eye metrics
    ear_left: float = 0.0
    ear_right: float = 0.0
    ear_avg: float = 0.0
    eyes_closed: bool = False

    # Mouth metrics
    mar: float = 0.0
    is_yawning: bool = False

    # Blink metrics
    blink_count: int = 0          # Total blinks in window
    blink_rate: float = 0.0       # Blinks per minute
    avg_blink_duration: float = 0.0  # Average blink duration (seconds)
    current_closure_duration: float = 0.0  # How long eyes have been closed now

    # PERCLOS
    perclos: float = 0.0          # Percentage of eye closure over window

    # Head pose
    head_pitch: float = 0.0       # Degrees — positive = looking down
    head_yaw: float = 0.0         # Degrees — positive = looking right
    head_roll: float = 0.0        # Degrees — positive = tilting right
    head_drooping: bool = False

    # Yawning
    yawn_count: int = 0           # Yawns in window
    yawn_frequency: float = 0.0   # Yawns per 5 minutes

    # Face presence
    face_detected: bool = False
    face_absent_duration: float = 0.0
    detection_confidence: float = 0.0

    def to_array(self) -> np.ndarray:
        """Convert to a numeric feature array for model input (16 features)."""
        return np.array([
            self.ear_avg,
            self.mar,
            self.blink_rate,
            self.avg_blink_duration,
            self.current_closure_duration,
            self.perclos,
            self.head_pitch,
            self.head_yaw,
            self.head_roll,
            self.yawn_frequency,
            float(self.eyes_closed),
            float(self.is_yawning),
            float(self.head_drooping),
            float(self.face_detected),
            self.face_absent_duration,
            self.detection_confidence,
        ], dtype=np.float32)

    @staticmethod
    def feature_names() -> list[str]:
        return [
            "ear_avg", "mar", "blink_rate", "avg_blink_duration",
            "current_closure_duration", "perclos", "head_pitch", "head_yaw",
            "head_roll", "yawn_frequency", "eyes_closed", "is_yawning",
            "head_drooping", "face_detected", "face_absent_duration",
            "detection_confidence",
        ]


class FeatureExtractor:
    """
    Extracts fatigue-related biometric features from MediaPipe FaceMesh
    landmarks with temporal buffering and sliding window analysis.
    """

    # MediaPipe FaceMesh landmark indices for EAR computation
    # Left eye: 6 key points
    LEFT_EYE_EAR = [33, 160, 158, 133, 153, 144]
    # Right eye: 6 key points
    RIGHT_EYE_EAR = [362, 385, 387, 263, 373, 380]

    # Mouth landmarks for MAR — outer lips vertical + horizontal
    MOUTH_MAR_OUTER = [61, 291, 0, 17]  # left, right, top, bottom corners
    MOUTH_MAR_INNER_TOP = [13]
    MOUTH_MAR_INNER_BOTTOM = [14]
    MOUTH_VERTICAL = [81, 178, 311, 402]  # Additional vertical points

    # 3D model points for head pose estimation (generic face model)
    MODEL_POINTS_3D = np.array([
        (0.0, 0.0, 0.0),             # Nose tip (index 1)
        (0.0, -330.0, -65.0),        # Chin (index 152)
        (-225.0, 170.0, -135.0),     # Left eye left corner (index 33)
        (225.0, 170.0, -135.0),      # Right eye right corner (index 263)
        (-150.0, -150.0, -125.0),    # Left mouth corner (index 61)
        (150.0, -150.0, -125.0),     # Right mouth corner (index 291)
    ], dtype=np.float64)

    POSE_LANDMARK_INDICES = [1, 152, 33, 263, 61, 291]

    def __init__(
        self,
        ear_threshold: float = 0.21,
        ear_consec_frames: int = 3,
        mar_threshold: float = 0.65,
        mar_consec_frames: int = 10,
        perclos_window: int = 60,
        blink_min_duration: float = 0.1,
        blink_max_duration: float = 0.4,
        head_pitch_threshold: float = 15.0,
        head_yaw_threshold: float = 30.0,
        head_droop_duration: float = 2.0,
        blink_rate_window: int = 60,
        yawn_rate_window: int = 300,
        fps: int = 30,
    ):
        self.ear_threshold = ear_threshold
        self.ear_consec_frames = ear_consec_frames
        self.mar_threshold = mar_threshold
        self.mar_consec_frames = mar_consec_frames
        self.perclos_window = perclos_window
        self.blink_min_duration = blink_min_duration
        self.blink_max_duration = blink_max_duration
        self.head_pitch_threshold = head_pitch_threshold
        self.head_yaw_threshold = head_yaw_threshold
        self.head_droop_duration = head_droop_duration
        self.fps = fps

        # ── Sliding window buffers ──────────────────────────────
        buffer_size = perclos_window * fps  # e.g., 60s × 30fps = 1800 frames
        self._ear_buffer: deque[float] = deque(maxlen=buffer_size)
        self._eye_closed_buffer: deque[bool] = deque(maxlen=buffer_size)

        # Blink tracking
        self._blink_timestamps: deque[float] = deque(maxlen=500)
        self._blink_durations: deque[float] = deque(maxlen=500)
        self._consecutive_closed: int = 0
        self._blink_start_time: Optional[float] = None
        self._is_blinking: bool = False
        self._blink_rate_window = blink_rate_window

        # Yawn tracking
        self._yawn_timestamps: deque[float] = deque(maxlen=100)
        self._consecutive_yawn: int = 0
        self._is_yawning: bool = False
        self._yawn_rate_window = yawn_rate_window

        # Head pose tracking
        self._head_droop_start: Optional[float] = None

        # Face absence tracking
        self._face_lost_time: Optional[float] = None

        # Camera matrix (approximate — recalculated on first frame)
        self._camera_matrix: Optional[np.ndarray] = None
        self._dist_coeffs = np.zeros((4, 1), dtype=np.float64)

        logger.info(
            "FeatureExtractor initialized — EAR=%.2f, MAR=%.2f, PERCLOS window=%ds",
            ear_threshold,
            mar_threshold,
            perclos_window,
        )

    def _compute_ear(self, landmarks_px: np.ndarray, eye_indices: list[int]) -> float:
        """
        Compute Eye Aspect Ratio for one eye.

        EAR = (‖p2−p6‖ + ‖p3−p5‖) / (2 · ‖p1−p4‖)

        Where p1-p6 are the 6 eye landmark points in order:
        p1=corner_left, p2=upper_lid_1, p3=upper_lid_2,
        p4=corner_right, p5=lower_lid_2, p6=lower_lid_1
        """
        pts = landmarks_px[eye_indices]
        # Vertical distances
        v1 = dist.euclidean(pts[1], pts[5])  # p2-p6
        v2 = dist.euclidean(pts[2], pts[4])  # p3-p5
        # Horizontal distance
        h = dist.euclidean(pts[0], pts[3])   # p1-p4

        if h == 0:
            return 0.0
        return (v1 + v2) / (2.0 * h)

    def _compute_mar(self, landmarks_px: np.ndarray) -> float:
        """
        Compute Mouth Aspect Ratio for yawn detection.

        MAR = vertical_opening / horizontal_opening
        """
        # Inner mouth vertical distance
        top = landmarks_px[13]     # Upper inner lip
        bottom = landmarks_px[14]  # Lower inner lip
        vertical = dist.euclidean(top, bottom)

        # Additional vertical measurements for robustness
        v2 = dist.euclidean(landmarks_px[81], landmarks_px[178])
        v3 = dist.euclidean(landmarks_px[311], landmarks_px[402])

        # Horizontal mouth distance
        left = landmarks_px[61]
        right = landmarks_px[291]
        horizontal = dist.euclidean(left, right)

        if horizontal == 0:
            return 0.0
        return (vertical + v2 + v3) / (3.0 * horizontal)

    def _estimate_head_pose(
        self, landmarks_px: np.ndarray, frame_h: int, frame_w: int
    ) -> tuple[float, float, float]:
        """
        Estimate head pose (pitch, yaw, roll) using PnP solver.

        Returns (pitch, yaw, roll) in degrees.
        """
        # Initialize camera matrix if needed
        if self._camera_matrix is None or self._camera_matrix[0, 2] != frame_w / 2:
            focal_length = frame_w
            center = (frame_w / 2, frame_h / 2)
            self._camera_matrix = np.array([
                [focal_length, 0, center[0]],
                [0, focal_length, center[1]],
                [0, 0, 1],
            ], dtype=np.float64)

        # Extract 2D image points for the 6 key landmarks
        image_points = landmarks_px[self.POSE_LANDMARK_INDICES].astype(np.float64)

        # Solve PnP
        success, rotation_vec, translation_vec = cv2.solvePnP(
            self.MODEL_POINTS_3D,
            image_points,
            self._camera_matrix,
            self._dist_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE,
        )

        if not success:
            return 0.0, 0.0, 0.0

        # Convert rotation vector to rotation matrix
        rotation_mat, _ = cv2.Rodrigues(rotation_vec)

        # Decompose to Euler angles
        proj_matrix = np.hstack((rotation_mat, translation_vec))
        _, _, _, _, _, _, euler_angles = cv2.decomposeProjectionMatrix(
            np.vstack((proj_matrix, [0, 0, 0, 1]))[:3]
        )

        pitch = float(euler_angles[0])
        yaw = float(euler_angles[1])
        roll = float(euler_angles[2])

        # Normalize angles to be between -90 and 90
        # OpenCV decomposeProjectionMatrix often returns values around +/- 180
        if pitch > 90:
            pitch -= 180
        elif pitch < -90:
            pitch += 180
            
        if yaw > 90:
            yaw -= 180
        elif yaw < -90:
            yaw += 180
            
        if roll > 90:
            roll -= 180
        elif roll < -90:
            roll += 180

        return pitch, yaw, roll

    def extract(self, detection: FaceDetection) -> FeatureVector:
        """
        Extract all fatigue features from a face detection result.

        Args:
            detection: FaceDetection from FaceDetector.detect()

        Returns:
            FeatureVector with all computed metrics.
        """
        now = time.time()
        fv = FeatureVector(timestamp=now)

        # ── Handle face absence ─────────────────────────────────
        if not detection.detected:
            if self._face_lost_time is None:
                self._face_lost_time = now
            fv.face_detected = False
            fv.face_absent_duration = now - self._face_lost_time
            # Do not count missing face as closed eyes for PERCLOS accuracy
            self._eye_closed_buffer.append(False)
            return fv

        self._face_lost_time = None
        fv.face_detected = True
        fv.detection_confidence = detection.confidence
        frame_h, frame_w = detection.frame_shape

        landmarks = detection.landmarks_px

        # ── EAR Computation ─────────────────────────────────────
        ear_left = self._compute_ear(landmarks, self.LEFT_EYE_EAR)
        ear_right = self._compute_ear(landmarks, self.RIGHT_EYE_EAR)
        ear_avg = (ear_left + ear_right) / 2.0

        fv.ear_left = ear_left
        fv.ear_right = ear_right
        fv.ear_avg = ear_avg

        eyes_closed = ear_avg < self.ear_threshold
        fv.eyes_closed = eyes_closed

        # Buffer for PERCLOS
        self._ear_buffer.append(ear_avg)
        self._eye_closed_buffer.append(eyes_closed)

        # ── Blink Detection ─────────────────────────────────────
        if eyes_closed:
            self._consecutive_closed += 1
            if self._blink_start_time is None:
                self._blink_start_time = now
            fv.current_closure_duration = now - self._blink_start_time
        else:
            if self._blink_start_time is not None:
                blink_duration = now - self._blink_start_time
                if self.blink_min_duration <= blink_duration <= self.blink_max_duration:
                    # Valid blink detected
                    self._blink_timestamps.append(now)
                    self._blink_durations.append(blink_duration)
                self._blink_start_time = None
            self._consecutive_closed = 0
            fv.current_closure_duration = 0.0

        # Blink rate (blinks per minute) over the rate window
        cutoff = now - self._blink_rate_window
        recent_blinks = [t for t in self._blink_timestamps if t > cutoff]
        fv.blink_count = len(recent_blinks)
        fv.blink_rate = len(recent_blinks) * (60.0 / self._blink_rate_window)

        # Average blink duration
        recent_durations = [
            d for t, d in zip(self._blink_timestamps, self._blink_durations)
            if t > cutoff
        ]
        fv.avg_blink_duration = (
            float(np.mean(recent_durations)) if recent_durations else 0.0
        )

        # ── PERCLOS ─────────────────────────────────────────────
        if len(self._eye_closed_buffer) > 0:
            closed_count = sum(self._eye_closed_buffer)
            fv.perclos = closed_count / len(self._eye_closed_buffer)

        # ── MAR / Yawn Detection ────────────────────────────────
        mar = self._compute_mar(landmarks)
        fv.mar = mar
        is_yawning = mar > self.mar_threshold

        if is_yawning:
            self._consecutive_yawn += 1
            if (
                self._consecutive_yawn >= self.mar_consec_frames
                and not self._is_yawning
            ):
                # New yawn detected
                self._is_yawning = True
                self._yawn_timestamps.append(now)
        else:
            self._consecutive_yawn = 0
            self._is_yawning = False

        fv.is_yawning = self._is_yawning

        # Yawn frequency (yawns per 5 minutes)
        yawn_cutoff = now - self._yawn_rate_window
        recent_yawns = [t for t in self._yawn_timestamps if t > yawn_cutoff]
        fv.yawn_count = len(recent_yawns)
        fv.yawn_frequency = len(recent_yawns) * (300.0 / self._yawn_rate_window)

        # ── Head Pose Estimation ────────────────────────────────
        try:
            pitch, yaw, roll = self._estimate_head_pose(landmarks, frame_h, frame_w)
            fv.head_pitch = pitch
            fv.head_yaw = yaw
            fv.head_roll = roll

            # Head drooping detection
            if abs(pitch) > self.head_pitch_threshold:
                if self._head_droop_start is None:
                    self._head_droop_start = now
                elif now - self._head_droop_start > self.head_droop_duration:
                    fv.head_drooping = True
            else:
                self._head_droop_start = None
                fv.head_drooping = False

        except Exception as e:
            logger.debug("Head pose estimation failed: %s", e)

        return fv

    def reset(self) -> None:
        """Reset all internal buffers and state."""
        self._ear_buffer.clear()
        self._eye_closed_buffer.clear()
        self._blink_timestamps.clear()
        self._blink_durations.clear()
        self._yawn_timestamps.clear()
        self._consecutive_closed = 0
        self._consecutive_yawn = 0
        self._blink_start_time = None
        self._is_blinking = False
        self._is_yawning = False
        self._head_droop_start = None
        self._face_lost_time = None
        logger.info("FeatureExtractor buffers reset")
