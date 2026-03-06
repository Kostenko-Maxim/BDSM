from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
    )

    bot_token: str
    superadmin_id: int
    database_url: str
    timezone: str = "Europe/Moscow"


settings = Settings()  # type: ignore[call-arg]
