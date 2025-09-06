import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from mmpy_bot import Plugin, listen_to
from mmpy_bot import Message

from ClickUpBot.services import clickup_client


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


@dataclass
class TaskViewDraft:
    operation: str = "view"  # view, search, list_tasks
    step: str = "list_selection"  # list_selection -> confirm
    list_id: Optional[str] = None
    task_id: Optional[str] = None
    search_query: Optional[str] = None
    current_tasks: List[Dict] = field(default_factory=list)  # For storing tasks when viewing
    # List selection state (reused from TaskDraft)
    current_teams: List[clickup_client.ClickUpItem] = field(default_factory=list)
    current_spaces: List[clickup_client.ClickUpItem] = field(default_factory=list)
    current_folders: List[clickup_client.ClickUpItem] = field(default_factory=list)
    current_lists: List[clickup_client.ClickUpItem] = field(default_factory=list)
    selected_team_id: Optional[str] = None
    selected_space_id: Optional[str] = None
    selected_folder_id: Optional[str] = None
    list_selection_step: str = "teams"


@dataclass
class TaskUpdateDraft:
    task_id: Optional[str] = None
    step: str = "task_id"  # task_id -> field_selection -> field_update -> confirm
    selected_field: Optional[str] = None
    new_value: Optional[str] = None
    available_fields: List[str] = field(default_factory=lambda: ["name", "description", "due_date", "status"])


@dataclass
class TaskDeleteDraft:
    task_id: Optional[str] = None
    step: str = "task_id"  # task_id -> confirm
    task_name: Optional[str] = None


