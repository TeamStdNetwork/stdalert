import time
import logging
from typing import Dict, Tuple
import jwt
import httpx

logger = logging.getLogger(__name__)

def generate_jwt(app_id: int, private_key: str) -> str:
    """Generate a JWT for GitHub App authentication."""
    now = int(time.time())
    payload = {
        # issued at time, 60 seconds in the past to allow for clock drift
        "iat": now - 60,
        # JWT expiration time (10 minute maximum)
        "exp": now + (10 * 60),
        # GitHub App's identifier
        "iss": app_id
    }
    
    return jwt.encode(payload, private_key, algorithm="RS256")

async def get_installation_token(app_id: int, private_key: str, installation_id: int) -> str:
    """Fetch a new installation token from GitHub API."""
    jwt_token = generate_jwt(app_id, private_key)
    
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data["token"]


class GitHubAppAuth:
    """GitHub App authentication with token caching."""
    def __init__(self, app_id: int, private_key: str):
        self.app_id = app_id
        self.private_key = private_key
        # Cache format: {installation_id: (token, expiry_timestamp)}
        self._cache: Dict[int, Tuple[str, float]] = {}

    async def get_token(self, installation_id: int) -> str:
        """Get an installation token, utilizing cache if available and valid."""
        now = time.time()
        
        if installation_id in self._cache:
            token, expiry = self._cache[installation_id]
            # Refresh if token expires in less than 5 minutes
            if expiry > now + 300:
                logger.debug(f"Using cached token for installation {installation_id}")
                return token
                
        logger.info(f"Fetching new token for installation {installation_id}")
        token = await get_installation_token(self.app_id, self.private_key, installation_id)
        
        # Tokens are usually valid for 1 hour
        self._cache[installation_id] = (token, now + 3600)
        return token
