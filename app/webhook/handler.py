import hmac
import hashlib
import logging

logger = logging.getLogger(__name__)

def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    if not signature.startswith("sha256="):
        return False
    mac = hmac.new(secret.encode('utf-8'), msg=payload, digestmod=hashlib.sha256)
    expected_signature = "sha256=" + mac.hexdigest()
    return hmac.compare_digest(expected_signature, signature)

async def process_webhook(event_type: str, payload: dict):
    logger.info(f"Processing webhook event: {event_type}")
    
    if event_type == "installation":
        action = payload.get("action")
        installation_id = payload.get("installation", {}).get("id")
        logger.info(f"Installation event: action={action}, installation_id={installation_id}")
        
    elif event_type == "push":
        ref = payload.get("ref", "")
        repo = payload.get("repository", {})
        default_branch = repo.get("default_branch", "main")
        repo_full_name = repo.get("full_name")
        
        if ref == f"refs/heads/{default_branch}":
            logger.info(f"Push to default branch {default_branch} in {repo_full_name}. Triggering scan...")
            
    elif event_type == "pull_request":
        action = payload.get("action")
        repo_full_name = payload.get("repository", {}).get("full_name")
        logger.info(f"Pull request event: action={action} in {repo_full_name}")
        
    else:
        logger.info(f"Ignored event type: {event_type}")
