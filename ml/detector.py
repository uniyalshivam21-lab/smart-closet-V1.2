"""
Camera-based clothing detection using OpenCV + lightweight ML.

Important constraint: NO RFID or tags are used; detection is purely
camera-based.

For this conceptual demo:
-------------------------
- We implement a simple detector that:
  * Captures a frame from the USB camera.
  * Splits the image horizontally into `slots` segments.
  * For each segment, extracts a simple color histogram.
  * Uses a lightweight classifier (or deterministic heuristic) to
    decide a clothing type label such as "shirt", "pants", "jacket".

You can later replace the classifier with:
- A scikit-learn model loaded via joblib.
- A tiny CNN (TensorFlow Lite) running on Raspberry Pi.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict

import cv2
import numpy as np
from joblib import load


class ClothingDetector:
    """
    Wrapper around OpenCV + ML classifier for clothing type detection.
    """

    def __init__(
        self,
        camera_index: int = 0,
        model_path: Path | None = None,
    ) -> None:
        self._logger = logging.getLogger(self.__class__.__name__)
        self.camera_index = camera_index
        self.model = None

        # Optional pre-trained model for more advanced use.
        if model_path is not None and model_path.exists():
            self._logger.info("Loading ML model from %s", model_path)
            self.model = load(model_path)
        else:
            self._logger.info("No ML model provided; using heuristic classifier.")

    def _capture_frame(self) -> np.ndarray:
        """
        Capture a single frame from the USB camera.
        """
        cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            raise RuntimeError("Could not open camera. Check USB connection/index.")

        ret, frame = cap.read()
        cap.release()
        if not ret:
            raise RuntimeError("Failed to read frame from camera.")
        return frame

    def _extract_feature(self, image: np.ndarray) -> np.ndarray:
        """
        Compute a very small feature vector for an image segment.

        For prototype purposes we use a coarse color histogram in HSV space.
        """
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [8, 8], [0, 180, 0, 256])
        cv2.normalize(hist, hist)
        return hist.flatten()

    def _heuristic_classify(self, feature: np.ndarray) -> str:
        """
        Lightweight heuristic classifier mapping color distribution to clothing type.

        This is intentionally simple and deterministic for educational purposes.
        Example rule:
        - If hue is concentrated in low range -> maybe "pants".
        - If hue is mid range -> "shirt".
        - If hue is high range -> "jacket".
        """
        # Approximate dominant hue bucket by summing along saturation axis
        hue_bins = feature.reshape(8, 8).sum(axis=1)
        dominant_idx = int(np.argmax(hue_bins))

        if dominant_idx < 2:
            return "pants"
        if dominant_idx < 5:
            return "shirt"
        return "jacket"

    def predict_segment(self, segment: np.ndarray) -> str:
        """
        Classify a single image segment corresponding to one carousel slot.
        """
        feat = self._extract_feature(segment)
        if self.model is not None:
            # Expected model API: clf.predict([feature_vector]) -> label
            label = self.model.predict([feat])[0]
            return str(label)
        return self._heuristic_classify(feat)

    def scan_carousel(self, slots: int) -> Dict[int, str]:
        """
        Scan the entire carousel and infer a clothing type for each slot.

        Flow (Algorithm):
        -----------------
        1. Capture one frame from the camera.
        2. Compute slot_width = frame_width / slots.
        3. For slot in 0..slots-1:
             a. x0 = slot * slot_width, x1 = (slot + 1) * slot_width
             b. segment = frame[:, x0:x1]
             c. clothing_type = predict_segment(segment)
             d. store mapping slot -> clothing_type.
        4. Return mapping.
        """
        frame = self._capture_frame()
        h, w, _ = frame.shape
        slot_width = w // slots
        results: Dict[int, str] = {}

        for slot in range(slots):
            x0 = slot * slot_width
            x1 = w if slot == slots - 1 else (slot + 1) * slot_width
            segment = frame[:, x0:x1]
            label = self.predict_segment(segment)
            self._logger.debug("Slot %d classified as %s", slot, label)
            results[slot] = label

        return results

