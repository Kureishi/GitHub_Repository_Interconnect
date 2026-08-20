"""
License detection and chain-compatibility classifier.
"""
from __future__ import annotations

from typing import Optional
from ..models.module import LicenseInfo, LicenseCompatibility

# SPDX → compatibility classification
_LICENSE_MAP: dict[str, tuple[LicenseCompatibility, Optional[str]]] = {
    # Permissive — freely chainable
    "MIT": (LicenseCompatibility.PERMISSIVE, None),
    "Apache-2.0": (LicenseCompatibility.PERMISSIVE, None),
    "BSD-2-Clause": (LicenseCompatibility.PERMISSIVE, None),
    "BSD-3-Clause": (LicenseCompatibility.PERMISSIVE, None),
    "ISC": (LicenseCompatibility.PERMISSIVE, None),
    "0BSD": (LicenseCompatibility.PERMISSIVE, None),
    "Unlicense": (LicenseCompatibility.PERMISSIVE, None),
    "CC0-1.0": (LicenseCompatibility.PERMISSIVE, None),
    "BSL-1.0": (LicenseCompatibility.PERMISSIVE, None),
    "Zlib": (LicenseCompatibility.PERMISSIVE, None),
    "PostgreSQL": (LicenseCompatibility.PERMISSIVE, None),
    # Weak copyleft — chainable with care
    "LGPL-2.0": (
        LicenseCompatibility.COPYLEFT_WEAK,
        "LGPL-2.0: You may link against this module, but modifications to the library itself "
        "must be released under LGPL. Dynamic linking is generally safe.",
    ),
    "LGPL-2.1": (
        LicenseCompatibility.COPYLEFT_WEAK,
        "LGPL-2.1: Linking is permitted. Modifications to this library must remain LGPL.",
    ),
    "LGPL-3.0": (
        LicenseCompatibility.COPYLEFT_WEAK,
        "LGPL-3.0: Chaining allowed if you comply with LGPL-3.0 terms for the library itself.",
    ),
    "MPL-2.0": (
        LicenseCompatibility.COPYLEFT_WEAK,
        "MPL-2.0: File-level copyleft. You can combine with proprietary code, "
        "but modified MPL files must remain MPL.",
    ),
    "CDDL-1.0": (
        LicenseCompatibility.COPYLEFT_WEAK,
        "CDDL-1.0: File-level copyleft — similar constraints to MPL.",
    ),
    "EPL-1.0": (
        LicenseCompatibility.COPYLEFT_WEAK,
        "EPL-1.0: Weak copyleft. Modules can be combined, but EPL code changes stay EPL.",
    ),
    "EPL-2.0": (
        LicenseCompatibility.COPYLEFT_WEAK,
        "EPL-2.0: Similar to EPL-1.0 with explicit patent grants.",
    ),
    # Strong copyleft — chain propagates license
    "GPL-2.0": (
        LicenseCompatibility.COPYLEFT_STRONG,
        "GPL-2.0: Any work that incorporates this module must also be released under GPL-2.0. "
        "This will 'infect' connected proprietary modules.",
    ),
    "GPL-3.0": (
        LicenseCompatibility.COPYLEFT_STRONG,
        "GPL-3.0: Strong copyleft. The entire chain including your code must be GPL-3.0 if "
        "you distribute a linked binary.",
    ),
    "AGPL-3.0": (
        LicenseCompatibility.COPYLEFT_STRONG,
        "AGPL-3.0: Extends GPL to network use — even SaaS usage requires source disclosure. "
        "Treat as non-chainable for most commercial scenarios.",
    ),
    "EUPL-1.1": (
        LicenseCompatibility.COPYLEFT_STRONG,
        "EUPL-1.1: Strong copyleft under EU law.",
    ),
    "EUPL-1.2": (
        LicenseCompatibility.COPYLEFT_STRONG,
        "EUPL-1.2: Strong copyleft under EU law.",
    ),
}


def classify_license(spdx_id: Optional[str], license_name: str = "") -> LicenseInfo:
    """
    Given a SPDX identifier and/or license name, return a LicenseInfo with
    compatibility classification and optional chain warning.
    """
    if spdx_id and spdx_id != "NOASSERTION":
        key = spdx_id.strip()
        if key in _LICENSE_MAP:
            compat, warning = _LICENSE_MAP[key]
            return LicenseInfo(
                spdx_id=spdx_id,
                name=license_name or spdx_id,
                compatibility=compat,
                chain_warning=warning,
            )

    # Fuzzy fallback on name
    name_lower = license_name.lower()
    if "agpl" in name_lower:
        compat, warning = _LICENSE_MAP["AGPL-3.0"]
        return LicenseInfo(
            spdx_id=spdx_id, name=license_name, compatibility=compat, chain_warning=warning
        )
    if "gpl" in name_lower and "lesser" not in name_lower and "lgpl" not in name_lower:
        compat, warning = _LICENSE_MAP["GPL-3.0"]
        return LicenseInfo(
            spdx_id=spdx_id, name=license_name, compatibility=compat, chain_warning=warning
        )
    if "lgpl" in name_lower or "lesser" in name_lower:
        compat, warning = _LICENSE_MAP["LGPL-3.0"]
        return LicenseInfo(
            spdx_id=spdx_id, name=license_name, compatibility=compat, chain_warning=warning
        )
    if "mit" in name_lower:
        return LicenseInfo(
            spdx_id=spdx_id, name=license_name, compatibility=LicenseCompatibility.PERMISSIVE
        )
    if "apache" in name_lower:
        return LicenseInfo(
            spdx_id=spdx_id, name=license_name, compatibility=LicenseCompatibility.PERMISSIVE
        )
    if "bsd" in name_lower:
        return LicenseInfo(
            spdx_id=spdx_id, name=license_name, compatibility=LicenseCompatibility.PERMISSIVE
        )
    if "proprietary" in name_lower or "commercial" in name_lower:
        return LicenseInfo(
            spdx_id=spdx_id,
            name=license_name,
            compatibility=LicenseCompatibility.PROPRIETARY,
            chain_warning="This module uses a proprietary license. Chaining or redistribution "
            "may require explicit permission from the copyright holder.",
        )

    return LicenseInfo(
        spdx_id=spdx_id,
        name=license_name or "No license detected",
        compatibility=LicenseCompatibility.UNKNOWN,
        chain_warning="No recognized license was detected. Assume all rights reserved. "
        "Do not chain without explicit permission from the author.",
    )


def get_chain_caution_notes(license_info: LicenseInfo) -> list[str]:
    """Build human-readable caution notes for the UI."""
    notes: list[str] = []
    if license_info.compatibility == LicenseCompatibility.UNKNOWN:
        notes.append(
            "⚠️ No license detected — chaining may infringe on the author's rights."
        )
    elif license_info.compatibility == LicenseCompatibility.PROPRIETARY:
        notes.append(
            "🔒 Proprietary license — contact the copyright holder before chaining."
        )
    elif license_info.compatibility == LicenseCompatibility.COPYLEFT_STRONG:
        notes.append(
            f"⚠️ Strong copyleft ({license_info.name}) — linking this module may require your "
            "entire pipeline to be released under the same license."
        )
    elif license_info.compatibility == LicenseCompatibility.COPYLEFT_WEAK:
        notes.append(
            f"ℹ️ Weak copyleft ({license_info.name}) — modifications to this library must stay "
            "under the same license, but your application code can remain separate."
        )
    return notes
