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
    # v1.5.1 — WS_PPL_W-UI ("unimproved drinking water") needs explicit
    # synonyms because the v1.5.0 Tier 2c Jaccard tier matched 'unimproved
    # drinking water' against 'basic drinking water' (overlap 2/4) at
    # score 70 and routed the semantic antonym to WS_PPL_W-ALB. Listed
    # before the WS_PPL_W-ALB keys so the antonym class is unambiguous.
    "unimproved drinking water": "WS_PPL_W-UI",
    "unimproved water": "WS_PPL_W-UI",
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
    # v1.5.1 — explicit MNCH_ANC4 synonyms. Without these, the v1.5.0
    # Tier 2c substring tier matched 'antenatal care 4 visits' (with '+'
    # stripped by _normalize) against synonym 'antenatal care' at score
    # 85, dropping the '4 visits' qualifier and resolving to MNCH_ANC1
    # (one visit). The v1.5.1 substring length-ratio guard plus these
    # synonyms together eliminate the misroute.
    "antenatal care 4 visits": "MNCH_ANC4",
    "antenatal care 4 or more visits": "MNCH_ANC4",
    "anc4": "MNCH_ANC4",
    "anc 4": "MNCH_ANC4",
    "anc 1": "MNCH_ANC1",
    # Note: do NOT add "anc 1+" here — `_normalize` strips '+' as a separator,
    # so the lookup key would never match. Use the post-normalize form above.
    "skilled birth attendant": "MNCH_SAB",
    "skilled birth attendance": "MNCH_SAB",
    "skilled attendance at birth": "MNCH_SAB",
    "sab": "MNCH_SAB",
    # ── Early childbearing — issue #64. Resolves the variants of
    #    "births to women under 18" / "early childbearing" that the
    #    model commonly emits when passing the indicator name to
    #    get_data. Without these synonyms, the model falls back to
    #    search_indicators(...), which historically returned
    #    Adolescent birth rate (MNCH_ABR — population 15–19) as the
    #    top match for "births under 18" queries.
    "early childbearing": "MNCH_BIRTH18",
    "early child bearing": "MNCH_BIRTH18",
    "births before age 18": "MNCH_BIRTH18",
    "births to women under 18": "MNCH_BIRTH18",
    "births under 18": "MNCH_BIRTH18",
    "births under age 18": "MNCH_BIRTH18",
    "first birth before age 18": "MNCH_BIRTH18",
    # ── Mortality variants — issue #64. Resolves age-specific
    #    phrasings of the CME_MR* family so the resolver picks the
    #    correct age bracket instead of letting substring matching
    #    in search_indicators bias toward Under-five.
    "child mortality 1-4": "CME_MRY1T4",
    "child mortality 1 to 4": "CME_MRY1T4",
    "child mortality aged 1-4": "CME_MRY1T4",
    "child mortality aged 1-4 years": "CME_MRY1T4",
    "child mortality rate 1-4": "CME_MRY1T4",
    "child mortality rate aged 1-4 years": "CME_MRY1T4",
    "mortality rate aged 1-4": "CME_MRY1T4",
    "mortality rate 1-4": "CME_MRY1T4",
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
    # v1.0.0: realigned with the current unicefdata YAML (PT_F_18-19_MRD
    # and PT_F_15-49_MRD_18 don't exist in the live registry; the
    # canonical 20-24 family does). PT_F_20-24_MRD_U18 is the SDG 5.3.1
    # headline (% of women 20-24 first married before age 18).
    "child marriage": ["PT_F_15-19_MRD", "PT_F_20-24_MRD_U15", "PT_F_20-24_MRD_U18"],
}


