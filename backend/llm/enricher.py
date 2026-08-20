"""
AI description enricher.
Uses the LLM to rewrite raw auto-generated endpoint descriptions into clear,
natural language sentences that are actually useful to a developer.
"""
from __future__ import annotations

import logging
from typing import Optional

from .lm_studio_client import LMStudioClient
from ..models.module import Endpoint, Module

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a technical writer who specializes in writing concise, accurate documentation for developer tools.
Given information about a software endpoint or interface, rewrite its description in 1-2 clear sentences.
Focus on: what it does, how a developer would use it, and what data flows in/out.
Be concrete, not vague. Avoid filler words like "powerful", "robust", "seamless".
Return ONLY the rewritten description text, nothing else."""


async def enrich_module_endpoints(
    module: Module,
    lm_url: str = "http://localhost:1234",
    model: Optional[str] = None,
) -> list[Endpoint]:
    """
    Enrich all static endpoints in a module with improved LLM descriptions.
    Returns the updated list of endpoints (only static ones are enriched; AI ones are left as-is).
    """
    enriched: list[Endpoint] = []

    async with LMStudioClient(base_url=lm_url) as lm:
        for ep in module.endpoints:
            if ep.source == "ai":
                # AI-inferred endpoints already have good descriptions
                enriched.append(ep)
                continue

            prompt = (
                f"Repository: {module.full_name} ({module.description or 'no description'})\n"
                f"Endpoint name: {ep.name}\n"
                f"Endpoint type: {ep.type.value}\n"
                f"Current description: {ep.description or '(none)'}\n"
                f"Details: {ep.details}\n\n"
                f"Rewrite the description in 1-2 clear, concrete sentences for a developer."
            )

            try:
                new_description = await lm.complete_chat(
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    model=model,
                    temperature=0.2,
                    max_tokens=150,
                )
                new_description = new_description.strip().strip('"').strip("'")
                # Keep original if LLM returned nothing useful
                if len(new_description) > 10:
                    ep = ep.model_copy(update={"description": new_description})
            except Exception as e:
                logger.warning("Failed to enrich endpoint %s: %s", ep.name, e)

            enriched.append(ep)

    return enriched
