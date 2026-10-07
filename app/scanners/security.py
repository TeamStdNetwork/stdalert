import logging
import httpx
from typing import List, Dict, Any
from app.models.schemas import DependencyInfo, VulnerabilityInfo

logger = logging.getLogger(__name__)

OSV_API_URL = "https://api.osv.dev/v1/query"

def _map_ecosystem(ecosystem: str) -> str:
    """Map our ecosystem names to OSV.dev ecosystem names."""
    mapping = {
        "pip": "PyPI",
        "npm": "npm"
    }
    return mapping.get(ecosystem, ecosystem)

def _map_severity(severity_data: List[Dict[str, Any]]) -> str:
    """Extract severity from OSV data."""
    if not severity_data:
        return "UNKNOWN"
        
    for sev in severity_data:
        if sev.get("type") == "CVSS_V3":
            score_str = sev.get("score", "")
            if "CRITICAL" in score_str or "HIGH" in score_str:
                return "HIGH"
            elif "MEDIUM" in score_str:
                return "MEDIUM"
            elif "LOW" in score_str:
                return "LOW"
    return "UNKNOWN"

async def check_vulnerability(package: str, version: str, ecosystem: str) -> List[VulnerabilityInfo]:
    """Check a single package version for vulnerabilities using OSV.dev."""
    osv_ecosystem = _map_ecosystem(ecosystem)
    payload = {
        "version": version,
        "package": {
            "name": package,
            "ecosystem": osv_ecosystem
        }
    }
    
    vulns = []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(OSV_API_URL, json=payload)
            response.raise_for_status()
            data = response.json()
            
            for vuln in data.get("vulns", []):
                vulns.append(VulnerabilityInfo(
                    id=vuln.get("id", "UNKNOWN"),
                    package_name=package,
                    ecosystem=ecosystem,
                    summary=vuln.get("summary", "No summary available"),
                    details=vuln.get("details", ""),
                    severity=_map_severity(vuln.get("severity", [])),
                    fixed_versions=[] # Extraction logic would go here
                ))
    except Exception as e:
        logger.error(f"Error checking vulnerabilities for {package}@{version}: {e}")
        
    return vulns

async def batch_check(dependencies: List[DependencyInfo]) -> List[VulnerabilityInfo]:
    """Check multiple dependencies for vulnerabilities."""
    all_vulns = []
    for dep in dependencies:
        vulns = await check_vulnerability(dep.name, dep.current_version, dep.ecosystem)
        all_vulns.extend(vulns)
    return all_vulns
