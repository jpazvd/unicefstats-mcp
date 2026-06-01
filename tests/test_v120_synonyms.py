"""v1.2.0 Commit 4 — multi-word synonyms + methodology phrases.

Pins the gate-4 functional invariants and the negative-side smoke:

  - U5MR / under-five mortality / under 5 mortality / under-5 mortality
    all surface CME_MRY0T4 as recommended.
  - IMR / NMR resolve via the v1.2.0 acronym query-expansion path.
  - Methodology-phrase boost ("modelled estimates" / "modeled estimates")
    surfaces `_MOD`-suffixed codes in the top results.
  - The curated catalog's phantom-code bug is fixed: CME_U5MR / CME_IMR
    / CME_NMR (which don't exist in the unicefdata registry) are gone;
    their alt_synonyms now route to the real codes CME_MRY0T4 / CME_MRY0
    / CME_MRM0.
  - Negative-side: new synonyms don't accidentally boost unrelated
    neutral queries.

Tests run against the LIVE unicefdata registry — same discipline as
``test_v111_scoring.py``.
"""

from __future__ import annotations

from unicefstats_mcp.curated import lookup_preferred
from unicefstats_mcp.server import search_indicators

# ---------------------------------------------------------------------------
# Multi-word + bare-acronym synonym resolution
# ---------------------------------------------------------------------------


def test_u5mr_surfaces_cme_mry0t4() -> None:
    r = search_indicators(query="U5MR", limit=5)
    rec = r.get("recommended") or {}
    assert rec.get("code") == "CME_MRY0T4"


def test_under_five_mortality_surfaces_cme_mry0t4() -> None:
    r = search_indicators(query="under-five mortality", limit=5)
    rec = r.get("recommended") or {}
    assert rec.get("code") == "CME_MRY0T4"


def test_under_5_mortality_surfaces_cme_mry0t4() -> None:
    r = search_indicators(query="under 5 mortality", limit=5)
    rec = r.get("recommended") or {}
    assert rec.get("code") == "CME_MRY0T4"


def test_under_dash_5_mortality_surfaces_cme_mry0t4() -> None:
    r = search_indicators(query="under-5 mortality", limit=5)
    rec = r.get("recommended") or {}
    assert rec.get("code") == "CME_MRY0T4"


def test_imr_surfaces_cme_mry0() -> None:
    """Pins v1.2.0 bare-acronym expansion. v1.1.x curated had a PHANTOM
    code 'CME_IMR' that 404s on get_data; v1.2.0 routes to the real
    canonical CME_MRY0."""
    r = search_indicators(query="IMR", limit=5)
    rec = r.get("recommended") or {}
    assert rec.get("code") == "CME_MRY0"


def test_nmr_surfaces_cme_mrm0() -> None:
    """Same as IMR — v1.1.x curated 'CME_NMR' is a phantom; real code
    is CME_MRM0."""
    r = search_indicators(query="NMR", limit=5)
    rec = r.get("recommended") or {}
    assert rec.get("code") == "CME_MRM0"


# ---------------------------------------------------------------------------
# Methodology-phrase boost — _MOD codes win when methodology is asked for
# ---------------------------------------------------------------------------


def test_modelled_phrase_boosts_mod_codes_in_top_results() -> None:
    """The METHOD_MOD dim-phrase boost surfaces `_MOD` codes in the
    top-N results when the user explicitly asks for modelled estimates.
    Pinning a query where a _MOD variant actually exists (NT_ANT_HAZ_*).
    """
    r = search_indicators(query="stunting modelled estimates", limit=5)
    results = r.get("results", [])
    assert results, f"expected non-empty results, got: {r}"
    top_codes = [x["code"] for x in results[:3]]
    assert any("_MOD" in code for code in top_codes), (
        f"expected at least one _MOD-suffixed code in top 3; got {top_codes}"
    )


def test_modeled_us_spelling_also_boosts() -> None:
    """US spelling 'modeled' (one l) must work the same as UK 'modelled'."""
    r = search_indicators(query="wasting modeled estimates", limit=5)
    results = r.get("results", [])
    top_codes = [x["code"] for x in results[:3]]
    assert any("_MOD" in code for code in top_codes), (
        f"US-spelling boost failed; top3={top_codes}"
    )


# ---------------------------------------------------------------------------
# Curated catalog phantom-code fix
# ---------------------------------------------------------------------------


def test_curated_lookup_no_longer_returns_phantom_codes() -> None:
    """v1.1.x CME_U5MR / CME_IMR / CME_NMR pointed at codes that don't
    exist in the unicefdata registry. v1.2.0 routes them to the real
    canonical codes. lookup_preferred via the multi-word labels must
    NOT return any phantom code.
    """
    for label in (
        "under-five mortality",
        "infant mortality rate",
        "neonatal mortality rate",
    ):
        entry = lookup_preferred(label)
        assert entry is not None, f"curated should match {label!r}"
        # The returned code must be a real one — none of CME_U5MR /
        # CME_IMR / CME_NMR (the phantoms removed in v1.2.0).
        assert entry["code"] not in {"CME_U5MR", "CME_IMR", "CME_NMR"}, (
            f"phantom code {entry['code']!r} returned for {label!r}"
        )


def test_v1_1_1_short_substring_collision_guard_still_holds() -> None:
    """v1.1.1 protection: bare 3-char queries 'imr' / 'imrish' must NOT
    hit the curated catalog (the 5-char guard prevents collisions). The
    v1.2.0 acronym path operates via search_indicators's query-expansion,
    not via lookup_preferred — so this curated-layer test still holds.
    """
    assert lookup_preferred("imr") is None
    assert lookup_preferred("imrish") is None


# ---------------------------------------------------------------------------
# Negative-side smoke — new synonyms don't false-boost neutral queries
# ---------------------------------------------------------------------------


def test_neutral_stunting_query_still_returns_nt_ant_haz_ne2() -> None:
    """Re-pin v1.1.1's test_backward_compat_neutral_query_unchanged from
    a different angle: a plain 'stunting' query must still surface
    NT_ANT_HAZ_NE2 in the top results, with no ambiguity flag.
    """
    r = search_indicators(query="stunting", limit=5)
    assert r.get("ambiguity_flag") is not True
    top_codes = [x["code"] for x in r.get("results", [])[:5]]
    assert "NT_ANT_HAZ_NE2" in top_codes


def test_unrelated_query_not_inflated_by_methodology_boost() -> None:
    """'urban planning literature' has nothing to do with methodology;
    the METHOD_MOD boost must not fire for unrelated queries.
    """
    r = search_indicators(query="urban planning literature", limit=5)
    results = r.get("results", [])
    if results:
        top_rel = results[0].get("relevance", 0)
        assert top_rel <= 70, (
            f"unrelated query inflated to relevance {top_rel}; "
            "the methodology boost should NOT have fired"
        )
