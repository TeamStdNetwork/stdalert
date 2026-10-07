import json
import logging
import httpx
from typing import Dict, List, Optional
from app.scanners.base import BaseScanner
from app.models.schemas import DependencyInfo

logger = logging.getLogger(__name__)

class NpmScanner(BaseScanner):
    name = "npm_scanner"
    ecosystem = "npm"
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=10.0)

    async def parse_file(self, content: str) -> List[Dict]:
        deps = []
        try:
            data = json.loads(content)
            dependencies = data.get("dependencies", {})
            dev_dependencies = data.get("devDependencies", {})
            
            all_deps = {**dependencies, **dev_dependencies}
            for name, version in all_deps.items():
                deps.append({
                    "name": name,
                    "current_version": version.replace('^', '').replace('~', '').replace('>=', '')
                })
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing package.json: {e}")
            
        return deps

    async def get_latest_version(self, package_name: str) -> Optional[str]:
        url = f"https://registry.npmjs.org/{package_name}/latest"
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            data = response.json()
            return data.get("version")
        except Exception as e:
            logger.error(f"Error fetching version for NPM package {package_name}: {e}")
            return None

    async def scan(self, repo_files: Dict[str, str]) -> List[DependencyInfo]:
        all_deps = []
        for file_path, content in repo_files.items():
            if file_path.endswith('package.json'):
                logger.info(f"Scanning package.json: {file_path}")
                parsed_deps = await self.parse_file(content)
                for dep in parsed_deps:
                    latest = await self.get_latest_version(dep['name'])
                    update_type = self.compare_versions(dep['current_version'], latest) if latest else 'none'
                    
                    info = DependencyInfo(
                        name=dep['name'],
                        ecosystem=self.ecosystem,
                        current_version=dep['current_version'],
                        latest_version=latest,
                        file_path=file_path,
                        update_type=update_type
                    )
                    all_deps.append(info)
        return all_deps
