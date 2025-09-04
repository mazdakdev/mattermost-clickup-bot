import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from urllib import error, request

from ClickUpBot.settings import settings


@dataclass
class ClickUpConfig:
    api_token: str
    list_id: str
    base_url: str


def get_config() -> Optional[ClickUpConfig]:
    if not settings.CLICKUP_API_TOKEN or not settings.CLICKUP_LIST_ID:
        return None
    return ClickUpConfig(
        api_token=settings.CLICKUP_API_TOKEN,
        list_id=settings.CLICKUP_LIST_ID,
        base_url=settings.CLICKUP_BASE_URL,
    )


def create_task(name: str, description: Optional[str] = None, due_date: Optional[str] = None) -> Tuple[bool, Any]:
    """Create a task in ClickUp. Returns (success, data_or_error)."""
    cfg = get_config()
    if cfg is None:
        return False, "Missing CLICKUP_API_TOKEN or CLICKUP_LIST_ID in environment."

    url = f"{cfg.base_url}/list/{cfg.list_id}/task"

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
    req = request.Request(url, data=data, method="POST")
    req.add_header("Authorization", cfg.api_token)
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


