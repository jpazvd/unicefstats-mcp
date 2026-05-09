#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["matplotlib"]
# ///
"""
mcp-figures.py — render a figure per data MCP from a real tool call.

================================================================================
What is this script for?
================================================================================

It is an end-to-end smoke test for five public-data Model Context Protocol
(MCP) servers. For each server it:

    1. Spawns the server as a subprocess.
    2. Speaks the MCP "initialize" handshake over stdin/stdout.
    3. Calls one tool ("tools/call") to fetch a real time series
       (e.g. India under-5 mortality from 1953-2024).
    4. Parses the server's response into (year, value) tuples.
    5. Plots a matplotlib figure of the series and writes it to disk.
    6. Captures the server's identity (name + version) and stamps it on
       the figure footnote, alongside the variable code, a UTC timestamp,
       the host name, and the agent that invoked the run — so the figure
       is self-documenting if it ever surfaces in a deck six months later.

This is *not* a benchmark and there is no LLM in the loop. It exists to
prove that each MCP returns well-formed data when called directly — the
canonical "smoke test" pattern, where you exercise the integration with
real traffic before trusting it in production.

================================================================================
What is MCP, in one paragraph?
================================================================================

The Model Context Protocol (MCP) is a JSON-RPC 2.0 protocol that lets a
"client" (the LLM agent, or this script) talk to a "server" (an external
data/tool provider) over stdin/stdout. The client sends a request like
{"method": "tools/call", "params": {"name": "get_data", "arguments": {...}}}
and the server responds with the result. The whole protocol is just JSON
messages over a pipe — no HTTP, no auth headers, no SDK required. That is
why this entire script is ~900 lines of pure Python with one external
dependency (matplotlib) and yet talks to five different public-data APIs.

================================================================================
What does the script output?
================================================================================

  <output-dir>/mcp-figure-<source>-<indicator>-<countries>-<YYYY-MM-DD>.png
  <output-dir>/mcp-figures-summary-<countries>-<YYYY-MM-DD>.md (run report)

Default <output-dir>: ~/.openclaw/canvas/. Override with --output-dir.

================================================================================
Usage
================================================================================

  uv run --script scripts/mcp-figures.py             # default: U5MR India
  uv run --script scripts/mcp-figures.py --countries IND,KEN
  uv run --script scripts/mcp-figures.py --combined  # also produce overlay
  uv run --script scripts/mcp-figures.py --output-dir examples/mcp-smoke-test/figures
  uv run --script scripts/mcp-figures.py --config /path/to/openclaw.json
  uv run --script scripts/mcp-figures.py --invoked-by "Claude Opus 4.7"

================================================================================
Default indicator: Under-5 mortality across four sources
================================================================================

  - unicefstats:   SDMX code CME_MRY0                       (UNICEF, no key)
  - world-bank:    series SH.DYN.MORT                       (WB Open Data, no key)
  - data360:       WB_WDI/WB_WDI_SH_DYN_MORT                (WB Data360, no key)
  - data-commons:  MortalityRate_Person_Upto5Years          (Google, free key)

fred is queried for UNRATE (US Unemployment Rate) — separate concept,
listed as a parallel demonstration of monthly time-series rendering.
fred needs a free FRED_API_KEY.

================================================================================
File roadmap (follow the section banners as you read)
================================================================================

  1. Imports and constants                          (lines ~40-90)
  2. MCP protocol helpers — speak JSON-RPC          (lines ~95-280)
  3. Per-source response parsers                    (lines ~285-450)
  4. Plotting helpers — matplotlib + footnotes      (lines ~455-625)
  5. main() — orchestrates one fetch+plot per MCP   (lines ~630-end)

================================================================================
"""
from __future__ import annotations  # allow modern type hints on Python 3.10+

# ============================================================================
#  Imports — grouped by purpose so a reader can spot what each block does.
# ============================================================================
# --- standard library ---------------------------------------------------------
import argparse  # parse the command-line flags (--countries, --combined…)
import contextlib  # tiny helper used to suppress benign exceptions cleanly
import csv  # World Bank MCP returns CSV; this reads it
import io  # wraps the CSV string so csv.DictReader can read it
import json  # encode/decode every JSON-RPC message + every parser
import os  # read environment variables, manipulate the env dict
import socket  # socket.gethostname() — hostname for the figure footnote
import subprocess  # spawn each MCP server as a child process
import sys  # exit codes from main()
import time  # poll-loop timing for waiting on server replies
from datetime import date, datetime, timezone  # timestamps + ISO-8601 + filenames
from pathlib import Path  # cleaner OS-portable paths than raw strings
from typing import Any  # used for permissive dict[str, Any] type hints

# --- matplotlib (the only third-party dependency, see PEP 723 header above) ---
import matplotlib

# Force the "Agg" backend BEFORE importing pyplot. Agg writes PNG files
# without ever opening a window — required for headless / CI / SSH runs.
# If you forget this, matplotlib may try to attach to a display and crash
# on machines that don't have one.
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402 — must come after matplotlib.use()

# ============================================================================
#  Constants — where the script reads its config and writes its output.
# ============================================================================

# CONFIG: path to the user's MCP server registry. Each entry says which
# binary to run and which env vars it needs. Default location is the
# OpenClaw convention used across these example scripts; override with
# the --config CLI flag.
CONFIG = Path.home() / ".openclaw" / "openclaw.json"

# CANVAS: default place to drop rendered figures. Each invocation writes
# PNGs and a summary markdown into this directory. Override with
# --output-dir for repo-relative output (e.g. examples/.../figures/).
CANVAS = Path.home() / ".openclaw" / "canvas"


# ============================================================================
#  MCP protocol helpers — speak JSON-RPC over a child process's stdin/stdout.
# ============================================================================
#
# This section is the protocol layer. A reader who has never seen MCP only
# needs to understand:
#
#   1. We launch a server binary as a subprocess (subprocess.Popen).
#   2. We write line-delimited JSON-RPC requests to its stdin.
#   3. We read line-delimited JSON-RPC responses from its stdout.
#   4. The protocol requires three exchanges: initialize → tools/call → done.
#
# Everything below is plumbing for those three exchanges.


def jsonrpc(method: str, msg_id: int, params: dict[str, Any] | None = None) -> bytes:
    """Serialize one JSON-RPC 2.0 request as bytes ready to write to stdin.

    Every JSON-RPC message has three required fields plus optional `params`:

        {"jsonrpc": "2.0", "id": <int>, "method": "<name>", "params": {...}}

    The trailing "\\n" matters: MCP servers are line-buffered — they read
    one message per newline. Forgetting the newline is the most common
    cause of "the server never replies" hangs.

    Args:
        method:  the JSON-RPC method name, e.g. "initialize" or "tools/call".
        msg_id:  any integer; the server echoes it back in its reply so the
                 client can match request ↔ response when calls are async.
                 This script issues calls one at a time so any unique int works.
        params:  the method-specific arguments dict (None for no-arg methods).

    Returns:
        The encoded line ready to feed into proc.stdin.write().
    """
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": msg_id, "method": method}
    if params is not None:
        payload["params"] = params
    return (json.dumps(payload) + "\n").encode()


def read_response(stdout, deadline: float) -> dict[str, Any] | None:
    """Read one JSON-RPC response line from a child's stdout, with a deadline.

    Polls stdout in a tight loop, ignoring blank lines and any non-JSON
    chatter (some MCP servers emit log lines mixed with protocol output).
    The first line that decodes to a JSON object containing an "id" key is
    treated as the response — anything else is skipped.

    Args:
        stdout:    the proc.stdout pipe from subprocess.Popen.
        deadline:  absolute wall-clock time (seconds since epoch) at which
                   to give up. Compare against time.time() each iteration.
                   Caller computes this as `time.time() + timeout`.

    Returns:
        The decoded response dict, or None if the deadline was reached
        before any valid JSON-RPC message arrived.

    Note: a 50ms sleep between empty reads keeps this from busy-looping.
    """
    while True:
        if time.time() > deadline:
            return None
        line = stdout.readline()
        if not line:
            time.sleep(0.05)
            continue
        try:
            decoded = json.loads(line.decode())
        except (UnicodeDecodeError, json.JSONDecodeError):
            # Some servers emit log lines or progress info on stdout
            # alongside protocol messages. Skip anything that isn't valid
            # JSON rather than crash.
            continue
        if isinstance(decoded, dict) and "id" in decoded:
            return decoded


