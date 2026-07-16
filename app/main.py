import json
import logging
import shutil
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.security import require_service_key
from app.schemas.movement import TaskType
from app.schemas.response import DemoAssessmentResponse, HealthResponse, MovementAssessmentResponse
from app.services.calibration.device_store import DeviceStore
from app.services.lifting.lifter import build_lifter
from app.services.pose_estimator import RtmlibAdapter
from app.services.response_mapper import build_fake_response
from app.services.video_analysis import VideoAnalysis, analyze_video
from app.services.video_io import save_upload, validate_video_upload

logger = logging.getLogger(__name__)


def select_device(configured_device: str) -> str:
    if configured_device == "cpu":
        return "cpu"
    if configured_device == "cuda:0":
        try:
            import onnxruntime as ort

            return "cuda:0" if "CUDAExecutionProvider" in ort.get_available_providers() else "cpu"
        except Exception:
            return "cpu"
    if configured_device == "auto":
        try:
            import onnxruntime as ort

            return "cuda:0" if "CUDAExecutionProvider" in ort.get_available_providers() else "cpu"
        except Exception:
            return "cpu"
    return "cpu"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.log_level)
    app.state.settings = settings
    app.state.device = select_device(settings.device)
    app.state.model_loaded = bool(settings.fake_mode)
    app.state.pose_estimator = None
    app.state.lifter = None
    app.state.device_store = None
    app.state.demo_results = {}
    if settings.fake_mode:
        logger.info("FAKE_MODE enabled; skipping pose model load")
    else:
        try:
            app.state.pose_estimator = RtmlibAdapter(app.state.device, settings.rtmlib_mode, settings.pose_model, settings.model_backend)
            app.state.model_loaded = True
        except Exception:
            logger.exception("pose model failed to load")
        # 3D path (Phase D): lifter is None unless enabled and weights pass the
        # I/O guard, so analysis degrades to 2D cleanly.
        app.state.lifter = build_lifter(settings.enable_3d, settings.motionbert_model_path, settings.model_backend)
        app.state.device_store = DeviceStore(Path(settings.calibration_data_dir))
    app.state.analysis_mode_available = "3d" if app.state.lifter is not None else "2d"
    logger.info(
        "startup device=%s model_backend=%s model_loaded=%s analysis_mode=%s",
        app.state.device,
        settings.model_backend,
        app.state.model_loaded,
        app.state.analysis_mode_available,
    )
    yield


app = FastAPI(title="RTMPose Movement Analysis Service", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


def _cleanup_demo_results() -> None:
    now = datetime.now(timezone.utc)
    expired = [session_id for session_id, item in app.state.demo_results.items() if item["expires_at"] <= now]
    for session_id in expired:
        shutil.rmtree(app.state.demo_results.pop(session_id)["directory"], ignore_errors=True)


async def _run_real_analysis(file: UploadFile, task_type: TaskType, view: str, subject_height_mm: float | None = None, want_pose_3d: bool = False) -> tuple[VideoAnalysis, Path]:
    settings = app.state.settings
    if app.state.pose_estimator is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="pose model is not loaded")
    input_path = None
    try:
        input_path = await save_upload(file, settings.demo_max_upload_mb * 1024 * 1024)
        output_path = input_path.parent / "annotated.mp4"
        analysis = analyze_video(
            input_path, output_path, task_type, view, settings, app.state.pose_estimator,
            lifter=app.state.lifter, device_store=app.state.device_store, subject_height_mm=subject_height_mm,
            want_pose_3d=want_pose_3d,
        )
        return analysis, output_path
    except ValueError as exc:
        if input_path is not None:
            shutil.rmtree(input_path.parent, ignore_errors=True)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from None
    except Exception:
        if input_path is not None:
            shutil.rmtree(input_path.parent, ignore_errors=True)
        logger.exception("video analysis failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="video analysis failed") from None


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_, exc: RequestValidationError):
    for error in exc.errors():
        if error.get("loc", [None])[-1] == "task_type":
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": "unknown task_type"})
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": "invalid request"})


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = app.state.settings
    return HealthResponse(
        status="ok",
        device=app.state.device,
        model_backend=settings.model_backend,
        model_loaded=app.state.model_loaded,
    )


@app.post(
    "/api/movement/assess",
    response_model=MovementAssessmentResponse,
    dependencies=[Depends(require_service_key)],
)
async def assess_movement(
    patient_id: str = Form(...),
    task_type: TaskType = Form(...),
    view: str = Form(...),
    file: UploadFile = File(...),
    subject_height_mm: float | None = Form(default=None),
) -> MovementAssessmentResponse:
    settings = app.state.settings
    normalized_view = view if view in {"frontal", "lateral"} else "frontal"
    if normalized_view != view:
        logger.warning("unknown view=%s; using frontal", view)

    try:
        await validate_video_upload(file)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="unreadable video") from None

    if settings.fake_mode:
        return build_fake_response(task_type, normalized_view, settings.frame_sample_fps)
    try:
        analysis, output_path = await _run_real_analysis(file, task_type, normalized_view, subject_height_mm)
        shutil.rmtree(output_path.parent, ignore_errors=True)
        return analysis.response
    except HTTPException:
        raise


@app.get("/", include_in_schema=False)
async def demo_page():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.post("/api/demo/assess", response_model=DemoAssessmentResponse, include_in_schema=False)
async def demo_assess(
    patient_id: str = Form(...),
    task_type: TaskType = Form(...),
    view: str = Form(...),
    file: UploadFile = File(...),
) -> DemoAssessmentResponse:
    settings = app.state.settings
    if settings.fake_mode:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="set FAKE_MODE=false for the demo UI")
    _cleanup_demo_results()
    normalized_view = view if view in {"frontal", "lateral"} else "frontal"
    try:
        analysis, output_path = await _run_real_analysis(file, task_type, normalized_view, want_pose_3d=True)
    except HTTPException:
        raise
    result = analysis.response
    result.video_metadata.task_type = task_type.value
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.demo_result_ttl_seconds)
    app.state.demo_results[result.session_id] = {"directory": output_path.parent, "expires_at": expires_at}

    pose_3d_url = None
    if analysis.pose_3d is not None:
        # Served as a file next to annotated.mp4 so it shares the same TTL cleanup.
        (output_path.parent / "pose3d.json").write_text(json.dumps(analysis.pose_3d), encoding="utf-8")
        pose_3d_url = f"/api/demo/results/{result.session_id}/pose3d.json"

    return DemoAssessmentResponse(
        assessment=result,
        annotated_video_url=f"/api/demo/results/{result.session_id}/annotated.mp4",
        pose_3d_url=pose_3d_url,
        expires_at=expires_at.isoformat(),
    )


@app.get("/api/demo/results/{session_id}/annotated.mp4", include_in_schema=False)
async def demo_result_video(session_id: str):
    _cleanup_demo_results()
    item = app.state.demo_results.get(session_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="result expired or not found")
    path = item["directory"] / "annotated.mp4"
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="result video not found")
    return FileResponse(
        path,
        media_type="video/mp4",
        filename=f"{session_id}-annotated.mp4",
        content_disposition_type="inline",
    )


@app.get("/api/demo/results/{session_id}/pose3d.json", include_in_schema=False)
async def demo_result_pose3d(session_id: str):
    _cleanup_demo_results()
    item = app.state.demo_results.get(session_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="result expired or not found")
    path = item["directory"] / "pose3d.json"
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="3d pose data not found")
    return FileResponse(path, media_type="application/json")
