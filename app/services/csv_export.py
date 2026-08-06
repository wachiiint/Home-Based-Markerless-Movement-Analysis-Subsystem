"""CSV views of the export payloads, for reading rather than replaying.

The JSON exports are the complete artifacts: they carry the skeleton topology,
the settings needed to reproduce a run, and an explicit null for every frame with
no detected subject. CSV keeps none of that structure -- so these are deliberately
lossy *views*, sized for a spreadsheet and a human eye.

Both pose tables are **wide**: one row per sampled frame, three columns per joint.
That keeps time on the vertical axis, which is how a movement is read. A frame with
no subject keeps its row (so the timeline stays intact) with ``detected`` at 0 and
every coordinate cell **left empty** -- never zero, which would read as a real
position at the origin.
"""

import csv
import io


def _writer() -> tuple[io.StringIO, "csv._writer"]:
    buffer = io.StringIO()
    # Explicit terminator: the default \r\n would become \r\r\n once the response
    # is written out on Windows.
    return buffer, csv.writer(buffer, lineterminator="\n")


def pose2d_csv(payload: dict) -> str:
    """Halpe26 pixel coordinates, one row per sampled frame."""
    names = payload["joint_names"]
    buffer, writer = _writer()

    header = ["frame", "source_frame", "detected"]
    for name in names:
        header += [f"{name}_x", f"{name}_y", f"{name}_score"]
    writer.writerow(header)

    frames = payload["frames"]
    scores = payload["scores"]
    for index, source_frame in enumerate(payload["source_frame_indices"]):
        detected = bool(payload["valid_mask"][index])
        row: list = [index, source_frame, int(detected)]
        if detected:
            for joint, (x, y) in enumerate(frames[index]):
                row += [x, y, scores[index][joint]]
        else:
            row += [""] * (len(names) * 3)
        writer.writerow(row)
    return buffer.getvalue()


def pose3d_csv(payload: dict) -> str:
    """Lifted 3D joint positions, one row per frame.

    Coordinates are root-relative and unitless unless the run was calibrated --
    the CSV cannot say so, which is why the JSON carries ``lift_reliable``.
    """
    names = payload["joint_names"]
    valid_mask = payload.get("valid_mask") or []
    buffer, writer = _writer()

    header = ["frame", "valid"]
    for name in names:
        header += [f"{name}_x", f"{name}_y", f"{name}_z"]
    writer.writerow(header)

    for index, joints in enumerate(payload["frames"]):
        valid = bool(valid_mask[index]) if index < len(valid_mask) else True
        row: list = [index, int(valid)]
        for coords in joints:
            row += list(coords)
        writer.writerow(row)
    return buffer.getvalue()


def _flatten(value, prefix: str = "") -> list[tuple[str, object]]:
    """Nested response -> dotted metric paths. Empty containers keep a row with a
    blank value, so ``gait_parameters`` being empty by design stays visible."""
    if isinstance(value, dict):
        if not value:
            return [(prefix, "")]
        rows: list[tuple[str, object]] = []
        for key, item in value.items():
            rows += _flatten(item, f"{prefix}.{key}" if prefix else str(key))
        return rows
    if isinstance(value, list):
        if not value:
            return [(prefix, "")]
        rows = []
        for index, item in enumerate(value):
            rows += _flatten(item, f"{prefix}[{index}]")
        return rows
    return [(prefix, "" if value is None else value)]


def assessment_csv(assessment: dict) -> str:
    """The assessment response as a flat metric/value table.

    The angle trajectory is left out: flattened, it would bury the twenty-odd
    metrics under hundreds of ``trajectory.left_angle_deg[n]`` rows. It has its
    own per-frame table below, which is the shape a spreadsheet plots from.
    """
    buffer, writer = _writer()
    writer.writerow(["metric", "value"])
    for path, value in _flatten({k: v for k, v in assessment.items() if k != "trajectory"}):
        writer.writerow([path, value])
    return buffer.getvalue()


def trajectory_csv(assessment: dict) -> str:
    """The angle graph as a table: one row per sampled frame, one column per leg.

    A frame with no usable angle keeps its row with an empty cell, so the gap
    survives into a spreadsheet chart instead of being drawn through.
    """
    trajectory = assessment.get("trajectory") or {}
    times = trajectory.get("time_sec") or []
    joint = trajectory.get("joint") or "angle_deg"
    sides = [(side, trajectory.get(f"{side}_angle_deg")) for side in ("left", "right")]
    present = [(side, values) for side, values in sides if values is not None]

    buffer, writer = _writer()
    writer.writerow(["frame", "time_sec"] + [f"{side}_{joint}" for side, _ in present])
    for index, time_sec in enumerate(times):
        row: list = [index, time_sec]
        for _, values in present:
            value = values[index] if index < len(values) else None
            row.append("" if value is None else value)
        writer.writerow(row)
    return buffer.getvalue()