def _detect_invoking_agent() -> str:
    """Best-effort identification of who is running this script.

    Checks well-known env-var signals from common AI dev tools and IDEs.
    Returns a short label; falls back to "shell" if nothing matches.

    Detection is lossy by design — agents don't volunteer model identity
    in env, only their CLI/UI identity. For explicit model labeling
    (e.g. "Claude Opus 4.7"), use --invoked-by on the CLI.
    """
    # Order matters: more specific signals first. CLAUDE_CODE_EXECPATH is
    # set by the Claude Code CLI; CURSOR_* by Cursor; TERM_PROGRAM by
    # Apple Terminal / iTerm / VS Code (covers IDE-launched runs).
    if os.environ.get("CLAUDE_CODE_EXECPATH"):
        return "Claude Code"
    if any(k.startswith("CURSOR_") for k in os.environ):
        return "Cursor"
    term = os.environ.get("TERM_PROGRAM")
    if term:
        # vscode → "VS Code"; iTerm.app → "iTerm"; Apple_Terminal → "Apple Terminal".
        return {"vscode": "VS Code", "Apple_Terminal": "Apple Terminal"}.get(term, term)
    if os.environ.get("CODESPACES") == "true":
        return "GitHub Codespaces"
    return "shell"


def _sanitize_for_markdown(text: str, *, max_len: int = 120) -> str:
    """Strip characters that could escape markdown code-spans or inject HTML.

    The `invoked_by` label flows from a user-controlled CLI argument
    into a markdown report that GitHub may render. The label is
    enclosed in backtick code-spans (e.g. `` `Claude Opus 4.7` ``) and
    in a single-line italicised footnote on the figure. A backtick or
    angle-bracket in the label would break the code-span boundary and
    resume markdown / HTML parsing — low-blast-radius (operator runs
    the script themselves) but trivial to harden.

    Sanitisation strategy: keep alphanumerics, whitespace, and a small
    safelist of punctuation that's harmless in code-spans
    (`. _ - ( ) /`). Drop everything else. Truncate to `max_len`
    characters as a belt-and-braces against pathologically long labels.
    """
    if not text:
        return ""
    safelist = set(" ._-()/")
    cleaned = "".join(c for c in text if c.isalnum() or c in safelist)
    return cleaned[:max_len]


def _provenance_footnote_text(invoked_by: str) -> str:
    """Build the second footnote line: timestamp + host + invoking agent.

    Format: `Generated 2026-05-08T13:45:00Z on <host> via <agent>`.

    The `invoked_by` value is sanitised before insertion — it flows
    from a user-controlled CLI flag (--invoked-by) and we don't want
    backticks, angle-brackets, or newlines to mangle the markdown
    report or the matplotlib text rendering.
    """
    ts = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    host = socket.gethostname()
    return f"Generated {ts} on {host} via {_sanitize_for_markdown(invoked_by)}"


def _format_server_id(info: dict[str, Any] | None) -> str:
    """Render a serverInfo dict as `name v<version>` for display.

    Returns 'unknown' when the server didn't report one (per MCP spec
    serverInfo is optional in the initialize result).
    """
    if not info:
        return "unknown"
    name = info.get("name") or "?"
    version = info.get("version") or "?"
    return f"{name} v{version}"


def fetch(
    server: dict[str, Any],
    call: dict[str, Any],
    *,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """Spawn an MCP server, run the init + one tool call, and return the result.

    This is the **central function** of the protocol layer. Everything else
    in this section feeds into it. The flow is:

      ┌─────────────────────────────────────────────────────────────────┐
      │  1. subprocess.Popen the server binary (its `command` + `args`) │
      │  2. send  → {"method": "initialize", ...}                       │
      │     wait  ← response (extract serverInfo block)                 │
      │  3. send  → {"method": "notifications/initialized"}  (no reply) │
      │  4. send  → {"method": "tools/call", "params": <call>}          │
      │     wait  ← response (extract content[].text)                   │
      │  5. close stdin, let child exit gracefully (kill if it hangs)   │
      └─────────────────────────────────────────────────────────────────┘

    Args:
        server:  one entry from openclaw.json's "servers" map. Looks like
                 {"command": "python", "args": ["-m", "..."], "env": {...}}.
                 The optional "env" dict is merged into os.environ before
                 spawning. Values of the form "${VARNAME}" are expanded
                 from the parent env (a tiny templating convention).
        call:    the JSON-RPC params for the tools/call. Looks like
                 {"name": "get_data", "arguments": {"indicator": "...", ...}}.
        timeout: per-message wall-clock budget in seconds. The init
                 exchange and the tools/call exchange each get the full
                 timeout (so total wait ≤ 2× timeout in the worst case).

    Returns:
        {"text": <str>, "server_info": <dict | None>}
        - text:        the joined "text" content blocks from the tool result.
                       Each per-source parser knows how to interpret this string.
        - server_info: the serverInfo block from the initialize result, e.g.
                       {"name": "unicefstats-mcp", "version": "0.7.1"}.
                       May be None if the server didn't volunteer one.

    Raises:
        RuntimeError: on initialize/call timeout or a JSON-RPC "error" result.
    """
    cmd = [server["command"], *server.get("args", [])]
    env = os.environ.copy()
    for k, v in (server.get("env") or {}).items():
        if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
            env[k] = os.environ.get(v[2:-1], "")
        else:
            env[k] = str(v)

    # stderr=DEVNULL: each MCP server logs init/health/auth chatter to stderr
    # (especially when API keys are missing or upstream is slow). Capturing
    # via PIPE without draining lets a chatty server fill the OS pipe buffer
    # (~64 KB on Linux/Mac, ~4 KB on Windows) and then block — the parent's
    # readline() on stdout would then hang until timeout. We don't surface
    # stderr in the smoke test, so dropping it is the right call.
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=env,
    )
    try:
        proc.stdin.write(
            jsonrpc(
                "initialize",
                1,
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "mcp-figures.py", "version": "0.1"},
                },
            )
        )
        proc.stdin.flush()
        init_resp = read_response(proc.stdout, time.time() + timeout)
        if init_resp is None:
            raise RuntimeError("initialize: no response")
        # serverInfo is optional in the initialize result per MCP spec; pull
        # it out so callers can stamp the figure footnote / summary report.
        server_info = (init_resp.get("result") or {}).get("serverInfo")
        proc.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
        proc.stdin.flush()
        proc.stdin.write(jsonrpc("tools/call", 2, call))
        proc.stdin.flush()
        resp = read_response(proc.stdout, time.time() + timeout)
        if resp is None:
            raise RuntimeError("tools/call: no response within timeout")
        if "error" in resp:
            raise RuntimeError(f"tools/call: {resp['error']}")
        content = resp["result"].get("content", [])
        text_parts = [
            c.get("text", "")
            for c in content
            if isinstance(c, dict) and c.get("type") == "text"
        ]
        return {"text": "\n".join(text_parts), "server_info": server_info}
    finally:
        # stdin may already be closed if the child exited; suppress the
        # secondary exception so the original RuntimeError (if any)
        # propagates cleanly.
        with contextlib.suppress(Exception):
            proc.stdin.close()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()


# ============================================================================
#  Per-source response parsers — one per MCP, all return the same shape.
# ============================================================================
#
# Each MCP server returns its own response format (UNICEF SDMX JSON, World
# Bank CSV, FRED JSON, Data360 SDMX-shaped JSON, Data Commons nested
# byVariable→byEntity envelope). The parsers below normalize all of those
# into one common shape that the plot functions can consume:
#
#     parse_<source>(text) → (label, indicator_name, by_country)
#
#     where:
#         label          = e.g. "unicefstats (UNICEF SDMX)" — for legend/title
#         indicator_name = the human-readable indicator (or "?" if unknown)
#         by_country     = {country_id: [(year, value), …]}, sorted by year
#
# parse_fred is the one exception: FRED is monthly time-series so it returns
# (label, indicator_name, [(date_str, value), …]) — a flat list of date-keyed
# pairs rather than country-keyed.
#
# Each parser is defensive: any row missing a country, period, or value is
# skipped silently rather than raising. Real upstream APIs frequently
# include partial / missing-value rows.


