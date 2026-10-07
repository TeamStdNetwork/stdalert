from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class DependencyInfo(BaseModel):
    name: str
    current_version: str
    latest_version: str
    ecosystem: str # pip|npm|docker
    update_type: str # major|minor|patch
    is_outdated: bool

class VulnerabilityInfo(BaseModel):
    id: str
    summary: str
    severity: str # critical|high|medium|low
    affected_versions: List[str]
    fixed_version: Optional[str] = None
    references: List[str]

class ScanResult(BaseModel):
    repo_full_name: str
    scanned_at: datetime
    dependencies: List[DependencyInfo]
    vulnerabilities: List[VulnerabilityInfo]
    total_outdated: int
    total_vulnerable: int

class PRInfo(BaseModel):
    title: str
    body: str
    branch_name: str
    base_branch: str
    files_changed: Dict[str, str]

class WebhookEvent(BaseModel):
    action: Optional[str] = None
    installation_id: Optional[int] = None
    repo_full_name: Optional[str] = None
    sender: Optional[str] = None
