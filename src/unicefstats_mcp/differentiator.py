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
import re
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


# v1.4.0 — when the original user query is supplied, scan it for tier
# keywords that map to a specific suffix. Lets the differentiator promote
# the candidate whose suffix matches the query's semantics. Example:
# query "completion rate primary school" + candidate ED_CR_L1 (suffix L1)
# gets " — best match for 'primary' in query" appended to its
# differentiator. Empirically the v9 Arm B FAW regressions concentrate on
# this exact pattern; see issue #100.
_TIER_KEYWORDS: dict[str, str] = {
    # Education tiers
    "primary": "L1",
    "lower secondary": "L2",
    "upper secondary": "L3",
    "secondary": "L3",
    "tertiary": "L4",
    # Sex
    "female": "F",
    "male": "M",
    # Settlement
    "rural": "R",
    "urban": "U",
    # Methodology
    "modelled": "MOD",
    "modeled": "MOD",
    "estimate": "MOD",
    "merged": "MERGE",
    "proxy": "PRXY",
}


def explain_difference(
    target_code: str,
    all_candidate_codes: Iterable[str],
    query: str | None = None,
) -> str:
    """Return a one-line differentiator for `target_code` relative to its
    siblings. Returns empty string when no heuristic applies — callers
    should not surface "differentiator: " when this is empty.

    The function works on codes alone, not on names. For richer plain-
    English context the caller pairs the differentiator with the
    indicator name in the response.

    v1.4.0: optional ``query`` parameter. When supplied, the function
    scans the lowercased query for known tier keywords (`primary`,
    `lower secondary`, `urban`, `modelled`, etc.) and appends a
    "best match for 'X' in query" hint when a candidate's suffix tokens
    intersect with the keyword-mapped suffix. Lets the LLM resume on the
    semantically-closest candidate instead of abstaining on L1/L2/L3-style
    sibling clusters where the query already specifies the tier.
    """
    codes = [c for c in all_candidate_codes if isinstance(c, str)]
    if target_code not in codes or len(codes) < 2:
        return ""

    # v1.4.0 — token-level common prefix (splits on '_') so a sibling
    # group like [ED_CR_L1, ED_CR_L2, ED_CR_L3] correctly extracts
    # suffix "L1" instead of the character-level prefix's "1". The old
    # character-level prefix would strip "ED_CR_L" and leave the suffix
    # as a bare digit, missing the L1/L2/L3 suffix table entries.
    prefix = _token_common_prefix(codes)
    suffix = target_code[len(prefix) :].lstrip("_")
    if not suffix:
        # target_code IS the common prefix — it's the "base" of the
        # family (e.g. ECD_CHLD_LMPSL among ECD_CHLD_LMPSL,
        # ECD_CHLD_LMPSL_MERGE, ECD_CHLD_LMPSL_PRXY).
        base = "base / canonical variant (no methodology suffix)"
        return base + _query_match_hint(suffix="", query=query)

    # Whole-suffix exact match
    if suffix in _SUFFIX_MEANINGS:
        return f"{suffix}: {_SUFFIX_MEANINGS[suffix]}" + _query_match_hint(
            suffix=suffix, query=query
        )

    # Token-level match (suffix like "AGE15_19_MOD" should pick up MOD)
    tokens = [t for t in suffix.split("_") if t]
    matched = [t for t in tokens if t in _SUFFIX_MEANINGS]
    if matched:
        # Prefer the most informative token (longest mapped meaning)
        best = max(matched, key=lambda t: len(_SUFFIX_MEANINGS[t]))
        return f"{best}: {_SUFFIX_MEANINGS[best]}" + _query_match_hint(
            suffix=suffix, query=query
        )

    # v1.5.0 — when prefix is empty AND no suffix tokens map to a
    # _SUFFIX_MEANINGS entry, the candidate set is a disjoint family
    # (e.g., [HVA_*, MNCH_*]) with no useful code-suffix differentiation.
    # Returning "variant suffix: _<full_code>" is misleading — it pretends
    # the entire code is a "variant" of a shared base when there is none.
    # Fall through to the query-aware hint (which may still fire if a
    # tier keyword applies) but suppress the bogus variant-suffix prefix.
    if not _token_common_prefix(codes):
        return _query_match_hint(suffix=suffix, query=query).lstrip(" —").strip()

    # Fallback: surface the raw suffix so the model can at least see
    # what varies. Common for indicator families we haven't curated yet.
    return f"variant suffix: _{suffix}" + _query_match_hint(suffix=suffix, query=query)


