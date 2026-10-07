import re
import logging
import httpx
from typing import Dict, List, Optional
from app.scanners.base import BaseScanner
from app.models.schemas import DependencyInfo

logger = logging.getLogger(__name__)

class DockerScanner(BaseScanner):
    name = "docker_scanner"
    ecosystem = "docker"
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=10.0)

    async def parse_file(self, content: str) -> List[Dict]:
        deps = []
        for line in content.splitlines():
            line = line.strip()
            if line.upper().startswith("FROM "):
                parts = line.split()
                if len(parts) >= 2:
                    image_part = parts[1]
                    if ' as ' in line.lower():
                        image_part = line.split()[1] # simplistic approach
                        
                    if ':' in image_part:
                        image_name, version = image_part.split(':', 1)
                    else:
                        image_name, version = image_part, "latest"
                        
                    if version not in ['latest', 'scratch']:
                        deps.append({
                            "name": image_name,
                            "current_version": version
                        })
        return deps

    async def get_latest_version(self, package_name: str) -> Optional[str]:
        # Handle official images vs non-official
        image = package_name if '/' in package_name else f"library/{package_name}"
        url = f"https://hub.docker.com/v2/repositories/{image}/tags?page_size=10&ordering=last_updated"
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            data = response.json()
            results = data.get("results", [])
            for res in results:
                tag = res.get("name")
                # Avoid beta/rc/alpine tags for general "latest" version logic, simplified here
                if tag != "latest" and re.match(r'^\d+(\.\d+)*$', tag):
                    return tag
                    
            if results and results[0].get("name") != "latest":
                return results[0].get("name")
        except Exception as e:
            logger.error(f"Error fetching version for Docker image {package_name}: {e}")
            
        return None

    async def scan(self, repo_files: Dict[str, str]) -> List[DependencyInfo]:
        all_deps = []
        for file_path, content in repo_files.items():
            if file_path.endswith('Dockerfile') or file_path.endswith('docker-compose.yml'):
                logger.info(f"Scanning docker file: {file_path}")
                if file_path.endswith('Dockerfile'):
                    parsed_deps = await self.parse_file(content)
                else:
                    # simplistic extraction for compose
                    parsed_deps = []
                    for line in content.splitlines():
                        if "image:" in line:
                            val = line.split("image:")[-1].strip()
                            if ':' in val:
                                n, v = val.split(':', 1)
                                if v not in ['latest', 'scratch']:
                                    parsed_deps.append({"name": n, "current_version": v})
                                
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
