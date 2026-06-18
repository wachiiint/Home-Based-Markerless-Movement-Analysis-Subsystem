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