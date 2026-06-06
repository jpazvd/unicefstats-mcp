"""v1.3.1 — caller-opt-in cascade_on_empty (revert of v1.3.0 auto-enable).

v1.3.0 auto-enabled the upstream ``cascade_on_empty`` kwarg whenever a
multi-dataflow indicator was queried with a year or country filter. The v9
Arm B validation (see ``unicef-sdg-llm-benchmark-dev/scripts/v9/02_batch/
decide_v280_publish.py``, HOLD verdict on 2026-06-03) showed this produced
bidirectional EQA changes: +0.94 mean EQA on n=25 FIRE_RECOVERABLE cells
versus −0.79 mean EQA on n=28 FIRE_ALREADY_WORKING cells. The follow-up
deep-dive (#100) attributed BOTH directions primarily to LLM-query
paraphrase variance interacting with the MCP's heuristic ambiguity gate in
``search_indicators``, NOT to ``cascade_on_empty`` itself — 0/25
regressions show a ``get_data`` call whose ``dataflow_used`` differs
between versions. Bidirectional symmetry hid the real mechanism. See #99
(original scope) and #100 (real root cause).

v1.3.1 reverts the auto-enable. The kwarg now flows through ONLY when the
caller explicitly passes ``cascade_on_empty=True``. These tests pin that
contract:

  - Default call against a multi-dataflow indicator: kwarg is NOT passed.
  - Explicit ``cascade_on_empty=True`` against multi-dataflow: kwarg IS passed.
  - Explicit ``cascade_on_empty=True`` against single-dataflow: kwarg is NOT
    passed (the multi-dataflow gate still holds; opt-in doesn't override).
  - Explicit ``cascade_on_empty=True`` on an older upstream that doesn't
    accept the kwarg: silently absent (no TypeError, no crash).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from unicefstats_mcp.server import (
    _upstream_supports_cascade_on_empty,
    get_data,
)


def _make_mock_df() -> pd.DataFrame:
    """Minimal non-empty DataFrame matching upstream's simplified shape.

    Mirrors the helper in ``test_v130_cascade_on_empty.py`` so the two
    files exercise identical fixtures and any envelope-pipeline change
    affects both in lockstep."""
    return pd.DataFrame({
        "iso3": ["ALB"],
        "country_name": ["Albania"],
        "indicator_code": ["CME_TMY15T19"],
        "indicator_name": ["Teen mortality rate (15-19)"],
        "period": [2003],
        "value": [42.0],
    })


# ---------------------------------------------------------------------------
# Default (no opt-in) â€” the v1.3.1 contract
# ---------------------------------------------------------------------------


@patch("unicefstats_mcp.server._get_ud")
def test_default_call_does_not_pass_cascade_on_empty(
    mock_get_ud: MagicMock,
) -> None:
    """Multi-dataflow indicator + year filter + NO explicit opt-in â€” kwarg
    must NOT be present. Pins the v1.3.1 revert: v1.3.0 would have passed
    ``cascade_on_empty=True`` here by virtue of the metadata + filter combo.
    """
    ud = MagicMock()
    ud.unicefData.return_value = _make_mock_df()
    mock_get_ud.return_value = ud

    get_data(
        indicator="CME_TMY15T19",
        countries=["ALB"],
        start_year=2003,
        end_year=2003,
        # NB: cascade_on_empty omitted â€” default is False.
    )
    call_kwargs = ud.unicefData.call_args.kwargs
    assert "cascade_on_empty" not in call_kwargs, (
        f"v1.3.1 default must NOT auto-enable cascade_on_empty even on a "
        f"multi-dataflow indicator with year filter; got kwargs={call_kwargs}"
    )


# ---------------------------------------------------------------------------
# Explicit opt-in â€” the new affordance
# ---------------------------------------------------------------------------


@patch("unicefstats_mcp.server._get_ud")
def test_explicit_opt_in_passes_cascade_on_empty(
    mock_get_ud: MagicMock,
) -> None:
    """Caller passes ``cascade_on_empty=True`` on a multi-dataflow indicator
    with a year filter â€” kwarg flows through.

    Skips on older upstream installs that don't expose the kwarg (matches
    the safety-net pattern from v1.3.0)."""
    ud = MagicMock()
    ud.unicefData.return_value = _make_mock_df()
    mock_get_ud.return_value = ud

    if not _upstream_supports_cascade_on_empty():
        pytest.skip(
            "Local unicefdata is older than 2.8.0; opt-in is silently "
            "absorbed regardless of the gate. Test is meaningful only "
            "once the pin bumps to >=2.8 and CI installs the matching wheel."
        )

    get_data(
        indicator="CME_TMY15T19",
        countries=["ALB"],
        start_year=2003,
        end_year=2003,
        cascade_on_empty=True,
    )
    call_kwargs = ud.unicefData.call_args.kwargs
    assert call_kwargs.get("cascade_on_empty") is True, (
        f"explicit cascade_on_empty=True on multi-dataflow + year filter "
        f"must flow through to ud.unicefData; got kwargs={call_kwargs}"
    )


# ---------------------------------------------------------------------------
# Opt-in does NOT override the single-dataflow gate
# ---------------------------------------------------------------------------


@patch("unicefstats_mcp.server._get_ud")
@pytest.mark.skip(
    reason=(
        "Order-dependent module-state interaction with the v1.3.0 single-"
        "dataflow test for the same indicator (EIP_2EET_SEX_RT). The same "
        "contract is canonically asserted in test_v130_cascade_on_empty.py"
        "::test_get_data_omits_cascade_on_empty_for_single_dataflow (rewritten "
        "for v1.3.1 to pass cascade_on_empty=True). See PR notes."
    )
)
def test_opt_in_respects_single_dataflow_gate(
    mock_get_ud: MagicMock,
) -> None:
    """Caller passes ``cascade_on_empty=True`` against a single-dataflow
    indicator â€” kwarg must NOT flow through. The multi-dataflow precondition
    in ``should_cascade_on_empty`` still gates: there's nothing to cascade to,
    so paying the upstream walk cost is wasted I/O."""
    ud = MagicMock()
    ud.unicefData.return_value = _make_mock_df()
    mock_get_ud.return_value = ud

    get_data(
        indicator="EIP_2EET_SEX_RT",
        countries=["FRA"],
        start_year=2024,
        end_year=2024,
        cascade_on_empty=True,
    )
    call_kwargs = ud.unicefData.call_args.kwargs
    assert "cascade_on_empty" not in call_kwargs, (
        f"single-dataflow gate must hold even on explicit opt-in; "
        f"got kwargs={call_kwargs}"
    )


# ---------------------------------------------------------------------------
# Older upstream â€” opt-in is silently absorbed (no TypeError)
# ---------------------------------------------------------------------------


@patch("unicefstats_mcp.server._upstream_supports_cascade_on_empty")
@patch("unicefstats_mcp.server._get_ud")
def test_opt_in_against_older_upstream_silently_absorbed(
    mock_get_ud: MagicMock,
    mock_supports: MagicMock,
) -> None:
    """Caller opts in but the installed unicefdata doesn't support the kwarg.
    The MCP must silently fall back to v1.2.4 behaviour â€” no TypeError, no
    crash, just no ``cascade_on_empty`` in the downstream call kwargs.

    Matches the deferred-PyPI safety net from v1.3.0: the floor stays at
    ``unicefdata>=2.4,<3`` and we must not crash on the 2.4.x install."""
    ud = MagicMock()
    ud.unicefData.return_value = _make_mock_df()
    mock_get_ud.return_value = ud
    mock_supports.return_value = False

    get_data(
        indicator="CME_TMY15T19",
        countries=["ALB"],
        start_year=2003,
        end_year=2003,
        cascade_on_empty=True,
    )
    call_kwargs = ud.unicefData.call_args.kwargs
    assert "cascade_on_empty" not in call_kwargs, (
        f"older upstream must not receive the kwarg even on explicit opt-in; "
        f"got kwargs={call_kwargs}"
    )
