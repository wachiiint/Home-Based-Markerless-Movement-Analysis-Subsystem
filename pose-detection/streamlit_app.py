import streamlit as st
import cv2
import numpy as np
import tempfile
import time
import os
from src.pipeline import PoseEstimationPipeline
from src.analytics import calculate_3d_angle, ClinicalTrackingProcessor, SquatAnalyzer, GaitAnalyzer
from src.logger import TelemetryLogger
from src.qc import get_brightness
from src.postprocessing import KinematicFilter
from src.config import *

# --- APP CONFIGURATION & UI ---
st.set_page_config(page_title="Team 5 Gait Analyzer Pro", layout="wide")
st.title("🏃‍♂️ Clinical Gait Subsystem - Advanced Local Testbed")
st.markdown("Equipped with **EMA Signal Smoothing**, **Occlusion Memory Hold**, and **Biomechanical Visualizations**.")

with st.expander("🛠️ Pre-flight Calibration & Setup Checklist", expanded=False):
    st.markdown("""
    Please ensure the following conditions are met for optimal clinical accuracy:
    - [ ] **Camera Position**: Waist height (approx 1 meter from floor) and perfectly level.
    - [ ] **Lighting**: Adequate ambient lighting (no strong backlight).
    - [ ] **Visibility**: Full body must be visible in the frame during the entire movement.
    - [ ] **Clothing**: Wear tight-fitting clothing for accurate joint detection.
    - [ ] **Calibration**: Hold an A4 paper in front of the camera to check leveling and scaling.
    """)