def parse_unicefstats(text: str) -> tuple[str, str, dict[str, list[tuple[int, float]]]]:
    """Parse the UNICEF SDMX MCP response.

    Expected response shape (from this repo's get_data tool):

        {
          "indicator": "CME_MRY0",
          "indicator_resolution": {"canonical_name": "Under-five mortality rate"},
          "data": [
            {"country": "India", "period": 2020, "value": 30.5},
            ...
          ]
        }

    The parser prefers `indicator_resolution.canonical_name` (the resolver-
    enriched human-readable name) over the raw `indicator` code if both
    are present.
    """
    obj = json.loads(text)
    indicator = obj.get("indicator_resolution", {}).get("canonical_name") or obj.get("indicator")
    by_country: dict[str, list[tuple[int, float]]] = {}
    for row in obj.get("data", []):
        country = row.get("country") or row.get("iso3")
        period = row.get("period")
        value = row.get("value")
        if country is None or period is None or value is None:
            continue
        try:
            year = int(period)
        except (TypeError, ValueError):
            continue
        try:
            v = float(value)
        except (TypeError, ValueError):
            continue
        by_country.setdefault(country, []).append((year, v))
    for v in by_country.values():
        v.sort()
    return ("unicefstats (UNICEF SDMX)", indicator or "?", by_country)


def parse_world_bank(text: str) -> tuple[str, str, dict[str, list[tuple[int, float]]]]:
    """Parse the World Bank MCP response (CSV format).

    Expected response shape (CSV with dotted column names, mirroring the
    World Bank Open Data API's flat layout):

        country.value,countryiso3code,date,value,indicator.value
        India,IND,2020,32.5,Mortality rate (per 1000)
        India,IND,2021,30.1,Mortality rate (per 1000)
        ...

    Falls back to `countryiso3code` if `country.value` is blank — useful
    when WB returns ISO3-only rows for some indicators.
    """
    rdr = csv.DictReader(io.StringIO(text))
    by_country: dict[str, list[tuple[int, float]]] = {}
    indicator_name = "?"
    for row in rdr:
        if not row:
            continue
        date_str = (row.get("date") or "").strip()
        value_str = (row.get("value") or "").strip()
        country = (row.get("country.value") or row.get("countryiso3code") or "").strip()
        ind_label = (row.get("indicator.value") or "").strip()
        if ind_label and indicator_name == "?":
            indicator_name = ind_label
        if not date_str or not value_str or not country:
            continue
        try:
            year = int(date_str)
            v = float(value_str)
        except ValueError:
            continue
        by_country.setdefault(country, []).append((year, v))
    for v in by_country.values():
        v.sort()
    return ("world-bank (WB API)", indicator_name, by_country)


def parse_data360(text: str) -> tuple[str, str, dict[str, list[tuple[int, float]]]]:
    """Parse the World Bank Data360 MCP response (SDMX-shaped JSON).

    Expected response shape (SDMX flat-row JSON with capital-letter keys
    matching the SDMX data structure definition):

        {
          "data": [
            {"REF_AREA": "IND", "TIME_PERIOD": "2020", "OBS_VALUE": 32.5,
             "INDICATOR": "WB_WDI_SH_DYN_MORT"},
            ...
          ]
        }

    TIME_PERIOD may be annual ("2020"), quarterly ("2020-Q1"), or full ISO
    date — the parser keeps only the year by taking the first 4 chars.
    Some variants use "TIME" or "PERIOD" instead of "TIME_PERIOD".
    """
    obj = json.loads(text)
    rows = obj.get("data", []) or []
    by_country: dict[str, list[tuple[int, float]]] = {}
    indicator = "?"
    for row in rows:
        country = row.get("REF_AREA")
        period = row.get("TIME_PERIOD") or row.get("TIME") or row.get("PERIOD")
        value = row.get("OBS_VALUE")
        if country is None or period is None or value is None:
            continue
        # TIME_PERIOD may be "2020", "2020-Q1", or full date — extract year
        try:
            year = int(str(period)[:4])
        except (TypeError, ValueError):
            continue
        try:
            v = float(value)
        except (TypeError, ValueError):
            continue
        by_country.setdefault(country, []).append((year, v))
        if indicator == "?":
            indicator = row.get("INDICATOR", indicator)
    for v in by_country.values():
        v.sort()
    return ("data360 (World Bank Data360)", indicator, by_country)


def parse_data_commons(text: str) -> tuple[str, str, dict[str, list[tuple[int, float]]]]:
    """Google Data Commons MCP returns the REST v2 observation envelope:

        {
          "byVariable": {
            "<variable_dcid>": {
              "byEntity": {
                "<entity_dcid>": {
                  "orderedFacets": [
                    {"observations": [{"date": "2023", "value": 40097761}], ...}
                  ]
                }
              }
            }
          },
          "facets": {...}
        }

    We flatten across `orderedFacets` (multiple facets = multiple sources
    for the same variable) and aggregate observations per entity. Entity
    DCIDs like ``country/IND`` are stripped to the ISO3 suffix (``IND``)
    so the country axis lines up with the other sources in the combined
    overlay.
    """
    obj = json.loads(text)
    by_variable = obj.get("byVariable", {}) or {}
    if not by_variable:
        return ("data-commons (Google Data Commons)", "?", {})

    # Take the first variable in the response (smoke test queries one at a time).
    var_dcid, var_block = next(iter(by_variable.items()))
    by_entity = (var_block or {}).get("byEntity", {}) or {}

    by_country: dict[str, list[tuple[int, float]]] = {}
    for entity_dcid, entity_block in by_entity.items():
        # Strip "country/" prefix so "country/IND" → "IND" for axis alignment.
        country = entity_dcid.split("/", 1)[1] if "/" in entity_dcid else entity_dcid
        for facet in (entity_block or {}).get("orderedFacets", []) or []:
            for ob in facet.get("observations", []) or []:
                date_str = ob.get("date")
                value = ob.get("value")
                if date_str is None or value is None:
                    continue
                try:
                    # Date may be "YYYY", "YYYY-MM", or full ISO — first 4 chars.
                    year = int(str(date_str)[:4])
                except (TypeError, ValueError):
                    continue
                try:
                    v = float(value)
                except (TypeError, ValueError):
                    continue
                by_country.setdefault(country, []).append((year, v))
    for v in by_country.values():
        v.sort()
    return ("data-commons (Google Data Commons)", var_dcid, by_country)


def parse_fred(text: str) -> tuple[str, str, list[tuple[str, float]]]:
    """Parse the FRED MCP response (Federal Reserve Economic Data, JSON).

    Expected response shape:

        {
          "title": "Unemployment Rate",
          "units": "Percent",
          "series_id": "UNRATE",
          "data": [
            {"date": "2020-01-01", "value": 3.5},
            {"date": "2020-04-01", "value": 14.7},
            ...
          ]
        }

    FRED data is **monthly** (date keyed, not year-keyed) and **single
    series** (no country axis). For these reasons it returns a flat list
    of (date_string, value) tuples instead of the per-country dict the
    other parsers return — and is plotted by `plot_fred_series` rather
    than `plot_one`.

    Dates are kept as YYYY-MM-DD strings so matplotlib's date axis can
    parse them directly.
    """
    obj = json.loads(text)
    title = obj.get("title") or obj.get("series_id") or "?"
    units = obj.get("units")
    if units:
        title = f"{title} ({units})"
    series: list[tuple[str, float]] = []
    for row in obj.get("data", []):
        date_str = row.get("date")
        value = row.get("value")
        if date_str is None or value is None:
            continue
        try:
            v = float(value)
        except (TypeError, ValueError):
            continue
        series.append((str(date_str), v))
    series.sort()
    return ("fred (Federal Reserve)", title, series)


# ============================================================================
#  Plotting helpers — render parsed data to PNG with provenance footnote.
# ============================================================================
#
# Three top-level plot functions:
#
#   plot_one          — yearly per-country panel (most common)
#   plot_fred_series  — monthly single-series with COVID shading (fred)
#   plot_combined     — overlay across multiple sources, source-disagreement
#
# All three render two lines of metadata at the bottom-right (the
# "footnote"):
#
#   Variable code: <CODE>  |  Source: <name> v<version>
#   Generated <UTC ts> on <host> via <agent>
#
# That makes the figure self-documenting if it surfaces in a deck six
# months from now: a viewer can answer (a) what data, (b) which server
# version, (c) when it was rendered, (d) where, (e) by whom.


COLORS = {"India": "#E69F00", "Kenya": "#56B4E9", "Brazil": "#009E73", "Nigeria": "#CC79A7"}


