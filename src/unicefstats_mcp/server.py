"""UNICEF Stats MCP Server — query child development indicators via Model Context Protocol.

Seven tools in a 4-step workflow:
  Step 1 (Discovery):  search_indicators, list_categories, list_countries
  Step 2 (Metadata):   get_indicator_info, get_temporal_coverage
  Step 3 (Data):       get_data
  Step 4 (Code):       get_api_reference

Plus two MCP prompts:
  compare_indicators     — pre-built analysis workflow (discovery → data → comparison)
  write_unicefdata_code  — generate Python/R/Stata code using the unicefdata package

Data source: UNICEF SDMX REST API (https://sdmx.data.unicef.org/ws/public/sdmxapi/rest)
No API key required. 790+ child-focused indicators, 200+ countries,
disaggregations by sex/age/wealth/residence.
"""

from __future__ import annotations

import json
import logging
import time as _time
import types
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, Literal, TypeVar

from fastmcp import FastMCP

from unicefstats_mcp import __version__
from unicefstats_mcp import dimensions as _dims
from unicefstats_mcp.country_resolver import lookup_country_name, resolve_countries
from unicefstats_mcp.formatters import (
    apply_limit,
    compute_trend,
    country_col,
    error,
    normalize_columns,
    ok,
    summarize_data,
    summarize_disaggregations,
    to_compact,
    to_full,
    truncate_description,
)
from unicefstats_mcp.indicator_context import get_indicator_context
from unicefstats_mcp.indicator_resolver import resolve_indicator
from unicefstats_mcp.reference import REFERENCES, VALID_LANGUAGES
from unicefstats_mcp.validators import (
    MAX_COUNTRIES,
    validate_age,
    validate_country_inputs,
    validate_filters,
    validate_indicator,
    validate_limit,
    validate_query,
    validate_region,
    validate_sex,
    validate_year,
)

T = TypeVar("T")

logger = logging.getLogger(__name__)


def _is_client_error(exc: BaseException) -> bool:
    """Heuristic: is this a 4xx-style client error we should NOT retry?

    Prefers structured signals (HTTP status code attribute, exception class) over
    substring matching. Substring is the last-resort fallback for `RuntimeError`s
    raised by `unicefdata` whose only signal is the message text. The check is
    word-bounded to avoid the v0.7.1 failure mode where `"404"` matched against a
    response body containing the literal characters (e.g. status `"4040"`).
    """
    # Structured signals first. requests.HTTPError carries .response.status_code;
    # urllib HTTPError IS the response and carries .code.
    status = getattr(exc, "status_code", None)
    if status is None:
        resp = getattr(exc, "response", None)
        status = getattr(resp, "status_code", None) if resp is not None else None
    if status is None:
        status = getattr(exc, "code", None)
    if isinstance(status, int) and 400 <= status < 500:
        return True

    # Fallback: word-bounded substring match. Match HTTP status as a standalone
    # token, not a substring (so "4040" / "404 Not Found" are handled correctly).
    import re as _re
    text = str(exc)
    if _re.search(r"\b(?:400|401|403|404|405|409|410|422)\b", text):
        return True
    text_lower = text.lower()
    return "not found" in text_lower or "does not exist" in text_lower


def _retry(
    fn: Callable[[], T],
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
) -> T:
    """Call fn with exponential backoff on transient failures.

    Retries on network/5xx-style errors. Client errors (4xx, "not found", etc.)
    are re-raised immediately — see `_is_client_error`. The exception message is
    sanitized before logging to avoid log injection via embedded newlines.
    """
    if max_attempts < 1:
        raise ValueError(f"max_attempts must be >= 1, got {max_attempts}")
    last_exc: BaseException | None = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if _is_client_error(exc):
                raise
            if attempt < max_attempts - 1:
                delay = min(base_delay * (2 ** attempt), max_delay)
                # Sanitize: strip embedded newlines/control chars from the
                # exception message before it lands in a log line.
                exc_safe = str(exc).replace("\n", " ").replace("\r", " ")
                logger.info(
                    "Retry %d/%d after %.1fs: %s",
                    attempt + 1, max_attempts, delay, exc_safe,
                )
                _time.sleep(delay)
    assert last_exc is not None  # loop ran at least once (max_attempts >= 1)
    raise last_exc

mcp = FastMCP(
    name="unicefstats-mcp",
    version=__version__,
    instructions=(
        "Query UNICEF child development statistics for 200+ countries. "
        "No API key required. 790+ child-focused indicators (mortality, nutrition, "
        "education, protection, WASH, HIV/AIDS, and more) with disaggregations "
        "by sex, age, wealth quintile, and residence. "
        "Data sourced from UNICEF SDMX API (sdmx.data.unicef.org)."
    ),
)

# ---------------------------------------------------------------------------
# Lazy import helpers — defer heavy unicefdata import until first tool call
# ---------------------------------------------------------------------------

_ud: types.ModuleType | None = None
_indicators_cache: dict[str, dict[str, Any]] | None = None
_countries_cache: dict[str, str] | None = None


def _get_ud() -> types.ModuleType:
    """Lazy-import unicefdata."""
    global _ud
    if _ud is None:
        import unicefdata as ud

        _ud = ud
    return _ud


def _get_indicators() -> dict[str, dict[str, Any]]:
    """Load and cache the full indicator registry."""
    global _indicators_cache
    if _indicators_cache is None:
        ud = _get_ud()
        _indicators_cache = ud.list_indicators()
    return _indicators_cache


def _get_countries() -> dict[str, str]:
    """Load and cache country code → name mapping."""
    global _countries_cache
    if _countries_cache is None:
        ud = _get_ud()
        _countries_cache = ud.load_country_codes()
    return _countries_cache


# ---------------------------------------------------------------------------
# Synonym expansion for search
# ---------------------------------------------------------------------------

_SYNONYMS: dict[str, str] = {
    # MNCH indicators
    "caesarean": "cesarean c-section",
    "caesarean section": "cesarean c-section",
    "c-section": "cesarean c-section",
    "c section": "cesarean c-section",
    "cesarean section": "cesarean c-section",
    "births under 18": "early childbearing birth before age 18",
    "births to women under 18": "early childbearing birth before age 18",
    "teenage pregnancy": "early childbearing adolescent birth",
    "adolescent birth": "early childbearing birth before age",
    "teen birth": "early childbearing adolescent birth",
    # Nutrition
    "stunting": "stunting height-for-age",
    "wasting": "wasting weight-for-height",
    "underweight": "underweight weight-for-age",
    "malnutrition": "stunting wasting underweight nutrition",
    # Mortality
    # v1.2.0 Commit 11 (Copilot #3328906511) — all under-five mortality
    # variants must map to the SAME expansion so the " rate" suffix
    # appears consistently regardless of phrasing. The earlier shape
    # ("under-5 mortality" → "under-five mortality") combined with
    # _expand_synonyms's `break` after first match silently produced
    # different expansions for "under-5 mortality" vs "under-five
    # mortality".
    "child mortality": "under-five mortality rate",
    "infant mortality": "infant mortality rate",
    "neonatal mortality": "neonatal mortality rate",
    "under-5 mortality": "under-five mortality rate",
    "under 5 mortality": "under-five mortality rate",
    "under-five mortality": "under-five mortality rate",
    "u5mr": "under-five mortality rate",
    # v1.2.0: bare-acronym query expansions so search_indicators('IMR')
    # surfaces CME_MRY0 by routing through the name-match path. Without
    # these, the bare 3-char acronyms produce zero scoring hits
    # (no indicator code/name/desc contains 'imr' / 'nmr' literally)
    # and the function bails out at the empty-results early return.
    "imr": "infant mortality",
    "nmr": "neonatal mortality",
    # Education
    "primary school": "primary education completion",
    "school completion": "education completion rate",
    "out of school": "out-of-school",
}


def _expand_synonyms(query: str) -> str:
    """Expand query with synonyms for better indicator matching."""
    expanded = query
    for term, expansion in _SYNONYMS.items():
        if term in query:
            expanded = f"{expanded} {expansion}"
            break  # one expansion per query to avoid noise
    return expanded


# Code-prefix and name-pattern markers for derived metrics. Used by
# search_indicators to deprioritise (not exclude) these — they remain
# discoverable when explicitly searched, but lose to the canonical
# indicator when the user's query is generic. See issue #64.
# Code-level grammar markers. Each token below carries semantic load in
# the UNICEF SDMX code grammar (see README "Code prefix grammar"):
#   TRGT = national TARGET (typically year-bound, e.g. TRGT_2030_*)
#   ARR  = Annual Rate of Reduction (a derived rate, not a stock measure)
#   PRJ  = PROJected variant (forecast / extrapolation, not observed)
# All three label DERIVED metrics that share a stem with a canonical
# indicator (e.g. CME_ARR_U5MR vs CME_MRY0T4), so we deprioritise them.
_DERIVED_METRIC_CODE_PATTERNS: tuple[str, ...] = (
    "TRGT_",       # TRGT = target — national target indicators (e.g. TRGT_2030_IM_DTP3)
    "_ARR_",       # ARR = Annual Rate of Reduction (e.g. CME_ARR_U5MR)
    "_ARR",        # ARR = Annual Rate of Reduction (trailing form)
    "_PRJ",        # PRJ = projected variant (forecast/extrapolation)
)

# NAME-level mirrors of the code-level grammar above. Same semantics,
# different surface form: "national target" mirrors TRGT_, "annual rate
# of reduction" mirrors _ARR(_), "projected " / "year 2030" / "(year "
# mirror _PRJ. We check both because upstream sometimes ships a derived
# indicator with a canonical-looking code but a giveaway name (or vice
# versa).
_DERIVED_METRIC_NAME_PATTERNS: tuple[str, ...] = (
    "national target",
    "annual rate of reduction",
    "tasa anual de reducci",  # Spanish form occasionally shipped by unicefdata
    "projected ",
    "year 2030",
    "(year ",  # e.g., "(Year 2030)"
)


def _is_derived_metric(code: str, name: str) -> bool:
    """Return True if `code`/`name` look like a derived metric.

    Derived metrics (targets, rates of reduction, projections) share
    naming and acronyms with the canonical indicator they derive from,
    so a generic search like "U5MR" can rank CME_ARR_U5MR (Annual Rate
    of Reduction of U5MR) above CME_MRY0T4 (the actual U5MR). This
    helper lets search_indicators apply a flat penalty so the
    canonical wins on a generic query while the derived metric remains
    discoverable when explicitly named. See issue #64.

    The TRGT_ / _ARR(_) / _PRJ prefixes/suffixes recognised here are
    documented in the README "Code prefix grammar" section alongside
    the family prefixes (CME, NT, IM, ED, WS, MNCH, ...).
    """
    code_u = code.upper()
    if any(pat in code_u for pat in _DERIVED_METRIC_CODE_PATTERNS):
        return True
    name_l = name.lower()
    return any(pat in name_l for pat in _DERIVED_METRIC_NAME_PATTERNS)


# ---------------------------------------------------------------------------
# Step 1: Discovery tools (local, instant, no API call)
# ---------------------------------------------------------------------------


# Natural-language tokens that signal the user is asking for the
# TARGET variant of an indicator (i.e. wants TRGT_* unmasked rather
# than deprioritised). These mirror the code-level TRGT_ prefix in
# _DERIVED_METRIC_CODE_PATTERNS above: TRGT = target, and these are
# the English words a user might type for the same concept.
_TARGET_QUERY_TOKENS: frozenset[str] = frozenset(
    {"target", "targets", "goal", "goals", "objective", "objectives",
     "aspiration", "aspirations", "milestone", "milestones"}
)

# v1.1.1 NOTE (FIX 2): _DIM_NAME_PATTERNS was REMOVED. Earlier drafts
# also matched dim hints against the indicator NAME (e.g. "women",
# "rural"), but names carry dimension language by construction:
# PT_F_20-24_MRD_U18 says "Percentage of women..." even though it is
# NOT a literacy indicator. A query "women's literacy" would falsely
# boost it. Code-suffix patterns in _DIM_TOKEN_MAP (the UNICEF SDMX
# convention) are the only reliable disaggregation signal.
_DIM_TOKEN_MAP: dict[str, tuple[str, ...]] = {
    # dimension_hint -> code-substring patterns to look for (uppercase)
    "SEX_F": ("_F_", "_F.", "_F-"),
    "SEX_M": ("_M_", "_M.", "_M-"),
    "WEALTH_Q1": ("_Q1_", "_Q1.", "_Q1-"),
    "WEALTH_Q5": ("_Q5_", "_Q5.", "_Q5-"),
    "RES_U": ("_U_", "_U.", "_U-"),
    "RES_R": ("_R_", "_R.", "_R-"),
    # v1.2.0 methodology marker. Indicators that carry _MOD in their
    # code are modelled estimates (as opposed to observed survey data).
    # When the user explicitly asks for modelled estimates, surface
    # those above the observed siblings.
    #
    # v1.2.0 Commit 11 (Copilot #3328906506) — `_MOD_` covers
    # `_MOD_NUMTH`-style intermediate cases (e.g. NT_ANT_HAZ_NE2_MOD_NUMTH);
    # the suffix-only case (codes ending in `_MOD` like NT_ANT_HAZ_NE2_MOD)
    # is handled by an explicit endswith branch in `_indicator_matches_dim`
    # so plain substring on `_MOD` alone doesn't over-fire on hypothetical
    # `_MODEL` / `_MODE` / `_MODERATE` codes.
    "METHOD_MOD": ("_MOD_",),
}

# Single-word query tokens (word-bounded) that activate each hint.
_DIM_QUERY_TOKENS: dict[str, frozenset[str]] = {
    "SEX_F": frozenset({"female", "girls", "women", "woman", "girl"}),
    "SEX_M": frozenset({"male", "boys", "men", "man", "boy"}),
    "WEALTH_Q1": frozenset({"poorest", "q1"}),
    "WEALTH_Q5": frozenset({"richest", "q5"}),
    "RES_U": frozenset({"urban", "city", "town"}),
    "RES_R": frozenset({"rural", "village"}),
}

