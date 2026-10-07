import logging
import asyncio
from typing import Dict, Any, List

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.models.schemas import ScanResult
from app.github.api import GitHubClient
from app.github.app_auth import get_installation_access_token
from app.scanners import PipScanner, NpmScanner, DockerScanner, SecurityScanner
from app.actions.branch import create_update_branch, branch_exists, generate_branch_name
from app.actions.updater import DependencyUpdater
from app.actions.pull_request import PRCreator
from app.actions.auto_merge import AutoMerger

logger = logging.getLogger(__name__)

class ScanScheduler:
    """
    Schedules and orchestrates automated dependency and security scans for repositories.
    """

    def __init__(self, scan_interval_hours: int = 24):
        self.scheduler = AsyncIOScheduler()
        self.scan_interval_hours = scan_interval_hours
        self.jobs: Dict[str, Any] = {}

    def start(self):
        """Starts the APScheduler instance."""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("ScanScheduler started.")

    def stop(self):
        """Stops the APScheduler instance."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("ScanScheduler stopped.")

    def add_repo(self, owner: str, repo: str, installation_id: int):
        """Schedules a periodic scan for a specific repository."""
        job_id = f"scan_{owner}_{repo}"
        if job_id in self.jobs:
            logger.info(f"Job already exists for {owner}/{repo}. Skipping.")
            return

        job = self.scheduler.add_job(
            self.run_scan,
            'interval',
            hours=self.scan_interval_hours,
            args=[owner, repo, installation_id],
            id=job_id,
            replace_existing=True
        )
        self.jobs[job_id] = job
        logger.info(f"Scheduled scan for {owner}/{repo} every {self.scan_interval_hours} hours.")

    def remove_repo(self, owner: str, repo: str):
        """Removes a repository from the scheduled scans."""
        job_id = f"scan_{owner}_{repo}"
        if job_id in self.jobs:
            self.scheduler.remove_job(job_id)
            del self.jobs[job_id]
            logger.info(f"Removed scan schedule for {owner}/{repo}.")

    async def run_scan(self, owner: str, repo: str, installation_id: int) -> ScanResult:
        """
        Orchestrates a full scan of a repository:
        1. Authenticate as GitHub App
        2. Fetch dependency files from repo
        3. Run all scanners (pip, npm, docker)
        4. Run security scanner on found dependencies
        5. For each outdated/vulnerable dependency:
           a. Check if PR already exists
           b. Create branch
           c. Update dependency file
           d. Commit changes
           e. Create PR
           f. Check auto-merge eligibility
        6. Return ScanResult
        """
        logger.info(f"Starting scheduled scan for {owner}/{repo} (Install ID: {installation_id})")
        scan_result = ScanResult(owner=owner, repo=repo, dependencies=[], vulnerabilities=[])

        try:
            # 1. Authenticate
            token = await get_installation_access_token(installation_id)
            github_client = GitHubClient(token=token)
            
            # 2. Fetch dependency files (Simplified simulation of fetching repo files)
            # In reality, you would use github_client to search for requirements.txt, package.json, etc.
            repo_files = await github_client.get_repository_files(owner, repo)

            # 3. & 4. Run scanners
            scanners = [PipScanner(), NpmScanner(), DockerScanner()]
            security_scanner = SecurityScanner()

            for scanner in scanners:
                # Mock: Find files relevant to the scanner
                relevant_files = scanner.get_relevant_files(repo_files)
                for file_info in relevant_files:
                    content = await github_client.get_file_content(owner, repo, file_info['path'])
                    
                    # Scan for dependencies
                    deps = await scanner.scan(content)
                    scan_result.dependencies.extend(deps)

                    # Scan for vulnerabilities
                    vulns = await security_scanner.scan(deps)
                    scan_result.vulnerabilities.extend(vulns)
                    
                    # 5. Process outdated/vulnerable dependencies
                    updater = DependencyUpdater()
                    pr_creator = PRCreator(github_client)
                    auto_merger = AutoMerger(github_client)

                    for dep in deps:
                        if not dep.is_outdated and not any(v.package_name == dep.name for v in vulns):
                            continue # Up to date and secure

                        branch_name = generate_branch_name(dep.ecosystem, dep.name, dep.new_version)
                        
                        # a. Check if branch/PR exists
                        if await branch_exists(github_client, owner, repo, branch_name):
                            logger.info(f"Branch {branch_name} already exists. Skipping PR creation.")
                            continue

                        # b. Create branch
                        branch_created = await create_update_branch(github_client, owner, repo, branch_name)
                        if not branch_created:
                            continue

                        # c. Update dependency file
                        new_content = updater.auto_update_file(
                            content, file_info['path'], dep.name, dep.current_version, dep.new_version
                        )

                        # d. Commit changes
                        await github_client.update_file(
                            owner=owner,
                            repo=repo,
                            path=file_info['path'],
                            message=f"chore(deps): update {dep.name} to {dep.new_version}",
                            content=new_content,
                            branch=branch_name
                        )

                        # e. Create PR
                        vuln = next((v for v in vulns if v.package_name == dep.name), None)
                        pr_data = await pr_creator.create_update_pr(owner, repo, scan_result, dep, vuln)
                        
                        # f. Check auto-merge
                        if pr_data and pr_data.get('number'):
                            pr_number = pr_data['number']
                            # Assuming no vulnerabilities in NEW version for this logic block
                            if await auto_merger.should_auto_merge(dep, []):
                                await auto_merger.enable_auto_merge(owner, repo, pr_number)

            logger.info(f"Completed scheduled scan for {owner}/{repo}")
            return scan_result

        except Exception as e:
            logger.error(f"Error during scan for {owner}/{repo}: {e}")
            raise
