from mmpy_bot import Bot, Settings

from ClickUpBot.settings import settings as app_settings
from ClickUpBot.plugins.my_plugin import MyPlugin
from ClickUpBot.plugins.clickup_plugin import ClickUpPlugin


def build_bot_settings() -> Settings:
    """Map AppSettings to mmpy_bot.Settings."""
    return Settings(
        MATTERMOST_URL=app_settings.MATTERMOST_URL,
        MATTERMOST_PORT=app_settings.MATTERMOST_PORT,
        BOT_TOKEN=app_settings.BOT_TOKEN,
        BOT_TEAM=app_settings.BOT_TEAM,
        SSL_VERIFY=app_settings.SSL_VERIFY,
        RESPOND_CHANNEL_HELP=app_settings.RESPOND_CHANNEL_HELP,
        WEBHOOK_HOST_ENABLED=app_settings.WEBHOOK_HOST_ENABLED,
        WEBHOOK_HOST_URL=app_settings.WEBHOOK_HOST_URL,
        WEBHOOK_HOST_PORT=app_settings.WEBHOOK_HOST_PORT,
    )


def main() -> None:
    bot = Bot(
        settings=build_bot_settings(),
        plugins=[MyPlugin(), ClickUpPlugin()],
    )
    bot.run()


if __name__ == "__main__":
    main()