def _code_footnote(
    fig,
    code: str | None,
    server_info: dict | None = None,
    invoked_by: str | None = None,
) -> None:
    """Emit a two-line provenance footnote at the bottom-right.

    Line 1: `Variable code: <code>  |  Source: <name> v<version>` —
            what data was queried and from which MCP server version.
    Line 2: `Generated <UTC ISO timestamp> on <host> via <agent>` —
            when, where, and by whom (Claude Code / Cursor / shell / …).

    Both lines together are sufficient to retrace any figure: data
    provenance (what + which server) and execution provenance (when +
    where + who). Useful when a figure surfaces in a deck six months
    later and someone asks "where did this come from?".
    """
    data_parts: list[str] = []
    if code:
        data_parts.append(f"Variable code: {code}")
    if server_info:
        data_parts.append(f"Source: {_format_server_id(server_info)}")

    invoked_by = invoked_by or _detect_invoking_agent()
    prov_line = _provenance_footnote_text(invoked_by)

    if data_parts:
        fig.text(
            0.99, 0.025, "  |  ".join(data_parts),
            ha="right", va="bottom",
            fontsize=8, color="#555555", style="italic",
        )
    fig.text(
        0.99, 0.005, prov_line,
        ha="right", va="bottom",
        fontsize=7, color="#888888", style="italic",
    )


def plot_one(
    label: str,
    indicator: str,
    by_country: dict[str, list[tuple[int, float]]],
    out_path: Path,
    *,
    code: str | None = None,
    server_info: dict | None = None,
    invoked_by: str | None = None,
) -> None:
    """Render the standard yearly per-country line panel.

    One line per country, all sharing one Y-axis (the indicator's unit).
    Used by all sources except FRED (which is monthly and uses
    plot_fred_series instead).

    Args:
        label:       legend / title source label, e.g. "unicefstats (UNICEF SDMX)".
        indicator:   human-readable indicator name (Y-axis label + title).
        by_country:  parser output — {"India": [(2020, 32.5), ...], ...}.
        out_path:    PNG file to write.
        code:        the *code* that was queried (CME_MRY0 etc.) — drives
                     the figure footnote so it's discoverable from the PNG.
        server_info: serverInfo dict from the MCP initialize response.
        invoked_by:  agent label for the provenance footnote line. None →
                     env-detected via _detect_invoking_agent().
    """
    fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
    for country, series in sorted(by_country.items()):
        if not series:
            continue
        years, values = zip(*series, strict=True)
        ax.plot(
            years,
            values,
            marker="o",
            markersize=2.5,
            linewidth=1.6,
            label=f"{country} (n={len(series)})",
            color=COLORS.get(country),
        )
    ax.set_xlabel("Year")
    ax.set_ylabel(indicator)
    ax.set_title(f"{indicator}\n{label}", fontsize=11)
    ax.grid(True, alpha=0.3, linestyle="--")
    ax.legend(loc="best", fontsize=9)
    _code_footnote(fig, code, server_info, invoked_by=invoked_by)
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def plot_fred_series(
    label: str,
    indicator: str,
    series: list[tuple[str, float]],
    out_path: Path,
    *,
    code: str | None = None,
    server_info: dict | None = None,
    invoked_by: str | None = None,
) -> None:
    """Render a FRED-style monthly time series with COVID shading.

    FRED data is **monthly** (date strings, not annual) and **single-
    series** (no country axis), so the layout differs from plot_one. We
    also add a grey vertical band over the WHO COVID-19 pandemic window
    (Mar 2020 – May 2021) with an in-figure annotation, because that
    period dominates the unemployment-rate visualization.

    Args:
        series:  flat list of (YYYY-MM-DD, value) tuples from parse_fred.
        (other args identical to plot_one — see its docstring).
    """
    if not series:
        return
    from datetime import datetime as _dt

    dates = [_dt.strptime(d, "%Y-%m-%d") for d, _ in series]
    values = [v for _, v in series]

    fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
    ax.plot(dates, values, linewidth=1.4, color="#0072B2", label=f"n={len(series)}")
    # Shade the broader US COVID-19 pandemic period: from the WHO pandemic
    # declaration (2020-03-11) through end of May 2021, by which point widespread
    # adult vaccine eligibility ended the strictest restrictions in most states.
    # Drawn before legend/grid so the band sits behind the line.
    covid_start = _dt(2020, 3, 1)
    covid_end = _dt(2021, 5, 31)
    if dates and dates[0] <= covid_end and dates[-1] >= covid_start:
        ax.axvspan(
            covid_start,
            covid_end,
            color="#888888",
            alpha=0.25,
            label="WHO COVID-19 pandemic (Mar 2020 – May 2021)",
        )
        # In-figure annotation pointing at the band so the meaning is obvious
        # without the legend.
        mid = covid_start + (covid_end - covid_start) / 2
        y_max = max(values)
        y_top = y_max * 0.95
        ax.annotate(
            "WHO COVID-19 pandemic\n(11 Mar 2020 declaration —\n"
            "widespread vaccine eligibility,\nend of May 2021)",
            xy=(mid, y_top * 0.7),
            xytext=(_dt(2010, 1, 1), y_top),
            fontsize=8,
            color="#333333",
            ha="left",
            va="top",
            arrowprops=dict(arrowstyle="->", color="#555555", lw=0.8),
        )
    ax.set_xlabel("Date")
    ax.set_ylabel(indicator)
    ax.set_title(f"{indicator}\n{label}", fontsize=11)
    ax.grid(True, alpha=0.3, linestyle="--")
    ax.legend(loc="best", fontsize=9)
    _code_footnote(fig, code, server_info, invoked_by=invoked_by)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def plot_combined(
    panels: list[dict],
    out_path: Path,
    *,
    countries: list[str] | None = None,
    invoked_by: str | None = None,
) -> None:
    """Overlay multiple sources on one figure to show source-disagreement.

    Each MCP that successfully returned data is appended to a `panels`
    list during the main loop. This function plots all of them on one
    pair of axes so the viewer can see at a glance whether different
    sources agree on the same indicator (they often don't — see the
    UNICEF/WB labeling drift documented in README).

    Each panel is a dict with these keys:

        {
          "label":       "<source label>",            # legend prefix
          "indicator":   "<human-readable name>",     # informational
          "code":        "<source-specific code>",    # for footnote
          "by_country":  {"India": [(2020, 30.5), ...], ...},
          "server_info": {"name": "...", "version": "..."} | None,
        }

    The combined footnote lists code + server identity per panel
    (e.g. `unicefstats=CME_MRY0 (unicefstats-mcp v0.7.1) | world-bank=…`)
    so a reader can attribute any disagreement back to the right server.
    """
    fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
    for panel in panels:
        for country, series in sorted(panel["by_country"].items()):
            if not series:
                continue
            years, values = zip(*series, strict=True)
            ax.plot(
                years,
                values,
                marker="o",
                markersize=2.5,
                linewidth=1.4,
                label=f"{panel['label']} — {country}",
                alpha=0.85,
            )
    ax.set_xlabel("Year")
    ax.set_ylabel("Indicator value")
    title_countries = ", ".join(countries) if countries else "(unspecified)"
    ax.set_title(
        f"MCP source comparison: Under-5 / Infant mortality, {title_countries}",
        fontsize=11,
    )
    ax.grid(True, alpha=0.3, linestyle="--")
    ax.legend(loc="best", fontsize=9)
    # Combined footnote: line 1 = code+server identity per panel,
    # line 2 = run provenance (timestamp + host + invoking agent).
    footnote_lines: list[str] = []
    for p in panels:
        if not p.get("code"):
            continue
        src_label = p["label"].split(" ")[0]
        sid = _format_server_id(p.get("server_info"))
        footnote_lines.append(f"{src_label}={p['code']} ({sid})")
    if footnote_lines:
        fig.text(
            0.99, 0.025, "Sources: " + " | ".join(footnote_lines),
            ha="right", va="bottom",
            fontsize=7, color="#555555", style="italic",
        )
    invoked_by = invoked_by or _detect_invoking_agent()
    fig.text(
        0.99, 0.005, _provenance_footnote_text(invoked_by),
        ha="right", va="bottom",
        fontsize=7, color="#888888", style="italic",
    )
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


# ============================================================================
#  Edge-case demonstrations — what unicefstats-mcp can and CANNOT solve.
# ============================================================================
#
# This section answers a recurring stakeholder question:
#
#   "If I just ask the MCP for 'under-5 mortality', does it give me the right
#    number? Or are there semantic-confusion edge cases the MCP can't solve?"
#
# Short answer: the MCP solves *most* cases via the v0.7.x indicator
# resolver (synonym table + refuse-with-disambiguation), but five
# classes of failure remain. Each one below is demonstrated by a real
# MCP call (no shortcuts to internal Python imports), with comments
# explaining (a) what the MCP does, (b) why it fails, (c) what would
# fix it (or why nothing inside the MCP can).
#
# Trigger this section with `--edge-cases` on the command line; it runs
# AFTER the figure rendering loop so a normal run is unaffected. Output
# goes to stdout AND a markdown report alongside the figures, so the
# findings persist past the terminal session.
#
# Why these are useful: an LLM agent calling MCPs naively will hit these
# edge cases in the wild. The smoke test surfaces them deliberately so
# anyone reading the example knows what to watch for.


