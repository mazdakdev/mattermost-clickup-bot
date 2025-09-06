import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib import error, request

from ClickUpBot.settings import settings


@dataclass
class ClickUpConfig:
    api_token: str
    list_id: str
    base_url: str


@dataclass
class ClickUpItem:
    id: str
    name: str
    type: str  # 'team', 'space', 'folder', 'list'
    parent_id: Optional[str] = None


def get_config() -> Optional[ClickUpConfig]:
    if not settings.CLICKUP_API_TOKEN:
        return None
    return ClickUpConfig(
        api_token=settings.CLICKUP_API_TOKEN,
        list_id=settings.CLICKUP_LIST_ID or "",
        base_url=settings.CLICKUP_BASE_URL,
    )


def _make_api_request(url: str, method: str = "GET", data: Optional[bytes] = None) -> Tuple[bool, Any]:
    """Make a generic API request to ClickUp. Returns (success, data_or_error)."""
    cfg = get_config()
    if cfg is None:
        return False, "Missing CLICKUP_API_TOKEN in environment."

    req = request.Request(url, data=data, method=method)
    req.add_header("Authorization", cfg.api_token)
    if data:
        req.add_header("Content-Type", "application/json")

    try:
        with request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
            if 200 <= resp.status < 300:
                try:
                    return True, json.loads(body)
                except json.JSONDecodeError:
                    return True, {"raw": body}
            else:
                return False, f"HTTP {resp.status}: {body}"
    except error.HTTPError as e:
        body = e.read().decode("utf-8") if hasattr(e, "read") else str(e)
        return False, f"HTTPError {e.code}: {body}"
    except Exception as e:  # noqa: BLE001 broad for network
        return False, str(e)


def get_teams() -> Tuple[bool, List[ClickUpItem]]:
    """Get all teams accessible to the user. Returns (success, teams_or_error)."""
    cfg = get_config()
    if cfg is None:
        return False, "Missing CLICKUP_API_TOKEN in environment."

    url = f"{cfg.base_url}/team"
    success, data = _make_api_request(url)
    
    if not success:
        return False, data
    
    if isinstance(data, dict) and "teams" in data:
        teams = []
        for team in data["teams"]:
            teams.append(ClickUpItem(
                id=team["id"],
                name=team["name"],
                type="team"
            ))
        return True, teams
    
    return False, "Unexpected response format"


def get_spaces(team_id: str) -> Tuple[bool, List[ClickUpItem]]:
    """Get all spaces in a team. Returns (success, spaces_or_error)."""
    cfg = get_config()
    if cfg is None:
        return False, "Missing CLICKUP_API_TOKEN in environment."

    url = f"{cfg.base_url}/team/{team_id}/space"
    success, data = _make_api_request(url)
    
    if not success:
        return False, data
    
    if isinstance(data, dict) and "spaces" in data:
        spaces = []
        for space in data["spaces"]:
            spaces.append(ClickUpItem(
                id=space["id"],
                name=space["name"],
                type="space",
                parent_id=team_id
            ))
        return True, spaces
    
    return False, "Unexpected response format"


def get_folders(space_id: str) -> Tuple[bool, List[ClickUpItem]]:
    """Get all folders in a space. Returns (success, folders_or_error)."""
    cfg = get_config()
    if cfg is None:
        return False, "Missing CLICKUP_API_TOKEN in environment."

    url = f"{cfg.base_url}/space/{space_id}/folder"
    success, data = _make_api_request(url)
    
    if not success:
        return False, data
    
    if isinstance(data, dict) and "folders" in data:
        folders = []
        for folder in data["folders"]:
            folders.append(ClickUpItem(
                id=folder["id"],
                name=folder["name"],
                type="folder",
                parent_id=space_id
            ))
        return True, folders
    
    return False, "Unexpected response format"


