import httpx
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class DependencyTrend(BaseModel):
    package_name: str
    ecosystem: str
    current_version: str
    latest_version: str
    versions_behind: int
    days_since_last_update: Optional[int]
    is_deprecated: bool
    is_abandoned: bool
    download_trend: str
    risk_score: int
    recommendation: str

class DependencyAnalytics:
    """Analyzes dependency trends and calculates risk scores."""
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=10.0)

    async def analyze_python_package(self, package_name: str, current_version: str = "0.0.0") -> DependencyTrend:
        url = f"https://pypi.org/pypi/{package_name}/json"
        
        trend = DependencyTrend(
            package_name=package_name,
            ecosystem="python",
            current_version=current_version,
            latest_version="Unknown",
            versions_behind=0,
            days_since_last_update=None,
            is_deprecated=False,
            is_abandoned=False,
            download_trend="stable",
            risk_score=0,
            recommendation="Keep monitoring."
        )

        try:
            response = await self.client.get(url)
            if response.status_code != 200:
                logger.warning(f"Could not fetch PyPI data for {package_name}")
                return trend

            data = response.json()
            info = data.get("info", {})
            releases = data.get("releases", {})

            latest_version = info.get("version", "Unknown")
            trend.latest_version = latest_version

            # Check if deprecated
            classifiers = info.get("classifiers", [])
            if any("Development Status :: 7 - Inactive" in c for c in classifiers):
                trend.is_deprecated = True
                trend.risk_score += 30

            # Calculate days since last release
            latest_releases = releases.get(latest_version, [])
            if latest_releases:
                upload_time_str = latest_releases[0].get("upload_time")
                if upload_time_str:
                    upload_time = datetime.strptime(upload_time_str, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
                    delta = datetime.now(timezone.utc) - upload_time
                    trend.days_since_last_update = delta.days

                    if delta.days >= 730:
                        trend.is_abandoned = True
                        trend.risk_score += 40

            # Estimate versions behind (simple counting)
            versions = list(releases.keys())
            try:
                if current_version in versions and latest_version in versions:
                    cur_idx = versions.index(current_version)
                    lat_idx = versions.index(latest_version)
                    trend.versions_behind = max(0, lat_idx - cur_idx)
                elif current_version != "0.0.0":
                    trend.versions_behind = 1 # Approximation
            except ValueError:
                pass

            if trend.versions_behind > 5:
                trend.risk_score += 20
                
            vulnerabilities = data.get("vulnerabilities")
            if vulnerabilities:
                trend.risk_score += 10

            if trend.risk_score >= 50:
                trend.recommendation = "Consider migrating to an active alternative."
            elif trend.risk_score >= 20:
                trend.recommendation = "Update soon and monitor."
            else:
                trend.recommendation = "Up to date / low risk."

        except Exception as e:
            logger.error(f"Error analyzing Python package {package_name}: {e}")

        return trend

    async def analyze_npm_package(self, package_name: str, current_version: str = "0.0.0") -> DependencyTrend:
        url = f"https://registry.npmjs.org/{package_name}"
        
        trend = DependencyTrend(
            package_name=package_name,
            ecosystem="npm",
            current_version=current_version,
            latest_version="Unknown",
            versions_behind=0,
            days_since_last_update=None,
            is_deprecated=False,
            is_abandoned=False,
            download_trend="stable",
            risk_score=0,
            recommendation="Keep monitoring."
        )

        try:
            response = await self.client.get(url)
            if response.status_code != 200:
                logger.warning(f"Could not fetch npm data for {package_name}")
                return trend

            data = response.json()
            
            latest_version = data.get("dist-tags", {}).get("latest", "Unknown")
            trend.latest_version = latest_version
            
            time_data = data.get("time", {})
            latest_time_str = time_data.get(latest_version)
            
            if latest_time_str:
                latest_time = datetime.strptime(latest_time_str, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
                delta = datetime.now(timezone.utc) - latest_time
                trend.days_since_last_update = delta.days
                
                if delta.days >= 730:
                    trend.is_abandoned = True
                    trend.risk_score += 40

            latest_version_data = data.get("versions", {}).get(latest_version, {})
            if "deprecated" in latest_version_data:
                trend.is_deprecated = True
                trend.risk_score += 30

            versions = list(data.get("versions", {}).keys())
            try:
                if current_version in versions and latest_version in versions:
                    cur_idx = versions.index(current_version)
                    lat_idx = versions.index(latest_version)
                    trend.versions_behind = max(0, lat_idx - cur_idx)
                elif current_version != "0.0.0":
                    trend.versions_behind = 1
            except ValueError:
                pass
                
            if trend.versions_behind > 5:
                trend.risk_score += 20
                
            if trend.risk_score >= 50:
                trend.recommendation = "Consider migrating to an active alternative."
            elif trend.risk_score >= 20:
                trend.recommendation = "Update soon and monitor."
            else:
                trend.recommendation = "Up to date / low risk."

        except Exception as e:
            logger.error(f"Error analyzing NPM package {package_name}: {e}")

        return trend

    async def analyze_all(self, dependencies: List[Dict[str, str]]) -> List[DependencyTrend]:
        trends = []
        for dep in dependencies:
            name = dep.get("name")
            ecosystem = dep.get("ecosystem")
            version = dep.get("version", "0.0.0")
            
            if ecosystem == "python":
                trend = await self.analyze_python_package(name, version)
                trends.append(trend)
            elif ecosystem == "npm":
                trend = await self.analyze_npm_package(name, version)
                trends.append(trend)
                
        trends.sort(key=lambda x: x.risk_score, reverse=True)
        return trends

    async def generate_report(self, trends: List[DependencyTrend]) -> str:
        if not trends:
            return "No dependency trends available."

        high_risk = sum(1 for t in trends if t.risk_score >= 50)
        medium_risk = sum(1 for t in trends if 20 <= t.risk_score < 50)
        low_risk = sum(1 for t in trends if t.risk_score < 20)

        report = [
            "## Dependency Analytics Report",
            "",
            "### Summary Statistics",
            f"- Total Dependencies Analyzed: {len(trends)}",
            f"- High Risk: {high_risk}",
            f"- Medium Risk: {medium_risk}",
            f"- Low Risk: {low_risk}",
            "",
            "### Risk Distribution (Pie Chart)",
            "```mermaid",
            "pie title Risk Distribution",
            f'    "High Risk" : {high_risk}',
            f'    "Medium Risk" : {medium_risk}',
            f'    "Low Risk" : {low_risk}',
            "```",
            "",
            "### Top Risky Dependencies",
            "| Package | Ecosystem | Risk Score | Versions Behind | Recommendation |",
            "|---|---|---|---|---|"
        ]

        for trend in trends[:10]: # Top 10
            report.append(f"| {trend.package_name} | {trend.ecosystem} | {trend.risk_score} | {trend.versions_behind} | {trend.recommendation} |")

        return "\n".join(report)

    async def close(self):
        await self.client.aclose()
