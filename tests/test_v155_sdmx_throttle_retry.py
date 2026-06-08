"""v1.5.5 — Opt-in SDMX throttle + retry-on-403 hardening.

The Jun 7 benchmark batches (v1.5.2 and v1.5.4) both aborted mid-Wave-3
when UNICEF SDMX's WAF / per-IP rate-limiter triggered. Memory note
`feedback_sdmx_403_burst_transient_pattern.md` (updated 2026-06-07)
documents the revised pattern hypothesis: bursts are request-volume
triggered (sustained > ~50-100 calls/min), not 24-72h time-bounded
transients as originally documented. Two bursts in 90 minutes with a
clean window between confirmed this.

v1.5.5 adds two opt-in defences via environment variables so normal
(non-batch) MCP server use is unchanged:

  UNICEFSTATS_SDMX_THROTTLE_MS  — inter-call delay (default 0 = off)
  UNICEFSTATS_SDMX_RETRY_403=1  — retry 403s with 30/60/120s backoff

These tests pin both contracts with mocked SDMX calls so we never touch
real network.
"""

from __future__ import annotations

import os
import time
from unittest.mock import patch

import pytest

import unicefstats_mcp.server as server

# ---------------------------------------------------------------------------
# 403 detection
# ---------------------------------------------------------------------------


def test_is_403_matches_sdmx_forbidden_error_by_name() -> None:
    """`_is_403` must match the `SDMXForbiddenError` exception class by
    NAME so we don't have to depend on importing `unicefdata.exceptions`
    at module load time."""

    class SDMXForbiddenError(Exception):
        pass

    e = SDMXForbiddenError(
        "Access Denied (403): You do not have permission to access 'X'."
    )
    assert server._is_403(e) is True


def test_is_403_matches_by_message_when_class_name_differs() -> None:
    """Fallback path: any exception whose message contains '403' AND
    'Access Denied' counts as a 403. Covers `RuntimeError`-wrapped 403s."""
    e = RuntimeError("Access Denied (403): You do not have permission to access 'X'.")
    assert server._is_403(e) is True


def test_is_403_rejects_unrelated_exceptions() -> None:
    assert server._is_403(ValueError("bad value")) is False
    assert server._is_403(ConnectionError("network")) is False
    assert server._is_403(RuntimeError("404 not found")) is False


# ---------------------------------------------------------------------------
# Throttle
# ---------------------------------------------------------------------------


def test_throttle_default_is_zero() -> None:
    """No throttle by default — preserves normal MCP server use case."""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop(server._THROTTLE_MS_ENV, None)
        assert server._throttle_ms() == 0


def test_throttle_reads_env_var() -> None:
    with patch.dict(os.environ, {server._THROTTLE_MS_ENV: "250"}):
        assert server._throttle_ms() == 250


def test_throttle_rejects_garbage_silently() -> None:
    """Invalid env-var values fall back to 0 (no throttle) rather than
    erroring at startup."""
    with patch.dict(os.environ, {server._THROTTLE_MS_ENV: "not-a-number"}):
        assert server._throttle_ms() == 0


def test_throttle_clamps_negative_to_zero() -> None:
    with patch.dict(os.environ, {server._THROTTLE_MS_ENV: "-100"}):
        assert server._throttle_ms() == 0


def test_call_sdmx_with_throttle_enforces_minimum_delay() -> None:
    """When throttle is configured to 100ms and two `_call_sdmx` calls
    happen back-to-back, the second must wait at least 90ms before
    executing (10ms tolerance for scheduling jitter)."""
    server._last_sdmx_call_ts[0] = 0.0  # reset
    with patch.dict(os.environ, {server._THROTTLE_MS_ENV: "100"}):
        t0 = time.monotonic()
        server._call_sdmx(lambda: 1)
        server._call_sdmx(lambda: 2)
        elapsed_ms = (time.monotonic() - t0) * 1000.0
    assert (
        elapsed_ms >= 90.0
    ), f"v1.5.5 throttle failed to enforce 100ms minimum; elapsed={elapsed_ms:.1f}ms"


def test_call_sdmx_without_throttle_does_not_sleep() -> None:
    """Default behaviour: zero throttle means back-to-back calls finish
    in well under 100ms (essentially instant)."""
    server._last_sdmx_call_ts[0] = 0.0
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop(server._THROTTLE_MS_ENV, None)
        t0 = time.monotonic()
        for _ in range(5):
            server._call_sdmx(lambda: 0)
        elapsed_ms = (time.monotonic() - t0) * 1000.0
    assert (
        elapsed_ms < 100.0
    ), f"v1.5.5 unthrottled _call_sdmx should be near-instant; got {elapsed_ms:.1f}ms"


