import logging
import re
from typing import List, Optional
import httpx

from app.scanners.base import BaseScanner
from app.models.schemas import DependencyInfo

logger = logging.getLogger(__name__)

class RustScanner(BaseScanner):
    """Scanner for Rust Cargo dependencies."""
    
    ecosystem = 'cargo'

    async def parse_file(self, content: str, file_path: str) -> List[DependencyInfo]:
        """Parse Cargo.toml file format to extract dependencies."""
        dependencies = []
        if not file_path.endswith("Cargo.toml"):
            return dependencies

        # Match package = "version"
        simple_pattern = re.compile(r'^([a-zA-Z0-9_-]+)\s*=\s*"([^"]+)"', re.MULTILINE)
        for match in simple_pattern.finditer(content):
            name, version = match.groups()
            dependencies.append(DependencyInfo(
                name=name,
                current_version=version,
                ecosystem=self.ecosystem,
                file_path=file_path
            ))
            
        # Match package = { version = "version", ... }
        inline_pattern = re.compile(r'^([a-zA-Z0-9_-]+)\s*=\s*\{[^}]*version\s*=\s*"([^"]+)"[^}]*\}', re.MULTILINE)
        for match in inline_pattern.finditer(content):
            name, version = match.groups()
            dependencies.append(DependencyInfo(
                name=name,
                current_version=version,
                ecosystem=self.ecosystem,
                file_path=file_path
            ))
            
        return dependencies

    async def get_latest_version(self, name: str) -> Optional[str]:
        """Query crates.io for the latest version."""
        url = f"https://crates.io/api/v1/crates/{name}"
        headers = {"User-Agent": "STDAlertBot (https://github.com/stdalert/bot)"}
        try:
            async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    crate = data.get("crate", {})
                    return crate.get("max_version")
                logger.warning(f"Failed to fetch {name} from crates.io. HTTP {response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"Network error querying crates.io for {name}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error getting latest version for {name}: {e}")
        return None

    async def scan(self, repo_files: List[str]) -> List[str]:
        """Find Cargo.toml files in the repository."""
        return [f for f in repo_files if f.endswith("Cargo.toml")]