def get_lists(space_id: str, folder_id: Optional[str] = None) -> Tuple[bool, List[ClickUpItem]]:
    """Get all lists in a space or folder. Returns (success, lists_or_error)."""
    cfg = get_config()
    if cfg is None:
        return False, "Missing CLICKUP_API_TOKEN in environment."

    if folder_id:
        url = f"{cfg.base_url}/folder/{folder_id}/list"
    else:
        url = f"{cfg.base_url}/space/{space_id}/list"
    
    success, data = _make_api_request(url)
    
    if not success:
        return False, data
    
    if isinstance(data, dict) and "lists" in data:
        lists = []
        for list_item in data["lists"]:
            lists.append(ClickUpItem(
                id=list_item["id"],
                name=list_item["name"],
                type="list",
                parent_id=folder_id or space_id
            ))
        return True, lists
    
    return False, "Unexpected response format"


def create_task(name: str, list_id: str, description: Optional[str] = None, due_date: Optional[str] = None) -> Tuple[bool, Any]:
    """Create a task in ClickUp. Returns (success, data_or_error)."""
    cfg = get_config()
    if cfg is None:
        return False, "Missing CLICKUP_API_TOKEN in environment."

    url = f"{cfg.base_url}/list/{list_id}/task"

    payload: Dict[str, object] = {"name": name or "Untitled task"}
    if description:
        payload["description"] = description

    if due_date:
        try:
            dt = datetime.strptime(due_date, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, tzinfo=timezone.utc
            )
            payload["due_date"] = str(int(dt.timestamp() * 1000))
            payload["due_date_time"] = True
        except ValueError:
            # ignore invalid date
            pass

    data = json.dumps(payload).encode("utf-8")
    return _make_api_request(url, method="POST", data=data)


def get_task(task_id: str) -> Tuple[bool, Any]:
    """Get a task by ID. Returns (success, task_data_or_error)."""
    cfg = get_config()
    if cfg is None:
        return False, "Missing CLICKUP_API_TOKEN in environment."

    url = f"{cfg.base_url}/task/{task_id}"
    return _make_api_request(url)


def get_tasks_from_list(list_id: str, include_closed: bool = False) -> Tuple[bool, Any]:
    """Get all tasks from a list. Returns (success, tasks_data_or_error)."""
    cfg = get_config()
    if cfg is None:
        return False, "Missing CLICKUP_API_TOKEN in environment."

    url = f"{cfg.base_url}/list/{list_id}/task"
    if include_closed:
        url += "?include_closed=true"
    
    return _make_api_request(url)


def update_task(task_id: str, updates: Dict[str, Any]) -> Tuple[bool, Any]:
    """Update a task. Returns (success, updated_task_data_or_error)."""
    cfg = get_config()
    if cfg is None:
        return False, "Missing CLICKUP_API_TOKEN in environment."

    url = f"{cfg.base_url}/task/{task_id}"

    # Handle due_date conversion if present
    if "due_date" in updates and updates["due_date"]:
        try:
            dt = datetime.strptime(updates["due_date"], "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, tzinfo=timezone.utc
            )
            updates["due_date"] = str(int(dt.timestamp() * 1000))
            updates["due_date_time"] = True
        except ValueError:
            # ignore invalid date
            pass

    data = json.dumps(updates).encode("utf-8")
    return _make_api_request(url, method="PUT", data=data)


def delete_task(task_id: str) -> Tuple[bool, Any]:
    """Delete a task. Returns (success, result_or_error)."""
    cfg = get_config()
    if cfg is None:
        return False, "Missing CLICKUP_API_TOKEN in environment."

    url = f"{cfg.base_url}/task/{task_id}"
    return _make_api_request(url, method="DELETE")


# def search_tasks(query: str, team_id: Optional[str] = None) -> Tuple[bool, Any]:
#     """Search for tasks. Returns (success, search_results_or_error)."""
#     cfg = get_config()
#     if cfg is None:
#         return False, "Missing CLICKUP_API_TOKEN in environment."

#     url = f"{cfg.base_url}/task"
#     params = [f"name={query}"]
#     if team_id:
#         params.append(f"team_ids[]={team_id}")
    
#     if params:
#         url += "?" + "&".join(params)
    
#     return _make_api_request(url)


