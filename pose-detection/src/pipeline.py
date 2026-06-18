# src/pipeline.py
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

class PoseEstimationPipeline:
    """Coordinates MediaPipe frame-by-frame video processing and pose estimation."""
    
    def __init__(self, model_path: str = 'pose_landmarker_full.task', min_detection_confidence: float = 0.4, min_tracking_confidence: float = 0.4):
        self.base_options = python.BaseOptions(model_asset_path=model_path)
        self.options = vision.PoseLandmarkerOptions(
            base_options=self.base_options,
            running_mode=vision.RunningMode.VIDEO,
            min_pose_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence
        )
        self.landmarker = None

    def __enter__(self):
        self.landmarker = vision.PoseLandmarker.create_from_options(self.options)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.landmarker:
            self.landmarker.close()

    def process_frame(self, frame_rgb, timestamp_ms: int):
        """
        Processes a single RGB frame at a given timestamp.
        Returns a tuple of (pose_landmarks, pose_world_landmarks) or (None, None).
        """
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
        results = self.landmarker.detect_for_video(mp_image, timestamp_ms)
        
        landmarks = None
        world_landmarks = None
        
        if results.pose_landmarks and len(results.pose_landmarks) > 0:
            landmarks = results.pose_landmarks[0]
        if results.pose_world_landmarks and len(results.pose_world_landmarks) > 0:
            world_landmarks = results.pose_world_landmarks[0]
            
        return landmarks, world_landmarks

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
                # Check MediaPipe visibility confidence score
                if lm.presence > 0.5:
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
