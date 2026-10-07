import json
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class DependencyUpdater:
    """
    Responsible for parsing and updating file contents with new dependency versions.
    """

    @staticmethod
    def update_requirements_txt(content: str, package: str, old_version: str, new_version: str) -> str:
        """
        Updates a package version in a requirements.txt content block.
        """
        # Match `package==old_version` ignoring spaces
        pattern = re.compile(rf"^({re.escape(package)}\s*==\s*){re.escape(old_version)}(.*)$", re.IGNORECASE | re.MULTILINE)
        
        new_content, count = pattern.subn(rf"\g<1>{new_version}\g<2>", content)
        if count == 0:
            logger.warning(f"Could not find {package}=={old_version} in requirements.txt")
        return new_content

    @staticmethod
    def update_package_json(content: str, package: str, old_version: str, new_version: str) -> str:
        """
        Updates a package version in a package.json content block.
        """
        try:
            data = json.loads(content)
            updated = False
            
            for dep_type in ["dependencies", "devDependencies", "peerDependencies"]:
                if dep_type in data and package in data[dep_type]:
                    # If it uses modifiers like ^ or ~, preserve them
                    current_val: str = data[dep_type][package]
                    prefix = ""
                    if current_val.startswith(("^", "~")):
                        prefix = current_val[0]
                    
                    data[dep_type][package] = f"{prefix}{new_version}"
                    updated = True
                    break
                    
            if not updated:
                logger.warning(f"Could not find {package} in package.json dependencies")
                
            return json.dumps(data, indent=2) + "\n"
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse package.json: {e}")
            return content

    @staticmethod
    def update_dockerfile(content: str, image: str, old_tag: str, new_tag: str) -> str:
        """
        Updates a base image tag in a Dockerfile content block.
        """
        # Match `FROM image:old_tag`
        pattern = re.compile(rf"^(FROM\s+{re.escape(image)}:){re.escape(old_tag)}(.*)$", re.IGNORECASE | re.MULTILINE)
        
        new_content, count = pattern.subn(rf"\g<1>{new_tag}\g<2>", content)
        if count == 0:
            logger.warning(f"Could not find FROM {image}:{old_tag} in Dockerfile")
        return new_content

    @staticmethod
    def auto_update_file(content: str, filename: str, package: str, old_version: str, new_version: str) -> str:
        """
        Auto-detects the file type and updates accordingly.
        """
        filename_lower = filename.lower()
        if filename_lower == "requirements.txt":
            return DependencyUpdater.update_requirements_txt(content, package, old_version, new_version)
        elif filename_lower == "package.json":
            return DependencyUpdater.update_package_json(content, package, old_version, new_version)
        elif "dockerfile" in filename_lower:
            return DependencyUpdater.update_dockerfile(content, package, old_version, new_version)
        else:
            logger.warning(f"Unsupported file type for update: {filename}")
            return content
