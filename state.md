# Workspace State: Home-Based Markerless Movement Analysis Subsystem

This document provides a human-and-AI-readable summary of the current project state, architecture, and workspace configuration to serve as a context handoff.

---

## 📌 Project Overview
*   **Subsystem:** Team 5 (Movement Analysis & Tele-Rehabilitation Subsystem)
*   **Purpose:** Ingest patient clinical videos, perform pose estimation, compute biomechanical kinematic features (ROM, joint angles, gait metrics, symmetry), flag compensation patterns, and present results to clinical staff.
*   **Primary Tech Stack:** Python 3.12, [uv](https://docs.astral.sh/uv/), FastAPI, Streamlit, MediaPipe Pose (Tasks API), OpenCV, NumPy.

---

## 📂 Key Source Code Mapping
*   **FastAPI Backend Orchestrator:** [pose-detection/main.py](file:///home/wachi/Chula/SummerProject/pose-detection/main.py)
    *   Exposes `POST /api/movement/assess` to ingest clinical videos and output structured biomechanical JSON payloads.
*   **Streamlit Interactive App:** [pose-detection/streamlit_app.py](file:///home/wachi/Chula/SummerProject/pose-detection/streamlit_app.py)
    *   Visualizes joint flexion, skeletal lines, pelvic alignment, and applies EMA coordinate smoothing.
*   **Biomechanical Logic (`pose-detection/src/`):**
    *   [filters.py](file:///home/wachi/Chula/SummerProject/pose-detection/src/filters.py): Real-time EMA coordinate smoothing via [EMACoordinateFilter](file:///home/wachi/Chula/SummerProject/pose-detection/src/filters.py#L4).
    *   [analytics.py](file:///home/wachi/Chula/SummerProject/pose-detection/src/analytics.py): Kinematic calculations like [calculate_2d_angle](file:///home/wachi/Chula/SummerProject/pose-detection/src/analytics.py#L5) and [calculate_symmetry_index](file:///home/wachi/Chula/SummerProject/pose-detection/src/analytics.py#L15).
    *   [screening.py](file:///home/wachi/Chula/SummerProject/pose-detection/src/screening.py): Rule-based decision support mapping joint angles to flags like `possible_trendelenburg_sign` via [run_rule_based_screening](file:///home/wachi/Chula/SummerProject/pose-detection/src/screening.py#L2).
    *   [pipeline.py](file:///home/wachi/Chula/SummerProject/pose-detection/src/pipeline.py): Empty placeholder for frame processing loop integration.

---

## 📈 Current Implementation Progress
*   [x] **Layer 1 (Sensing):** Support for webcam streams and local video file uploads.
*   [x] **Layer 2 (Pose Estimation & Quality Control):** Landmark detection using `pose_landmarker_full.task` with occlusion memory hold.
*   [x] **Layer 3 (Feature Extraction):** 2D joint angle & symmetry calculations completed.
*   [x] **Layer 4 (Screening):** Basic clinical rules for flagging compensations (Trendelenburg/trunk lean).
*   [x] **Layer 5 (Presentation):** Prototype Streamlit interface and mock FastAPI assessment payload.

---

## 🚀 Execution Guide
1.  **FastAPI Backend Server:**
    ```bash
    cd pose-detection
    uv run uvicorn main:app --reload
    ```
2.  **Streamlit Dashboard:**
    ```bash
    cd pose-detection
    uv run streamlit run streamlit_app.py
    ```

---

## Recent Changes
*   Resolved a disk storage leak in streamlit_app.py by introducing a try/finally block to remove the uploaded temporary video files after the run_processing_loop completes.
*   Fixed a Python 3.12 deprecation warning in main.py by replacing the deprecated datetime.utcnow() utility with the timezone-aware datetime.now(timezone.utc) standard.
