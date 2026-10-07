import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

class IssueManager:
    def __init__(self, github_client):
        self.github = github_client

    async def auto_label_issue(self, owner: str, repo: str, issue_number: int, title: str, body: str) -> list[str]:
        text = f"{title} {body}".lower()
        labels_to_add = set()

        keywords = {
            'bug': ['bug', 'error', 'crash', 'fix', 'broken', 'fail', 'not working'],
            'enhancement': ['feature', 'request', 'add', 'implement', 'enhance', 'new'],
            'question': ['question', 'how', 'help', 'why', 'what', 'explain'],
            'documentation': ['docs', 'documentation', 'readme', 'typo'],
            'security': ['security', 'vulnerability', 'cve', 'exploit'],
            'performance': ['performance', 'slow', 'memory', 'optimize'],
            'dependencies': ['dependency', 'update', 'upgrade', 'version']
        }

        for label, words in keywords.items():
            if any(word in text for word in words):
                labels_to_add.add(label)

        labels = list(labels_to_add)
        if labels:
            try:
                await self.github.request("POST", f"/repos/{owner}/{repo}/issues/{issue_number}/labels", json={"labels": labels})
                logger.info(f"Added labels {labels} to issue #{issue_number} in {owner}/{repo}")
            except Exception as e:
                logger.error(f"Failed to add labels to issue #{issue_number}: {e}")
        return labels

    async def check_duplicate(self, owner: str, repo: str, title: str) -> dict | None:
        try:
            issues = await self.github.request("GET", f"/repos/{owner}/{repo}/issues?state=open")
            
            title_words = set(title.lower().split())
            if not title_words:
                return None
                
            for issue in issues:
                if "pull_request" in issue:
                    continue
                issue_title_words = set(issue['title'].lower().split())
                if not issue_title_words:
                    continue
                
                intersection = len(title_words.intersection(issue_title_words))
                union = len(title_words.union(issue_title_words))
                similarity = intersection / union if union > 0 else 0
                
                if similarity > 0.7:
                    return issue
            return None
        except Exception as e:
            logger.error(f"Failed to check duplicate issues: {e}")
            return None

    async def close_stale_issues(self, owner: str, repo: str, stale_days: int = 60, warn_days: int = 45) -> dict:
        result = {"warned": 0, "closed": 0}
        try:
            issues = await self.github.request("GET", f"/repos/{owner}/{repo}/issues?state=open")
            now = datetime.now(timezone.utc)
            
            for issue in issues:
                updated_at = datetime.fromisoformat(issue['updated_at'].replace('Z', '+00:00'))
                days_inactive = (now - updated_at).days
                
                if days_inactive >= stale_days:
                    # Close issue
                    await self.github.request("PATCH", f"/repos/{owner}/{repo}/issues/{issue['number']}", json={"state": "closed"})
                    await self.github.request("POST", f"/repos/{owner}/{repo}/issues/{issue['number']}/comments", json={"body": "This issue has been closed due to inactivity."})
                    result["closed"] += 1
                elif days_inactive >= warn_days:
                    # Warn and label
                    labels = [l['name'] for l in issue.get('labels', [])]
                    if 'stale' not in labels:
                        await self.github.request("POST", f"/repos/{owner}/{repo}/issues/{issue['number']}/labels", json={"labels": ["stale"]})
                        await self.github.request("POST", f"/repos/{owner}/{repo}/issues/{issue['number']}/comments", json={"body": f"This issue has been inactive for {warn_days} days and will be closed in {stale_days - warn_days} days if no further activity occurs."})
                        result["warned"] += 1
            return result
        except Exception as e:
            logger.error(f"Failed to process stale issues: {e}")
            return result

    async def welcome_new_contributor(self, owner: str, repo: str, username: str, issue_or_pr_number: int, is_pr: bool = False):
        try:
            # Check if user has previous issues/PRs
            q = f"repo:{owner}/{repo} author:{username}"
            search_result = await self.github.request("GET", f"/search/issues?q={q}")
            
            if search_result.get("total_count", 0) <= 1: # 1 because the current one is already created
                item_type = "PR" if is_pr else "issue"
                message = f"👋 Welcome @{username}! Thanks for your first {item_type} to this project! \n     A maintainer will review it shortly. 🎉"
                await self.github.request("POST", f"/repos/{owner}/{repo}/issues/{issue_or_pr_number}/comments", json={"body": message})
        except Exception as e:
            logger.error(f"Failed to welcome new contributor {username}: {e}")

    async def add_size_label(self, owner: str, repo: str, pr_number: int) -> str:
        try:
            pr = await self.github.request("GET", f"/repos/{owner}/{repo}/pulls/{pr_number}")
            changes = pr.get("additions", 0) + pr.get("deletions", 0)
            
            if changes < 10:
                label = "size/XS"
            elif changes < 50:
                label = "size/S"
            elif changes < 200:
                label = "size/M"
            elif changes < 500:
                label = "size/L"
            else:
                label = "size/XL"
                
            await self.github.request("POST", f"/repos/{owner}/{repo}/issues/{pr_number}/labels", json={"labels": [label]})
            
            if label == "size/XL":
                message = "⚠️ This PR is quite large (XL). Consider splitting it into smaller, more manageable PRs if possible."
                await self.github.request("POST", f"/repos/{owner}/{repo}/issues/{pr_number}/comments", json={"body": message})
                
            return label
        except Exception as e:
            logger.error(f"Failed to add size label to PR #{pr_number}: {e}")
            return ""
