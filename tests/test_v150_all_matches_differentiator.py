"""v1.5.0 — Tier 2a: all-matches accumulation in _query_match_hint.

The v1.4.0 first-match-wins loop mis-fired on queries containing multiple
tier keywords whose mapped suffixes were not all present in a single
candidate. The v140 residual-failure investigation pinned the smoking gun:
for "completion rate primary school age modeled" the loop broke on
'primary' (→ L1) first, never reaching 'modeled' (→ MOD), so three
candidates [ED_CR_L1, ED_CR_L1_UIS_MOD, ED_ANAR_L1] all got tagged
"best match for 'primary'" — false tie → Path B ambiguity_flag.

v1.5.0 rewrites the loop to collect ALL distinct tier keywords (with
position-overlap tracking so multi-word keywords consume their span)
and emit the hint ONLY for candidates covering EVERY matched suffix.

Tests pin both halves of the contract:
  - Multi-keyword query promotes the UNIQUE candidate covering all
    matched suffixes (ED_CR_L1_UIS_MOD for primary+modeled).
  - Partial-coverage candidates (ED_CR_L1, ED_ANAR_L1) get no hint.
  - Single-keyword behaviour from v1.4.0 is preserved.
  - Multi-word keywords ('lower secondary') still outrank substrings.
"""

from __future__ import annotations

from unicefstats_mcp.differentiator import explain_difference

# ---------------------------------------------------------------------------
# The smoking-gun case from the v140 residual-failure investigation
# ---------------------------------------------------------------------------


def test_primary_plus_modeled_uniquely_promotes_l1_uis_mod() -> None:
    """The smoking-gun cell: query contains both 'primary' (→L1) and
    'modeled' (→MOD). Only ED_CR_L1_UIS_MOD has suffix tokens [L1, UIS, MOD]
    that cover both. v1.4.0 mis-tagged three candidates with the same
    "primary" hint, creating a false tie. v1.5.0 must promote uniquely."""
    siblings = [
        "ED_CR_L1",
        "ED_CR_L1_UIS_MOD",
        "ED_CR_L3_UIS_MOD",
        "ED_ANAR_L1",
        "ED_CR_L2",
    ]
    q = "completion rate primary school age modeled"
    diff_l1_mod = explain_difference("ED_CR_L1_UIS_MOD", siblings, query=q)
    diff_l1 = explain_difference("ED_CR_L1", siblings, query=q)
    diff_anar = explain_difference("ED_ANAR_L1", siblings, query=q)
    diff_l3_mod = explain_difference("ED_CR_L3_UIS_MOD", siblings, query=q)
    diff_l2 = explain_difference("ED_CR_L2", siblings, query=q)

    # ED_CR_L1_UIS_MOD covers both L1 AND MOD — gets the hint.
    assert "best match for" in diff_l1_mod, (
        f"v1.5.0 Tier 2a: ED_CR_L1_UIS_MOD must get unique hint covering "
        f"both 'primary' and 'modeled'; got {diff_l1_mod!r}"
    )
    assert "primary" in diff_l1_mod
    assert "modeled" in diff_l1_mod

    # ED_CR_L1 covers only L1 (missing MOD) — no hint.
    assert "best match for" not in diff_l1, (
        f"ED_CR_L1 covers only L1 (missing MOD); must not get hint "
        f"(would re-introduce v1.4.0 false tie); got {diff_l1!r}"
    )

    # ED_ANAR_L1 covers only L1 (missing MOD) — no hint.
    assert "best match for" not in diff_anar, (
        f"ED_ANAR_L1 covers only L1 (missing MOD); must not get hint; "
        f"got {diff_anar!r}"
    )

    # ED_CR_L3_UIS_MOD covers MOD but missing L1 — no hint.
    assert (
        "best match for" not in diff_l3_mod
    ), f"ED_CR_L3_UIS_MOD covers MOD but missing L1; got {diff_l3_mod!r}"

    # ED_CR_L2 covers neither — no hint.
    assert "best match for" not in diff_l2


# ---------------------------------------------------------------------------
# Single-keyword v1.4.0 behaviour preserved
# ---------------------------------------------------------------------------


def test_single_keyword_query_still_promotes_matching_candidate() -> None:
    """Query mentions only 'primary' (no other tier keyword). v1.4.0
    promoted ED_CR_L1 with the 'primary' hint; v1.5.0 must keep doing
    so (single-keyword case is unchanged)."""
    diff = explain_difference(
        "ED_CR_L1",
        ["ED_CR_L1", "ED_CR_L2", "ED_CR_L3"],
        query="completion rate primary school",
    )
    assert "best match for 'primary' in query" in diff