mode = st.radio("Select Input Source:", ["Live Webcam (Instant Testing)", "Upload Video File"])

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
            
    # Instantiate our filter/memory engine and analyzers
    tracker = ClinicalTrackingProcessor(alpha=SMOOTHING_ALPHA, max_missing_frames=MAX_MISSING_FRAMES)
    squat_analyzer = SquatAnalyzer(valgus_threshold=-0.05)
    gait_analyzer = GaitAnalyzer(step_threshold=0.25, stance_threshold=0.15)
    session_logger = TelemetryLogger(patient_id=PATIENT_ID)
    frame_idx = 0
    
    # Target Gait Landmark Index Mapping
    target_indices = {
        "l_shoulder": 11, "r_shoulder": 12,
        "l_hip": 23, "r_hip": 24,
        "l_knee": 25, "r_knee": 26,
        "l_ankle": 27, "r_ankle": 28
    }

    webcam_retry_count = 0
    calibration_multiplier = 1.0
    is_calibrated = False

    try:
        with PoseEstimationPipeline() as pipeline:
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
                landmarks, world_landmarks, segmentation_mask = pipeline.process_frame(rgb_frame, timestamp_ms)

                # Mask rendering moved further down after analysis to allow dynamic colors

                # Extract coordinates via pipeline and update tracker
                raw_coords = pipeline.extract_joint_coordinates(landmarks, w, h, target_indices)
                world_coords = pipeline.extract_world_coordinates(world_landmarks, target_indices)
                
                clean_points = {}
                for name, idx in target_indices.items():
                    raw_coord, detected = raw_coords[name]
                    clean_points[name] = tracker.process_landmark(idx, raw_coord, detected)
                
                # QC 1: Environmental Lighting Check
                brightness = get_brightness(frame)
                if brightness < QC_LIGHTING_MIN_BRIGHTNESS:
                    cv2.putText(frame, "QC WARNING: TOO DARK", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                elif brightness > QC_LIGHTING_MAX_BRIGHTNESS:
                    cv2.putText(frame, "QC WARNING: TOO BRIGHT", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                else:
                    cv2.putText(frame, f"QC Lighting: Good ({brightness:.1f})", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

                # QC 2: A4 Paper Calibration Target Check & 3D Math Correction
                calibration_multiplier, is_recently_calibrated, a4_contour = pipeline.calculate_calibration_multiplier(
                    frame, clean_points, world_coords, calibration_multiplier
                )
                
                if is_recently_calibrated:
                    is_calibrated = True

                if a4_contour is not None:
                    cv2.drawContours(frame, [a4_contour], -1, (255, 0, 0), 3)
                    cv2.putText(frame, f"QC: A4 Target - Scale x{calibration_multiplier:.2f}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
                else:
                    if is_calibrated:
                        cv2.putText(frame, f"Scale Locked: x{calibration_multiplier:.2f}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    else:
                        cv2.putText(frame, "Awaiting A4 Calibration Target...", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)

                # Apply Calibration Multiplier to all 3D Data
                if is_calibrated:
                    world_coords = pipeline.apply_calibration(world_coords, calibration_multiplier)

                # Process Biomechanics (Squat & Gait Analysis)
                squat_metrics = squat_analyzer.process_frame(world_coords)
                gait_metrics = gait_analyzer.process_frame(world_coords)
                
                combined_metrics = {}
                if squat_metrics: combined_metrics.update(squat_metrics)
                if gait_metrics: combined_metrics.update(gait_metrics)
                
                # Compute 3D Angles for Logging
                angles = {}
                if world_coords.get("l_hip") and world_coords.get("l_knee") and world_coords.get("l_ankle"):
                    angles["l_knee_angle_3d"] = calculate_3d_angle(world_coords["l_hip"], world_coords["l_knee"], world_coords["l_ankle"])
                if world_coords.get("r_hip") and world_coords.get("r_knee") and world_coords.get("r_ankle"):
                    angles["r_knee_angle_3d"] = calculate_3d_angle(world_coords["r_hip"], world_coords["r_knee"], world_coords["r_ankle"])
                    
                session_logger.log_frame(timestamp_ms, world_coords, angles, combined_metrics)
                
                is_valgus = False
                if squat_metrics:
                    is_valgus = squat_metrics["valgus_l"] or squat_metrics["valgus_r"]
                    
                    # Display Squat Metrics HUD (black box, top-right)
                    cv2.rectangle(frame, (w - 240, 10), (w - 10, 200), (0, 0, 0), -1)
                    
                    state_txt = "DOWN" if squat_metrics["is_squatting"] else "UP"
                    state_color = (0, 255, 255) if squat_metrics["is_squatting"] else (255, 255, 255)
                    cv2.putText(frame, f"SQUATS: {squat_metrics['reps']}  [{state_txt}]", (w - 230, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0) if squat_metrics['reps'] > 0 else (255, 255, 255), 2)
                    cv2.putText(frame, f"DEPTH: {squat_metrics['current_depth']:.3f} (min: {squat_metrics['min_depth_this_rep']:.3f})", (w - 230, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    
                    # 3D Knee angles
                    cv2.putText(frame, f"KNEE L: {squat_metrics['knee_angle_l']:.1f}deg  R: {squat_metrics['knee_angle_r']:.1f}deg", (w - 230, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (200, 255, 200), 1)
                    cv2.putText(frame, f"MAX FLEX L: {squat_metrics['max_flexion_l']:.1f}  R: {squat_metrics['max_flexion_r']:.1f}", (w - 230, 108), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (180, 200, 255), 1)
                    
                    # Valgus status
                    vl_color = (0, 0, 255) if squat_metrics["valgus_l"] else (0, 255, 0)
                    vr_color = (0, 0, 255) if squat_metrics["valgus_r"] else (0, 255, 0)
                    cv2.putText(frame, f"VALGUS L: {'YES' if squat_metrics['valgus_l'] else 'NO'} ({squat_metrics['valgus_idx_l']:.3f}m)", (w - 230, 133), cv2.FONT_HERSHEY_SIMPLEX, 0.48, vl_color, 1)
                    cv2.putText(frame, f"VALGUS R: {'YES' if squat_metrics['valgus_r'] else 'NO'} ({squat_metrics['valgus_idx_r']:.3f}m)", (w - 230, 155), cv2.FONT_HERSHEY_SIMPLEX, 0.48, vr_color, 1)
                    
                if gait_metrics:
                    # Display Gait Metrics HUD (below Squat HUD)
                    cv2.rectangle(frame, (w - 240, 210), (w - 10, 320), (0, 0, 0), -1)
                    cv2.putText(frame, f"STEPS: {gait_metrics['step_count']}", (w - 230, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0) if gait_metrics['step_count'] > 0 else (255, 255, 255), 2)
                    cv2.putText(frame, f"PHASE: {gait_metrics['phase']}", (w - 230, 268), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 1)
                    cv2.putText(frame, f"STRIDE: {gait_metrics['current_step_dist']:.2f}m", (w - 230, 290), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 255), 1)
                    
                    si_color = (0, 0, 255) if gait_metrics['is_asymmetric'] else (0, 255, 0)
                    cv2.putText(frame, f"SYMMETRY: {gait_metrics['symmetry_index']}%", (w - 230, 312), cv2.FONT_HERSHEY_SIMPLEX, 0.55, si_color, 1)
                
                # Draw the "full mass" segmentation overlay dynamically
                if segmentation_mask is not None:
                    condition = np.squeeze(segmentation_mask > 0.5)
                    overlay = frame.copy()
                    # Color changes to RED/ORANGE if valgus detected, else CYAN/BLUE
                    color = (0, 100, 255) if is_valgus else (255, 100, 0)
                    overlay[condition] = color
                    frame = cv2.addWeighted(overlay, 0.4, frame, 0.6, 0)

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
                    # Scale the raw JSON output too for consistency
                    raw_landmark_placeholder.json({
                        "x": l_knee_raw.x * calibration_multiplier,
                        "y": l_knee_raw.y * calibration_multiplier,
                        "z": l_knee_raw.z * calibration_multiplier,
                        "visibility": l_knee_raw.visibility,
                        "presence": l_knee_raw.presence,
                        "applied_scale": calibration_multiplier
                    })

                # Format and display all raw world landmarks in tab 2 as a structured table
                raw_landmarks_md = "| Landmark | Index | X (m) | Y (m) | Z (m) | Visibility | Presence |\n|---|---|---|---|---|---|---|\n"
                for name, idx in target_indices.items():
                    if world_landmarks and idx < len(world_landmarks):
                        lm = world_landmarks[idx]
                        raw_landmarks_md += f"| **{name}** | {idx} | {lm.x * calibration_multiplier:.4f} | {lm.y * calibration_multiplier:.4f} | {lm.z * calibration_multiplier:.4f} | {lm.visibility:.4f} | {lm.presence:.4f} |\n"
                    else:
                        raw_landmarks_md += f"| **{name}** | {idx} | Lost | Lost | Lost | Lost | Lost |\n"
                raw_landmarks_placeholder.markdown(raw_landmarks_md)

                # Enforce "Full Body Required" protocol for lower-body clinical data
                missing_legs = False
                for leg_joint in ["l_knee", "r_knee", "l_ankle", "r_ankle"]:
                    if clean_points.get(leg_joint) is None:
                        missing_legs = True
                        break

                if missing_legs:
                    # Project large UI warning
                    cv2.rectangle(frame, (0, h//2 - 40), (w, h//2 + 40), (0, 0, 0), -1)
                    cv2.putText(frame, "LOWER BODY OUT OF FRAME", (w//2 - 240, h//2), cv2.FONT_HERSHEY_DUPLEX, 1.0, (0, 0, 255), 2)
                    cv2.putText(frame, "PLEASE STEP BACK", (w//2 - 140, h//2 + 30), cv2.FONT_HERSHEY_DUPLEX, 0.8, (0, 0, 255), 2)
                    # Skip drawing the biomechanical skeleton to avoid logging garbage
                else:
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
                    if "l_knee_angle_3d" in angles:
                        if clean_points["l_knee"]:
                            text_pos_l = (int(clean_points["l_knee"][0]) + 15, int(clean_points["l_knee"][1]))
                            cv2.putText(frame, f"L: {int(angles['l_knee_angle_3d'])}deg", text_pos_l,
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
                        
                    # Right Knee (3D)
                    if "r_knee_angle_3d" in angles:
                        if clean_points["r_knee"]:
                            text_pos_r = (int(clean_points["r_knee"][0]) - 85, int(clean_points["r_knee"][1]))
                            cv2.putText(frame, f"R: {int(angles['r_knee_angle_3d'])}deg", text_pos_r,
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
            
                # 4. Draw Joint Target Trackers (The Dots) & QC 3: Occlusion Warning
                occluded_joints = []
                for name, pt in clean_points.items():
                    if pt is not None:
                        # Convert the float tuple to an integer tuple for OpenCV
                        pt_int = (int(pt[0]), int(pt[1]))
                        
                        # Determine occlusion status by checking raw landmarks visibility
                        is_occluded = False
                        idx = target_indices[name]
                        if landmarks and idx < len(landmarks):
                            if landmarks[idx].visibility < QC_OCCLUSION_VISIBILITY_THRESHOLD:
                                is_occluded = True
                                occluded_joints.append(f"{name} (vis: {landmarks[idx].visibility:.2f})")
                        
                        if is_occluded:
                            # Draw red solid tracker dot for occluded joints (Memory hold visualization)
                            cv2.circle(frame, pt_int, 6, (0, 0, 255), -1)
                            cv2.circle(frame, pt_int, 10, (0, 0, 255), 1)
                        else:
                            # Draw solid tracker dot using the integer tuple
                            cv2.circle(frame, pt_int, 6, (0, 215, 255), -1)
                            # Outer target ring
                            cv2.circle(frame, pt_int, 10, (255, 255, 255), 1)
                            
                # Draw Occlusion Warning Text
                if occluded_joints:
                    y_offset = 90
                    cv2.putText(frame, "QC OCCLUSION WARNING:", (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                    for i, oc_joint in enumerate(occluded_joints):
                        cv2.putText(frame, f"- {oc_joint}", (20, y_offset + 20 + i*20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

                # Render updated UI frame matrix within the first layout column
                frame_placeholder.image(frame, channels="BGR", use_container_width=True)
                frame_idx += 1
                if not is_webcam:
                    time.sleep(1.0 / fps)

    finally:
        cap.release()
        
    saved_file = session_logger.save()
    if saved_file:
        # Apply Post-Processing Kinematic Filters (Outlier Rejection -> PCHIP -> Butterworth)
        filter_engine = KinematicFilter()
        filtered_file = filter_engine.process_session_csv(saved_file)
        
        status_placeholder.success(f"Stream completed. Telemetry processed & filtered to {filtered_file}")
        with open(filtered_file, "rb") as f:
            st.download_button("Download Filtered Telemetry CSV (Physics-Ready)", f.read(), file_name=os.path.basename(filtered_file), mime="text/csv")
    else:
        status_placeholder.success(f"Stream completed. Patient: {PATIENT_ID}")

# --- APP METHOD CONTROLLERS ---
if mode == "Live Webcam (Instant Testing)":
    st.subheader("Webcam Recording & Calibration Mode")
    st.markdown("Check the box below to start recording. Hold an A4 paper in frame to calibrate. Uncheck to save.")
    
    is_recording = st.checkbox("🔴 Start Recording")
    cache_video_path = "data/latest_recording.mp4"
    
    if is_recording:
        cap = cv2.VideoCapture(0)
        # Ensure data directory exists
        os.makedirs("data", exist_ok=True)
        
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(cache_video_path, fourcc, 30.0, (int(cap.get(3)), int(cap.get(4))))
        
        frame_placeholder = st.empty()
        st.warning("Recording in progress... Uncheck the box above to stop.")
        
        # Mini pipeline just for A4 detection feedback
        with PoseEstimationPipeline() as pipeline:
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    time.sleep(0.1)
                    continue
                
                frame = cv2.flip(frame, 1)
                
                # Write pristine frame to disk
                out.write(frame)
                
                # Draw A4 overlay for user feedback (but don't save to the disk video)
                ui_frame = frame.copy()
                a4_contour = pipeline.detect_a4_paper(ui_frame)
                if a4_contour is not None:
                    cv2.drawContours(ui_frame, [a4_contour], -1, (255, 0, 0), 3)
                    cv2.putText(ui_frame, "A4 TARGET ACQUIRED", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
                else:
                    cv2.putText(ui_frame, "A4 NOT DETECTED", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                    
                frame_placeholder.image(ui_frame, channels="BGR")
                
        cap.release()
        out.release()
    else:
        if os.path.exists(cache_video_path):
            st.success(f"Cached video ready at: {cache_video_path}")
            if st.button("Process Cached Video"):
                st.subheader("Processing Video Feed")
                with st.spinner("Extracting kinematics..."):
                    run_processing_loop(cache_video_path, is_webcam=False)

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