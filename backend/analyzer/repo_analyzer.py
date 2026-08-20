"""
Main repository analysis orchestrator.
Coordinates GitHub API calls, endpoint extraction, and license classification.
Sends progress updates via an async generator.
"""
from __future__ import annotations

import asyncio
import logging
from typing import AsyncGenerator, Optional

from .github_client import GitHubClient, parse_repo_url
from .endpoint_extractor import extract_endpoints
from .license_checker import classify_license, get_chain_caution_notes
from ..models.module import (
    AnalysisProgress,
    AnalysisStatus,
    LicenseCompatibility,
    Module,
)

logger = logging.getLogger(__name__)

# Files we will actually fetch content for (to keep API calls reasonable)
CONTENT_FETCH_FILES = {
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "package.json",
    "Cargo.toml",
    "Makefile",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "main.py",
    "app.py",
    "server.py",
    "api.py",
    "cli.py",
    "manage.py",
    "wsgi.py",
    "asgi.py",
    "openapi.json",
    "openapi.yaml",
    "openapi.yml",
    "swagger.json",
    "swagger.yaml",
}

# Secondary patterns — fetch if they exist and we haven't hit our budget
SECONDARY_PATTERNS = [
    "models.py",
    "schemas.py",
    "types.py",
    "__main__.py",
]

MAX_CONTENT_FILES = 20  # never fetch more than this many files


def _progress(
    status: AnalysisStatus,
    message: str,
    progress: float,
    module: Optional[Module] = None,
    error: Optional[str] = None,
) -> AnalysisProgress:
    return AnalysisProgress(
        status=status,
        message=message,
        progress=progress,
        module=module,
        error=error,
    )


async def analyze_repository(
    repo_url: str,
    github_token: Optional[str] = None,
) -> AsyncGenerator[AnalysisProgress, None]:
    """
    Async generator that yields AnalysisProgress events while analyzing a repo.
    Final event (status=DONE) contains the completed Module.
    """
    # --- Parse URL ---
    try:
        owner, repo_name = parse_repo_url(repo_url)
    except ValueError as e:
        yield _progress(AnalysisStatus.ERROR, str(e), 0.0, error=str(e))
        return

    async with GitHubClient(token=github_token) as client:
        # --- Step 1: Fetch repo metadata ---
        yield _progress(AnalysisStatus.FETCHING, f"Fetching metadata for {owner}/{repo_name}…", 0.05)
        try:
            repo_data = await client.get_repo(owner, repo_name)
        except (FileNotFoundError, PermissionError) as e:
            yield _progress(AnalysisStatus.ERROR, str(e), 0.0, error=str(e))
            return
        except Exception as e:
            msg = f"Failed to fetch repository: {e}"
            yield _progress(AnalysisStatus.ERROR, msg, 0.0, error=msg)
            return

        default_branch = repo_data.get("default_branch", "main")

        # --- Step 2: Fetch file tree ---
        yield _progress(AnalysisStatus.FETCHING, f"Fetching file tree ({default_branch})…", 0.15)
        try:
            tree = await client.get_file_tree(owner, repo_name, default_branch)
        except Exception as e:
            msg = f"Failed to fetch file tree: {e}"
            yield _progress(AnalysisStatus.ERROR, msg, 0.0, error=msg)
            return

        # --- Step 3: Fetch license + topics concurrently ---
        yield _progress(AnalysisStatus.FETCHING, "Fetching license and topics…", 0.25)
        import asyncio as _asyncio
        license_raw, topics = await _asyncio.gather(
            client.get_license(owner, repo_name),
            client.get_topics(owner, repo_name),
            return_exceptions=True,
        )
        if isinstance(license_raw, Exception):
            license_raw = {}
        if isinstance(topics, Exception):
            topics = []

        spdx_id = license_raw.get("license", {}).get("spdx_id")
        license_name = license_raw.get("license", {}).get("name", "")
        license_url = license_raw.get("html_url")
        license_info = classify_license(spdx_id, license_name)
        license_info.url = license_url

        # --- Step 5: Identify files to fetch ---
        tree_paths = {item["path"] for item in tree if item.get("type") == "blob"}
        files_to_fetch = list(CONTENT_FETCH_FILES & tree_paths)

        # Add secondary patterns (only files in tree)
        for p in SECONDARY_PATTERNS:
            for tp in tree_paths:
                if tp.endswith("/" + p) or tp == p:
                    if tp not in files_to_fetch:
                        files_to_fetch.append(tp)

        files_to_fetch = files_to_fetch[:MAX_CONTENT_FILES]

        # --- Step 6: Fetch file contents ---
        yield _progress(
            AnalysisStatus.FETCHING,
            f"Fetching {len(files_to_fetch)} key file(s)…",
            0.35,
        )

        file_contents: dict[str, str] = {}
        tasks = {
            path: client.get_file_content(owner, repo_name, path, default_branch)
            for path in files_to_fetch
        }
        # Fetch concurrently
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        for path, result in zip(tasks.keys(), results):
            if isinstance(result, str):
                file_contents[path] = result

        # --- Step 7: Extract endpoints ---
        yield _progress(AnalysisStatus.ANALYZING, "Analyzing endpoints…", 0.65)
        endpoints = extract_endpoints(tree, file_contents, repo_data)

        # --- Step 8: Build caution notes ---
        caution_notes = get_chain_caution_notes(license_info)

        is_chainable = license_info.compatibility not in (
            LicenseCompatibility.PROPRIETARY,
        )
        if license_info.compatibility == LicenseCompatibility.UNKNOWN:
            caution_notes.insert(
                0,
                "❓ License unknown — treat as all rights reserved until confirmed."
            )

        if not endpoints:
            caution_notes.append(
                "⚠️ No recognizable endpoints were automatically detected. "
                "Manual inspection required."
            )

        # --- Step 9: Assemble module ---
        yield _progress(AnalysisStatus.ANALYZING, "Assembling module…", 0.9)

        module = Module(
            repo_url=f"https://github.com/{owner}/{repo_name}",
            owner=owner,
            repo_name=repo_name,
            full_name=f"{owner}/{repo_name}",
            description=repo_data.get("description") or "",
            stars=repo_data.get("stargazers_count", 0),
            language=repo_data.get("language"),
            topics=topics,
            license=license_info,
            endpoints=endpoints,
            is_chainable=is_chainable,
            caution_notes=caution_notes,
        )

        yield _progress(
            AnalysisStatus.DONE,
            f"Analysis complete — {len(endpoints)} endpoint(s) detected.",
            1.0,
            module=module,
        )
