# mcp-smoke-test

A self-contained example of fetching real time-series data from **five**
stdio-MCP servers — `unicefstats-mcp` (this repo), the World Bank
`world-bank-mcp-server`, the Federal Reserve `fred-mcp-server`,
`data360-mcp`, and Google's `datacommons-mcp` — then rendering one
matplotlib figure per source.

Use it as a worked reference for:

- consuming an MCP server from outside an LLM agent
- the canonical stdio JSON-RPC sequence (`initialize` → `tools/call`)
- shape parsing for each source's response (UNICEF SDMX JSON, WB CSV,
  FRED JSON, data360 SDMX-shaped JSON, Data Commons byVariable→byEntity)

## Files

| Path | Description |
| --- | --- |
| `mcp-figures.py` | Self-contained `uv run --script` Python program. |
| `figures/mcp-figure-unicefstats-CME_MRY0-IND-2026-05-08.png` | UNICEF SDMX, India, 72 obs (1953-2024). Two-line footnote: variable code + server identity (line 1), UTC timestamp + host + invoking agent (line 2). |
| `figures/mcp-figure-world-bank-SH.DYN.MORT-IND-2026-05-08.png` | World Bank, India, 65 obs (1960-2024). Server reports as `mysql_mcp_server v1.26.0` because the upstream package was forked from a MySQL template and never renamed its FastMCP `name` — the footnote captures this faithfully (which is exactly what reproducibility metadata is for). |
| `figures/mcp-figure-combined-IND-2026-05-08.png` | Overlay (UNICEF vs WB) — surfaces a real **labeling drift**: UNICEF's `CME_MRY0` tracks ~30% below WB's `SH.DYN.MORT`, confirming UNICEF labels the code as "Infant mortality rate" (0-1 yr) while WB returns "Under-5 mortality rate" (0-5 yr) for what would otherwise look like comparable codes. The footnote lists both server identities side-by-side. |
| `figures/mcp-figure-fred-UNRATE-2026-05-07.png` | FRED, US Unemployment Rate, 938 monthly obs (1948-2026). Pre-footnote — regenerate when `FRED_API_KEY` is set. |
| `figures/mcp-figure-data360-WB_WDI_SH_DYN_MORT-IND-2026-05-07.png` | data360 (WB WDI), India, 65 obs (1960-2024). Pre-footnote — upstream `worldbank/data360-mcp` is HTTP/SSE only, not stdio, so this script can't drive it as-is. |
| (not yet rendered) `figures/mcp-figure-data-commons-MortalityRate_Person_Upto5Years-IND-*.png` | Google Data Commons, India, U5MR series — needs free `DC_API_KEY` from <https://apikeys.datacommons.org>. |
| `figures/mcp-figures-summary-IND-2026-05-08.md` | Last-run summary report (Source / Code / n obs / MCP server table). |

## Run it

```bash
# default (Under-5 mortality, India)
uv run --script mcp-figures.py

# multiple countries; produce overlay figure
uv run --script mcp-figures.py --countries IND,KEN,BRA --combined

# longer per-call timeout for slow upstream APIs
uv run --script mcp-figures.py --timeout 60

# write directly into the repo's figures/ directory (e.g. for refreshing
# the committed snapshots after a code change)
uv run --script mcp-figures.py --combined \
    --output-dir examples/mcp-smoke-test/figures

# point at a non-default MCP server config
uv run --script mcp-figures.py --config /path/to/openclaw.json

# label the invoking agent/model on the footnote (defaults: env-detected)
uv run --script mcp-figures.py --invoked-by "Claude Opus 4.7 via Claude Code"

# run the 5-case edge-case battery and write a markdown report
# documenting where unicefstats-mcp resolver fails and where it
# succeeds (synonym gaps, misleading code prefixes, cross-provider
# taxonomy, search_indicators bypass, refuse-with-disambiguation)
uv run --script mcp-figures.py --edge-cases
```

Default output directory: `~/.openclaw/canvas/`. Override with
`--output-dir <path>`.

