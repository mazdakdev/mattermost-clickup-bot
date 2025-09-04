from pydantic_settings import BaseSettings


class AppSettings(BaseSettings):
    """Application settings loaded from environment variables (.env supported).

    These are mapped to mmpy_bot.Settings in the entrypoint.
    """

    # Core Mattermost bot configuration
    MATTERMOST_URL: str = "http://127.0.0.1"
    MATTERMOST_PORT: int = 8065
    BOT_TOKEN: str = ""
    BOT_TEAM: str = ""
    SSL_VERIFY: bool = False

    # Optional: built-in Help plugin behavior
    RESPOND_CHANNEL_HELP: bool = False

    # Optional: webhook server configuration
    WEBHOOK_HOST_ENABLED: bool = False
    WEBHOOK_HOST_URL: str | None = None
    WEBHOOK_HOST_PORT: int | None = None

    # ClickUp API configuration
    CLICKUP_API_TOKEN: str | None = None
    CLICKUP_LIST_ID: str | None = None
    CLICKUP_BASE_URL: str = "https://api.clickup.com/api/v2"

    class Config:
        env_file = ".env"


# Singleton-style settings instance
settings = AppSettings()