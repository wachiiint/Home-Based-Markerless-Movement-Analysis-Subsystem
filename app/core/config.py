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
    enable_3d: bool = Field(default=False, alias="ENABLE_3D")
    motionbert_model_path: str = Field(default="", alias="MOTIONBERT_MODEL_PATH")
    calibration_data_dir: str = Field(default="data/calibration", alias="CALIBRATION_DATA_DIR")
    store_temp_files: bool = Field(default=False, alias="STORE_TEMP_FILES")
    fake_mode: bool = Field(default=False, alias="FAKE_MODE")
    demo_max_upload_mb: int = Field(default=100, alias="DEMO_MAX_UPLOAD_MB")
    demo_max_duration_seconds: int = Field(default=120, alias="DEMO_MAX_DURATION_SECONDS")
    demo_result_ttl_seconds: int = Field(default=3600, alias="DEMO_RESULT_TTL_SECONDS")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")


@lru_cache
def get_settings() -> Settings:
    return Settings()
