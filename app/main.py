import json
import logging
import shutil
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Response, UploadFile, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.security import require_service_key
from app.models.calibration import CharucoBoardSpec
from app.schemas.movement import SideType, TaskType, ViewType
from app.schemas.response import (
    AsymmetryComparisonResponse,
    DemoAssessmentResponse,
    HealthResponse,
    MovementAssessmentResponse,
)
from app.services.asymmetry_report import compare_sessions
from app.services.calibration.charuco_calibrator import calibrate_device_from_images
from app.services.calibration.device_id import derive_device_id
from app.services.calibration.device_store import DeviceStore
from app.services.calibration.print_verify import compute_print_scale
from app.services.csv_export import assessment_csv, pose2d_csv, pose3d_csv, trajectory_csv
from app.tools.calibrate_device import sample_video_frames
from app.services.lifting.lifter import build_lifter
from app.services.pose.pose_estimator import RtmlibAdapter
from app.services.response_mapper import build_fake_response
from app.services.session_store import SessionStore
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
    # Completed analyses are kept on disk rather than in memory, so a result
    # outlives the process that produced it.
    app.state.session_store = SessionStore(Path(settings.session_data_dir))
    app.state.session_store.purge_expired()
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


class NoCacheStaticFiles(StaticFiles):
    """Serve the browser assets with ``no-cache``, so they are revalidated.

    Starlette sends an ETag but no ``Cache-Control``, which lets a browser reuse
    a script from cache without asking. The page markup and ``app.js`` change
    together, and a cached script paired with a fresh page looks for elements
    that page does not have -- the interface then fails *after* a successful
    analysis, which reads as "nothing happened". Revalidation is a 304 when
    nothing changed, so this costs a round trip and no bandwidth.
    """

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        return response


app = FastAPI(title="RTMPose Movement Analysis Service", lifespan=lifespan)
app.mount("/static", NoCacheStaticFiles(directory=Path(__file__).parent / "static"), name="static")


def _normalize_view(view: str) -> str:
    """Coerce the ``view`` form field onto ``ViewType``.

    ``view`` is accepted as a plain string rather than declared as the enum on
    purpose: an unrecognised value is metadata about how the clip was filmed, not
    a reason to refuse the clip, so it is logged and falls back to frontal
    instead of 422-ing the way ``task_type`` and ``side`` do. The enum is the one
    definition of what the valid values are.
    """
    try:
        return ViewType(view).value
    except ValueError:
        logger.warning("unknown view=%s; using %s", view, ViewType.FRONTAL.value)
        return ViewType.FRONTAL.value


def _purge_expired_sessions() -> None:
    """A no-op under the default settings, where stored sessions never expire."""
    store: SessionStore | None = getattr(app.state, "session_store", None)
    if store is not None:
        store.purge_expired()


async def _run_real_analysis(file: UploadFile, task_type: TaskType, view: str, side: str, subject_height_mm: float | None = None, want_pose_3d: bool = False, want_pose_2d: bool = False, device_make: str = "", device_model: str = "") -> tuple[VideoAnalysis, Path]:
    settings = app.state.settings
    if app.state.pose_estimator is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="pose model is not loaded")
    input_path = None
    try:
        input_path = await save_upload(file, settings.demo_max_upload_mb * 1024 * 1024)
        output_path = input_path.parent / "annotated.mp4"
        analysis = analyze_video(
            input_path, output_path, task_type, view, side, settings, app.state.pose_estimator,
            lifter=app.state.lifter, device_store=app.state.device_store, subject_height_mm=subject_height_mm,
            want_pose_3d=want_pose_3d, want_pose_2d=want_pose_2d, device_make=device_make, device_model=device_model,
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
        field = error.get("loc", [None])[-1]
        if field == "task_type":
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": "unknown task_type"})
        if field == "side":
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": "side must be 'left' or 'right'"})
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
    side: SideType = Form(...),
    file: UploadFile = File(...),
    subject_height_mm: float | None = Form(default=None),
    device_make: str = Form(default=""),
    device_model: str = Form(default=""),
) -> MovementAssessmentResponse:
    settings = app.state.settings
    normalized_view = _normalize_view(view)

    try:
        await validate_video_upload(file)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="unreadable video") from None

    if settings.fake_mode:
        return build_fake_response(task_type, normalized_view, side.value, settings.frame_sample_fps)
    try:
        analysis, output_path = await _run_real_analysis(
            file, task_type, normalized_view, side.value, subject_height_mm,
            device_make=device_make, device_model=device_model,
        )
        shutil.rmtree(output_path.parent, ignore_errors=True)
        return analysis.response
    except HTTPException:
        raise