# Plain-English disambiguation tips embedded in search_indicators tool
# results when the query matches an _AMBIGUOUS key. Pattern adopted from
# World Bank's data360-mcp anti-hallucination templates: educate the
# model without forcing refusal. The model still gets ranked results;
# the tip explains which candidate matches UNICEF's headline / SDG
# convention and how to disambiguate before calling get_data.
#
# Sources for the editorial recommendations:
#   - SDG 3.2.1: Under-five mortality rate (CME_MRY0T4)
#   - SDG 3.b.1: DTP3 coverage as headline immunization indicator
#   - SDG 5.3.1: PT_F_15-49_MRD_18 (women 20-24 married before 18)
#   - UNICEF Data Warehouse headline framing for the mortality family
_DISAMBIGUATION_TIPS: dict[str, str] = {
    "child mortality": (
        "Ambiguous query. UNICEF's headline figure is under-five "
        "mortality (CME_MRY0T4, SDG 3.2.1 indicator). If the user meant "
        "the 1-4 age bracket specifically, use CME_MRY1T4. Other "
        "variants: CME_MRM0 (neonatal, first 28 days), CME_MRY0 "
        "(infant, 0-1 year). Verify which age bracket the user wants "
        "before calling get_data."
    ),
    "child mortality rate": (
        "Ambiguous query. UNICEF's headline figure is under-five "
        "mortality rate (CME_MRY0T4, SDG 3.2.1). For the 1-4 age "
        "bracket specifically, use CME_MRY1T4. Verify which age "
        "bracket the user wants before calling get_data."
    ),
    "mortality rate": (
        "Ambiguous query. Mortality rate has multiple age-bracket "
        "variants: CME_MRM0 (neonatal, 0-28 days), CME_MRY0 (infant, "
        "0-1 year), CME_MRY0T4 (under-five, 0-5 years — SDG 3.2.1 "
        "headline), CME_MRY1T4 (childhood, 1-4 years). Confirm which "
        "age bracket the user wants before calling get_data."
    ),
    "vaccination coverage": (
        "Ambiguous query. Specify the vaccine: IM_BCG (tuberculosis, "
        "neonatal), IM_DTP1 / IM_DTP3 (diphtheria-tetanus-pertussis, "
        "1st / 3rd dose — DTP3 is the SDG 3.b.1 headline immunization "
        "indicator), IM_MCV1 / IM_MCV2 (measles 1st / 2nd dose). Ask "
        "the user which vaccine before calling get_data."
    ),
    "vaccination": (
        "Ambiguous query. See vaccination coverage indicators above. "
        "DTP3 (IM_DTP3) is commonly used as the headline immunization "
        "metric (SDG 3.b.1). Ask the user which vaccine before "
        "calling get_data."
    ),
    "immunization coverage": (
        "Ambiguous query. See vaccination coverage indicators above. "
        "DTP3 (IM_DTP3) is the SDG 3.b.1 headline immunization "
        "indicator. Ask the user which vaccine before calling get_data."
    ),
    "child marriage": (
        "Ambiguous query. UNICEF's headline child-marriage indicator "
        "is PT_F_20-24_MRD_U18 (% of women 20-24 who were first married "
        "or in union before age 18, SDG 5.3.1). Other variants: "
        "PT_F_20-24_MRD_U15 (% married before age 15, women 20-24), "
        "PT_F_15-19_MRD (% currently married, girls 15-19). Confirm "
        "which framing the user wants before calling get_data."
    ),
}


def get_disambiguation_tip(query: str) -> str | None:
    """Return a curated disambiguation tip if `query` is known-ambiguous.

    Substring-match against `_DISAMBIGUATION_TIPS` keys after
    normalisation (so "what is the child mortality rate in Brazil"
    matches the "child mortality rate" key).

    Returns None when:
      - the query is empty or non-string
      - no `_DISAMBIGUATION_TIPS` key is a substring of the normalised query
      - the query *also* contains a `_SYNONYMS` key that resolves
        unambiguously to one indicator (e.g., "under-five mortality
        rate" trivially substring-matches "mortality rate" but is
        already specific — no tip needed)

    Called by `server.search_indicators` to attach a `disambiguation_tip`
    field to the tool result, in the data360-mcp anti-hallucination-
    template style: educate the model with plain-English guidance about
    which canonical indicator matches the user's likely intent, without
    forcing refusal. The model still gets the ranked candidate list.
    """
    if not isinstance(query, str) or not query.strip():
        return None
    normalized = _normalize(query)
    if not normalized:
        return None

    # Specificity check first: if the query already contains a phrase
    # that resolves unambiguously, the search is going to land on the
    # right indicator regardless. Surfacing the ambiguous-term tip
    # would be noise (e.g., "under-five mortality rate" trivially
    # substring-matches the "mortality rate" key). Iterate _SYNONYMS
    # longest-first so the most specific synonym wins the match check.
    for synonym in sorted(_SYNONYMS.keys(), key=len, reverse=True):
        if synonym in normalized:
            return None

    # Iterate disambiguation keys longest-first so that
    # "child mortality rate" wins over "child mortality" when both
    # substrings are present.
    for key in sorted(_DISAMBIGUATION_TIPS.keys(), key=len, reverse=True):
        if key in normalized:
            return _DISAMBIGUATION_TIPS[key]
    return None


