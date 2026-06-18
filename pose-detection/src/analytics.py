# src/analytics.py
import math
import numpy as np

def calculate_2d_angle(a, b, c):
    try:
        radians = math.atan2(c[1] - b[1], c[0] - b[0]) - math.atan2(a[1] - b[1], a[0] - b[0])
        angle = abs(radians * 180.0 / math.pi)
        if angle > 180.0:
            angle = 360.0 - angle
        return round(angle, 2)
    except Exception:
        return 0.0

def calculate_symmetry_index(left_val, right_val):
    if (left_val + right_val) == 0: return 0.0
    return round(abs(left_val - right_val) / (0.5 * (left_val + right_val)), 2)

def calculate_3d_angle(a, b, c):
    """
    Calculates the 3D angle (in degrees) at joint b given three 3D points a, b, c.
    Each point should be a sequence of 3 floats (x, y, z).
    """
    try:
        vec_ba = np.array(a) - np.array(b)
        vec_bc = np.array(c) - np.array(b)
        
        norm_ba = np.linalg.norm(vec_ba)
        norm_bc = np.linalg.norm(vec_bc)
        
        if norm_ba == 0 or norm_bc == 0:
            return 0.0
            
        cosine_angle = np.dot(vec_ba, vec_bc) / (norm_ba * norm_bc)
        cosine_angle = np.clip(cosine_angle, -1.0, 1.0)
        
        angle = np.arccos(cosine_angle)
        return round(np.degrees(angle), 2)
    except Exception:
        return 0.0

class ClinicalTrackingProcessor:
    """Handles noise filtering and landmark memory retention during temporary occlusion."""
    def __init__(self, alpha=0.4, max_missing_frames=6):
        self.alpha = alpha
        self.max_missing_frames = max_missing_frames
        self.history = {} # Stores {'joint_id': (filtered_x, filtered_y)}
        self.missing_counters = {} # Tracks how many frames a joint has been missing

    def process_landmark(self, joint_id, current_coords, is_detected):
        """Applies EMA smoothing and holds the last position if tracking is dropped briefly."""
        if is_detected and current_coords is not None:
            self.missing_counters[joint_id] = 0
            curr_x, curr_y = current_coords
            
            if joint_id not in self.history:
                self.history[joint_id] = (curr_x, curr_y)
                return (curr_x, curr_y)
            
            # Apply EMA formula
            prev_x, prev_y = self.history[joint_id]
            smooth_x = self.alpha * curr_x + (1 - self.alpha) * prev_x
            smooth_y = self.alpha * curr_y + (1 - self.alpha) * prev_y
            
            self.history[joint_id] = (smooth_x, smooth_y)
            return (smooth_x, smooth_y)
        
        else:
            # Drop tracking fallback: check if we can borrow from memory
            if joint_id in self.history:
                self.missing_counters[joint_id] = self.missing_counters.get(joint_id, 0) + 1
                if self.missing_counters[joint_id] <= self.max_missing_frames:
                    # Return last known position
                    return self.history[joint_id]
            
            # Completely lost
            return None