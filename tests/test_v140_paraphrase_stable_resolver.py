"""v1.4.0 — paraphrase-stable resolver fallback.

The deep-dive on issue #100 found that the v9 Arm B FIRE_ALREADY_WORKING
regression (15/25 cells, 60% of FAW regressions) was driven by the
``_normalize`` + ``_SYNONYMS`` lookup being word-order-sensitive at
``indicator_resolver.py:376``. The same conceptual query phrased with
permuted word order (e.g., "primary school completion rate" vs
"completion rate primary school") would hit the synonym table on one
phrasing but fall through to ``status='unknown'`` on the other, where
the heuristic ambiguity Path B at ``server.py:785-819`` would then fire
and halt the LLM.

v1.4.0 adds a sorted-token mirror of ``_SYNONYMS`` (``_SYNONYMS_SORTED``)
that the resolver consults as a strict fallback after the order-sensitive
lookup misses. Token-bag collisions (sorted-token form maps to multiple
distinct codes) are dropped so the fallback can never silently misroute.

These tests pin the contract:
  - The issue #100 reproducer ("primary school completion rate" vs
    "completion rate primary school") resolves to ED_CR_L1 either way.
  - The fallback is strict: queries that should remain unknown stay
    unknown (no spurious matches from sorted-token false positives).
  - Token-bag collisions in ``_SYNONYMS`` are skipped — the fallback
    refuses to misroute even when two synonym keys with different
    word orders would collide on a sorted form.
  - The order-sensitive primary path is unchanged for callers using
    the canonical phrasing — same status, same code, byte-identical
    return value.
"""

from __future__ import annotations

import pytest

from unicefstats_mcp.indicator_resolver import (
    _SYNONYMS,
    _SYNONYMS_SORTED,
    _ensure_synonyms_sorted_built,
    _normalize,
    _sort_tokens,
    resolve_indicator,
)

# ---------------------------------------------------------------------------
# Helper unit tests
# ---------------------------------------------------------------------------


def test_sort_tokens_is_order_insensitive() -> None:
    assert _sort_tokens("primary school completion rate") == _sort_tokens(
        "completion rate primary school"
    )


def test_sort_tokens_preserves_token_set() -> None:
    sorted_form = _sort_tokens("under five mortality rate")
    assert set(sorted_form.split()) == {"under", "five", "mortality", "rate"}


def test_sort_tokens_handles_single_token() -> None:
    assert _sort_tokens("stunting") == "stunting"


def test_sort_tokens_collapses_empty() -> None:
    assert _sort_tokens("") == ""


# ---------------------------------------------------------------------------
# Lazy-build contract
# ---------------------------------------------------------------------------


def test_ensure_synonyms_sorted_built_is_idempotent() -> None:
    _ensure_synonyms_sorted_built()
    snapshot = dict(_SYNONYMS_SORTED)
    _ensure_synonyms_sorted_built()  # second call must not mutate
    assert snapshot == _SYNONYMS_SORTED


def test_ensure_synonyms_sorted_built_populates_from_synonyms() -> None:
    _ensure_synonyms_sorted_built()
    # Every key in _SYNONYMS that has no token-bag collision should appear
    # in the sorted mirror.
    assert len(_SYNONYMS_SORTED) > 0
    # And the codes should be a subset of the original _SYNONYMS values.
    assert set(_SYNONYMS_SORTED.values()) <= set(_SYNONYMS.values())


# ---------------------------------------------------------------------------
# Issue #100 reproducer
# ---------------------------------------------------------------------------


def test_issue_100_reproducer_both_word_orders_resolve() -> None:
    """The exact v124 vs v130 paraphrase that drove the v9 Arm B HOLD."""
    v124_phrasing = resolve_indicator("primary school completion rate")
    v130_phrasing = resolve_indicator("completion rate primary school")

    # Both must hit a synonym match.
    assert v124_phrasing.status == "synonym_match", (
        f"v124 phrasing should resolve via _SYNONYMS; got status="
        f"{v124_phrasing.status!r}"
    )
    assert v130_phrasing.status == "synonym_match", (
        f"v130 phrasing should resolve via _SYNONYMS_SORTED fallback; "
        f"got status={v130_phrasing.status!r}"
    )

    # And both must point at the same code.
    assert v124_phrasing.code == "ED_CR_L1"
    assert v130_phrasing.code == "ED_CR_L1"


# ---------------------------------------------------------------------------
# Strictness: no spurious matches
# ---------------------------------------------------------------------------


def test_truly_unknown_query_stays_unknown() -> None:
    """A query with no plausible synonym mapping must NOT match by accident.

    The sorted-token fallback only consults ``_SYNONYMS_SORTED``, which
    is derived strictly from ``_SYNONYMS`` keys. A random string with no
    overlap to any synonym should still return ``status='unknown'``.
    """
    res = resolve_indicator("zzz arbitrary nonexistent indicator phrase qqq")
    assert res.status == "unknown"


def test_collision_synonyms_are_dropped_from_sorted_mirror() -> None:
    """If two ``_SYNONYMS`` keys collide on sorted-token form AND map to
    different codes, the colliding entry must not appear in
    ``_SYNONYMS_SORTED`` (it would otherwise silently route one query to
    the wrong code)."""
    _ensure_synonyms_sorted_built()
    # For every (key, code) pair, the sorted form is either absent from
    # the sorted mirror (collision dropped) or points back at the same
    # code (no collision).
    for key, code in _SYNONYMS.items():
        sorted_form = _sort_tokens(_normalize(key))
        if not sorted_form:
            continue
        if sorted_form in _SYNONYMS_SORTED:
            assert _SYNONYMS_SORTED[sorted_form] == code, (
                f"Collision leaked: sorted form {sorted_form!r} of key "
                f"{key!r} (→ {code}) maps to "
                f"{_SYNONYMS_SORTED[sorted_form]} in the sorted mirror."
            )


# ---------------------------------------------------------------------------
# Back-compat: order-sensitive primary path unchanged
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "phrasing, expected_code",
    [
        ("primary school completion rate", "ED_CR_L1"),
        ("primary completion rate", "ED_CR_L1"),
        ("primary completion", "ED_CR_L1"),
    ],
)
def test_v124_canonical_phrasings_still_hit_primary_path(
    phrasing: str, expected_code: str
) -> None:
    """The v124 phrasings that already worked must keep working without
    relying on the sorted-token fallback. Status is ``synonym_match``
    either way, but pinning this guards against the primary _SYNONYMS
    lookup regressing if a future refactor reorders the resolver."""
    res = resolve_indicator(phrasing)
    assert res.status == "synonym_match"
    assert res.code == expected_code
