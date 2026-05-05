"""Indicator-name → code resolver for `get_data`.

Added in v0.7.0 to address the indicator-name failure mode (the model
calls `get_data(indicator='CME_MRY0T4')` thinking it's neonatal mortality
when it's actually under-five mortality, or hallucinates similar codes
like `CME_MRY0T4_F`). With this resolver, `get_data` accepts indicator
codes OR human-readable names; the server canonicalizes whichever the
model passes.

Mirrors the v0.6.2 country_resolver pattern. Loads the 738-indicator
metadata shipped by `unicefdata` (`_unicefdata_indicators_metadata.yaml`)
and builds a normalized name→code index. Curates a SYNONYMS table for
common phrasings ("neonatal mortality", "stunting", "U5MR", etc.) and
an AMBIGUOUS table for terms that legitimately match multiple codes
("child mortality" → NMR / IMR / U5MR / 1-4 mortality).

Returns an `IndicatorResolution` dataclass with explicit status:

  code_passthrough — input was already a valid code (no resolution needed)
  synonym_match    — matched a curated synonym
  name_index_hit   — exact match against the canonical-name index
  ambiguous        — matched multiple codes; caller must disambiguate
  unknown          — no match found
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from functools import lru_cache

# Curated synonyms — colloquial phrasing → unique canonical code.
# Only enter mappings that resolve unambiguously to ONE canonical leaf
# (tier=1) indicator. Ambiguous phrases go in _AMBIGUOUS below.
_SYNONYMS: dict[str, str] = {
    # ── Mortality ────────────────────────────────────────────────────
    "neonatal mortality": "CME_MRM0",
    "neonatal mortality rate": "CME_MRM0",
    "nmr": "CME_MRM0",
    "infant mortality": "CME_MRY0",
    "infant mortality rate": "CME_MRY0",
    "imr": "CME_MRY0",
    "under-five mortality": "CME_MRY0T4",
    "under five mortality": "CME_MRY0T4",
    "under-five mortality rate": "CME_MRY0T4",
    "under five mortality rate": "CME_MRY0T4",
    "under 5 mortality": "CME_MRY0T4",
    "u5mr": "CME_MRY0T4",
    "stillbirth rate": "CME_SBR",
    "sbr": "CME_SBR",
    # ── Nutrition ────────────────────────────────────────────────────
    "stunting": "NT_ANT_HAZ_NE2",
    "stunting prevalence": "NT_ANT_HAZ_NE2",
    "stunting rate": "NT_ANT_HAZ_NE2",
    "wasting": "NT_ANT_WHZ_NE2",
    "wasting prevalence": "NT_ANT_WHZ_NE2",
    "wasting rate": "NT_ANT_WHZ_NE2",
    "underweight": "NT_ANT_WAZ_NE2",
    "underweight prevalence": "NT_ANT_WAZ_NE2",
    "overweight": "NT_ANT_WHZ_PO2",
    "overweight prevalence": "NT_ANT_WHZ_PO2",
    "low birth weight": "NT_BW_LBW",
    "low birthweight": "NT_BW_LBW",
    "lbw": "NT_BW_LBW",
    "lbw prevalence": "NT_BW_LBW",
    # ── Education ────────────────────────────────────────────────────
    "primary completion rate": "ED_CR_L1",
    "primary school completion rate": "ED_CR_L1",
    "primary completion": "ED_CR_L1",
    "youth literacy rate": "ED_15-24_LR",
    "youth literacy": "ED_15-24_LR",
    "literacy rate 15-24": "ED_15-24_LR",
    # ── WASH ─────────────────────────────────────────────────────────
    "basic drinking water": "WS_PPL_W-ALB",
    "drinking water access": "WS_PPL_W-ALB",
    "safely managed drinking water": "WS_PPL_W-SM",
    # ── Immunization ─────────────────────────────────────────────────
    "bcg coverage": "IM_BCG",
    "bcg vaccination": "IM_BCG",
    "dtp1 coverage": "IM_DTP1",
    "dtp1 vaccination": "IM_DTP1",
    "dtp3 coverage": "IM_DTP3",
    "dtp3 vaccination": "IM_DTP3",
    # ── MNCH ─────────────────────────────────────────────────────────
    "antenatal care": "MNCH_ANC1",
    "antenatal care 1": "MNCH_ANC1",
    "anc1": "MNCH_ANC1",
    "anc 1": "MNCH_ANC1",
    # Note: do NOT add "anc 1+" here — `_normalize` strips '+' as a separator,
    # so the lookup key would never match. Use the post-normalize form above.
    "skilled birth attendant": "MNCH_SAB",
    "skilled birth attendance": "MNCH_SAB",
    "skilled attendance at birth": "MNCH_SAB",
    "sab": "MNCH_SAB",
    # ── Child protection ─────────────────────────────────────────────
    "fgm prevalence": "PT_F_15-49_FGM",
    "female genital mutilation": "PT_F_15-49_FGM",
}

# Phrases that legitimately match multiple codes — refuse with
# disambiguation list rather than silently picking one. The list of
# codes is filtered against the loaded index at lookup time so stale
# entries don't crash the resolver.
_AMBIGUOUS: dict[str, list[str]] = {
    "child mortality": ["CME_MRM0", "CME_MRY0", "CME_MRY0T4", "CME_MRY1T4"],
    "child mortality rate": ["CME_MRY0T4", "CME_MRY1T4"],
    "mortality rate": ["CME_MRM0", "CME_MRY0", "CME_MRY0T4", "CME_MRY1T4"],
    "vaccination coverage": ["IM_BCG", "IM_DTP1", "IM_DTP3", "IM_MCV1", "IM_MCV2"],
    "vaccination": ["IM_BCG", "IM_DTP1", "IM_DTP3", "IM_MCV1", "IM_MCV2"],
    "immunization coverage": ["IM_BCG", "IM_DTP1", "IM_DTP3", "IM_MCV1", "IM_MCV2"],
    "child marriage": ["PT_F_15-19_MRD", "PT_F_18-19_MRD", "PT_F_15-49_MRD_18"],
}


def _normalize(s: str) -> str:
    """Lowercase, strip diacritics, drop punctuation, collapse whitespace.

    Keeps hyphens (e.g., `ED_15-24_LR`) so they survive the round-trip
    when callers pass codes verbatim.

    Examples:
      "Under-Five Mortality Rate" → "under-five mortality rate"
      "ANC1+"                     → "anc1"
      "Côte d'Ivoire stunting"    → "cote divoire stunting"
    """
    if not isinstance(s, str):
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    out: list[str] = []
    prev_space = False
    for c in s:
        if c.isalnum() or c == "-":
            out.append(c)
            prev_space = False
        elif c in " _/.,()+":
            if not prev_space:
                out.append(" ")
                prev_space = True
        # else: drop apostrophes, quotes, brackets, etc.
    return "".join(out).strip()


@dataclass(frozen=True)
class IndicatorResolution:
    """Result of resolving an indicator input.

    Always returned (never raises). The `status` field tells the caller
    what to do next; on `ambiguous`, `candidates` is non-empty.
    """

    status: str  # see module docstring for the 5 valid values
    code: str | None = None
    name: str | None = None
    candidates: tuple[tuple[str, str], ...] = ()
    original_input: str = ""


@lru_cache(maxsize=1)
def _load_indicator_index() -> tuple[dict[str, str], dict[str, list[str]]]:
    """Load the unicefdata indicators YAML and build code-set + name-index.

    Returns:
      - code_to_name: every code (tier 1 + tier 2) → canonical display name.
        Used for code passthrough and for resolving canonical names of
        already-known codes (e.g., when echoing in resolution_info).
      - name_to_codes: normalized canonical name → list of matching codes.
        Only tier=1 (real-data-bearing) indicators are indexed by name —
        tier=2 are aggregates/categories that aren't valid for get_data.
    """
    import os

    import unicefdata
    import yaml  # type: ignore[import-untyped]

    yaml_path = os.path.join(
        os.path.dirname(unicefdata.__file__),
        "metadata", "current", "_unicefdata_indicators_metadata.yaml",
    )
    if not os.path.exists(yaml_path):
        return {}, {}

    with open(yaml_path, encoding="utf-8") as f:
        doc = yaml.safe_load(f)

    inds = doc.get("indicators", {}) or {}
    code_to_name: dict[str, str] = {}
    name_to_codes: dict[str, list[str]] = {}
    for code, meta in inds.items():
        if not isinstance(code, str) or not isinstance(meta, dict):
            continue
        name = meta.get("name") or ""
        tier = meta.get("tier", 2)
        code_to_name[code] = name if isinstance(name, str) else ""
        if tier == 1 and isinstance(name, str) and name:
            normalized = _normalize(name)
            if normalized:
                name_to_codes.setdefault(normalized, []).append(code)
    return code_to_name, name_to_codes


def resolve_indicator(input_str: str) -> IndicatorResolution:
    """Resolve a single user input (indicator code or name) to canonical code(s).

    Always returns an IndicatorResolution. Inspect `.status` to decide:
      - "code_passthrough" / "synonym_match" / "name_index_hit" → use `.code`
      - "ambiguous" → present `.candidates` to the user / model and refuse
      - "unknown" → caller decides. `get_data` passes the original string
        through to the SDMX call (which will 404 if the code doesn't exist),
        preserving backward compatibility with codes added upstream after
        the YAML snapshot. Other callers may prefer to error early.
    """
    if not isinstance(input_str, str):
        return IndicatorResolution(status="unknown", original_input=str(input_str))
    s = input_str.strip()
    if not s:
        return IndicatorResolution(status="unknown", original_input=input_str)

    code_to_name, name_to_codes = _load_indicator_index()

    # Fast path: exact code match (case-insensitive against the YAML's keys).
    # The YAML uses uppercase codes throughout, but accept any case from the
    # caller. Compare upper-to-upper to find the canonical key.
    upper_s = s.upper()
    if upper_s in code_to_name:
        return IndicatorResolution(
            status="code_passthrough",
            code=upper_s,
            name=code_to_name.get(upper_s),
            original_input=input_str,
        )

    normalized = _normalize(s)

    # Curated synonyms: deterministic 1-to-1 mapping.
    if normalized in _SYNONYMS:
        code = _SYNONYMS[normalized]
        # Defensive: only return the synonym if it's actually a known code
        # (protects against codelist drift dropping an indicator we synonym'd).
        if code in code_to_name:
            return IndicatorResolution(
                status="synonym_match",
                code=code,
                name=code_to_name.get(code),
                original_input=input_str,
            )

    # Curated ambiguous phrases: refuse with disambiguation list.
    if normalized in _AMBIGUOUS:
        candidate_codes = [c for c in _AMBIGUOUS[normalized] if c in code_to_name]
        if len(candidate_codes) == 1:
            # Only one candidate survives the codelist filter — collapse to a
            # synonym match.
            code = candidate_codes[0]
            return IndicatorResolution(
                status="synonym_match",
                code=code,
                name=code_to_name.get(code),
                original_input=input_str,
            )
        if len(candidate_codes) > 1:
            return IndicatorResolution(
                status="ambiguous",
                candidates=tuple(
                    (c, code_to_name.get(c, "")) for c in candidate_codes
                ),
                original_input=input_str,
            )

    # Exact match against the canonical-name index.
    if normalized in name_to_codes:
        codes = name_to_codes[normalized]
        if len(codes) == 1:
            return IndicatorResolution(
                status="name_index_hit",
                code=codes[0],
                name=code_to_name.get(codes[0]),
                original_input=input_str,
            )
        return IndicatorResolution(
            status="ambiguous",
            candidates=tuple((c, code_to_name.get(c, "")) for c in codes),
            original_input=input_str,
        )

    return IndicatorResolution(status="unknown", original_input=input_str)


def resolve_indicators(
    inputs: list[str],
) -> tuple[list[IndicatorResolution], list[str]]:
    """Resolve a list of indicator inputs.

    Returns:
      - resolutions: one IndicatorResolution per input (same length).
        Caller decides what to do based on each `.status`.
      - resolved_codes: convenience list of just the canonical codes for
        inputs that resolved unambiguously. Length ≤ len(inputs).

    The caller (get_data) typically wants to fail the whole call if ANY
    input came back ambiguous or unknown, so the list-of-resolutions
    return makes the per-input status visible without losing information.
    """
    resolutions = [resolve_indicator(s) for s in inputs]
    resolved_codes = [
        r.code for r in resolutions
        if r.status in ("code_passthrough", "synonym_match", "name_index_hit")
        and r.code is not None
    ]
    return resolutions, resolved_codes
