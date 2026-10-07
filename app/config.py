import logging
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    GITHUB_APP_ID: int
    GITHUB_PRIVATE_KEY: str
    GITHUB_WEBHOOK_SECRET: str
    SCAN_INTERVAL_HOURS: int = 24
    AUTO_MERGE_ENABLED: bool = False
    AUTO_MERGE_MAX_SEMVER: str = "patch"
    LOG_LEVEL: str = "INFO"
    DATABASE_URL: str = "sqlite:///std_alert.db"
    OSV_API_URL: str = "https://api.osv.dev/v1"

    # Telegram Bot
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None
    TELEGRAM_THREAD_ID: Optional[int] = None

    # Slack
    SLACK_WEBHOOK_URL: Optional[str] = None

    # Discord
    DISCORD_WEBHOOK_URL: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
