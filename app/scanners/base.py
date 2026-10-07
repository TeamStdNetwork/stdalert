import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, List
from packaging.version import Version, InvalidVersion
from app.models.schemas import DependencyInfo

logger = logging.getLogger(__name__)

class BaseScanner(ABC):
    name: str
    ecosystem: str

    @abstractmethod
    async def parse_file(self, content: str) -> List[Dict]:
        """Parse dependency file content."""
        pass

    @abstractmethod
    async def get_latest_version(self, package_name: str) -> Optional[str]:
        """Get the latest version of a package."""
        pass

    @abstractmethod
    async def scan(self, repo_files: Dict[str, str]) -> List[DependencyInfo]:
        """Full scan of repository files."""
        pass

    def compare_versions(self, current: str, latest: str) -> str:
        """
        Compare current and latest versions.
        Returns 'major', 'minor', 'patch', or 'none'.
        """
        try:
            curr_v = Version(current)
            latest_v = Version(latest)
        except InvalidVersion:
            logger.warning(f"Invalid version format: current='{current}', latest='{latest}'")
            return "none"

        if curr_v.major < latest_v.major:
            return "major"
        elif curr_v.minor < latest_v.minor:
            return "minor"
        elif curr_v.micro < latest_v.micro:
            return "patch"
        
        return "none"
