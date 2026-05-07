#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["matplotlib"]
# ///
"""
mcp-figures.py — render a figure per data MCP from a real tool call.

Companion to scripts/test-mcps.py: where that script *probes* the MCPs for
health, this one *fetches data and plots it* — proving end-to-end that:

  1. The MCP responds to a tools/call
  2. The response carries real time-series data
  3. The data can be parsed into (year, value) tuples
  4. A figure can be rendered from those tuples

Output:
  ~/.openclaw/canvas/mcp-figure-<source>-<indicator>-<countries>-<YYYY-MM-DD>.png

Usage:
  uv run --script scripts/mcp-figures.py             # default: U5MR India
  uv run --script scripts/mcp-figures.py --countries IND,KEN
  uv run --script scripts/mcp-figures.py --combined  # also produce overlay

The default indicator is Under-5 mortality:
  - unicefstats: SDMX code CME_MRY0
  - world-bank:  series SH.DYN.MORT
data360 has no get_data tool exposed yet (only data360_search), so it is
listed as a catalog probe rather than plotted.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import subprocess
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any, Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

CONFIG = Path.home() / ".openclaw" / "openclaw.json"
CANVAS = Path.home() / ".openclaw" / "canvas"


# --- MCP protocol helpers (mirror test-mcps.py) -------------------------------


def jsonrpc(method: str, msg_id: int, params: dict[str, Any] | None = None) -> bytes:
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": msg_id, "method": method}
    if params is not None:
        payload["params"] = params
    return (json.dumps(payload) + "\n").encode()


def read_response(stdout, deadline: float) -> dict[str, Any] | None:
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
            continue
        if isinstance(decoded, dict) and "id" in decoded:
            return decoded


def fetch(server: dict[str, Any], call: dict[str, Any], *, timeout: float = 60.0) -> str:
    """Run init + tools/call against a server and return the text payload."""
    cmd = [server["command"], *server.get("args", [])]
    env = os.environ.copy()
    for k, v in (server.get("env") or {}).items():
        if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
            env[k] = os.environ.get(v[2:-1], "")
        else:
            env[k] = str(v)

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
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
        if read_response(proc.stdout, time.time() + timeout) is None:
            raise RuntimeError("initialize: no response")
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
        text_parts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
        return "\n".join(text_parts)
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()


# --- per-source response parsers --------------------------------------------


def parse_unicefstats(text: str) -> tuple[str, str, dict[str, list[tuple[int, float]]]]:
    """Returns (label, indicator_name, {country: [(year, value)]})."""
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
    """World Bank MCP returns a CSV string."""
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
    """data360 returns SDMX-shaped JSON with data: [{OBS_VALUE, TIME_PERIOD, REF_AREA, ...}]."""
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


def parse_fred(text: str) -> tuple[str, str, list[tuple[str, float]]]:
    """FRED MCP returns JSON with data: [{date, value}].

    Returns (label, indicator_name, [(date_str, value)]). Dates are kept
    as strings (YYYY-MM-DD) for matplotlib's date parsing.
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


# --- plotting ---------------------------------------------------------------


COLORS = {"India": "#E69F00", "Kenya": "#56B4E9", "Brazil": "#009E73", "Nigeria": "#CC79A7"}


