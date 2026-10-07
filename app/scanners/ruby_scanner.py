import logging
import re
from typing import List, Optional
import httpx

from app.scanners.base import BaseScanner
from app.models.schemas import DependencyInfo

logger = logging.getLogger(__name__)

class RubyScanner(BaseScanner):
    """Scanner for Ruby Bundler dependencies."""
    
    ecosystem = 'rubygems'

    async def parse_file(self, content: str, file_path: str) -> List[DependencyInfo]:
        """Parse Gemfile file format to extract dependencies."""
        dependencies = []
        if not (file_path.endswith("Gemfile") or file_path.endswith(".gemspec")):
            return dependencies

        # Match gem 'name', 'version' or gem "name", "~> version"
        pattern = re.compile(r'^\s*gem\s+[\'"]([^\'"]+)[\'"]\s*(?:,\s*[\'"]([^\'"]+)[\'"])?', re.MULTILINE)
        for match in pattern.finditer(content):
            name, version_str = match.groups()
            # If no version specified, we don't have a current version to report
            if version_str:
                dependencies.append(DependencyInfo(
                    name=name,
                    current_version=version_str,
                    ecosystem=self.ecosystem,
                    file_path=file_path
                ))
        return dependencies

    async def get_latest_version(self, name: str) -> Optional[str]:
        """Query rubygems.org for the latest version."""
        url = f"https://rubygems.org/api/v1/gems/{name}.json"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    return data.get("version")
                logger.warning(f"Failed to fetch {name} from rubygems.org. HTTP {response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"Network error querying rubygems.org for {name}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error getting latest version for {name}: {e}")
        return None

    async def scan(self, repo_files: List[str]) -> List[str]:
        """Find Gemfile and .gemspec files in the repository."""
        return [f for f in repo_files if f.endswith("Gemfile") or f.endswith(".gemspec")]
