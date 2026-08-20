"""
AI endpoint inferrer.
Uses the LLM to identify repository endpoints that static analysis missed,
by reading the README, file tree summary, and already-detected endpoints.
"""
from __future__ import annotations

import json
import logging
import re
from typing import AsyncGenerator, Optional

from .lm_studio_client import LMStudioClient
from ..models.module import Endpoint, EndpointType, Module
from ..analyzer.github_client import GitHubClient

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are an expert software architect who specializes in analyzing open-source repositories.
Your job is to identify all public interfaces, endpoints, and integration points that a repository exposes.
Be thorough but accurate. Only list real, documented or clearly implied interfaces — never invent things.
Always respond with valid JSON only, no explanation or markdown fences."""

INFER_PROMPT_TEMPLATE = """\
Repository: {full_name}
Description: {description}
Primary language: {language}
License: {license}

=== Already detected (by static analysis) ===
{detected_endpoints}

=== File tree sample (first 80 paths) ===
{file_tree_sample}

=== README (first 3000 chars) ===
{readme}

=== Task ===
Identify additional public endpoints or interfaces this repository exposes that are NOT already listed above.
Consider: REST APIs, CLIs, Python/JS/Rust library APIs, data schemas, Docker images, ML model inference APIs,
WebSocket servers, event systems, gRPC/GraphQL services, config file formats the tool reads, plugin systems, etc.

Return ONLY a JSON array. Each item must have these exact keys:
- "name": short display name (string)
- "type": one of: rest_api, cli, library, data_file, data_structure, docker, ml_model, graphql, grpc, unknown
- "description": 1-2 clear sentences explaining what this interface does and how to use it
- "is_output": true if this produces/exposes something, false if this consumes input

Return [] if you find nothing new.
Example: [{{"name": "Python SDK", "type": "library", "description": "...", "is_output": true}}]"""


async def infer_endpoints(
    module: Module,
    github_token: Optional[str] = None,
    lm_url: str = "http://localhost:1234",
    model: Optional[str] = None,
) -> AsyncGenerator[dict, None]:
    """
    Async generator that yields progress events and finally a list of inferred Endpoint objects.

    Yields dicts:
      {"type": "progress", "message": "..."}
      {"type": "token",    "text": "..."}        — streaming LLM output
      {"type": "done",     "endpoints": [...]}   — final parsed endpoints
      {"type": "error",    "message": "..."}
    """
    yield {"type": "progress", "message": "Fetching README from GitHub…"}

    readme = ""
    file_tree_sample = ""
    try:
        async with GitHubClient(token=github_token) as gh:
            # Try common README file names
            for readme_name in ["README.md", "README.rst", "README.txt", "README"]:
                content = await gh.get_file_content(
                    module.owner, module.repo_name, readme_name
                )
                if content:
                    readme = content[:3000]
                    break

            # Get file tree for context
            try:
                tree = await gh.get_file_tree(module.owner, module.repo_name)
                paths = [item["path"] for item in tree if item.get("type") == "blob"]
                file_tree_sample = "\n".join(paths[:80])
            except Exception:
                file_tree_sample = "(could not fetch file tree)"
    except Exception as e:
        yield {"type": "progress", "message": f"Warning: could not fetch README ({e}). Proceeding with available data."}

    # Format already-detected endpoints
    detected = module.endpoints
    if detected:
        detected_str = "\n".join(
            f"- [{ep.type.value}] {ep.name}: {ep.description}" for ep in detected
        )
    else:
        detected_str = "(none detected by static analysis)"

    prompt = INFER_PROMPT_TEMPLATE.format(
        full_name=module.full_name,
        description=module.description or "No description provided.",
        language=module.language or "unknown",
        license=module.license.name if module.license else "unknown",
        detected_endpoints=detected_str,
        file_tree_sample=file_tree_sample or "(not available)",
        readme=readme or "(no README found)",
    )

    yield {"type": "progress", "message": "Asking LLM to analyze the repository…"}

    full_response = ""
    try:
        async with LMStudioClient(base_url=lm_url) as lm:
            async for token in lm.stream_chat(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                model=model,
                temperature=0.2,
                max_tokens=1500,
            ):
                full_response += token
                yield {"type": "token", "text": token}
    except Exception as e:
        yield {"type": "error", "message": str(e)}
        return

    # Parse the JSON response
    yield {"type": "progress", "message": "Parsing LLM response…"}
    endpoints = _parse_endpoints(full_response)

    yield {"type": "done", "endpoints": [ep.model_dump(mode="json") for ep in endpoints]}


def _parse_endpoints(raw: str) -> list[Endpoint]:
    """Extract and validate the JSON array from an LLM response."""
    # Strip markdown fences if present
    raw = re.sub(r"```(?:json)?", "", raw).strip().strip("`")

    # Find first [ ... ] block
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        logger.warning("LLM response did not contain a JSON array: %s", raw[:200])
        return []

    try:
        items = json.loads(match.group(0))
    except json.JSONDecodeError as e:
        logger.warning("Failed to parse LLM JSON: %s | raw: %s", e, raw[:200])
        return []

    endpoints: list[Endpoint] = []
    for item in items:
        if not isinstance(item, dict) or "name" not in item:
            continue
        try:
            ep_type = EndpointType(item.get("type", "unknown"))
        except ValueError:
            ep_type = EndpointType.UNKNOWN

        endpoints.append(Endpoint(
            name=str(item.get("name", "Unknown"))[:80],
            type=ep_type,
            description=str(item.get("description", ""))[:500],
            is_output=bool(item.get("is_output", True)),
            source="ai",
        ))

    return endpoints
