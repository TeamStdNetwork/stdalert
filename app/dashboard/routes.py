from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from typing import List, Dict, Any
from app.dashboard.storage import ScanStorage
from app.dashboard.health_score import HealthScorer
import os

router = APIRouter(prefix='/dashboard')
storage = ScanStorage()
scorer = HealthScorer()

@router.get('/', response_class=HTMLResponse)
async def get_dashboard():
    template_path = os.path.join(os.path.dirname(__file__), 'templates', 'index.html')
    with open(template_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)

@router.get('/api/repos')
async def list_repos() -> List[Dict[str, Any]]:
    repos = await storage.get_all_repos()
    result = []
    for repo in repos:
        latest_scan = await storage.get_latest_scan(repo)
        if latest_scan:
            score_data = scorer.calculate_score(latest_scan)
            result.append({
                'repo': repo,
                'latest_scan': latest_scan,
                'health': score_data
            })
    return result

@router.get('/api/repos/{owner}/{repo_name}/scans')
async def get_repo_scans(owner: str, repo_name: str) -> List[Dict[str, Any]]:
    full_name = f"{owner}/{repo_name}"
    scans = await storage.get_scans(full_name)
    return scans

@router.get('/api/repos/{owner}/{repo_name}/health')
async def get_repo_health(owner: str, repo_name: str) -> Dict[str, Any]:
    full_name = f"{owner}/{repo_name}"
    latest_scan = await storage.get_latest_scan(full_name)
    if not latest_scan:
        raise HTTPException(status_code=404, detail="No scans found for repository")
    return scorer.calculate_score(latest_scan)

@router.get('/api/stats')
async def get_stats() -> Dict[str, int]:
    return await storage.get_stats()

@router.post('/api/repos/{owner}/{repo_name}/scan')
async def trigger_scan(owner: str, repo_name: str) -> Dict[str, str]:
    full_name = f"{owner}/{repo_name}"
    # In a real app, this would trigger a background task or message queue
    return {"message": f"Scan triggered for {full_name}", "status": "pending"}
