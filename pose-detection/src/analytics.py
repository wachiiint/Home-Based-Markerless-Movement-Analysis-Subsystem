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