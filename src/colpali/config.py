"""ColPali service configuration from environment variables."""

from pydantic_settings import BaseSettings


class ColPaliSettings(BaseSettings):
    """Settings for the ColPali visual retrieval service."""

    index_root: str = "/data/colpali_index"
    index_name: str = "soccer_drills"
    model_name: str = "vidore/colqwen2-v1.0"

    model_config = {"env_prefix": "COLPALI_", "case_sensitive": False}


settings = ColPaliSettings()
