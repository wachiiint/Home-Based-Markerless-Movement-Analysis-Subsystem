from dataclasses import dataclass

from app.schemas.movement import TaskType


@dataclass(frozen=True)
class TaskConfig:
    task_type: TaskType
    vertex_joint: str
    ray_a_joint: str
    ray_b_joint: str
    max_key: str
    min_key: str
    rom_key: str
    expected_rom_deg: float
    borderline_rom_deg: float


TASK_CONFIGS: dict[TaskType, TaskConfig] = {
    TaskType.HIP_FLEXION: TaskConfig(TaskType.HIP_FLEXION, "hip", "shoulder", "knee", "hip_flexion_max_deg", "hip_flexion_min_deg", "hip_rom_deg", 40, 25),
    TaskType.HIP_EXTENSION: TaskConfig(TaskType.HIP_EXTENSION, "hip", "shoulder", "knee", "hip_flexion_max_deg", "hip_flexion_min_deg", "hip_rom_deg", 20, 10),
    TaskType.KNEE_FLEXION: TaskConfig(TaskType.KNEE_FLEXION, "knee", "hip", "ankle", "knee_flexion_max_deg", "knee_flexion_min_deg", "knee_rom_deg", 60, 40),
    TaskType.KNEE_EXTENSION: TaskConfig(TaskType.KNEE_EXTENSION, "knee", "hip", "ankle", "knee_flexion_max_deg", "knee_flexion_min_deg", "knee_rom_deg", 20, 10),
    TaskType.ANKLE_DORSIFLEXION: TaskConfig(TaskType.ANKLE_DORSIFLEXION, "ankle", "knee", "big_toe", "ankle_angle_max_deg", "ankle_angle_min_deg", "ankle_rom_deg", 15, 8),
    TaskType.ANKLE_PLANTARFLEXION: TaskConfig(TaskType.ANKLE_PLANTARFLEXION, "ankle", "knee", "big_toe", "ankle_angle_max_deg", "ankle_angle_min_deg", "ankle_rom_deg", 25, 15),
}
