from app.schemas.movement import TaskType
from app.services.response_mapper import build_assessment_response


def test_response_mapper_nested_shape():
    response = build_assessment_response(
        task_type=TaskType.KNEE_FLEXION,
        view="lateral",
        duration_sec=12.4,
        fps=30,
        processed_frames=124,
        sampled_fps=10,
        angle_min=4.2,
        angle_max=61.4,
        mean_keypoint_confidence=0.88,
        valid_frame_ratio=0.94,
        risk_level="low",
        confidence_score=0.82,
        flags=[],
    ).model_dump()

    assert set(response) == {
        "session_id",
        "video_metadata",
        "clinical_metrics",
        "screening_result",
        "transformation_matrix_6dof",
    }
    assert response["clinical_metrics"]["joint_angles"]["knee_rom_deg"] == 57.2
    assert response["clinical_metrics"]["gait_parameters"] == {}
    assert response["clinical_metrics"]["symmetry_index_score"] is None