# The pages are revalidated on every load rather than served from cache blind:
# the markup and app.js change together, and a cached page paired with fresh
# JavaScript is a broken interface (the script looks for elements the old page
# does not have). Revalidation is a 304 when nothing changed, so it costs nothing.
_NO_CACHE = {"Cache-Control": "no-cache"}


@app.get("/", include_in_schema=False)
async def demo_page():
    return FileResponse(Path(__file__).parent / "static" / "index.html", headers=_NO_CACHE)


@app.get("/calibrate", include_in_schema=False)
async def calibrate_page():
    return FileResponse(Path(__file__).parent / "static" / "calibrate.html", headers=_NO_CACHE)


@app.get("/compare", include_in_schema=False)
async def compare_page():
    """Left against right, from two stored recordings -- its own page because it
    reads sessions that already exist rather than producing one."""
    return FileResponse(Path(__file__).parent / "static" / "compare.html", headers=_NO_CACHE)


def _demo_payload(record: dict, assessment: MovementAssessmentResponse | None = None) -> DemoAssessmentResponse:
    """Build the browser's payload from one stored session.

    A fresh analysis and a session reopened from history come through here
    together, so a past result renders through exactly the same path as a new one
    -- there is no second, quietly diverging view of a result.
    """
    session_id = record["session_id"]
    if assessment is None:
        directory = app.state.session_store.directory_of(record)
        assessment = MovementAssessmentResponse.model_validate_json(
            directory.joinpath("assessment.json").read_text(encoding="utf-8")
        )
    base = f"/api/demo/results/{session_id}"
    has_2d = bool(record.get("has_pose_2d"))
    has_3d = bool(record.get("has_pose_3d"))
    return DemoAssessmentResponse(
        assessment=assessment,
        annotated_video_url=f"{base}/annotated.mp4" if record.get("has_annotated_video") else None,
        assessment_url=f"{base}/assessment.json",
        assessment_csv_url=f"{base}/assessment.csv",
        trajectory_csv_url=f"{base}/trajectory.csv" if assessment.trajectory is not None else None,
        pose_3d_url=f"{base}/pose3d.json" if has_3d else None,
        pose_3d_csv_url=f"{base}/pose3d.csv" if has_3d else None,
        pose_2d_url=f"{base}/pose2d.json" if has_2d else None,
        pose_2d_csv_url=f"{base}/pose2d.csv" if has_2d else None,
        expires_at=record.get("expires_at"),
        patient_id=record.get("patient_id"),
        recorded_at=record.get("recorded_at"),
    )


@app.post("/api/demo/assess", response_model=DemoAssessmentResponse, include_in_schema=False)
async def demo_assess(
    patient_id: str = Form(...),
    task_type: TaskType = Form(...),
    view: str = Form(...),
    side: SideType = Form(...),
    file: UploadFile = File(...),
    device_make: str = Form(default=""),
    device_model: str = Form(default=""),
) -> DemoAssessmentResponse:
    settings = app.state.settings
    if settings.fake_mode:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="set FAKE_MODE=false for the demo UI")
    _purge_expired_sessions()
    normalized_view = _normalize_view(view)
    analysis, output_path = await _run_real_analysis(
        file, task_type, normalized_view, side.value, want_pose_3d=True, want_pose_2d=True,
        device_make=device_make, device_model=device_model,
    )

    result = analysis.response
    result.video_metadata.task_type = task_type.value
    ttl = settings.demo_result_ttl_seconds
    expires_at = (
        (datetime.now(timezone.utc) + timedelta(seconds=ttl)).isoformat() if ttl > 0 else None
    )
    record = app.state.session_store.save(
        patient_id=patient_id,
        assessment=result,
        annotated_video=output_path,
        pose_2d=analysis.pose_2d,
        pose_3d=analysis.pose_3d,
        keep_annotated_video=settings.keep_annotated_video,
        expires_at=expires_at,
    )
    # The uploaded clip is never kept. Removing the working directory takes it,
    # along with anything the store chose not to move out.
    shutil.rmtree(output_path.parent, ignore_errors=True)
    return _demo_payload(record, assessment=result)


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


@app.get("/api/demo/sessions", include_in_schema=False)
async def demo_sessions(patient_id: str = "", limit: int = 50) -> JSONResponse:
    """Stored analyses, newest first, for the history list.

    Summary rows only -- one row is what the list shows. Opening a session costs a
    second request, which is the one that reads the full assessment off disk.
    """
    _purge_expired_sessions()
    sessions = app.state.session_store.list(patient_id or None, limit)
    return JSONResponse(content={"sessions": sessions})


