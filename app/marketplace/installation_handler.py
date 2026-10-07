import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

class InstallationHandler:
    def __init__(self, app_auth, scan_scheduler):
        self.app_auth = app_auth
        self.scan_scheduler = scan_scheduler

    async def handle_installation(self, payload: Dict[str, Any]) -> None:
        action = payload.get('action')
        installation = payload.get('installation', {})
        installation_id = installation.get('id')
        account = installation.get('account', {}).get('login', 'unknown')
        
        if action == 'created':
            logger.info(f"New installation: {account} (ID: {installation_id})")
            repos = payload.get('repositories', [])
            for repo in repos:
                repo_full_name = repo.get('full_name')
                if repo_full_name:
                    # Add to scan scheduler
                    await self.scan_scheduler.add_repository(installation_id, repo_full_name)
                    # Trigger initial scan
                    await self.scan_scheduler.trigger_scan(installation_id, repo_full_name)
            logger.info(f"New installation: {account} with {len(repos)} repos")
            
        elif action == 'deleted':
            logger.info(f"Installation removed: {account} (ID: {installation_id})")
            await self.scan_scheduler.remove_installation(installation_id)
            
        elif action == 'suspend':
            logger.info(f"Installation suspended: {account} (ID: {installation_id})")
            await self.scan_scheduler.pause_installation(installation_id)
            
        elif action == 'unsuspend':
            logger.info(f"Installation unsuspended: {account} (ID: {installation_id})")
            await self.scan_scheduler.resume_installation(installation_id)

    async def handle_installation_repos(self, payload: Dict[str, Any]) -> None:
        action = payload.get('action')
        installation_id = payload.get('installation', {}).get('id')
        
        if action == 'added':
            repos_added = payload.get('repositories_added', [])
            for repo in repos_added:
                repo_full_name = repo.get('full_name')
                if repo_full_name:
                    await self.scan_scheduler.add_repository(installation_id, repo_full_name)
                    await self.scan_scheduler.trigger_scan(installation_id, repo_full_name)
                    
        elif action == 'removed':
            repos_removed = payload.get('repositories_removed', [])
            for repo in repos_removed:
                repo_full_name = repo.get('full_name')
                if repo_full_name:
                    await self.scan_scheduler.remove_repository(installation_id, repo_full_name)

    async def list_installations(self) -> list[Dict[str, Any]]:
        client = await self.app_auth.get_app_client()
        try:
            response = await client.get("/app/installations")
            return response.json()
        except Exception as e:
            logger.error(f"Failed to list installations: {e}")
            return []

    async def get_installation_repos(self, installation_id: int) -> list[Dict[str, Any]]:
        client = await self.app_auth.get_installation_client(installation_id)
        try:
            response = await client.get("/installation/repositories")
            data = response.json()
            return data.get('repositories', [])
        except Exception as e:
            logger.error(f"Failed to get repos for installation {installation_id}: {e}")
            return []