## Required environment

The script reads canonical server commands from
`~/.openclaw/openclaw.json`. The MCP processes inherit env from the
calling shell, so for `fred` and `data360` you need:

```bash
export FRED_API_KEY=$(launchctl getenv FRED_API_KEY)
export DATA360_API_BASE_URL="https://data360api.worldbank.org"
export DATA360_CODELIST_API_BASE_URL="https://data360api.worldbank.org"
```

`unicefstats`, `world-bank`, and `data-commons` need no API key.

The `data-commons` entry should run Google's official MCP via uvx:

```jsonc
"data-commons": {
  "command": "uvx",
  "args": ["datacommons-mcp", "serve", "stdio"]
}
```

(Google's [datacommons-mcp on PyPI](https://pypi.org/project/datacommons-mcp/) — published from
[datacommonsorg/agent-toolkit](https://github.com/datacommonsorg/agent-toolkit).)

## Notes

- **data360** required a small upstream patch — its server only exposes
  `data360_search` by default; the underlying `api` module also has
  `get_data` and `get_metadata`. The patch (adding `@mcp.tool` wrappers
  for those two) is local; consider PRing to
  `worldbank/data360-mcp` if the upstream maintainers want to take it.
- **labeling drift** — UNICEF labels `CME_MRY0` as "Infant mortality
  rate" (0-1 yr) and uses `CME_MRY0T4` for "Under-five mortality rate"
  (0-5 yr). World Bank `SH.DYN.MORT` is U5MR. So when the original
  combined figure compares `CME_MRY0` vs `SH.DYN.MORT`, the lines diverge
  by ~30% — which is the *real* IMR-vs-U5MR age-window difference, not
  a country-composition or methodology issue. Confirmed by direct
  cross-check (see [CROSS-CHECK-imr-vs-u5mr.md](CROSS-CHECK-imr-vs-u5mr.md)
  and figure `mcp-figure-crosscheck-IMR-vs-U5MR-IND-2026-05-08.png`):
  when the same concept is queried (UNICEF `CME_MRY0T4` vs WB
  `SH.DYN.MORT`, both U5MR), the values agree within rounding (±0.04
  across the 7 sample years tested between 1970 and 2024) because
  both providers surface the same UN IGME estimates. Note: this
  demonstrates **upstream-data agreement** between two IGME-sourced
  wrappers — not a general claim that "the MCP layer doesn't introduce
  drift" for arbitrary indicators. To test MCP-layer fidelity in the
  general case you'd need an indicator pair where UNICEF and WB
  *compute independently* (e.g. fertility, GDP, education completion);
  that follow-up is out of scope for this smoke test.
- **two-line provenance footnote** — each per-source figure carries
  two italic-grey lines at the bottom-right:
  - `Variable code: <CODE>  |  Source: <name> v<version>` — what data
    was queried and from which MCP server version. Captures
    server-side reproducibility: a number that shifts between two
    runs of the same figure could be upstream-data drift OR a
    server-side resolver change, and the version stamp tells you which.
  - `Generated <UTC ISO timestamp> on <host> via <agent>` — execution
    provenance. The agent is auto-detected (`Claude Code` /
    `Cursor` / `VS Code` / `GitHub Codespaces` / `shell`) from common
    env signals, or set explicitly via `--invoked-by "<label>"` to
    record an underlying model name (agents don't volunteer model
    identity in env, so explicit labeling is the only way to record
    "Claude Opus 4.7" vs "GPT-5" in the footnote). The combined
    figure lists code + server-id per panel and the same provenance
    line.
- **end-of-run summary report** — each invocation writes a markdown
  summary alongside the figures
  (`mcp-figures-summary-<countries>-<date>.md`), with: Generated /
  Invoked-by header lines + a Source / Code / n obs / MCP server table.
- For health-only probing (no data fetch, no figures), see the sibling
  `test-mcps.py` in `jpazvd.lab-config/scripts/`.
