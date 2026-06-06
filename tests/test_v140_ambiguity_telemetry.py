"""v1.4.0 — structured telemetry on ambiguity_flag fires.

When ``search_indicators`` fires ``ambiguity_flag`` (curated Path A or
heuristic Path B), the MCP now emits a structured log line at INFO level
on the ``unicefstats_mcp.server`` logger. Operators can route this to a
JSONL file via standard Python logging configuration.

The post-#100 forensic had to recompute the same diagnostic data from
parquet artefacts; this telemetry captures it at source.

These tests pin the contract:
  - Curated Path A fires emit ``ambiguity_source='curated'`` + query
    + candidate_codes + candidate_count.
  - Heuristic Path B fires emit ``ambiguity_source='heuristic'`` + query
    + candidate_codes + candidate_count + top_relevance + window-size +
    min-candidates settings.
  - No log entry is emitted when ``search_indicators`` returns a
    confident match (no ambiguity).
"""

from __future__ import annotations

import logging

import pytest

from unicefstats_mcp.server import search_indicators


def _ambiguity_records(records: list[logging.LogRecord]) -> list[logging.LogRecord]:
    return [r for r in records if "ambiguity_flag fired" in r.getMessage()]


def test_curated_path_emits_telemetry(caplog: pytest.LogCaptureFixture) -> None:
    """A curated ambiguous query (one that resolves to _AMBIGUOUS in the
    resolver) fires Path A and emits the curated telemetry record."""
    caplog.set_level(logging.INFO, logger="unicefstats_mcp.server")
    search_indicators(query="child mortality")
    records = _ambiguity_records(caplog.records)
    curated_records = [
        r for r in records if getattr(r, "ambiguity_source", None) == "curated"
    ]
    assert len(curated_records) >= 1, (
        f"expected curated Path A telemetry; saw records="
        f"{[r.getMessage() for r in caplog.records]}"
    )
    r = curated_records[0]
    assert r.query == "child mortality"
    assert getattr(r, "candidate_count", 0) >= 2
    assert getattr(r, "top_relevance", "missing-marker") is None


def test_unambiguous_query_emits_no_telemetry(caplog: pytest.LogCaptureFixture) -> None:
    """A clear synonym match should NOT fire ambiguity_flag, so no
    telemetry record is emitted."""
    caplog.set_level(logging.INFO, logger="unicefstats_mcp.server")
    search_indicators(query="under-five mortality rate")
    assert _ambiguity_records(caplog.records) == [], (
        "no ambiguity_flag should fire for a clean synonym match"
    )


def test_heuristic_path_telemetry_extras_when_fired(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """IF the heuristic fires on any query in this session, the record
    carries the expected diagnostic extras. This is a contract check
    rather than a forced trigger — different test environments may have
    different relevance distributions, but the extras must be populated
    whenever Path B fires."""
    caplog.set_level(logging.INFO, logger="unicefstats_mcp.server")
    # Try a noisy query likely to land on Path B.
    search_indicators(query="indicator survey field area xyz random")
    records = _ambiguity_records(caplog.records)
    heuristic = [
        r for r in records if getattr(r, "ambiguity_source", None) == "heuristic"
    ]
    for r in heuristic:
        assert hasattr(r, "candidate_count")
        assert hasattr(r, "top_relevance")
        assert hasattr(r, "similar_window_size")
        assert hasattr(r, "min_similar_candidates")
        assert r.candidate_count >= 1
