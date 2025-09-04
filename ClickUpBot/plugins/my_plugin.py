import re

from mmpy_bot import Plugin, listen_to
from mmpy_bot import Message


class MyPlugin(Plugin):
    """Example plugin with a couple of simple listeners."""

    @listen_to("wake up")
    async def wake_up(self, message: Message):
        self.driver.reply_to(message, "I'm awake!")

    @listen_to("hi", re.IGNORECASE)
    async def hi(self, message: Message):
        self.driver.create_post(message.channel_id, "I can understand hi or HI!")

    @listen_to("hey", needs_mention=True)
    async def hey(self, message: Message):
        self.driver.reply_to(message, "Hi! You mentioned me?")