# Multi-word phrases (lowercased) that activate each hint; checked via
# substring on the raw lowercased query (NOT tokenised) so that
# "lowest quintile" survives. Keep narrow to avoid false positives.
_DIM_QUERY_PHRASES: dict[str, tuple[str, ...]] = {
    "WEALTH_Q1": ("lowest quintile",),
    "WEALTH_Q5": ("highest quintile",),
    # v1.2.0: methodology-phrase boost. Both spellings cover UK ("modelled")
    # and US ("modeled"); both singular and plural ensure "the modelled
    # estimate" matches as well as "modelled estimates". Substring match
    # (not token) so the prefixed-with article forms work too.
    "METHOD_MOD": (
        "modelled estimate",
        "modeled estimate",
        "modelled estimates",
        "modeled estimates",
    ),
}


def _query_seeks_target(query_tokens: set[str]) -> bool:
    """True if the user explicitly asked for target-style indicators.

    A True return unmasks the TRGT_ code prefix (TRGT = target) that
    _is_derived_metric would otherwise deprioritise.

    FIX 3: use set-intersection against the pre-tokenised query, NEVER
    a substring on the raw query. 'targeting children', 'on-target',
    'no target group' must NOT unmask TRGT_* codes.
    """
    return bool(query_tokens & _TARGET_QUERY_TOKENS)


def _query_dimension_hints(query_lower: str, query_tokens: set[str]) -> set[str]:
    """Return the set of dimension hints (e.g. {'SEX_F','RES_R'}) the
    query word-boundedly asks for. Empty set = no boost should fire."""
    hints: set[str] = set()
    for hint, toks in _DIM_QUERY_TOKENS.items():
        if query_tokens & toks:
            hints.add(hint)
    for hint, phrases in _DIM_QUERY_PHRASES.items():
        if any(p in query_lower for p in phrases):
            hints.add(hint)
    return hints


def _indicator_matches_dim(code: str, name: str, hints: set[str]) -> bool:
    """True if `code` carries any of the requested dimension markers.

    FIX 2: ONLY check code-side suffix patterns from _DIM_TOKEN_MAP.
    Name-side matching was removed because indicator names carry
    dimension language for unrelated reasons (PT_F_20-24_MRD_U18's
    name mentions 'women' but it isn't a literacy indicator). The
    UNICEF SDMX code-suffix convention is the only reliable
    disaggregation signal. The `name` parameter is retained in the
    signature for call-site stability but is intentionally unused.
    """
    if not hints:
        return False
    code_u = code.upper()
    for hint in hints:
        patterns = _DIM_TOKEN_MAP.get(hint, ())
        for pat in patterns:
            if pat in code_u:
                return True
        # v1.2.0 Commit 11 (Copilot #3328906506) — METHOD_MOD's `_MOD`
        # token must also match the code-SUFFIX case (codes ending in
        # `_MOD` with no further `_MOD_NUMTH`-style trailing segment).
        # The existing patterns in _DIM_TOKEN_MAP all include trailing
        # separators (`_F_`, `_F.`, `_F-`) which work via plain
        # substring; `_MOD` alone is special because trailing chars
        # (`_MODEL`, `_MODE`, `_MODERATE`) could over-fire.
        if hint == "METHOD_MOD" and code_u.endswith("_MOD"):
            return True
    return False


@mcp.tool()
def search_indicators(query: str, limit: int = 20) -> dict[str, Any]:
    """Search UNICEF child development indicators by keyword.

    Returns indicator codes, names, and categories. Use the returned `code`
    values with get_indicator_info() or get_data().
    Always start here if you don't know the indicator code.

    Examples: "mortality", "breastfeeding", "education", "child labour", "stunting"

    v1.1.0 advisory layer (additive to v0.9.0/v1.0.0 ambiguity_flag):
    - If response carries requires_confirmation=True, STOP and ask the
      user to disambiguate before calling get_data.
    - If response carries recommended + next_step, the model SHOULD call
      next_step verbatim (e.g. get_indicator_info(code='...')).
    - assistant_guidance is a plain-English directive (<200 chars).
    - Decision order: curated-ambiguous -> curated-preferred -> confident
      match -> none (wire-equivalent to v1.0.0). See
      internal/v1.1.0_design/ for rationale.
    """
    if err := validate_query(query):
        return error(err, tip="Provide a search term like 'mortality' or 'education'.")
    if err := validate_limit(limit, max_limit=100):
        return error(err)

    try:
        all_indicators = _get_indicators()
    except Exception as exc:
        return error(f"Failed to load indicator registry: {exc}")

    query_lower = query.lower()
    # Expand synonyms so common terms find the right indicators
    query_expanded = _expand_synonyms(query_lower)
    query_tokens = set(query_expanded.split())
    # ------------------------------------------------------------------
    # ORDERING INVARIANT (v1.1.1, FIX 1)
    # ------------------------------------------------------------------
    # The TRGT penalty and dim_hints rerank results[] ONLY.
    # lookup_preferred(query) is downstream of this block and operates
    # on the RAW query string, never on the reranked results[]. Do NOT
    # move the curated lookup before this block — the curated
    # short-circuit must not depend on scoring ordering. Future
    # refactors that touch the search_indicators control flow MUST
    # preserve: (a) curated lookup sees only `query`, never `matches`;
    # (b) `recommended` is computed from the curated entry, not from
    # `results[0]`; (c) this scoring loop never mutates `query`.
    # ------------------------------------------------------------------
    # v1.1.1 advisory layer: pre-compute target-seeking intent and any
    # dimension hints once per query so we don't re-tokenise per
    # indicator. Both compose with the existing 4-layer scoring; if
    # neither fires the relative ordering is byte-identical to v1.0.0.
    seeks_target = _query_seeks_target(query_tokens)
    dim_hints = _query_dimension_hints(query_lower, query_tokens)
    matches: list[dict[str, Any]] = []

    for code, meta in all_indicators.items():
        # Skip tier-2 category codes (CME, CHILD_PROTECTION, etc.). They
        # surface as search hits because of code substring matches but
        # are NOT valid arguments to get_data — they are aggregates over
        # tier-1 indicators. The distinguishing feature in the unicefdata
        # codelist: tier-1 indicators have a `parent` field pointing to
        # their category; tier-2 categories don't. See issue #64.
        if "parent" not in meta:
            continue

        name = meta.get("name", "")
        desc = meta.get("description", "")
        cat = meta.get("category", "")
        searchable = f"{code} {name} {desc} {cat}".lower()

        # Score: exact code match > code contains > full phrase > token overlap > category
        score = 0
        if query_lower == code.lower():
            score = 100
        elif query_lower in code.lower():
            score = 90
        elif query_expanded in name.lower() or query_lower in name.lower():
            score = 80
        elif query_expanded in desc.lower() or query_lower in desc.lower():
            score = 40
        elif query_lower in cat.lower():
            score = 60
        else:
            # Token-level matching: what fraction of query tokens appear?
            if len(query_tokens) >= 2:
                hits = sum(1 for t in query_tokens if len(t) > 2 and t in searchable)
                frac = hits / len(query_tokens)
                if frac >= 0.5:
                    score = int(30 + 40 * frac)  # 50-70 range

        # Derived-metric penalty. National targets (TRGT_*), annual
        # rates of reduction (*_ARR_*), and projected variants are
        # derived metrics, not the headline indicator the model is
        # usually looking for. When the user asks for "U5MR", they
        # mean CME_MRY0T4 (the rate), not CME_ARR_U5MR (the annual
        # rate of reduction *of* that rate). Subtract 35 so a derived
        # metric with a code-substring hit (90) loses to the
        # canonical name match (80) but still surfaces if it is the
        # only result. See issue #64.
        #
        # v1.1.1 query-aware refinement (per maintainer directive:
        # "TRGT should only be used if the user is looking for a
        # target"). When the query carries an explicit target token
        # (target/goal/objective/aspiration/milestone — see
        # _query_seeks_target), TRGT_* / "national target" codes are
        # what the user actually wants, so we WAIVE the penalty for
        # them. Other derived metrics (_ARR_, _PRJ, "annual rate of
        # reduction") keep the unconditional penalty — those are
        # truly off-topic regardless of query intent.
        if score > 0 and _is_derived_metric(code, name):
            is_trgt_like = (
                code.upper().startswith("TRGT_")
                or "national target" in name.lower()
            )
            if not (is_trgt_like and seeks_target):
                score -= 35

        # v1.1.1 dimension-token boost. When the user asks for a
        # specific sex/wealth/residence slice, surface the matching
        # disaggregated code (+15) so e.g. "stunting in girls" promotes
        # NT_ANT_HAZ_NE2_F over the unstratified NT_ANT_HAZ_NE2.
        #
        # FIX 2 gate: the boost fires ONLY when the indicator's CODE
        # carries the SDMX disaggregation suffix (_F_, _M_, _Q1_, _U_,
        # _R_, etc.). Indicator NAMES are NOT checked — names carry
        # dimension language for unrelated reasons (PT_F_20-24_MRD_U18
        # mentions "women" but isn't a literacy indicator), which
        # would mis-fire boosts on queries like "women's literacy".
        # Code-suffix is the only reliable disaggregation signal in
        # the UNICEF SDMX codespace.
        #
        # Magnitude is deliberately smaller than the penalty (15 vs
        # 35) so it nudges within a tied band rather than overriding
        # the 4-layer ordering — a category-only hit (40) with a
        # dimension match (55) still loses to a name match (80)
        # without one.
        if score > 0 and dim_hints and _indicator_matches_dim(code, name, dim_hints):
            score += 15

        if score > 0:
            matches.append(
                {
                    "code": code,
                    "name": name,
                    "description": truncate_description(desc),
                    "category": cat,
                    "relevance": score,
                }
            )

    # Sort by relevance descending, then alphabetically
    matches.sort(key=lambda m: (-m["relevance"], m["code"]))
    results = matches[:limit]

    # v0.9.0: keep relevance in the output. The v9 benchmark diagnosis
    # showed 96.3% of stuck queries looped on search_indicators because
    # the model couldn't tell which match was canonical. The score was
    # computed but hidden — exposing it lets the model rank without a
    # second tool call. The field is documented in the tool's return
    # contract (see lookup_by_code for the strict-canonical alternative).

    # Curated disambiguation tip (data360-mcp anti-hallucination-
    # template pattern). When the query matches a known-ambiguous term
    # — "child mortality" has four age-bracket variants, "vaccination"
    # has five vaccines, etc. — embed plain-English guidance about
    # which canonical indicator UNICEF treats as the headline figure,
    # so the model can verify with the user before calling get_data
    # against the wrong variant. Closes the semantic half of issue #64.
    from .indicator_resolver import get_disambiguation_tip, resolve_indicator
    disambiguation_tip = get_disambiguation_tip(query) if results else None

    if not results:
        return error(
            f"No indicators match '{query}'.",
            tip="Try broader terms like 'health', 'education', 'nutrition', "
            "or use list_categories() to browse topics.",
            no_data=True,
        )

    payload: dict[str, Any] = {
        "query": query,
        "total_matches": len(matches),
        "showing": len(results),
        "results": results,
        "tip": (
            f"Use get_indicator_info('{results[0]['code']}') for full details "
            "including available disaggregations."
        ),
    }
    if disambiguation_tip:
        payload["disambiguation_tip"] = disambiguation_tip

    # v0.9.0+ ambiguity flag. Two paths fire here:
    #
    #   (A) CURATED — query matches a known-ambiguous entry in
    #       _AMBIGUOUS (child mortality, vaccination, child marriage).
    #       Highest-confidence detection; candidates come straight from
    #       the curated dict via resolve_indicator.
    #
    #   (B) HEURISTIC (v1.0.0) — resolver returned 'unknown' but the
    #       search results show novel ambiguity: top relevance is below
    #       the canonical-match threshold (90) AND multiple candidates
    #       have similar scores. Catches the empirical pathology from
    #       the v9 Arm B run (e.g., ECD_CHLD_LMPSL / ECD_CHLD_LMPSL_MERGE
    #       / ECD_CHLD_LMPSL_PRXY variants — not in _AMBIGUOUS).
    #
    # Either path sets ambiguity_flag=True + candidates + abstain
    # instruction so callers honor a single signal. The v9 Arm B
    # benchmark observed 96.3% of stuck queries looped on
    # search_indicators because nothing in the response told the model
    # to STOP.
    resolution = resolve_indicator(query)
    CANONICAL_RELEVANCE_THRESHOLD = 90  # exact-code match in current scoring
    SIMILAR_RELEVANCE_WINDOW = 10
    MIN_SIMILAR_CANDIDATES = 3
    HEURISTIC_CANDIDATE_CAP = 5

    if resolution.status == "ambiguous" and resolution.candidates:
        # Path A — curated
        from .differentiator import explain_difference
        curated_codes = [c for c, _ in resolution.candidates]
        payload["ambiguity_flag"] = True
        payload["ambiguity_source"] = "curated"
        payload["candidates"] = [
            {
                "code": code,
                "name": name,
                "differentiator": explain_difference(code, curated_codes),
            }
            for code, name in resolution.candidates
        ]
        payload["abstain_instruction"] = (
            "Multiple UNICEF indicators match this query and the MCP "
            "cannot select a canonical answer. STOP — emit a final "
            "response listing the candidates above and asking the "
            "requester to specify a code, OR abstain if the question "
            "cannot be answered unambiguously. Do NOT call "
            "search_indicators again — the result will be identical."
        )
    elif resolution.status == "unknown" and results:
        # Path B — heuristic. Fires only when the resolver gave up AND
        # the search yields multiple candidates with similar relevance.
        # If the resolver returned name_index_hit / synonym_match /
        # code_passthrough it already picked a canonical winner and we
        # do NOT second-guess it.
        top_relevance = results[0].get("relevance", 0)
        if top_relevance < CANONICAL_RELEVANCE_THRESHOLD:
            similar = [
                r for r in results
                if r.get("relevance", 0) >= top_relevance - SIMILAR_RELEVANCE_WINDOW
            ]
            if len(similar) >= MIN_SIMILAR_CANDIDATES:
                from .differentiator import explain_difference
                similar_capped = similar[:HEURISTIC_CANDIDATE_CAP]
                heuristic_codes = [r["code"] for r in similar_capped]
                payload["ambiguity_flag"] = True
                payload["ambiguity_source"] = "heuristic"
                payload["candidates"] = [
                    {
                        "code": r["code"],
                        "name": r["name"],
                        "differentiator": explain_difference(r["code"], heuristic_codes),
                    }
                    for r in similar_capped
                ]
                payload["abstain_instruction"] = (
                    "Search returned multiple candidates with similar "
                    "relevance and no canonical match. STOP — emit a "
                    "final response listing the candidates above and "
                    "ask the requester to specify a code, OR abstain. "
                    "Do NOT call search_indicators again with a different "
                    "keyword — none of the candidates is canonical for "
                    "this query."
                )

    # v1.1.1 Decision order (REORDERED — curated takes precedence over
    # heuristic ambiguity; see docs/v1.1.1 decision-logic rationale):
    #   1. CURATED_PREFERRED hit (lookup_preferred on RAW query) ->
    #      False, canonical pick from catalog with category +
    #      dimension_hint. Wins over heuristic ambiguity because the
    #      catalog match is a deliberate human-curated signal whereas
    #      the heuristic is a pattern guess on noisy similar-score
    #      results. Forensic ambiguity_forensic.md C-1 (IM_DTP3 query
    #      returning 5 TRGT_2030_IM_* siblings as a heuristic-ambiguous
    #      cluster while the curated pick was sitting there) motivates
    #      this reorder.
    #   2. ambiguity flag still set (curated _AMBIGUOUS path A or
    #      heuristic path B) AND no curated hit -> True, stop-and-ask.
    #   3. confident in-results top match (relevance >= 90 OR gap >= 15)
    #      -> False, canonical pick from search results.
    #   4. otherwise -> all four locals stay None (v1.0.0 wire-equivalent).
    from .curated import lookup_preferred

    RELEVANCE_GAP_THRESHOLD = 15
    requires_confirmation: bool | None = None
    recommended: dict[str, Any] | None = None
    assistant_guidance: str | None = None
    next_step: str | None = None

    curated_entry = lookup_preferred(query)
    if curated_entry is not None:
        requires_confirmation = False
        recommended = {
            "code": curated_entry["code"],
            "category": curated_entry["category"],
            "why": f"curated canonical pick for {curated_entry['family']} family",
        }
        hint = curated_entry.get("dimension_hint")
        hint_suffix = f" {hint}" if hint else ""
        assistant_guidance = (
            f"Curated match: '{query}' -> "
            f"{curated_entry['canonical_label']}. Call "
            f"get_indicator_info(code='{curated_entry['code']}'), "
            f"then get_data.{hint_suffix}"
        )
        next_step = f"get_indicator_info(code='{curated_entry['code']}')"
    # v1.2.0: synonym-resolver fallback. If the curated catalog had no
    # entry (the 5-char min-length guard rejects bare acronyms like
    # 'U5MR' / 'IMR' / 'NMR'), try the indicator_resolver's _SYNONYMS
    # table. A `synonym_match` or `code_passthrough` status means the
    # query resolves UNAMBIGUOUSLY to one canonical code; surface it
    # as recommended so search_indicators('U5MR') no longer returns
    # nothing useful for the LLM. Pure-additive: queries that DO hit
    # the curated catalog stay on the v1.1.x path above (the curated
    # picks the human-vetted variant, which may differ from the
    # resolver's bare-synonym pick by design — e.g. "stunting"
    # routes to the curated NT_ANT_STZ_MOD_SV, not the resolver's
    # NT_ANT_HAZ_NE2).
    elif (
        (_resolution := resolve_indicator(query))
        and _resolution.status in ("synonym_match", "code_passthrough")
        and _resolution.code
    ):
        requires_confirmation = False
        recommended = {
            "code": _resolution.code,
            "category": "",
            "why": (
                f"synonym match: '{query}' -> {_resolution.code} "
                f"({_resolution.name or 'canonical indicator'})"
            ),
        }
        assistant_guidance = (
            f"'{query}' resolves to "
            f"{_resolution.name or _resolution.code}. Call "
            f"get_indicator_info(code='{_resolution.code}'), then get_data."
        )
        next_step = f"get_indicator_info(code='{_resolution.code}')"
    elif payload.get("ambiguity_flag"):
        requires_confirmation = True
        assistant_guidance = (
            "Multiple UNICEF indicators match this query. Present the "
            "candidates list to the user and ask which one they mean "
            "before calling get_data."
        )
    elif results:
        top = results[0]
        top_rel = top.get("relevance", 0)
        runner_up_rel = results[1].get("relevance", 0) if len(results) > 1 else 0
        gap = top_rel - runner_up_rel
        if top_rel >= CANONICAL_RELEVANCE_THRESHOLD or gap >= RELEVANCE_GAP_THRESHOLD:
            requires_confirmation = False
            recommended = {
                "code": top["code"],
                "category": top.get("category", ""),
                "why": f"top match (score {top_rel}, gap {gap})",
            }
            assistant_guidance = (
                f"Strong match for '{query}'. Call "
                f"get_indicator_info(code='{top['code']}') to view "
                f"available disaggregations, then get_data."
            )
            next_step = f"get_indicator_info(code='{top['code']}')"

    return ok(
        payload,
        requires_confirmation=requires_confirmation,
        recommended=recommended,
        assistant_guidance=assistant_guidance,
        next_step=next_step,
    )


