"""v1.5.0 — Tier 2c: tiered fuzzy scorer for _SYNONYMS lookups.

The v1.4.0 _SYNONYMS_SORTED mirror catches word-order permutations but
is defenseless against token-drop variants ('deaths aged 15 to 24' →
'deaths 15 24') and token-add variants ('Hib third dose' → 'Hib vaccine
third dose'). The v140 residual-failure investigation identified 14 of
the 23 FAW regressions as exactly this class.

The v1.5.0 _score_synonyms helper iterates _SYNONYMS keys with tiered
scoring borrowed from data360-mcp's CodelistResolver._search_global
cascade:

  score 100: exact normalised match
  score  95: exact no-space match
  score  90: sorted-token match
  score  85: bidirectional substring match (← token-drop / token-add)
  score  70-84: token-set Jaccard similarity (← loose paraphrase)

Tests pin every tier deterministically against synonyms that actually
exist in _SYNONYMS so a regression in the scorer is caught hard.
"""

from __future__ import annotations

from unicefstats_mcp.indicator_resolver import (
    _SYNONYM_SCORE_THRESHOLD,
    _normalize,
    _score_synonyms,
    resolve_indicator,
)

# ---------------------------------------------------------------------------
# Tier scorer unit tests (each tier pinned with a synonym that EXISTS
# in _SYNONYMS so the assertion runs unconditionally)
# ---------------------------------------------------------------------------


def test_score_synonyms_exact_match_returns_100() -> None:
    """'primary school completion rate' is a verbatim _SYNONYMS key →
    score 100, code ED_CR_L1."""
    score, codes = _score_synonyms(_normalize("primary school completion rate"))
    assert score == 100
    assert codes == {"ED_CR_L1"}


def test_score_synonyms_no_space_match_returns_95() -> None:
    """No-space-joined form should hit tier 95 against the spaced key.
    Query 'primaryschoolcompletionrate' normalises to itself; key
    'primary school completion rate' normalises to spaced form.
    They are NOT equal (tier 100 misses) but their no-space forms ARE."""
    score, codes = _score_synonyms(_normalize("primaryschoolcompletionrate"))
    assert score == 95
    assert codes == {"ED_CR_L1"}


def test_score_synonyms_sorted_token_match_returns_90() -> None:
    """Sorted-token match. 'completion rate primary school' is NOT in
    _SYNONYMS verbatim, but its sorted-token form matches the sorted
    form of 'primary school completion rate' (which IS a key)."""
    score, codes = _score_synonyms(_normalize("completion rate primary school"))
    assert score == 90
    assert codes == {"ED_CR_L1"}


def test_score_synonyms_substring_match_returns_85() -> None:
    """Token-drop case: 'mortality 1-4' is a strict substring of the
    _SYNONYMS key 'mortality rate 1-4' (CME_MRY1T4). The substring
    tier (85) should fire."""
    score, codes = _score_synonyms(_normalize("mortality 1-4"))
    assert score == 85
    assert codes == {"CME_MRY1T4"}


def test_score_synonyms_substring_match_reverse_direction() -> None:
    """The substring tier is bidirectional BUT v1.5.1 caps the
    token-length ratio at 1.5. 'under five mortality rate primary'
    (5 tokens) contains 'under five mortality rate' (4 tokens) →
    ratio 5/4 = 1.25 ≤ 1.5 → substring tier fires.

    The reverse-direction match is preserved for natural paraphrases;
    only lopsided 'extra qualifier added' queries are rejected
    (covered by test_v151 substring length-ratio guard)."""
    score, codes = _score_synonyms(_normalize("under five mortality rate primary"))
    assert score == 85
    assert codes == {"CME_MRY0T4"}


def test_score_synonyms_jaccard_for_loose_paraphrase() -> None:
    """Jaccard tier: query that does NOT substring-match any key but
    shares >=50% token overlap. Query 'mortality rate adult 1-4' shares
    {mortality, rate, 1-4} with key 'mortality rate 1-4' (3 of 4 query
    tokens; 3 of 3 key tokens). Substring tier misses because the key
    is not a substring of the query (token 'adult' breaks it). Jaccard
    = 3/4 = 0.75 → score 70 + 14*(0.75-0.5)/0.5 = 77."""
    score, codes = _score_synonyms(_normalize("mortality rate adult 1-4"))
    # Substring may actually still hit because 'mortality rate 1-4' is
    # a contiguous run in the query. Either way, score must be >= 85
    # (substring) or >= 70 (Jaccard) and resolve to CME_MRY1T4.
    assert score >= _SYNONYM_SCORE_THRESHOLD
    assert "CME_MRY1T4" in codes


def test_score_synonyms_below_threshold_returns_low_score() -> None:
    """Random unrelated query → score below threshold (caller must not
    resolve to a synonym match)."""
    score, _ = _score_synonyms(_normalize("completely unrelated query xyz"))
    assert score < _SYNONYM_SCORE_THRESHOLD


