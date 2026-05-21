import cv2
import numpy as np
import time
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

def draw_stick_figure(image, landmarks):
    h, w, c = image.shape

    def to_pixel(landmark):
        return (int(landmark.x * w), int(landmark.y * h))
    
    # Modern Tasks API landmark mapping (Indices 0 to 33)
    nose = landmarks[0]
    left_shoulder = landmarks[11]
    right_shoulder = landmarks[12]
    left_elbow = landmarks[13]
    right_elbow = landmarks[14]
    left_wrist = landmarks[15]
    right_wrist = landmarks[16]
    left_hip = landmarks[23]
    right_hip = landmarks[24]
    left_knee = landmarks[25]
    right_knee = landmarks[26]
    left_ankle = landmarks[27]
    right_ankle = landmarks[28]

    color = (0, 100, 255)  # Orange (BGR format)
    thickness = 24

    # Calculate head size from shoulder width
    shoulder_width = abs(left_shoulder.x - right_shoulder.x) * w
    head_radius = int(shoulder_width * 0.4)

    # Calculate center of body
    neck_x = (left_shoulder.x + right_shoulder.x) / 2
    neck_y = (left_shoulder.y + right_shoulder.y) / 2
    
    hip_center_x = (left_hip.x + right_hip.x) / 2
    hip_center_y = (left_hip.y + right_hip.y) / 2

    # Convert to pixel
    neck_pixel = (int(neck_x * w), int(neck_y * h))
    hip_center_pixel = (int(hip_center_x * w), int(hip_center_y * h))

    # Put head above neck
    head_center_x = neck_x
    head_center_y = neck_y - (head_radius + thickness) / h
    head_center_pixel = (int(head_center_x * w), int(head_center_y * h))

    # Draw main body (neck to hip)
    cv2.line(image, neck_pixel, hip_center_pixel, color, thickness)

    # Draw arms (with elbows)
    cv2.line(image, neck_pixel, to_pixel(left_elbow), color, thickness)
    cv2.line(image, to_pixel(left_elbow), to_pixel(left_wrist), color, thickness)
    cv2.line(image, neck_pixel, to_pixel(right_elbow), color, thickness)
    cv2.line(image, to_pixel(right_elbow), to_pixel(right_wrist), color, thickness)

    # Draw legs (with knees)
    cv2.line(image, hip_center_pixel, to_pixel(left_knee), color, thickness)
    cv2.line(image, to_pixel(left_knee), to_pixel(left_ankle), color, thickness)
    cv2.line(image, hip_center_pixel, to_pixel(right_knee), color, thickness)
    cv2.line(image, to_pixel(right_knee), to_pixel(right_ankle), color, thickness)

    # Draw head
    cv2.circle(image, head_center_pixel, head_radius, color, thickness)

# Read webcam
cap = cv2.VideoCapture(0)

# Configure Modern MediaPipe Task Options
base_options = python.BaseOptions(model_asset_path='pose_landmarker_full.task')
options = vision.PoseLandmarkerOptions(
    base_options=base_options,
    running_mode=vision.RunningMode.VIDEO,
    min_pose_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

# Start tracking utilizing the context manager
with vision.PoseLandmarker.create_from_options(options) as landmarker:
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        h, w, _ = frame.shape
        white_canvas = np.ones((h, w, 3), dtype=np.uint8) * 255  # White background

        # Transform BGR OpenCV frames into MediaPipe Image wrappers
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        # Generate a strictly increasing timestamp in milliseconds
        timestamp_ms = int(time.perf_counter() * 1000)
        results = landmarker.detect_for_video(mp_image, timestamp_ms)

        # Process results if any body tracking exists
        if results.pose_landmarks:
            # results.pose_landmarks returns a nested list of all tracked humans. 
            # We grab the first person index [0].
            draw_stick_figure(white_canvas, results.pose_landmarks[0])

        cv2.imshow('Stick Figure', white_canvas)
        
        if cv2.waitKey(10) & 0xFF == ord('q'):
            break

cap.release()
cv2.destroyAllWindows()