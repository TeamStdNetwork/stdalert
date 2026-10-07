import re
import logging
from pydantic import BaseModel
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class SecretFinding(BaseModel):
    file_path: str
    line_number: int
    secret_type: str
    severity: str
    masked_value: str
    recommendation: str

class SecretScanner:
    """Scans repository files for leaked secrets and credentials."""
    
    PATTERNS = {
        'AWS Access Key': re.compile(r'AKIA[0-9A-Z]{16}'),
        'AWS Secret Key': re.compile(r'[0-9a-zA-Z/+]{40}'),
        'GitHub Token': re.compile(r'ghp_[0-9a-zA-Z]{36}|github_pat_[0-9a-zA-Z_]{82}'),
        'Google API Key': re.compile(r'AIza[0-9A-Za-z-_]{35}'),
        'Slack Token': re.compile(r'xox[baprs]-[0-9a-zA-Z-]{10,}'),
        'Generic API Key': re.compile(r'(api[_-]?key|apikey|api[_-]?secret)\s*[:=]\s*[\'"]([0-9a-zA-Z]{16,})[\'"]'),
        'Private Key': re.compile(r'-----BEGIN (RSA |EC |DSA )?PRIVATE KEY-----'),
        'Database URL': re.compile(r'(postgres|mysql|mongodb)://[^\s]+'),
        'JWT Token': re.compile(r'eyJ[A-Za-z0-9-_]+\.eyJ[A-Za-z0-9-_]+'),
        'Stripe Key': re.compile(r'sk_live_[0-9a-zA-Z]{24}'),
        'SendGrid Key': re.compile(r'SG\.[0-9A-Za-z-_]{22}\.[0-9A-Za-z-_]{43}'),
        'Twilio Key': re.compile(r'SK[0-9a-fA-F]{32}')
    }
    
    IGNORE_FILES = {'.env.example'}
    IGNORE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.pdf', '.exe', '.dll', '.so', '.dylib', '.pyc'}
    
    def _mask_secret(self, value: str) -> str:
        """Masks a secret, showing only the first 4 characters."""
        if len(value) <= 4:
            return "****"
        return value[:4] + "****"

    def _should_skip_file(self, file_path: str) -> bool:
        """Determines if a file should be skipped from scanning."""
        if any(file_path.endswith(ext) for ext in self.IGNORE_EXTENSIONS):
            return True
        if any(ignored in file_path for ignored in self.IGNORE_FILES):
            return True
        if 'test/fixtures' in file_path or 'tests/fixtures' in file_path:
            return True
        return False

    async def scan_file(self, file_path: str, content: str) -> List[SecretFinding]:
        """Scans a single file's content for secrets."""
        if self._should_skip_file(file_path):
            return []

        findings = []
        lines = content.splitlines()
        for i, line in enumerate(lines, start=1):
            for secret_type, pattern in self.PATTERNS.items():
                for match in pattern.finditer(line):
                    if secret_type == 'Generic API Key':
                        secret_value = match.group(2) if match.lastindex and match.lastindex >= 2 else match.group(0)
                    else:
                        secret_value = match.group(0)
                    
                    masked = self._mask_secret(secret_value)
                    
                    findings.append(
                        SecretFinding(
                            file_path=file_path,
                            line_number=i,
                            secret_type=secret_type,
                            severity="critical",
                            masked_value=masked,
                            recommendation=f"Revoke this {secret_type} immediately and remove it from version control."
                        )
                    )
        return findings

    async def scan_repo(self, repo_files: Dict[str, str]) -> List[SecretFinding]:
        """Scans a dictionary of file paths to contents for secrets."""
        all_findings = []
        for file_path, content in repo_files.items():
            try:
                findings = await self.scan_file(file_path, content)
                all_findings.extend(findings)
            except Exception as e:
                logger.error(f"Error scanning file {file_path} for secrets: {e}")
        return all_findings