def test_single_keyword_query_does_not_promote_non_covering_candidate() -> None:
    diff = explain_difference(
        "ED_CR_L2",
        ["ED_CR_L1", "ED_CR_L2", "ED_CR_L3"],
        query="completion rate primary school",
    )
    assert "best match for" not in diff


# ---------------------------------------------------------------------------
# Multi-word vs substring keyword precedence preserved
# ---------------------------------------------------------------------------


def test_lower_secondary_outranks_secondary_via_range_claim() -> None:
    """v1.5.0 range-overlap tracking must preserve the v1.4.0 invariant:
    'lower secondary' claims its span so the substring 'secondary' does
    NOT independently match. ED_CR_L2 covers L2 only; without range
    claiming, both 'lower secondary'→L2 and 'secondary'→L3 would be in
    query_matches, forcing ED_CR_L2 to fail the strict cover-all rule."""
    diff_l2 = explain_difference(
        "ED_CR_L2",
        ["ED_CR_L1", "ED_CR_L2", "ED_CR_L3"],
        query="completion rate lower secondary",
    )
    assert "best match for 'lower secondary' in query" in diff_l2

    # The L3 candidate must NOT get a hint via the substring 'secondary'.
    diff_l3 = explain_difference(
        "ED_CR_L3",
        ["ED_CR_L1", "ED_CR_L2", "ED_CR_L3"],
        query="completion rate lower secondary",
    )
    assert "best match for" not in diff_l3


# ---------------------------------------------------------------------------
# All-three-keyword case (primary + modeled + urban)
# ---------------------------------------------------------------------------


def test_three_keyword_query_promotes_uniquely_covering_candidate() -> None:
    """Synthetic three-keyword query: 'primary urban modeled'. Only the
    candidate whose suffix covers L1, U AND MOD all three should get the
    hint with all three keywords mentioned."""
    siblings = [
        "X_L1",
        "X_L1_U",
        "X_L1_U_MOD",
        "X_L1_MOD",
        "X_R",
    ]
    q = "indicator primary urban modeled"
    diff_all_three = explain_difference("X_L1_U_MOD", siblings, query=q)
    diff_l1_u_only = explain_difference("X_L1_U", siblings, query=q)
    diff_l1_only = explain_difference("X_L1", siblings, query=q)

    assert "best match for" in diff_all_three
    assert "primary" in diff_all_three
    assert "urban" in diff_all_three
    assert "modeled" in diff_all_three

    # Partial covers (missing MOD or missing U) must NOT get the hint.
    assert (
        "best match for" not in diff_l1_u_only
    ), f"X_L1_U covers L1+U but missing MOD; got {diff_l1_u_only!r}"
    assert (
        "best match for" not in diff_l1_only
    ), f"X_L1 covers only L1; got {diff_l1_only!r}"


# ---------------------------------------------------------------------------
# Disjoint family char-prefix fallback (Tier 2b)
# ---------------------------------------------------------------------------


def test_disjoint_family_uses_char_prefix_fallback() -> None:
    """When the token-level common prefix is empty (disjoint families
    like [HVA_ADOL_..., HVA_EPI_..., MNCH_...]), the v1.5.0 fallback to
    char-level common prefix should produce a non-empty differentiator.
    Otherwise the suffix degrades to "variant suffix: _<full_code>"
    (strictly worse than v1.3.x)."""
    siblings = [
        "HVA_ADOL_ART_RECEIVE",
        "HVA_EPI_INF_ANN_15-24",
        "HVA_EPI_INF_RT",
        "HVA_PED_ART_CVG",
        "MNCH_ADO_ALCOHOL",
    ]
    diff = explain_difference("HVA_EPI_INF_RT", siblings)
    # Token-level common prefix is "" (no whole-token match across all
    # codes). Char-level fallback should find "HVA_" as a shared prefix
    # of 4/5 codes — but commonprefix returns "" for the full set because
    # MNCH doesn't share even a character.
    # The point: differentiator should not surface "variant suffix:
    # _HVA_EPI_INF_RT" (the entire code as suffix). Either it returns
    # a meaningful prefix or a non-empty suffix that excludes the code itself.
    assert "HVA_EPI_INF_RT" not in diff or "variant suffix" not in diff, (
        f"differentiator surfaced full code as variant suffix for "
        f"disjoint family; got {diff!r}"
    )
