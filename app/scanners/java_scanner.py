import logging
import re
import xml.etree.ElementTree as ET
from typing import List, Optional
import httpx

from app.scanners.base import BaseScanner
from app.models.schemas import DependencyInfo

logger = logging.getLogger(__name__)

class JavaScanner(BaseScanner):
    """Scanner for Java Maven and Gradle dependencies."""
    
    ecosystem = 'maven'

    async def parse_file(self, content: str, file_path: str) -> List[DependencyInfo]:
        """Parse pom.xml and build.gradle file format to extract dependencies."""
        dependencies = []
        
        if file_path.endswith("pom.xml"):
            try:
                root = ET.fromstring(content)
                # Note: This is simplified. Proper parsing needs namespace handling.
                # Remove namespaces for easier querying
                xml_str = re.sub(r'\sxmlns="[^"]+"', '', content, count=1)
                root = ET.fromstring(xml_str)
                
                properties = {}
                props_elem = root.find("properties")
                if props_elem is not None:
                    for prop in props_elem:
                        properties[prop.tag] = prop.text

                for dep in root.findall(".//dependency"):
                    group_id_elem = dep.find("groupId")
                    artifact_id_elem = dep.find("artifactId")
                    version_elem = dep.find("version")
                    
                    if group_id_elem is not None and artifact_id_elem is not None and version_elem is not None:
                        group_id = group_id_elem.text
                        artifact_id = artifact_id_elem.text
                        version = version_elem.text
                        
                        # Resolve property like ${spring.version}
                        if version and version.startswith("${") and version.endswith("}"):
                            prop_name = version[2:-1]
                            version = properties.get(prop_name, version)
                            
                        name = f"{group_id}:{artifact_id}"
                        dependencies.append(DependencyInfo(
                            name=name,
                            current_version=version,
                            ecosystem=self.ecosystem,
                            file_path=file_path
                        ))
            except ET.ParseError as e:
                logger.error(f"Failed to parse pom.xml at {file_path}: {e}")
                
        elif file_path.endswith("build.gradle"):
            # Match implementation 'group:artifact:version' or implementation("group:artifact:version")
            pattern = re.compile(r'(?:implementation|api|compileOnly|runtimeOnly|testImplementation)\s+[\'"]([^\'"]+):([^\'"]+):([^\'"]+)[\'"]')
            for match in pattern.finditer(content):
                group, artifact, version = match.groups()
                name = f"{group}:{artifact}"
                dependencies.append(DependencyInfo(
                    name=name,
                    current_version=version,
                    ecosystem=self.ecosystem,
                    file_path=file_path
                ))
                
        return dependencies

    async def get_latest_version(self, name: str) -> Optional[str]:
        """Query Maven Central for the latest version."""
        try:
            group_id, artifact_id = name.split(":")
        except ValueError:
            logger.error(f"Invalid dependency name format for Java: {name}")
            return None
            
        url = f"https://search.maven.org/solrsearch/select?q=g:{group_id}+AND+a:{artifact_id}&rows=1&wt=json"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    docs = data.get("response", {}).get("docs", [])
                    if docs:
                        return docs[0].get("latestVersion")
                logger.warning(f"Failed to fetch {name} from Maven Central. HTTP {response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"Network error querying Maven Central for {name}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error getting latest version for {name}: {e}")
        return None

    async def scan(self, repo_files: List[str]) -> List[str]:
        """Find pom.xml and build.gradle files in the repository."""
        return [f for f in repo_files if f.endswith("pom.xml") or f.endswith("build.gradle")]
