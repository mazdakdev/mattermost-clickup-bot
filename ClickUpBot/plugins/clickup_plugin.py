import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from mmpy_bot import Plugin, listen_to
from mmpy_bot import Message
services import clickup_client


@dataclass
class TaskDraft:
    name: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[str] = None
    list_id: Optional[str] = None
    step: str = "name"  # one of: name -> description -> due_date -> list_selection -> confirm
    # List selection state
    current_teams: List[clickup_client.ClickUpItem] = field(default_factory=list)
    current_spaces: List[clickup_client.ClickUpItem] = field(default_factory=list)
    current_folders: List[clickup_client.ClickUpItem] = field(default_factory=list)
    current_lists: List[clickup_client.ClickUpItem] = field(default_factory=list)
    selected_team_id: Optional[str] = None
    selected_space_id: Optional[str] = None
    selected_folder_id: Optional[str] = None
    list_selection_step: str = "teams"  # teams -> spaces -> folders -> lists


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
            draft.step = "list_selection"
            await self._start_list_selection(message, draft)
            return

        if draft.step == "list_selection":
            await self._handle_list_selection(message, draft, content)
            return

        if draft.step == "confirm":
            if content.lower() == "confirm":
                created, info = clickup_client.create_task(
                    name=draft.name or "Untitled task",
                    list_id=draft.list_id,
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

    async def _start_list_selection(self, message: Message, draft: TaskDraft):
        """Start the list selection process by fetching teams."""
        self.driver.reply_to(message, "Now let's select where to create the task. Fetching your teams...")
        
        success, teams_or_error = clickup_client.get_teams()
        if not success:
            self.driver.reply_to(message, f"Failed to fetch teams: {teams_or_error}")
            self.user_states.pop(message.user_id, None)
            return
        
        draft.current_teams = teams_or_error
        draft.list_selection_step = "teams"
        
        if not draft.current_teams:
            self.driver.reply_to(message, "No teams found. Task creation cancelled.")
            self.user_states.pop(message.user_id, None)
            return
        
        teams_text = "Available teams:\n"
        for i, team in enumerate(draft.current_teams, 1):
            teams_text += f"{i}. {team.name}\n"
        teams_text += "\nType the number of the team you want to use, or 'cancel' to abort."
        
        self.driver.reply_to(message, teams_text)

    async def _handle_list_selection(self, message: Message, draft: TaskDraft, content: str):
        """Handle the list selection process."""
        if content.lower() == "cancel":
            self.driver.reply_to(message, "Cancelled task creation.")
            self.user_states.pop(message.user_id, None)
            return
        
        if content.lower() == "back":
            await self._go_back_in_selection(message, draft)
            return
        
        try:
            selection = int(content)
        except ValueError:
            self.driver.reply_to(message, "Please enter a valid number, 'back', or 'cancel'.")
            return
        
        if draft.list_selection_step == "teams":
            await self._handle_team_selection(message, draft, selection)
        elif draft.list_selection_step == "spaces":
            await self._handle_space_selection(message, draft, selection)
        elif draft.list_selection_step == "folders":
            await self._handle_folder_selection(message, draft, selection)
        elif draft.list_selection_step == "lists":
            await self._handle_list_final_selection(message, draft, selection)

    async def _handle_team_selection(self, message: Message, draft: TaskDraft, selection: int):
        """Handle team selection and fetch spaces."""
        if selection < 1 or selection > len(draft.current_teams):
            self.driver.reply_to(message, f"Please enter a number between 1 and {len(draft.current_teams)}.")
            return
        
        selected_team = draft.current_teams[selection - 1]
        draft.selected_team_id = selected_team.id
        
        self.driver.reply_to(message, f"Selected team: {selected_team.name}. Fetching spaces...")
        
        success, spaces_or_error = clickup_client.get_spaces(selected_team.id)
        if not success:
            self.driver.reply_to(message, f"Failed to fetch spaces: {spaces_or_error}")
            return
        
        draft.current_spaces = spaces_or_error
        draft.list_selection_step = "spaces"
        
        if not draft.current_spaces:
            self.driver.reply_to(message, "No spaces found in this team. Task creation cancelled.")
            self.user_states.pop(message.user_id, None)
            return
        
        spaces_text = "Available spaces:\n"
        for i, space in enumerate(draft.current_spaces, 1):
            spaces_text += f"{i}. {space.name}\n"
        spaces_text += "\nType the number of the space you want to use, 'back' to go back, or 'cancel' to abort."
        
        self.driver.reply_to(message, spaces_text)

    async def _handle_space_selection(self, message: Message, draft: TaskDraft, selection: int):
        """Handle space selection and fetch folders."""
        if selection < 1 or selection > len(draft.current_spaces):
            self.driver.reply_to(message, f"Please enter a number between 1 and {len(draft.current_spaces)}.")
            return
        
        selected_space = draft.current_spaces[selection - 1]
        draft.selected_space_id = selected_space.id
        
        self.driver.reply_to(message, f"Selected space: {selected_space.name}. Fetching folders...")
        
        success, folders_or_error = clickup_client.get_folders(selected_space.id)
        if not success:
            self.driver.reply_to(message, f"Failed to fetch folders: {folders_or_error}")
            return
        
        draft.current_folders = folders_or_error
        draft.list_selection_step = "folders"
        
        folders_text = "Available folders:\n"
        for i, folder in enumerate(draft.current_folders, 1):
            folders_text += f"{i}. {folder.name}\n"
        folders_text += f"{len(draft.current_folders) + 1}. (No folder - lists directly in space)\n"
        folders_text += "\nType the number of the folder you want to use, 'back' to go back, or 'cancel' to abort."
        
        self.driver.reply_to(message, folders_text)

    async def _handle_folder_selection(self, message: Message, draft: TaskDraft, selection: int):
        """Handle folder selection and fetch lists."""
        if selection < 1 or selection > len(draft.current_folders) + 1:
            self.driver.reply_to(message, f"Please enter a number between 1 and {len(draft.current_folders) + 1}.")
            return
        
        if selection == len(draft.current_folders) + 1:
            # No folder selected, get lists directly from space
            draft.selected_folder_id = None
            self.driver.reply_to(message, "No folder selected. Fetching lists directly from space...")
        else:
            selected_folder = draft.current_folders[selection - 1]
            draft.selected_folder_id = selected_folder.id
            self.driver.reply_to(message, f"Selected folder: {selected_folder.name}. Fetching lists...")
        
        success, lists_or_error = clickup_client.get_lists(
            draft.selected_space_id, 
            draft.selected_folder_id
        )
        if not success:
            self.driver.reply_to(message, f"Failed to fetch lists: {lists_or_error}")
            return
        
        draft.current_lists = lists_or_error
        draft.list_selection_step = "lists"
        
        if not draft.current_lists:
            self.driver.reply_to(message, "No lists found. Task creation cancelled.")
            self.user_states.pop(message.user_id, None)
            return
        
        lists_text = "Available lists:\n"
        for i, list_item in enumerate(draft.current_lists, 1):
            lists_text += f"{i}. {list_item.name}\n"
        lists_text += "\nType the number of the list you want to use, 'back' to go back, or 'cancel' to abort."
        
        self.driver.reply_to(message, lists_text)

    async def _handle_list_final_selection(self, message: Message, draft: TaskDraft, selection: int):
        """Handle final list selection and move to confirmation."""
        if selection < 1 or selection > len(draft.current_lists):
            self.driver.reply_to(message, f"Please enter a number between 1 and {len(draft.current_lists)}.")
            return
        
        selected_list = draft.current_lists[selection - 1]
        draft.list_id = selected_list.id
        
        # Move to confirmation step
        draft.step = "confirm"
        
        # Build path for display
        path_parts = []
        if draft.selected_team_id:
            team_name = next((t.name for t in draft.current_teams if t.id == draft.selected_team_id), "Unknown Team")
            path_parts.append(team_name)
        if draft.selected_space_id:
            space_name = next((s.name for s in draft.current_spaces if s.id == draft.selected_space_id), "Unknown Space")
            path_parts.append(space_name)
        if draft.selected_folder_id:
            folder_name = next((f.name for f in draft.current_folders if f.id == draft.selected_folder_id), "Unknown Folder")
            path_parts.append(folder_name)
        path_parts.append(selected_list.name)
        
        path_str = " > ".join(path_parts)
        
        summary = (
            f"Please confirm task creation:\n"
            f"- Name: {draft.name}\n"
            f"- Description: {draft.description or '-'}\n"
            f"- Due date: {draft.due_date or '-'}\n"
            f"- Location: {path_str}\n"
            "Type 'confirm' to create or 'cancel' to abort."
        )
        self.driver.reply_to(message, summary)

    async def _go_back_in_selection(self, message: Message, draft: TaskDraft):
        """Go back one step in the list selection process."""
        if draft.list_selection_step == "spaces":
            draft.list_selection_step = "teams"
            draft.selected_team_id = None
            draft.current_spaces = []
            draft.current_folders = []
            draft.current_lists = []
            
            teams_text = "Available teams:\n"
            for i, team in enumerate(draft.current_teams, 1):
                teams_text += f"{i}. {team.name}\n"
            teams_text += "\nType the number of the team you want to use, or 'cancel' to abort."
            self.driver.reply_to(message, teams_text)
            
        elif draft.list_selection_step == "folders":
            draft.list_selection_step = "spaces"
            draft.selected_space_id = None
            draft.current_folders = []
            draft.current_lists = []
            
            spaces_text = "Available spaces:\n"
            for i, space in enumerate(draft.current_spaces, 1):
                spaces_text += f"{i}. {space.name}\n"
            spaces_text += "\nType the number of the space you want to use, 'back' to go back, or 'cancel' to abort."
            self.driver.reply_to(message, spaces_text)
            
        elif draft.list_selection_step == "lists":
            draft.list_selection_step = "folders"
            draft.selected_folder_id = None
            draft.current_lists = []
            
            folders_text = "Available folders:\n"
            for i, folder in enumerate(draft.current_folders, 1):
                folders_text += f"{i}. {folder.name}\n"
            folders_text += f"{len(draft.current_folders) + 1}. (No folder - lists directly in space)\n"
            folders_text += "\nType the number of the folder you want to use, 'back' to go back, or 'cancel' to abort."
            self.driver.reply_to(message, folders_text)

