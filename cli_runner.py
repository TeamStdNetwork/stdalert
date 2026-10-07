"""
STD Alert - GitHub Action CLI Runner
Executes repository scans directly inside GitHub Actions workflow runners.
Scans for outdated dependencies, CVE vulnerabilities, leaked secrets,
and automatically opens Pull Requests using the runner's GITHUB_TOKEN.
"""

import asyncio
import os
import sys
import logging
from pathlib import Path
import httpx

from app.scanners.pip_scanner import PipScanner
from app.scanners.npm_scanner import NpmScanner
from app.scanners.docker_scanner import DockerScanner
from app.scanners.go_scanner import GoScanner
from app.scanners.rust_scanner import RustScanner
from app.scanners.security import batch_check
from app.scanners.secret_scanner import SecretScanner
from app.scanners.license_scanner import LicenseScanner
from app.actions.updater import DependencyUpdater
from app.github.api import GitHubClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("std-alert-action")


async def main():
    token = os.getenv("GITHUB_TOKEN") or os.getenv("INPUT_GITHUB_TOKEN")
    repo_full_name = os.getenv("GITHUB_REPOSITORY")
    auto_merge = (os.getenv("INPUT_AUTO_MERGE", "false")).lower() == "true"
    fail_on_critical = (os.getenv("INPUT_FAIL_ON_CRITICAL", "false")).lower() == "true"

    if not token or not repo_full_name:
        logger.error("Missing GITHUB_TOKEN or GITHUB_REPOSITORY environment variable.")
        sys.exit(1)

    owner, repo_name = repo_full_name.split("/")
    workspace = Path(os.getenv("GITHUB_WORKSPACE", "."))
    summary_file = os.getenv("GITHUB_STEP_SUMMARY")

    logger.info(f"🛡️ Starting STD Alert Scan for {repo_full_name}...")

    # Read relevant files from workspace
    repo_files = {}
    scan_extensions = {".txt", ".json", ".toml", ".mod", ".sum", ".yml", ".yaml", ".py", ".js", ".ts"}
    ignore_dirs = {".git", ".venv", "venv", "node_modules", "__pycache__", "dist", "build"}

    for root, dirs, files in os.walk(workspace):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for f in files:
            file_path = Path(root) / f
            rel_path = str(file_path.relative_to(workspace)).replace("\\", "/")
            if f in {"Dockerfile", "requirements.txt", "package.json", "go.mod", "Cargo.toml"} or file_path.suffix in scan_extensions:
                try:
                    repo_files[rel_path] = file_path.read_text(encoding="utf-8", errors="ignore")
                except Exception as e:
                    logger.debug(f"Could not read {rel_path}: {e}")

    logger.info(f"Loaded {len(repo_files)} repository files for scanning.")

    # 1. Run Dependency Scanners
    scanners = [
        PipScanner(),
        NpmScanner(),
        DockerScanner(),
        GoScanner(),
        RustScanner(),
    ]

    all_dependencies = []
    for scanner in scanners:
        try:
            deps = await scanner.scan(repo_files)
            all_dependencies.extend(deps)
            logger.info(f"Scanned with {scanner.name}: found {len(deps)} dependencies.")
        except Exception as e:
            logger.warning(f"Scanner {scanner.name} failed: {e}")

    # 2. Check Security Vulnerabilities (OSV.dev)
    logger.info("Checking vulnerabilities via OSV.dev...")
    vulnerabilities = []
    try:
        vulnerabilities = await batch_check(all_dependencies)
        logger.info(f"Found {len(vulnerabilities)} vulnerabilities.")
    except Exception as e:
        logger.warning(f"Vulnerability check error: {e}")

    # 3. Scan for Leaked Secrets
    logger.info("Scanning for leaked credentials & secrets...")
    secret_scanner = SecretScanner()
    secrets_found = await secret_scanner.scan_repo(repo_files)
    if secrets_found:
        logger.warning(f"🚨 CRITICAL: Found {len(secrets_found)} leaked secrets!")

    # 4. Check License Compliance
    logger.info("Scanning license compliance...")
    license_scanner = LicenseScanner()
    license_issues = await license_scanner.scan_dependencies(all_dependencies, project_license="MIT")

    # 5. Filter Outdated Dependencies
    outdated = [d for d in all_dependencies if d.is_outdated]
    logger.info(f"Found {len(outdated)} outdated dependencies.")

    # 6. Create PRs for Outdated Dependencies via GitHub API
    github_client = GitHubClient(token=token)
    pr_created_count = 0

    if outdated:
        # Get default branch info
        repo_info = await github_client.get_repo_info(owner, repo_name)
        default_branch = repo_info.get("default_branch", "main")
        open_prs = await github_client.get_open_prs(owner, repo_name, head_prefix="std-alert/")
        open_titles = {pr.get("title", "") for pr in open_prs}

        updater = DependencyUpdater()

        for dep in outdated[:5]:  # Limit to 5 per run to avoid rate limits
            pr_title = f"chore(deps): update {dep.name} from {dep.current_version} to {dep.latest_version}"
            branch_name = f"std-alert/update-{dep.ecosystem}-{dep.name.replace('/', '-')}-{dep.latest_version}"

            if pr_title in open_titles:
                logger.info(f"PR already exists for {dep.name}, skipping.")
                continue

            # Find matching vulnerability
            vuln_text = ""
            dep_vulns = [v for v in vulnerabilities if dep.name.lower() in v.affected_versions.lower()]
            if dep_vulns:
                vuln_text = f"\n\n### 🔐 Security Vulnerabilities Fixed\n"
                for v in dep_vulns:
                    vuln_text += f"- **{v.id}** ({v.severity.upper()}): {v.summary}\n"

            # Create branch
            branch_created = await github_client.create_branch(owner, repo_name, branch_name, from_branch=default_branch)
            if not branch_created:
                logger.warning(f"Failed to create branch {branch_name}")
                continue

            # Update file
            updated_any = False
            for fpath, fcontent in repo_files.items():
                new_content = None
                if fpath.endswith("requirements.txt") and dep.ecosystem == "pip":
                    new_content = updater.update_requirements_txt(fcontent, dep.name, dep.current_version, dep.latest_version)
                elif fpath.endswith("package.json") and dep.ecosystem == "npm":
                    new_content = updater.update_package_json(fcontent, dep.name, dep.current_version, dep.latest_version)
                elif "Dockerfile" in fpath and dep.ecosystem == "docker":
                    new_content = updater.update_dockerfile(fcontent, dep.name, dep.current_version, dep.latest_version)

                if new_content and new_content != fcontent:
                    await github_client.update_file(
                        owner=owner,
                        repo=repo_name,
                        path=fpath,
                        content=new_content,
                        message=f"bump {dep.name} to {dep.latest_version}",
                        branch=branch_name
                    )
                    updated_any = True

            if updated_any:
                pr_body = (
                    f"## 🛡️ STD Alert Dependency Update\n\n"
                    f"| Package | Current | Latest | Type |\n"
                    f"|---|---|---|---|\n"
                    f"| `{dep.name}` | `{dep.current_version}` | `{dep.latest_version}` | `{dep.update_type.upper()}` |\n"
                    f"{vuln_text}\n\n"
                    f"> *Automated PR generated by [STD Alert](https://github.com/TeamStdNetwork/std-alert) 🛡️*"
                )
                pr = await github_client.create_pull_request(
                    owner=owner,
                    repo=repo_name,
                    title=pr_title,
                    body=pr_body,
                    head=branch_name,
                    base=default_branch
                )
                if pr:
                    pr_created_count += 1
                    logger.info(f"✅ Successfully opened PR: #{pr.get('number')} for {dep.name}")

    # 7. Write GitHub Step Summary
    if summary_file:
        summary_md = [
            "# 🛡️ STD Alert Scan Report",
            "",
            f"**Repository:** `{repo_full_name}`",
            "",
            "### 📊 Scan Summary",
            f"- 📦 **Total Dependencies Scanned:** `{len(all_dependencies)}`",
            f"- 🔄 **Outdated Packages:** `{len(outdated)}`",
            f"- 🔐 **Known Vulnerabilities:** `{len(vulnerabilities)}`",
            f"- 🚨 **Secrets Leaked:** `{len(secrets_found)}`",
            f"- 🔀 **Pull Requests Raised:** `{pr_created_count}`",
            "",
        ]

        if secrets_found:
            summary_md.append("### 🚨 Leaked Secrets Alert")
            summary_md.append("| File | Line | Type | Recommendation |")
            summary_md.append("|---|---|---|---|")
            for s in secrets_found:
                summary_md.append(f"| `{s.file_path}` | `{s.line_number}` | `{s.secret_type}` | {s.recommendation} |")
            summary_md.append("")

        if outdated:
            summary_md.append("### 📦 Outdated Dependencies")
            summary_md.append("| Ecosystem | Package | Current | Latest | Type |")
            summary_md.append("|---|---|---|---|---|")
            for d in outdated[:10]:
                summary_md.append(f"| {d.ecosystem} | `{d.name}` | `{d.current_version}` | `{d.latest_version}` | `{d.update_type}` |")
            summary_md.append("")

        try:
            with open(summary_file, "a", encoding="utf-8") as f:
                f.write("\n".join(summary_md))
        except Exception as e:
            logger.warning(f"Could not write to step summary: {e}")

    logger.info("🎉 STD Alert Scan Completed Successfully!")

    if fail_on_critical and (secrets_found or any(v.severity == "critical" for v in vulnerabilities)):
        logger.error("Critical issues found and fail_on_critical is enabled. Exiting with error.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
