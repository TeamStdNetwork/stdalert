import logging
import httpx
from pydantic import BaseModel
from typing import List, Optional

logger = logging.getLogger(__name__)

class LicenseInfo(BaseModel):
    package_name: str
    license_type: str
    is_compatible: bool
    risk_level: str
    details: str

class LicenseScanner:
    """Checks license compatibility of dependencies."""
    
    COMPATIBILITY = {
        'MIT': {'compatible': True, 'risk': 'none'},
        'Apache-2.0': {'compatible': True, 'risk': 'none'},
        'BSD-2-Clause': {'compatible': True, 'risk': 'none'},
        'BSD-3-Clause': {'compatible': True, 'risk': 'none'},
        'ISC': {'compatible': True, 'risk': 'none'},
        'Unlicense': {'compatible': True, 'risk': 'none'},
        'LGPL-2.1': {'compatible': True, 'risk': 'low'},
        'LGPL-3.0': {'compatible': True, 'risk': 'low'},
        'MPL-2.0': {'compatible': True, 'risk': 'low'},
        'GPL-2.0': {'compatible': False, 'risk': 'high'},
        'GPL-3.0': {'compatible': False, 'risk': 'high'},
        'AGPL-3.0': {'compatible': False, 'risk': 'high'}
    }

    async def get_package_license(self, package_name: str, ecosystem: str) -> Optional[str]:
        """Fetches the license for a given package from its ecosystem registry."""
        try:
            async with httpx.AsyncClient() as client:
                if ecosystem.lower() == 'pypi':
                    response = await client.get(f"https://pypi.org/pypi/{package_name}/json")
                    if response.status_code == 200:
                        data = response.json()
                        return data.get('info', {}).get('license')
                elif ecosystem.lower() == 'npm':
                    response = await client.get(f"https://registry.npmjs.org/{package_name}/latest")
                    if response.status_code == 200:
                        data = response.json()
                        license_data = data.get('license')
                        if isinstance(license_data, dict):
                            return license_data.get('type')
                        return license_data
        except Exception as e:
            logger.error(f"Failed to fetch license for {package_name} in {ecosystem}: {e}")
        return None

    async def check_compatibility(self, project_license: str, dependency_license: str) -> LicenseInfo:
        """Checks if a dependency license is compatible with the project license."""
        dep_lic_upper = str(dependency_license).upper() if dependency_license else 'UNKNOWN'
        
        matched_lic = 'UNKNOWN'
        for lic in self.COMPATIBILITY:
            if lic.upper() in dep_lic_upper or lic.upper().replace('-','') in dep_lic_upper.replace('-',''):
                matched_lic = lic
                break

        if matched_lic == 'UNKNOWN':
            return LicenseInfo(
                package_name="",
                license_type=dependency_license or "Unknown",
                is_compatible=True,
                risk_level="medium",
                details="Unknown license type. Manual review recommended."
            )
            
        compat_info = self.COMPATIBILITY[matched_lic]
        
        return LicenseInfo(
            package_name="",
            license_type=matched_lic,
            is_compatible=compat_info['compatible'],
            risk_level=compat_info['risk'],
            details=f"Dependency license {matched_lic} has {compat_info['risk']} risk for project license {project_license}."
        )

    async def scan_dependencies(self, dependencies: List[dict], project_license: str = 'MIT') -> List[LicenseInfo]:
        """
        Scans a list of dependencies for license compatibility.
        dependencies format: [{'name': 'requests', 'ecosystem': 'pypi'}, ...]
        """
        results = []
        for dep in dependencies:
            name = dep.get('name')
            ecosystem = dep.get('ecosystem')
            
            if not name or not ecosystem:
                continue
                
            lic_str = await self.get_package_license(name, ecosystem)
            info = await self.check_compatibility(project_license, lic_str)
            info.package_name = name
            results.append(info)
            
        return results
