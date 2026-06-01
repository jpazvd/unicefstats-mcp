"""Regression tests for `_extract_from_tool_calls` result persistence.

Locks in the contract introduced in commit 126888a:

  - Tool results dispatched at run time are persisted in the call record
    as `tc["result"]` (a JSON string).
  - At analysis time, `_extract_from_tool_calls` reads `tc["result"]`
    first; it only re-invokes `dispatch_tool` against the live MCP when
    the record was written by an older harness that lacked the field.

Why this matters: post-run re-dispatch had been silently coupling EQA
extraction to upstream UNICEF SDMX availability long after the
benchmark itself completed. A 1500-call burst (Wave 1+2 of an n=500 run)
was enough to trigger transient 404 cascades on the second-pass
re-dispatch, which the script tolerated by falling through to text
extraction — biasing EQA downward by ~0.16 in a way that had nothing
to do with the MCP under test. See the v0.7.3 post-fix run debrief.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# benchmark_eqa imports `anthropic` and `dotenv` at module level. CI's
# [dev] install does not include them (both live in the [benchmark]
# extra), so without these guards the test module fails to collect on CI
# even though the actual test logic never touches either SDK. Matches the
# convention in tests/test_harness_alignment.py and test_state_checkpoint.py.
pytest.importorskip("anthropic")
pytest.importorskip("dotenv")

# The extractor lives in the benchmark harness, which is at examples/, not
# under the importable `unicefstats_mcp` package.
EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"
sys.path.insert(0, str(EXAMPLES_DIR))


# Importing benchmark_eqa initialises a few things (Anthropic client setup,
# pricing dict). These work without an API key — we never call the real
# Anthropic in these tests.
from benchmark_eqa import _extract_from_tool_calls, extract_numeric  # noqa: E402


def test_uses_persisted_result_without_dispatching(monkeypatch):
    """When `tc["result"]` is present, dispatch_tool MUST NOT be called."""

    def _fail_if_called(*_args, **_kwargs):
        raise AssertionError(
            "dispatch_tool was invoked even though the call record had a "
            "persisted result — the extractor regressed to its old "
            "re-dispatch path."
        )

    monkeypatch.setattr("benchmark_eqa.dispatch_tool", _fail_if_called)

    persisted = json.dumps({
        "data": [
            {"period": 2022, "value": 8.0},
            {"period": 2024, "value": 8.4},  # max period — extractor picks this
            {"period": 2023, "value": 8.2},
        ],
    })
    tool_calls = [
        {"tool": "search_indicators", "input": {"query": "neonatal mortality"}},
        {"tool": "get_data", "input": {"indicator": "CME_MRM0", "countries": ["HND"]},
         "result": persisted},
    ]

    value, year = _extract_from_tool_calls(tool_calls)

    assert value == pytest.approx(8.4)
    assert year == 2024


def test_falls_back_to_dispatch_when_result_absent(monkeypatch):
    """When `tc["result"]` is missing (older parquet), dispatch_tool is called."""

    dispatch_inputs: list[tuple[str, dict]] = []

    def _fake_dispatch(name: str, args: dict) -> str:
        dispatch_inputs.append((name, args))
        return json.dumps({"data": [{"period": 2019, "value": 33.4}]})

    monkeypatch.setattr("benchmark_eqa.dispatch_tool", _fake_dispatch)

    legacy_tool_calls = [
        {"tool": "get_data", "input": {"indicator": "MNCH_CSEC", "countries": ["BOL"]}},
    ]

    value, year = _extract_from_tool_calls(legacy_tool_calls)

    assert value == pytest.approx(33.4)
    assert year == 2019
    # Exactly one re-dispatch — the legacy fallback path
    assert dispatch_inputs == [("get_data", {"indicator": "MNCH_CSEC", "countries": ["BOL"]})]


def test_persisted_result_takes_precedence_over_dispatch(monkeypatch):
    """If both fields exist, the persisted result wins (live MCP may have drifted)."""

    def _fake_dispatch_returns_wrong(*_args, **_kwargs):
        # The whole point of persistence is to ignore the live MCP; if this
        # value ever leaks into the extracted result, the test will fail
        # because it's not what `persisted` says.
        return json.dumps({"data": [{"period": 2025, "value": 99.9}]})

    monkeypatch.setattr("benchmark_eqa.dispatch_tool", _fake_dispatch_returns_wrong)

    persisted = json.dumps({"data": [{"period": 2024, "value": 3.885}]})
    tool_calls = [
        {"tool": "get_data",
         "input": {
             "indicator": "CME_MRY0T4",
             "countries": ["NLD"],
             "start_year": 2024,
             "end_year": 2024,
         },
         "result": persisted},
    ]

    value, year = _extract_from_tool_calls(tool_calls)

    assert value == pytest.approx(3.885)
    assert year == 2024


def test_malformed_persisted_result_falls_back(monkeypatch):
    """If `tc["result"]` is not valid JSON, the extractor doesn't crash —
    it falls through and returns (None, None) once the record exhausts."""

    def _no_dispatch(*_args, **_kwargs):
        return json.dumps({"data": [{"period": 2020, "value": 50.0}]})

    monkeypatch.setattr("benchmark_eqa.dispatch_tool", _no_dispatch)

    tool_calls = [
        {"tool": "get_data", "input": {"indicator": "X"}, "result": "this is not json"},
    ]

    value, year = _extract_from_tool_calls(tool_calls)

    # Malformed result on the only get_data record → no fallback for THIS
    # record (we already had a result, just couldn't parse it). The function
    # exhausts the loop and returns (None, None).
    assert value is None
    assert year is None


# ---------------------------------------------------------------------------
# extract_numeric (text-based fallback) — context-capture regression suite
# ---------------------------------------------------------------------------
#
# v1.4 of the extractor (introduced after the v0.7.3 v4 hallucination
# analysis) tightened refusal handling: any response containing explicit
# refusal language ("no data is available", "not available", "does not
# exist", etc.) is treated as a refusal and returns None, even if the
# response then provides surrounding-year data points as conversational
# context. The previous v1.3 behaviour pulled context numbers as if they
# were the answer, scoring 45 of 49 v4 hallucinations as fabrications
# when the model had actually refused correctly.


def test_extract_numeric_refusal_with_context_returns_none():
    """Refusal preamble followed by context numbers must still return None.

    Verbatim shape from v0.7.3 v4 (NT_ANT_HAZ_NE2 SLE 2020 direct).
    """
    response = (
        "No data is available for stunting prevalence in Sierra Leone for 2020. "
        "The UNICEF database shows that for Sierra Leone, stunting data "
        "(Height-for-age <-2 SD) is available for 2019 (29.4872%) and "
        "2021 (26.2586%), but not for 2020."
    )
    assert extract_numeric(response) is None, (
        "Context numbers (29.4872, 26.2586) must not be extracted when the "
        "preamble is an explicit refusal — the model is correctly refusing, "
        "the surrounding-year data is just conversational context."
    )


def test_extract_numeric_refusal_with_resolver_substitution_returns_none():
    """Wrong-indicator-substitution refusals (issue #64) also return None.

    Verbatim shape from MNCH_BIRTH18 WLF baseline_latest in v4: model
    refuses on the asked-for indicator but offers the resolver's
    near-neighbour (adolescent birth rate) as a courtesy.
    """
    response = (
        "Based on the UNICEF data, I can provide you with information about "
        "adolescent births in Wallis and Futuna, though this is for the "
        "broader age group of 15-19 years rather than specifically under 18. "
        "The latest available data for the Adolescent birth rate "
        "(number of live births to adolescent women per 1,000) is approximately "
        "10.0 per 1,000 in 2021. The specific data on births to women under 18 "
        "is not available in the UNICEF database."
    )
    assert extract_numeric(response) is None


def test_extract_numeric_clean_value_still_extracted():
    """Unambiguous successful response still returns its value."""
    response = (
        "Based on the UNICEF data, the under-five mortality rate for the "
        "Netherlands in 2024 was 3.8851310792395 per 1,000 live births."
    )
    val = extract_numeric(response)
    assert val is not None
    assert abs(val - 3.8851) < 1e-3


def test_extract_numeric_refusal_alone_returns_none():
    """Bare refusal without context numbers must obviously return None."""
    response = (
        "Norfolk Island is not available in the UNICEF database for "
        "underweight prevalence data."
    )
    assert extract_numeric(response) is None
