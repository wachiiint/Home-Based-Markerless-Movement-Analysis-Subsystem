import streamlit as st
import cv2
import numpy as np
import tempfile
import time
import math
from src.pipeline import PoseEstimationPipeline
from src.analytics import calculate_3d_angle

# --- APP CONFIGURATION & UI ---
st.set_page_config(page_title="Team 5 Gait Analyzer Pro", layout="wide")
st.title("🏃‍♂️ Clinical Gait Subsystem - Advanced Local Testbed")
st.markdown("Equipped with **EMA Signal Smoothing**, **Occlusion Memory Hold**, and **Biomechanical Visualizations**.")

# Configuration Constants
patient_id = "PT-001"
smoothing_alpha = 0.25

mode = st.radio("Select Input Source:", ["Live Webcam (Instant Testing)", "Upload Video File"])

# --- ADVANCED TRACKING & FILTER ENGINE ---
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
                    # Return last known position (Dot doesn't disappear instantly!)
                    return self.history[joint_id]
            
            # Completely lost
            return None

# --- PIPELINE INITIALIZATION ---

# --- CORE RENDER LOOP ---
def run_processing_loop(source_input, is_webcam=False):
    cap = cv2.VideoCapture(source_input)
    fps = cap.get(cv2.CAP_PROP_FPS) if cap.get(cv2.CAP_PROP_FPS) > 0 else 30
    
    # Side-by-side layout columns to fit all elements without scrolling
    col1, col2 = st.columns([3, 2])
    
    with col1:
        st.markdown("### Video Stream")
        frame_placeholder = st.empty()
        status_placeholder = st.empty()
        
    with col2:
        st.markdown("### Live Telemetry & Landmarks")
        tab1, tab2, tab3 = st.tabs(["3D Coordinates Table", "Raw Landmarks Output", "Raw Left Knee JSON"])
        with tab1:
            world_landmarks_placeholder = st.empty()
        with tab2:
            raw_landmarks_placeholder = st.empty()
        with tab3:
            raw_landmark_placeholder = st.empty()
            
    # Instantiate our filter/memory engine
    tracker = ClinicalTrackingProcessor(alpha=smoothing_alpha)
    frame_idx = 0
    
    # Target Gait Landmark Index Mapping
    target_indices = {
        "l_shoulder": 11, "r_shoulder": 12,
        "l_hip": 23, "r_hip": 24,
        "l_knee": 25, "r_knee": 26,
        "l_ankle": 27, "r_ankle": 28
    }

    webcam_retry_count = 0

    with PoseEstimationPipeline(model_path='pose_landmarker_full.task', min_detection_confidence=0.4, min_tracking_confidence=0.4) as pipeline:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                # Retry loop to account for webcam hardware initialization delays
                if is_webcam and webcam_retry_count < 30:
                    webcam_retry_count += 1
                    time.sleep(0.1)
                    continue
                break
            
            # Reset retry count once a frame is successfully read
            webcam_retry_count = 0

            if is_webcam:
                frame = cv2.flip(frame, 1)

            h, w, _ = frame.shape
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            timestamp_ms = int(time.perf_counter() * 1000) if is_webcam else int((frame_idx / fps) * 1000)
            landmarks, world_landmarks = pipeline.process_frame(rgb_frame, timestamp_ms)

            # Extract coordinates via pipeline and update tracker
            raw_coords = pipeline.extract_joint_coordinates(landmarks, w, h, target_indices)
            world_coords = pipeline.extract_world_coordinates(world_landmarks, target_indices)

            # Format and display metric world coordinates in tab 1
            world_landmarks_md = "| Joint | X (Left/Right) | Y (Up/Down) | Z (Depth) |\n|---|---|---|---|\n"
            for name, coord in world_coords.items():
                if coord is not None:
                    world_landmarks_md += f"| **{name}** | {coord[0]:.3f} m | {coord[1]:.3f} m | {coord[2]:.3f} m |\n"
                else:
                    world_landmarks_md += f"| **{name}** | Tracking Lost | Tracking Lost | Tracking Lost |\n"
            world_landmarks_placeholder.markdown(world_landmarks_md)

            # Format and display raw landmark structure for Left Knee (index 25) in tab 3
            if world_landmarks and len(world_landmarks) > 25:
                l_knee_raw = world_landmarks[25]
                raw_landmark_placeholder.json({
                    "x": l_knee_raw.x,
                    "y": l_knee_raw.y,
                    "z": l_knee_raw.z,
                    "visibility": l_knee_raw.visibility,
                    "presence": l_knee_raw.presence
                })

            # Format and display all raw world landmarks in tab 2 as a structured table
            raw_landmarks_md = "| Landmark | Index | X (m) | Y (m) | Z (m) | Visibility | Presence |\n|---|---|---|---|---|---|---|\n"
            for name, idx in target_indices.items():
                if world_landmarks and idx < len(world_landmarks):
                    lm = world_landmarks[idx]
                    raw_landmarks_md += f"| **{name}** | {idx} | {lm.x:.4f} | {lm.y:.4f} | {lm.z:.4f} | {lm.visibility:.4f} | {lm.presence:.4f} |\n"
                else:
                    raw_landmarks_md += f"| **{name}** | {idx} | Lost | Lost | Lost | Lost | Lost |\n"
            raw_landmarks_placeholder.markdown(raw_landmarks_md)
            
            clean_points = {}
            for name, idx in target_indices.items():
                raw_coord, detected = raw_coords[name]
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
            # Left Knee (3D)
            if world_coords["l_hip"] and world_coords["l_knee"] and world_coords["l_ankle"]:
                l_knee_angle_3d = calculate_3d_angle(world_coords["l_hip"], world_coords["l_knee"], world_coords["l_ankle"])
                if clean_points["l_knee"]:
                    text_pos_l = (int(clean_points["l_knee"][0]) + 15, int(clean_points["l_knee"][1]))
                    cv2.putText(frame, f"L: {int(l_knee_angle_3d)}deg", text_pos_l,
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
                
            # Right Knee (3D)
            if world_coords["r_hip"] and world_coords["r_knee"] and world_coords["r_ankle"]:
                r_knee_angle_3d = calculate_3d_angle(world_coords["r_hip"], world_coords["r_knee"], world_coords["r_ankle"])
                if clean_points["r_knee"]:
                    text_pos_r = (int(clean_points["r_knee"][0]) - 85, int(clean_points["r_knee"][1]))
                    cv2.putText(frame, f"R: {int(r_knee_angle_3d)}deg", text_pos_r,
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

            # Render updated UI frame matrix within the first layout column
            frame_placeholder.image(frame, channels="BGR", width="stretch")
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
        try:
            with st.spinner("Processing file frame iterations..."):
                run_processing_loop(tfile.name, is_webcam=False)
        finally:
            import os
            try:
                os.remove(tfile.name)
            except OSError:
                pass