# ---------------------------------------------------------------------------
# Retry-on-403
# ---------------------------------------------------------------------------


def test_retry_403_disabled_by_default() -> None:
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop(server._RETRY_403_ENV, None)
        assert server._retry_403_enabled() is False


@pytest.mark.parametrize("val", ["1", "true", "True", "yes", "on"])
def test_retry_403_enabled_by_env(val: str) -> None:
    with patch.dict(os.environ, {server._RETRY_403_ENV: val}):
        assert server._retry_403_enabled() is True


def test_call_sdmx_without_retry_403_reraises_immediately() -> None:
    """Default behaviour preserves v1.5.4: a 403 fails fast, no backoff."""

    class SDMXForbiddenError(Exception):
        pass

    def fn() -> int:
        raise SDMXForbiddenError("Access Denied (403): ...")

    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop(server._RETRY_403_ENV, None)
        os.environ.pop(server._THROTTLE_MS_ENV, None)
        t0 = time.monotonic()
        with pytest.raises(SDMXForbiddenError):
            server._call_sdmx(fn)
        elapsed = time.monotonic() - t0
    assert (
        elapsed < 1.0
    ), f"v1.5.5: 403 without RETRY_403=1 must fail fast; got {elapsed:.2f}s"


def test_call_sdmx_with_retry_403_retries_with_backoff(monkeypatch) -> None:
    """When RETRY_403 is on AND the closure raises 403 every time, the
    helper retries with the documented backoff schedule (30/60/120s)
    and ultimately re-raises after attempts are exhausted. We monkey-
    patch `_time.sleep` to a no-op so the test runs in milliseconds
    while still exercising the call sequence."""

    class SDMXForbiddenError(Exception):
        pass

    attempts: list[int] = []

    def fn() -> int:
        attempts.append(len(attempts))
        raise SDMXForbiddenError(f"Access Denied (403): attempt {len(attempts)}")

    sleeps: list[float] = []
    monkeypatch.setattr(server._time, "sleep", sleeps.append)

    with (
        patch.dict(os.environ, {server._RETRY_403_ENV: "1"}),
        pytest.raises(SDMXForbiddenError),
    ):
        server._call_sdmx(fn)

    # 1 initial attempt + 3 retries = 4 attempts total.
    assert len(attempts) == 4, f"expected 4 attempts; got {len(attempts)}"
    # Backoff schedule applied between retries — exact values can vary if
    # the inner `_retry` also sleeps for non-client errors, but the three
    # 403-specific backoffs (30, 60, 120) MUST be in the sleep log.
    assert 30.0 in sleeps, f"missing 30s backoff in sleep log: {sleeps}"
    assert 60.0 in sleeps, f"missing 60s backoff in sleep log: {sleeps}"
    assert 120.0 in sleeps, f"missing 120s backoff in sleep log: {sleeps}"


def test_call_sdmx_with_retry_403_succeeds_after_transient_403(monkeypatch) -> None:
    """The common-case happy path: WAF burst fires on the first attempt,
    clears within the 30s backoff window, and the second attempt
    succeeds. The helper must return the success value, not the 403."""

    class SDMXForbiddenError(Exception):
        pass

    call_count = [0]

    def fn() -> str:
        call_count[0] += 1
        if call_count[0] == 1:
            raise SDMXForbiddenError("Access Denied (403): transient burst")
        return "success-on-retry"

    monkeypatch.setattr(server._time, "sleep", lambda s: None)

    with patch.dict(os.environ, {server._RETRY_403_ENV: "1"}):
        result = server._call_sdmx(fn)

    assert result == "success-on-retry"
    assert call_count[0] == 2


def test_call_sdmx_with_retry_403_does_not_retry_non_403_errors(monkeypatch) -> None:
    """The 403-specific retry path MUST NOT engage on other errors —
    they should be re-raised exactly as before, after the inner _retry's
    handling of transient network errors."""

    def fn() -> int:
        raise ValueError("not a 403")

    monkeypatch.setattr(server._time, "sleep", lambda s: None)

    with (
        patch.dict(os.environ, {server._RETRY_403_ENV: "1"}),
        pytest.raises(ValueError, match="not a 403"),
    ):
        server._call_sdmx(fn)
