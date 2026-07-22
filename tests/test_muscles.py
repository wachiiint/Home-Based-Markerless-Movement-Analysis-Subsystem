import json

import numpy as np

from app.services.lifting.muscles import compute_muscle_overlay

# H36M17 indices: 0 pelvis, 1 r_hip, 2 r_knee, 3 r_ankle, 4 l_hip, 5 l_knee,
# 6 l_ankle, 8 thorax. We build a right leg whose knee flexes over the clip.


def _pose(knee_angle_deg: float) -> np.ndarray:
    """A frame where the RIGHT knee subtends `knee_angle_deg`.

    Thigh points straight down (hip->knee along -Y); the shank swings in the YZ
    plane so hip-knee-ankle form the requested angle. Other joints are placed
    plausibly and don't affect the right-knee muscles under test.
    """
    kp = np.zeros((17, 3))
    kp[0] = (0, 100, 0)      # pelvis
    kp[8] = (0, 160, 0)      # thorax (above pelvis)
    kp[1] = (10, 100, 0)     # r_hip
    kp[2] = (10, 60, 0)      # r_knee (femur straight down)
    # shank of length 40 leaving the knee; interior knee angle = knee_angle_deg
    theta = np.radians(knee_angle_deg)
    # direction from knee: rotate the (knee->hip)=+Y direction by theta in YZ
    d = np.array([0.0, np.cos(theta), np.sin(theta)])
    kp[3] = kp[2] + 40.0 * d  # r_ankle
    return kp


def _series(name, side="right"):
    seq = np.stack([_pose(a) for a in np.linspace(170, 60, 12)])  # knee flexes over clip
    overlay = compute_muscle_overlay(seq)
    return next(m for m in overlay if m["name"] == name and m["side"] == side)


def test_overlay_covers_both_legs():
    seq = np.stack([_pose(a) for a in (170, 120, 90)])
    overlay = compute_muscle_overlay(seq)
    sides = {m["side"] for m in overlay}
    assert sides == {"left", "right"}
    for m in overlay:
        # one normalized value per frame, all in [0, 1]
        assert len(m["length"]) == 3
        assert all(0.0 <= v <= 1.0 for v in m["length"])
        # anchors: an ordered list of [jointA, jointB, t] with t in [0, 1]
        assert len(m["anchors"]) >= 2
        for a, b, t in m["anchors"]:
            assert isinstance(a, int) and isinstance(b, int)
            assert 0.0 <= t <= 1.0
        assert "bulge" in m


def test_extensor_stretches_as_knee_flexes():
    # Quadriceps (knee extensor) lengthens as the knee flexes: first frame (most
    # extended) is the shortest, last frame (most flexed) is the longest.
    quad = _series("Quadriceps")
    assert quad["length"][0] == min(quad["length"])
    assert quad["length"][-1] == max(quad["length"])


def test_flexor_shortens_as_knee_flexes():
    # Hamstrings (knee flexor) shorten as the knee flexes: opposite trend.
    ham = _series("Hamstrings")
    assert ham["length"][0] == max(ham["length"])
    assert ham["length"][-1] == min(ham["length"])


def test_static_pose_is_neutral():
    seq = np.stack([_pose(120.0) for _ in range(10)])  # no movement
    overlay = compute_muscle_overlay(seq)
    quad = next(m for m in overlay if m["name"] == "Quadriceps" and m["side"] == "right")
    assert all(v == 0.5 for v in quad["length"])


def test_empty_sequence_returns_no_muscles():
    assert compute_muscle_overlay(np.zeros((0, 17, 3))) == []


# --- gait2392 extractor + loader ------------------------------------------------

_SYNTHETIC_OSIM = """<?xml version="1.0"?>
<OpenSimDocument>
 <Model>
  <ForceSet><objects>
   <Thelen2003Muscle name="rect_fem_r">
    <GeometryPath><PathPointSet><objects>
     <PathPoint name="p1"><body>femur_r</body><location>0.03 -0.202 0.005</location></PathPoint>
     <PathPoint name="p2"><body>tibia_r</body><location>0.06 -0.043 0.0</location></PathPoint>
    </objects></PathPointSet></GeometryPath>
   </Thelen2003Muscle>
   <Thelen2003Muscle name="rect_fem_l">
    <GeometryPath><PathPointSet><objects>
     <PathPoint name="p1"><body>femur_l</body><location>0.03 -0.202 -0.005</location></PathPoint>
     <PathPoint name="p2"><body>tibia_l</body><location>0.06 -0.043 0.0</location></PathPoint>
    </objects></PathPointSet></GeometryPath>
   </Thelen2003Muscle>
   <Thelen2003Muscle name="soleus_r">
    <GeometryPath><PathPointSet><objects>
     <PathPoint name="s1"><body>tibia_r</body><location>-0.002 -0.15 0.007</location></PathPoint>
    </objects></PathPointSet></GeometryPath>
   </Thelen2003Muscle>
  </objects></ForceSet>
 </Model>
</OpenSimDocument>"""


def test_extractor_maps_points_to_bone_fractions(tmp_path):
    from app.tools.extract_gait2392_muscles import extract

    osim = tmp_path / "mini.osim"
    osim.write_text(_SYNTHETIC_OSIM, encoding="utf-8")
    muscles = extract(osim)

    # Only the curated rect_fem is kept (soleus is not in the curated set).
    assert [m["name"] for m in muscles] == ["Quadriceps"]
    quad = muscles[0]
    assert quad["joint"] == "knee" and quad["lengthens_on_flexion"] is True
    # femur point (~mid-femur) -> hip->knee fraction; tibia point near knee -> knee->ankle.
    assert quad["anchors"][0][:2] == ["hip", "knee"]
    assert 0.4 < quad["anchors"][0][2] < 0.6
    assert quad["anchors"][1][:2] == ["knee", "ankle"]
    assert quad["bulge"] > 0  # anterior points (x > 0) -> front bulge


def test_muscles_uses_gait2392_table_when_present(tmp_path, monkeypatch):
    from app.services.lifting.muscles import active_muscles

    table = {"muscles": [{"name": "Sartorius", "joint": "knee", "lengthens_on_flexion": False,
                          "bulge": 0.05, "anchors": [["hip", "knee", 0.1], ["knee", "ankle", 0.2]]}]}
    path = tmp_path / "gait2392_muscles.json"
    path.write_text(json.dumps(table), encoding="utf-8")
    monkeypatch.setenv("GAIT2392_MUSCLES_PATH", str(path))

    names = [m.name for m in active_muscles()]
    assert names == ["Sartorius"]  # the loaded table replaces the built-in set
