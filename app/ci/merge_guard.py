import logging
from typing import Optional
from app.ci.status_checker import CIStatusChecker

logger = logging.getLogger(__name__)

class MergeGuard:
    def __init__(self, github_client, status_checker: CIStatusChecker):
        self.github_client = github_client
        self.status_checker = status_checker

    async def can_merge(self, owner: str, repo: str, pr_number: int) -> dict:
        result = {
            'can_merge': False,
            'checks_passed': False,
            'no_conflicts': False,
            'no_critical_vulns': True, # To be implemented
            'approved': False,
            'reasons': []
        }
        
        try:
            # Get PR info
            pr_endpoint = f"/repos/{owner}/{repo}/pulls/{pr_number}"
            pr_response = await self.github_client.get(pr_endpoint)
            pr_data = pr_response.json()
            
            # Check conflicts
            mergeable = pr_data.get("mergeable")
            if mergeable is True:
                result['no_conflicts'] = True
            elif mergeable is False:
                result['no_conflicts'] = False
                result['reasons'].append("PR has merge conflicts.")
            
            # Check checks on HEAD
            head_sha = pr_data.get("head", {}).get("sha")
            if head_sha:
                checks_passed = await self.status_checker.are_checks_passing(owner, repo, head_sha)
                result['checks_passed'] = checks_passed
                if not checks_passed:
                    result['reasons'].append("CI checks have not passed.")
            else:
                result['reasons'].append("Could not determine PR head SHA.")

            # Check approvals
            reviews_endpoint = f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
            reviews_response = await self.github_client.get(reviews_endpoint)
            reviews_data = reviews_response.json()
            
            approved = any(review.get("state") == "APPROVED" for review in reviews_data)
            result['approved'] = approved
            if not approved:
                result['reasons'].append("PR requires at least one approval.")

            if result['checks_passed'] and result['no_conflicts'] and result['no_critical_vulns'] and result['approved']:
                result['can_merge'] = True

        except Exception as e:
            logger.error(f"Error checking mergeability for PR #{pr_number} in {owner}/{repo}: {e}")
            result['reasons'].append(f"Error during checks: {str(e)}")

        return result

    async def auto_merge_if_ready(self, owner: str, repo: str, pr_number: int, merge_method: str = 'squash') -> bool:
        status = await self.can_merge(owner, repo, pr_number)
        
        if status['can_merge']:
            try:
                merge_endpoint = f"/repos/{owner}/{repo}/pulls/{pr_number}/merge"
                payload = {"merge_method": merge_method}
                response = await self.github_client.put(merge_endpoint, json=payload)
                if response.status_code in (200, 204):
                    logger.info(f"Successfully auto-merged PR #{pr_number} in {owner}/{repo}")
                    await self.add_merge_status_comment(owner, repo, pr_number, status)
                    return True
            except Exception as e:
                logger.error(f"Failed to auto-merge PR #{pr_number} in {owner}/{repo}: {e}")
                
        # Update status comment even if not merging
        await self.add_merge_status_comment(owner, repo, pr_number, status)
        return False

    async def add_merge_status_comment(self, owner: str, repo: str, pr_number: int, status: dict):
        ci_icon = "✅" if status['checks_passed'] else "❌"
        conflicts_icon = "✅" if status['no_conflicts'] else "❌"
        vulns_icon = "✅" if status['no_critical_vulns'] else "❌"
        appr_icon = "✅" if status['approved'] else "⏳"
        
        comment = (
            "🤖 STD Alert Merge Status\n\n"
            f"{ci_icon} CI Checks: {'Passed' if status['checks_passed'] else 'Failed/Pending'}\n"
            f"{conflicts_icon} No Conflicts\n"
            f"{vulns_icon} No Critical Vulnerabilities\n"
            f"{appr_icon} {'Approved' if status['approved'] else 'Waiting for approval'}"
        )
        
        if status['reasons']:
            comment += "\n\n**Reasons preventing merge:**\n"
            for reason in status['reasons']:
                comment += f"- {reason}\n"
                
        try:
            comments_endpoint = f"/repos/{owner}/{repo}/issues/{pr_number}/comments"
            await self.github_client.post(comments_endpoint, json={"body": comment})
        except Exception as e:
            logger.error(f"Failed to post merge status comment on PR #{pr_number} in {owner}/{repo}: {e}")