def plot_one(
    label: str,
    indicator: str,
    by_country: dict[str, list[tuple[int, float]]],
    out_path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
    for country, series in sorted(by_country.items()):
        if not series:
            continue
        years, values = zip(*series)
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
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def plot_fred_series(label: str, indicator: str, series: list[tuple[str, float]], out_path: Path) -> None:
    """FRED data is monthly with date strings — different shape than the
    yearly country-keyed data the other parsers return."""
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
            "WHO COVID-19 pandemic\n(11 Mar 2020 declaration —\nwidespread vaccine eligibility,\nend of May 2021)",
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
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def plot_combined(
    panels: list[tuple[str, str, dict[str, list[tuple[int, float]]]]],
    out_path: Path,
) -> None:
    """Overlay all sources on one figure to show source-disagreement, if any."""
    fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
    for label, indicator, by_country in panels:
        for country, series in sorted(by_country.items()):
            if not series:
                continue
            years, values = zip(*series)
            ax.plot(
                years,
                values,
                marker="o",
                markersize=2.5,
                linewidth=1.4,
                label=f"{label} — {country}",
                alpha=0.85,
            )
    ax.set_xlabel("Year")
    ax.set_ylabel("Indicator value")
    ax.set_title("MCP source comparison: Under-5 / Infant mortality, India", fontsize=11)
    ax.grid(True, alpha=0.3, linestyle="--")
    ax.legend(loc="best", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


# --- main -------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--countries", default="IND", help="Comma-separated ISO3 (default: IND)")
    parser.add_argument(
        "--combined",
        action="store_true",
        help="Also render a combined overlay figure across sources",
    )
    parser.add_argument("--timeout", type=float, default=60.0)
    args = parser.parse_args()

    countries = [c.strip() for c in args.countries.split(",") if c.strip()]
    today = date.today().isoformat()

    cfg = json.loads(CONFIG.read_text())
    servers = cfg.get("mcp", {}).get("servers", {})
    CANVAS.mkdir(parents=True, exist_ok=True)

    panels: list[tuple[str, str, dict[str, list[tuple[int, float]]]]] = []
    print(f"countries: {countries}")
    print(f"output dir: {CANVAS}")
    print()

    # 1. unicefstats — Under-5 / Infant mortality (CME_MRY0)
    if "unicefstats" in servers:
        print("[unicefstats] fetching CME_MRY0 …", end=" ", flush=True)
        try:
            text = fetch(
                servers["unicefstats"],
                {"name": "get_data", "arguments": {"indicator": "CME_MRY0", "countries": countries}},
                timeout=args.timeout,
            )
            label, indicator, by_country = parse_unicefstats(text)
            n = sum(len(v) for v in by_country.values())
            print(f"{n} obs across {len(by_country)} countries; indicator={indicator!r}")
            out = CANVAS / f"mcp-figure-unicefstats-CME_MRY0-{'-'.join(countries)}-{today}.png"
            plot_one(label, indicator, by_country, out)
            print(f"  saved: {out}")
            panels.append((label, indicator, by_country))
        except Exception as e:
            print(f"FAILED: {e}")

    # 2. world-bank — Under-5 mortality (SH.DYN.MORT)
    if "world-bank" in servers:
        print("[world-bank] fetching SH.DYN.MORT …", end=" ", flush=True)
        try:
            # World Bank MCP fetches one country per call.
            by_country_all: dict[str, list[tuple[int, float]]] = {}
            indicator_name = "?"
            label = "world-bank (WB API)"
            for c in countries:
                text = fetch(
                    servers["world-bank"],
                    {
                        "name": "get_indicator_for_country",
                        "arguments": {"country_id": c, "indicator_id": "SH.DYN.MORT"},
                    },
                    timeout=args.timeout,
                )
                _label, ind, by_country = parse_world_bank(text)
                if ind != "?":
                    indicator_name = ind
                for k, v in by_country.items():
                    by_country_all.setdefault(k, []).extend(v)
            for v in by_country_all.values():
                v.sort()
            n = sum(len(v) for v in by_country_all.values())
            print(f"{n} obs across {len(by_country_all)} countries; indicator={indicator_name!r}")
            out = CANVAS / f"mcp-figure-world-bank-SH.DYN.MORT-{'-'.join(countries)}-{today}.png"
            plot_one(label, indicator_name, by_country_all, out)
            print(f"  saved: {out}")
            panels.append((label, indicator_name, by_country_all))
        except Exception as e:
            print(f"FAILED: {e}")

    # 3. fred — Unemployment Rate (UNRATE), monthly time series
    if "fred" in servers:
        print("[fred] fetching UNRATE …", end=" ", flush=True)
        try:
            text = fetch(
                servers["fred"],
                {
                    "name": "fred_get_series",
                    "arguments": {"series_id": "UNRATE", "limit": 1000},
                },
                timeout=args.timeout,
            )
            label, indicator, series = parse_fred(text)
            print(f"{len(series)} obs; indicator={indicator!r}")
            out = CANVAS / f"mcp-figure-fred-UNRATE-{today}.png"
            plot_fred_series(label, indicator, series, out)
            print(f"  saved: {out}")
        except Exception as e:
            print(f"FAILED: {e}")

    # 4. data360 — Under-5 mortality via WB_WDI database
    if "data360" in servers:
        print("[data360] fetching WB_WDI/WB_WDI_SH_DYN_MORT …", end=" ", flush=True)
        try:
            # data360_get_data accepts a single REF_AREA via disaggregation_filters.
            # For multi-country, call once per country (matches world-bank panel).
            by_country_all: dict[str, list[tuple[int, float]]] = {}
            indicator_name = "?"
            label = "data360 (World Bank Data360)"
            for c in countries:
                text = fetch(
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
                _label, ind, by_country = parse_data360(text)
                if ind != "?":
                    indicator_name = ind
                for k, v in by_country.items():
                    by_country_all.setdefault(k, []).extend(v)
            for v in by_country_all.values():
                v.sort()
            n = sum(len(v) for v in by_country_all.values())
            print(f"{n} obs across {len(by_country_all)} countries; indicator={indicator_name!r}")
            out = CANVAS / f"mcp-figure-data360-WB_WDI_SH_DYN_MORT-{'-'.join(countries)}-{today}.png"
            plot_one(label, indicator_name, by_country_all, out)
            print(f"  saved: {out}")
            panels.append((label, indicator_name, by_country_all))
        except Exception as e:
            print(f"FAILED: {e}")

    # Optional combined panel
    if args.combined and len(panels) >= 2:
        out = CANVAS / f"mcp-figure-combined-{'-'.join(countries)}-{today}.png"
        plot_combined(panels, out)
        print(f"\n[combined] saved: {out}")

    print(f"\ndone. canvas dir: {CANVAS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
