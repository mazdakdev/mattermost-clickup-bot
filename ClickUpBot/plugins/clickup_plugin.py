import re
from dataclasses import dataclass, field
from typing import Dict, Optional

from mmpy_bot import Plugin, listen_to
from mmpy_bot import Message

from ClickUpBot.services import clickup_client


@dataclass
class TaskDraft:
    name: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[str] = None
    step: str = "name"  # one of: name -> description -> due_date -> confirm


class ClickUpPlugin(Plugin):
    """
    Interactive flow to create a ClickUp task.
    """

    def __init__(self):
        super().__init__()
        self.user_states: Dict[str, TaskDraft] = {}

    # Entry trigger
    @listen_to(r"^create\s+task$", re.IGNORECASE)
    async def start_create_task(self, message: Message):
        user_id = message.user_id
        self.user_states[user_id] = TaskDraft()
        self.driver.reply_to(message, "Let's create a task. What is the task name?")

    # Catch-all while user is in flow
    @listen_to(r"^(?!create\s+task$).+", re.IGNORECASE)
    async def interactive_steps(self, message: Message):
        user_id = message.user_id
        draft = self.user_states.get(user_id)

        if not draft:
            # Ignore messages if user not in flow
            return

        content = message.text.strip()

        if draft.step == "name":
            draft.name = content
            draft.step = "description"
            self.driver.reply_to(message, "Great. Add a short description (or type 'skip').")
            return

        if draft.step == "description":
            if content.lower() != "skip":
                draft.description = content
            draft.step = "due_date"
            self.driver.reply_to(
                message,
                "Optional: provide a due date (YYYY-MM-DD) or type 'skip'.",
            )
            return

        if draft.step == "due_date":
            if content.lower() != "skip":
                draft.due_date = content
            draft.step = "confirm"
            summary = (
                f"Please confirm creation:\n"
                f"- Name: {draft.name}\n"
                f"- Description: {draft.description or '-'}\n"
                f"- Due date: {draft.due_date or '-'}\n"
                "Type 'confirm' to create or 'cancel' to abort."
            )
            self.driver.reply_to(message, summary)
            return

        if draft.step == "confirm":
            if content.lower() == "confirm":
                created, info = clickup_client.create_task(
                    name=draft.name or "Untitled task",
                    description=draft.description,
                    due_date=draft.due_date,
                )
                if created:
                    self.driver.reply_to(
                        message,
                        f"Task created successfully. ID: {info.get('id', '?')} URL: {info.get('url', '-')}",
                    )
                else:
                    self.driver.reply_to(
                        message,
                        f"Failed to create task: {info}",
                    )
                self.user_states.pop(user_id, None)
                return

            if content.lower() == "cancel":
                self.driver.reply_to(message, "Cancelled task creation.")
                self.user_states.pop(user_id, None)
                return

            self.driver.reply_to(
                message,
                "Please type 'confirm' to create or 'cancel' to abort.",
            )
            return


#TODO: IMPORTANT - Dynamic List ID retrieval from user - perhaps show menu to it first
