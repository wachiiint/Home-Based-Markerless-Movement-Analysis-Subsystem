# Pose2Sim: Technical Architecture, Pipeline Specification, and Research Roadmap

## 1. What is Pose2Sim?

**Pose2Sim** (Pagnon et al., *Journal of Open Source Software*, 2022) is an open-source Python framework for **multiview markerless 3D kinematics**. It translates multi-camera 2D video recordings into research-grade 3D skeletal motion and OpenSim biomechanical simulations without requiring reflective skin markers, specialized suits, or proprietary motion capture hardware.

Originally created to bridge OpenPose with OpenSim ("Open**Pose to** Open**Sim**"), modern versions of Pose2Sim have transitioned to **RTMPose** as their default 2D pose estimation engine.

---

## 2. Input Specifications: What is Actually Needed?

To run Pose2Sim successfully, the system requires four inputs:

| Input | Requirement | Details |
|---|---|---|
| **1. Multi-View Video** | **Minimum 2 cameras** (4+ recommended) | Consumer cameras, GoPros, or phones. Angles must have overlapping fields of view with minimal collinearity (e.g., 45° to 90° apart). |
| **2. Calibration Data** | **Mandatory** | 3D reconstruction mathematically requires knowing camera intrinsics and extrinsics. Provided via:<br>• A checkerboard / ChArUco board video (computed via OpenCV).<br>• Pre-existing calibration files (Qualisys `.qca.txt`, Vicon `.xcp`, OpenCap `.pickle`, Caliscope, etc.).<br>• Scene landmarks with measured 3D physical coordinates. |
| **3. Project Configuration** | `Config.toml` | Defines model selection, detection thresholds, filter frequencies, camera names, and participant mass/height. |
| **4. Biomechanical Model** | `.osim` file *(only for IK)* | Musculoskeletal model (e.g. Gait2392, Rajagopal 2016). Pose2Sim bundles modified models without muscle constraints for kinematic solving. |

> **Note on Single Camera**: Pure Pose2Sim **cannot** operate with only one camera. Triangulating 3D space requires intersecting rays from at least two distinct perspectives. Single-camera setups require alternative strategies (detailed in Section 5).

---

## 3. The Pose2Sim Pipeline: Stage-by-Stage Technical Architecture

