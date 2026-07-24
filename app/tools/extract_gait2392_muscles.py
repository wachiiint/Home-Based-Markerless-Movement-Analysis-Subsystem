"""Extract gait2392 muscle path geometry into ``models/gait2392_muscles.json``.

Reads an OpenSim **gait2392** ``.osim`` (XML) -- which you download yourself,
see ``docs2/02-pipeline.md`` -- and writes the anchor table the 3D viewer's muscle
overlay consumes. It reads **geometry only**: it does NOT run OpenSim and
computes no forces (a single camera can't measure force anyway).

Mapping (documented, approximate): each OpenSim muscle path point lives in a body
frame (femur, tibia, pelvis, ...). We project it onto the matching skeleton bone
as a fraction ``t`` along that bone (``t=0`` proximal joint, ``t=1`` distal) --
the single-camera-robust coordinate. Anterior/posterior offsets are discarded;
the viewer adds an illustrative belly bulge whose *sign* we take from the mean
anterior/posterior side of the points. Segment lengths are gait2392 nominals.

Only a representative muscle per functional group is extracted (see ``_CURATED``);
the driving joint and flexion role are curated (kinematics), while the path
geometry comes from the model. Run:

    uv run python -m app.tools.extract_gait2392_muscles --osim gait2392_simbody.osim
"""

from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path

# gait2392 nominal segment lengths (m), proximal joint at body-frame origin,
# distal joint at -Y. Fractions are scale-invariant on our side, so exact values
# matter only mildly.
_FEMUR_LEN = 0.4040
_TIBIA_LEN = 0.4300

# gait2392 muscle name (side suffix stripped) -> (display, driving joint, lengthens_on_flexion).
# One representative per group; add more if you want them drawn.
_CURATED: dict[str, tuple[str, str, bool]] = {
    "rect_fem": ("Quadriceps", "knee", True),
    "bifemlh": ("Hamstrings", "knee", False),
    "med_gas": ("Gastrocnemius", "knee", False),
    "psoas": ("Iliopsoas", "hip", False),
    "glut_max1": ("Gluteals", "hip", True),
}

_BULGE_MAG = 0.06


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _map_point(body: str, loc: tuple[float, float, float]) -> tuple[tuple[str, str], float, float] | None:
    """(segment joints, fraction t along it, anterior x) for a point on ``body``."""
    x, y, _z = loc
    if body.startswith("femur"):
        return ("hip", "knee"), _clamp01(-y / _FEMUR_LEN), x
    if body.startswith("tibia"):
        return ("knee", "ankle"), _clamp01(-y / _TIBIA_LEN), x
    if body.startswith("pelvis"):
        return ("pelvis", "hip"), 0.3, x
    if body.startswith("torso"):
        return ("thorax", "pelvis"), 0.5, x
    if body.startswith(("calcn", "talus", "toes")):
        return ("knee", "ankle"), 0.95, x
    return None


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _point_body(point: ET.Element) -> str | None:
    # Newer format: <socket_parent_frame>/bodyset/femur_r</socket_parent_frame>; older: <body>femur_r</body>.
    for child in point:
        if _local(child.tag) in ("socket_parent_frame", "body") and child.text:
            return child.text.strip().rsplit("/", 1)[-1]
    return None


def _point_location(point: ET.Element) -> tuple[float, float, float] | None:
    for child in point:
        if _local(child.tag) == "location" and child.text:
            nums = [float(v) for v in child.text.split()]
            if len(nums) == 3:
                return (nums[0], nums[1], nums[2])
    return None


def _muscle_name(elem: ET.Element) -> str:
    return (elem.get("name") or "").strip()


def extract(osim_path: Path) -> list[dict]:
    root = ET.parse(osim_path).getroot()
    muscles: list[dict] = []
    for elem in root.iter():
        if not _local(elem.tag).endswith("Muscle"):
            continue
        name = _muscle_name(elem)
        if name.endswith("_l"):
            continue  # geometry is side-agnostic; extract one side (right) only
        key = name[:-2] if name.endswith("_r") else name  # strip side suffix
        if key not in _CURATED:
            continue
        display, joint, lengthens = _CURATED[key]
        anchors: list[list] = []
        x_signs: list[float] = []
        for point in elem.iter():
            if _local(point.tag) not in ("PathPoint", "ConditionalPathPoint"):
                continue
            body = _point_body(point)
            loc = _point_location(point)
            if body is None or loc is None:
                continue
            mapped = _map_point(body, loc)
            if mapped is None:
                continue
            (seg_a, seg_b), t, x = mapped
            anchors.append([seg_a, seg_b, round(t, 4)])
            x_signs.append(x)
        if len(anchors) < 2:
            continue
        bulge = _BULGE_MAG if (sum(x_signs) >= 0) else -_BULGE_MAG
        muscles.append(
            {"name": display, "joint": joint, "lengthens_on_flexion": lengthens, "bulge": bulge, "anchors": anchors}
        )
    return muscles


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract gait2392 muscle path geometry to JSON.")
    parser.add_argument("--osim", required=True, type=Path, help="path to gait2392 .osim")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "models" / "target" / "gait2392_muscles.json",
        help="output JSON (default: models/gait2392_muscles.json)",
    )
    args = parser.parse_args()
    muscles = extract(args.osim)
    if not muscles:
        raise SystemExit(f"no curated muscles found in {args.osim}; check it is a gait2392 model")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"source": "gait2392", "muscles": muscles}, indent=2), encoding="utf-8")
    print(f"wrote {len(muscles)} muscles -> {args.out}")


if __name__ == "__main__":
    main()
