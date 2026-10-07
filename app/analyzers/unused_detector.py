import re
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

class UnusedDependencyDetector:
    """Detects potentially unused dependencies in a repository."""

    def __init__(self):
        # Common package name mappings: PyPI name -> import name
        self.python_mappings = {
            "pillow": ["PIL"],
            "beautifulsoup4": ["bs4"],
            "python-dotenv": ["dotenv"],
            "scikit-learn": ["sklearn"],
            "pyyaml": ["yaml"],
            "djangorestframework": ["rest_framework"],
            "psycopg2-binary": ["psycopg2"],
        }

    async def detect_python(self, repo_files: Dict[str, str], dependencies: List[str]) -> List[str]:
        unused = []
        py_files_content = "\n".join(
            content for path, content in repo_files.items() if path.endswith('.py')
        )

        for dep in dependencies:
            # Strip version specifiers
            clean_dep = re.split(r'[=><~]', dep)[0].strip().lower()
            if not clean_dep:
                continue

            import_names = self.python_mappings.get(clean_dep, [clean_dep.replace("-", "_")])
            
            is_used = False
            for import_name in import_names:
                # Search for 'import package' or 'from package'
                pattern = rf"^\s*(import\s+{import_name}|from\s+{import_name}\s+import)"
                if re.search(pattern, py_files_content, re.MULTILINE):
                    is_used = True
                    break
            
            if not is_used:
                unused.append(clean_dep)

        return unused

    async def detect_npm(self, repo_files: Dict[str, str], dependencies: List[str]) -> List[str]:
        unused = []
        js_files_content = "\n".join(
            content for path, content in repo_files.items() 
            if path.endswith(('.js', '.jsx', '.ts', '.tsx'))
        )

        for dep in dependencies:
            if dep.startswith("@types/"):
                continue # Skip type definitions
                
            clean_dep = dep.strip()
            if not clean_dep:
                continue

            # Check require or import
            escaped_dep = re.escape(clean_dep)
            patterns = [
                rf"require\(['\"]{escaped_dep}['\"]\)",
                rf"from\s+['\"]{escaped_dep}['\"]",
                rf"import\s+['\"]{escaped_dep}['\"]"
            ]
            
            is_used = False
            for pattern in patterns:
                if re.search(pattern, js_files_content):
                    is_used = True
                    break
            
            if not is_used:
                unused.append(clean_dep)

        return unused

    async def detect_all(self, repo_files: Dict[str, str], dependencies: List[str], ecosystem: str) -> List[str]:
        if ecosystem == "python":
            return await self.detect_python(repo_files, dependencies)
        elif ecosystem == "npm":
            return await self.detect_npm(repo_files, dependencies)
        else:
            logger.warning(f"Unsupported ecosystem for unused detection: {ecosystem}")
            return []
