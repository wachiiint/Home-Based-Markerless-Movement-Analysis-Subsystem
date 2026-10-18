#!/usr/bin/env python3
"""Evaluate Pose2Sim 3D reconstruction and kinematics from TRC files."""

import os
import sys
from pathlib import Path
import numpy as np

RESEARCH_DIR = Path(__file__).resolve().parent
DEFAULT_DEMO_DIR = RESEARCH_DIR / "Demo_SinglePerson"


def parse_trc(trc_path: Path) -> dict:
    """Parse an OpenSim TRC marker trajectory file."""
    with open(trc_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    if len(lines) < 6:
        raise ValueError(f"TRC file {trc_path} is too short or malformed.")

    # Line 3: Meta parameters
    meta_keys = lines[1].split("\t")
    meta_vals = lines[2].split("\t")
    meta = dict(zip(meta_keys, meta_vals))

    data_rate = float(meta.get("DataRate", 60.0))
    units = meta.get("Units", "m")

    # Line 4: Marker names (Frame#, Time, Marker1, <tab>, <tab>, Marker2...)
    marker_line = lines[3].split("\t")
    marker_names = [m.strip() for m in marker_line[2:] if m.strip()]

    # Data lines start from index 5
    frames = []
    times = []
    coords = []

    for line in lines[5:]:
        parts = line.split("\t")
        if len(parts) < 2 + len(marker_names) * 3:
            continue
        try:
            frames.append(int(parts[0]))
            times.append(float(parts[1]))
            # (N_markers, 3)
            row_coords = []
            for i in range(len(marker_names)):
                idx = 2 + i * 3
                x = float(parts[idx]) if parts[idx] else np.nan
                y = float(parts[idx + 1]) if parts[idx + 1] else np.nan
                z = float(parts[idx + 2]) if parts[idx + 2] else np.nan
                row_coords.append([x, y, z])
            coords.append(row_coords)
        except ValueError:
            continue

    coords_arr = np.array(coords)  # Shape: (N_frames, N_markers, 3)

    return {
        "file_name": trc_path.name,
        "data_rate": data_rate,
        "units": units,
        "num_frames": len(frames),
        "marker_names": marker_names,
        "marker_index": {name: i for i, name in enumerate(marker_names)},
        "times": np.array(times),
        "coords": coords_arr,
    }


def compute_distance(p1: np.ndarray, p2: np.ndarray) -> np.ndarray:
    """Euclidean distance between two 3D coordinate arrays of shape (N, 3)."""
    return np.linalg.norm(p1 - p2, axis=1)


def compute_angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> np.ndarray:
    """Compute 3D joint angle at vertex b between vectors (a - b) and (c - b) in degrees."""
    v1 = a - b
    v2 = c - b
    norm1 = np.linalg.norm(v1, axis=1)
    norm2 = np.linalg.norm(v2, axis=1)

    with np.errstate(invalid="ignore", divide="ignore"):
        cos_ang = np.sum(v1 * v2, axis=1) / (norm1 * norm2)
        cos_ang = np.clip(cos_ang, -1.0, 1.0)
        angles = np.degrees(np.arccos(cos_ang))

    return angles


def find_marker_key(marker_index: dict, candidates: list[str]) -> str | None:
    """Find matching marker key from candidates (case-insensitive)."""
    lower_map = {k.lower(): k for k in marker_index.keys()}
    for cand in candidates:
        if cand.lower() in lower_map:
            return lower_map[cand.lower()]
    return None


def evaluate_trc(trc_path: Path) -> dict:
    """Compute bone stability and joint angle kinematics."""
    trc = parse_trc(trc_path)
    coords = trc["coords"]
    m_idx = trc["marker_index"]

    report = {
        "trc_file": trc_path.name,
        "num_frames": trc["num_frames"],
        "data_rate": trc["data_rate"],
        "units": trc["units"],
        "bone_lengths": {},
        "joint_angles": {},
    }

    # Locate leg markers
    r_hip = find_marker_key(m_idx, ["RHip", "R_Hip", "hip_r"])
    r_knee = find_marker_key(m_idx, ["RKnee", "R_Knee", "knee_r"])
    r_ankle = find_marker_key(m_idx, ["RAnkle", "R_Ankle", "ankle_r"])

    l_hip = find_marker_key(m_idx, ["LHip", "L_Hip", "hip_l"])
    l_knee = find_marker_key(m_idx, ["LKnee", "L_Knee", "knee_l"])
    l_ankle = find_marker_key(m_idx, ["LAnkle", "L_Ankle", "ankle_l"])

    # 1. Bone length stability (rigid segments shouldn't fluctuate)
    bones = [
        ("right_femur", r_hip, r_knee),
        ("right_tibia", r_knee, r_ankle),
        ("left_femur", l_hip, l_knee),
        ("left_tibia", l_knee, l_ankle),
    ]

    for name, p_start, p_end in bones:
        if p_start and p_end:
            i1 = m_idx[p_start]
            i2 = m_idx[p_end]
            dists = compute_distance(coords[:, i1, :], coords[:, i2, :])
            valid = dists[~np.isnan(dists)]
            if len(valid) > 0:
                report["bone_lengths"][name] = {
                    "mean": float(np.mean(valid)),
                    "std": float(np.std(valid)),
                    "cv_percent": float((np.std(valid) / np.mean(valid)) * 100),
                }

    # 2. Knee flexion angles
    if r_hip and r_knee and r_ankle:
        r_angles = compute_angle(coords[:, m_idx[r_hip], :], coords[:, m_idx[r_knee], :], coords[:, m_idx[r_ankle], :])
        valid_r = r_angles[~np.isnan(r_angles)]
        if len(valid_r) > 0:
            report["joint_angles"]["right_knee_flexion"] = {
                "min_deg": float(np.min(valid_r)),
                "max_deg": float(np.max(valid_r)),
                "rom_deg": float(np.max(valid_r) - np.min(valid_r)),
                "mean_deg": float(np.mean(valid_r)),
            }

    if l_hip and l_knee and l_ankle:
        l_angles = compute_angle(coords[:, m_idx[l_hip], :], coords[:, m_idx[l_knee], :], coords[:, m_idx[l_ankle], :])
        valid_l = l_angles[~np.isnan(l_angles)]
        if len(valid_l) > 0:
            report["joint_angles"]["left_knee_flexion"] = {
                "min_deg": float(np.min(valid_l)),
                "max_deg": float(np.max(valid_l)),
                "rom_deg": float(np.max(valid_l) - np.min(valid_l)),
                "mean_deg": float(np.mean(valid_l)),
            }

    return report


def format_report(report: dict) -> str:
    """Format evaluation metrics into readable text."""
    lines = [
        "============================================================",
        "             POSE2SIM BASELINE EVALUATION REPORT            ",
        "============================================================",
        f"TRC File:     {report['trc_file']}",
        f"Frames:       {report['num_frames']} frames at {report['data_rate']} Hz",
        f"Units:        {report['units']}",
        "\n1. BONE LENGTH STABILITY (Lower std dev = higher stability):",
    ]

    for bone, stats in report["bone_lengths"].items():
        lines.append(
            f"  - {bone.replace('_', ' ').title():<15}: Mean = {stats['mean']:.4f} {report['units']} | "
            f"Std = {stats['std']:.4f} {report['units']} (CV: {stats['cv_percent']:.2f}%)"
        )

    lines.append("\n2. JOINT ANGLES & RANGE OF MOTION (ROM):")
    for joint, stats in report["joint_angles"].items():
        lines.append(
            f"  - {joint.replace('_', ' ').title():<20}: Min = {stats['min_deg']:.1f}° | "
            f"Max = {stats['max_deg']:.1f}° | ROM = {stats['rom_deg']:.1f}°"
        )

    lines.append("============================================================\n")
    return "\n".join(lines)


def main():
    demo_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DEMO_DIR
    pose3d_dir = demo_dir / "pose-3d"

    if not pose3d_dir.exists():
        print(f"Error: Directory {pose3d_dir} not found. Please run run_baseline.py first.")
        sys.exit(1)

    # Prefer filtered TRC files
    trc_files = list(pose3d_dir.glob("*_filt_*.trc"))
    if not trc_files:
        trc_files = list(pose3d_dir.glob("*.trc"))

    if not trc_files:
        print(f"Error: No .trc files found in {pose3d_dir}.")
        sys.exit(1)

    target_trc = trc_files[0]
    print(f"Evaluating 3D reconstruction from: {target_trc}\n")

    report = evaluate_trc(target_trc)
    formatted = format_report(report)
    print(formatted)

    output_summary = RESEARCH_DIR / "evaluation_summary.txt"
    with open(output_summary, "w", encoding="utf-8") as f:
        f.write(formatted)
    print(f"Summary report written to {output_summary}")


if __name__ == "__main__":
    main()