def _normalize(s: str) -> str:
    """Lowercase, strip diacritics, drop punctuation, collapse whitespace.

    Keeps hyphens (e.g., `ED_15-24_LR`) so they survive the round-trip
    when callers pass codes verbatim. Does NOT sort tokens — the order-
    sensitive form is the primary lookup key. Paraphrase-stable lookup
    uses the companion `_sort_tokens()` helper against
    `_SYNONYMS_SORTED` as a strict fallback (v1.4.0, issue #100).

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


def _sort_tokens(normalized: str) -> str:
    """Sort tokens within a normalised string for word-order-insensitive lookup.

    Used by the v1.4.0 paraphrase-stable fallback against
    ``_SYNONYMS_SORTED``. Tokens are split on whitespace, sorted
    alphabetically, and re-joined with single spaces. Does not change
    diacritic/case/punctuation handling — pure tokenwise reordering.

    Examples:
      "primary school completion rate"   → "completion primary rate school"
      "completion rate primary school"   → "completion primary rate school"
    """
    return " ".join(sorted(normalized.split()))


# v1.4.0 — sorted-token mirror of ``_SYNONYMS``, lazily built on first use.
# Lets the resolver hit the same synonym for any token permutation of the
# key. Token-bag collisions (two distinct synonym keys whose sorted-token
# form matches a different code) are skipped so the fallback never
# silently misroutes a query. See issue #100 (paraphrase × ambiguity gate)
# for the empirical motivation.
_SYNONYMS_SORTED: dict[str, str] = {}

# v1.5.0 — tiered fuzzy-score threshold for ``_score_synonyms``. data360-mcp
# uses 70 as the floor for fuzzy similarity; the v1.5.0 partial-batch diff
# (1484 cells) flagged 8 cells where 'unimproved drinking water' Jaccard-tied
# at exactly 0.5 overlap with 'basic drinking water' (score 70) and routed
# to the semantic-antonym WS_PPL_W-ALB. v1.5.1 bumps the floor to 75 so the
# Jaccard tier requires >2/3 token overlap before resolving — eliminates the
# antonym-misroute class while preserving genuine paraphrase matches.
_SYNONYM_SCORE_THRESHOLD: int = 75

# v1.5.1 — substring tier length-ratio guard. The substring tier (score 85)
# fired when a SHORT synonym key was contained in a much LONGER query,
# ignoring the query's extra qualifier tokens. Example failure: query
# 'antenatal care 4 visits' substring-matched synonym 'antenatal care' →
# resolved to MNCH_ANC1 (one visit), dropping the '4 visits' qualifier
# that meant MNCH_ANC4. Reject substring tier when the longer side has
# >1.5× the shorter side's token count.
_SUBSTRING_LENGTH_RATIO_CAP: float = 1.5


def _score_synonyms(query_normalized: str) -> tuple[int, set[str]]:
    """Tiered scoring against every key in ``_SYNONYMS``.

    Borrowed from the data360-mcp ``CodelistResolver``'s
    ``_search_global`` / ``_search_static`` cascade. Tiers:

      score 100: exact normalised match (already caught by the primary
                 ``_SYNONYMS`` lookup; included here for completeness).
      score  95: exact no-space match (handles "viet nam" vs "vietnam"
                 style space-joining).
      score  90: sorted-token match (handles word-order permutations
                 the primary lookup misses).
      score  85: bidirectional substring match (handles token-drop
                 variants like "deaths aged 15 to 24" → "deaths 15 24").
      score  70-84: token-set Jaccard similarity (handles loose paraphrases
                 like "Hib third dose" → "Hib vaccine third dose").

    Returns ``(best_score, {codes at best_score})``. When multiple
    synonym keys map to DIFFERENT codes at the same best score, the set
    has ``len > 1`` and the caller must NOT pick a winner — let the
    remaining resolver paths handle it (no silent misroute).
    """
    if not query_normalized:
        return 0, set()
    query_no_spaces = query_normalized.replace(" ", "")
    query_tokens = set(query_normalized.split())
    query_sorted = _sort_tokens(query_normalized)
    best_score = 0
    best_codes: set[str] = set()

    for key, code in _SYNONYMS.items():
        key_normalized = _normalize(key)
        if not key_normalized:
            continue
        key_no_spaces = key_normalized.replace(" ", "")
        key_tokens = set(key_normalized.split())
        score = 0

        if query_normalized == key_normalized:
            score = 100
        elif query_no_spaces == key_no_spaces:
            score = 95
        elif query_sorted and query_sorted == _sort_tokens(key_normalized):
            score = 90
        elif query_normalized in key_normalized or key_normalized in query_normalized:
            # v1.5.1 — guard against extra-qualifier misroutes. If the
            # query carries substantially more tokens than the matched
            # synonym key (or vice versa), the extra tokens probably
            # change the meaning ('antenatal care' → 'antenatal care 4
            # visits' = MNCH_ANC4 ≠ MNCH_ANC1). Reject substring tier
            # when the token-count ratio exceeds the cap.
            q_n = len(query_tokens)
            k_n = len(key_tokens)
            if q_n and k_n:
                ratio = max(q_n, k_n) / min(q_n, k_n)
                if ratio <= _SUBSTRING_LENGTH_RATIO_CAP:
                    score = 85
        elif query_tokens and key_tokens:
            overlap = query_tokens & key_tokens
            union = query_tokens | key_tokens
            if overlap and union:
                jaccard = len(overlap) / len(union)
                if jaccard >= 0.5:
                    score = int(70 + 14 * (jaccard - 0.5) / 0.5)

        if score > best_score:
            best_score = score
            best_codes = {code}
        elif score == best_score and score > 0:
            best_codes.add(code)

    return best_score, best_codes


def _ensure_synonyms_sorted_built() -> None:
    """Build ``_SYNONYMS_SORTED`` lazily on first lookup.

    Empty until the first ``resolve_indicator`` call needs it. Idempotent:
    if already populated, no-ops. Collisions (sorted-token form maps to
    multiple distinct codes) are dropped to keep the fallback safe.
    """
    if _SYNONYMS_SORTED:
        return
    collisions: set[str] = set()
    for key, code in _SYNONYMS.items():
        sorted_key = _sort_tokens(_normalize(key))
        if not sorted_key or sorted_key in collisions:
            continue
        existing = _SYNONYMS_SORTED.get(sorted_key)
        if existing is not None and existing != code:
            # Two synonym keys with different word orders map to
            # different codes once their tokens are sorted — drop the
            # ambiguous entry. The original word-order-sensitive lookup
            # remains authoritative for these queries.
            _SYNONYMS_SORTED.pop(sorted_key, None)
            collisions.add(sorted_key)
            continue
        _SYNONYMS_SORTED[sorted_key] = code


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
        "metadata",
        "current",
        "_unicefdata_indicators_metadata.yaml",
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

    # v1.4.0 — paraphrase-stable fallback. If the word-order-sensitive
    # _SYNONYMS lookup missed, retry with the sorted-token form against
    # _SYNONYMS_SORTED (built lazily at first lookup, with token-bag
    # collisions skipped so this fallback can never silently misroute).
    # Closes issue #100: "primary school completion rate" (in _SYNONYMS)
    # and "completion rate primary school" (the v130 paraphrase that
    # missed) now both resolve to ED_CR_L1 with status='synonym_match'.
    _ensure_synonyms_sorted_built()
    sorted_normalized = _sort_tokens(normalized)
    if sorted_normalized and sorted_normalized in _SYNONYMS_SORTED:
        code = _SYNONYMS_SORTED[sorted_normalized]
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
                candidates=tuple((c, code_to_name.get(c, "")) for c in candidate_codes),
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

    # v1.5.0 — tiered fuzzy scorer (data360-mcp `CodelistResolver` pattern).
    # Runs LAST so curated _AMBIGUOUS, _SYNONYMS, and name-index lookups all
    # get priority. The scorer is the safety net for token-drop / token-add
    # paraphrases ("deaths aged 15 to 24" → "deaths 15 24", "Hib third dose"
    # → "Hib vaccine third dose") that the v1.4.0 _SYNONYMS_SORTED mirror
    # cannot catch. Best-score ties across DIFFERENT codes are rejected
    # (no silent misroute); unique winners above the threshold resolve.
    best_score, best_codes = _score_synonyms(normalized)
    if best_score >= _SYNONYM_SCORE_THRESHOLD and len(best_codes) == 1:
        code = next(iter(best_codes))
        if code in code_to_name:
            return IndicatorResolution(
                status="synonym_match",
                code=code,
                name=code_to_name.get(code),
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
        r.code
        for r in resolutions
        if r.status in ("code_passthrough", "synonym_match", "name_index_hit")
        and r.code is not None
    ]
    return resolutions, resolved_codes
