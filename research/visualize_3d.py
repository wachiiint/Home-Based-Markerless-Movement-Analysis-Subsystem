#!/usr/bin/env python3
"""Quick 3D skeleton visualizer for Pose2Sim TRC files."""

import sys
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

RESEARCH_DIR = Path(__file__).resolve().parent
DEFAULT_DEMO_DIR = RESEARCH_DIR / "Demo_SinglePerson"

# Halpe26 / Pose2Sim standard limb connections
SKELETON_EDGES = [
    ("Hip", "RHip"), ("RHip", "RKnee"), ("RKnee", "RAnkle"), ("RAnkle", "RBigToe"), ("RAnkle", "RHeel"),
    ("Hip", "LHip"), ("LHip", "LKnee"), ("LKnee", "LAnkle"), ("LAnkle", "LBigToe"), ("LAnkle", "LHeel"),
    ("Hip", "Neck"), ("Neck", "Head"), ("Neck", "Nose"),
    ("Neck", "RShoulder"), ("RShoulder", "RElbow"), ("RElbow", "RWrist"),
    ("Neck", "LShoulder"), ("LShoulder", "LElbow"), ("LElbow", "LWrist"),
]


def parse_trc(trc_path: Path):
    """Parse TRC file into coordinates array and marker names."""
    with open(trc_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    marker_line = lines[3].split("\t")
    marker_names = [m.strip() for m in marker_line[2:] if m.strip()]
    marker_idx = {name.lower(): i for i, name in enumerate(marker_names)}

    coords = []
    for line in lines[5:]:
        parts = line.split("\t")
        if len(parts) < 2 + len(marker_names) * 3:
            continue
        row = []
        for i in range(len(marker_names)):
            idx = 2 + i * 3
            try:
                row.append([float(parts[idx]), float(parts[idx + 1]), float(parts[idx + 2])])
            except (ValueError, IndexError):
                row.append([np.nan, np.nan, np.nan])
        coords.append(row)

    return np.array(coords), marker_idx, marker_names


def animate_3d(trc_path: Path, save_path: Path | None = None):
    """Animate 3D skeleton using Matplotlib."""
    coords, marker_idx, _ = parse_trc(trc_path)
    n_frames = len(coords)

    fig = plt.figure(figsize=(8, 8))
    ax = fig.add_subplot(111, projection="3d")

    # Determine axis boundaries from valid coordinates
    valid_pts = coords[~np.isnan(coords)].reshape(-1, 3)
    mid_x, mid_y, mid_z = np.median(valid_pts, axis=0)
    radius = 1.0  # meters

    ax.set_xlim(mid_x - radius, mid_x + radius)
    ax.set_ylim(mid_y - radius, mid_y + radius)
    ax.set_zlim(mid_z - radius, mid_z + radius)
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.set_zlabel("Z (m)")
    ax.set_title(f"Pose2Sim 3D Reconstruction: {trc_path.name}")

    scatter = ax.scatter([], [], [], color="blue", s=25)
    lines = [ax.plot([], [], [], color="red", linewidth=2)[0] for _ in SKELETON_EDGES]

    def update(frame_idx):
        frame_pts = coords[frame_idx]
        valid = ~np.isnan(frame_pts[:, 0])

        scatter._offsets3d = (
            frame_pts[valid, 0],
            frame_pts[valid, 1],
            frame_pts[valid, 2],
        )

        for line, (p1, p2) in zip(lines, SKELETON_EDGES):
            i1 = marker_idx.get(p1.lower())
            i2 = marker_idx.get(p2.lower())
            if i1 is not None and i2 is not None:
                pt1 = frame_pts[i1]
                pt2 = frame_pts[i2]
                if not np.isnan(pt1).any() and not np.isnan(pt2).any():
                    line.set_data_3d([pt1[0], pt2[0]], [pt1[1], pt2[1]], [pt1[2], pt2[2]])
                    continue
            line.set_data_3d([], [], [])

        return [scatter] + lines

    anim = FuncAnimation(fig, update, frames=n_frames, interval=30, blit=False)

    if save_path:
        print(f"Saving animation to {save_path}...")
        anim.save(str(save_path), writer="pillow", fps=30)
        print(f"Animation saved: {save_path}")
    else:
        plt.show()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Visualize Pose2Sim 3D reconstruction from TRC files.")
    parser.add_argument(
        "demo_dir",
        nargs="?",
        default=str(DEFAULT_DEMO_DIR),
        help="Path to demo directory containing pose-3d/ (defaults to research/Demo_SinglePerson)",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save animation as GIF to research/3d_skeleton_animation.gif instead of displaying interactively",
    )
    args = parser.parse_args()

    demo_dir = Path(args.demo_dir)
    pose3d_dir = demo_dir / "pose-3d"
    trc_files = list(pose3d_dir.glob("*_filt_*.trc")) or list(pose3d_dir.glob("*.trc"))

    if not trc_files:
        print(f"No .trc file found in {pose3d_dir}")
        sys.exit(1)

    output_gif = RESEARCH_DIR / "3d_skeleton_animation.gif"
    target_output = output_gif if args.save else None

    print(f"Visualizing: {trc_files[0]}")
    animate_3d(trc_files[0], save_path=target_output)

