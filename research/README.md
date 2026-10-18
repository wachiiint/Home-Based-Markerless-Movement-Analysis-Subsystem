# Pose2Sim Research & Baseline Sandbox

This directory contains an isolated environment to run, evaluate, and experiment with **Pose2Sim** without modifying the main application code.

---

## 1. Environment Setup

Install Pose2Sim:

```bash
pip install pose2sim
```

Copy the official Pose2Sim demo dataset (`Demo_SinglePerson`) into this directory:

```bash
python3 -c "import Pose2Sim, os, shutil; src = os.path.join(os.path.dirname(Pose2Sim.__file__), 'Demo_SinglePerson'); shutil.copytree(src, 'research/Demo_SinglePerson', dirs_exist_ok=True); print('Demo dataset copied to research/Demo_SinglePerson')"
```

---

## 2. Running the Baseline

Run the standard Pose2Sim pipeline (pose estimation, triangulation, and filtering):

```bash
python3 research/run_baseline.py
```

Outputs will be saved inside `research/Demo_SinglePerson/`:
- `pose-2d/`: 2D keypoint detections per camera
- `pose-3d/`: 3D triangulated and filtered `.trc` marker trajectory files

---

## 3. Evaluating the Results

Run the objective evaluation script to measure accuracy, bone stability, and processing speed:

```bash
python3 research/evaluate.py
```

This generates `research/evaluation_summary.txt` containing:
- Bone length variation across frames (rigid bone stability in mm)
- Joint angle trajectories and Range of Motion (ROM)
- Execution speed per stage