# Test cases. Each tuple = (label, query_string, expected_outcome, why).
# Full explanations live in demonstrate_edge_cases() below; the tuple is
# just the data so the function logic stays compact.
EDGE_CASES: list[dict[str, Any]] = [
    {
        "id": 1,
        "label": "Synonym-table gap (hyphen variant)",
        "tool": "get_data",
        "args": {"indicator": "under-5 mortality", "countries": ["IND"]},
        "expected": "FAIL — 'under-5 mortality' (with hyphen) isn't in the synonym table",
    },
    {
        "id": 2,
        "label": "Code prefix is misleading (CME family contains both IMR and U5MR)",
        "tool": "get_data",
        "args": {"indicator": "CME_MRY0", "countries": ["IND"]},
        "expected": (
            "PASS technically — but the value is IMR (0-1 yr), "
            "NOT U5MR, despite the 'CME' prefix"
        ),
    },
    {
        "id": 3,
        "label": "Refuse-with-disambiguation (the MCP doing well)",
        "tool": "get_data",
        "args": {"indicator": "child mortality", "countries": ["IND"]},
        "expected": "REFUSE — server returns ambiguity error listing NMR/IMR/U5MR/MR1T4 candidates",
    },
    {
        "id": 4,
        "label": "Cross-provider taxonomy mismatch (no MCP can fix)",
        "tool": "get_data",  # we just call ours; the comparison is conceptual
        "args": {
            "indicator": "MortalityRate_Person_Upto5Years",
            "countries": ["IND"],
        },
        "expected": (
            "FAIL — Data Commons code passed to UNICEF MCP; "
            "each provider has its own taxonomy"
        ),
    },
    {
        "id": 5,
        "label": "search_indicators bypass — agent picks wrong code from list",
        "tool": "search_indicators",
        "args": {"query": "mortality"},
        "expected": (
            "AMBIGUOUS — returns multiple results; agent must "
            "disambiguate without the resolver's help"
        ),
    },
]


def _record_outcome(
    case: dict[str, Any], call_result: dict[str, Any] | None, error: Exception | None,
) -> dict[str, Any]:
    """Format one edge-case attempt as a record for the markdown report.

    The record includes: the case metadata, what was actually returned by
    the MCP server (or the error if it raised), and a short verdict.
    """
    record = dict(case)
    if error is not None:
        record["actual"] = f"Exception: {type(error).__name__}: {error}"
        record["text"] = ""
    elif call_result is None:
        record["actual"] = "no response"
        record["text"] = ""
    else:
        text = call_result.get("text", "")
        # Truncate to keep the report readable; full payload is in the log.
        record["text"] = text[:600] + ("..." if len(text) > 600 else "")
        record["actual"] = "see Response below"
        record["server_info"] = call_result.get("server_info")
    return record


