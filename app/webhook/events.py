from enum import Enum
import logging
from app.models.schemas import WebhookEvent

logger = logging.getLogger(__name__)

class EventType(str, Enum):
    INSTALLATION = "installation"
    PUSH = "push"
    PULL_REQUEST = "pull_request"
    INSTALLATION_REPOSITORIES = "installation_repositories"

def parse_event(event_type: str, payload: dict) -> WebhookEvent:
    logger.debug(f"Parsing event: {event_type}")
    action = payload.get("action")
    installation_id = payload.get("installation", {}).get("id")
    repo_full_name = payload.get("repository", {}).get("full_name")
    sender = payload.get("sender", {}).get("login")
    
    return WebhookEvent(
        action=action,
        installation_id=installation_id,
        repo_full_name=repo_full_name,
        sender=sender
    )
