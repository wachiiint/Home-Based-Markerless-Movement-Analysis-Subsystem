import cv2
import numpy as np

def get_brightness(frame):
    """Calculates the average brightness of the frame."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return np.mean(gray)
