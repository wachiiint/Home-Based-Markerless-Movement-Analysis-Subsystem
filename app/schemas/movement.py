from enum import StrEnum


class TaskType(StrEnum):
    HIP_FLEXION = "hip_flexion"
    HIP_EXTENSION = "hip_extension"
    KNEE_FLEXION = "knee_flexion"
    KNEE_EXTENSION = "knee_extension"
    ANKLE_DORSIFLEXION = "ankle_dorsiflexion"
    ANKLE_PLANTARFLEXION = "ankle_plantarflexion"


class ViewType(StrEnum):
    FRONTAL = "frontal"
    LATERAL = "lateral"
