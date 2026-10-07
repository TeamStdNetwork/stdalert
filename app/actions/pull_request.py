import logging
from typing import Optional, List, Dict, Any

from app.models.schemas import ScanResult, DependencyInfo, VulnerabilityInfo
from app.github.api import GitHubClient

logger = logging.getLogger(__name__)

class PRCreator:
    """
    Creates pull requests for dependency updates and security patches.
    """

    def __init__(self, github_client: GitHubClient):
        self.github = github_client

    async def create_update_pr(
        self,
        owner: str,
        repo: str,
        scan_result: ScanResult,
        dependency: DependencyInfo,
        vulnerability: Optional[VulnerabilityInfo] = None
    ) -> Dict[str, Any]:
        """
        Creates a professional PR for a single dependency update.
        """
        ecosystem = dependency.ecosystem.lower()
        package = dependency.name
        new_version = dependency.new_version
        old_version = dependency.current_version
        
        branch_name = f"std-alert/update-{ecosystem}-{package}-{new_version}"
        title = f"chore(deps): update {package} from {old_version} to {new_version}"
        body = self._generate_pr_body(dependency, vulnerability)
        
        logger.info(f"Creating PR for {owner}/{repo}: {title}")
        
        # Depending on GitHubClient implementation, it typically expects a dict with these params
        pr_data = await self.github.create_pull_request(
            owner=owner,
            repo=repo,
            title=title,
            body=body,
            head=branch_name,
            base="main"  # This could be configurable or fetched dynamically
        )
        return pr_data

    async def create_grouped_pr(
        self,
        owner: str,
        repo: str,
        scan_result: ScanResult,
        dependencies: List[DependencyInfo]
    ) -> Dict[str, Any]:
        """
        Groups related updates into one PR.
        """
        import datetime
        date_str = datetime.datetime.utcnow().strftime("%Y-%m-%d")
        ecosystems = list(set(d.ecosystem.lower() for d in dependencies))
        eco_prefix = ecosystems[0] if len(ecosystems) == 1 else "mixed"
        
        branch_name = f"std-alert/update-{eco_prefix}-{date_str}"
        title = f"chore(deps): group update for {len(dependencies)} packages ({eco_prefix})"
        body = self._generate_grouped_pr_body(dependencies)
        
        logger.info(f"Creating Grouped PR for {owner}/{repo}: {title}")
        
        pr_data = await self.github.create_pull_request(
            owner=owner,
            repo=repo,
            title=title,
            body=body,
            head=branch_name,
            base="main"
        )
        return pr_data

    def _generate_pr_body(self, dependency: DependencyInfo, vulnerability: Optional[VulnerabilityInfo]) -> str:
        """Build the markdown body for a single dependency update PR."""
        update_type = self._determine_update_type(dependency.current_version, dependency.new_version)
        badge_color = {"patch": "success", "minor": "yellow", "major": "critical"}.get(update_type, "blue")
        
        body = f"""## 🔄 Dependency Update
This pull request updates **{dependency.name}** from version `{dependency.current_version}` to `{dependency.new_version}`.

| Package | Ecosystem | Old Version | New Version | Update Type |
|---|---|---|---|---|
| `{dependency.name}` | {dependency.ecosystem} | `{dependency.current_version}` | `{dependency.new_version}` | ![{update_type}](https://img.shields.io/badge/update-{update_type}-{badge_color}) |

"""
        if vulnerability:
            body += f"""### 🔐 Security Vulnerability Fixed
* **Severity**: {vulnerability.severity.upper()}
* **CVE**: {vulnerability.cve_id or 'N/A'}
* **Description**: {vulnerability.description}

"""

        body += """### 📋 What Changed
*Please review the changelog and release notes for this package on its respective registry or GitHub repository.*

"""
        
        if update_type == "major":
            body += """### ⚠️ Breaking Changes Warning
This is a **MAJOR** update. Please review the release notes carefully as it likely contains breaking changes. Ensure your test suite passes before merging.

"""

        body += """---
🤖 *This PR was automatically created by STD Alert.*
"""
        return body

    def _generate_grouped_pr_body(self, dependencies: List[DependencyInfo], vulnerabilities: Optional[List[VulnerabilityInfo]] = None) -> str:
        """Build the markdown body for a grouped dependency update PR."""
        body = f"## 🔄 Grouped Dependency Update\n\nThis pull request updates **{len(dependencies)}** packages.\n\n"
        
        body += "| Package | Ecosystem | Old Version | New Version | Update Type |\n|---|---|---|---|---|\n"
        for dep in dependencies:
            u_type = self._determine_update_type(dep.current_version, dep.new_version)
            color = {"patch": "success", "minor": "yellow", "major": "critical"}.get(u_type, "blue")
            body += f"| `{dep.name}` | {dep.ecosystem} | `{dep.current_version}` | `{dep.new_version}` | ![{u_type}](https://img.shields.io/badge/update-{u_type}-{color}) |\n"
            
        body += "\n---\n🤖 *This PR was automatically created by STD Alert.*\n"
        return body

    def _determine_update_type(self, old: str, new: str) -> str:
        """Basic semver comparison to determine update type (major, minor, patch)."""
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
