"""
GitHub API client for fetching repository metadata and file trees.
"""
from __future__ import annotations

import base64
import logging
from typing import Any, AsyncGenerator, Optional
import httpx

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
GITHUB_RAW = "https://raw.githubusercontent.com"


class GitHubClient:
    def __init__(self, token: Optional[str] = None):
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.AsyncClient(
            headers=headers,
            timeout=30.0,
            follow_redirects=True,
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self._client.aclose()

    async def close(self):
        await self._client.aclose()

    def _raise_for_status(self, resp: httpx.Response) -> None:
        if resp.status_code == 403:
            raise PermissionError(
                "GitHub API rate limit exceeded or authentication required. "
                "Please provide a valid GitHub Personal Access Token."
            )
        if resp.status_code == 404:
            raise FileNotFoundError("Repository not found. Check the URL and that it is public.")
        resp.raise_for_status()

    async def get_repo(self, owner: str, repo: str) -> dict[str, Any]:
        """Fetch top-level repository metadata."""
        resp = await self._client.get(f"{GITHUB_API}/repos/{owner}/{repo}")
        self._raise_for_status(resp)
        return resp.json()

    async def get_license(self, owner: str, repo: str) -> dict[str, Any]:
        """Fetch license information for the repository."""
        resp = await self._client.get(f"{GITHUB_API}/repos/{owner}/{repo}/license")
        if resp.status_code == 404:
            return {}
        self._raise_for_status(resp)
        return resp.json()

    async def get_file_tree(self, owner: str, repo: str, branch: str = "HEAD") -> list[dict]:
        """
        Fetch the full recursive file tree of the repository.
        Returns a flat list of file/directory entries.
        """
        resp = await self._client.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{branch}",
            params={"recursive": "1"},
        )
        if resp.status_code == 409:
            # Empty repository
            return []
        self._raise_for_status(resp)
        data = resp.json()
        return data.get("tree", [])

    async def get_file_content(
        self, owner: str, repo: str, path: str, branch: str = "HEAD"
    ) -> Optional[str]:
        """
        Fetch the decoded text content of a specific file.
        Returns None if the file is binary or too large.
        """
        resp = await self._client.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}",
            params={"ref": branch},
        )
        if resp.status_code == 404:
            return None
        self._raise_for_status(resp)
        data = resp.json()

        # Respect size limit (GitHub caps at 1MB via this endpoint)
        if data.get("size", 0) > 500_000:
            return None
        encoding = data.get("encoding", "")
        content = data.get("content", "")
        if encoding == "base64":
            try:
                return base64.b64decode(content).decode("utf-8", errors="replace")
            except Exception:
                return None
        return content or None

    async def get_topics(self, owner: str, repo: str) -> list[str]:
        """Fetch repository topics."""
        resp = await self._client.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/topics",
            headers={"Accept": "application/vnd.github.mercy-preview+json"},
        )
        if resp.status_code != 200:
            return []
        return resp.json().get("names", [])

    async def get_default_branch(self, repo_data: dict) -> str:
        """Extract default branch from repo metadata dict."""
        return repo_data.get("default_branch", "HEAD")


def parse_repo_url(url: str) -> tuple[str, str]:
    """
    Parse a GitHub URL or 'owner/repo' string into (owner, repo).
    Supports:
      - https://github.com/owner/repo
      - https://github.com/owner/repo.git
      - owner/repo
    """
    url = url.strip().rstrip("/")
    if url.startswith("https://github.com/"):
        path = url.replace("https://github.com/", "")
    elif url.startswith("github.com/"):
        path = url.replace("github.com/", "")
    else:
        path = url

    if path.endswith(".git"):
        path = path[:-4]
    parts = [p for p in path.split("/") if p]
    if len(parts) < 2:
        raise ValueError(f"Cannot parse repository URL: '{url}'. Expected format: owner/repo")
    return parts[0], parts[1]
