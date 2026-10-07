import logging
import re
from typing import List, Optional
import httpx

from app.scanners.base import BaseScanner
from app.models.schemas import DependencyInfo

logger = logging.getLogger(__name__)

class GoScanner(BaseScanner):
    """Scanner for Go modules."""
    
    ecosystem = 'go'

    async def parse_file(self, content: str, file_path: str) -> List[DependencyInfo]:
        """Parse go.mod file format to extract dependencies."""
        dependencies = []
        if not file_path.endswith("go.mod"):
            return dependencies

        # Match single line require: require example.com/pkg v1.2.3 [// indirect]
        single_req_pattern = re.compile(r"^require\s+([^\s]+)\s+([^\s]+)(?:\s+// indirect)?", re.MULTILINE)
        for match in single_req_pattern.finditer(content):
            name, version = match.groups()
            dependencies.append(DependencyInfo(
                name=name,
                current_version=version,
                ecosystem=self.ecosystem,
                file_path=file_path
            ))

        # Match block require: require ( \n pkg v1.2.3 \n )
        block_req_pattern = re.compile(r"^require\s+\((.*?)\)", re.DOTALL | re.MULTILINE)
        for block_match in block_req_pattern.finditer(content):
            block_content = block_match.group(1)
            line_pattern = re.compile(r"^\s+([^\s]+)\s+([^\s]+)(?:\s+// indirect)?", re.MULTILINE)
            for match in line_pattern.finditer(block_content):
                name, version = match.groups()
                dependencies.append(DependencyInfo(
                    name=name,
                    current_version=version,
                    ecosystem=self.ecosystem,
                    file_path=file_path
                ))
        return dependencies

    async def get_latest_version(self, name: str) -> Optional[str]:
        """Query proxy.golang.org for the latest version."""
        url = f"https://proxy.golang.org/{name}/@latest"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    return data.get("Version")
                logger.warning(f"Failed to fetch {name} from Go proxy. HTTP {response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"Network error querying Go proxy for {name}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error getting latest version for {name}: {e}")
        return None

    async def scan(self, repo_files: List[str]) -> List[str]:
        """Find go.mod files in the repository."""
        return [f for f in repo_files if f.endswith("go.mod")]
