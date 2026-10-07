import re
import logging
from typing import Dict, List, Optional
import httpx
from cachetools import TTLCache
from app.scanners.base import BaseScanner
from app.models.schemas import DependencyInfo

logger = logging.getLogger(__name__)

class PipScanner(BaseScanner):
    name = "pip_scanner"
    ecosystem = "pip"
    
    def __init__(self):
        self.version_cache = TTLCache(maxsize=1000, ttl=3600)  # Cache for 1 hour
        self.client = httpx.AsyncClient(timeout=10.0)

    async def parse_file(self, content: str) -> List[Dict]:
        """Parse requirements.txt format."""
        deps = []
        for line in content.splitlines():
            line = line.strip()
            # Handle comments and empty lines
            if not line or line.startswith('#'):
                continue
            
            # Handle -r includes (simplistic approach, as we don't have file resolution here)
            if line.startswith('-r'):
                continue
                
            # Basic parsing of requirement line (handles ==, >=, ~=)
            match = re.match(r'^([a-zA-Z0-9_\-\.]+)(?:([=><~]=?)(.*))?', line.split()[0])
            if match:
                package_name = match.group(1)
                operator = match.group(2)
                version = match.group(3)
                
                # Try to clean up version
                if version:
                    version = version.split(';')[0].strip() # Remove environment markers
                    
                deps.append({
                    "name": package_name,
                    "current_version": version if version else "unknown",
                    "operator": operator if operator else ""
                })
        return deps

    async def get_latest_version(self, package_name: str) -> Optional[str]:
        """Query PyPI for the latest version."""
        if package_name in self.version_cache:
            return self.version_cache[package_name]
            
        url = f"https://pypi.org/pypi/{package_name}/json"
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            data = response.json()
            latest_version = data.get("info", {}).get("version")
            if latest_version:
                self.version_cache[package_name] = latest_version
                return latest_version
        except httpx.RequestError as e:
            logger.error(f"Network error while fetching version for {package_name}: {e}")
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code} while fetching version for {package_name}")
        except Exception as e:
            logger.error(f"Unexpected error fetching version for {package_name}: {e}")
            
        return None

    async def scan(self, repo_files: Dict[str, str]) -> List[DependencyInfo]:
        """Find and parse Python dependency files."""
        all_deps = []
        
        # Simplified scanning logic for demonstration
        for file_path, content in repo_files.items():
            if 'requirements.txt' in file_path or 'requirements/' in file_path:
                logger.info(f"Scanning requirements file: {file_path}")
                parsed_deps = await self.parse_file(content)
                for dep in parsed_deps:
                    latest = await self.get_latest_version(dep['name'])
                    update_type = self.compare_versions(dep['current_version'], latest) if latest and dep['current_version'] != 'unknown' else 'none'
                    
                    info = DependencyInfo(
                        name=dep['name'],
                        ecosystem=self.ecosystem,
                        current_version=dep['current_version'],
                        latest_version=latest,
                        file_path=file_path,
                        update_type=update_type
                    )
                    all_deps.append(info)
                    
            elif file_path.endswith('setup.py'):
                # Very basic setup.py parsing
                logger.info(f"Scanning setup.py: {file_path}")
                match = re.search(r'install_requires\s*=\s*\[(.*?)\]', content, re.DOTALL)
                if match:
                    reqs_str = match.group(1).replace("'", "").replace('"', "").replace(",", "\n")
                    parsed_deps = await self.parse_file(reqs_str)
                    for dep in parsed_deps:
                        latest = await self.get_latest_version(dep['name'])
                        info = DependencyInfo(
                            name=dep['name'],
                            ecosystem=self.ecosystem,
                            current_version=dep['current_version'],
                            latest_version=latest,
                            file_path=file_path,
                            update_type="unknown" # Simplified
                        )
                        all_deps.append(info)
            
            elif file_path.endswith('pyproject.toml'):
                # Skipping real TOML parsing for simplicity, fallback to regex or simple lines
                pass 
                
        return all_deps