def _token_common_prefix(codes: list[str]) -> str:
    """Return the longest common '_'-delimited token prefix of ``codes``.

    Replaces the v1.3.x character-level ``os.path.commonprefix`` which
    would extract "ED_CR_L" from [ED_CR_L1, ED_CR_L2, ED_CR_L3], leaving
    the suffix as a bare digit and missing the L1/L2/L3 entries in
    ``_SUFFIX_MEANINGS``.

    v1.5.0 — when the token-level prefix is empty (disjoint families like
    [HVA_ADOL_..., HVA_EPI_..., MNCH_...] where no whole token segment
    matches across all codes), fall back to ``os.path.commonprefix`` so
    the suffix is "extra detail beyond the shared prefix" rather than the
    full code. This addresses the v140 forensic finding that
    differentiators degraded to "variant suffix: _HVA_EPI_INF_ANN_15-24"
    (full code) on disjoint clusters — strictly worse than v1.3.x's
    character-level prefix which at least returned "HVA_".
    """
    if not codes:
        return ""
    token_lists = [c.split("_") for c in codes]
    common: list[str] = []
    # strict=False — codes may legitimately have different segment counts
    # (e.g., [CME_MRY0T4, CME_MRY1T4_AGGREG]); we just stop at the first
    # divergence in any case, so the strict check would be a false alarm.
    for tokens in zip(*token_lists, strict=False):
        if len(set(tokens)) == 1:
            common.append(tokens[0])
        else:
            break
    if common:
        return "_".join(common)
    # v1.5.0 fallback — token-level prefix is empty (disjoint families).
    # Use character-level common prefix so the suffix is still trimmed to
    # the differing portion. Only fires when token-level returned "".
    char_prefix = os.path.commonprefix(codes)
    # Strip a trailing partial token so we don't end mid-token (e.g.,
    # for char_prefix="HVA_EPI_INF" trim to "HVA_EPI", then strip the
    # trailing underscore so the suffix starts cleanly). The most useful
    # boundary is the last underscore in the char prefix; rstrip removes
    # the trailing "_" itself so the returned prefix doesn't end in one.
    if "_" in char_prefix:
        char_prefix = char_prefix[: char_prefix.rfind("_") + 1].rstrip("_")
    return char_prefix


def _query_match_hint(suffix: str, query: str | None) -> str:
    """Append a " — best match for ..." hint when this candidate's suffix
    tokens cover ALL tier keywords present in the lowercased query.

    v1.5.0 — replaces the v1.4.0 first-match-wins loop with all-matches
    accumulation. The v1.4.0 single-winner-break logic mis-fired on
    queries containing multiple tier keywords whose mapped suffixes were
    not all present in a single candidate: e.g., for
    "completion rate primary school age modeled" the loop broke on
    'primary' (→ L1) first, never reaching 'modeled' (→ MOD); three
    candidates (ED_CR_L1, ED_CR_L1_UIS_MOD, ED_ANAR_L1) all got tagged
    "best match for 'primary'", forming a false tie that fired Path B
    ambiguity_flag. The v1.5.0 rule promotes ONLY the candidate whose
    suffix covers EVERY matched keyword — for the example, only
    ED_CR_L1_UIS_MOD (suffix [L1, UIS, MOD]) covers both L1 and MOD, so
    it gets the unique hint and the others get no hint.

    Word boundaries are preserved so 'urban' doesn't match 'suburban',
    'male' doesn't match 'female', etc.

    Returns the empty string when:
      - ``query`` is None / empty / non-string
      - no tier keyword is present in the query
      - this candidate does NOT cover every matched suffix
    """
    if not isinstance(query, str) or not query:
        return ""
    lowered = query.lower()
    suffix_tokens = {tok for tok in (suffix or "").split("_") if tok}
    # v1.5.0 — collect ALL DISTINCT tier keywords present in the query.
    # Longer multi-word keywords like 'lower secondary' must consume the
    # space they occupy so the substring keyword 'secondary' inside them
    # does not get a separate match (which would force an ED_CR_L2
    # candidate to also cover L3 to pass the strict all-matches rule).
    # Track claimed (start, end) character ranges; skip a keyword whose
    # match falls inside a longer keyword's claimed range.
    query_matches: list[tuple[str, str]] = []
    seen_suffixes: set[str] = set()
    claimed_ranges: list[tuple[int, int]] = []
    for keyword in sorted(_TIER_KEYWORDS, key=lambda k: -len(k)):
        pattern = r"\b" + re.escape(keyword) + r"\b"
        match = re.search(pattern, lowered)
        if not match:
            continue
        m_start, m_end = match.span()
        if any(
            c_start <= m_start and m_end <= c_end for c_start, c_end in claimed_ranges
        ):
            # This keyword sits inside a longer-keyword's claimed range —
            # skip so 'secondary' does not double-count inside 'lower secondary'.
            continue
        claimed_ranges.append((m_start, m_end))
        mapped = _TIER_KEYWORDS[keyword]
        if mapped not in seen_suffixes:
            query_matches.append((keyword, mapped))
            seen_suffixes.add(mapped)
    if not query_matches:
        return ""
    # Strict all-matches rule: hint fires only when THIS candidate's
    # suffix tokens cover EVERY matched suffix. Candidates that cover
    # only a partial subset get no hint, eliminating the v1.4.0 false-tie
    # pattern where a query with both 'primary' and 'modeled' tagged
    # three candidates with "best match for 'primary'".
    if not all(suf in suffix_tokens for _, suf in query_matches):
        return ""
    matched_keywords = [kw for kw, _ in query_matches]
    if len(matched_keywords) == 1:
        return f" — best match for '{matched_keywords[0]}' in query"
    joined = ", ".join(f"'{kw}'" for kw in matched_keywords)
    return f" — best match for {joined} in query"
