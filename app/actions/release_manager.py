import logging
import re

logger = logging.getLogger(__name__)

class ReleaseManager:
    def __init__(self, github_client):
        self.github = github_client

    async def generate_changelog(self, owner: str, repo: str, from_tag: str | None = None, to_ref: str = 'HEAD') -> str:
        try:
            if from_tag:
                commits_data = await self.github.request("GET", f"/repos/{owner}/{repo}/compare/{from_tag}...{to_ref}")
                commits = commits_data.get("commits", [])
            else:
                commits = await self.github.request("GET", f"/repos/{owner}/{repo}/commits?sha={to_ref}")

            categories = {
                'feat': ('✨ Features', []),
                'fix': ('🐛 Bug Fixes', []),
                'docs': ('📝 Documentation', []),
                'chore': ('🔧 Maintenance', []),
                'perf': ('⚡ Performance', []),
                'refactor': ('♻️ Refactors', []),
                'test': ('✅ Tests', []),
                'ci': ('👷 CI/CD', []),
                'breaking': ('⚠️ Breaking Changes', [])
            }

            for commit_data in commits:
                msg = commit_data['commit']['message'].split('\n')[0]
                author = commit_data['author']['login'] if commit_data.get('author') else 'Unknown'
                sha = commit_data['sha'][:7]
                
                entry = f"- {msg} ({sha}) by @{author}"
                
                if 'BREAKING CHANGE' in commit_data['commit']['message']:
                    categories['breaking'][1].append(entry)
                
                match = re.match(r'^(\w+)(\(.*\))?!?:.*', msg)
                if match:
                    type_prefix = match.group(1).lower()
                    if type_prefix in categories:
                        categories[type_prefix][1].append(entry)
                    else:
                        categories['chore'][1].append(entry)
                else:
                    categories['chore'][1].append(entry)

            changelog = "## Changelog\n\n"
            for _, (title, entries) in categories.items():
                if entries:
                    changelog += f"### {title}\n"
                    changelog += "\n".join(entries) + "\n\n"
            
            return changelog.strip()
        except Exception as e:
            logger.error(f"Failed to generate changelog: {e}")
            return "## Changelog\n\nFailed to generate changelog."

    async def suggest_version(self, owner: str, repo: str, from_tag: str | None = None) -> str:
        try:
            if from_tag:
                commits_data = await self.github.request("GET", f"/repos/{owner}/{repo}/compare/{from_tag}...HEAD")
                commits = commits_data.get("commits", [])
            else:
                commits = await self.github.request("GET", f"/repos/{owner}/{repo}/commits")

            has_breaking = False
            has_feat = False

            for commit_data in commits:
                msg = commit_data['commit']['message']
                if 'BREAKING CHANGE' in msg or re.match(r'^.*!:', msg.split('\n')[0]):
                    has_breaking = True
                    break
                if re.match(r'^feat(\(.*\))?:', msg.split('\n')[0]):
                    has_feat = True

            current_version = "0.0.0"
            if from_tag and from_tag.startswith('v'):
                current_version = from_tag[1:]
            
            try:
                major, minor, patch = map(int, current_version.split('.'))
            except ValueError:
                major, minor, patch = 0, 0, 0

            if has_breaking:
                major += 1
                minor = 0
                patch = 0
            elif has_feat:
                minor += 1
                patch = 0
            else:
                patch += 1

            return f"v{major}.{minor}.{patch}"
        except Exception as e:
            logger.error(f"Failed to suggest version: {e}")
            return "v0.1.0"

    async def create_release(self, owner: str, repo: str, tag: str, changelog: str, draft: bool = True) -> dict:
        try:
            release_data = {
                "tag_name": tag,
                "name": f"Release {tag}",
                "body": changelog,
                "draft": draft,
                "prerelease": False
            }
            release = await self.github.request("POST", f"/repos/{owner}/{repo}/releases", json=release_data)
            logger.info(f"Created release {tag} for {owner}/{repo}")
            return release
        except Exception as e:
            logger.error(f"Failed to create release {tag}: {e}")
            return {}
