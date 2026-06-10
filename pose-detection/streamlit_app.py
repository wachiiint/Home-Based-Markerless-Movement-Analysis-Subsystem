import streamlit as st
import cv2
import numpy as np
import tempfile
import time
import math
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# --- APP CONFIGURATION & UI ---
st.set_page_config(page_title="Team 5 Gait Analyzer Pro", layout="wide")
st.title("🏃‍♂️ Clinical Gait Subsystem - Advanced Local Testbed")
st.markdown("Equipped with **EMA Signal Smoothing**, **Occlusion Memory Hold**, and **Biomechanical Visualizations**.")

# Sidebar Settings
st.sidebar.header("Assessment Settings")
patient_id = st.sidebar.text_input("Patient ID", value="PT-001")
smoothing_alpha = st.sidebar.slider("EMA Filter Smoothing (Lower = Smoother, Higher = Faster)", 0.05, 1.0, 0.25)

mode = st.radio("Select Input Source:", ["Live Webcam (Instant Testing)", "Upload Video File"])

# --- ADVANCED TRACKING & FILTER ENGINE ---
class ClinicalTrackingProcessor:
    """Handles noise filtering and landmark memory retention during temporary occlusion."""
    def __init__(self, alpha=0.25, max_missing_frames=6):
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
                    # Return last known position (Dot doesn't disappear instantly!)
                    return self.history[joint_id]
            
            # Completely lost
            return None

def calculate_2d_angle(a, b, c):
    """Calculates the interior angle at joint 'b'."""
    try:
        radians = math.atan2(c[1] - b[1], c[0] - b[0]) - math.atan2(a[1] - b[1], a[0] - b[0])
        angle = abs(radians * 180.0 / math.pi)
        if angle > 180.0:
            angle = 360.0 - angle
        return int(angle)
    except:
        return 0

# --- INITIALIZE PIPELINE OPTIONS ---
base_options = python.BaseOptions(model_asset_path='pose_landmarker_full.task')
options = vision.PoseLandmarkerOptions(
    base_options=base_options,
    running_mode=vision.RunningMode.VIDEO,
    min_pose_detection_confidence=0.4, # Slightly lower to catch tricky positions
    min_tracking_confidence=0.4
)

