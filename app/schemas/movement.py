from enum import StrEnum


class TaskType(StrEnum):
    HIP_FLEXION = "hip_flexion"
    HIP_EXTENSION = "hip_extension"
    KNEE_FLEXION = "knee_flexion"
    KNEE_EXTENSION = "knee_extension"
    ANKLE_DORSIFLEXION = "ankle_dorsiflexion"
    ANKLE_PLANTARFLEXION = "ankle_plantarflexion"


class ViewType(StrEnum):
    """Camera plane. Metadata about *how the clip was filmed* -- orthogonal to
    ``SideType``, which says *which leg was told to move*."""

    FRONTAL = "frontal"
    LATERAL = "lateral"


class SideType(StrEnum):
    """The leg the patient was instructed to move. Mandatory on every request:
    the v1 task set is unilateral, so without it the service has to guess which
    leg is the subject and which is the resting contralateral reference."""

    LEFT = "left"
    RIGHT = "right"
