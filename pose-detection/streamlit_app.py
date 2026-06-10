import streamlit as st
import cv2
import numpy as np
import tempfile
import time
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# --- APP CONFIGURATION & UI ---
st.set_page_config(page_title="Team 5 Gait Analyzer Testbed", layout="wide")
st.title("🏃‍♂️ Clinical Gait Subsystem - Local Test Application")
st.markdown("Toggle between your live webcam or file uploads to test your pipeline components locally.")

# Sidebar Settings
st.sidebar.header("Assessment Metadata")
patient_id = st.sidebar.text_input("Patient ID", value="PT-001")
task_type = st.sidebar.selectbox("Movement Task", ["gait_walk", "squat", "shoulder_abduction"])

# --- INPUT SELECTION MODALITY ---
mode = st.radio("Select Input Source:", ["Live Webcam (Instant Testing)", "Upload Video File"])

# Setup MediaPipe task options once
base_options = python.BaseOptions(model_asset_path='pose_landmarker_full.task')
options = vision.PoseLandmarkerOptions(
    base_options=base_options,
    running_mode=vision.RunningMode.VIDEO,
    min_pose_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

# --- PROCESSING PIPELINE ENGINE ---
def run_processing_loop(source_input, is_webcam=False):
    cap = cv2.VideoCapture(source_input)
    fps = cap.get(cv2.CAP_PROP_FPS) if cap.get(cv2.CAP_PROP_FPS) > 0 else 30
    
    # Placeholders for web interfaces
    frame_placeholder = st.empty()
    status_placeholder = st.empty()
    
    frame_idx = 0
    
    with vision.PoseLandmarker.create_from_options(options) as landmarker:
        # Keep running if capture is open. If it's webcam, Streamlit will stop it when un-checked
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                if is_webcam:
                    st.warning("Webcam feed interrupted.")
                break

            # Mirror webcam preview so it feels natural to move in front of it
            if is_webcam:
                frame = cv2.flip(frame, 1)

            h, w, _ = frame.shape
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

            # Generate strictly increasing timestamp
            if is_webcam:
                timestamp_ms = int(time.perf_counter() * 1000)
            else:
                timestamp_ms = int((frame_idx / fps) * 1000)
                
            results = landmarker.detect_for_video(mp_image, timestamp_ms)

            # Render keypoint indicators onto the live web dashboard frame
            if results.pose_landmarks:
                landmarks = results.pose_landmarks[0]
                # Highlight knees (25, 26) and hips (23, 24)
                for idx in [23, 24, 25, 26]:
                    pt = landmarks[idx]
                    cv2.circle(frame, (int(pt.x * w), int(pt.y * h)), 8, (0, 255, 255), -1)
                
                cv2.putText(frame, f"Tracking Active - Frame {frame_idx}", (20, 40), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            # Push current image matrix out to the web client container view
            frame_placeholder.image(frame, channels="BGR", use_container_width=True)
            frame_idx += 1
            
            # Prevent loop from consuming excessive CPU cycles during file reading
            if not is_webcam:
                time.sleep(1.0 / fps)

    cap.release()
    status_placeholder.success(f"Session safely concluded. Analysed {frame_idx} frames for {patient_id}.")

# --- APP METHOD CONTROLLERS ---
if mode == "Live Webcam (Instant Testing)":
    run_webcam = st.checkbox("🔌 Turn On Live Webcam Stream")
    if run_webcam:
        st.subheader("Live Tracking Viewport")
        # 0 is usually your system's default integrated webcam
        run_processing_loop(0, is_webcam=True)

elif mode == "Upload Video File":
    uploaded_file = st.file_uploader("Upload Patient Movement Video", type=["mp4", "mov", "avi"])
    if uploaded_file is not None:
        tfile = tempfile.NamedTemporaryFile(delete=False)
        tfile.write(uploaded_file.read())
        
        st.subheader("Processing Video File Feed")
        with st.spinner("Processing file frame iterations..."):
            run_processing_loop(tfile.name, is_webcam=False)