class ClickUpPlugin(Plugin):
    """
    Interactive ClickUp CRUD operations for tasks.
    """

    def __init__(self):
        super().__init__()
        self.user_states: Dict[str, Any] = {}  # Can hold TaskDraft, TaskViewDraft, TaskUpdateDraft, or TaskDeleteDraft

    # Entry triggers for CRUD operations
    @listen_to(r"^create\s+task$", re.IGNORECASE)
    async def start_create_task(self, message: Message):
        user_id = message.user_id
        self.user_states[user_id] = TaskDraft()
        self.driver.reply_to(message, "Let's create a task. What is the task name?")

    @listen_to(r"^view\s+task$", re.IGNORECASE)
    async def start_view_task(self, message: Message):
        user_id = message.user_id
        self.user_states[user_id] = TaskViewDraft(operation="view")
        await self._start_list_selection_for_viewing(message, self.user_states[user_id])

    @listen_to(r"^list\s+tasks$", re.IGNORECASE)
    async def start_list_tasks(self, message: Message):
        user_id = message.user_id
        self.user_states[user_id] = TaskViewDraft(operation="list_tasks")
        await self._start_list_selection_for_viewing(message, self.user_states[user_id])

    @listen_to(r"^search\s+tasks$", re.IGNORECASE)
    async def start_search_tasks(self, message: Message):
        user_id = message.user_id
        self.user_states[user_id] = TaskViewDraft(operation="search", step="search_query")
        self.driver.reply_to(message, "Let's search for tasks. What would you like to search for?")

    @listen_to(r"^update\s+task$", re.IGNORECASE)
    async def start_update_task(self, message: Message):
        user_id = message.user_id
        self.user_states[user_id] = TaskUpdateDraft()
        self.driver.reply_to(message, "Let's update a task. Please provide the task ID:")

    @listen_to(r"^delete\s+task$", re.IGNORECASE)
    async def start_delete_task(self, message: Message):
        user_id = message.user_id
        self.user_states[user_id] = TaskDeleteDraft()
        self.driver.reply_to(message, "Let's delete a task. Please provide the task ID:")

    # Catch-all while user is in flow
    @listen_to(r"^(?!create\s+task$|view\s+task$|list\s+tasks$|search\s+tasks$|update\s+task$|delete\s+task$).+", re.IGNORECASE)
    async def interactive_steps(self, message: Message):
        user_id = message.user_id
        draft = self.user_states.get(user_id)

        if not draft:
            # Ignore messages if user not in flow
            return

        content = message.text.strip()

        # Handle different types of drafts
        if isinstance(draft, TaskDraft):
            await self._handle_task_creation(message, draft, content)
        elif isinstance(draft, TaskViewDraft):
            await self._handle_task_viewing(message, draft, content)
        elif isinstance(draft, TaskUpdateDraft):
            await self._handle_task_updating(message, draft, content)
        elif isinstance(draft, TaskDeleteDraft):
            await self._handle_task_deletion(message, draft, content)

    async def _handle_task_creation(self, message: Message, draft: TaskDraft, content: str):
        """Handle task creation flow."""
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
                self.user_states.pop(message.user_id, None)
                return

            if content.lower() == "cancel":
                self.driver.reply_to(message, "Cancelled task creation.")
                self.user_states.pop(message.user_id, None)
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

    async def _start_list_selection_for_viewing(self, message: Message, draft: TaskViewDraft):
        """Start the list selection process for viewing operations by fetching teams."""
        self.driver.reply_to(message, "Let's select where to view tasks from. Fetching your teams...")
        
        success, teams_or_error = clickup_client.get_teams()
        if not success:
            self.driver.reply_to(message, f"Failed to fetch teams: {teams_or_error}")
            self.user_states.pop(message.user_id, None)
            return
        
        draft.current_teams = teams_or_error
        draft.list_selection_step = "teams"
        
        if not draft.current_teams:
            self.driver.reply_to(message, "No teams found. Operation cancelled.")
            self.user_states.pop(message.user_id, None)
            return
        
        teams_text = "Available teams:\n"
        for i, team in enumerate(draft.current_teams, 1):
            teams_text += f"{i}. {team.name}\n"
        teams_text += "\nType the number of the team you want to use, or 'cancel' to abort."
        
        self.driver.reply_to(message, teams_text)

    async def _handle_task_viewing(self, message: Message, draft: TaskViewDraft, content: str):
        """Handle task viewing flow (view, list, search)."""
        if content.lower() == "cancel":
            self.driver.reply_to(message, "Cancelled task viewing.")
            self.user_states.pop(message.user_id, None)
            return

        # Handle task selection step (for view operation)
        if draft.step == "task_selection":
            try:
                selection = int(content)
                if 1 <= selection <= len(draft.current_tasks):
                    selected_task = draft.current_tasks[selection - 1]
                    await self._show_task_details(message, selected_task)
                    self.user_states.pop(message.user_id, None)
                    return
                else:
                    self.driver.reply_to(message, f"Please enter a number between 1 and {len(draft.current_tasks)}.")
            except ValueError:
                self.driver.reply_to(message, "Please enter a valid number or 'cancel' to abort.")
            return

        # Handle search query step (for search operation)
        if draft.operation == "search" and draft.step == "search_query":
            draft.search_query = content
            draft.step = "confirm"
            self.driver.reply_to(message, f"Searching for tasks with query: '{content}'. Type 'confirm' to search or 'cancel' to abort.")
            return

        # Handle list selection step
        if draft.step == "list_selection":
            await self._handle_list_selection_for_viewing(message, draft, content)
            return

        # Handle confirmation step
        if draft.step == "confirm":
            if content.lower() == "confirm":
                if draft.operation == "search":
                    await self._execute_search(message, draft)
                    self.user_states.pop(message.user_id, None)
                elif draft.operation == "list_tasks":
                    await self._execute_list_tasks(message, draft)
                    self.user_states.pop(message.user_id, None)
                elif draft.operation == "view":
                    await self._execute_view_task(message, draft)
                    # Don't pop user state here - user needs to select a task
                return

            if content.lower() == "cancel":
                self.driver.reply_to(message, "Cancelled task viewing.")
                self.user_states.pop(message.user_id, None)
                return

    async def _handle_task_updating(self, message: Message, draft: TaskUpdateDraft, content: str):
        """Handle task updating flow."""
        if content.lower() == "cancel":
            self.driver.reply_to(message, "Cancelled task update.")
            self.user_states.pop(message.user_id, None)
            return

        if draft.step == "task_id":
            draft.task_id = content
            # Fetch the task to show current details
            success, task_data = clickup_client.get_task(content)
            if not success:
                self.driver.reply_to(message, f"Failed to fetch task: {task_data}")
                return
            
            draft.step = "field_selection"
            task_name = task_data.get("name", "Unknown")
            self.driver.reply_to(
                message,
                f"Found task: {task_name}\n\nAvailable fields to update:\n"
                f"1. name\n2. description\n3. due_date\n4. status\n\n"
                "Type the number of the field you want to update, or 'cancel' to abort."
            )
            return

        if draft.step == "field_selection":
            try:
                field_num = int(content)
                if 1 <= field_num <= 4:
                    field_map = {1: "name", 2: "description", 3: "due_date", 4: "status"}
                    draft.selected_field = field_map[field_num]
                    draft.step = "field_update"
                    
                    if draft.selected_field == "due_date":
                        self.driver.reply_to(message, f"Enter new {draft.selected_field} (YYYY-MM-DD format) or 'cancel' to abort:")
                    else:
                        self.driver.reply_to(message, f"Enter new {draft.selected_field} or 'cancel' to abort:")
                else:
                    self.driver.reply_to(message, "Please enter a number between 1 and 4, or 'cancel' to abort.")
            except ValueError:
                self.driver.reply_to(message, "Please enter a valid number, or 'cancel' to abort.")
            return

        if draft.step == "field_update":
            draft.new_value = content
            draft.step = "confirm"
            self.driver.reply_to(
                message,
                f"Please confirm update:\n"
                f"Task ID: {draft.task_id}\n"
                f"Field: {draft.selected_field}\n"
                f"New value: {draft.new_value}\n\n"
                "Type 'confirm' to update or 'cancel' to abort."
            )
            return

        if draft.step == "confirm":
            if content.lower() == "confirm":
                updates = {draft.selected_field: draft.new_value}
                success, result = clickup_client.update_task(draft.task_id, updates)
                if success:
                    self.driver.reply_to(message, f"Task updated successfully!")
                else:
                    self.driver.reply_to(message, f"Failed to update task: {result}")
                self.user_states.pop(message.user_id, None)
                return

            if content.lower() == "cancel":
                self.driver.reply_to(message, "Cancelled task update.")
                self.user_states.pop(message.user_id, None)
                return

    async def _handle_task_deletion(self, message: Message, draft: TaskDeleteDraft, content: str):
        """Handle task deletion flow."""
        if content.lower() == "cancel":
            self.driver.reply_to(message, "Cancelled task deletion.")
            self.user_states.pop(message.user_id, None)
            return

        if draft.step == "task_id":
            draft.task_id = content
            # Fetch the task to show details before deletion
            success, task_data = clickup_client.get_task(content)
            if not success:
                self.driver.reply_to(message, f"Failed to fetch task: {task_data}")
                return
            
            draft.task_name = task_data.get("name", "Unknown")
            draft.step = "confirm"
            self.driver.reply_to(
                message,
                f"⚠️ WARNING: You are about to DELETE this task:\n"
                f"ID: {draft.task_id}\n"
                f"Name: {draft.task_name}\n\n"
                "This action cannot be undone!\n\n"
                "Type 'DELETE' to confirm deletion or 'cancel' to abort."
            )
            return

        if draft.step == "confirm":
            if content.upper() == "DELETE":
                success, result = clickup_client.delete_task(draft.task_id)
                if success:
                    self.driver.reply_to(message, f"Task '{draft.task_name}' deleted successfully!")
                else:
                    self.driver.reply_to(message, f"Failed to delete task: {result}")
                self.user_states.pop(message.user_id, None)
                return

            if content.lower() == "cancel":
                self.driver.reply_to(message, "Cancelled task deletion.")
                self.user_states.pop(message.user_id, None)
                return

            self.driver.reply_to(message, "Please type 'DELETE' to confirm or 'cancel' to abort.")

    async def _handle_list_selection_for_viewing(self, message: Message, draft: TaskViewDraft, content: str):
        """Handle list selection for viewing operations (reuses existing logic)."""
        if content.lower() == "back":
            await self._go_back_in_selection_for_viewing(message, draft)
            return
        
        try:
            selection = int(content)
        except ValueError:
            self.driver.reply_to(message, "Please enter a valid number, 'back', or 'cancel'.")
            return
        
        if draft.list_selection_step == "teams":
            await self._handle_team_selection_for_viewing(message, draft, selection)
        elif draft.list_selection_step == "spaces":
            await self._handle_space_selection_for_viewing(message, draft, selection)
        elif draft.list_selection_step == "folders":
            await self._handle_folder_selection_for_viewing(message, draft, selection)
        elif draft.list_selection_step == "lists":
            await self._handle_list_final_selection_for_viewing(message, draft, selection)

    async def _handle_team_selection_for_viewing(self, message: Message, draft: TaskViewDraft, selection: int):
        """Handle team selection for viewing operations."""
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
            self.driver.reply_to(message, "No spaces found in this team. Operation cancelled.")
            self.user_states.pop(message.user_id, None)
            return
        
        spaces_text = "Available spaces:\n"
        for i, space in enumerate(draft.current_spaces, 1):
            spaces_text += f"{i}. {space.name}\n"
        spaces_text += "\nType the number of the space you want to use, 'back' to go back, or 'cancel' to abort."
        
        self.driver.reply_to(message, spaces_text)

    async def _handle_space_selection_for_viewing(self, message: Message, draft: TaskViewDraft, selection: int):
        """Handle space selection for viewing operations."""
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

    async def _handle_folder_selection_for_viewing(self, message: Message, draft: TaskViewDraft, selection: int):
        """Handle folder selection for viewing operations."""
        if selection < 1 or selection > len(draft.current_folders) + 1:
            self.driver.reply_to(message, f"Please enter a number between 1 and {len(draft.current_folders) + 1}.")
            return
        
        if selection == len(draft.current_folders) + 1:
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
            self.driver.reply_to(message, "No lists found. Operation cancelled.")
            self.user_states.pop(message.user_id, None)
            return
        
        lists_text = "Available lists:\n"
        for i, list_item in enumerate(draft.current_lists, 1):
            lists_text += f"{i}. {list_item.name}\n"
        lists_text += "\nType the number of the list you want to use, 'back' to go back, or 'cancel' to abort."
        
        self.driver.reply_to(message, lists_text)

    async def _handle_list_final_selection_for_viewing(self, message: Message, draft: TaskViewDraft, selection: int):
        """Handle final list selection for viewing operations."""
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
        
        if draft.operation == "list_tasks":
            self.driver.reply_to(message, f"Ready to list tasks from: {path_str}\nType 'confirm' to proceed or 'cancel' to abort.")
        elif draft.operation == "view":
            self.driver.reply_to(message, f"Ready to browse tasks from: {path_str}\nType 'confirm' to proceed or 'cancel' to abort.")

    async def _go_back_in_selection_for_viewing(self, message: Message, draft: TaskViewDraft):
        """Go back one step in the list selection process for viewing operations."""
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

    # async def _execute_search(self, message: Message, draft: TaskViewDraft):
    #     """Execute task search."""
    #     success, results = clickup_client.search_tasks(draft.search_query, draft.selected_team_id)
    #     if not success:
    #         self.driver.reply_to(message, f"Search failed: {results}")
    #         return
        
    #     if isinstance(results, dict) and "tasks" in results:
    #         tasks = results["tasks"]
    #         if not tasks:
    #             self.driver.reply_to(message, f"No tasks found matching '{draft.search_query}'")
    #             return
            
    #         response = f"Found {len(tasks)} task(s) matching '{draft.search_query}':\n\n"
    #         for i, task in enumerate(tasks[:10], 1):  # Limit to 10 results
    #             response += f"{i}. {task.get('name', 'Unnamed')} (ID: {task.get('id', '?')})\n"
    #             if task.get('description'):
    #                 desc = task['description'][:100] + "..." if len(task['description']) > 100 else task['description']
    #                 response += f"   Description: {desc}\n"
    #             response += f"   Status: {task.get('status', {}).get('status', 'Unknown')}\n"
    #             response += f"   URL: {task.get('url', 'N/A')}\n\n"
            
    #         if len(tasks) > 10:
    #             response += f"... and {len(tasks) - 10} more tasks."
            
    #         self.driver.reply_to(message, response)
    #     else:
    #         self.driver.reply_to(message, f"Unexpected search results format: {results}")
        self.driver.reply_to(message, "Search functionality is not implemented yet. \n TODO: ClickUp API does not support search tasks by name.")

    async def _execute_list_tasks(self, message: Message, draft: TaskViewDraft):
        """Execute list tasks operation."""
        success, results = clickup_client.get_tasks_from_list(draft.list_id, include_closed=False)
        if not success:
            self.driver.reply_to(message, f"Failed to fetch tasks: {results}")
            return
        
        if isinstance(results, dict) and "tasks" in results:
            tasks = results["tasks"]
            if not tasks:
                self.driver.reply_to(message, "No tasks found in this list.")
                return
            
            response = f"Tasks in this list ({len(tasks)} total):\n\n"
            for i, task in enumerate(tasks[:20], 1):  # Limit to 20 results
                response += f"{i}. {task.get('name', 'Unnamed')} (ID: {task.get('id', '?')})\n"
                if task.get('description'):
                    desc = task['description'][:100] + "..." if len(task['description']) > 100 else task['description']
                    response += f"   Description: {desc}\n"
                response += f"   Status: {task.get('status', {}).get('status', 'Unknown')}\n"
                if task.get('due_date'):
                    response += f"   Due: {task.get('due_date')}\n"
                response += f"   URL: {task.get('url', 'N/A')}\n\n"
            
            if len(tasks) > 20:
                response += f"... and {len(tasks) - 20} more tasks."
            
            self.driver.reply_to(message, response)
        else:
            self.driver.reply_to(message, f"Unexpected task list format: {results}")

    async def _execute_view_task(self, message: Message, draft: TaskViewDraft):
        """Execute view task operation - show tasks and let user select one."""
        success, results = clickup_client.get_tasks_from_list(draft.list_id, include_closed=False)
        if not success:
            self.driver.reply_to(message, f"Failed to fetch tasks: {results}")
            return
        
        if isinstance(results, dict) and "tasks" in results:
            tasks = results["tasks"]
            if not tasks:
                self.driver.reply_to(message, "No tasks found in this list.")
                return
            
            # Store tasks for selection
            draft.current_tasks = tasks[:20]  # Limit to 20 tasks
            
            response = f"Tasks in this list ({len(tasks)} total):\n\n"
            for i, task in enumerate(draft.current_tasks, 1):
                response += f"{i}. {task.get('name', 'Unnamed')} (ID: {task.get('id', '?')})\n"
                response += f"   Status: {task.get('status', {}).get('status', 'Unknown')}\n"
                if task.get('due_date'):
                    response += f"   Due: {task.get('due_date')}\n"
                response += "\n"
            
            if len(tasks) > 20:
                response += f"... and {len(tasks) - 20} more tasks (showing first 20)."
            
            response += "\nType the number of the task you want to view in detail, or 'cancel' to abort."
            self.driver.reply_to(message, response)
            
            # Change step to task selection
            draft.step = "task_selection"
        else:
            self.driver.reply_to(message, f"Unexpected task list format: {results}")

    async def _show_task_details(self, message: Message, task: Dict):
        """Show detailed information about a task."""
        response = f"📋 **Task Details**\n\n"
        response += f"**Name:** {task.get('name', 'Unnamed')}\n"
        response += f"**ID:** {task.get('id', 'Unknown')}\n"
        response += f"**Status:** {task.get('status', {}).get('status', 'Unknown')}\n"
        
        if task.get('description'):
            response += f"**Description:**\n{task['description']}\n"
        
        if task.get('due_date'):
            response += f"**Due Date:** {task['due_date']}\n"
        
        if task.get('priority'):
            response += f"**Priority:** {task.get('priority', {}).get('priority', 'Normal')}\n"
        
        if task.get('assignees'):
            assignees = [assignee.get('username', 'Unknown') for assignee in task['assignees']]
            response += f"**Assignees:** {', '.join(assignees)}\n"
        
        if task.get('tags'):
            tags = [tag.get('name', 'Unknown') for tag in task['tags']]
            response += f"**Tags:** {', '.join(tags)}\n"
        
        if task.get('url'):
            response += f"**URL:** {task['url']}\n"
        
        response += f"\n**Created:** {task.get('date_created', 'Unknown')}"
        if task.get('date_updated'):
            response += f"\n**Last Updated:** {task['date_updated']}"
        
        self.driver.reply_to(message, response)

