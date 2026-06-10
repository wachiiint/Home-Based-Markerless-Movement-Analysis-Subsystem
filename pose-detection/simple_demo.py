import cv2
import numpy as np
import time
import math
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

def calculate_angle(a, b, c):
    """Calculates the interior angle at joint 'b' given three landmarks."""
    try:
        radians = math.atan2(c.y - b.y, c.x - b.x) - math.atan2(a.y - b.y, a.x - b.x)
        angle = abs(radians * 180.0 / math.pi)
        if angle > 180.0:
            angle = 360.0 - angle
        return int(angle)
    except:
        return 0

def get_alignment_tilt(a, b):
    """Calculates the angle of a line between two paired landmarks relative to the horizon."""
    try:
        radians = math.atan2(b.y - a.y, b.x - a.x)
        angle = radians * 180.0 / math.pi
        return int(angle) # 0 means perfectly level with the floor
    except:
        return 0

def draw_biomechanical_dashboard(image, landmarks):
    h, w, c = image.shape

    # Helper function to convert normalized landmark to pixel coordinates
    def to_px(lm):
        return (int(lm.x * w), int(lm.y * h))

    # Extract Key Landmarks (Modern Tasks API Indices)
    l_shoulder, r_shoulder = landmarks[11], landmarks[12]
    l_elbow, r_elbow       = landmarks[13], landmarks[14]
    l_wrist, r_wrist       = landmarks[15], landmarks[16]
    l_hip, r_hip           = landmarks[23], landmarks[24]
    l_knee, r_knee         = landmarks[25], landmarks[26]
    l_ankle, r_ankle       = landmarks[27], landmarks[28]

    # --- 1. FEATURE EXTRACTION ---
    # Joint Flexion Angles
    left_elbow_angle   = calculate_angle(l_shoulder, l_elbow, l_wrist)
    right_elbow_angle  = calculate_angle(r_shoulder, r_elbow, r_wrist)
    left_knee_angle    = calculate_angle(l_hip, l_knee, l_ankle)
    right_knee_angle   = calculate_angle(r_hip, r_knee, r_ankle)

    # Posture Symmetry & Tilt (Ideal is close to 0°)
    shoulder_tilt = get_alignment_tilt(r_shoulder, l_shoulder)
    hip_tilt      = get_alignment_tilt(r_hip, l_hip)

    # Center of Mass / Torso Position Tracking
    mid_hip_x = (l_hip.x + r_hip.x) / 2
    mid_hip_y = (l_hip.y + r_hip.y) / 2

    # Bounding Box Dynamics (Useful for tracking Squat Depth or Jump Height)
    all_y = [lm.y for lm in landmarks]
    highest_point = min(all_y) # MediaPipe 0 is at the top
    lowest_point  = max(all_y)
    vertical_span = abs(lowest_point - highest_point)

    # --- 2. RENDER GRAPHICS & VISUALS ---
    # Draw simple joint overlay dots & lines for context
    connections = [(11, 13), (13, 15), (12, 14), (14, 16), # Arms
                   (11, 12), (23, 24), (11, 23), (12, 24), # Torso box
                   (23, 25), (25, 27), (24, 26), (26, 28)] # Legs
    
    for start, end in connections:
        cv2.line(image, to_px(landmarks[start]), to_px(landmarks[end]), (0, 255, 0), 2)
    
    # Label angles directly onto the joints in the video feed
    cv2.putText(image, f"{left_knee_angle}deg", to_px(l_knee), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)
    cv2.putText(image, f"{right_knee_angle}deg", to_px(r_knee), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)

    # --- 3. TELEMETRY DASHBOARD OVERLAY ---
    # Semi-transparent background panel for telemetry data
    overlay = image.copy()
    cv2.rectangle(overlay, (10, 10), (340, 320), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, image, 0.4, 0, image)

    # Render data text onto panel
    telemetry = [
        ("BIOMECHANICAL METRICS", ""),
        ("-------------------", ""),
        (f"Left Elbow Flexion: ", f"{left_elbow_angle} deg"),
        (f"Right Elbow Flexion: ", f"{right_elbow_angle} deg"),
        (f"Left Knee Flexion: ", f"{left_knee_angle} deg"),
        (f"Right Knee Flexion: ", f"{right_knee_angle} deg"),
        ("-------------------", ""),
        (f"Shoulder Tilt: ", f"{shoulder_tilt} deg"),
        (f"Hip Tilt: ", f"{hip_tilt} deg"),
        ("-------------------", ""),
        (f"Torso Center (X, Y): ", f"({mid_hip_x:.2f}, {mid_hip_y:.2f})"),
        (f"Vertical Body Span: ", f"{vertical_span:.2f} (norm)"),
    ]

    y_offset = 35
    for label, val in telemetry:
        cv2.putText(image, label + val, (20, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        y_offset += 22

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

with vision.PoseLandmarker.create_from_options(options) as landmarker:
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break

        # Mirror the frame for natural user interaction (optional but helpful for home use)
        frame = cv2.flip(frame, 1)

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        timestamp_ms = int(time.perf_counter() * 1000)
        results = landmarker.detect_for_video(mp_image, timestamp_ms)

        if results.pose_landmarks:
            draw_biomechanical_dashboard(frame, results.pose_landmarks[0])

        cv2.imshow('Movement Analysis Subsystem - Team 5', frame)
        if cv2.waitKey(10) & 0xFF == ord('q'):
            break

cap.release()
cv2.destroyAllWindows()