def demonstrate_edge_cases(
    server_cfg: dict[str, Any],
    out_dir: Path,
    today: str,
    invoked_by: str,
) -> Path:
    """Run the EDGE_CASES battery against unicefstats-mcp and write a report.

    Calls each test case via the SAME `fetch()` path the figure rendering
    uses — i.e. it speaks JSON-RPC to a freshly-spawned server, no
    internal-Python shortcuts. Captures the response (or exception) and
    writes a markdown report at:

        <out_dir>/mcp-edge-cases-<YYYY-MM-DD>.md

    The function is deliberately verbose with section comments below
    because the report's audience is "someone who just learned what MCP
    is and is wondering whether they can trust it for their work" —
    each case includes the fix path (or the explanation of why no fix
    inside the MCP layer is possible).

    Args:
        server_cfg:  one entry from openclaw.json — typically the
                     "unicefstats" server config. All cases run against
                     this single server (the resolver lives there).
        out_dir:     directory to write the markdown report.
        today:       date string for the filename (YYYY-MM-DD).
        invoked_by:  agent label for the report header.

    Returns:
        Path to the markdown report.
    """
    print()
    print("=" * 78)
    print("  Edge-case demonstration — what the MCP can and CANNOT solve")
    print("=" * 78)

    records: list[dict[str, Any]] = []
    for case in EDGE_CASES:
        print(f"\n[case {case['id']}] {case['label']}")
        print(f"  call:     {case['tool']}({case['args']})")
        print(f"  expected: {case['expected']}")
        try:
            result = fetch(
                server_cfg,
                {"name": case["tool"], "arguments": case["args"]},
                timeout=60.0,
            )
            err: Exception | None = None
        except Exception as e:  # noqa: BLE001 — broad-but-logged
            result = None
            err = e
        rec = _record_outcome(case, result, err)
        records.append(rec)
        # Show the first ~200 chars of whatever came back so the operator
        # sees outcome immediately, not just at the end.
        preview = (rec.get("text") or rec.get("actual") or "")[:200].replace("\n", " ")
        print(f"  actual:   {preview}")

    # ---- Markdown report ---------------------------------------------------
    # The five edge cases below each get a section in the report. The
    # narrative (why, fix path) is hardcoded here rather than parsed from
    # the response — these are diagnostic explanations, not data.
    report_path = out_dir / f"mcp-edge-cases-{today}.md"
    ts = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    host = socket.gethostname()
    with report_path.open("w", encoding="utf-8") as f:
        f.write("# MCP edge cases — what the unicefstats-mcp resolver can ")
        f.write("and CANNOT solve\n\n")
        f.write(f"- Generated: `{ts}` on `{host}`\n")
        f.write(f"- Invoked by: `{invoked_by}`\n")
        f.write("- Source: `examples/mcp-smoke-test/mcp-figures.py --edge-cases`\n")
        f.write("\n")
        f.write(
            "Each case below sends a real `tools/call` request through the same "
            "JSON-RPC stdio path the figure rendering uses — no shortcuts to "
            "internal Python imports. The intent is to make the MCP's failure "
            "modes empirically visible: an LLM agent calling these MCPs naively "
            "will hit each case in the wild.\n\n"
        )

        # ====================================================================
        # Case 1: Synonym-table gap
        # ====================================================================
        # The v0.7.x resolver maintains a hand-curated `_SYNONYMS` table
        # mapping common phrasings to indicator codes. It covers
        # "under five mortality" → CME_MRY0T4, but NOT "under-5 mortality"
        # (with hyphen). When the agent uses an unanticipated phrasing,
        # the resolver returns "unknown" and the input passes through to
        # SDMX which 404s.
        #
        # Why MCP can't fully solve this: synonym tables are inherently
        # incomplete. New queries phrase concepts in ways the table author
        # didn't anticipate. Fix path: synonym mining from real query logs
        # (parking-lot item 3), Levenshtein/fuzzy matching, or LLM-assisted
        # query normalisation upstream of the MCP.
        f.write("## Case 1 — Synonym-table gap (the table is hand-curated)\n\n")
        f.write(f"- **Tried:** `{records[0]['tool']}({records[0]['args']})`\n")
        f.write(f"- **Expected:** {records[0]['expected']}\n")
        f.write(f"- **Got:** `{records[0]['actual']}`\n")
        if records[0].get("text"):
            f.write(f"- **Response (truncated):**\n\n```\n{records[0]['text']}\n```\n")
        f.write("\n**Why it fails:** The resolver's `_SYNONYMS` table covers ")
        f.write("`'under five mortality' → CME_MRY0T4`, but the hyphen variant ")
        f.write("`'under-5 mortality'` isn't a key in the table after normalisation, ")
        f.write("so the resolver returns `unknown`.\n\n")
        f.write("**MCP-level mitigations that exist:** the resolver does normalise ")
        f.write("case and whitespace, and refuses-with-list when a query matches ")
        f.write("multiple candidates (see Case 3 below).\n\n")
        f.write("**MCP-level mitigations that don't exist (yet):** fuzzy matching, ")
        f.write("synonym-table mining from query logs (parking-lot item 3), or LLM-")
        f.write("assisted normalisation upstream of the MCP.\n\n---\n\n")

        # ====================================================================
        # Case 2: Code prefix is misleading
        # ====================================================================
        # UNICEF's "Child Mortality Estimates" (CME_) prefix is misleading:
        # CME_MRY0 is specifically Infant mortality rate (0-1 yr), NOT
        # under-5. The MCP returns the correct value but cannot relabel
        # the code — UNICEF themselves return `indicator_name='Infant
        # mortality rate'` for CME_MRY0. The naming is upstream and the
        # MCP is faithful to it.
        #
        # Why MCP can't fully solve this: the MCP wraps the upstream API.
        # If the agent passes a code, the MCP fetches it and returns
        # whatever upstream says. It cannot unilaterally rewrite the
        # indicator's name. The cross-check figure
        # (mcp-figure-crosscheck-IMR-vs-U5MR-IND-*.png) shows this in
        # action: CME_MRY0 line tracks ~30% below CME_MRY0T4, despite
        # both having the misleading "CME" (= Child Mortality Estimates)
        # prefix.
        f.write("## Case 2 — Code prefix is misleading (CME_ ≠ U5MR)\n\n")
        f.write(f"- **Tried:** `{records[1]['tool']}({records[1]['args']})`\n")
        f.write(f"- **Expected:** {records[1]['expected']}\n")
        f.write(f"- **Got:** `{records[1]['actual']}`\n")
        if records[1].get("text"):
            f.write(f"- **Response (truncated):**\n\n```\n{records[1]['text']}\n```\n")
        f.write("\n**Why it's confusing:** UNICEF's *Child Mortality Estimates* ")
        f.write("(CME_) prefix groups four codes — `CME_MRM0` (NMR), `CME_MRY0` ")
        f.write("(IMR), `CME_MRY0T4` (U5MR), `CME_MRY1T4` (1-4 mortality). ")
        f.write("`CME_MRY0` is specifically *infant* mortality despite the ")
        f.write("'child mortality' prefix.\n\n")
        f.write("**Why the MCP can't relabel:** UNICEF's API itself returns ")
        f.write("`indicator_name='Infant mortality rate'` for `CME_MRY0`. The ")
        f.write("MCP wraps upstream faithfully — relabelling would mask drift ")
        f.write("between MCP cache and upstream truth. See ")
        f.write("[CROSS-CHECK-imr-vs-u5mr.md](CROSS-CHECK-imr-vs-u5mr.md) for the ")
        f.write("empirical demonstration.\n\n")
        f.write("**MCP-level mitigation that exists:** the response includes ")
        f.write("`indicator_resolution.canonical_name`, which a careful agent ")
        f.write("can read to verify it got what it asked for.\n\n---\n\n")

        # ====================================================================
        # Case 3: Refuse-with-disambiguation (the GOOD case — MCP doing well)
        # ====================================================================
        # When a query matches multiple synonym candidates ("child mortality"
        # could be NMR, IMR, U5MR, or 1-4), the resolver refuses with the
        # candidate list. This is what the MCP does WELL — surfaces the
        # ambiguity instead of silently picking. Documented here as a "good
        # edge case" so readers see the contrast with the other failures.
        f.write("## Case 3 — Refuse-with-disambiguation (the MCP doing well) ✓\n\n")
        f.write(f"- **Tried:** `{records[2]['tool']}({records[2]['args']})`\n")
        f.write(f"- **Expected:** {records[2]['expected']}\n")
        f.write(f"- **Got:** `{records[2]['actual']}`\n")
        if records[2].get("text"):
            f.write(f"- **Response (truncated):**\n\n```\n{records[2]['text']}\n```\n")
        f.write("\n**Why this works:** The resolver's `_AMBIGUOUS` table maps ")
        f.write("known-confusing terms (`'child mortality'`, `'vaccination'`, ")
        f.write("etc.) to a list of candidate codes. When the agent submits ")
        f.write("such a term, `get_data` returns an error listing the candidates ")
        f.write("instead of silently picking one. This is the v0.7.0 resolver's ")
        f.write("headline contribution.\n\n")
        f.write("**The trade-off:** refuse-with-list trades POS-EQA accuracy ")
        f.write("for hallucination reduction. The clean v0.7.1-vs-v0.6.4 benchmark ")
        f.write("(this PR's same-day re-run) showed this is approximately neutral ")
        f.write("on POS-EQA and slightly better on hallucination rate — net ")
        f.write("positive for the use case.\n\n---\n\n")

        # ====================================================================
        # Case 4: Cross-provider taxonomy mismatch
        # ====================================================================
        # Same concept (under-5 mortality), different codes per provider:
        #   UNICEF:    CME_MRY0T4
        #   WB:        SH.DYN.MORT
        #   DC:        MortalityRate_Person_Upto5Years
        #   data360:   WB_WDI_SH_DYN_MORT
        # MCPs reflect upstream conventions — they don't reconcile
        # taxonomies. An agent comparing across providers must know the
        # mapping. This is fundamentally not solvable inside any single
        # MCP — it would require a meta-resolver layer above the MCPs.
        f.write("## Case 4 — Cross-provider taxonomy mismatch (no MCP can fix)\n\n")
        f.write(f"- **Tried:** `{records[3]['tool']}({records[3]['args']})`\n")
        f.write("  (passing Data Commons' code to the UNICEF MCP)\n")
        f.write(f"- **Expected:** {records[3]['expected']}\n")
        f.write(f"- **Got:** `{records[3]['actual']}`\n")
        if records[3].get("text"):
            f.write(f"- **Response (truncated):**\n\n```\n{records[3]['text']}\n```\n")
        f.write("\n**Why it fails:** Same concept, different codes per provider:\n\n")
        f.write("- UNICEF:        `CME_MRY0T4`\n")
        f.write("- World Bank:    `SH.DYN.MORT`\n")
        f.write("- Data Commons:  `MortalityRate_Person_Upto5Years`\n")
        f.write("- Data360:       `WB_WDI_SH_DYN_MORT`\n\n")
        f.write("**Why MCPs can't fix this:** each MCP wraps one provider's API ")
        f.write("and faithfully exposes its native taxonomy. Reconciling across ")
        f.write("providers requires a meta-layer above the MCPs (e.g., a Data ")
        f.write("Commons-style knowledge graph that maps cross-provider codes), ")
        f.write("which is a fundamentally different artifact.\n\n")
        f.write("**Empirical bound:** when the SAME concept (U5MR) is queried ")
        f.write("from UNICEF and WB, the values agree within ±0.04 across 70 ")
        f.write("years (see CROSS-CHECK-imr-vs-u5mr.md). So providers ARE ")
        f.write("consistent on the same concept — they just call it different ")
        f.write("codes.\n\n---\n\n")

        # ====================================================================
        # Case 5: search_indicators bypass
        # ====================================================================
        # If an agent calls search_indicators("mortality") directly, it gets
        # a list of codes including both CME_MRY0 (IMR) and CME_MRY0T4
        # (U5MR). The agent has to pick one — and the resolver's
        # disambiguation logic ONLY triggers on get_data calls with strings,
        # not on search_indicators output processing. So an agent that
        # bypasses get_data and uses search_indicators gets no protection.
        f.write("## Case 5 — search_indicators bypass (resolver doesn't help)\n\n")
        f.write(f"- **Tried:** `{records[4]['tool']}({records[4]['args']})`\n")
        f.write(f"- **Expected:** {records[4]['expected']}\n")
        f.write(f"- **Got:** `{records[4]['actual']}`\n")
        if records[4].get("text"):
            f.write(f"- **Response (truncated):**\n\n```\n{records[4]['text']}\n```\n")
        f.write("\n**Why MCP can't fully fix this:** the resolver's ")
        f.write("disambiguation pattern (Case 3) only fires when the agent ")
        f.write("calls `get_data` with a string argument. If the agent ")
        f.write("instead calls `search_indicators` to discover codes, then ")
        f.write("picks the first one and feeds it to `get_data`, the ")
        f.write("resolver sees only a valid code (passthrough) and has no ")
        f.write("opportunity to flag ambiguity.\n\n")
        f.write("**MCP-level mitigation that exists:** `search_indicators` ")
        f.write("returns canonical names from UNICEF metadata, so a careful ")
        f.write("agent can read the names and notice when two results have ")
        f.write("similar codes but different concepts (e.g., `CME_MRY0` = ")
        f.write("'Infant mortality' vs `CME_MRY0T4` = 'Under-five mortality').\n\n")
        f.write("**MCP-level mitigation that doesn't exist:** ")
        f.write("`search_indicators` doesn't refuse-with-disambiguation when ")
        f.write("the query matches multiple high-similarity codes. Adding ")
        f.write("that would require carrying the disambiguation table into ")
        f.write("the search path — non-trivial since search_indicators ")
        f.write("returns ranked results, not exact-match candidates.\n\n---\n\n")

        # ====================================================================
        # Trailer
        # ====================================================================
        f.write("## Summary table\n\n")
        f.write("| # | Case | What MCP does | What MCP CAN'T do |\n")
        f.write("|---|---|---|---|\n")
        rows = [
            ("1", "Hyphen-variant synonym",
             "Normalises case/whitespace; refuses-with-list on multi-match",
             "Catch every phrasing humans invent"),
            ("2", "Misleading code prefix",
             "Returns the upstream `canonical_name` so agent can verify",
             "Relabel codes that upstream itself labels confusingly"),
            ("3", "True ambiguity",
             "Refuses-with-list (the v0.7.0 headline feature) ✓",
             "n/a — this is what the MCP does well"),
            ("4", "Cross-provider codes",
             "Stays faithful to its own provider's taxonomy",
             "Reconcile across providers (needs a meta-layer)"),
            ("5", "search_indicators path",
             "Returns canonical names alongside codes",
             "Refuse-with-list on search-path queries"),
        ]
        for row in rows:
            f.write(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} |\n")

    print(f"\n  report saved: {report_path}")
    return report_path


