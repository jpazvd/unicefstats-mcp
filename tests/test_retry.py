"""Tests for the _retry helper and _is_client_error heuristic.

Added in v0.7.3 — the v0.7.1 substring matching against `str(exc).lower()` for
"404" / "not found" had two latent bugs: (a) `"4040"` in a 5xx response body
matched `"404"`, and (b) `if attempt < max_attempts - 1` left a `raise last_exc`
fall-through where `last_exc` could in principle be None on `max_attempts == 0`.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from unicefstats_mcp.server import _is_client_error, _retry


class _FakeResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code


class _StatusError(Exception):
    """Mimics requests-style exceptions that carry a .response.status_code."""

    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.response = _FakeResponse(status_code)


class TestIsClientError:
    def test_404_via_response_status(self):
        assert _is_client_error(_StatusError("nope", 404)) is True

    def test_500_via_response_status_is_not_client_error(self):
        assert _is_client_error(_StatusError("server boom", 500)) is False

    def test_404_via_word_bounded_substring(self):
        assert _is_client_error(RuntimeError("HTTP 404 Not Found")) is True

    def test_4040_in_message_is_not_client_error(self):
        # The v0.7.1 bug: substring "404" matched "4040" in a 5xx body.
        # Word-bounded match must not flag this.
        assert _is_client_error(RuntimeError("upstream returned status 4040")) is False

    def test_not_found_phrase_is_client_error(self):
        assert _is_client_error(RuntimeError("Indicator FOO does not exist")) is True

    def test_network_timeout_is_not_client_error(self):
        assert _is_client_error(TimeoutError("read timeout after 30s")) is False

    def test_403_via_word_bounded_substring(self):
        # Observed live during the 2026-05-09 v0.7.3 validation run: AWS ELB
        # in front of UNICEF SDMX returned `403 Forbidden` once cumulative
        # tool-call rate from the n=500 batch tripped abuse detection.
        # `unicefdata` raised it as `RuntimeError('403 Client Error: Forbidden
        # for url: ...')`. Must classify as client error so we don't waste the
        # exponential-backoff budget on a request that won't recover within
        # our retry window.
        assert _is_client_error(
            RuntimeError("403 Client Error: Forbidden for url: https://sdmx...")
        ) is True

    def test_403_access_denied_phrase_is_client_error(self):
        # Same incident, the unicefdata library wraps the upstream 403 as a
        # second message variant: `Access Denied (403): You do not have
        # permission to access 'CME_MRY0T4'.`
        assert _is_client_error(
            RuntimeError("Access Denied (403): You do not have permission to access 'CME_MRY0T4'")
        ) is True


class TestRetry:
    def test_returns_immediately_on_success(self):
        calls = {"n": 0}

        def fn():
            calls["n"] += 1
            return "ok"

        assert _retry(fn) == "ok"
        assert calls["n"] == 1

    def test_retries_on_transient_then_succeeds(self):
        calls = {"n": 0}

        def fn():
            calls["n"] += 1
            if calls["n"] < 3:
                raise RuntimeError("connection reset")
            return "ok"

        with patch("unicefstats_mcp.server._time.sleep") as sleep_mock:
            assert _retry(fn, base_delay=0.0) == "ok"
        assert calls["n"] == 3
        assert sleep_mock.call_count == 2  # slept between attempts 1→2 and 2→3

    def test_does_not_retry_on_client_error(self):
        calls = {"n": 0}

        def fn():
            calls["n"] += 1
            raise _StatusError("indicator not found", 404)

        with (
            patch("unicefstats_mcp.server._time.sleep") as sleep_mock,
            pytest.raises(_StatusError),
        ):
            _retry(fn)
        assert calls["n"] == 1
        sleep_mock.assert_not_called()

    def test_does_not_retry_when_message_contains_4040(self):
        # Regression: 4040 in a 5xx body must not be treated as 404.
        calls = {"n": 0}

        def fn():
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("upstream returned status 4040 chars of HTML")
            return "ok"

        with patch("unicefstats_mcp.server._time.sleep"):
            assert _retry(fn, base_delay=0.0) == "ok"
        assert calls["n"] == 2

    def test_raises_last_exc_after_exhausting_retries(self):
        def fn():
            raise RuntimeError("persistent transient")

        with (
            patch("unicefstats_mcp.server._time.sleep"),
            pytest.raises(RuntimeError, match="persistent transient"),
        ):
            _retry(fn, max_attempts=2, base_delay=0.0)

    def test_max_attempts_zero_raises_value_error(self):
        with pytest.raises(ValueError, match="max_attempts"):
            _retry(lambda: "never", max_attempts=0)

    def test_log_message_strips_newlines(self, caplog):
        # Log injection guard: an exception message containing newlines must
        # not produce a multi-line log record.
        state = {"n": 0}

        def fn():
            state["n"] += 1
            if state["n"] == 1:
                raise RuntimeError("line1\nFAKE LOG INJECTED\nline3")
            return "ok"

        import logging
        with (
            caplog.at_level(logging.INFO, logger="unicefstats_mcp.server"),
            patch("unicefstats_mcp.server._time.sleep"),
        ):
            _retry(fn, base_delay=0.0)
        # The exception text in the formatted log message must be on one line.
        for record in caplog.records:
            if "Retry" in record.getMessage():
                assert "\n" not in record.getMessage()
