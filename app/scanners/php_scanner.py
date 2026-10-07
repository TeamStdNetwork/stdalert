import logging
import json
from typing import List, Optional
import httpx

from app.scanners.base import BaseScanner
from app.models.schemas import DependencyInfo

logger = logging.getLogger(__name__)

class PHPScanner(BaseScanner):
    """Scanner for PHP Composer dependencies."""
    
    ecosystem = 'packagist'

    async def parse_file(self, content: str, file_path: str) -> List[DependencyInfo]:
        """Parse composer.json file format to extract dependencies."""
        dependencies = []
        if not file_path.endswith("composer.json"):
            return dependencies

        try:
            data = json.loads(content)
            reqs = {**data.get('require', {}), **data.get('require-dev', {})}
            for name, version in reqs.items():
                if name == "php" or name.startswith("ext-"):
                    continue
                dependencies.append(DependencyInfo(
                    name=name,
                    current_version=version,
                    ecosystem=self.ecosystem,
                    file_path=file_path
                ))
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse composer.json at {file_path}: {e}")

        return dependencies

    async def get_latest_version(self, name: str) -> Optional[str]:
        """Query packagist.org for the latest version."""
        url = f"https://repo.packagist.org/p2/{name}.json"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    packages = data.get("packages", {}).get(name, [])
                    for pkg in packages:
                        version = pkg.get("version")
                        # Skip dev versions or RCs if possible in a real implementation
                        if version and "-dev" not in version:
                            return version
                logger.warning(f"Failed to fetch {name} from packagist. HTTP {response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"Network error querying packagist for {name}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error getting latest version for {name}: {e}")
        return None

    async def scan(self, repo_files: List[str]) -> List[str]:
        """Find composer.json files in the repository."""
        return [f for f in repo_files if f.endswith("composer.json")]
