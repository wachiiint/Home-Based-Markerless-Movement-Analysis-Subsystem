"""3D joint angles from the lifted H36M17 skeleton.

Hybrid design (Phase D decision): hip/knee angles come from the 3D skeleton;
ankle tasks stay on the 2D path because H36M17 has no toe joint. Task joint
names are resolved against the H36M17 layout via ``H36M17_LEG``.
"""

from app.models.task_config import TASK_CONFIGS
from app.schemas.movement import TaskType
from app.services.analysis.kinematics import three_point_angle_3d

# task joint name -> H36M17 index, per side. No toe here (H36M17 lacks it), so
# ankle tasks (ray_b = big_toe) are intentionally unsupported in 3D.
H36M17_LEG = {
    "left": {"shoulder": 11, "hip": 4, "knee": 5, "ankle": 6},
    "right": {"shoulder": 14, "hip": 1, "knee": 2, "ankle": 3},
}

_SUPPORTED_JOINTS = set(H36M17_LEG["left"])


def supports_3d_angle(task_type: TaskType) -> bool:
    """True when all of the task's joints exist in H36M17 (hip/knee, not ankle)."""
    config = TASK_CONFIGS[task_type]
    joints = {config.vertex_joint, config.ray_a_joint, config.ray_b_joint}
    return joints.issubset(_SUPPORTED_JOINTS)


def _leg(side: str) -> dict[str, int]:
    return H36M17_LEG["left"] if side == "left" else H36M17_LEG["right"]


def angle_series_3d(keypoints_3d, task_type: TaskType, side: str) -> list[float]:
    """Per-frame 3D angle for ``task_type`` on ``side``. ``keypoints_3d``: (T,17,3)."""
    if not supports_3d_angle(task_type):
        raise ValueError(f"{task_type} has joints outside H36M17; use the 2D path")
    config = TASK_CONFIGS[task_type]
    idx = _leg(side)
    vertex, ray_a, ray_b = idx[config.vertex_joint], idx[config.ray_a_joint], idx[config.ray_b_joint]
    return [
        three_point_angle_3d(frame[ray_a], frame[vertex], frame[ray_b])
        for frame in keypoints_3d
    ]
