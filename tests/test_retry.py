"""Tests for the _retry helper and _is_client_error heuristic.

Added in v0.7.3 — the v0.7.1 substring matching against `str(exc).lower()` for
"404" / "not found" had two latent bugs: (a) `"4040"` in a 5xx response body
matched `"404"`, and (b) `if attempt < max_attempts - 1` left a `raise last_exc`
fall-through where `last_exc` could in principle be None on `max_attempts == 0`.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from unicefstats_mcp.server import _is_client_error, _looks_not_found, _retry


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

    def test_structured_429_is_not_client_error(self):
        # 429 Too Many Requests is transient by definition — the correct
        # response is retry-with-backoff, so it must NOT short-circuit as a
        # client error. Pre-fix, the structured path treated all 4xx as
        # non-retryable while the text-fallback regex (which omits 429)
        # would have retried the same error arriving as message text.
        assert _is_client_error(_StatusError("too many requests", 429)) is False

    def test_structured_408_is_not_client_error(self):
        # 408 Request Timeout: same reasoning as 429.
        assert _is_client_error(_StatusError("request timeout", 408)) is False

    def test_text_429_is_not_client_error(self):
        # Consistency with the structured path: "429" as message text should
        # also be retryable (the regex deliberately omits it).
        assert _is_client_error(RuntimeError("429 Too Many Requests for url")) is False

    def test_structured_429_with_4xx_like_number_in_message_still_retries(self):
        # Structured status must be authoritative. Pre-fix, a structured 429
        # fell through to the text regex, so an unrelated "400" in the message
        # (here a retry-after hint) classified it as a client error and
        # `_retry` aborted after one attempt instead of backing off.
        assert _is_client_error(
            _StatusError("429 Too Many Requests; retry after 400 seconds", 429)
        ) is False

    def test_structured_408_with_404_in_url_still_retries(self):
        assert _is_client_error(
            _StatusError("408 Request Timeout for url: https://sdmx.example/data/404", 408)
        ) is False

    def test_structured_5xx_with_404_in_url_is_not_client_error(self):
        # A 502 whose diagnostic URL happens to end in "/404" is still a
        # server error and must consume retry budget.
        assert _is_client_error(
            _StatusError("502 Bad Gateway for url: https://sdmx.example/rest/data/404", 502)
        ) is False

    def test_structured_5xx_with_not_found_phrase_is_not_client_error(self):
        assert _is_client_error(
            _StatusError("503 upstream not found in pool", 503)
        ) is False

    def test_403_access_denied_phrase_is_client_error(self):
        # Same incident, the unicefdata library wraps the upstream 403 as a
        # second message variant: `Access Denied (403): You do not have
        # permission to access 'CME_MRY0T4'.`
        assert _is_client_error(
            RuntimeError("Access Denied (403): You do not have permission to access 'CME_MRY0T4'")
        ) is True


class TestLooksNotFound:
    """`_looks_not_found` gates `get_data`'s authoritative no_data envelope —
    the response that instructs the model the warehouse "confirmed this data
    does not exist". It must therefore be word-bounded: the v0.7.1 substring
    bug (`"404" in str(exc)` matching "4040") was fixed in `_is_client_error`
    in v0.7.3 but survived in the no_data classifier until this helper."""

    def test_structured_404(self):
        assert _looks_not_found(_StatusError("nope", 404)) is True

    def test_word_bounded_404_in_text(self):
        assert _looks_not_found(RuntimeError("HTTP 404 Not Found")) is True

    def test_4040_in_text_is_not_not_found(self):
        # A transient 5xx whose body mentions "4040" must never be presented
        # to the model as an authoritative absence-of-data verdict.
        assert _looks_not_found(
            RuntimeError("upstream returned 4040 chars of HTML")
        ) is False

    def test_structured_500_is_not_not_found(self):
        assert _looks_not_found(_StatusError("server boom", 500)) is False

    def test_structured_502_with_404_in_url_is_not_not_found(self):
        # Structured status is authoritative: a 502 whose diagnostic URL ends
        # in "/404" is a server failure, and must never trigger the
        # authoritative no_data envelope. Pre-fix the text regex matched.
        assert _looks_not_found(
            _StatusError("502 Bad Gateway for url: https://sdmx.example/rest/data/404", 502)
        ) is False

    def test_structured_503_with_not_found_phrase_is_not_not_found(self):
        assert _looks_not_found(
            _StatusError("503 Service Unavailable: backend not found in pool", 503)
        ) is False

    def test_structured_404_with_misleading_text_is_not_found(self):
        # And the converse: a structured 404 is not-found regardless of text.
        assert _looks_not_found(_StatusError("upstream error 500", 404)) is True

    def test_cascade_end_message_is_not_found(self):
        # unicefdata's cascade-end exception (lowercase "not found").
        assert _looks_not_found(
            RuntimeError("Indicator 'NT_ANT_HAZ_NE2' not found in any dataflow.")
        ) is True

    def test_does_not_exist_phrase(self):
        assert _looks_not_found(RuntimeError("Indicator FOO does not exist")) is True


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

    def test_retries_on_structured_429_then_succeeds(self):
        # A rate-limit response must consume backoff budget, not abort.
        calls = {"n": 0}

        def fn():
            calls["n"] += 1
            if calls["n"] == 1:
                raise _StatusError("too many requests", 429)
            return "ok"

        with patch("unicefstats_mcp.server._time.sleep") as sleep_mock:
            assert _retry(fn, base_delay=0.0) == "ok"
        assert calls["n"] == 2
        assert sleep_mock.call_count == 1

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