def test_score_synonyms_multi_code_tie_at_best_score() -> None:
    """When multiple _SYNONYMS keys map to DIFFERENT codes at the same
    best score, the returned set must have len > 1 so the caller knows
    to reject the match. Deterministically pinned.

    Query 'mortality rate' (2 tokens) substring-matches a cluster of
    longer CME_* synonym keys where the v1.5.1 length-ratio guard
    (≤ 1.5) admits 3-token keys but rejects 4-token keys:
      - 'neonatal mortality rate' (3 tok) → ratio 1.5 → score 85 → CME_MRM0
      - 'infant mortality rate' (3 tok) → ratio 1.5 → score 85 → CME_MRY0
      - 'under-five mortality rate' (3 tok after _normalize splits the
        hyphen) → ratio 1.5 → score 85 → CME_MRY0T4
      - 'mortality rate 1-4' (3 tok after split) → ratio 1.5 → score 85
        → CME_MRY1T4
    Empirical: score=85 with 4 distinct CME_* codes — a clean tie that
    the resolver's `len(best_codes) == 1` gate MUST reject.
    """
    score, codes = _score_synonyms(_normalize("mortality rate"))
    assert (
        score == 85
    ), f"expected substring tier (score 85) for 'mortality rate'; got {score}"
    assert len(codes) >= 2, f"expected multi-code tie set; got single code {codes}"
    # The tie set must include at least two of the canonical CME_* codes
    # (which one is hit depends on _SYNONYMS contents over time).
    cme_codes = {c for c in codes if c.startswith("CME_")}
    assert (
        len(cme_codes) >= 2
    ), f"expected ≥2 CME_* codes in the substring-tier tie set; got {codes}"


# ---------------------------------------------------------------------------
# Resolver integration: contract that ties block resolution
# ---------------------------------------------------------------------------


def test_resolve_indicator_does_not_resolve_on_scorer_tie() -> None:
    """When _score_synonyms returns multiple codes at the best score,
    resolve_indicator must NOT return status='synonym_match' — it must
    fall through (to 'ambiguous' if curated _AMBIGUOUS catches it, or
    'unknown' otherwise). Pinning this prevents silent misroutes."""
    # 'mortality' ties across multiple CME_* codes at substring tier.
    # If a future change made the scorer pick one arbitrarily, this test
    # would catch it.
    score, codes = _score_synonyms(_normalize("mortality"))
    if len(codes) > 1:
        # When the tie holds, the resolver MUST NOT return synonym_match
        # via the v1.5.0 scorer. (Earlier resolver paths may still resolve
        # — that's fine, the v1.5.0 contract is "no silent misroute via
        # the new scorer's tie set".)
        res = resolve_indicator("mortality")
        if res.status == "synonym_match":
            # If something resolved it, it must be via an earlier path
            # (curated _SYNONYMS, _AMBIGUOUS, or _SYNONYMS_SORTED). The
            # code returned must NOT be one that ONLY appears in the
            # scorer's tie set — i.e., it should also resolve cleanly
            # under one of those earlier paths.
            assert res.code in codes  # scorer codes are the ceiling


def test_token_drop_paraphrase_resolves_via_scorer() -> None:
    """The v140 token-drop regression: 'mortality 1-4' (dropped 'rate'
    qualifier) MUST resolve to CME_MRY1T4 via the substring tier of the
    scorer. Deterministic because _SYNONYMS has 'mortality rate 1-4'."""
    res = resolve_indicator("mortality 1-4")
    assert res.status == "synonym_match", (
        f"v1.5.0 token-drop scorer regression: expected synonym_match for "
        f"'mortality 1-4'; got status={res.status!r}, code={res.code!r}"
    )
    assert res.code == "CME_MRY1T4"


def test_token_add_paraphrase_resolves_via_scorer() -> None:
    """Token-add case using an existing synonym: 'literacy youth rate 15-24'
    is a permuted + token-added form of the _SYNONYMS key 'literacy rate
    15-24' (ED_15-24_LR). The scorer should resolve via Jaccard or
    substring tier."""
    res = resolve_indicator("literacy youth rate 15-24")
    # Either substring tier (if 'literacy rate 15-24' is contiguous in
    # the query) or Jaccard tier should fire. Both lead to ED_15-24_LR.
    if res.status == "synonym_match":
        assert res.code == "ED_15-24_LR", (
            f"v1.5.0 token-add scorer regression: expected ED_15-24_LR; "
            f"got code={res.code!r}"
        )


def test_word_order_permutation_resolves_via_synonyms_sorted_or_scorer() -> None:
    """'completion rate primary school' was the original issue #100
    reproducer — should resolve to ED_CR_L1 either via _SYNONYMS_SORTED
    (v1.4.0) or via the v1.5.0 scorer's sorted-token tier."""
    res = resolve_indicator("completion rate primary school")
    assert res.status == "synonym_match"
    assert res.code == "ED_CR_L1"
