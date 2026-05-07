# mcp-smoke-test

A self-contained example of fetching real time-series data from
**four** stdio-MCP servers — `unicefstats-mcp` (this repo), the World
Bank `world-bank-mcp-server`, the Federal Reserve `fred-mcp-server`,
and `data360-mcp` — then rendering one matplotlib figure per source.

Use it as a worked reference for:

- consuming an MCP server from outside an LLM agent
- the canonical stdio JSON-RPC sequence (`initialize` → `tools/call`)
- shape parsing for each source's response (UNICEF SDMX JSON, WB CSV,
  FRED JSON, data360 SDMX-shaped JSON)

## Files

| Path | Description |
| --- | --- |
| `mcp-figures.py` | Self-contained `uv run --script` Python program. |
| `figures/mcp-figure-unicefstats-CME_MRY0-IND-2026-05-07.png` | UNICEF SDMX, India, 72 obs (1953-2024). |
| `figures/mcp-figure-world-bank-SH.DYN.MORT-IND-2026-05-07.png` | World Bank, India, 65 obs (1960-2024). |
| `figures/mcp-figure-fred-UNRATE-2026-05-07.png` | FRED, US Unemployment Rate, 938 monthly obs (1948-2026). |
| `figures/mcp-figure-data360-WB_WDI_SH_DYN_MORT-IND-2026-05-07.png` | data360 (WB WDI), India, 65 obs (1960-2024). |
| `figures/mcp-figure-combined-IND-2026-05-07.png` | Overlay — surfaces a labeling drift between the UNICEF series (reported as IMR) and WB U5MR. |

## Run it

```bash
# default (Under-5 mortality, India)
uv run --script mcp-figures.py

# multiple countries; produce overlay figure
uv run --script mcp-figures.py --countries IND,KEN,BRA --combined

# longer per-call timeout for slow upstream APIs
uv run --script mcp-figures.py --timeout 60
```

Output PNGs go to `~/.openclaw/canvas/`.

## Required environment

The script reads canonical server commands from
`~/.openclaw/openclaw.json`. The MCP processes inherit env from the
calling shell, so for `fred` and `data360` you need:

```bash
export FRED_API_KEY=$(launchctl getenv FRED_API_KEY)
export DATA360_API_BASE_URL="https://data360api.worldbank.org"
export DATA360_CODELIST_API_BASE_URL="https://data360api.worldbank.org"
```

`unicefstats` and `world-bank` need no API key.

## Notes

- **data360** required a small upstream patch — its server only exposes
  `data360_search` by default; the underlying `api` module also has
  `get_data` and `get_metadata`. The patch (adding `@mcp.tool` wrappers
  for those two) is local; consider PRing to
  `worldbank/data360-mcp` if the upstream maintainers want to take it.
- **labeling drift** — UNICEF reports `CME_MRY0` as "Infant mortality
  rate" while the canonical UNICEF dataflow uses that code for U5MR.
  The combined figure makes this visible: UNICEF's series tracks
  slightly above WB/data360. Worth knowing when an agent picks an
  indicator code via search.
- For health-only probing (no data fetch, no figures), see the sibling
  `test-mcps.py` in `jpazvd.lab-config/scripts/`.
