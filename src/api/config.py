"""Application configuration from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = (
        "postgresql+asyncpg://soccer_analytics:changeme_soccer_2026"
        "@postgres:5432/soccer_analytics"
    )

    # Ollama VLM
    ollama_url: str = "http://ollama:11434"
    vlm_model: str = "qwen3-vl:8b"

    # Processing
    max_upload_size_mb: int = 50
    extraction_timeout_seconds: int = 300
    upload_dir: str = "/app/uploads"

    model_config = {"env_prefix": "", "case_sensitive": False}


settings = Settings()