@mcp.tool()
def list_categories() -> dict[str, Any]:
    """List all UNICEF indicator categories (thematic groups).

    Categories correspond to SDMX dataflows: CME (child mortality), NUTRITION,
    EDUCATION, CHILD_PROTECTION, WASH, HIV_AIDS, etc.
    Use this to browse available topics before searching for specific indicators.
    """
    try:
        all_indicators = _get_indicators()
    except Exception as exc:
        return error(f"Failed to load indicator registry: {exc}")

    # Build category → indicator count mapping
    categories: dict[str, int] = {}
    for meta in all_indicators.values():
        cat = meta.get("category", "Uncategorized")
        categories[cat] = categories.get(cat, 0) + 1

    cat_list = [
        {"name": name, "indicator_count": count}
        for name, count in sorted(categories.items())
    ]

    return ok(
        {
            "total_categories": len(cat_list),
            "total_indicators": sum(c["indicator_count"] for c in cat_list),
            "categories": cat_list,
            "tip": (
                "Use search_indicators(query='mortality', limit=10)"
                " to find indicators in a category."
            ),
        }
    )


@mcp.tool()
def list_countries(region: str | None = None) -> dict[str, Any]:
    """List countries available in the UNICEF database with ISO3 codes.

    Optionally filter by region name (case-insensitive partial match).
    Use the iso3 values in get_data().
    """
    if err := validate_region(region):
        return error(err)
    try:
        country_map = _get_countries()
    except Exception as exc:
        return error(f"Failed to load country codes: {exc}")

    countries = [
        {"iso3": code, "name": name} for code, name in sorted(country_map.items())
    ]

    if region:
        region_lower = region.lower()
        countries = [c for c in countries if region_lower in c["name"].lower()]

    return ok(
        {
            "total": len(countries),
            "region_filter": region,
            "countries": countries,
        }
    )


# ---------------------------------------------------------------------------
# Step 2: Metadata tools
# ---------------------------------------------------------------------------


def _build_indicator_envelope(
    code: str, info: dict[str, Any]
) -> dict[str, Any]:
    """Shared envelope shape for ``get_indicator_info`` + ``lookup_by_code``.

    v1.2.0 single source of truth — pins the v1.1.x copy-paste hazard
    where both tools independently invented (and drifted on) the
    ``disaggregation_filters`` block.

    All dimension surface is grounded in the unicefdata-shipped YAML
    for the indicator's primary dataflow (via ``dimensions.py``):
      - tier-1 indicators with a known dataflow get the real dim menu
        plus a populated ``variants`` list of same-family siblings.
      - tier-2 family / aggregator codes get ``{"_source":
        "fallback_unknown", "dimensions": null}`` and empty variants.
    """
    primary_df = _dims.primary_dataflow(code)
    disagg = _dims.build_disaggregation_filters(code)
    meta = _dims.load_indicator_metadata().get(code) or {}
    tier = meta.get("tier")
    parent = meta.get("parent")

    variants: list[str] = []
    if tier == 1 and parent:
        family_prefix = code.split("_")[0]
        all_meta = _dims.load_indicator_metadata()
        siblings = [
            other_code
            for other_code, other_meta in all_meta.items()
            if other_code != code
            and other_meta.get("parent") == parent
            and other_code.startswith(family_prefix)
        ]
        variants = sorted(siblings)[:10]

    dimension_source = (
        "yaml_grounded"
        if tier == 1 and disagg.get("_source") != "fallback_unknown"
        else "no_dataflow_metadata"
    )

    return {
        "code": code,
        "name": info.get("name", ""),
        "description": info.get("description", ""),
        "category": info.get("category", ""),
        "dataflow": primary_df,
        "dataflow_used": primary_df,
        "sdmx_api": (
            f"https://sdmx.data.unicef.org/ws/public/sdmxapi/rest/data/"
            f"UNICEF,{primary_df or 'GLOBAL_DATAFLOW'},1.0/.{code}?format=csv"
        )
        if primary_df
        else None,
        "tier": tier,
        "dimension_source": dimension_source,
        "disaggregation_filters": disagg,
        "variants": variants,
    }


@mcp.tool()
def get_indicator_info(code: str) -> dict[str, Any]:
    """Get full metadata for a UNICEF indicator.

    Returns description, category, dataflow, and SDMX API details.
    Use this before calling get_data() to understand what the indicator measures
    and which disaggregation filters (sex, age, wealth_quintile, residence) apply.
    """
    try:
        ud = _get_ud()
        info = ud.get_indicator_info(code)
    except Exception as exc:
        return error(f"Failed to retrieve indicator info: {exc}")

    if info is None:
        return error(
            f"Indicator '{code}' not found in the UNICEF Data Warehouse.",
            tip="Use search_indicators('your topic') to find valid indicator codes.",
            no_data=True,
        )

    # v1.2.0: shared envelope with lookup_by_code; disaggregation_filters,
    # dataflow, variants, tier, and dimension_source all flow from
    # `dimensions.py` (YAML-grounded on the indicator's primary dataflow).
    result = _build_indicator_envelope(code, info)
    result["tip"] = (
        f"Use get_data(indicator='{code}', countries=['BRA','IND']) "
        "to fetch observations."
    )

    # Add semantic context (related indicators, disambiguation, SDG targets, methodology)
    context = get_indicator_context(code)
    if context:
        result.update(context)

    return ok(
        result,
        warnings=[
            "Disaggregation filters listed above are grounded in the shipped "
            "UNICEF metadata snapshot for this indicator's primary dataflow. "
            "Not all countries or years have data for every disaggregation — "
            "actual availability varies; check the data response for what "
            "was returned.",
        ],
    )


@mcp.tool()
def lookup_by_code(code: str) -> dict[str, Any]:
    """Strict canonical lookup of a UNICEF indicator by its exact code.

    Use this INSTEAD of search_indicators when you already have a
    UNICEF indicator code (e.g. CME_MRY0T4, IM_DTP3, ED_15-24_LR).
    Do NOT pass natural-language descriptions, synonyms, or partial
    names — this tool is canonical-only.

    Two-tool separation introduced in v0.9.0 to give the LLM a
    self-describing choice at tool-selection time:
      - have a CODE? → lookup_by_code(code)
      - have WORDS?  → search_indicators(query)

    Returns the same canonical metadata shape as get_indicator_info
    on success. On unknown code, returns an error with an explicit
    abstain_instruction directing the model to stop — NOT to fall
    back to search_indicators (which would re-enter the loop that
    96% of v9 Arm B stuck queries hit).

    Returns:
      - on success: {status: "ok", code, name, description, dataflow,
        sdmx_api, disaggregation_filters, ambiguity_flag: false, ...}
      - on unknown code: {status: "error", error, ambiguity_flag: false,
        abstain_instruction, tip}
      - on natural-language input mistakenly passed: {status: "error",
        error, abstain_instruction directing to search_indicators}
    """
    if err := validate_indicator(code):
        return error(err)

    # Reject natural-language input. resolve_indicator returns one of
    # five statuses; only `code_passthrough` is acceptable here (the
    # input is an exact match against the YAML's canonical code list).
    # synonym_match / ambiguous / name_index_hit / unknown all imply
    # the input wasn't a code — redirect to search_indicators instead
    # of silently resolving (which would defeat the two-tool design).
    from .indicator_resolver import resolve_indicator
    resolution = resolve_indicator(code)
    if resolution.status != "code_passthrough":
        return error(
            f"Input '{code}' is not a valid UNICEF indicator code.",
            tip=(
                "lookup_by_code requires an exact code (e.g. CME_MRY0T4). "
                "For natural-language queries use search_indicators instead. "
                "Do NOT invent a code or retry this tool with variants — "
                "STOP and pivot to search_indicators if you have words, "
                "or abstain if no canonical code is available."
            ),
            extra={
                "ambiguity_flag": False,
                "abstain_instruction": (
                    "Input does not match the canonical UNICEF code "
                    "registry. STOP — call search_indicators(query) with "
                    "a natural-language description, OR abstain. Do NOT "
                    "retry lookup_by_code with code variants."
                ),
                "resolver_status": resolution.status,
            },
        )

    # At this point resolution.code is the canonical code (uppercased).
    # Delegate to the same metadata-fetching path get_indicator_info uses
    # so the success shape stays consistent across the two tools.
    canonical_code = resolution.code or code
    try:
        ud = _get_ud()
        info = ud.get_indicator_info(canonical_code)
    except Exception as exc:
        return error(f"Failed to retrieve indicator info: {exc}")

    if info is None:
        # The code looked canonical to the resolver (passed code_passthrough)
        # but the unicefdata SDK has no metadata for it — codelist drift
        # between the resolver's YAML snapshot and the SDK's. Tell the
        # model to abstain rather than search-loop.
        return error(
            f"Indicator '{canonical_code}' is registered but no metadata "
            "is available from the UNICEF Data Warehouse.",
            tip="This is likely a codelist drift issue. Abstain.",
            extra={
                "ambiguity_flag": False,
                "abstain_instruction": (
                    "Code is registered but metadata is unavailable. "
                    "STOP — abstain. Do NOT fall back to search_indicators "
                    "or invent a value."
                ),
            },
        )

    # v1.2.0: shared envelope with get_indicator_info. The disaggregation_filters
    # block is the SAME dict (literal equality) for the same code across both
    # tools — pins the v1.1.x copy-paste hazard.
    result = _build_indicator_envelope(canonical_code, info)
    result["ambiguity_flag"] = False
    result["tip"] = (
        f"Use get_data(indicator='{canonical_code}', countries=['BRA','IND']) "
        "to fetch observations."
    )

    context = get_indicator_context(canonical_code)
    if context:
        result.update(context)

    return ok(
        result,
        warnings=[
            "Disaggregation filters listed above are grounded in the shipped "
            "UNICEF metadata snapshot for this indicator's primary dataflow. "
            "Not all countries or years have data for every disaggregation — "
            "actual availability varies; check the data response for what "
            "was returned.",
        ],
    )