```
Camera Videos (>= 2 views)
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│ Stage 0: Calibration                                        │
│ OpenCV calibrateCamera / QCA Parser                         │
│ Output: Calib.toml (Intrinsics K, Extrinsics R & T)        │
└─────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│ Stage 1: 2D Pose Estimation                                 │
│ Detector: YOLOX-m/l (bounding boxes)                        │
│ Estimator: RTMPose-m/l (Halpe26 keypoints via SimCC)       │
│ Output: Per-frame 2D JSONs with pixel coords & confidence   │
└─────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│ Stage 2: Camera Synchronization                             │
│ Cross-correlation on filtered vertical velocity signals     │
│ Output: Frame-shifted synced 2D JSONs                       │
└─────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│ Stage 3: Person Association                                 │
│ Epipolar line distance matching / Sports2D tracker          │
│ Output: Consistent person ID assigned across all cameras    │
└─────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│ Stage 4: 3D Triangulation                                   │
│ Direct Linear Transform (DLT) + Outlier Camera Exclusion    │
│ Output: Raw 3D marker trajectory (.trc file) in meters      │
└─────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│ Stage 5: 3D Trajectory Filtering                            │
│ Hampel outlier filter + 4th-order zero-lag Butterworth      │
│ Output: Filtered .trc and .c3d files                        │
└─────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│ Stage 6: Biomechanical Kinematics (OpenSim)                │
│ Model Scaling + Weighted Least-Squares Inverse Kinematics   │
│ Output: .osim scaled model + .mot joint kinematics          │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Deep Technical Breakdown per Stage

### Stage 0: Camera Calibration
- **Purpose**: Establishes the mathematical mapping between 2D pixel coordinates $(u, v)$ and 3D world coordinates $(X, Y, Z)$.
- **Mathematical Model**: Pinhole camera model:
  $$s \begin{bmatrix} u \\ v \\ 1 \end{bmatrix} = \mathbf{K} [\mathbf{R} \mid \mathbf{T}] \begin{bmatrix} X \\ Y \\ Z \\ 1 \end{bmatrix}$$
- **Intrinsics ($\mathbf{K}$)**: $3 \times 3$ matrix containing focal length $(f_x, f_y)$ and principal point $(c_x, c_y)$, coupled with radial/tangential distortion coefficients $(k_1, k_2, p_1, p_2)$.
- **Extrinsics ($[\mathbf{R} \mid \mathbf{T}]$)**: 3D rotation matrix $\mathbf{R}$ (expressed via Rodrigues vector or quaternions) and translation vector $\mathbf{T}$ defining camera position relative to world origin $(0, 0, 0)$.
- **Methods**:
  - `convert`: Parses pre-calculated calibrations from Qualisys (`Calib.qca.txt`), OptiTrack, Vicon, or OpenCap.
  - `calculate`: Uses OpenCV `findChessboardCorners` / `cornerSubPix` on board images to compute $\mathbf{K}$ and $\mathbf{R}, \mathbf{T}$ via bundle adjustment.

### Stage 1: 2D Pose Estimation
- **Detector**: **YOLOX** (top-down object detector). Detects human bounding boxes.
- **Pose Estimator**: **RTMPose** (from OpenMMLab / `rtmlib`).
  - Architecture: High-resolution backbone with **SimCC** (Simple Coordinate Classification), treating keypoint localization as horizontal and vertical classification sub-problems rather than heatmaps. This enables sub-pixel accuracy at >90 FPS.
- **Keypoint Topology**: **Halpe26** (26 keypoints: 17 standard COCO body landmarks + 6 foot points [Left/Right BigToe, SmallToe, Heel] + Hip center, Neck, Head).
- **Optimization (`det_frequency`)**: To maximize throughput, YOLOX detection runs only every $N$ frames (e.g. $N=4$); in intervening frames, bounding boxes are tracked via bounding-box overlap (IoU) while RTMPose runs on every frame.

### Stage 2: Camera Synchronization
- **Problem**: Asynchronous cameras record with unknown frame offsets.
- **Method**: Cross-correlation of vertical keypoint velocities.
  - Extracts vertical ($y$) positions of fast-moving keypoints (e.g. Ankle, Wrist).
  - Differentiates signal to get vertical velocity $v_y(t)$.
  - Applies a 4th-order Butterworth filter to isolate intentional movement from jitter.
  - Computes cross-correlation between camera pairs:
    $$R_{xy}(\tau) = \sum_{t} v_1(t) v_2(t + \tau)$$
  - The lag $\tau$ that maximizes correlation is the discrete frame offset used to time-align the image sequences.

### Stage 3: Person Association Across Cameras
- **Problem**: When multiple people are visible, camera 1's "Person 0" might be camera 2's "Person 1".
- **Method**: Epipolar Geometry and Hungarian Matching.
  - Using camera projection matrices, a 2D point in Camera 1 defines an epipolar line in Camera 2.
  - The algorithm calculates Euclidean reprojection distances between candidate keypoint sets and epipolar lines.
  - Solves the linear sum assignment problem to assign uniform global IDs across all camera feeds.

### Stage 4: 3D Triangulation
- **Algorithm**: **Direct Linear Transform (DLT)** with robust camera exclusion.
- **Formulation**: Each camera $i$ gives two linear equations for each 3D point $\mathbf{X} = [X, Y, Z, 1]^T$:
  $$\mathbf{A}_i \mathbf{X} = \mathbf{0}$$
  Stacking $\mathbf{A}_i$ for all visible cameras yields an overdetermined system $\mathbf{A} \mathbf{X} = \mathbf{0}$, solved via Singular Value Decomposition (SVD).
- **Outlier Camera Rejection**: If the reprojection error from any individual camera exceeds a configurable threshold (e.g. 20 pixels due to limb occlusion), that camera is excluded for that specific joint on that frame, and SVD is re-computed.
- **Output**: `.trc` (Track Row Column) file containing raw millimeter/meter 3D trajectories.

### Stage 5: 3D Trajectory Filtering
- **Step 5A: Hampel Filter (Outlier Rejection)**: Replaces transient tracking spikes using rolling median and Median Absolute Deviation (MAD):
  $$|x_t - \text{median}(x_{t-k:t+k})| > 3 \times 1.4826 \times \text{MAD}$$
- **Step 5B: Zero-Lag Low-Pass Butterworth Filter**:
  - 4th-order low-pass filter with cutoff frequency $\sim 6\text{ Hz}$ (human voluntary movement rarely exceeds 4–8 Hz).
  - Applied forward and backward (`scipy.signal.filtfilt`) to achieve exact **zero phase lag**.

### Stage 6: Biomechanical Kinematics (OpenSim)
- **Model Scaling**: Adjusts segment dimensions of an `.osim` generic model to match participant marker distances.
- **Inverse Kinematics (IK)**:
  - Formulated as a global non-linear optimization problem at each frame:
    $$\min_{\mathbf{q}} \sum_{i \in \text{markers}} w_i \left\| \mathbf{x}_i^{\text{model}}(\mathbf{q}) - \mathbf{x}_i^{\text{measured}} \right\|^2$$
    where $\mathbf{q}$ is the vector of generalized coordinates (joint angles, pelvis translation/orientation), subject to physiological joint constraints.
- **Output**: `.mot` (motion) file containing true anatomical angles (degrees) through time.

---

## 5. What Can Be Improved? (Future Research Differentiators)

Standard Pose2Sim is effective for multi-camera lab setups, but has clear limitations. The following areas represent concrete research opportunities:

### 1. Monocular (Single-Camera) 3D Biomechanics
- **Current Pose2Sim Limit**: Requires $\ge 2$ calibrated cameras. Completely fails with 1 smartphone camera due to depth ambiguity.
- **Improvement**: Replace multi-view triangulation with **physics-informed 2D-to-3D deep lifting** (e.g. MotionBERT or HybrIK) constrained by patient-specific bone lengths, or direct 2D-to-OpenSim optimization (minimizing 2D reprojection error subject to OpenSim kinematic limits).

### 2. IMU-Vision Sensor Fusion
- **Current Pose2Sim Limit**: Purely optical. Subject to self-occlusion (e.g., far leg hidden behind near leg in side view).
- **Improvement**: Fuse single-camera RTMPose keypoints with 1 or 2 wearable IMU sensors (placed on the shank/thigh) using an Extended Kalman Filter (EKF). The IMU provides drift-free high-frequency 3D joint orientation, while the camera provides drift-free global spatial positioning.

### 3. Automatic Boardless Calibration (Auto-Extrinsics)
- **Current Pose2Sim Limit**: Requires manually filming a physical calibration board before every session.
- **Improvement**: Compute camera extrinsics automatically from moving human keypoints using Fundamental matrix estimation and multi-view Bundle Adjustment, eliminating physical boards.

### 4. Edge-Optimized Real-Time Execution
- **Current Pose2Sim Limit**: Offline post-processing tool (takes several minutes per trial on CPU).
- **Improvement**: Quantize RTMPose to INT8 / TensorRT and implement a streaming sliding-window triangulation worker to deliver real-time kinematic readouts at 30+ FPS.

### 5. Clinical Movement Quality Engine
- **Current Pose2Sim Limit**: Outputs raw joint angles for biomechanists; provides zero clinical interpretation.
- **Improvement**: Layer motor-control metrics on top of the kinematics:
  - **SPARC (Spectral Arc Length)** and **LDLJ (Log Dimensionless Jerk)** for movement smoothness.
  - **Zifchock Symmetry Angle** to quantify bilateral deficits.
  - Automated risk grading against normative clinical thresholds.

---

## 6. File-by-File Guide: What Each File Does

### A. Root Research Tools & Code (Committed to Git)

| File | Purpose |
|---|---|
| **[`research/README.md`](README.md)** | Quickstart instructions explaining how to install Pose2Sim, copy the demo dataset, run the baseline, and evaluate results. |
| **[`research/RESEARCH_NOTES.md`](RESEARCH_NOTES.md)** | This document: full technical specification, mathematics, stage-by-stage architecture, and future research directions. |
| **[`research/run_baseline.py`](run_baseline.py)** | Pipeline runner script. Automatically changes into the demo directory, executes all Pose2Sim stages (Calibration, 2D RTMPose, Synchronization, Person Association, 3D Triangulation, and Butterworth Filtering), logs stage timings, and restores the working directory. |
| **[`research/evaluate.py`](evaluate.py)** | Evaluation tool. Parses the output 3D `.trc` file to compute rigid bone segment stability (femur/tibia mean length, standard deviation, and CV%) and joint angle Range of Motion (ROM). Writes the report to `evaluation_summary.txt`. |
| **[`research/visualize_3d.py`](visualize_3d.py)** | Standalone 3D visualizer using Matplotlib. Parses the 3D `.trc` file, connects Halpe26 anatomical limbs, and animates the 3D moving skeleton. Can be run interactively or saved as a GIF (`--save`). |
| **[`research/evaluation_summary.txt`](evaluation_summary.txt)** | Recorded benchmark output from the baseline evaluation script for tracking performance over time. |

---

### B. Project Configuration & Calibration Files

| File | Purpose |
|---|---|
| **`Config.toml`** | Central configuration file for Pose2Sim. Controls all parameters across every stage (e.g. frame range, RTMPose model type, detector frequency, filter cutoffs, camera names, and participant mass/height). |
| **`calibration/Calib.qca.txt`** | Raw text calibration file exported from Qualisys motion capture system containing 3D camera positions and orientation matrices. |
| **`calibration/Calib_qualisys.toml`** | The standardized Pose2Sim calibration file generated by Stage 0. Contains intrinsic matrix $\mathbf{K}$, distortion coefficients $\mathbf{D}$, rotation matrices $\mathbf{R}$, and translation vectors $\mathbf{T}$ for all 4 cameras. |

---

### C. Video Inputs & Intermediate Outputs (Ignored in Git via `.gitignore`)

| Directory / File | Purpose |
|---|---|
| **`videos/cam01.mp4` – `cam04.mp4`** | Synchronized 60 FPS input video feeds filmed from 4 distinct angles around the participant. |
| **`pose/`** | Outputs of Stage 1 (2D Pose Estimation):<br>• `camXX_pose.mp4`: Video overlays showing detected 2D skeletons.<br>• `camXX_json/`: Raw per-frame JSON files with 2D $(x, y)$ coordinates and confidences. |
| **`pose-sync/`** | Outputs of Stage 2 (Synchronization):<br>• `sync_camXX_vs_camYY.png`: Cross-correlation velocity plots showing time offsets.<br>• Time-aligned, frame-shifted JSON coordinates. |
| **`pose-associated/`** | Outputs of Stage 3 (Person Association):<br>• JSON coordinates with consistent global human IDs assigned across all camera viewpoints. |
| **`logs.txt`** | Full execution log detailing detection backends, frame counts, per-joint reprojection errors, and processing durations. |

---

### D. Final 3D Biomechanical Outputs

| File | Purpose |
|---|---|
| **`pose-3d/Demo_SinglePerson_1-97.trc`** | Raw triangulated 3D Cartesian coordinates $(X, Y, Z)$ for all 26 keypoints across 96 frames before smoothing. |
| **`pose-3d/Demo_SinglePerson_1-97_filt_butterworth.trc`** | The primary final result: 3D coordinates filtered with the 4th-order zero-lag Butterworth filter. Ready to be loaded into OpenSim for Inverse Kinematics or into Blender. |
| **`pose-3d/Demo_SinglePerson_1-97_filt_butterworth.c3d`** | Binary version of the filtered 3D marker trajectory in standard motion capture C3D format. |
| **`pose-3d/filtering_plots_ik/*.png`** | Validation plots for each joint (e.g. `person00_RKnee.png`) showing raw noisy 3D trajectories (red) vs. smoothed trajectories (blue). |

