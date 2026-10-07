from typing import Dict, Any, List

class HealthScorer:
    def calculate_score(self, scan_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate health score based on scan result.
        Assumes scan_result has 'dependencies' (list) and 'vulnerabilities' (list).
        """
        deps = scan_result.get('dependencies', [])
        vulns = scan_result.get('vulnerabilities', [])
        
        # 1. Dependency freshness (40 points)
        total_deps = len(deps)
        outdated_deps = sum(1 for d in deps if d.get('outdated', False))
        
        if total_deps == 0:
            dep_score = 40
        else:
            outdated_ratio = outdated_deps / total_deps
            if outdated_ratio == 0:
                dep_score = 40
            elif outdated_ratio < 0.2:
                dep_score = 30
            elif outdated_ratio < 0.5:
                dep_score = 20
            elif outdated_ratio < 1.0:
                dep_score = 10
            else:
                dep_score = 0
                
        # 2. Security (40 points)
        has_critical = any(v.get('severity', '').lower() == 'critical' for v in vulns)
        has_high = any(v.get('severity', '').lower() == 'high' for v in vulns)
        
        if len(vulns) == 0:
            sec_score = 40
        elif has_critical:
            sec_score = 0
        elif has_high:
            sec_score = 10
        else:
            sec_score = 25
            
        # 3. Maintenance (20 points)
        # Assuming we have some flags in the scan_result metadata
        metadata = scan_result.get('metadata', {})
        has_lockfile = metadata.get('has_lockfile', True)
        deps_pinned = metadata.get('deps_pinned', True)
        no_deprecated = not metadata.get('has_deprecated', False)
        docker_tagged = metadata.get('docker_tagged', True)
        
        maint_score = 0
        if has_lockfile: maint_score += 5
        if deps_pinned: maint_score += 5
        if no_deprecated: maint_score += 5
        if docker_tagged: maint_score += 5
        
        total_score = dep_score + sec_score + maint_score
        
        if total_score >= 95:
            grade = 'A+'
        elif total_score >= 85:
            grade = 'A'
        elif total_score >= 70:
            grade = 'B'
        elif total_score >= 55:
            grade = 'C'
        elif total_score >= 40:
            grade = 'D'
        else:
            grade = 'F'
            
        recommendations = []
        if dep_score < 40:
            recommendations.append("Update outdated dependencies.")
        if sec_score < 40:
            recommendations.append("Fix security vulnerabilities.")
        if not has_lockfile:
            recommendations.append("Commit a dependency lockfile.")
            
        return {
            'total_score': total_score,
            'grade': grade,
            'dependency_score': dep_score,
            'security_score': sec_score,
            'maintenance_score': maint_score,
            'recommendations': recommendations
        }
