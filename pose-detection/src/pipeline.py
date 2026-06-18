# src/pipeline.py
import mediapipe as mp
import cv2
import math
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from src.config import *

class PoseEstimationPipeline:
    """Coordinates MediaPipe frame-by-frame video processing and pose estimation."""
    
    def __init__(self, model_path: str = MP_MODEL_PATH, min_detection_confidence: float = MP_MIN_DETECTION_CONFIDENCE, min_tracking_confidence: float = MP_MIN_TRACKING_CONFIDENCE):
        self.base_options = python.BaseOptions(model_asset_path=model_path)
        self.options = vision.PoseLandmarkerOptions(
            base_options=self.base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_poses=3, # Multi-pose ghost defense
            min_pose_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
            output_segmentation_masks=True # Full mass segmentation feature
        )
        self.landmarker = None

    def __enter__(self):
        self.landmarker = vision.PoseLandmarker.create_from_options(self.options)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.landmarker:
            self.landmarker.close()

    def process_frame(self, frame_rgb, timestamp_ms: int):
        """Processes a single frame and returns the best subject's landmarks and segmentation mask."""
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
        results = self.landmarker.detect_for_video(mp_image, timestamp_ms)
        
        if not results.pose_landmarks or len(results.pose_landmarks) == 0:
            return None, None, None
            
        # --- Lower-Body Priority Subject Selector ---
        best_idx = 0
        best_score = -1.0
        # Focus strictly on: hips(23,24), knees(25,26), ankles(27,28)
        lower_body_indices = [23, 24, 25, 26, 27, 28]
        
        for i, landmarks in enumerate(results.pose_landmarks):
            score = 0.0
            for idx in lower_body_indices:
                if idx < len(landmarks):
                    score += landmarks[idx].visibility
            if score > best_score:
                best_score = score
                best_idx = i
                
        best_landmarks = results.pose_landmarks[best_idx]
        best_world_landmarks = results.pose_world_landmarks[best_idx]
        
        # Extract segmentation mask as numpy array
        best_mask_np = None
        if results.segmentation_masks and len(results.segmentation_masks) > best_idx:
            best_mask_np = results.segmentation_masks[best_idx].numpy_view()
            
        return best_landmarks, best_world_landmarks, best_mask_np

    def extract_joint_coordinates(self, landmarks, width: int, height: int, target_indices: dict):
        """
        Extracts pixel coordinates (x, y) for specified target joint indices.
        Returns a dictionary mapping joint names to (x, y) coordinates or None.
        """
        coordinates = {}
        for name, idx in target_indices.items():
            raw_coord = None
            detected = False
            if landmarks and idx < len(landmarks):
                lm = landmarks[idx]
                # Stricter Integrity Check: Must be unoccluded/visible to be tracked reliably
                if lm.presence > 0.5 and lm.visibility > 0.4:
                    raw_coord = (int(lm.x * width), int(lm.y * height))
                    detected = True
            coordinates[name] = (raw_coord, detected)
        return coordinates

    def extract_world_coordinates(self, world_landmarks, target_indices: dict):
        """
        Extracts 3D metric world coordinates (x, y, z) for target joints.
        Returns a dictionary mapping joint names to (x, y, z) tuples or None.
        """
        coordinates = {}
        for name, idx in target_indices.items():
            coord = None
            if world_landmarks and idx < len(world_landmarks):
                lm = world_landmarks[idx]
                if lm.presence > 0.5:
                    coord = (lm.x, lm.y, lm.z)
            coordinates[name] = coord
        return coordinates

    def detect_a4_paper(self, frame, clean_points=None):
        """Detects an A4 paper in the frame for calibration."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        # Use lower thresholds to catch edges even in varying lighting
        edges = cv2.Canny(blur, 30, 100)
        
        # Dilate slightly to connect edges broken by fingers or lighting
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        edges = cv2.dilate(edges, kernel, iterations=1)
        
        contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        
        # Sort top contours by area to ignore background noise quickly
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]
        
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area > A4_MIN_CONTOUR_AREA:
                # Use minAreaRect instead of approxPolyDP to gracefully handle finger occlusion!
                rect = cv2.minAreaRect(cnt)
                (x, y), (w, h), angle = rect
                
                # Proximity Filter: Ignore objects far from the user's body
                if clean_points and clean_points.get("l_shoulder") and clean_points.get("r_shoulder"):
                    ls = clean_points["l_shoulder"]
                    rs = clean_points["r_shoulder"]
                    # Check if tracking is valid
                    if ls is not None and rs is not None:
                        shoulder_center_x = (ls[0] + rs[0]) / 2.0
                        shoulder_center_y = (ls[1] + rs[1]) / 2.0
                        shoulder_width = math.sqrt((ls[0] - rs[0])**2 + (ls[1] - rs[1])**2)
                        
                        if shoulder_width > 0:
                            dist = math.sqrt((x - shoulder_center_x)**2 + (y - shoulder_center_y)**2)
                            # If object is further than 2.5x shoulder widths away, it's a background object (like a shirt)
                            if dist > (shoulder_width * 2.5):
                                continue
                                
                if w > 0 and h > 0:
                    aspect_ratio = max(w, h) / float(min(w, h))
                    
                    # A4 paper aspect ratio is ~1.414. We give it a generous margin.
                    if A4_MIN_ASPECT_RATIO < aspect_ratio < A4_MAX_ASPECT_RATIO:
                        # Check solidity to ensure it's somewhat rectangular and not a weird shape
                        hull = cv2.convexHull(cnt)
                        hull_area = cv2.contourArea(hull)
                        if hull_area > 0 and (area / hull_area) > 0.7:
                            box = cv2.boxPoints(rect)
                            box = np.intp(box)
                            return box
        return None

    def calculate_calibration_multiplier(self, frame, clean_points, world_coords, current_multiplier):
        """Calculates scale multiplier based on A4 paper and updates it."""
        a4_contour = self.detect_a4_paper(frame, clean_points)
        new_multiplier = current_multiplier
        is_calibrated = False

        if a4_contour is not None:
            x, y, w_box, h_box = cv2.boundingRect(a4_contour)
            paper_px_h = max(w_box, h_box)
            
            if paper_px_h > 0 and clean_points.get("l_shoulder") and clean_points.get("r_shoulder"):
                meters_per_pixel = A4_REAL_HEIGHT_M / paper_px_h
                
                ls_px = clean_points["l_shoulder"]
                rs_px = clean_points["r_shoulder"]
                shoulder_dist_px = math.sqrt((ls_px[0] - rs_px[0])**2 + (ls_px[1] - rs_px[1])**2)
                real_shoulder_width_m = shoulder_dist_px * meters_per_pixel
                
                if world_coords.get("l_shoulder") and world_coords.get("r_shoulder"):
                    ls_w = world_coords["l_shoulder"]
                    rs_w = world_coords["r_shoulder"]
                    mp_shoulder_width_m = math.sqrt((ls_w[0] - rs_w[0])**2 + (ls_w[1] - rs_w[1])**2 + (ls_w[2] - rs_w[2])**2)
                    
                    if mp_shoulder_width_m > 0:
                        raw_multiplier = real_shoulder_width_m / mp_shoulder_width_m
                        new_multiplier = (CALIBRATION_EMA_ALPHA * raw_multiplier) + ((1 - CALIBRATION_EMA_ALPHA) * current_multiplier)
                        is_calibrated = True
                        
        return new_multiplier, is_calibrated, a4_contour

    def apply_calibration(self, world_coords, multiplier):
        """Applies the multiplier to all 3D world coordinates."""
        for name, coord in world_coords.items():
            if coord is not None:
                world_coords[name] = (coord[0] * multiplier, coord[1] * multiplier, coord[2] * multiplier)
        return world_coords
