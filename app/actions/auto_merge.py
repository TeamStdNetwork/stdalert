import logging
from typing import List

from app.models.schemas import DependencyInfo, VulnerabilityInfo
from app.github.api import GitHubClient

logger = logging.getLogger(__name__)

class AutoMerger:
    """
    Handles auto-merging of pull requests based on safety rules.
    """

    def __init__(self, github_client: GitHubClient, max_semver: str = 'patch'):
        self.github = github_client
        self.max_semver = max_semver.lower()

    async def should_auto_merge(self, dependency: DependencyInfo, vulnerabilities: List[VulnerabilityInfo]) -> bool:
        """
        Determines if a dependency update is safe to auto-merge.
        Rules:
        - Only patch updates auto-merge by default (or up to max_semver).
        - No known vulnerabilities in NEW version (vulnerabilities list applies to new version here).
        - No breaking changes (inherent in patch).
        """
        if vulnerabilities:
            logger.info(f"Auto-merge disabled for {dependency.name}: known vulnerabilities in target version.")
            return False

        update_type = self._determine_update_type(dependency.current_version, dependency.new_version)
        
        if update_type == "major":
            logger.info(f"Auto-merge disabled for {dependency.name}: major update detected.")
            return False
            
        if self.max_semver == "patch" and update_type != "patch":
            logger.info(f"Auto-merge disabled for {dependency.name}: {update_type} update exceeds max_semver ({self.max_semver}).")
            return False

        return True

    async def enable_auto_merge(self, owner: str, repo: str, pr_number: int) -> bool:
        """
        Enables GitHub's native auto-merge feature on a PR.
        Note: Requires a GraphQL mutation since REST API support is limited/preview for auto-merge.
        We'll simulate or use standard merge if native auto-merge isn't directly exposed by the client.
        """
        logger.info(f"Enabling auto-merge for PR #{pr_number} in {owner}/{repo}")
        try:
            # Placeholder for actual client call (GraphQL enablePullRequestAutoMerge)
            await self.github.enable_auto_merge(owner, repo, pr_number)
            return True
        except Exception as e:
            logger.error(f"Failed to enable auto-merge for PR #{pr_number}: {e}")
            return False

    async def merge_pr(self, owner: str, repo: str, pr_number: int, merge_method: str = 'squash') -> bool:
        """
        Immediately merges a PR using the specified method.
        """
        logger.info(f"Merging PR #{pr_number} in {owner}/{repo} via {merge_method}")
        try:
            await self.github.merge_pull_request(
                owner=owner, 
                repo=repo, 
                pr_number=pr_number, 
                merge_method=merge_method
            )
            return True
        except Exception as e:
            logger.error(f"Failed to merge PR #{pr_number}: {e}")
            return False

    def _determine_update_type(self, old: str, new: str) -> str:
        """Basic semver comparison helper."""
        try:
            o_parts = old.strip("v^~").split(".")
            n_parts = new.strip("v^~").split(".")
            if len(o_parts) > 0 and len(n_parts) > 0 and o_parts[0] != n_parts[0]:
                return "major"
            if len(o_parts) > 1 and len(n_parts) > 1 and o_parts[1] != n_parts[1]:
                return "minor"
            return "patch"
        except Exception:
            return "unknown"
