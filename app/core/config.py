from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_api_key: str = Field(default="dev-local-analysis-key", alias="SERVICE_API_KEY")
    device: str = Field(default="auto", alias="DEVICE")
    model_backend: str = Field(default="rtmlib", alias="MODEL_BACKEND")
    pose_model: str = Field(default="rtmpose-m", alias="POSE_MODEL")
    rtmlib_mode: str = Field(default="balanced", alias="RTMLIB_MODE")
    frame_sample_fps: int = Field(default=10, alias="FRAME_SAMPLE_FPS")
    min_keypoint_confidence: float = Field(default=0.4, alias="MIN_KEYPOINT_CONFIDENCE")
    min_valid_frame_ratio: float = Field(default=0.6, alias="MIN_VALID_FRAME_RATIO")
    smoothing_alpha: float = Field(default=0.4, alias="SMOOTHING_ALPHA")
    # Hampel spike rejection on the angle series -- see analysis/outliers.py.
    # Window is in seconds so the behaviour is independent of FRAME_SAMPLE_FPS.
    outlier_window_sec: float = Field(default=0.3, alias="OUTLIER_WINDOW_SEC")
    outlier_n_sigma: float = Field(default=3.0, alias="OUTLIER_N_SIGMA")
    outlier_min_scale_deg: float = Field(default=2.0, alias="OUTLIER_MIN_SCALE_DEG")
    enable_3d: bool = Field(default=False, alias="ENABLE_3D")
    motionbert_model_path: str = Field(default="", alias="MOTIONBERT_MODEL_PATH")
    calibration_data_dir: str = Field(default="data/calibration", alias="CALIBRATION_DATA_DIR")
    # Where completed analyses are kept. Results used to live in a temp folder and
    # vanish on a TTL, which made every run disposable -- nothing to reopen, and
    # nothing for a later recording to be compared against. See services/session_store.py.
    session_data_dir: str = Field(default="data/sessions", alias="SESSION_DATA_DIR")
    # How far apart the left-leg and right-leg clips of one asymmetry comparison
    # may be recorded before the pair is flagged. A warning rather than a refusal:
    # the clinically defensible limit is still an open question, so this default
    # is a prompt to think, not a decision (docs2/04-planning.md).
    asymmetry_max_days_apart: int = Field(default=30, alias="ASYMMETRY_MAX_DAYS_APART")
    fake_mode: bool = Field(default=False, alias="FAKE_MODE")
    demo_max_upload_mb: int = Field(default=100, alias="DEMO_MAX_UPLOAD_MB")
    # Zero or less means a stored session never expires, which is the default while
    # this is a proof of concept. A positive value restores the old behaviour of
    # deleting a session that many seconds after it was analysed.
    demo_result_ttl_seconds: int = Field(default=0, alias="DEMO_RESULT_TTL_SECONDS")
    # The annotated video is the patient's own footage with a skeleton drawn over
    # it. Keeping it is useful while we are proving the concept on our own clips;
    # turn it off before real patient recordings are stored, and only the metrics
    # and keypoints are kept. The uploaded clip itself is never stored either way.
    keep_annotated_video: bool = Field(default=True, alias="KEEP_ANNOTATED_VIDEO")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")


@lru_cache
def get_settings() -> Settings:
    return Settings()
