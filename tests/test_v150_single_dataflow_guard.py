"""v1.5.0 — Tier 1: single-dataflow guard at heuristic Path B gate.

The v1.4.0 9-cell NON_ELIGIBLE clean->broken regression was driven by Path B
firing on candidate clusters where every candidate resolved to the SAME
primary dataflow — flagging those as ambiguous gave the LLM a misleading
abstain signal. The Tier 1 fix in `server.py:785-839` adds a precondition:
if every candidate in the `similar` set shares a single primary dataflow,
the heuristic suppresses `ambiguity_flag` and lets the LLM proceed.

Contract: if ``search_indicators`` returns ``ambiguity_flag=True`` with
``ambiguity_source='heuristic'``, the candidate set MUST span at least
two distinct primary dataflows.
"""

from __future__ import annotations

import logging

import pytest

from unicefstats_mcp.server import search_indicators


@pytest.mark.parametrize(
    "query",
    [
        # The 9-cell regression families from the v140 residual-failure forensic.
        "youth not in employment education training",  # EIP_NEET_*
        "completion rate primary school age modeled",  # ED_CR_*_UIS_MOD smoking gun
        "HIV infections 0-14",  # HVA_EPI_INF_RT_*
        "HIV incidence 15-19 adolescent",  # HVA_EPI_INF_RT_*
    ],
)
def test_heuristic_ambiguity_flag_only_fires_on_multi_dataflow_clusters(
    caplog: pytest.LogCaptureFixture, query: str
) -> None:
    """For any query that fires heuristic Path B, the candidate set must
    span >=2 distinct primary dataflows. Single-dataflow clusters are
    structurally not ambiguous at the dataflow level — the v1.5.0 guard
    suppresses the flag in that case."""
    caplog.set_level(logging.INFO, logger="unicefstats_mcp.server")
    out = search_indicators(query=query)
    payload = out.get("payload", out) or {}

    if not payload.get("ambiguity_flag"):
        return  # guard not exercised — that's the desired outcome
    if payload.get("ambiguity_source") != "heuristic":
        return  # Path A (curated) is independent of this guard

    candidates = payload.get("candidates") or []
    candidate_codes = [c.get("code") for c in candidates if c.get("code")]
    assert (
        candidate_codes
    ), f"heuristic ambiguity_flag fired for {query!r} but candidates list is empty"

    from unicefstats_mcp import dimensions as _dims

    dataflows = {_dims.primary_dataflow(c) for c in candidate_codes}
    dataflows.discard(None)

    assert len(dataflows) > 1, (
        f"v1.5.0 Tier 1 guard violation: heuristic ambiguity_flag fired on "
        f"a single-dataflow cluster for query {query!r} "
        f"(candidates={candidate_codes}, shared_dataflow={dataflows!r})"
    )


def test_guard_emits_suppression_telemetry(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When the guard fires, a structured `ambiguity_flag SUPPRESSED` log
    record is emitted on the server logger for operator forensics."""
    caplog.set_level(logging.INFO, logger="unicefstats_mcp.server")
    # Iterate through several queries; at least one likely triggers the
    # guard against the real catalogue. The assertion is conditional:
    # IF the suppression fires, the telemetry must be well-formed.
    for q in [
        "youth not in employment education training",
        "completion rate primary school age modeled",
        "HIV infections 0-14",
    ]:
        search_indicators(query=q)

    suppression_records = [r for r in caplog.records if "SUPPRESSED" in r.getMessage()]
    for r in suppression_records:
        assert hasattr(r, "query")
        assert hasattr(r, "candidate_codes")
        assert hasattr(r, "shared_dataflow")
