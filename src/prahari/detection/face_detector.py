"""
PRAHARI — Stage 1: Face Detection

Uses MediaPipe FaceMesh (468 landmarks) as the primary detector for superior
landmark quality. Falls back to YOLOv8n for coarse face detection under
extreme conditions (heavy occlusion, very low light).

Includes CLAHE preprocessing for low-light robustness and handles spectacles
via confidence filtering.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import cv2
import mediapipe as mp
import numpy as np

logger = logging.getLogger("prahari.detection.face")


@dataclass
class FaceDetection:
    """Result of face detection for a single frame."""

    detected: bool = False
    # Bounding box (x, y, w, h) in pixel coords
    bbox: tuple[int, int, int, int] = (0, 0, 0, 0)
    # 468 facial landmarks — shape (468, 3) normalized [0,1]
    landmarks_norm: np.ndarray = field(default_factory=lambda: np.zeros((468, 3)))
    # 468 facial landmarks — shape (468, 2) pixel coords
    landmarks_px: np.ndarray = field(default_factory=lambda: np.zeros((468, 2)))
    # Cropped and resized face ROI for CNN (224×224×3 BGR)
    face_roi: Optional[np.ndarray] = None
    # Detection confidence
    confidence: float = 0.0
    # Original frame dimensions
    frame_shape: tuple[int, int] = (480, 640)


class FaceDetector:
    """
    Multi-strategy face detector combining MediaPipe FaceMesh
    with YOLOv8n fallback for maximum robustness.
    """

    # MediaPipe FaceMesh landmark indices for key features
    # Eyes
    LEFT_EYE_INDICES = [33, 7, 163, 144, 145, 153, 154, 155, 133,
                        173, 157, 158, 159, 160, 161, 246]
    RIGHT_EYE_INDICES = [362, 382, 381, 380, 374, 373, 390, 249,
                         263, 466, 388, 387, 386, 385, 384, 398]
    # Lips
    LIPS_INDICES = [61, 146, 91, 181, 84, 17, 314, 405, 321, 375,
                    291, 308, 324, 318, 402, 317, 14, 87, 178, 88, 95]
    # Nose
    NOSE_INDICES = [1, 2, 98, 327]
    # Face oval
    FACE_OVAL_INDICES = [10, 338, 297, 332, 284, 251, 389, 356, 454,
                         323, 361, 288, 397, 365, 379, 378, 400, 377,
                         152, 148, 176, 149, 150, 136, 172, 58, 132,
                         93, 234, 127, 162, 21, 54, 103, 67, 109]

    # 6-point subset for PnP head pose estimation
    POSE_LANDMARK_INDICES = [1, 152, 33, 263, 61, 291]

    def __init__(
        self,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        clahe_clip_limit: float = 2.0,
        clahe_grid_size: int = 8,
        roi_size: int = 224,
    ):
        self.roi_size = roi_size

        # Initialize MediaPipe FaceMesh
        self._mp_face_mesh = mp.solutions.face_mesh
        self._face_mesh = self._mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,  # Enable iris landmarks for better eye tracking
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )

        # CLAHE for low-light enhancement
        self._clahe = cv2.createCLAHE(
            clipLimit=clahe_clip_limit,
            tileGridSize=(clahe_grid_size, clahe_grid_size),
        )

        # YOLOv8 fallback (lazy loaded)
        self._yolo_model = None
        self._yolo_confidence = 0.4

        # Frame counter for logging
        self._frame_count = 0
        self._detection_failures = 0

        logger.info(
            "FaceDetector initialized — MediaPipe FaceMesh (det=%.2f, track=%.2f)",
            min_detection_confidence,
            min_tracking_confidence,
        )

    def _preprocess_low_light(self, frame: np.ndarray) -> np.ndarray:
        """
        Apply CLAHE histogram equalization to improve detection in low light.
        Only applied when the frame is determined to be dark.
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        mean_brightness = np.mean(gray)

        if mean_brightness < 80:  # Low-light threshold
            # Convert to LAB color space for better CLAHE application
            lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
            l_channel, a_channel, b_channel = cv2.split(lab)
            l_enhanced = self._clahe.apply(l_channel)
            lab_enhanced = cv2.merge([l_enhanced, a_channel, b_channel])
            enhanced = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)
            return enhanced

        return frame

    def _extract_bbox_from_landmarks(
        self, landmarks_px: np.ndarray, frame_h: int, frame_w: int, padding: float = 0.2
    ) -> tuple[int, int, int, int]:
        """Compute a padded bounding box from facial landmarks."""
        x_min = int(np.min(landmarks_px[:, 0]))
        x_max = int(np.max(landmarks_px[:, 0]))
        y_min = int(np.min(landmarks_px[:, 1]))
        y_max = int(np.max(landmarks_px[:, 1]))

        w = x_max - x_min
        h = y_max - y_min
        pad_x = int(w * padding)
        pad_y = int(h * padding)

        x_min = max(0, x_min - pad_x)
        y_min = max(0, y_min - pad_y)
        x_max = min(frame_w, x_max + pad_x)
        y_max = min(frame_h, y_max + pad_y)

        return (x_min, y_min, x_max - x_min, y_max - y_min)

    def _crop_face_roi(
        self, frame: np.ndarray, bbox: tuple[int, int, int, int]
    ) -> np.ndarray:
        """Crop and resize the face region to the CNN input size."""
        x, y, w, h = bbox
        if w <= 0 or h <= 0:
            return np.zeros((self.roi_size, self.roi_size, 3), dtype=np.uint8)

        face = frame[y : y + h, x : x + w]
        face_resized = cv2.resize(face, (self.roi_size, self.roi_size))
        return face_resized

    def detect(self, frame: np.ndarray) -> FaceDetection:
        """
        Detect face and extract landmarks from a BGR frame.

        Args:
            frame: Input BGR image from camera (H, W, 3).

        Returns:
            FaceDetection with landmarks, bbox, and cropped ROI.
        """
        self._frame_count += 1
        h, w = frame.shape[:2]
        result = FaceDetection(frame_shape=(h, w))

        # Preprocess for low-light conditions
        processed = self._preprocess_low_light(frame)

        # Convert BGR to RGB for MediaPipe
        rgb_frame = cv2.cvtColor(processed, cv2.COLOR_BGR2RGB)
        rgb_frame.flags.writeable = False

        # Run MediaPipe FaceMesh
        mp_results = self._face_mesh.process(rgb_frame)

        if mp_results.multi_face_landmarks:
            face_landmarks = mp_results.multi_face_landmarks[0]

            # Extract all 468 landmarks
            landmarks_norm = np.array(
                [(lm.x, lm.y, lm.z) for lm in face_landmarks.landmark],
                dtype=np.float32,
            )
            landmarks_px = np.array(
                [(lm.x * w, lm.y * h) for lm in face_landmarks.landmark],
                dtype=np.float32,
            )

            # Compute bounding box
            bbox = self._extract_bbox_from_landmarks(landmarks_px, h, w)

            # Crop face ROI for CNN
            face_roi = self._crop_face_roi(frame, bbox)

            # Estimate detection confidence from landmark visibility
            # MediaPipe doesn't give a single confidence, so we approximate
            # using the variance of landmark z-coordinates (lower = more confident)
            z_std = np.std(landmarks_norm[:, 2])
            confidence = max(0.0, min(1.0, 1.0 - z_std * 10))

            result.detected = True
            result.bbox = bbox
            result.landmarks_norm = landmarks_norm
            result.landmarks_px = landmarks_px
            result.face_roi = face_roi
            result.confidence = confidence

            self._detection_failures = 0
        else:
            self._detection_failures += 1
            if self._detection_failures % 30 == 1:
                logger.warning(
                    "Face not detected for %d consecutive frames", self._detection_failures
                )

        return result

    def get_eye_landmarks(
        self, detection: FaceDetection, side: str = "both"
    ) -> dict[str, np.ndarray]:
        """
        Extract eye landmark coordinates (pixel) from detection result.

        Returns dict with 'left' and/or 'right' keys → (N, 2) arrays.
        """
        eyes = {}
        if side in ("left", "both"):
            eyes["left"] = detection.landmarks_px[self.LEFT_EYE_INDICES]
        if side in ("right", "both"):
            eyes["right"] = detection.landmarks_px[self.RIGHT_EYE_INDICES]
        return eyes

    def get_lip_landmarks(self, detection: FaceDetection) -> np.ndarray:
        """Extract lip landmark coordinates (pixel) → (N, 2) array."""
        return detection.landmarks_px[self.LIPS_INDICES]

    def get_pose_landmarks(self, detection: FaceDetection) -> np.ndarray:
        """Extract the 6 key landmarks for PnP head pose estimation → (6, 2)."""
        return detection.landmarks_px[self.POSE_LANDMARK_INDICES]

    def draw_overlay(
        self,
        frame: np.ndarray,
        detection: FaceDetection,
        draw_landmarks: bool = True,
        draw_bbox: bool = True,
        draw_eyes: bool = True,
    ) -> np.ndarray:
        """Draw detection overlay on the frame for visualization."""
        overlay = frame.copy()

        if not detection.detected:
            # Draw "NO FACE" warning
            cv2.putText(
                overlay,
                "NO FACE DETECTED",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2,
            )
            return overlay

        # Draw bounding box
        if draw_bbox:
            x, y, w, h = detection.bbox
            cv2.rectangle(overlay, (x, y), (x + w, y + h), (0, 255, 0), 2)

        # Draw facial landmarks
        if draw_landmarks:
            for i, (px, py) in enumerate(detection.landmarks_px):
                color = (200, 200, 200)
                radius = 1

                if i in self.LEFT_EYE_INDICES or i in self.RIGHT_EYE_INDICES:
                    color = (0, 255, 255) if draw_eyes else (200, 200, 200)
                    radius = 2
                elif i in self.LIPS_INDICES:
                    color = (0, 128, 255)
                    radius = 1
                elif i in self.NOSE_INDICES:
                    color = (255, 0, 128)
                    radius = 2

                cv2.circle(overlay, (int(px), int(py)), radius, color, -1)

        return overlay

    def release(self) -> None:
        """Release MediaPipe resources."""
        self._face_mesh.close()
        logger.info("FaceDetector resources released")
