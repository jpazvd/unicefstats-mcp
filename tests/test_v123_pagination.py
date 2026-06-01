"""v1.2.3 — pagination metadata tests.

Pins the per-tool pagination envelope (total_count / count / offset /
has_more / next_offset) plus the v1.1.x-compat aliases that callers may
already depend on.

Also pins the v1.2.3 fix for Copilot finding #91 L652: when the caller
pages past the last page (offset >= total_count), the tool must return a
valid empty-page envelope, NOT a no-data error claiming there are no
matches at all.

Tests run against the LIVE unicefdata registry — same discipline as
``test_v111_scoring.py`` and ``test_v120_synonyms.py``.
"""

from __future__ import annotations

from unicefstats_mcp.server import (
    list_categories,
    list_countries,
    search_indicators,
)

# ---------------------------------------------------------------------------
# search_indicators
# ---------------------------------------------------------------------------


def test_search_indicators_default_offset_zero_returns_first_page() -> None:
    """Default call (no offset arg) should behave exactly as v1.2.2: page 1,
    offset=0, and the new pagination metadata should agree with the
    v1.1.x-compat aliases.
    """
    r = search_indicators(query="mortality", limit=10)
    assert "error" not in r
    assert r["offset"] == 0
    assert r["count"] == len(r["results"])
    # v1.1.x-compat aliases
    assert r["showing"] == r["count"]
    assert r["total_matches"] == r["total_count"]
    # When there are more matches than the limit, has_more must be True.
    if r["total_count"] > 10:
        assert r["has_more"] is True
        assert r["next_offset"] == 10
    else:
        assert r["has_more"] is False
        assert r["next_offset"] is None


def test_search_indicators_offset_pages_correctly() -> None:
    """offset=10 must skip the first 10 results."""
    page1 = search_indicators(query="mortality", limit=5, offset=0)
    page2 = search_indicators(query="mortality", limit=5, offset=5)
    # Both pages must succeed.
    assert "error" not in page1
    assert "error" not in page2
    # Different rows on each page (assuming >5 mortality matches, which holds).
    page1_codes = [r["code"] for r in page1["results"]]
    page2_codes = [r["code"] for r in page2["results"]]
    assert page1_codes != page2_codes, (
        f"page1 and page2 returned identical codes:\n  {page1_codes}"
    )
    # offset advances correctly.
    assert page1["offset"] == 0
    assert page2["offset"] == 5


def test_search_indicators_offset_past_end_returns_empty_page_not_error() -> None:
    """v1.2.3 Copilot #91 L652 fix: paging past the last page must return
    a valid envelope with `count=0` and `has_more=False`, NOT a no-data
    error claiming no indicators match.
    """
    huge_offset = 1_000_000
    r = search_indicators(query="mortality", limit=10, offset=huge_offset)
    # The tool must NOT report "no indicators match" — there ARE matches,
    # just none on this page.
    assert "error" not in r, (
        f"expected empty-page envelope, got error: {r.get('error')!r}"
    )
    assert r["count"] == 0
    assert r["has_more"] is False
    assert r["next_offset"] is None
    assert r["total_count"] > 0, (
        "test relies on at least one mortality match existing; if this fails "
        "the test fixture is broken, not the pagination logic"
    )
    assert r["results"] == []
    # The tip points the caller back at offset=0 so they can recover in one wave.
    assert "offset=0" in r["tip"]


def test_search_indicators_genuine_no_match_still_errors() -> None:
    """v1.2.3 fix must NOT regress the v1.1.x behavior for genuine no-match
    queries — `zzzznosuchquery` returns no matches in either path.
    """
    r = search_indicators(query="zzzznosuchquery", limit=10)
    assert "error" in r
    # The `error()` helper translates `no_data=True` into status="no_data";
    # the boolean kwarg doesn't survive as a top-level field.
    assert r.get("status") == "no_data"


# ---------------------------------------------------------------------------
# list_categories
# ---------------------------------------------------------------------------


def test_list_categories_default_returns_pagination_envelope() -> None:
    r = list_categories()
    assert "error" not in r
    # v1.2.3 fields present.
    assert "total_count" in r
    assert "count" in r
    assert "offset" in r
    assert "has_more" in r
    assert "next_offset" in r
    # v1.1.x-compat fields still present.
    assert "total_categories" in r
    assert "total_indicators" in r
    # Default limit=100 covers the full ~30-category universe in one page.
    assert r["has_more"] is False
    assert r["next_offset"] is None
    assert r["count"] == r["total_count"]
    assert r["total_categories"] == r["total_count"]


def test_list_categories_offset_skips_categories() -> None:
    page1 = list_categories(limit=3, offset=0)
    page2 = list_categories(limit=3, offset=3)
    assert "error" not in page1
    assert "error" not in page2
    p1_codes = [c["name"] for c in page1["categories"]]
    p2_codes = [c["name"] for c in page2["categories"]]
    assert p1_codes != p2_codes
    assert page1["count"] <= 3
    assert page2["offset"] == 3


# ---------------------------------------------------------------------------
# list_countries
# ---------------------------------------------------------------------------


def test_list_countries_default_returns_pagination_envelope() -> None:
    r = list_countries()
    assert "error" not in r
    # v1.2.3 fields present.
    assert "total_count" in r
    assert "count" in r
    assert "offset" in r
    assert "has_more" in r
    assert "next_offset" in r
    # v1.1.x-compat field still present.
    assert "total" in r
    assert r["total"] == r["total_count"]
    # Default limit=250 should cover the full ~200-country universe.
    assert r["has_more"] is False
    assert r["count"] == r["total_count"]


def test_list_countries_offset_pages_alphabetically() -> None:
    page1 = list_countries(limit=10, offset=0)
    page2 = list_countries(limit=10, offset=10)
    assert "error" not in page1
    assert "error" not in page2
    p1_iso = [c["iso3"] for c in page1["countries"]]
    p2_iso = [c["iso3"] for c in page2["countries"]]
    # Both pages must succeed and be different.
    assert p1_iso != p2_iso
    # Countries are sorted alphabetically by ISO3; page 2's first code
    # must be alphabetically after page 1's last.
    if p1_iso and p2_iso:
        assert p1_iso[-1] < p2_iso[0]


def test_list_countries_offset_past_end_returns_empty_page_not_error() -> None:
    """Same Copilot #91 L652-shaped invariant for list_countries."""
    r = list_countries(limit=10, offset=10_000)
    assert "error" not in r
    assert r["count"] == 0
    assert r["has_more"] is False
    assert r["next_offset"] is None
    assert r["countries"] == []


def test_list_countries_region_filter_then_pagination() -> None:
    """Pagination must apply AFTER the region substring-filter, not before
    — otherwise the user paging through 'south asia' would see countries
    from elsewhere on later pages.
    """
    r = list_countries(region="south", limit=5, offset=0)
    assert "error" not in r
    # Every returned country must contain 'south' in its name.
    for c in r["countries"]:
        assert "south" in c["name"].lower()
    # total_count is the count of region-filtered countries, not the raw 200+.
    assert r["total_count"] < 200
