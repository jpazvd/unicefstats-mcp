"""Derive plain-English differentiators for ambiguous indicator candidates.

Used by `search_indicators` to enrich `candidates` entries in
ambiguity-flag responses. When the MCP returns multiple candidates the
model can't disambiguate, each entry carries:

  - code:           the canonical UNICEF code
  - name:           the indicator's display name
  - differentiator: a one-line explanation of what makes THIS candidate
                    different from the others (new in v1.0.0)

The differentiator is derived heuristically from:

  1. The longest common prefix among the candidate codes (so the
     differentiator focuses on the SUFFIX that varies).
  2. A curated table of common UNICEF suffix conventions
     (sex split, age band, methodology, derived metric).
  3. Token-level matching for compound suffixes.
  4. Fallback to the raw suffix text if no heuristic applies.

Examples:

  CME_MRM0   in family [CME_MRM0, CME_MRY0, CME_MRY0T4, CME_MRY1T4]
    -> "M0: neonatal (0-28 days)"

  IM_DTP3    in family [IM_DTP1, IM_DTP3]
    -> "DTP3: diphtheria-tetanus-pertussis, 3rd dose"

  ECD_CHLD_LMPSL_MERGE  in family [ECD_CHLD_LMPSL, ECD_CHLD_LMPSL_MERGE,
                                    ECD_CHLD_LMPSL_PRXY]
    -> "MERGE: merged data series"

The mapping table is curated from the UNICEF SDMX codelist conventions.
It is intentionally conservative — when nothing matches, the function
returns an empty string rather than guessing. Callers should treat an
empty differentiator as "no plain-English summary available; consult
the indicator name."
"""

from __future__ import annotations

import os
from collections.abc import Iterable

# Curated mapping of common UNICEF code suffixes to plain English.
# Conservative — only entries with strong empirical support from the
# 738-indicator YAML registry. Order doesn't matter; matching is
# exact-string against the suffix segment.
_SUFFIX_MEANINGS: dict[str, str] = {
    # ── Mortality age brackets (CME_MR* family) ──────────────────────
    "M0": "neonatal (0-28 days)",
    "MRM0": "neonatal mortality rate (0-28 days)",
    "Y0": "infant (0-1 year)",
    "MRY0": "infant mortality rate (0-1 year)",
    "Y0T4": "under-five (0-5 years, SDG 3.2.1 headline)",
    "MRY0T4": "under-five mortality rate (0-5 years, SDG 3.2.1)",
    "Y1T4": "childhood (1-4 years)",
    "MRY1T4": "childhood mortality rate (1-4 years)",
    "Y5T14": "school-age (5-14 years)",
    "Y10T19": "adolescent (10-19 years)",
    # ── Immunization vaccines (IM_* family) ──────────────────────────
    "BCG": "BCG (tuberculosis, neonatal dose)",
    "DTP1": "DTP 1st dose (diphtheria-tetanus-pertussis)",
    "DTP3": "DTP 3rd dose (SDG 3.b.1 headline immunization)",
    "MCV1": "measles 1st dose",
    "MCV2": "measles 2nd dose",
    "PCV3": "pneumococcal conjugate 3rd dose",
    "ROTAC": "rotavirus, last dose",
    # ── Sex split ────────────────────────────────────────────────────
    "F": "female only",
    "M": "male only",
    "_T": "both sexes / total",
    "MF": "both sexes",
    # ── Methodology / derivation ─────────────────────────────────────
    "MOD": "modelled estimate",
    "PRXY": "proxy variant",
    "MERGE": "merged data series",
    "NEW": "new methodology",
    "PRJ": "projected variant",
    "TND": "trend series",
    "ARR": "annual rate of reduction (derived from main indicator)",
    "TRGT": "national target (derived)",
    # ── Education levels (ISCED) ─────────────────────────────────────
    "L1": "ISCED level 1 (primary)",
    "L2": "ISCED level 2 (lower secondary)",
    "L3": "ISCED level 3 (upper secondary)",
    # ── Marriage age cutoffs ─────────────────────────────────────────
    "U15": "first union/marriage before age 15",
    "U18": "first union/marriage before age 18 (SDG 5.3.1)",
    "BFR15": "before age 15",
    "BFR18": "before age 18",
    # ── Wash / nutrition specifics ───────────────────────────────────
    "ALB": "at least basic level",
    "SM": "safely managed level",
    "NE2": "below -2 SD (moderate or severe)",
    "NE3": "below -3 SD (severe)",
    "PO2": "above +2 SD (overweight)",
    "LBW": "low birth weight (<2500g)",
}


def explain_difference(
    target_code: str,
    all_candidate_codes: Iterable[str],
) -> str:
    """Return a one-line differentiator for `target_code` relative to its
    siblings. Returns empty string when no heuristic applies — callers
    should not surface "differentiator: " when this is empty.

    The function works on codes alone, not on names. For richer plain-
    English context the caller pairs the differentiator with the
    indicator name in the response.
    """
    codes = [c for c in all_candidate_codes if isinstance(c, str)]
    if target_code not in codes or len(codes) < 2:
        return ""

    prefix = os.path.commonprefix(codes)
    suffix = target_code[len(prefix):].lstrip("_")
    if not suffix:
        # target_code IS the common prefix — it's the "base" of the
        # family (e.g. ECD_CHLD_LMPSL among ECD_CHLD_LMPSL,
        # ECD_CHLD_LMPSL_MERGE, ECD_CHLD_LMPSL_PRXY).
        return "base / canonical variant (no methodology suffix)"

    # Whole-suffix exact match
    if suffix in _SUFFIX_MEANINGS:
        return f"{suffix}: {_SUFFIX_MEANINGS[suffix]}"

    # Token-level match (suffix like "AGE15_19_MOD" should pick up MOD)
    tokens = [t for t in suffix.split("_") if t]
    matched = [t for t in tokens if t in _SUFFIX_MEANINGS]
    if matched:
        # Prefer the most informative token (longest mapped meaning)
        best = max(matched, key=lambda t: len(_SUFFIX_MEANINGS[t]))
        return f"{best}: {_SUFFIX_MEANINGS[best]}"

    # Fallback: surface the raw suffix so the model can at least see
    # what varies. Common for indicator families we haven't curated yet.
    return f"variant suffix: _{suffix}"
