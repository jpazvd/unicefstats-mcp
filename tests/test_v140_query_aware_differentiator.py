"""v1.4.0 — query-aware differentiator hints.

``explain_difference`` now accepts an optional ``query`` parameter. When
supplied, the function scans the lowercased query for known tier keywords
(``primary``, ``lower secondary``, ``rural``, ``modelled``, etc.) and
appends a " — best match for 'X' in query" hint when the candidate's
suffix tokens intersect with the keyword's mapped suffix.

The intent: on L1/L2/L3-style sibling clusters where the query already
specifies the tier, the LLM has enough information to resume on the
semantically-closest candidate instead of abstaining.

Tests pin the contract:
  - When the query contains a tier keyword AND the candidate's suffix
    matches, the differentiator carries the " — best match for 'X'" tail.
  - When the query is absent / empty / non-string, the differentiator
    behaves exactly as it did in v1.3.x (back-compat).
  - When the query contains a tier keyword that does NOT match the
    candidate's suffix, no hint is appended (no spurious promotion).
  - Multi-word keywords ("lower secondary") win over their substring
    ("secondary") so an ED_CR_L2 candidate against a "lower secondary"
    query gets the correct hint.
"""

from __future__ import annotations

from unicefstats_mcp.differentiator import explain_difference

# ---------------------------------------------------------------------------
# Back-compat: query=None preserves v1.3.x behaviour
# ---------------------------------------------------------------------------


def test_explain_difference_no_query_unchanged() -> None:
    """The two-arg call from v1.3.x must keep returning identical strings."""
    diff = explain_difference("ED_CR_L1", ["ED_CR_L1", "ED_CR_L2", "ED_CR_L3"])
    assert diff == "L1: ISCED level 1 (primary)"


def test_explain_difference_empty_query_unchanged() -> None:
    diff = explain_difference(
        "ED_CR_L1", ["ED_CR_L1", "ED_CR_L2", "ED_CR_L3"], query=""
    )
    assert diff == "L1: ISCED level 1 (primary)"


def test_explain_difference_non_string_query_unchanged() -> None:
    diff = explain_difference(
        "ED_CR_L1", ["ED_CR_L1", "ED_CR_L2", "ED_CR_L3"], query=None
    )
    assert diff == "L1: ISCED level 1 (primary)"


# ---------------------------------------------------------------------------
# Query-aware hint fires on matching tier keywords
# ---------------------------------------------------------------------------


def test_primary_query_promotes_l1_candidate() -> None:
    diff = explain_difference(
        "ED_CR_L1",
        ["ED_CR_L1", "ED_CR_L2", "ED_CR_L3"],
        query="completion rate primary school",
    )
    assert "L1: ISCED level 1" in diff
    assert "best match for 'primary' in query" in diff


def test_lower_secondary_promotes_l2_over_l3() -> None:
    """The multi-word keyword 'lower secondary' must win over the
    substring 'secondary' (which maps to L3). Otherwise an L2 query
    would be misrouted to an L3 candidate."""
    diff_l2 = explain_difference(
        "ED_CR_L2",
        ["ED_CR_L1", "ED_CR_L2", "ED_CR_L3"],
        query="completion rate lower secondary",
    )
    diff_l3 = explain_difference(
        "ED_CR_L3",
        ["ED_CR_L1", "ED_CR_L2", "ED_CR_L3"],
        query="completion rate lower secondary",
    )
    assert "best match for 'lower secondary' in query" in diff_l2
    # L3 candidate must NOT get a promotion hint because "lower secondary"
    # outranks the plain "secondary" keyword and points at L2.
    assert "best match for" not in diff_l3


def test_modelled_query_promotes_mod_candidate() -> None:
    diff = explain_difference(
        "NT_ANT_HAZ_NE2_MOD",
        ["NT_ANT_HAZ_NE2", "NT_ANT_HAZ_NE2_MOD"],
        query="modelled stunting prevalence",
    )
    assert "best match for 'modelled' in query" in diff


# ---------------------------------------------------------------------------
# No spurious promotion when query keyword doesn't match candidate suffix
# ---------------------------------------------------------------------------


def test_primary_query_does_not_promote_l2() -> None:
    diff = explain_difference(
        "ED_CR_L2",
        ["ED_CR_L1", "ED_CR_L2", "ED_CR_L3"],
        query="completion rate primary school",
    )
    assert "L2: ISCED level 2" in diff
    # L2 must NOT get a "primary" hint — the keyword maps to L1.
    assert "best match for" not in diff


def test_query_without_tier_keyword_no_hint() -> None:
    """A query that contains no tier keyword should not append any hint."""
    diff = explain_difference(
        "ED_CR_L1",
        ["ED_CR_L1", "ED_CR_L2", "ED_CR_L3"],
        query="school stats",
    )
    assert "best match for" not in diff


def test_query_with_unrelated_tier_keyword_no_hint() -> None:
    """A query mentioning 'urban' should not promote an education
    candidate where the suffix has no R/U token."""
    diff = explain_difference(
        "ED_CR_L1",
        ["ED_CR_L1", "ED_CR_L2", "ED_CR_L3"],
        query="completion rate urban areas",
    )
    # ED_CR_L1's suffix is "L1", no R/U token — no hint should fire.
    assert "best match for" not in diff


# ---------------------------------------------------------------------------
# Word-boundary matching (regression: 'male' must NOT match 'female';
# 'urban' must NOT match 'suburban')
# ---------------------------------------------------------------------------


def test_suburban_query_does_not_promote_urban_candidate() -> None:
    """The keyword 'urban' must use word-boundary matching so a query
    mentioning 'suburban' does not accidentally fire the 'urban' hint."""
    diff = explain_difference(
        "WS_PPL_U",
        ["WS_PPL_U", "WS_PPL_R"],
        query="suburban water access trends",
    )
    # 'urban' should not match inside 'suburban' — no hint should fire.
    assert "best match for 'urban'" not in diff


def test_female_query_does_not_promote_male_candidate() -> None:
    """The keyword 'male' must use word-boundary matching so a 'female'
    query does not accidentally promote the 'M'-suffix (male) candidate."""
    diff = explain_difference(
        "MNCH_X_M",
        ["MNCH_X_M", "MNCH_X_F"],
        query="female adolescent pregnancy",
    )
    assert "best match for 'male'" not in diff


def test_female_query_promotes_f_candidate() -> None:
    """The complementary positive case — a 'female' query DOES promote
    the F-suffix candidate via the 'female' keyword."""
    diff = explain_difference(
        "MNCH_X_F",
        ["MNCH_X_M", "MNCH_X_F"],
        query="female adolescent pregnancy",
    )
    assert "best match for 'female' in query" in diff
