import logging
from typing import Optional

from app.github.api import GitHubClient

logger = logging.getLogger(__name__)

async def create_update_branch(github_client: GitHubClient, owner: str, repo: str, branch_name: str, base_branch: str = "main") -> bool:
    """
    Creates a new branch for the dependency update based on the base branch.
    """
    try:
        # Get the SHA of the base branch
        base_ref = await github_client.get_reference(owner, repo, f"heads/{base_branch}")
        sha = base_ref.get("object", {}).get("sha")
        
        if not sha:
            logger.error(f"Could not find SHA for base branch {base_branch} in {owner}/{repo}")
            return False

        # Create the new branch
        await github_client.create_reference(
            owner=owner,
            repo=repo,
            ref=f"refs/heads/{branch_name}",
            sha=sha
        )
        logger.info(f"Created branch {branch_name} in {owner}/{repo}")
        return True
    except Exception as e:
        logger.error(f"Failed to create branch {branch_name} in {owner}/{repo}: {e}")
        return False

async def delete_branch(github_client: GitHubClient, owner: str, repo: str, branch_name: str) -> bool:
    """
    Deletes an existing branch.
    """
    try:
        await github_client.delete_reference(owner, repo, f"heads/{branch_name}")
        logger.info(f"Deleted branch {branch_name} in {owner}/{repo}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete branch {branch_name} in {owner}/{repo}: {e}")
        return False

async def branch_exists(github_client: GitHubClient, owner: str, repo: str, branch_name: str) -> bool:
    """
    Checks if a branch already exists.
    """
    try:
        ref = await github_client.get_reference(owner, repo, f"heads/{branch_name}")
        return ref is not None and "ref" in ref
    except Exception:
        # Typically returns 404 if it doesn't exist
        return False

def generate_branch_name(ecosystem: str, package: str, new_version: str) -> str:
    """
    Generates a standardized branch name for a dependency update.
    """
    safe_package = package.replace(":", "-").replace("/", "-")
    safe_version = new_version.replace(":", "-").replace("/", "-")
    return f"std-alert/update-{ecosystem.lower()}-{safe_package}-{safe_version}"