# ============================================================================
#  main() — orchestrate one fetch+parse+plot per MCP source.
# ============================================================================
#
# Reading order:
#
#   1. Argparse block — defines all CLI flags.
#   2. Config / output-dir / panels list — setup before the per-source loop.
#   3. Five "if <source> in servers" sections — one per MCP. Each section
#      is independent and wrapped in try/except so a single failure
#      (server not installed, bad API key, network error) doesn't kill the
#      rest of the run.
#   4. Optional combined-panel rendering (only if 2+ sources succeeded).
#   5. End-of-run markdown summary report.
#
# The script is designed to "best-effort" — if you only have one MCP
# configured, you still get one figure plus the summary report.


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--countries", default="IND", help="Comma-separated ISO3 (default: IND)")
    parser.add_argument(
        "--combined",
        action="store_true",
        help="Also render a combined overlay figure across sources",
    )
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=(
            "Directory for rendered figures. Default: ~/.openclaw/canvas/. "
            "Useful for repo-relative output (e.g. examples/mcp-smoke-test/figures/)."
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to MCP server config JSON. Default: ~/.openclaw/openclaw.json.",
    )
    parser.add_argument(
        "--invoked-by",
        default=None,
        help=(
            "Label for the agent/bot/model invoking this run, written into the "
            "figure footnote and end-of-run summary. Defaults to env-detection "
            "(Claude Code / Cursor / VS Code / shell). Use this to record the "
            "underlying model — e.g. --invoked-by 'Claude Opus 4.7' — since "
            "agents don't volunteer model identity in env."
        ),
    )
    parser.add_argument(
        "--edge-cases",
        action="store_true",
        help=(
            "After rendering figures, run the edge-case battery against "
            "unicefstats-mcp and write a markdown report documenting where "
            "the MCP / resolver fails and where it succeeds. Useful for "
            "anyone evaluating whether MCPs alone are sufficient for their "
            "data-discovery use case. See demonstrate_edge_cases() for the "
            "five cases tested."
        ),
    )
    args = parser.parse_args()

    countries = [c.strip() for c in args.countries.split(",") if c.strip()]
    today = date.today().isoformat()

    config_path = args.config or CONFIG
    try:
        cfg = json.loads(config_path.read_text())
    except FileNotFoundError:
        print(
            f"error: MCP server config not found at {config_path}\n"
            f"  Set up ~/.openclaw/openclaw.json with your MCP server commands,\n"
            f"  or pass --config <path/to/openclaw.json>. The config has shape:\n"
            f'  {{"mcp": {{"servers": {{"unicefstats": {{"command": "...", "args": [...]}}}}}}}}',
            file=sys.stderr,
        )
        return 2
    servers = cfg.get("mcp", {}).get("servers", {})
    out_dir = args.output_dir or CANVAS
    out_dir.mkdir(parents=True, exist_ok=True)

    panels: list[dict] = []
    # Sanitise the invoked-by label at entry so the cleaned value
    # propagates to every downstream consumer (figure footnotes, markdown
    # report header, edge-cases report header). _sanitize_for_markdown
    # is idempotent, so the inner call inside _provenance_footnote_text
    # is harmless but kept as defence-in-depth for non-main() callers.
    invoked_by = _sanitize_for_markdown(
        args.invoked_by or _detect_invoking_agent()
    )
    print(f"countries: {countries}")
    print(f"output dir: {out_dir}")
    print(f"invoked by: {invoked_by} (host={socket.gethostname()})")
    print()

    # ------------------------------------------------------------------
    # Source 1 of 5: UNICEF unicefstats-mcp (this repo).
    #   - Tool: get_data
    #   - Returns: SDMX JSON with {"data": [{country, period, value}, …]}
    #   - Auth: none (open SDMX)
    # ------------------------------------------------------------------
    if "unicefstats" in servers:
        print("[unicefstats] fetching CME_MRY0 …", end=" ", flush=True)
        try:
            resp = fetch(
                servers["unicefstats"],
                {
                    "name": "get_data",
                    "arguments": {"indicator": "CME_MRY0", "countries": countries},
                },
                timeout=args.timeout,
            )
            text = resp["text"]
            server_info = resp["server_info"]
            label, indicator, by_country = parse_unicefstats(text)
            n = sum(len(v) for v in by_country.values())
            print(
                f"{n} obs across {len(by_country)} countries; "
                f"indicator={indicator!r}; server={_format_server_id(server_info)}"
            )
            out = out_dir / f"mcp-figure-unicefstats-CME_MRY0-{'-'.join(countries)}-{today}.png"
            plot_one(
                label, indicator, by_country, out,
                code="CME_MRY0", server_info=server_info, invoked_by=invoked_by,
            )
            print(f"  saved: {out}")
            panels.append({
                "label": label,
                "indicator": indicator,
                "code": "CME_MRY0",
                "by_country": by_country,
                "server_info": server_info,
            })
        except Exception as e:
            print(f"FAILED: {e}")

    # ------------------------------------------------------------------
    # Source 2 of 5: World Bank world_bank_mcp_server (anshumax/...).
    #   - Tool: get_indicator_for_country (one country per call)
    #   - Returns: CSV with country.value, date, value, indicator.value
    #   - Auth: none (WB Open Data API is open access)
    # ------------------------------------------------------------------
    if "world-bank" in servers:
        print("[world-bank] fetching SH.DYN.MORT …", end=" ", flush=True)
        try:
            # World Bank MCP fetches one country per call.
            by_country_all: dict[str, list[tuple[int, float]]] = {}
            indicator_name = "?"
            label = "world-bank (WB API)"
            server_info = None
            for c in countries:
                resp = fetch(
                    servers["world-bank"],
                    {
                        "name": "get_indicator_for_country",
                        "arguments": {"country_id": c, "indicator_id": "SH.DYN.MORT"},
                    },
                    timeout=args.timeout,
                )
                # serverInfo is identical across per-country calls — capture once.
                if server_info is None:
                    server_info = resp["server_info"]
                _label, ind, by_country = parse_world_bank(resp["text"])
                if ind != "?":
                    indicator_name = ind
                for k, v in by_country.items():
                    by_country_all.setdefault(k, []).extend(v)
            for v in by_country_all.values():
                v.sort()
            n = sum(len(v) for v in by_country_all.values())
            print(
                f"{n} obs across {len(by_country_all)} countries; "
                f"indicator={indicator_name!r}; server={_format_server_id(server_info)}"
            )
            out = out_dir / f"mcp-figure-world-bank-SH.DYN.MORT-{'-'.join(countries)}-{today}.png"
            plot_one(
                label, indicator_name, by_country_all, out,
                code="SH.DYN.MORT", server_info=server_info, invoked_by=invoked_by,
            )
            print(f"  saved: {out}")
            panels.append({
                "label": label,
                "indicator": indicator_name,
                "code": "SH.DYN.MORT",
                "by_country": by_country_all,
                "server_info": server_info,
            })
        except Exception as e:
            print(f"FAILED: {e}")

    # ------------------------------------------------------------------
    # Source 3 of 5: FRED fred-mcp-server (Federal Reserve Economic Data).
    #   - Tool: fred_get_series
    #   - Returns: JSON with title, units, data: [{date, value}, …]
    #   - Auth: free FRED_API_KEY required (32-char string from
    #           https://fred.stlouisfed.org/docs/api/api_key.html)
    #   - Different from the others: monthly time series, no country axis
    # ------------------------------------------------------------------
    if "fred" in servers:
        print("[fred] fetching UNRATE …", end=" ", flush=True)
        try:
            resp = fetch(
                servers["fred"],
                {
                    "name": "fred_get_series",
                    "arguments": {"series_id": "UNRATE", "limit": 1000},
                },
                timeout=args.timeout,
            )
            label, indicator, series = parse_fred(resp["text"])
            server_info = resp["server_info"]
            print(
                f"{len(series)} obs; indicator={indicator!r}; "
                f"server={_format_server_id(server_info)}"
            )
            out = out_dir / f"mcp-figure-fred-UNRATE-{today}.png"
            plot_fred_series(
                label, indicator, series, out,
                code="UNRATE", server_info=server_info, invoked_by=invoked_by,
            )
            print(f"  saved: {out}")
        except Exception as e:
            print(f"FAILED: {e}")

    # ------------------------------------------------------------------
    # Source 4 of 5: World Bank Data360 MCP (data360-mcp).
    #   - Tool: data360_get_data (one country per call via REF_AREA filter)
    #   - Returns: SDMX-shaped JSON with capital-letter keys
    #              (REF_AREA, TIME_PERIOD, OBS_VALUE)
    #   - Auth: no key (Data360 API is open). DATA360_API_BASE_URL
    #           env var has a public default.
    #   - Note: upstream data360-mcp is HTTP/SSE only; this section
    #           assumes a stdio-mode build/wrapper.
    # ------------------------------------------------------------------
    if "data360" in servers:
        print("[data360] fetching WB_WDI/WB_WDI_SH_DYN_MORT …", end=" ", flush=True)
        try:
            # data360_get_data accepts a single REF_AREA via disaggregation_filters.
            # For multi-country, call once per country (matches world-bank panel).
            by_country_all: dict[str, list[tuple[int, float]]] = {}
            indicator_name = "?"
            label = "data360 (World Bank Data360)"
            server_info = None
            for c in countries:
                resp = fetch(
                    servers["data360"],
                    {
                        "name": "data360_get_data",
                        "arguments": {
                            "database_id": "WB_WDI",
                            "indicator_id": "WB_WDI_SH_DYN_MORT",
                            "disaggregation_filters": {"REF_AREA": c},
                        },
                    },
                    timeout=max(args.timeout, 30.0),
                )
                if server_info is None:
                    server_info = resp["server_info"]
                _label, ind, by_country = parse_data360(resp["text"])
                if ind != "?":
                    indicator_name = ind
                for k, v in by_country.items():
                    by_country_all.setdefault(k, []).extend(v)
            for v in by_country_all.values():
                v.sort()
            n = sum(len(v) for v in by_country_all.values())
            print(
                f"{n} obs across {len(by_country_all)} countries; "
                f"indicator={indicator_name!r}; server={_format_server_id(server_info)}"
            )
            out = (
                out_dir / f"mcp-figure-data360-WB_WDI_SH_DYN_MORT-"
                f"{'-'.join(countries)}-{today}.png"
            )
            plot_one(
                label, indicator_name, by_country_all, out,
                code="WB_WDI_SH_DYN_MORT", server_info=server_info,
                invoked_by=invoked_by,
            )
            print(f"  saved: {out}")
            panels.append({
                "label": label,
                "indicator": indicator_name,
                "code": "WB_WDI_SH_DYN_MORT",
                "by_country": by_country_all,
                "server_info": server_info,
            })
        except Exception as e:
            print(f"FAILED: {e}")

    # ------------------------------------------------------------------
    # Source 5 of 5: Google Data Commons MCP (datacommons-mcp).
    #   - Tool: get_observations (multi-country in one call)
    #   - Returns: nested envelope
    #     {byVariable → byEntity → orderedFacets → observations: [{date, value}]}
    #   - Auth: free DC_API_KEY required (register at apikeys.datacommons.org)
    #   - Place IDs use DCIDs ("country/IND"); the parser strips the
    #     "country/" prefix so the country axis lines up with the
    #     other three U5MR sources in the combined overlay.
    # ------------------------------------------------------------------
    if "data-commons" in servers:
        print("[data-commons] fetching MortalityRate_Person_Upto5Years …",
              end=" ", flush=True)
        try:
            place_dcids = [f"country/{c}" for c in countries]
            resp = fetch(
                servers["data-commons"],
                {
                    "name": "get_observations",
                    "arguments": {
                        "variable_dcids": ["MortalityRate_Person_Upto5Years"],
                        "entity_dcids": place_dcids,
                    },
                },
                timeout=max(args.timeout, 30.0),
            )
            label, indicator, by_country = parse_data_commons(resp["text"])
            server_info = resp["server_info"]
            n = sum(len(v) for v in by_country.values())
            print(
                f"{n} obs across {len(by_country)} entities; "
                f"indicator={indicator!r}; server={_format_server_id(server_info)}"
            )
            out = (
                out_dir / f"mcp-figure-data-commons-MortalityRate_Person_Upto5Years-"
                f"{'-'.join(countries)}-{today}.png"
            )
            plot_one(
                label, indicator, by_country, out,
                code="MortalityRate_Person_Upto5Years", server_info=server_info,
                invoked_by=invoked_by,
            )
            print(f"  saved: {out}")
            panels.append({
                "label": label,
                "indicator": indicator,
                "code": "MortalityRate_Person_Upto5Years",
                "by_country": by_country,
                "server_info": server_info,
            })
        except Exception as e:
            print(f"FAILED: {e}")

    # ------------------------------------------------------------------
    # Optional: combined overlay across all sources that succeeded.
    # Only renders if --combined was passed AND we got data from ≥2
    # sources (a single-line "overlay" wouldn't be informative).
    # ------------------------------------------------------------------
    if args.combined and len(panels) >= 2:
        out = out_dir / f"mcp-figure-combined-{'-'.join(countries)}-{today}.png"
        plot_combined(panels, out, countries=countries, invoked_by=invoked_by)
        print(f"\n[combined] saved: {out}")

    # ------------------------------------------------------------------
    # End-of-run summary report (markdown).
    #
    # Captures the same provenance info as the figure footnote, but in
    # a machine-readable + human-readable file that lives next to the
    # PNGs. Useful when six months later you want to know:
    #   - which sources rendered successfully (vs. failed silently)
    #   - which MCP server version produced which panel
    #   - which agent / host / timestamp ran the script
    # The first three header lines map directly to the figure footnote.
    # ------------------------------------------------------------------
    summary_path = out_dir / f"mcp-figures-summary-{'-'.join(countries)}-{today}.md"
    ts_iso = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with summary_path.open("w", encoding="utf-8") as f:
        f.write(f"# mcp-smoke-test summary — {today}\n\n")
        f.write(f"- Countries: {', '.join(countries)}\n")
        f.write(f"- Output dir: `{out_dir}`\n")
        f.write(f"- Generated: `{ts_iso}` on `{socket.gethostname()}`\n")
        f.write(f"- Invoked by: `{invoked_by}`\n")
        f.write(f"- Sources rendered: {len(panels)}\n\n")
        f.write("| Source | Code | n obs | MCP server |\n")
        f.write("| --- | --- | --- | --- |\n")
        for p in panels:
            n_obs = sum(len(v) for v in p["by_country"].values())
            sid = _format_server_id(p.get("server_info"))
            f.write(
                f"| {p['label']} | `{p['code']}` | {n_obs} | "
                f"`{sid}` |\n"
            )
        f.write("\n")
        f.write(
            "Each per-source figure carries a `Variable code: <CODE>  |  "
            "Source: <name> v<version>` footnote. The combined figure "
            "(if rendered) lists code + server identity for every panel, "
            "so source-disagreement can be attributed to the right server "
            "version when figures are re-examined later.\n"
        )
    print(f"\nsummary: {summary_path}")

    # ------------------------------------------------------------------
    # Optional: edge-case demonstration battery.
    #
    # When the user passes --edge-cases, run the five-case battery
    # against unicefstats-mcp and write the markdown report. Runs AFTER
    # the figure rendering loop so a normal run is unaffected.
    # ------------------------------------------------------------------
    if args.edge_cases:
        if "unicefstats" not in servers:
            print(
                "\n[edge-cases] requires 'unicefstats' in openclaw.json — skipping",
                file=sys.stderr,
            )
        else:
            demonstrate_edge_cases(
                servers["unicefstats"],
                out_dir,
                today,
                invoked_by,
            )

    print(f"\ndone. output dir: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
