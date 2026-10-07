import base64
import logging
from typing import Optional, List, Dict, Any
import httpx

logger = logging.getLogger(__name__)

class GitHubClient:
    """Client for interacting with the GitHub API."""
    
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        self.client = httpx.AsyncClient(base_url=self.base_url, headers=self.headers)
        
    async def _request(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        logger.debug(f"GitHub API {method} {endpoint}")
        response = await self.client.request(method, endpoint, **kwargs)
        
        # Simple rate limit logging
        remaining = response.headers.get("X-RateLimit-Remaining")
        if remaining is not None and int(remaining) < 100:
            logger.warning(f"GitHub API rate limit remaining: {remaining}")
            
        return response

    async def get_repo_info(self, owner: str, repo: str) -> Dict[str, Any]:
        """Get repository information."""
        resp = await self._request("GET", f"/repos/{owner}/{repo}")
        resp.raise_for_status()
        return resp.json()

    async def get_file_content(self, owner: str, repo: str, path: str, ref: Optional[str] = None) -> Optional[str]:
        """Get decoded file content."""
        params = {}
        if ref:
            params["ref"] = ref
            
        resp = await self._request("GET", f"/repos/{owner}/{repo}/contents/{path}", params=params)
        
        if resp.status_code == 404:
            return None
            
        resp.raise_for_status()
        data = resp.json()
        
        if data.get("type") == "file" and data.get("encoding") == "base64":
            return base64.b64decode(data["content"]).decode("utf-8")
        return None

    async def list_repo_files(self, owner: str, repo: str, path: str = '', ref: Optional[str] = None) -> List[str]:
        """List files in a repository directory recursively if needed (using tree API or simple content if shallow)."""
        params = {}
        if ref:
            params["ref"] = ref
            
        resp = await self._request("GET", f"/repos/{owner}/{repo}/contents/{path}", params=params)
        if resp.status_code == 404:
            return []
            
        resp.raise_for_status()
        data = resp.json()
        
        if isinstance(data, list):
            return [item["path"] for item in data if item["type"] == "file"]
        return []

    async def get_dependency_files(self, owner: str, repo: str) -> Dict[str, str]:
        """Search for and fetch dependency files."""
        # Simple approach: Check common locations
        common_files = [
            "requirements.txt",
            "setup.py",
            "pyproject.toml",
            "package.json",
            "Dockerfile",
            "docker-compose.yml"
        ]
        
        files_found = {}
        for file_path in common_files:
            content = await self.get_file_content(owner, repo, file_path)
            if content is not None:
                files_found[file_path] = content
                
        # Handle requirements/*.txt
        req_dir_files = await self.list_repo_files(owner, repo, "requirements")
        for req_file in req_dir_files:
            if req_file.endswith(".txt"):
                content = await self.get_file_content(owner, repo, req_file)
                if content is not None:
                    files_found[req_file] = content
                    
        return files_found

    async def create_branch(self, owner: str, repo: str, branch_name: str, from_branch: Optional[str] = None) -> bool:
        """Create a new branch."""
        # Get base branch SHA
        if from_branch is None:
            repo_info = await self.get_repo_info(owner, repo)
            from_branch = repo_info["default_branch"]
            
        ref_resp = await self._request("GET", f"/repos/{owner}/{repo}/git/ref/heads/{from_branch}")
        ref_resp.raise_for_status()
        sha = ref_resp.json()["object"]["sha"]
        
        # Create new ref
        try:
            create_resp = await self._request(
                "POST", 
                f"/repos/{owner}/{repo}/git/refs",
                json={
                    "ref": f"refs/heads/{branch_name}",
                    "sha": sha
                }
            )
            create_resp.raise_for_status()
            return True
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 422: # Reference already exists
                logger.info(f"Branch {branch_name} already exists.")
                return False
            raise

    async def update_file(self, owner: str, repo: str, path: str, content: str, message: str, branch: str, sha: Optional[str] = None) -> Dict[str, Any]:
        """Update or create a file in a branch."""
        if sha is None:
            # Try to get current file SHA
            resp = await self._request("GET", f"/repos/{owner}/{repo}/contents/{path}", params={"ref": branch})
            if resp.status_code == 200:
                sha = resp.json().get("sha")
                
        payload = {
            "message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
            "branch": branch
        }
        if sha:
            payload["sha"] = sha
            
        resp = await self._request("PUT", f"/repos/{owner}/{repo}/contents/{path}", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def create_pull_request(self, owner: str, repo: str, title: str, body: str, head: str, base: str) -> Dict[str, Any]:
        """Create a pull request."""
        payload = {
            "title": title,
            "body": body,
            "head": head,
            "base": base
        }
        resp = await self._request("POST", f"/repos/{owner}/{repo}/pulls", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def add_labels(self, owner: str, repo: str, pr_number: int, labels: List[str]):
        """Add labels to a PR/Issue."""
        resp = await self._request("POST", f"/repos/{owner}/{repo}/issues/{pr_number}/labels", json={"labels": labels})
        resp.raise_for_status()

    async def enable_auto_merge(self, owner: str, repo: str, pr_number: int) -> bool:
        """Enable auto-merge for a PR using GraphQL API."""
        # Using REST API workaround or directly if available (GraphQL is preferred for this, but REST works via passing node_id)
        # Assuming repo has auto-merge enabled. We will need the node_id of the PR.
        pr_resp = await self._request("GET", f"/repos/{owner}/{repo}/pulls/{pr_number}")
        pr_resp.raise_for_status()
        node_id = pr_resp.json()["node_id"]
        
        query = """
        mutation EnableAutoMerge($pullRequestId: ID!) {
          enablePullRequestAutoMerge(input: {pullRequestId: $pullRequestId}) {
            pullRequest {
              autoMergeRequest {
                enabledAt
              }
            }
          }
        }
        """
        variables = {"pullRequestId": node_id}
        
        resp = await self.client.post("/graphql", json={"query": query, "variables": variables})
        if resp.status_code == 200 and "errors" not in resp.json():
            return True
        logger.error(f"Failed to enable auto-merge: {resp.text}")
        return False

    async def get_open_prs(self, owner: str, repo: str, head_prefix: str = 'std-alert/') -> List[Dict[str, Any]]:
        """Get open PRs that match the head prefix."""
        resp = await self._request("GET", f"/repos/{owner}/{repo}/pulls", params={"state": "open"})
        resp.raise_for_status()
        
        prs = resp.json()
        return [pr for pr in prs if pr["head"]["ref"].startswith(head_prefix)]

    async def close_pr(self, owner: str, repo: str, pr_number: int):
        """Close a pull request."""
        resp = await self._request("PATCH", f"/repos/{owner}/{repo}/pulls/{pr_number}", json={"state": "closed"})
        resp.raise_for_status()

    async def add_comment(self, owner: str, repo: str, issue_number: int, body: str):
        """Add a comment to a PR or issue."""
        resp = await self._request("POST", f"/repos/{owner}/{repo}/issues/{issue_number}/comments", json={"body": body})
        resp.raise_for_status()

    async def close(self):
        """Close the underlying client."""
        await self.client.aclose()
