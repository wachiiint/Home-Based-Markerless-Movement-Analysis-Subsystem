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
from app.models.calibration import CharucoBoardSpec
from app.schemas.movement import TaskType
from app.schemas.response import DemoAssessmentResponse, HealthResponse, MovementAssessmentResponse
from app.services.calibration.charuco_calibrator import calibrate_device_from_images
from app.services.calibration.device_id import derive_device_id
from app.services.calibration.device_store import DeviceStore
from app.services.calibration.print_verify import compute_print_scale
from app.tools.calibrate_device import sample_video_frames
from app.services.lifting.lifter import build_lifter
from app.services.pose.pose_estimator import RtmlibAdapter
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


async def _run_real_analysis(file: UploadFile, task_type: TaskType, view: str, subject_height_mm: float | None = None, want_pose_3d: bool = False, device_make: str = "", device_model: str = "") -> tuple[VideoAnalysis, Path]:
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
            want_pose_3d=want_pose_3d, device_make=device_make, device_model=device_model,
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
    device_make: str = Form(default=""),
    device_model: str = Form(default=""),
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
        analysis, output_path = await _run_real_analysis(
            file, task_type, normalized_view, subject_height_mm,
            device_make=device_make, device_model=device_model,
        )
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
    device_make: str = Form(default=""),
    device_model: str = Form(default=""),
) -> DemoAssessmentResponse:
    settings = app.state.settings
    if settings.fake_mode:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="set FAKE_MODE=false for the demo UI")
    _cleanup_demo_results()
    normalized_view = view if view in {"frontal", "lateral"} else "frontal"
    try:
        analysis, output_path = await _run_real_analysis(
            file, task_type, normalized_view, want_pose_3d=True,
            device_make=device_make, device_model=device_model,
        )
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


@app.post("/api/demo/calibrate", include_in_schema=False)
async def demo_calibrate(
    file: UploadFile = File(...),
    make: str = Form(default=""),
    model: str = Form(default=""),
    measured_bar_mm: float = Form(default=100.0),
    square_length_mm: float = Form(default=25.0),
    marker_length_mm: float = Form(default=18.0),
) -> JSONResponse:
    """Calibrate a device's intrinsics from a board video uploaded in the browser.

    Mirrors the ``app.tools.calibrate_device`` CLI: sample frames, run ChArUco
    calibration with the given board size + print-scale correction, and persist
    the ``DeviceIntrinsics`` keyed by device_id so the metric-3D path can engage.
    """
    settings = app.state.settings
    if settings.fake_mode:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="set FAKE_MODE=false for the demo UI")
    if app.state.device_store is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="calibration store unavailable (model not loaded)")
    if marker_length_mm <= 0 or square_length_mm <= 0 or marker_length_mm >= square_length_mm:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="marker_length_mm must be > 0 and smaller than square_length_mm",
        )

    input_path = None
    try:
        input_path = await save_upload(file, settings.demo_max_upload_mb * 1024 * 1024)
        frames, image_size = sample_video_frames(input_path, sample_fps=2.0, max_frames=40)
        if not frames:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="could not decode any frames -- the codec may be unsupported (e.g. HEVC/H.265 from iPhone); re-encode to H.264 MP4 and retry",
            )

        print_scale_factor, scale_warnings = compute_print_scale(measured_bar_mm)
        width, height = image_size
        orientation = "portrait" if height >= width else "landscape"
        meta = {"make": make, "model": model, "width": width, "height": height, "orientation": orientation}
        device_id, source = derive_device_id(meta)

        spec = CharucoBoardSpec(square_length_mm=square_length_mm, marker_length_mm=marker_length_mm)
        intrinsics = calibrate_device_from_images(
            frames, device_id=device_id, image_size=image_size, spec=spec,
            print_scale_factor=print_scale_factor, raw_meta=meta, source=source,
        )

        warnings = list(scale_warnings)
        if source == "resolution_only":
            warnings.append("no make/model given -> device_id keyed on resolution only; two phones at this resolution will collide")

        if intrinsics.status != "valid":
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "ok": False, "device_id": device_id, "source": source,
                    "image_size": [width, height], "frames_sampled": len(frames),
                    "status": intrinsics.status, "warnings": warnings,
                    "message": "calibration failed: need >=3 frames with the board clearly visible",
                },
            )

        app.state.device_store.put(intrinsics)
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "ok": True, "device_id": device_id, "source": source,
                "image_size": [width, height], "frames_sampled": len(frames),
                "reproj_error_px": round(intrinsics.reproj_error_px, 3),
                "print_scale_factor": round(print_scale_factor, 4),
                "status": intrinsics.status, "warnings": warnings,
                "message": "device calibrated; use the same make/model/resolution when analyzing a patient clip",
            },
        )
    except HTTPException:
        raise
    except ValueError as exc:
        # save_upload / frame sampling raise ValueError for actionable input
        # problems ("video is too large", unreadable) -> surface, don't mask as 500.
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from None
    except Exception:
        logger.exception("calibration failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="calibration failed") from None
    finally:
        if input_path is not None:
            shutil.rmtree(input_path.parent, ignore_errors=True)


@app.get("/api/demo/devices", include_in_schema=False)
async def demo_devices() -> JSONResponse:
    """List calibrated devices so the analysis form can offer them as a choice."""
    store = app.state.device_store
    if store is None:
        return JSONResponse(content={"devices": []})
    devices = [
        {
            "device_id": d.device_id,
            "make": d.raw_meta.get("make", ""),
            "model": d.raw_meta.get("model", ""),
            "image_size": list(d.image_size),
            "source": d.source,
            "status": d.status,
            "reproj_error_px": round(d.reproj_error_px, 3),
        }
        for d in store.all()
    ]
    return JSONResponse(content={"devices": devices})


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