@mcp.tool()
def get_temporal_coverage(code: str) -> dict[str, Any]:
    """Check what years of data are available for a UNICEF indicator.

    Fetches a small sample to determine the time range. Lightweight — does not
    fetch all observations. Use before get_data() to pick a year range.
    """
    try:
        ud = _get_ud()
        # Fetch a minimal sample: totals only, all countries, to get year range
        df = _retry(lambda: ud.unicefData(
            indicator=code,
            sex="_T",
            totals=True,
            tidy=True,
            country_names=False,
            simplify=True,
        ))
    except Exception as exc:
        return error(
            f"Failed to fetch temporal coverage for '{code}': {exc}",
            tip="Check that the indicator code is correct with search_indicators().",
        )

    if df.empty:
        return error(
            f"No data found for indicator '{code}' in the UNICEF Data Warehouse.",
            tip="Use search_indicators() to verify the indicator code.",
            no_data=True,
        )

    periods = df["period"].dropna()
    try:
        years = periods.astype(float).astype(int)
        start_yr = int(years.min())
        end_yr = int(years.max())
    except (ValueError, TypeError):
        # Non-numeric periods (e.g. "2019-Q1") — try to extract year prefix
        try:
            years = periods.astype(str).str[:4].astype(int)
            start_yr = int(years.min())
            end_yr = int(years.max())
        except (ValueError, TypeError):
            start_yr = 0
            end_yr = 0

    countries_col = country_col(df)
    n_countries = df[countries_col].nunique() if countries_col in df.columns else 0

    # Detect if this looks like a survey-based indicator (sparse years)
    warnings: list[str] = [
        "Not all countries have data for all years. Coverage varies by country.",
    ]
    if start_yr and end_yr:
        year_span = end_yr - start_yr + 1
        unique_years = len(set(years.unique())) if len(years) > 0 else 0
        if year_span > 5 and unique_years < year_span * 0.5:
            warnings.append(
                "This indicator appears to be survey-based (DHS/MICS) — "
                "data is collected every 3-5 years, not annually. "
                "Year gaps are normal and do NOT mean the data is missing."
            )

    return ok(
        {
            "code": code,
            "start_year": start_yr,
            "end_year": end_yr,
            "latest_year": end_yr,
            "countries_with_data": n_countries,
        },
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Step 3: Data retrieval
# ---------------------------------------------------------------------------


# Per-session cache of data frontier (max year observed) per indicator.
# Cleared at process restart. Avoids repeated coverage calls during the same
# session — typical use accesses 1-3 indicators, so the cache pays for itself
# within a few `get_data` calls. Bounded by indicator count (790 max).
_data_frontier_cache: dict[str, int] = {}


def _get_data_frontier(indicator: str) -> int | None:
    """Return the max year observed for `indicator` in the UNICEF Data
    Warehouse, or None if it can't be determined.

    Used by `get_data` for pre-flight year-frontier checks (v0.6.0+). Cached
    per session — lookup cost is amortized across all `get_data` calls for the
    same indicator.

    Implementation: calls the existing `get_temporal_coverage` machinery, which
    fetches a minimal totals-only sample to learn the year range. Returns the
    `end_year` field from that sample. None on lookup failure (treated as "no
    frontier check possible" — falls through to the API rather than blocking).
    """
    if indicator in _data_frontier_cache:
        return _data_frontier_cache[indicator]
    try:
        cov = get_temporal_coverage(indicator)
    except Exception:
        return None
    if not isinstance(cov, dict) or cov.get("status") != "ok":
        return None
    end_year = cov.get("end_year")
    if isinstance(end_year, int) and end_year > 0:
        _data_frontier_cache[indicator] = end_year
        return end_year
    return None


def _max_year_from_periods(periods: Any) -> int | None:
    """Best-effort max year extractor for a `period` series.

    Handles annual integers, float-cast integers ("2019.0"), and SDMX-style
    quarterly/monthly forms ("2019-Q1", "2019-M03") by taking the four-character
    year prefix. Returns None if no year can be extracted.
    """
    try:
        import pandas as pd
    except Exception:
        return None
    try:
        s = pd.Series(periods).dropna()
    except Exception:
        return None
    if s.empty:
        return None
    try:
        return int(s.astype(float).max())
    except (ValueError, TypeError):
        pass
    try:
        years = s.astype(str).str[:4].astype(int)
        if not years.empty:
            return int(years.max())
    except (ValueError, TypeError):
        pass
    return None


def _seed_data_frontier_cache(indicator: str, df: Any) -> None:
    """Populate the per-session frontier cache from a successful response.

    Avoids the duplicate-fetch pattern where the next `get_data` call with
    year args would re-issue the totals-only `get_temporal_coverage` request
    just to learn the same frontier we just observed in the response.

    Only updates the cache when the observed max year is *higher* than what
    is already cached. The response's df is filtered by the request's country
    list and start_year/end_year, so its `period.max()` reflects "max year
    in the bounded slice the user asked for" — not the indicator's true
    frontier. Lowering the cache from a year-bounded or country-bounded slice
    would refuse later valid queries (e.g., a Liberia 2023 query seeding the
    cache to 2023 would then refuse a Netherlands 2024 query for an indicator
    whose true frontier is 2024). Only monotonic-up updates are sound.
    """
    if not indicator:
        return
    try:
        if "period" not in df.columns:
            return
        max_year = _max_year_from_periods(df["period"])
    except Exception:
        return
    if max_year and max_year > 0:
        existing = _data_frontier_cache.get(indicator, 0)
        if max_year > existing:
            _data_frontier_cache[indicator] = max_year


@mcp.tool()
def get_data(
    indicator: str,
    countries: list[str],
    start_year: int | None = None,
    end_year: int | None = None,
    sex: str = "_T",
    age: str | None = None,
    filters: dict[str, str | None] | None = None,
    format: Literal["compact", "full"] = "compact",
    limit: int = 200,
    # v1.1.x removed-kwarg tripwires — direct Python callers still hit these.
    # Passing them returns the structured migration error (see below). The MCP
    # tool schema will advertise them with their docstring deprecation note,
    # so LLM callers also see the migration guidance up front.
    wealth_quintile: str | None = None,
    residence: str | None = None,
) -> dict[str, Any]:
    """Fetch UNICEF data for an indicator and one or more countries.

    Returns annual observations from the UNICEF SDMX API. Use format="compact"
    (default) for a clean 5-column table; use format="full" for all columns
    including disaggregation details and confidence bounds.

    **`indicator` accepts BOTH codes AND human-readable names** (v0.7.0). Pass
    whichever you have from the user's question — the server resolves names
    to canonical codes for you. Examples:
      indicator='CME_MRM0'                     → code passthrough
      indicator='neonatal mortality'           → resolves to 'CME_MRM0'
      indicator='Under-five mortality rate'    → resolves to 'CME_MRY0T4'
      indicator='U5MR'                         → resolves to 'CME_MRY0T4'
      indicator='stunting'                     → resolves to 'NT_ANT_HAZ_NE2'
      indicator='LBW' / 'low birth weight'     → resolves to 'NT_BW_LBW'
    Acronyms accepted: NMR, IMR, U5MR, SBR, LBW, ANC1, SAB, BCG, DTP1/3 …

    Genuinely ambiguous queries are refused with a disambiguation list. Examples:
      indicator='child mortality'      → refused: pick CME_MRM0 / CME_MRY0 /
                                          CME_MRY0T4 / CME_MRY1T4
      indicator='vaccination'          → refused: pick IM_BCG / IM_DTP1/3 / IM_MCV1/2

    **Prefer passing the user's phrasing verbatim over guessing the code from
    memory** — that's where the v0.6.x had a documented failure mode (model
    recalls `CME_MRY0T4` thinking it's neonatal mortality; it's under-five).
    The response echoes the resolution under `indicator_resolution` so you
    can confirm the canonical code+name match the user's intent.

    **`countries` accepts BOTH ISO3 codes AND country names** (v0.6.2). Pass
    whichever you have from the user's question — the server resolves country
    names to canonical ISO3 codes for you. Examples:
      countries=['Burundi']            → resolves to ['BDI']
      countries=['BDI', 'Belgium']     → resolves to ['BDI', 'BEL']
      countries=['Cote d\\'Ivoire']     → resolves to ['CIV']
      countries=['USA', 'UK']          → resolves to ['USA', 'GBR']
    Common synonyms accepted: 'USA'/'United States', 'UK'/'Great Britain',
    'Ivory Coast'/'Cote d\\'Ivoire', 'South Korea', 'DRC', 'Czech Republic',
    'Burma', 'Vatican', etc. The response echoes the resolution under
    `country_resolutions` and the canonical name+code pairs under
    `countries_returned_with_names` so you can confirm intent matched.

    **Prefer passing the user's country name verbatim over guessing the ISO3
    code from memory** — that's where v0.6.0 had a documented failure mode.

    **v0.6.0 server-side hardening**: this tool also performs a pre-flight
    year-frontier check. If `start_year` or `end_year` exceeds the indicator's
    data frontier (max year observed), the call is refused server-side without
    issuing the SDMX request — preventing the silent-truncation pattern where
    a range like 2020-2027 returns 2020-2024 and the model extrapolates the
    missing years. Successful responses include a `data_frontier` field
    naming the max year and an explicit no-extrapolation directive.

    Disaggregation filters (v1.2.0):
      sex: "_T" (total, default), "M" (male), "F" (female).
      age: SDMX AGE code such as "Y0T4", "Y15T19", "Y15T24". The age codelist
           depends on the indicator's dataflow — call `get_indicator_info(code)`
           to see what's supported.
      filters: dict[str, str | None] for every other dimension. Examples:
           filters={"WEALTH_QUINTILE": "Q1"}              → poorest quintile
           filters={"RESIDENCE": "U"}                     → urban
           filters={"EDUCATION_LEVEL": "ISCED11_2"}       → secondary
           filters={"WEALTH_QUINTILE": "Q1", "RESIDENCE": "U"}  → both
           A None value is treated as "use the dim's total" (typically "_T").

    When any non-`_T` filter is present (typed `age=` or `filters` dict
    non-empty), the response carries `mode: "raw_filtered"` to signal that
    the underlying call switched to `raw=True` + post-filter — same call,
    different number versus a totals-only response.

    Validation: filters are checked against the indicator's actual primary
    dataflow before the SDMX call. Unsupported (dim, value) pairs are
    refused with a `failed_validation` envelope listing available
    dimensions and codelist values, so the LLM can recover in a single
    wave instead of retrying blindly.

    BREAKING CHANGE FROM v1.1.x: the typed `wealth_quintile=` and
    `residence=` kwargs no longer route to the SDMX call — they are present
    in the signature only as deprecation trip-wires. Pass them and the call
    returns a structured migration error pointing at
    `filters={"WEALTH_QUINTILE": ...}`. v1.1.x silently dropped these
    kwargs at the SDMX call and returned the totals slice — that hazard
    is gone.

    Limit defaults to 200 rows — narrow your country/year filters or
    increase limit (max 500) if you need more data. In `raw_filtered` mode,
    `rows_truncated: true` also means the pre-filter raw pull was larger
    than `limit`, so post-filter rows you wanted may be missing.
    """
    # Validate inputs
    if err := validate_indicator(indicator):
        return error(err)

    # v0.7.0 indicator-name resolver: accept indicator codes OR human-readable
    # names. The model often picks indicator codes from training-data memory and
    # gets a similar-but-wrong one (e.g., wants neonatal mortality, recalls
    # CME_MRY0T4 instead of CME_MRM0). With server-side resolution, the model
    # can pass "neonatal mortality" verbatim and the server canonicalizes.
    indicator_input = indicator
    indicator_resolution = resolve_indicator(indicator)
    if indicator_resolution.status == "ambiguous":
        candidate_lines = "\n".join(
            f"  - {code}: {name}" for code, name in indicator_resolution.candidates
        )
        return error(
            f"Indicator '{indicator}' is ambiguous — it matches multiple codes. "
            f"Pass one of these specific codes (or a more precise name):\n{candidate_lines}",
            tip="Use search_indicators() if you need to browse further.",
            extra={"indicator_disambiguation": [
                {"code": code, "name": name}
                for code, name in indicator_resolution.candidates
            ]},
        )
    if indicator_resolution.status in (
        "code_passthrough",
        "synonym_match",
        "name_index_hit",
    ):
        # Adopt the canonical form for code_passthrough too: the resolver
        # uppercases and strips whitespace ("cme_mrm0" → "CME_MRM0"), so the
        # downstream SDMX call and the echoed `result["indicator"]` match the
        # YAML's canonical key. Without this, "  cme_mrm0  " would round-trip
        # verbatim and obscure successful matches in the response envelope.
        indicator = indicator_resolution.code or indicator
    # status == "unknown": leave indicator as-is. Unknown codes flow through
    # to the SDMX call which will 404; this preserves backward compatibility
    # for callers passing codes the resolver doesn't know about (e.g., new
    # indicators added upstream after the YAML snapshot).

    # v0.6.2 country-name resolver: accept ISO3 codes OR country names. The
    # model often calls get_data with the wrong ISO3 ("Burundi" → 'BEL')
    # because it's resolving the name from memory. Letting the server do the
    # canonical name → ISO3 mapping eliminates that failure mode entirely.
    if not countries:
        return error("At least one country (ISO3 code or name) is required.")
    if len(countries) > MAX_COUNTRIES:
        return error(
            f"Too many countries ({len(countries)}). Maximum is {MAX_COUNTRIES} per call. "
            "Split into multiple calls or use list_countries() to find a region filter."
        )
    if err := validate_country_inputs(countries):
        return error(err)
    resolved_codes, country_resolutions, unresolved = resolve_countries(countries)
    if unresolved:
        return error(
            f"Could not resolve country/countries: {', '.join(repr(u) for u in unresolved)}. "
            "Pass either the ISO3 code (e.g. 'BDI') or the country name (e.g. 'Burundi'). "
            "Common alternates accepted: 'USA'/'United States', 'UK'/'United Kingdom', "
            "'Ivory Coast'/'Cote d\\'Ivoire', 'South Korea', 'DRC', etc.",
            tip="Use list_countries() to enumerate valid codes and names.",
        )
    # Replace caller's input with canonical ISO3 codes for downstream use.
    # Keep the original `countries` list for echoing back to the caller.
    countries_input = countries
    countries = resolved_codes

    if err := validate_limit(limit):
        return error(err)
    if err := validate_year(start_year, "start_year"):
        return error(err)
    if err := validate_year(end_year, "end_year"):
        return error(err)
    if err := validate_sex(sex):
        return error(err)

    # v1.2.0 Commit 11 (Copilot #3328906514) — breaking-change tripwire
    # must fire BEFORE validate_age / validate_filters so v1.1.x callers
    # who pass the removed `wealth_quintile=` / `residence=` kwargs
    # alongside a malformed `age=` / `filters` see the migration
    # guidance first (the more actionable signal), not a generic
    # "filters must be a dict" / "age too long" error that hides the
    # actual root cause.
    removed_v1_1 = [
        name
        for name, val in (
            ("wealth_quintile", wealth_quintile),
            ("residence", residence),
        )
        if val is not None
    ]
    if removed_v1_1:
        named = ", ".join(repr(k) for k in sorted(removed_v1_1))
        return error(
            f"Removed in v1.2.0: {named}. Pass dimension filters via the new "
            "`filters` dict instead, e.g. "
            "filters={'WEALTH_QUINTILE': 'Q1', 'RESIDENCE': 'U'}. The new path "
            "validates the (dim, value) pair against the indicator's actual "
            "dataflow before the SDMX call and engages mode='raw_filtered' "
            "transparently.",
            tip="See CHANGELOG [1.2.0] Breaking subsection.",
            extra={
                "removed_kwargs": sorted(removed_v1_1),
                "migration": "filters_dict",
                "v1_2_0": True,
            },
        )

    if err := validate_age(age):
        return error(err)
    if err := validate_filters(filters):
        return error(err)

    # v1.2.0 pre-flight dimension validation. Build the unified filter set
    # (typed `age=` + free-form `filters` dict) and check every (dim, value)
    # triple against the indicator's actual dataflow before any SDMX call.
    # Refusal here is structured: the LLM sees `available_dimensions` and
    # can recover in a single wave instead of retrying blindly.
    effective_filters: dict[str, str] = {}
    if filters:
        for raw_k, raw_v in filters.items():
            if raw_v is None:
                continue  # None = "use this dim's total"; no SDMX filter
            effective_filters[raw_k.upper()] = raw_v
    # v1.2.0 Commit 11 (Copilot #3328906494) — reject conflicting AGE
    # before folding the typed `age=` kwarg into effective_filters. If
    # the caller passes both `age='Y15T19'` AND `filters={'AGE': 'Y0T4'}`,
    # silent precedence (filters wins) is the same v1.1.x-shaped silent-
    # drop hazard the PR was built to close. Same-value collisions are
    # harmless; reject only when the two values disagree.
    if age:
        filter_age = effective_filters.get("AGE")
        if filter_age is not None and filter_age != age:
            return error(
                f"Conflicting AGE: typed age='{age}' vs filters['AGE']="
                f"'{filter_age}'. Pass only one — the filters dict is the "
                "canonical v1.2.0 channel; the typed `age=` kwarg exists "
                "for backward compatibility.",
                tip="Drop one of the two arguments and retry.",
                extra={
                    "conflicting_kwargs": {
                        "age": age,
                        "filters.AGE": filter_age,
                    },
                },
            )
        # No collision (or same value) — set / keep.
        effective_filters["AGE"] = age

    # v1.2.0 Commit 8 — when raw_filtered mode is about to engage (any
    # AGE or filters dict entry is present), fold the `sex` value into
    # the post-filter. unicefdata's raw=True path bypasses the `sex=`
    # kwarg, so without this the response silently includes EVERY SEX
    # value (F, M, _T) instead of the requested slice — defeating the
    # v1.1.x default of `sex='_T'` (totals) on any raw_filtered query.
    # First_class mode (no AGE / no filters) keeps the v1.1.x semantics
    # where `sex` is honored natively by unicefdata's first-class kwarg.
    #
    # SEX already in the filters dict wins over the typed `sex=` kwarg —
    # the filters dict is the more-explicit channel in v1.2.0. The typed
    # `sex` default ('_T') would otherwise silently overwrite an
    # explicit filters={'SEX': 'F'}.
    if effective_filters and sex and "SEX" not in effective_filters:
        effective_filters["SEX"] = sex

    target_dataflow = _dims.primary_dataflow(indicator)

    # v1.2.0 follow-up — unconditional tier-2 refusal. The earlier shape
    # only fired when `effective_filters` was non-empty, so an unfiltered
    # call to a tier-2 family code (e.g. `get_data('CME', countries=...)`)
    # would fall through to `unicefdata`'s SDMX 404 path and surface as
    # a generic "no data" error, hiding the structured `tier_reason`
    # signal the LLM needs to pivot to `search_indicators()`. We
    # distinguish KNOWN tier-2 codes (refuse here with structure) from
    # UNKNOWN codes (let the SDMX 404 handler below catch them — its
    # message is already actionable: "check indicator code with
    # search_indicators()").
    indicator_meta = _dims.load_indicator_metadata().get(indicator)
    if indicator_meta and indicator_meta.get("tier") == 2:
        return error(
            f"Indicator '{indicator}' is a tier-2 family / aggregator code "
            "(metadata only, no SDMX data). Tier-2 codes group related "
            "tier-1 indicators; use search_indicators() to find a "
            "queryable child indicator.",
            tip="Pick a tier-1 child code, then retry get_data().",
            no_data=True,
            extra={
                "tier": 2,
                "tier_reason": indicator_meta.get(
                    "tier_reason", "no_dataflow_metadata"
                ),
                "indicator": indicator,
            },
        )

    if effective_filters:
        # target_dataflow is None for KNOWN tier-2 codes (handled above)
        # or UNKNOWN codes. Tier-2 was caught; this catches the
        # unknown-code-with-filters case where we can't validate.
        if target_dataflow is None:
            return error(
                f"Indicator '{indicator}' has no associated dataflow metadata "
                "in the unicefdata snapshot. Filter pre-flight cannot "
                "proceed, and the SDMX call would fail.",
                tip=(
                    "Confirm the code via search_indicators() — the snapshot "
                    "may be out of date, or the code may be misspelled."
                ),
                extra={
                    "indicator": indicator,
                    "metadata_status": "unknown_code",
                },
            )
        # Validate each (dim, value). v1.2.0 Commit 11 (Copilot
        # #3328906519): fetch the dim menu ONCE here; dimension_supported
        # would otherwise call dimensions_for_indicator twice per rejected
        # filter (once for the True/False decision, once for the reason).
        # Bounded by validate_filters' MAX=20 so even pre-Commit-11 this
        # wasn't a hot path, but the lookup-once shape also makes the
        # rejection-reason logic clearer.
        rejected: list[dict[str, str]] = []
        dims_menu = _dims.dimensions_for_indicator(indicator)
        for dim_id, val in effective_filters.items():
            if val == "_T":
                continue  # totals always supported
            if dim_id in dims_menu and val.upper() in {
                str(v).upper() for v in dims_menu[dim_id]
            }:
                continue
            reason = "invalid_value" if dim_id in dims_menu else "unsupported_dim"
            rejected.append({"reason": reason, "dim": dim_id, "value": val})
        if rejected:
            return error(
                f"Pre-flight filter validation failed for indicator "
                f"'{indicator}'. The indicator's primary dataflow "
                f"('{target_dataflow}') does not accept the requested "
                "filter(s). Inspect `failed_validation.available_dimensions` "
                "to see what this indicator actually supports.",
                tip="Call get_indicator_info() to see the dim menu.",
                extra={
                    "failed_validation": {
                        "indicator": indicator,
                        "dataflow_used": target_dataflow,
                        "rejected": rejected,
                        "available_dimensions": (
                            _dims.dimensions_for_indicator(indicator)
                        ),
                    },
                    "dataflow_used": target_dataflow,
                },
            )

    # v0.6.0 pre-flight year-frontier check.
    # Refuse calls where requested year(s) exceed the indicator's data frontier,
    # WITHOUT issuing the SDMX request. The "silent retry" hallucination pattern
    # (model asks 2027 → no_data → asks 2020-2027 → API returns 2020-2024 → model
    # extrapolates) is broken because the broader range is now refused too.
    if start_year is not None or end_year is not None:
        max_year = _get_data_frontier(indicator)
        if max_year is not None:
            target_start = start_year if start_year is not None else end_year
            target_end = end_year if end_year is not None else start_year
            if target_start is not None and target_start > max_year:
                return error(
                    f"Year {target_start} exceeds the data frontier ({max_year}) "
                    f"for indicator '{indicator}'. The UNICEF Data Warehouse does "
                    f"not have observations beyond {max_year} for this indicator.",
                    tip=f"Narrow start_year to {max_year} or earlier.",
                    no_data=True,
                    extra={
                        "data_frontier": {
                            "max_year_observed": max_year,
                            "indicator": indicator,
                        },
                        "out_of_frontier": True,
                    },
                )
            if target_end is not None and target_end > max_year:
                return error(
                    f"Requested range {start_year or '...'}-{target_end} extends "
                    f"past the data frontier ({max_year}) for indicator "
                    f"'{indicator}'. The API will not silently truncate to "
                    f"{max_year} on your behalf — that pattern is a known "
                    f"source of forward-of-frontier extrapolation.",
                    tip=f"Narrow end_year to {max_year} or earlier.",
                    no_data=True,
                    extra={
                        "data_frontier": {
                            "max_year_observed": max_year,
                            "indicator": indicator,
                        },
                        "out_of_frontier": True,
                    },
                )

    # Build year argument (unicefdata accepts "start:end" range syntax)
    year_arg = None
    if start_year is not None and end_year is not None:
        year_arg = f"{start_year}:{end_year}"
    elif start_year is not None:
        year_arg = f"{start_year}:2099"
    elif end_year is not None:
        year_arg = f"1900:{end_year}"

    # v1.2.0: route to the indicator's actual primary dataflow (not
    # GLOBAL_DATAFLOW), and engage raw=True + post-filter when any
    # non-`_T` filter is present. `mode='first_class'` is the v1.1.x
    # behaviour for sex-only / unfiltered queries — same payload shape,
    # same wave count.
    mode = "first_class"
    ud_kwargs: dict[str, Any] = {
        "indicator": indicator,
        "countries": [c.upper() for c in countries],
        "year": year_arg,
        "sex": sex,
        "tidy": True,
        "country_names": True,
        "simplify": True,
    }
    if target_dataflow is not None:
        ud_kwargs["dataflow"] = target_dataflow
    if effective_filters:
        mode = "raw_filtered"
        ud_kwargs["raw"] = True

    try:
        ud = _get_ud()
        df = _retry(lambda: ud.unicefData(**ud_kwargs))
    except Exception as exc:
        exc_str = str(exc)
        exc_lower = exc_str.lower()
        # "not found" (lowercase) catches `unicefdata.unicefdata.SDMXNotFoundError:
        # Indicator 'X' not found in any dataflow.` — the cascade-end exception
        # raised after `unicefdata` walks its hardcoded fallback dataflow chain
        # for indicators whose primary dataflow returned 404. Treating that as
        # no_data lets the model receive a clean "no data" verdict and refuse
        # honestly, instead of receiving a generic error that confuses its
        # tool-loop heuristics. See unicefdata-dev issue tracking the upstream
        # behavior (filed alongside this commit).
        is_not_found = (
            "404" in exc_str
            or "not found" in exc_lower
            or "does not exist" in exc_lower
            or "not found in any dataflow" in exc_lower
        )
        return error(
            f"Data fetch failed: {exc}",
            tip=(
                "Check indicator code with search_indicators() "
                "and country codes with list_countries()."
            ),
            no_data=is_not_found,
        )

    if df.empty:
        return error(
            "No data exists in the UNICEF Data Warehouse for this indicator, "
            "country, and year combination.",
            tip="Try broader filters: remove year range or add more countries.",
            no_data=True,
        )

    # v1.2.0 post-fetch for raw_filtered mode (3 stages):
    #
    # (1) COUNTRY FILTER — upstream `ud.unicefData(raw=True)` does NOT
    #     honour `countries=[...]`; the response carries every country
    #     in the dataflow (173 for HIV_AIDS as of 2026-05). Without
    #     this filter, the user asks for THA and gets 173 countries'
    #     worth of rows. Fixes Commit 6 Bug A.
    #
    # (2) DIM FILTER — apply the user's effective_filters (already
    #     pre-flight-validated against the indicator's actual dataflow).
    #
    # (3) AUTO-TOTALS FALLBACK — when the dim filter yields 0 rows
    #     (the requested (country, dim) combination has no observations
    #     in the upstream snapshot), re-fetch the indicator's TOTALS
    #     slice (no dim filter) and return THAT, with an `alert` field
    #     describing the substitution and a `dimensions_available` menu
    #     so the LLM can pick a valid slice without another tool round-
    #     trip. Costs +1 SDMX call on the unhappy path; saves +1 LLM
    #     wave per affected query.
    fallback_alert: str | None = None
    effective_filters_original = dict(effective_filters)  # snapshot for envelope
    if mode == "raw_filtered" and not df.empty:
        # (1) country filter
        df = _dims.filter_by_dimensions(
            df, {"REF_AREA": [c.upper() for c in countries]}
        )
        # (2) dim filter
        df_filtered = _dims.filter_by_dimensions(df, effective_filters)
        if df_filtered.empty:
            # (3) auto-totals fallback
            fallback_kwargs = {k: v for k, v in ud_kwargs.items() if k != "raw"}
            df_totals: Any = None
            try:
                df_totals = _retry(lambda: ud.unicefData(**fallback_kwargs))
            except Exception:  # noqa: BLE001 — best-effort; falls through to no_data
                df_totals = None
            if df_totals is None or df_totals.empty:
                return error(
                    f"Filtered slice is empty for indicator '{indicator}' "
                    f"with filters {effective_filters!r} AND the totals "
                    "fallback also returned no data. The (dim, value) "
                    "pairs are valid (pre-flight passed) but no observations "
                    "exist for any slice of this indicator on the requested "
                    "countries / year range.",
                    tip=(
                        "Broaden the country list or year range; try a "
                        "different indicator from search_indicators()."
                    ),
                    no_data=True,
                    extra={
                        "mode": mode,
                        "dataflow_used": target_dataflow,
                        "applied_filters": effective_filters,
                        "dimensions_available": (
                            _dims.dimensions_for_indicator(indicator)
                        ),
                    },
                )
            df = df_totals
            mode = "totals_fallback"
            fallback_alert = (
                f"Requested filter {effective_filters!r} returned 0 rows "
                f"for the selected countries. Returning the indicator's "
                "TOTALS (no dim filter) so you don't have to re-call. "
                "Other dimension values that DO have data for this "
                "indicator are in `dimensions_available` — pick one and "
                "re-issue get_data with the corrected filter."
            )
            # totals_fallback re-uses the first_class column shape
            # (`simplify=True` is on for this re-fetch). Reset
            # effective_filters since we dropped them.
            effective_filters = {}
        else:
            df = df_filtered

    # v1.2.0 Commit 7: normalise SDMX-shape raw=True column names
    # (REF_AREA / OBS_VALUE / TIME_PERIOD / SEX / AGE / ...) to the
    # canonical lowercase shape every downstream helper expects.
    # Without this, summarize_data / summarize_disaggregations /
    # compute_trend / _seed_data_frontier_cache / sparse-year check /
    # data_frontier observation / countries_returned_with_names all
    # silently no-op on raw=True responses, producing thin envelopes
    # that diverge from the first_class path's envelope.
    df = normalize_columns(df)

    # Seed the per-session frontier cache from this response so subsequent
    # `get_data` calls for the same indicator skip the duplicate totals-only
    # `get_temporal_coverage` round-trip in `_get_data_frontier`.
    _seed_data_frontier_cache(indicator, df)

    # Generate summary before formatting (uses full DataFrame)
    data_summary = summarize_data(df)
    disagg_summary = summarize_disaggregations(df)

    # Apply format
    if format == "compact":
        records = to_compact(df)
        columns = ["iso3", "country", "period", "indicator", "value"]
    else:
        records = to_full(df)
        columns = list(df.columns)

    total_rows = len(records)
    records, truncated = apply_limit(records, limit)

    # --- Detect warnings and data completeness ---
    warnings: list[str] = []
    completeness = "complete"

    # Check for missing countries (requested but not in results)
    countries_col = country_col(df)
    if countries_col in df.columns:
        returned_countries = set(df[countries_col].str.upper().unique())
        requested_upper = {c.upper() for c in countries}
        missing_countries = requested_upper - returned_countries
        if missing_countries:
            missing_str = ", ".join(sorted(missing_countries))
            warnings.append(
                f"No data returned for: {missing_str}. "
                "These countries may lack data for this indicator, year range, "
                "or disaggregation. Do NOT estimate values for missing countries."
            )
            completeness = "partial"

    if truncated:
        completeness = "truncated"
        filter_tip = ""
        if disagg_summary:
            dims = ", ".join(disagg_summary.keys())
            filter_tip = f" Data contains disaggregations by {dims} — filter to reduce rows."
        warnings.append(
            f"Results truncated: showing {len(records)} of {total_rows} rows.{filter_tip}"
            f" Increase limit (max 500) or narrow filters to see all data."
        )

    # Check for sparse year coverage (gaps in time series). Tolerate non-numeric
    # periods (e.g. SDMX quarterly "2019-Q1") by taking the four-char year prefix.
    if "period" in df.columns and start_year is not None and end_year is not None:
        expected_years = set(range(start_year, end_year + 1))
        try:
            periods_s = df["period"].dropna()
            try:
                actual_years = set(periods_s.astype(float).astype(int).unique())
            except (ValueError, TypeError):
                actual_years = set(periods_s.astype(str).str[:4].astype(int).unique())
        except (ValueError, TypeError, KeyError):
            actual_years = set()
        if actual_years:
            missing_years = expected_years - actual_years
            if len(missing_years) > len(expected_years) * 0.5 and len(missing_years) > 2:
                warnings.append(
                    "Sparse year coverage — this indicator may be survey-based "
                    "(DHS/MICS, collected every 3-5 years). Year gaps are expected "
                    "and do NOT indicate missing data. Do NOT interpolate."
                )
                if completeness == "complete":
                    completeness = "partial"

    # v0.6.1 — extract resolved country names so the model sees the human-readable
    # name of every country returned. Mitigates the country-substitution failure
    # mode revealed at n=500 (model calls get_data with the wrong ISO3 code and
    # the response had no prominent name to flag the mismatch).
    #
    # v1.2.0 Commit 7 — fallback to `lookup_country_name` when the payload has
    # no country-name column (the raw=True / SDMX path returns REF_AREA codes
    # only; the simplified path with country_names=True carries the names).
    # Without this, the raw_filtered envelope had an empty
    # countries_returned_with_names, defeating the v0.6.1 protection.
    countries_returned_with_names: dict[str, str] = {}
    if countries_col in df.columns:
        # Find the country-name column. unicefdata uses "country" with
        # country_names=True; tests simulate "country_name". Accept either.
        name_col = next(
            (c for c in ("country", "country_name") if c in df.columns), None
        )
        if name_col:
            unique_pairs = df[[countries_col, name_col]].drop_duplicates()
            for code, name in unique_pairs.itertuples(index=False):
                if isinstance(code, str) and isinstance(name, str):
                    countries_returned_with_names[code.upper()] = name
        else:
            # raw=True path: fill names from the country_resolver index.
            unique_codes = df[countries_col].dropna().unique()
            for raw_code in unique_codes:
                if not isinstance(raw_code, str):
                    continue
                iso3 = raw_code.upper()
                name = lookup_country_name(iso3)
                if name:
                    countries_returned_with_names[iso3] = name

    result: dict[str, Any] = {
        "indicator": indicator,
        # v0.7.0: indicator name → code resolution performed server-side. The
        # `status` field tells the model whether the input was a code passthrough,
        # a synonym match, a name-index hit, or (for ambiguous cases, returned as
        # an error not here) a refusal. The `name` is the canonical display name.
        "indicator_resolution": {
            "original_input": indicator_input,
            "resolved_code": indicator_resolution.code or indicator,
            "canonical_name": indicator_resolution.name,
            "status": indicator_resolution.status,
        },
        "countries_requested": countries_input,
        "countries_resolved_to": countries,
        # v0.6.2: name → ISO3 resolutions performed server-side. Empty if the
        # caller passed only ISO3 codes. If non-empty, the model can confirm
        # "Burundi → BDI" and proceed without worrying about its own ISO3 memory.
        "country_resolutions": country_resolutions,
        "countries_returned_with_names": countries_returned_with_names,
        "verify_country_directive": (
            "Country resolution: see `country_resolutions` and "
            "`countries_returned_with_names`. If the names there match what "
            "the user asked about, proceed. If you passed an ISO3 code and "
            "the returned country name doesn't match the user's question, "
            "retry with the country NAME instead of the code — the server "
            "will resolve it canonically."
        ),
        "total_rows_available": total_rows,
        "rows_returned": len(records),
        "rows_truncated": truncated,
        # v1.2.0 envelope additions. `mode` tells the LLM which SDMX path
        # served this answer ('first_class' = same as v1.1.x; 'raw_filtered'
        # = raw=True + post-filter, possibly truncated). `dataflow_used`
        # surfaces which of the indicator's dataflows was queried — useful
        # when the indicator's metadata lists multiple. `truncated` is the
        # raw_filtered-aware view of rows_truncated (same value; the
        # rename is for the wave-count optimization, since LLMs key off
        # exact field names).
        "mode": mode,
        "format": format,
        "columns": columns,
        "summary": data_summary,
        "data": records,
    }
    if target_dataflow is not None:
        result["dataflow_used"] = target_dataflow
    if mode == "raw_filtered":
        result["applied_filters"] = effective_filters
        result["truncated"] = truncated
    if mode == "totals_fallback":
        # Auto-fallback fired: original filter yielded no rows; the LLM
        # sees the totals slice instead of erroring. Surface what was
        # requested so the model can pick a valid (dim, value) pair on
        # the next wave if it cares about the original disaggregation.
        result["filter_requested_no_data"] = effective_filters_original
        if fallback_alert is not None:
            result["alert"] = fallback_alert

    # Issue #77 — units envelope field. The simplified path that
    # serves first_class mode strips UNIT_MEASURE and UNIT_MULTIPLIER,
    # so a value like `0.188` for DM_POP_U5 NIU 2001 surfaces with
    # no context — Haiku interpreted it as 188 (thousands) on v1.0.0
    # and 188,000 (millions) on v1.1.0. The raw=True paths
    # (raw_filtered, totals_fallback) carry the unit columns in `df`
    # directly; first_class mode needs a separate cached resolver
    # (one SDMX round-trip per indicator per process).
    units: dict[str, Any] | None = _dims.units_from_dataframe(df)
    if units is None and mode == "first_class":
        units = _dims.unit_info_for(indicator, target_dataflow)
    if units:
        result["units"] = units

    # v1.2.0 dim-menu pull-forward (v1.3.0 candidate): surface the
    # indicator's full dim menu on every successful response. Lets the
    # LLM discover available disaggregations without a second tool call
    # to `get_indicator_info`. For tier-2 indicators (no dataflow
    # metadata) this is an empty dict, which the LLM should read as "no
    # additional disaggregations available".
    dims_avail = _dims.dimensions_for_indicator(indicator)
    if dims_avail:
        result["dimensions_available"] = dims_avail

    # Include disaggregation summary if there are non-trivial dimensions
    if disagg_summary:
        result["disaggregations_in_data"] = disagg_summary

    # Compute annualized rate of change (trend over last 5 years)
    trend = compute_trend(df, window=5)
    if trend:
        result["trend_5yr"] = trend

    # Source citation — verifiable SDMX API URL
    country_str = "+".join(c.upper() for c in countries)
    result["citation"] = {
        "provider": "UNICEF Data Warehouse",
        "api_url": (
            f"https://sdmx.data.unicef.org/ws/public/sdmxapi/rest/data/"
            f"UNICEF,GLOBAL_DATAFLOW,1.0/{country_str}.{indicator}"
            f"?format=csv&startPeriod={start_year or ''}&endPeriod={end_year or ''}"
        ),
        "web_url": "https://data.unicef.org/",
        "note": "Verify values at the URLs above before citing in publications.",
    }

    # v0.6.0 — embed data frontier in successful responses so the model has
    # the boundary in context at the moment it composes its answer (not just
    # on the failure path). Computed from the response itself when possible
    # (most accurate); falls back to the cached frontier from the indicator's
    # full coverage. The directive names the user-visible behavior to enforce.
    max_year_in_response: int | None = None
    if "period" in df.columns:
        max_year_in_response = _max_year_from_periods(df["period"])
    if max_year_in_response is None:
        max_year_in_response = _get_data_frontier(indicator)
    if max_year_in_response:
        result["data_frontier"] = {
            "max_year_observed": max_year_in_response,
            "indicator": indicator,
            "directive": (
                f"Data does not exist beyond {max_year_in_response} for this "
                f"indicator. Do not extrapolate, project, or estimate values "
                f"for years > {max_year_in_response}. If the user asked about "
                f"a year > {max_year_in_response}, respond 'No data is available "
                f"for [year]' and do not provide a numeric answer."
            ),
        }

    if not truncated:
        result["tip"] = None

    return ok(result, warnings=warnings or None, data_completeness=completeness)


# ---------------------------------------------------------------------------
# Step 4: Code reference (local, no API call)
# ---------------------------------------------------------------------------


@mcp.tool()
def get_api_reference(
    language: str = "python",
    function: str | None = None,
) -> dict[str, Any]:
    """Get the unicefdata package API reference for Python, R, or Stata.

    Returns function signatures, parameter descriptions, and usage examples.
    Use this when you need to write code that uses the unicefdata package,
    or when the user wants to move from conversational exploration to
    reproducible scripts.

    Args:
        language: "python", "r", or "stata"
        function: Specific function name (e.g. "unicefData", "search_indicators").
                  If None, returns all functions for the language.
    """
    lang = language.lower()
    if lang not in VALID_LANGUAGES:
        return error(
            f"Unknown language: '{language}'. Valid: python, r, stata",
            tip="Use get_api_reference(language='python') for the Python API.",
        )

    ref = REFERENCES[lang]

    if function:
        func_ref = ref["functions"].get(function)
        if func_ref is None:
            available = ", ".join(ref["functions"].keys())
            return error(
                f"Function '{function}' not found for {lang}.",
                tip=f"Available functions: {available}",
            )
        return ok(
            {
                "language": lang,
                "install": ref["install"],
                "import": ref["import"],
                "function": function,
                **func_ref,
            }
        )

    # Return all functions for the language
    return ok(
        {
            "language": lang,
            "install": ref["install"],
            "import": ref["import"],
            "functions": {
                name: {
                    "signature": f["signature"],
                    "returns": f["returns"],
                    "example_count": len(f["examples"]),
                }
                for name, f in ref["functions"].items()
            },
            "tip": (
                f"Use get_api_reference(language='{lang}',"
                f" function='unicefData') for full details + examples."
            ),
        }
    )


# ---------------------------------------------------------------------------
# MCP Prompts
# ---------------------------------------------------------------------------


# --- compare_indicators ---


@mcp.prompt()
def compare_indicators(
    indicator: str,
    countries: str,
    start_year: str = "2015",
    end_year: str = "2023",
) -> str:
    """Compare a UNICEF indicator across countries over time.

    Pre-built analysis workflow: fetches indicator metadata and data, then asks
    for a structured comparison including trends, regional patterns, and caveats.

    Args:
        indicator: Indicator code (e.g. "CME_MRY0T4")
        countries: Comma-separated ISO3 codes (e.g. "BRA,IND,NGA")
        start_year: Start year for comparison (default "2015")
        end_year: End year for comparison (default "2023")
    """
    # repr-safe formatting: use json.dumps for the country list literal so that
    # any embedded quote/special character in user input is escaped instead of
    # silently breaking the rendered Python literal in the prompt body.
    country_list = [c.strip().upper() for c in countries.split(",") if c.strip()]
    country_display = ", ".join(country_list)
    country_list_literal = json.dumps(country_list)
    indicator_literal = json.dumps(indicator)

    return (
        f"I need to compare the UNICEF indicator {indicator} across "
        f"{country_display} from {start_year} to {end_year}.\n\n"
        f"Please:\n"
        f"1. Call get_indicator_info({indicator_literal}) to understand what this "
        f"indicator measures\n"
        f"2. Call get_data(indicator={indicator_literal}, "
        f"countries={country_list_literal}, "
        f"start_year={start_year}, end_year={end_year}, format='compact') "
        f"to fetch the data\n"
        f"3. Analyze the results:\n"
        f"   - Show a summary table of values by country and year\n"
        f"   - Identify trends (improving, worsening, stagnant) per country\n"
        f"   - Highlight the best and worst performers\n"
        f"   - Note any data gaps or caveats\n"
        f"   - If relevant, suggest related indicators to explore\n"
    )


# --- write_unicefdata_code ---


@mcp.prompt()
def write_unicefdata_code(
    task: str,
    language: str = "python",
) -> str:
    """Generate unicefdata code for a data analysis task.

    Takes a plain-language description of what the user wants to do and
    generates runnable code in Python, R, or Stata using the unicefdata package.

    Args:
        task: What the user wants to do (e.g. "Compare under-5 mortality for
              Brazil and India from 2015 to 2023, then plot the trends")
        language: "python", "r", or "stata"
    """
    lang = language.lower()
    if lang not in VALID_LANGUAGES:
        lang = "python"

    ref = REFERENCES[lang]

    return (
        f"The user wants to write {lang} code using the unicefdata package.\n\n"
        f"**Task:** {task}\n\n"
        f"**Instructions:**\n"
        f"1. Call get_api_reference(language='{lang}', function='unicefData') to get "
        f"the exact function signature, parameters, and examples\n"
        f"2. If you need to find indicator codes, call search_indicators() first\n"
        f"3. Write complete, runnable {lang} code that accomplishes the task\n"
        f"4. Include the install/import lines:\n"
        f"   - Install: `{ref['install']}`\n"
        f"   - Import: `{ref['import']}`\n"
        f"5. Add brief comments explaining each step\n"
        f"6. If the task involves visualization, use the standard plotting library "
        f"for the language (matplotlib for Python, ggplot2 for R, twoway for Stata)\n\n"
        f"**Important:** Use the exact parameter names and syntax from the API reference. "
        f"Do not guess — the reference is authoritative.\n"
    )


# --- trend_analysis ---


@mcp.prompt()
def trend_analysis(
    indicator: str,
    country: str,
    start_year: str = "2000",
    end_year: str = "2024",
) -> str:
    """Analyze the trend of a UNICEF indicator for a single country over time.

    Fetches the full time series and produces a structured trend assessment
    with annualized rate of change, inflection points, and policy context.

    Args:
        indicator: Indicator code (e.g. "CME_MRY0T4") or name (e.g. "under-five mortality")
        country: ISO3 code (e.g. "NGA") or country name (e.g. "Nigeria")
        start_year: Start year (default "2000")
        end_year: End year (default "2024")
    """
    return (
        f"Analyze the trend for UNICEF indicator '{indicator}' in {country} "
        f"from {start_year} to {end_year}.\n\n"
        f"Steps:\n"
        f"1. If '{indicator}' is not an indicator code, call search_indicators('{indicator}') "
        f"to find the code\n"
        f"2. Call get_indicator_info(code) to understand the indicator, its unit, and SDG target\n"
        f"3. Call get_data(indicator=code, countries=['{country}'], "
        f"start_year={start_year}, end_year={end_year}, format='compact') to fetch the series\n"
        f"4. Analyze:\n"
        f"   - Report the value at start, end, and any notable inflection points\n"
        f"   - Calculate the annualized rate of change (AARC)\n"
        f"   - Classify the trend: rapid improvement, slow improvement, stagnant, worsening\n"
        f"   - Compare to the SDG target (if available from indicator info)\n"
        f"   - Note data gaps (years with no observation)\n"
        f"   - Suggest what might explain changes (conflicts, policy shifts, data revisions)\n"
        f"5. If the indicator has disaggregations (sex, residence), suggest fetching "
        f"disaggregated data to check for equity gaps\n"
    )


# --- country_profile ---


@mcp.prompt()
def country_profile(
    country: str,
) -> str:
    """Generate a child development profile for a country using key UNICEF indicators.

    Fetches the latest values for a curated set of child health, nutrition,
    education, and protection indicators and presents them as a country brief.

    Args:
        country: ISO3 code (e.g. "NGA") or country name (e.g. "Nigeria")
    """
    core_indicators = [
        ("CME_MRY0T4", "Under-five mortality rate"),
        ("CME_MRM0", "Neonatal mortality rate"),
        ("NT_ANT_HAZ_NE2", "Stunting prevalence"),
        ("NT_ANT_WHZ_NE2", "Wasting prevalence"),
        ("ED_CR_L1", "Primary education completion rate"),
        ("MNCH_CSEC", "C-section rate"),
    ]
    indicator_list = "\n".join(
        f"   - {code} ({name})" for code, name in core_indicators
    )

    return (
        f"Create a child development profile for {country}.\n\n"
        f"Steps:\n"
        f"1. For each of these core indicators, call get_data() to fetch the latest value:\n"
        f"{indicator_list}\n"
        f"2. Present a structured country brief:\n"
        f"   - **Country**: {country} (include region and income group)\n"
        f"   - **Child Survival**: U5MR + neonatal mortality, trend direction\n"
        f"   - **Nutrition**: stunting + wasting, prevalence and severity classification\n"
        f"   - **Education**: primary completion rate\n"
        f"   - **Maternal Health**: C-section rate (too low = underserved, too high = overuse)\n"
        f"3. For each indicator, note:\n"
        f"   - The latest value and year\n"
        f"   - Whether it's above/below regional and global averages\n"
        f"   - The trend (improving/worsening) if data spans multiple years\n"
        f"4. Conclude with 2-3 key takeaways about the country's child development status\n"
        f"5. Cite the SDMX source URLs from the tool responses\n"
    )


# --- sdg_progress ---


@mcp.prompt()
def sdg_progress(
    country: str,
) -> str:
    """Assess a country's progress on child-related SDG targets using UNICEF data.

    Maps UNICEF indicators to SDG targets (3.2, 2.2, 4.1) and reports
    whether the country is on track, needs acceleration, or is off-track.

    Args:
        country: ISO3 code (e.g. "NGA") or country name (e.g. "Nigeria")
    """
    sdg_map = [
        ("SDG 3.2.1", "CME_MRY0T4", "Under-five mortality", "<=25 per 1,000 by 2030"),
        ("SDG 3.2.2", "CME_MRM0", "Neonatal mortality", "<=12 per 1,000 by 2030"),
        ("SDG 2.2.1", "NT_ANT_HAZ_NE2", "Stunting", "Reduce by 40% from 2012 baseline"),
        ("SDG 2.2.2", "NT_ANT_WHZ_NE2", "Wasting", "<=3% by 2030"),
        ("SDG 4.1", "ED_CR_L1", "Primary completion", "100% by 2030"),
    ]
    map_text = "\n".join(
        f"   - {sdg}: {name} ({code}) — target: {target}"
        for sdg, code, name, target in sdg_map
    )

    return (
        f"Assess {country}'s progress on child-related SDG targets.\n\n"
        f"SDG indicator mapping:\n{map_text}\n\n"
        f"Steps:\n"
        f"1. For each SDG indicator, call get_data() to fetch the latest value and "
        f"a 2015-latest time series\n"
        f"2. For each target, assess:\n"
        f"   - **Current value** and year\n"
        f"   - **2015 baseline** (or earliest available)\n"
        f"   - **Required annual rate of reduction** to meet the 2030 target\n"
        f"   - **Actual annual rate of change** (from the time series)\n"
        f"   - **Status**: On track / Needs acceleration / Off track / Achieved\n"
        f"3. Present as a summary table:\n"
        f"   | SDG | Indicator | Latest | Target | Status |\n"
        f"4. Highlight which targets are achievable and which require urgent intervention\n"
        f"5. Note data limitations (survey gaps, model estimates vs survey data)\n"
    )


# ---------------------------------------------------------------------------
# MCP Resources — preloaded reference data, no tool call needed
# ---------------------------------------------------------------------------

LLM_INSTRUCTIONS = """\
# UNICEF Stats MCP — Instructions for AI Assistants

## Workflow
1. **search_indicators(query)** → find indicator codes
2. **get_indicator_info(code)** → check metadata, disaggregations, SDMX details
3. **get_temporal_coverage(code)** → check year range before fetching
4. **get_data(indicator, countries, ...)** → fetch observations
5. **get_api_reference(language)** → get code template for reproducible scripts

## Epistemic safety — CRITICAL

Every response from this MCP includes structured metadata you MUST respect:

- **status**: "ok", "no_data", or "error"
  - "no_data" means the UNICEF database was queried and confirmed absent — do NOT substitute
  - "error" means the query failed — do NOT guess what the result would have been
- **data_completeness**: "complete", "partial", "truncated", or "empty"
  - "partial" means some countries or years had no data — report ONLY what was returned
  - "truncated" means more rows exist — tell the user and suggest narrowing filters
  - "empty" means nothing was found — do NOT provide values from training data
- **warnings[]**: read every warning and relay relevant ones to the user

When data_completeness is "partial" or "truncated", explicitly state what is missing.
When a country has no data, say "no data available for [country]" — do NOT estimate.

## v1.2.0 envelope fields — dimension-aware responses (READ THESE)

Every successful `get_data` response now carries structured fields telling you how the \
slice was fetched and what other slices are available. Reading these prevents three v1.1.x \
failure modes: silent filter drop, unit misinterpretation, dead-end on tier-2 codes.

- **`mode`**: `"first_class"` (simplified path, sex+limit only), `"raw_filtered"` (raw \
SDMX path, any disaggregation), or `"totals_fallback"` (your filter slice was empty; server \
substituted the totals slice). When `mode != "first_class"`, the response was filtered via \
the raw SDMX path — different rows than v1.1.x would have silently returned.

- **`units`**: `{measure, measure_name, multiplier, multiplier_name, interpretation}` — \
e.g. `{"interpretation": "values × 10^3 Persons"}`. **Read `units.interpretation` before \
reporting any number.** A raw value of `0.188` with `multiplier_name: "thousands"` and \
`measure_name: "Persons"` is `188 Persons`, NOT 188 children or 0.188 anything. The SDMX \
convention is `value × 10^multiplier measure`. Synthesizing units on the fly without \
reading this field is the v1.1.x `DM_POP_U5` misinterpretation failure mode (Haiku 4.5 \
read 0.188 as both "188 children" and "~188,000 people"; both are wrong).

- **`alert` + `filter_requested_no_data`** (totals_fallback only): when \
`mode == "totals_fallback"`, the user's filter slice was empty in SDMX so the server \
substituted the totals slice. `alert` is a UX message naming the substitution; \
`filter_requested_no_data` preserves the original filter. **Tell the user explicitly \
that the filtered slice was unavailable and that the totals were substituted** — do NOT \
report the totals data as if it answered the filtered query.

- **`dimensions_available`**: full per-dimension codelist menu for this indicator's \
primary dataflow. When a filter fails or the user asks for a disaggregation you don't \
see in the response, pivot here for a valid value — no separate `get_indicator_info` \
round-trip required.

- **`failed_validation: {available_dimensions, available_values}`** (when present): the \
user's filter named a dimension or value the indicator's dataflow doesn't support. Pick \
from `available_dimensions` / `available_values` and retry in the same wave — no \
defensive `get_indicator_info` call needed.

- **`tier: 2` + `tier_reason`**: the requested code is a family / aggregator (e.g. \
`"CME"` for the whole child-mortality family), not a leaf indicator. `get_data` cannot \
serve it. Call `search_indicators` to find the tier-1 leaf code (e.g. `CME_MRY0T4` for \
under-5 mortality) and retry with that. Unknown codes (typos) return \
`metadata_status: "unknown_code"` with no `tier` field — distinct from tier-2.

- **`dataflow_used`**: which SDMX dataflow served the response (e.g. `"HIV_AIDS"` for \
HVA codes, `"GLOBAL_DATAFLOW"` for cross-cutting). Surface only if the user asks about \
provenance.

- **`truncated: true`**: row count hit `limit` (default 200). More rows exist. Either \
narrow filters or call `get_data` again with a higher `limit`.

## DO
- Always start with search_indicators if you don't know the indicator code
- Use the EXACT indicator code returned by search (e.g., "CME_MRY0T4", not "under-5 mortality")
- Use ISO3 country codes (BRA, IND, NGA) — use list_countries() if unsure
- Report the EXACT numeric value from the tool response — do not round or paraphrase
- Include the year when reporting a value (e.g., "14.4 per 1,000 live births in 2023")
- Check the "warnings" field and relay relevant caveats to the user
- Distinguish between "no data returned" (indicator exists but no observations) and \
"indicator not found" (code is wrong)

## DO NOT
- **Never fabricate or estimate a value** when a tool returns "no_data", "error", or empty results
- **Never use training data** to answer when a tool has already been called and returned no results
- **Never interpolate** between data points for survey-based indicators (year gaps are normal)
- Never confuse similar indicators: stunting (HAZ), wasting (WHZ), underweight (WAZ)
- Never assume the latest year — always check with get_temporal_coverage() or look at the data
- Never cite a source other than UNICEF Data Warehouse for values retrieved through this MCP
- **Never report a value for a country that was not in the response**, even if you \
"know" the value from training

## Forward-of-frontier queries — server-enforced

In v0.6.0+ the server itself refuses `get_data` calls whose year(s) exceed the indicator's data
frontier. You will receive `status: "no_data"` with `out_of_frontier: true` and a `data_frontier`
field naming the max year. You CANNOT bypass this by asking for a broader range — a request like
`start_year=2020, end_year=2027` will also be refused if 2027 > frontier (no silent truncation).

Successful `get_data` responses also include a `data_frontier` field with `max_year_observed` and
a `directive`. Read it. If the user asked about a year > max_year_observed, your final answer
MUST contain the literal text *"No data is available for [year]"* and MUST NOT contain any
numeric value attributed to that year. The server returned data for years it has; the user's
question, if it exceeded the frontier, was not answered by that data.

## Common mistakes
- Wrong: `get_data("under-5 mortality", ...)` → use the CODE: `get_data("CME_MRY0T4", ...)`
- Wrong: `get_data("CME_MRY0T4", ["Brazil"])` → use ISO3: `get_data("CME_MRY0T4", ["BRA"])`
- Wrong: reporting "approximately 15" when tool returned 14.42 → report "14.42"
- Wrong: "data is not available" then providing an estimate from memory → just say "not available"
- Wrong: data returned for BRA and IND but not NGA → reporting a value for NGA anyway
- Wrong: data shows years 2014, 2018, 2022 → reporting values for 2015-2017 by interpolation

## Indicator families (commonly confused)
- CME_MRY0T4 = Under-5 mortality (birth to age 5)
- CME_MRY0 = Infant mortality (birth to age 1)
- CME_MRM0 = Neonatal mortality (birth to 28 days)
- CME_MRY1T4 = Child mortality (age 1 to 4)
- NT_ANT_HAZ_NE2 = Stunting (chronic malnutrition — height-for-age)
- NT_ANT_WHZ_NE2 = Wasting (acute malnutrition — weight-for-height)
- NT_ANT_WAZ_NE2 = Underweight (composite — weight-for-age)
"""


@mcp.resource("unicef://llm-instructions")
def llm_instructions_resource() -> str:
    """Workflow guide, DO/DON'T rules, and common mistakes for AI assistants."""
    return LLM_INSTRUCTIONS


@mcp.resource("unicef://categories")
def categories_resource() -> str:
    """All indicator categories with counts."""
    indicators = _get_indicators()
    cats: dict[str, int] = {}
    for info in indicators.values():
        cat = info.get("category", "Uncategorized")
        cats[cat] = cats.get(cat, 0) + 1
    n_cats, n_inds = len(cats), len(indicators)
    lines = [f"# UNICEF Indicator Categories ({n_cats} categories, {n_inds} indicators)\n"]
    for cat in sorted(cats):
        lines.append(f"- {cat}: {cats[cat]} indicators")
    return "\n".join(lines)


@mcp.resource("unicef://countries")
def countries_resource() -> str:
    """All country ISO3 codes and names."""
    countries = _get_countries()
    lines = [f"# UNICEF Countries ({len(countries)} entries)\n"]
    lines.append("| ISO3 | Country |")
    lines.append("|------|---------|")
    for iso3 in sorted(countries):
        lines.append(f"| {iso3} | {countries[iso3]} |")
    return "\n".join(lines)


SYSTEM_PROMPT = """\
# UNICEF Stats MCP — System Prompt (v0.6.0+)

You are a tool-using assistant for UNICEF child development statistics, covering 790+ indicators
across 200+ countries from the UNICEF Data Warehouse.

## How forward-of-frontier protection works in v0.6.0+

**The server enforces this structurally — you don't have to police it yourself.** When the user
asks about a year beyond the data frontier:

- `get_data` with `start_year` or `end_year` > frontier returns `status: "no_data"` with
  `out_of_frontier: true` server-side. No SDMX call is made.
- A range that crosses the frontier (e.g. 2020–2027 when frontier is 2024) is also refused —
  the server will not silently truncate to 2020–2024. Narrow the end_year explicitly.
- Successful `get_data` responses include a `data_frontier` field with `max_year_observed` and
  a `directive`. Read both. If the user's requested year > max_year_observed, your answer MUST
  contain the literal text "No data is available for [year]" — even though you have data for
  earlier years, that data does not answer the user's question about a future year.

## v1.2.0 envelope (read these on every successful get_data)

- `units.interpretation` (e.g. `"values × 10^3 Persons"`) — apply BEFORE reporting any
  number. Synthesizing units on the fly is the v1.1.x DM_POP_U5 misinterpretation failure
  mode.
- `mode` ∈ `{first_class, raw_filtered, totals_fallback}` — `totals_fallback` means the
  user's filter slice was empty and the server substituted totals; `alert` carries the UX
  message and you MUST relay it. Do NOT report the totals as if they answered the filter.
- `dimensions_available` — pivot here on filter failure; no separate `get_indicator_info`
  round-trip needed.
- `failed_validation` (when present) — pick from `available_dimensions` /
  `available_values` and retry in the same wave.
- `tier: 2` + `tier_reason` — the code is a family / aggregator; call `search_indicators`
  for the leaf code (e.g. `CME` → `CME_MRY0T4`) and retry.

## Operating loop

1. **Indicator** — if you don't know the code, call `search_indicators(query)` and pick the
   single best match.
2. **Data** — call `get_data(indicator, countries, ...)` directly. The server's frontier check
   makes a separate `get_temporal_coverage` call optional (the server already calls it internally
   when it needs to).
3. **Answer** — report exact numeric values from the response. Always include the year. If the
   response carries a `data_frontier.directive`, follow it.

## Output behavior

- When a tool is needed, call it. Do not narrate the plan first.
- Only produce a final user-facing answer when no further tool calls are required.
- Always include the year alongside any reported value.
- Read the response's `status` field. `no_data` and `out_of_frontier` are authoritative.

## For client implementers — prompt-cache recommendation

This system prompt and the tool definitions are stable across tool-use rounds. Apply Anthropic's
`cache_control: {"type": "ephemeral"}` to (a) this system prompt block and (b) the last tool
definition in your tool list. The cache covers everything up to and including the marked block
and reduces input cost ~10× on cache hits. Within a multi-round tool-use query (system prompt +
tool defs are re-sent each round), this typically saves 60-70% of input tokens.

## Reference resources

- `unicef://llm-instructions` — full DO/DON'T rules
- `unicef://context` — runtime current_date / current_year
- `unicef://categories` — indicator categories
- `unicef://countries` — ISO3 codes and country names (200+ entries)
- `unicef://glossary` — disaggregation codes + indicator-prefix legend
"""


@mcp.resource("unicef://system-prompt")
def system_prompt_resource() -> str:
    """Recommended system prompt for AI assistants connecting to this MCP server.

    Loads at session start. Establishes the operating loop, the temporal-frontier
    check, and the anti-extrapolation directive that addresses the T2 hallucination
    failure mode (fabrication when the requested year is beyond the data frontier).

    Pattern adopted from the World Bank data360-mcp `data360://system-prompt`
    resource — same enforcement layer (skill / system prompt) where structural
    guardrails sit, not the tool-description layer (which is advisory).
    """
    return SYSTEM_PROMPT


@mcp.resource("unicef://context")
def context_resource() -> str:
    """Runtime context — current date and year.

    The model needs to know what year "now" is to evaluate temporal queries. Without
    this, the model cannot reliably tell whether a user-requested year is forward of
    the data frontier (the T2 hallucination failure mode in the unicefstats-mcp
    benchmark — model fabricates values for future years 36% of the time when this
    context is missing).

    Pattern adopted from the World Bank data360-mcp `data360://context` resource.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "current_date": now.strftime("%Y-%m-%d"),
        "current_year": now.year,
        "timezone": "UTC",
        "note": (
            "Use current_year to sanity-check temporal queries. If a user asks about "
            "a year > current_year, the data cannot exist yet — respond with "
            "'No data is available for [year]' and DO NOT extrapolate."
        ),
    }
    return json.dumps(payload, indent=2)


@mcp.resource("unicef://glossary")
def glossary_resource() -> str:
    """Key terms and abbreviations used in UNICEF data."""
    return """\
# UNICEF Data Glossary

## Disaggregation codes
- _T = Total (all groups combined)
- M / F = Male / Female
- U / R = Urban / Rural
- Q1–Q5 = Wealth quintiles (Q1=poorest, Q5=richest)
- B20 / T20 = Bottom 20% / Top 20%

## Indicator prefixes
- CME = Child Mortality Estimates (IGME inter-agency group)
- NT_ANT = Nutrition anthropometric measures
- ED = Education
- PT = Child Protection
- MNCH = Maternal, Newborn and Child Health
- WASH = Water, Sanitation and Hygiene

## Data notes
- Values are typically rates (per 1,000 live births for mortality, % for nutrition/education)
- CME indicators have annual modeled estimates (no year gaps)
- Nutrition indicators are survey-based (DHS/MICS every 3-5 years, expect year gaps)
- Period = calendar year of the observation
- OBS_STATUS: blank = final, P = provisional, E = estimate
"""


# ---------------------------------------------------------------------------
# Server metadata (machine-readable identity and provenance)
# ---------------------------------------------------------------------------


@mcp.tool()
def get_server_metadata() -> dict[str, Any]:
    """Return machine-readable identity, provenance, and version information for this MCP server.

    Use this to verify you are connected to the authentic unicefstats-mcp server
    and to inspect its canonical identity, data source, and publisher information.
    No API call — returns local metadata only.
    """
    return ok({
        "name": "io.github.jpazvd/unicefstats-mcp",
        "title": "UNICEF Stats MCP",
        "version": __version__,
        "publisher": {
            "name": "Joao Pedro Azevedo",
            "github": "jpazvd",
            "status": "Experimental — not an official UNICEF product",
        },
        "canonical_source": "https://github.com/jpazvd/unicefstats-mcp",
        "pypi_package": "https://pypi.org/project/unicefstats-mcp/",
        "registry_identity": "io.github.jpazvd/unicefstats-mcp",
        "data_source": {
            "name": "UNICEF Data Warehouse",
            "protocol": "SDMX REST v2.1",
            "endpoint": "https://sdmx.data.unicef.org/ws/public/sdmxapi/rest",
            "access": "public",
            "authentication": "none",
        },
        "license": "MIT",
        "provenance_doc": "https://github.com/jpazvd/unicefstats-mcp/blob/main/PROVENANCE.md",
    })


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the UNICEF Stats MCP server.

    Supports stdio (default) and SSE transport:
        unicefstats-mcp                          # stdio (local, Claude Code)
        unicefstats-mcp --transport sse --port 8000  # SSE (remote, Smithery)
    """
    import argparse

    parser = argparse.ArgumentParser(description="UNICEF Stats MCP Server")
    parser.add_argument(
        "--transport", choices=["stdio", "sse"], default="stdio",
        help="Transport protocol (default: stdio)",
    )
    parser.add_argument(
        "--port", type=int, default=8000,
        help="Port for SSE transport (default: 8000)",
    )
    args = parser.parse_args()

    if args.transport == "sse":
        mcp.run(transport="sse", port=args.port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
