#!/usr/bin/env python3
"""Run exact baseline Pose2Sim pipeline on the demo dataset."""

import os
import sys
import time
from pathlib import Path

# Base directory for the research sandbox
RESEARCH_DIR = Path(__file__).resolve().parent
DEFAULT_DEMO_DIR = RESEARCH_DIR / "Demo_SinglePerson"


def check_demo_dir(demo_dir: Path) -> bool:
    """Check that demo directory and required assets exist."""
    if not demo_dir.exists():
        print(f"Error: Demo directory not found at {demo_dir}")
        print("\nPlease follow the setup instructions in research/README.md:")
        print("1. pip install pose2sim")
        print("2. python3 -c \"import Pose2Sim, os, shutil; src = os.path.join(os.path.dirname(Pose2Sim.__file__), 'Demo_SinglePerson'); shutil.copytree(src, 'research/Demo_SinglePerson', dirs_exist_ok=True)\"")
        return False

    config_path = demo_dir / "Config.toml"
    if not config_path.exists():
        print(f"Error: Config.toml not found in {demo_dir}")
        return False

    return True


def run_baseline(demo_dir: Path = DEFAULT_DEMO_DIR) -> dict:
    """Run standard Pose2Sim pipeline stages."""
    if not check_demo_dir(demo_dir):
        sys.exit(1)

    try:
        from Pose2Sim import Pose2Sim
    except ImportError:
        print("Error: pose2sim package is not installed.")
        print("Please run: pip install pose2sim")
        sys.exit(1)

    config_filename = "Config.toml"
    print(f"=== Starting Pose2Sim Baseline ===")
    print(f"Project directory: {demo_dir.resolve()}\n")

    timing = {}

    # Pose2Sim expects the current working directory to be the project directory
    # so that relative paths in Config.toml (e.g. project_dir = '.') resolve properly.
    original_cwd = Path.cwd()
    os.chdir(demo_dir)

    try:
        # Stage 0: Calibration (converts Calib.qca.txt to .toml calibration file)
        print("--- Stage 0: Camera Calibration ---")
        t0 = time.time()
        Pose2Sim.calibration(config_filename)
        timing["calibration_sec"] = time.time() - t0
        print(f"Completed in {timing['calibration_sec']:.2f} s\n")

        # Stage 1: 2D Pose Estimation
        print("--- Stage 1: 2D Pose Estimation (RTMPose) ---")
        t0 = time.time()
        Pose2Sim.poseEstimation(config_filename)
        timing["pose_estimation_sec"] = time.time() - t0
        print(f"Completed in {timing['pose_estimation_sec']:.2f} s\n")

        # Stage 2: Synchronization (if needed)
        print("--- Stage 2: Camera Synchronization ---")
        t0 = time.time()
        try:
            Pose2Sim.synchronization(config_filename)
            timing["synchronization_sec"] = time.time() - t0
            print(f"Completed in {timing['synchronization_sec']:.2f} s\n")
        except Exception as e:
            print(f"Skipping synchronization (natively synchronized or error: {e})\n")
            timing["synchronization_sec"] = 0.0

        # Stage 3: Person Association
        print("--- Stage 3: Person Association ---")
        t0 = time.time()
        Pose2Sim.personAssociation(config_filename)
        timing["person_association_sec"] = time.time() - t0
        print(f"Completed in {timing['person_association_sec']:.2f} s\n")

        # Stage 4: 3D Triangulation
        print("--- Stage 4: 3D Triangulation ---")
        t0 = time.time()
        Pose2Sim.triangulation(config_filename)
        timing["triangulation_sec"] = time.time() - t0
        print(f"Completed in {timing['triangulation_sec']:.2f} s\n")

        # Stage 5: 3D Filtering (Butterworth)
        print("--- Stage 5: 3D Filtering ---")
        t0 = time.time()
        Pose2Sim.filtering(config_filename)
        timing["filtering_sec"] = time.time() - t0
        print(f"Completed in {timing['filtering_sec']:.2f} s\n")

        # Stage 6: OpenSim Marker Augmentation & Kinematics (Scaling and IK)
        print("--- Stage 6: OpenSim Kinematics (Scaling & Inverse Kinematics) ---")
        t0 = time.time()
        try:
            # Run marker augmentation if enabled in Config.toml
            try:
                Pose2Sim.markerAugmentation(config_filename)
            except Exception:
                pass

            Pose2Sim.kinematics(config_filename)
            timing["kinematics_sec"] = time.time() - t0
            print(f"Completed in {timing['kinematics_sec']:.2f} s\n")
            print(f"OpenSim outputs saved under {demo_dir / 'kinematics'}")
        except ModuleNotFoundError as e:
            if "opensim" in str(e).lower():
                print("Notice: 'opensim' library is not yet installed in your Python environment.")
                print("To run OpenSim scaling and inverse kinematics:")
                print("  conda install -c opensim-org opensim  (or: pip install opensim)")
                print("Alternatively, you can open the generated .trc file in the free OpenSim desktop GUI.\n")
            else:
                print(f"Kinematics error: {e}\n")
            timing["kinematics_sec"] = 0.0
        except Exception as e:
            print(f"OpenSim kinematics notice: {e}\n")
            timing["kinematics_sec"] = 0.0

        timing["total_sec"] = sum(timing.values())
        print(f"=== Baseline Execution Finished in {timing['total_sec']:.2f} s ===")
        print(f"3D marker outputs: {demo_dir / 'pose-3d'}")
        if (demo_dir / "kinematics").exists():
            print(f"OpenSim outputs:   {demo_dir / 'kinematics'}")

        return timing

    finally:
        os.chdir(original_cwd)


if __name__ == "__main__":
    target_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DEMO_DIR
    run_baseline(target_dir)