@app.get("/api/demo/sessions/{session_id}", response_model=DemoAssessmentResponse, include_in_schema=False)
async def demo_session(session_id: str) -> DemoAssessmentResponse:
    """Reopen one stored analysis, in the shape a fresh analysis returns."""
    _purge_expired_sessions()
    record = app.state.session_store.get(session_id)
    if record is None or not app.state.session_store.directory_of(record).is_dir():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")
    return _demo_payload(record)


@app.get("/api/demo/compare", response_model=AsymmetryComparisonResponse, include_in_schema=False)
async def demo_compare(left: str = "", right: str = "") -> AsymmetryComparisonResponse:
    """Compare two stored recordings, one leg each.

    Both ids are required and must resolve to a stored session that named a side.
    A pair that is stored but not comparable is **not** an error: it comes back
    with ``comparable=false`` and the blocking checks that say why, because "these
    two cannot be compared, and here is the reason" is the useful answer.
    """
    if not left or not right:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="left and right session ids are both required")
    if left == right:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="a session cannot be compared against itself")
    _purge_expired_sessions()
    comparison = compare_sessions(
        app.state.session_store,
        left,
        right,
        max_days_apart=app.state.settings.asymmetry_max_days_apart,
    )
    if comparison is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="one of those sessions is missing, or was stored without a side",
        )
    return comparison


def _demo_result_file(session_id: str, filename: str, missing_detail: str) -> Path:
    """Locate one artifact of a stored session, 404-ing on a session that is not
    there and on an artifact that run never produced (e.g. no 3D when the lifter
    is off, or no video when KEEP_ANNOTATED_VIDEO is false)."""
    _purge_expired_sessions()
    directory = app.state.session_store.resolve(session_id)
    if directory is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="result not found")
    path = directory / filename
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=missing_detail)
    return path


@app.get("/api/demo/results/{session_id}/annotated.mp4", include_in_schema=False)
async def demo_result_video(session_id: str):
    path = _demo_result_file(session_id, "annotated.mp4", "result video not found")
    return FileResponse(
        path,
        media_type="video/mp4",
        filename=f"{session_id}-annotated.mp4",
        content_disposition_type="inline",
    )


@app.get("/api/demo/results/{session_id}/pose3d.json", include_in_schema=False)
async def demo_result_pose3d(session_id: str):
    path = _demo_result_file(session_id, "pose3d.json", "3d pose data not found")
    return FileResponse(path, media_type="application/json")


@app.get("/api/demo/results/{session_id}/pose2d.json", include_in_schema=False)
async def demo_result_pose2d(session_id: str):
    path = _demo_result_file(session_id, "pose2d.json", "2d pose data not found")
    return FileResponse(path, media_type="application/json")


@app.get("/api/demo/results/{session_id}/assessment.json", include_in_schema=False)
async def demo_result_assessment(session_id: str):
    path = _demo_result_file(session_id, "assessment.json", "assessment not found")
    return FileResponse(path, media_type="application/json")


def _csv_response(session_id: str, filename: str, missing_detail: str, convert, download_name: str) -> Response:
    """Derive a CSV view from a stored JSON export. Generated per request: the CSV
    is a lossy convenience, so it is not worth a second copy on disk."""
    path = _demo_result_file(session_id, filename, missing_detail)
    body = convert(json.loads(path.read_text(encoding="utf-8")))
    return Response(
        content=body,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{session_id}-{download_name}"'},
    )


@app.get("/api/demo/results/{session_id}/pose2d.csv", include_in_schema=False)
async def demo_result_pose2d_csv(session_id: str):
    return _csv_response(session_id, "pose2d.json", "2d pose data not found", pose2d_csv, "pose2d.csv")


@app.get("/api/demo/results/{session_id}/pose3d.csv", include_in_schema=False)
async def demo_result_pose3d_csv(session_id: str):
    return _csv_response(session_id, "pose3d.json", "3d pose data not found", pose3d_csv, "pose3d.csv")


@app.get("/api/demo/results/{session_id}/assessment.csv", include_in_schema=False)
async def demo_result_assessment_csv(session_id: str):
    return _csv_response(session_id, "assessment.json", "assessment not found", assessment_csv, "assessment.csv")


@app.get("/api/demo/results/{session_id}/trajectory.csv", include_in_schema=False)
async def demo_result_trajectory_csv(session_id: str):
    """The angle graph's data, derived from the same stored assessment."""
    return _csv_response(session_id, "assessment.json", "assessment not found", trajectory_csv, "trajectory.csv")
