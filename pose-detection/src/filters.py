# src/filters.py
import numpy as np

class EMACoordinateFilter:
    """Smooths landmark coordinates in real-time to remove high-frequency jitter."""
    def __init__(self, alpha=0.3):
        self.alpha = alpha
        self.smoothed_landmarks = {}

    def filter(self, landmark_id, current_coords):
        """
        Accepts a landmark ID and its current (x, y) tuple.
        Returns the smoothed (x, y) tuple.
        """
        if landmark_id not in self.smoothed_landmarks:
            # Initialize with the first seen coordinates
            self.smoothed_landmarks[landmark_id] = current_coords
            return current_coords

        prev_x, prev_y = self.smoothed_landmarks[landmark_id]
        curr_x, curr_y = current_coords

        # Apply EMA formula
        smooth_x = self.alpha * curr_x + (1 - self.alpha) * prev_x
        smooth_y = self.alpha * curr_y + (1 - self.alpha) * prev_y

        self.smoothed_landmarks[landmark_id] = (smooth_x, smooth_y)
        return (smooth_x, smooth_y)