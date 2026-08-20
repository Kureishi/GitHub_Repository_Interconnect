"""
Flow reporter.
Uses the LLM to generate a structured narrative report about a module graph —
describing the data pipeline, transformations, bottlenecks, and license concerns.
Streams the markdown response token-by-token.
"""
from __future__ import annotations

import logging
from typing import AsyncGenerator, Optional

from .lm_studio_client import LMStudioClient
from ..models.module import Connection, Module

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a senior software architect who specializes in analyzing data pipelines and software integration patterns.
Given a set of software modules and the connections between them, write a comprehensive technical report.
Use clear markdown formatting with headers, bullet points, and tables where appropriate.
Be specific and actionable. Flag real risks, not hypothetical ones."""

REPORT_PROMPT_TEMPLATE = """\
You are analyzing a module graph with {module_count} module(s) and {connection_count} connection(s).

=== MODULES ===
{modules_section}

=== CONNECTIONS (Data Flow) ===
{connections_section}

=== TASK ===
Write a structured technical report with the following sections:

## 1. Pipeline Overview
Describe the overall architecture and purpose of this connected system in 2-3 paragraphs.
What does this pipeline accomplish end-to-end?

## 2. Data Flow Analysis
For each connection, explain what data flows between the modules, what transformations
likely occur, and whether the interface pairing makes sense technically.

## 3. License & Compliance Concerns
Identify any license compatibility issues. Flag any GPL/AGPL modules in the chain.
Explain what these mean for the end user or product.

## 4. Potential Bottlenecks & Risks
What could go wrong? Identify: rate limits, single points of failure, version
incompatibilities, missing authentication, or tight coupling between modules.

## 5. Recommendations
Suggest: better module pairings, missing middleware, alternative approaches, or
improvements to the current architecture.

Write in a professional but accessible tone. Use markdown formatting throughout."""


def _format_modules(modules: list[Module]) -> str:
    lines = []
    for mod in modules:
        lines.append(f"### {mod.full_name}")
        lines.append(f"- **Description**: {mod.description or 'No description'}")
        lines.append(f"- **Language**: {mod.language or 'unknown'}")
        lines.append(f"- **License**: {mod.license.name} ({mod.license.compatibility.value})")
        lines.append(f"- **Stars**: {mod.stars:,}")
        if mod.endpoints:
            lines.append(f"- **Endpoints** ({len(mod.endpoints)}):")
            for ep in mod.endpoints:
                ai_tag = " [AI-inferred]" if ep.source == "ai" else ""
                lines.append(f"  - [{ep.type.value}] **{ep.name}**{ai_tag}: {ep.description}")
        if mod.caution_notes:
            for note in mod.caution_notes:
                lines.append(f"- ⚠️ {note}")
        lines.append("")
    return "\n".join(lines)


def _format_connections(
    connections: list[Connection],
    modules_by_id: dict[str, Module],
) -> str:
    if not connections:
        return "No connections defined yet."

    lines = []
    for i, conn in enumerate(connections, 1):
        src_mod = modules_by_id.get(conn.source_module_id)
        tgt_mod = modules_by_id.get(conn.target_module_id)

        # Find endpoint names
        src_ep_name = conn.source_endpoint_id
        tgt_ep_name = conn.target_endpoint_id
        if src_mod:
            for ep in src_mod.endpoints:
                if conn.source_endpoint_id in (ep.id, f"{ep.id}-out"):
                    src_ep_name = ep.name
                    break
        if tgt_mod:
            for ep in tgt_mod.endpoints:
                if conn.target_endpoint_id in (ep.id, f"{ep.id}-in"):
                    tgt_ep_name = ep.name
                    break

        src_name = src_mod.full_name if src_mod else conn.source_module_id
        tgt_name = tgt_mod.full_name if tgt_mod else conn.target_module_id
        lines.append(
            f"{i}. **{src_name}** [{src_ep_name}] → **{tgt_name}** [{tgt_ep_name}]"
        )
        if conn.label:
            lines.append(f"   Label: {conn.label}")
    return "\n".join(lines)


async def stream_flow_report(
    modules: list[Module],
    connections: list[Connection],
    lm_url: str = "http://localhost:1234",
    model: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """
    Stream a markdown flow report about the current module graph.
    Yields string tokens as they arrive from the LLM.
    """
    if not modules:
        yield "# No Modules\n\nAdd some GitHub repositories to the canvas first."
        return

    modules_by_id = {m.id: m for m in modules}

    prompt = REPORT_PROMPT_TEMPLATE.format(
        module_count=len(modules),
        connection_count=len(connections),
        modules_section=_format_modules(modules),
        connections_section=_format_connections(connections, modules_by_id),
    )

    async with LMStudioClient(base_url=lm_url) as lm:
        async for token in lm.stream_chat(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            model=model,
            temperature=0.4,
            max_tokens=3000,
        ):
            yield token
