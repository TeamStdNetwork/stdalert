import os
import json
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

class ScanStorage:
    def __init__(self, data_dir: str = 'data'):
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        
    def _get_repo_dir(self, repo_full_name: str) -> str:
        safe_name = repo_full_name.replace('/', '_')
        return os.path.join(self.data_dir, safe_name)
        
    async def save_scan(self, repo_full_name: str, scan_result: Dict[str, Any]) -> None:
        repo_dir = self._get_repo_dir(repo_full_name)
        scans_dir = os.path.join(repo_dir, 'scans')
        os.makedirs(scans_dir, exist_ok=True)
        
        timestamp = datetime.utcnow().isoformat().replace(':', '-')
        filepath = os.path.join(scans_dir, f"{timestamp}.json")
        
        scan_result['timestamp'] = timestamp
        scan_result['repo'] = repo_full_name
        
        def write_file():
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(scan_result, f, indent=2)
                
        await asyncio.to_thread(write_file)
        
    async def get_scans(self, repo_full_name: str, limit: int = 20) -> List[Dict[str, Any]]:
        repo_dir = self._get_repo_dir(repo_full_name)
        scans_dir = os.path.join(repo_dir, 'scans')
        
        if not os.path.exists(scans_dir):
            return []
            
        def read_files():
            files = sorted([f for f in os.listdir(scans_dir) if f.endswith('.json')], reverse=True)
            scans = []
            for file in files[:limit]:
                with open(os.path.join(scans_dir, file), 'r', encoding='utf-8') as f:
                    try:
                        scans.append(json.load(f))
                    except json.JSONDecodeError:
                        pass
            return scans
            
        return await asyncio.to_thread(read_files)
        
    async def get_latest_scan(self, repo_full_name: str) -> Optional[Dict[str, Any]]:
        scans = await self.get_scans(repo_full_name, limit=1)
        if scans:
            return scans[0]
        return None
        
    async def get_all_repos(self) -> List[str]:
        if not os.path.exists(self.data_dir):
            return []
            
        def list_repos():
            repos = []
            for d in os.listdir(self.data_dir):
                repo_dir = os.path.join(self.data_dir, d)
                if os.path.isdir(repo_dir):
                    scans_dir = os.path.join(repo_dir, 'scans')
                    if os.path.exists(scans_dir) and os.listdir(scans_dir):
                        # try to get actual name from latest scan
                        files = sorted([f for f in os.listdir(scans_dir) if f.endswith('.json')], reverse=True)
                        if files:
                            try:
                                with open(os.path.join(scans_dir, files[0]), 'r', encoding='utf-8') as f:
                                    data = json.load(f)
                                    repos.append(data.get('repo', d.replace('_', '/')))
                            except Exception:
                                pass
            return list(set(repos))
            
        return await asyncio.to_thread(list_repos)
        
    async def get_stats(self) -> Dict[str, int]:
        stats = {
            'total_repos_monitored': 0,
            'total_scans_run': 0,
            'total_prs_created': 0,
            'total_vulnerabilities_found': 0,
            'total_dependencies_updated': 0
        }
        
        repos = await self.get_all_repos()
        stats['total_repos_monitored'] = len(repos)
        
        for repo in repos:
            scans = await self.get_scans(repo, limit=1000)
            stats['total_scans_run'] += len(scans)
            for scan in scans:
                stats['total_vulnerabilities_found'] += len(scan.get('vulnerabilities', []))
                # For prs created and dependencies updated, this would typically be tracked separately
                # but we'll infer it from scan metadata if available
                metadata = scan.get('metadata', {})
                stats['total_prs_created'] += metadata.get('prs_created', 0)
                stats['total_dependencies_updated'] += metadata.get('dependencies_updated', 0)
                
        return stats
