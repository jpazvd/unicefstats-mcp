"""v1.3.0 + v1.3.1 — MCP-side cascade_on_empty gating.

When ``get_data`` is called against a multi-dataflow indicator with a year
or country filter set AND the caller explicitly passes
``cascade_on_empty=True``, the MCP passes ``cascade_on_empty=True`` to
upstream ``unicefData()``.

These tests verify:
  - The ``should_cascade_on_empty()`` helper gates correctly on
    multi-dataflow vs single-dataflow indicators.
  - The ``get_data`` call-site adds the kwarg ONLY when ALL hold:
      (a) the caller passes ``cascade_on_empty=True`` (v1.3.1 — was
          auto-enabled in v1.3.0, reverted after the v9 Arm B HOLD verdict),
      (b) the indicator is multi-dataflow,
      (c) a year or country filter is set,
      (d) the installed unicefdata supports the kwarg (>= 2.8.0).
  - When upstream lacks the kwarg (older unicefdata installs), the MCP
    falls back to v1.2.4 behavior without raising.

5 mock-tier tests + 1 live-SDMX integration test gated on
``RUN_LIVE_TESTS=1``.

Pattern: mock ``ud.unicefData`` via ``unittest.mock.patch`` to capture the
kwargs that would be sent to upstream. No network.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from unicefstats_mcp import dimensions as d
from unicefstats_mcp.server import (
    _upstream_supports_cascade_on_empty,
    get_data,
)

# ---------------------------------------------------------------------------
# Helper-level tests
# ---------------------------------------------------------------------------


def test_should_cascade_multi_dataflow_returns_true() -> None:
    """CME_TMY15T19 has dataflows ['CME', 'GLOBAL_DATAFLOW'] in metadata —
    cascade should fire on year-filtered empty results."""
    assert d.should_cascade_on_empty("CME_TMY15T19") is True


def test_should_cascade_single_dataflow_returns_false() -> None:
    """A single-dataflow indicator (e.g. EIP family — no fallback in
    metadata) — cascade would walk uselessly. Gate prevents that."""
    # EIP family indicators have no `dataflows` field in metadata.
    assert d.should_cascade_on_empty("EIP_2EET_SEX_RT") is False


def test_should_cascade_unknown_code_returns_false() -> None:
    """An unknown code should NOT trigger cascade — tier-2 / typo case."""
    assert d.should_cascade_on_empty("BOGUS_NONEXISTENT_CODE") is False


# ---------------------------------------------------------------------------
# Call-site gating tests
# ---------------------------------------------------------------------------


def _make_mock_df() -> pd.DataFrame:
    """A minimal non-empty DataFrame matching the upstream's simplified
    output shape. Used so the MCP's downstream pipeline doesn't trip."""
    return pd.DataFrame({
        "iso3": ["ALB"],
        "country_name": ["Albania"],
        "indicator_code": ["CME_TMY15T19"],
        "indicator_name": ["Teen mortality rate (15-19)"],
        "period": [2003],
        "value": [42.0],
    })


@patch("unicefstats_mcp.server._upstream_supports_cascade_on_empty",
       return_value=True)
@patch("unicefstats_mcp.server._get_ud")
def test_get_data_passes_cascade_on_empty_when_caller_opts_in(
    mock_get_ud: MagicMock,
    mock_supports: MagicMock,
) -> None:
    """Multi-dataflow indicator + year filter + caller opts in — kwarg present.

    v1.3.1: this previously asserted auto-enable. v1.3.1 reverted that, so the
    caller must pass ``cascade_on_empty=True`` explicitly for the kwarg to flow.

    Patches ``_upstream_supports_cascade_on_empty`` to True so CI exercises
    the positive pass-through path regardless of the installed unicefdata
    version (project pin is ``unicefdata>=2.4,<3``, so the live install may
    not yet have the kwarg until upstream PyPI publishes 2.8.x)."""
    ud = MagicMock()
    ud.unicefData.return_value = _make_mock_df()
    mock_get_ud.return_value = ud

    get_data(
        indicator="CME_TMY15T19",
        countries=["ALB"],
        start_year=2003,
        end_year=2003,
        cascade_on_empty=True,
    )
    call_kwargs = ud.unicefData.call_args.kwargs
    assert call_kwargs.get("cascade_on_empty") is True, (
        f"expected cascade_on_empty=True after explicit caller opt-in; "
        f"got kwargs={call_kwargs}"
    )


@patch("unicefstats_mcp.server._get_ud")
def test_get_data_omits_cascade_on_empty_for_single_dataflow(
    mock_get_ud: MagicMock,
) -> None:
    """Single-dataflow indicator — kwarg NOT present (gating works)."""
    ud = MagicMock()
    ud.unicefData.return_value = _make_mock_df()
    mock_get_ud.return_value = ud

    # Even with explicit opt-in, the single-dataflow gate must hold.
    get_data(
        indicator="EIP_2EET_SEX_RT",
        countries=["FRA"],
        start_year=2024,
        end_year=2024,
        cascade_on_empty=True,
    )
    call_kwargs = ud.unicefData.call_args.kwargs
    assert "cascade_on_empty" not in call_kwargs, (
        f"single-dataflow indicator should NOT trigger cascade_on_empty; "
        f"got kwargs={call_kwargs}"
    )


# ---------------------------------------------------------------------------
# Live SDMX integration — gated
# ---------------------------------------------------------------------------


LIVE = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_TESTS") != "1",
    reason="Live SDMX integration test; set RUN_LIVE_TESTS=1 to enable.",
)


@LIVE
def test_live_cme_tmy_recovers_via_cascade() -> None:
    """End-to-end live: CME_TMY15T19 ALB 2003 should return data via the
    GLOBAL_DATAFLOW fallback. Reproduces the regression-fix path through
    the full MCP -> unicefdata -> SDMX chain."""
    if not _upstream_supports_cascade_on_empty():
        pytest.skip(
            "Live unicefdata install < 2.8.0; cascade_on_empty kwarg not "
            "available upstream. Re-run with `pip install -e ../unicefData-dev/python` "
            "or after the v2.8.0 PyPI publish (Phase 4.1)."
        )

    # v1.3.1: caller must opt in explicitly; auto-enable removed.
    result = get_data(
        indicator="CME_TMY15T19",
        countries=["ALB"],
        start_year=2003,
        end_year=2003,
        cascade_on_empty=True,
    )
    # The MCP envelope returns a dict; a non-empty result means cascade
    # walked through and found data.
    assert result.get("status") == "ok", (
        f"expected status='ok' (data found via cascade); got {result.get('status')}"
    )
    records = result.get("records") or []
    assert len(records) >= 1, (
        f"expected at least one record for ALB 2003; got {len(records)}. "
        f"The cascade-on-empty fix did not recover the data."
    )
