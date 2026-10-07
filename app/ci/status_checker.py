import logging
import asyncio

logger = logging.getLogger(__name__)

class CIStatusChecker:
    def __init__(self, github_client):
        """
        Initialize the CIStatusChecker with a GitHub client.
        :param github_client: The GitHub client used to make API requests.
        """
        self.github_client = github_client

    async def get_check_runs(self, owner: str, repo: str, ref: str) -> list[dict]:
        endpoint = f"/repos/{owner}/{repo}/commits/{ref}/check-runs"
        try:
            response = await self.github_client.get(endpoint)
            data = response.json()
            return data.get("check_runs", [])
        except Exception as e:
            logger.error(f"Failed to get check runs for {owner}/{repo} at {ref}: {e}")
            return []

    async def get_commit_status(self, owner: str, repo: str, ref: str) -> dict:
        endpoint = f"/repos/{owner}/{repo}/commits/{ref}/status"
        try:
            response = await self.github_client.get(endpoint)
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get commit status for {owner}/{repo} at {ref}: {e}")
            return {}

    async def are_checks_passing(self, owner: str, repo: str, ref: str) -> bool:
        check_runs = await self.get_check_runs(owner, repo, ref)
        commit_status = await self.get_commit_status(owner, repo, ref)

        for run in check_runs:
            if run.get("conclusion") not in ["success", "neutral", "skipped"]:
                return False
        
        status_state = commit_status.get("state")
        if status_state and status_state != "success":
            return False

        return True

    async def wait_for_checks(self, owner: str, repo: str, ref: str, timeout_minutes: int = 30, poll_interval: int = 60) -> bool:
        timeout_seconds = timeout_minutes * 60
        elapsed = 0

        while elapsed < timeout_seconds:
            check_runs = await self.get_check_runs(owner, repo, ref)
            commit_status = await self.get_commit_status(owner, repo, ref)
            
            all_completed = True
            all_passed = True

            for run in check_runs:
                if run.get("status") != "completed":
                    all_completed = False
                    break
                if run.get("conclusion") not in ["success", "neutral", "skipped"]:
                    all_passed = False
            
            status_state = commit_status.get("state", "pending")
            if status_state == "pending":
                all_completed = False
            elif status_state != "success":
                all_passed = False

            if all_completed:
                return all_passed

            logger.info(f"Waiting for checks to complete on {owner}/{repo} at {ref}... ({elapsed}s elapsed)")
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        logger.warning(f"Timeout waiting for checks on {owner}/{repo} at {ref}.")
        return False

    async def get_check_summary(self, owner: str, repo: str, ref: str) -> str:
        check_runs = await self.get_check_runs(owner, repo, ref)
        commit_status = await self.get_commit_status(owner, repo, ref)

        summary = []
        for run in check_runs:
            name = run.get("name", "unknown")
            status = run.get("status")
            conclusion = run.get("conclusion")
            
            if status != "completed":
                icon = "⏳"
                state = "pending"
            elif conclusion in ["success", "neutral", "skipped"]:
                icon = "✅"
                state = conclusion
            else:
                icon = "❌"
                state = conclusion or "failed"
                
            summary.append(f"{icon} {name}: {state}")

        status_state = commit_status.get("state")
        if status_state:
            icon = "✅" if status_state == "success" else "⏳" if status_state == "pending" else "❌"
            summary.append(f"{icon} commit status: {status_state}")

        return "\n".join(summary)