# --- CORE RENDER LOOP ---
def run_processing_loop(source_input, is_webcam=False):
    cap = cv2.VideoCapture(source_input)
    fps = cap.get(cv2.CAP_PROP_FPS) if cap.get(cv2.CAP_PROP_FPS) > 0 else 30
    
    frame_placeholder = st.empty()
    status_placeholder = st.empty()
    
    # Instantiate our filter/memory engine
    tracker = ClinicalTrackingProcessor(alpha=smoothing_alpha)
    frame_idx = 0
    
    with vision.PoseLandmarker.create_from_options(options) as landmarker:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret: break

            if is_webcam:
                frame = cv2.flip(frame, 1)

            h, w, _ = frame.shape
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

            timestamp_ms = int(time.perf_counter() * 1000) if is_webcam else int((frame_idx / fps) * 1000)
            results = landmarker.detect_for_video(mp_image, timestamp_ms)

            # Target Gait Landmark Index Mapping
            target_indices = {
                "l_shoulder": 11, "r_shoulder": 12,
                "l_hip": 23, "r_hip": 24,
                "l_knee": 25, "r_knee": 26,
                "l_ankle": 27, "r_ankle": 28
            }
            
            clean_points = {}
            
            # Extract and pass raw keypoints through the memory & filtering layer
            for name, idx in target_indices.items():
                raw_coord = None
                detected = False
                
                if results.pose_landmarks and len(results.pose_landmarks) > 0:
                    lm = results.pose_landmarks[0][idx]
                    # Check MediaPipe visibility confidence score
                    if lm.presence > 0.5:
                        raw_coord = (int(lm.x * w), int(lm.y * h))
                        detected = True
                
                # Filter/Memory calculation
                clean_points[name] = tracker.process_landmark(idx, raw_coord, detected)

            # --- DRAWING EXPANDED VISUALIZATIONS ON CANVAS ---
            # 1. Draw Pelvic Alignment Baseline (If both hips exist)
            if clean_points["l_hip"] and clean_points["r_hip"]:
                hip_l = (int(clean_points["l_hip"][0]), int(clean_points["l_hip"][1]))
                hip_r = (int(clean_points["r_hip"][0]), int(clean_points["r_hip"][1]))
                
                # Draw a clear baseline connecting the hips
                cv2.line(frame, hip_l, hip_r, (255, 0, 165), 3)
                
                # Draw an extended horizontal dashed line for balance comparison
                mid_hip_y = int((hip_l[1] + hip_r[1]) / 2)
                cv2.line(frame, (0, mid_hip_y), (w, mid_hip_y), (100, 100, 100), 1)

            # 2. Draw Bones (Skeletal Segment Lines)
            bone_connections = [
                ("l_shoulder", "r_shoulder"), ("l_shoulder", "l_hip"), ("r_shoulder", "r_hip"),
                ("l_hip", "l_knee"), ("l_knee", "l_ankle"),
                ("r_hip", "r_knee"), ("r_knee", "r_ankle")
            ]
            for start, end in bone_connections:
                if clean_points[start] and clean_points[end]:
                    pt1 = (int(clean_points[start][0]), int(clean_points[start][1]))
                    pt2 = (int(clean_points[end][0]), int(clean_points[end][1]))
                    cv2.line(frame, pt1, pt2, (0, 200, 0), 2)

            # 3. Calculate Joint Flexion and Draw On-Canvas Callouts
            if clean_points["l_hip"] and clean_points["l_knee"] and clean_points["l_ankle"]:
                l_knee_angle = calculate_2d_angle(clean_points["l_hip"], clean_points["l_knee"], clean_points["l_ankle"])
                # Safe integer placement tuple
                text_pos_l = (int(clean_points["l_knee"][0]) + 15, int(clean_points["l_knee"][1]))
                cv2.putText(frame, f"L: {l_knee_angle}deg", text_pos_l,
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
                
            if clean_points["r_hip"] and clean_points["r_knee"] and clean_points["r_ankle"]:
                r_knee_angle = calculate_2d_angle(clean_points["r_hip"], clean_points["r_knee"], clean_points["r_ankle"])
                # Safe integer placement tuple
                text_pos_r = (int(clean_points["r_knee"][0]) - 85, int(clean_points["r_knee"][1]))
                cv2.putText(frame, f"R: {r_knee_angle}deg", text_pos_r,
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
    
            # 4. Draw Joint Target Trackers (The Dots)
            for name, pt in clean_points.items():
                if pt is not None:
                    # Convert the float tuple to an integer tuple for OpenCV
                    pt_int = (int(pt[0]), int(pt[1]))
                    
                    # Draw solid tracker dot using the integer tuple
                    cv2.circle(frame, pt_int, 6, (0, 215, 255), -1)
                    # Outer target ring
                    cv2.circle(frame, pt_int, 10, (255, 255, 255), 1)

            # Render updated UI frame matrix
            frame_placeholder.image(frame, channels="BGR", use_container_width=True)
            frame_idx += 1
            if not is_webcam:
                time.sleep(1.0 / fps)

    cap.release()
    status_placeholder.success(f"Stream completed. Patient: {patient_id}")

# --- APP METHOD CONTROLLERS ---
if mode == "Live Webcam (Instant Testing)":
    run_webcam = st.checkbox("🔌 Turn On Live Webcam Stream")
    if run_webcam:
        st.subheader("Live Biomechanical Telemetry Viewport")
        run_processing_loop(0, is_webcam=True)

elif mode == "Upload Video File":
    uploaded_file = st.file_uploader("Upload Patient Movement Video", type=["mp4", "mov", "avi"])
    if uploaded_file is not None:
        tfile = tempfile.NamedTemporaryFile(delete=False)
        tfile.write(uploaded_file.read())
        
        st.subheader("Processing Video File Feed")
        with st.spinner("Processing file frame iterations..."):
            run_processing_loop(tfile.name, is_webcam=False)