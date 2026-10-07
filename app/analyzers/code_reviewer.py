import ast
import re
import logging
from typing import List, Dict, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class ReviewFinding(BaseModel):
    file_path: str
    line_number: int
    category: str
    severity: str
    message: str
    suggestion: str

class CodeReviewer:
    """Analyzes code files for common issues using pattern matching and AST analysis."""

    async def review_python_file(self, path: str, content: str) -> List[ReviewFinding]:
        findings = []
        lines = content.splitlines()

        # Regex checks
        for i, line in enumerate(lines, 1):
            if re.search(r'\bprint\s*\(', line):
                findings.append(ReviewFinding(
                    file_path=path, line_number=i, category="style", severity="info",
                    message="print() in production code.",
                    suggestion="Use logging instead of print()."
                ))
            if re.search(r'(?i)(TODO|FIXME|HACK)', line):
                findings.append(ReviewFinding(
                    file_path=path, line_number=i, category="maintenance", severity="info",
                    message="Found TODO/FIXME/HACK comment.",
                    suggestion="Address or track this technical debt."
                ))
            if re.search(r'password\s*=\s*[\'"].+[\'"]', line, re.IGNORECASE) or \
               re.search(r'secret\s*=\s*[\'"].+[\'"]', line, re.IGNORECASE) or \
               re.search(r'api_key\s*=\s*[\'"].+[\'"]', line, re.IGNORECASE):
                findings.append(ReviewFinding(
                    file_path=path, line_number=i, category="security", severity="error",
                    message="Potential hardcoded secret or password.",
                    suggestion="Use environment variables or a secrets manager."
                ))
            if re.search(r'from\s+\S+\s+import\s+\*', line):
                findings.append(ReviewFinding(
                    file_path=path, line_number=i, category="style", severity="warning",
                    message="import * usage found.",
                    suggestion="Import specific modules or functions instead."
                ))
        
        # AST based checks
        try:
            tree = ast.parse(content, filename=path)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id in ('eval', 'exec'):
                        findings.append(ReviewFinding(
                            file_path=path, line_number=node.lineno, category="security", severity="error",
                            message=f"Usage of {node.func.id}().",
                            suggestion="Avoid using eval() or exec() as they pose significant security risks."
                        ))
                    if isinstance(node.func, ast.Attribute) and node.func.attr == 'Popen' and isinstance(node.func.value, ast.Name) and node.func.value.id == 'subprocess':
                        for kw in node.keywords:
                            if kw.arg == 'shell' and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                                findings.append(ReviewFinding(
                                    file_path=path, line_number=node.lineno, category="security", severity="error",
                                    message="subprocess with shell=True.",
                                    suggestion="Avoid shell=True as it introduces shell injection vulnerabilities."
                                ))
                    
                    if isinstance(node.func, ast.Attribute) and node.func.attr == 'execute':
                        if node.args and isinstance(node.args[0], ast.JoinedStr): # f-string
                            findings.append(ReviewFinding(
                                file_path=path, line_number=node.lineno, category="security", severity="error",
                                message="Potential SQL injection via string formatting.",
                                suggestion="Use parameterized queries instead of formatting SQL strings."
                            ))

                if isinstance(node, ast.FunctionDef):
                    # Check for mutable default arguments
                    for default in node.args.defaults:
                        if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                            findings.append(ReviewFinding(
                                file_path=path, line_number=node.lineno, category="bug_risk", severity="warning",
                                message="Mutable default argument found.",
                                suggestion="Use None as default and initialize the mutable object inside the function."
                            ))
                    # Check for type hints
                    if not node.returns or any(arg.annotation is None for arg in node.args.args if arg.arg != 'self' and arg.arg != 'cls'):
                         findings.append(ReviewFinding(
                            file_path=path, line_number=node.lineno, category="style", severity="info",
                            message="Missing type hints on function signature.",
                            suggestion="Add type hints for arguments and return value."
                        ))

                if isinstance(node, ast.ExceptHandler):
                    if node.type is None:
                        findings.append(ReviewFinding(
                            file_path=path, line_number=node.lineno, category="bug_risk", severity="warning",
                            message="Bare except clause found.",
                            suggestion="Catch specific exceptions instead of using a bare except."
                        ))

        except SyntaxError as e:
            logger.warning(f"Syntax error while parsing Python file {path}: {e}")

        # Basic context manager check for open()
        for i, line in enumerate(lines, 1):
             if re.search(r'(?<!with\s)\bopen\(', line) and 'with open(' not in line:
                 findings.append(ReviewFinding(
                    file_path=path, line_number=i, category="bug_risk", severity="warning",
                    message="open() without context manager.",
                    suggestion="Use 'with open(...)' to ensure files are properly closed."
                ))
             if re.search(r'requests\.(get|post|put|delete|patch|request)\(', line) and 'timeout=' not in line:
                 findings.append(ReviewFinding(
                    file_path=path, line_number=i, category="bug_risk", severity="warning",
                    message="requests call without timeout.",
                    suggestion="Always specify a timeout when using requests to prevent hanging."
                ))

        return findings

    async def review_javascript_file(self, path: str, content: str) -> List[ReviewFinding]:
        findings = []
        lines = content.splitlines()

        for i, line in enumerate(lines, 1):
            if re.search(r'\beval\s*\(', line):
                findings.append(ReviewFinding(
                    file_path=path, line_number=i, category="security", severity="error",
                    message="Usage of eval().",
                    suggestion="Avoid using eval() due to security and performance risks."
                ))
            if '.innerHTML' in line and '=' in line:
                findings.append(ReviewFinding(
                    file_path=path, line_number=i, category="security", severity="error",
                    message="innerHTML assignment.",
                    suggestion="Use textContent or secure DOM manipulation to avoid XSS risks."
                ))
            if re.search(r'\bconsole\.log\s*\(', line):
                findings.append(ReviewFinding(
                    file_path=path, line_number=i, category="style", severity="info",
                    message="console.log in production.",
                    suggestion="Remove or replace with a proper logging mechanism."
                ))
            if re.search(r'\bvar\s+\w+', line):
                findings.append(ReviewFinding(
                    file_path=path, line_number=i, category="style", severity="warning",
                    message="Usage of var.",
                    suggestion="Use let or const for block-scoped variables."
                ))
            if re.search(r'(?<![=!])==(?!==)', line):
                findings.append(ReviewFinding(
                    file_path=path, line_number=i, category="bug_risk", severity="warning",
                    message="Usage of == instead of ===.",
                    suggestion="Use strict equality (===) to prevent unexpected type coercion."
                ))
            if re.search(r'\bdocument\.write\s*\(', line):
                findings.append(ReviewFinding(
                    file_path=path, line_number=i, category="security", severity="warning",
                    message="document.write usage.",
                    suggestion="Avoid document.write as it can overwrite the document or introduce XSS."
                ))
            if re.search(r'\b(setTimeout|setInterval)\s*\(\s*[\'"`]', line):
                findings.append(ReviewFinding(
                    file_path=path, line_number=i, category="security", severity="error",
                    message="setTimeout/setInterval with string argument.",
                    suggestion="Pass a function instead of a string to avoid eval-like execution."
                ))
        
        # multiline check for async/await without try/catch
        if 'await ' in content and 'try {' not in content and '.catch(' not in content:
            findings.append(ReviewFinding(
                file_path=path, line_number=1, category="bug_risk", severity="warning",
                message="Potential lack of error handling in async/await code.",
                suggestion="Wrap await calls in try/catch blocks or use .catch()."
            ))

        return findings

    async def review_dockerfile(self, path: str, content: str) -> List[ReviewFinding]:
        findings = []
        lines = content.splitlines()
        
        has_user = False
        has_healthcheck = False
        stages = 0
        as_stages = 0

        for i, line in enumerate(lines, 1):
            line_upper = line.upper().strip()
            if line_upper.startswith("USER "):
                has_user = True
            if line_upper.startswith("HEALTHCHECK "):
                has_healthcheck = True
            if line_upper.startswith("FROM "):
                stages += 1
                if " AS " in line_upper:
                    as_stages += 1
                if ":latest" in line.lower() or (":" not in line.split()[1] and "@" not in line.split()[1]):
                    findings.append(ReviewFinding(
                        file_path=path, line_number=i, category="bug_risk", severity="warning",
                        message="Using :latest tag or missing version tag.",
                        suggestion="Pin base images to a specific version instead of latest."
                    ))
            if line_upper.startswith("ADD ") and not ((".tar" in line.lower() and "http" not in line.lower()) or "http" in line.lower()):
                 findings.append(ReviewFinding(
                    file_path=path, line_number=i, category="style", severity="info",
                    message="ADD instruction used instead of COPY.",
                    suggestion="Use COPY unless you specifically need ADD's tar extraction or URL fetching capabilities."
                ))
            if line_upper.startswith("ENV ") and any(secret in line.lower() for secret in ["secret", "password", "key", "token"]):
                findings.append(ReviewFinding(
                    file_path=path, line_number=i, category="security", severity="error",
                    message="Potential secret stored in ENV.",
                    suggestion="Do not store secrets in environment variables in Dockerfile."
                ))
            if line_upper.startswith("RUN ") and "apt-get" in line and "install" in line:
                if "--no-install-recommends" not in line:
                    findings.append(ReviewFinding(
                        file_path=path, line_number=i, category="performance", severity="warning",
                        message="apt-get install without --no-install-recommends.",
                        suggestion="Use --no-install-recommends to reduce image size."
                    ))
                if "rm -rf /var/lib/apt/lists/*" not in content:
                    findings.append(ReviewFinding(
                        file_path=path, line_number=i, category="performance", severity="warning",
                        message="Not cleaning apt cache.",
                        suggestion="Add 'rm -rf /var/lib/apt/lists/*' after apt-get install."
                    ))

        if not has_user:
            findings.append(ReviewFinding(
                file_path=path, line_number=1, category="security", severity="error",
                message="Running as root (no USER instruction).",
                suggestion="Add a USER instruction to run the container as a non-root user."
            ))
        if not has_healthcheck:
             findings.append(ReviewFinding(
                file_path=path, line_number=1, category="maintenance", severity="warning",
                message="No HEALTHCHECK instruction.",
                suggestion="Add a HEALTHCHECK instruction to help orchestrators monitor container health."
            ))
        if stages > 1 and as_stages < stages:
             findings.append(ReviewFinding(
                file_path=path, line_number=1, category="style", severity="info",
                message="Multiple FROM without AS (unnamed stages).",
                suggestion="Name your build stages using 'FROM ... AS ...' for better readability."
            ))
        
        return findings

    async def review_repo(self, repo_files: Dict[str, str]) -> List[ReviewFinding]:
        all_findings = []
        for path, content in repo_files.items():
            if path.endswith('.py'):
                findings = await self.review_python_file(path, content)
                all_findings.extend(findings)
            elif path.endswith(('.js', '.ts', '.jsx', '.tsx')):
                findings = await self.review_javascript_file(path, content)
                all_findings.extend(findings)
            elif "Dockerfile" in path:
                findings = await self.review_dockerfile(path, content)
                all_findings.extend(findings)
                
            if "Dockerfile" in path and ".dockerignore" not in repo_files:
                all_findings.append(ReviewFinding(
                    file_path=".dockerignore", line_number=1, category="performance", severity="warning",
                    message="No .dockerignore mentioned.",
                    suggestion="Add a .dockerignore file to exclude unnecessary files from the build context."
                ))
        return all_findings
