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
| `mcp-figures.py` | Per-source smoke test — speaks JSON-RPC to 5 MCPs, deterministic, no LLM in the loop, renders one matplotlib figure per source. |
| `mcp-multimodel-smoketest.py` | Cross-provider LLM smoke test — sends 3 canonical prompts (1 POS + 1 T1 + 1 T2) to N models (Anthropic, OpenAI, Google, OpenRouter) with unicefstats-mcp attached as a tool layer. Surfaces tool-engagement, refusal discipline, and cost-per-question by tier. ~$1 / run on the 6-model MVP set. See "Cross-model smoke test" below. |
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

## Cross-model smoke test

> **Full reference:** [`MULTIMODEL_SMOKETEST.md`](MULTIMODEL_SMOKETEST.md) — design,
> rubric, per-provider tool-loop details, output format, JSON one-liners,
> limitations, path to a full mini-EQA, cost model, troubleshooting.
> The section below is a quick-start summary.

`mcp-multimodel-smoketest.py` is structurally different from `mcp-figures.py`:
- `mcp-figures.py` probes **N MCP servers** with **1 deterministic client** (no LLM)
- `mcp-multimodel-smoketest.py` probes **1 MCP server** with **N LLM clients** at different price tiers

Why this exists: the v0.7.3 + fixes benchmark established that
unicefstats-mcp makes Claude Sonnet 4 *strictly safer* on absent-data
queries than the no-tools baseline (`hall_b 1.00%` / `2.25%` vs `hall_a
2.50%`). That result is Sonnet-4-only — the v3 LinkedIn drafts explicitly
flag cross-model generalisation as the next open question. This script
is the cheapest way to start answering it.

### Default model set (6 models, 3 providers × 2 tiers)

```bash
uv run --script mcp-multimodel-smoketest.py --list-models
```

| Provider | Model | Tier | Price ($/M in $/M out) |
|---|---|---|---|
| Anthropic | `claude-sonnet-4-20250514` | mid | $3.00 / $15.00 |
| Anthropic | `claude-haiku-4-5-20251001` | cheap | $0.25 / $1.25 |
| OpenAI | `gpt-4o-2024-11-20` | mid | $2.50 / $10.00 |
| OpenAI | `gpt-4o-mini-2024-07-18` | cheap | $0.15 / $0.60 |
| Google | `gemini-2.5-flash` | mid | $0.30 / $2.50 |
| Google | `gemini-2.0-flash` | cheap | $0.075 / $0.30 |

### Run it

```bash
# all default models (needs ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY/GOOGLE_API_KEY)
uv run --script mcp-multimodel-smoketest.py

# subset
uv run --script mcp-multimodel-smoketest.py --models claude-sonnet-4-20250514,gpt-4o-mini-2024-07-18

# trace each tool call to stderr
uv run --script mcp-multimodel-smoketest.py --verbose

# write into a different directory
uv run --script mcp-multimodel-smoketest.py --output-dir ./my-results
```

Models whose API key is missing are skipped with a `⊘` marker in the
report — you don't need all three providers' keys to get useful output.

### Output

Two files, named for the run date:

| File | Content |
|---|---|
| `mcp-multimodel-smoketest-YYYY-MM-DD.md` | Markdown report: per-model rubric pass-rate, per-prompt detail (tool calls, value, year, refusal, latency, cost), totals |
| `mcp-multimodel-smoketest-YYYY-MM-DD.json` | Raw per-model-per-prompt results for downstream analysis |

### Rubric

| Prompt | Pass criterion |
|---|---|
| POS: U5MR Nigeria 2023 | Value in [100, 130] AND year = 2023 (canonical IGME estimate ~114) |
| T1: Stunting Liechtenstein | Refusal language detected AND no numeric value extracted |
| T2: U5MR Nigeria 2028 | Refusal language detected AND no numeric value extracted |

A model that scores **3/3** is a candidate for a full mini-EQA run.
A model that scores **<3/3** reveals a behaviour we did not see on
Sonnet 4 and worth investigating before claiming cross-model
generalisation.

### Limits

This is a **3-prompt smoke test**, not a benchmark. With n=3 there is no
statistical power. The goal is qualitative: surface tool-engagement
patterns, refusal discipline, and cost-per-question fast and cheap
before spending $X on a full multi-provider EQA run.

Reference baseline (Sonnet 4, v0.7.3 + fixes, n=500): `POS_EQA = 0.891`
(mcp060) / `0.909` (mcp073); `hall_b` combined `= 1.00%` (mcp060) /
`2.25%` (mcp073). See [`internal/v0_7_3_validation.md`](../../internal/v0_7_3_validation.md)
and [`internal/v0_7_3_second_sample_validation.md`](../../internal/v0_7_3_second_sample_validation.md).
