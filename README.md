<!-- mcp-name: io.github.jpazvd/unicefstats-mcp -->
[![MCP Badge](https://lobehub.com/badge/mcp/jpazvd-unicefstats-mcp?style=for-the-badge)](https://lobehub.com/mcp/jpazvd-unicefstats-mcp)

# unicefstats-mcp

> **Disclaimer** — This is an independent research project. It is **not an official UNICEF product** and does not represent the views or policies of UNICEF. The software is provided "as is", without warranty of any kind, express or implied. Use at your own risk.
>
> **Experimental / Research Prototype** — this project is under active development and has not been validated for production use. Tool signatures and response formats may change without notice.
>
> **Human verification is essential.** While MCP tools significantly improve LLM accuracy on UNICEF statistics (EQA 0.990 vs 0.147 baseline, replicated across 40 countries), results are not error-free. Our benchmark shows that even with tool access, the LLM may fabricate data when the underlying API returns no results (T2 hallucination ~10% after correcting for ground truth misclassification). Any statistic retrieved through this MCP should be verified against the [UNICEF Data Warehouse](https://data.unicef.org/) before use in policy documents, publications, or official communications.
>
> Contributions and feedback welcome — see [Contributing](#contributing) below.

MCP server for UNICEF child development statistics. Query 790+ child-focused indicators across 200+ countries with disaggregations by sex, age, wealth quintile, and residence. No API key required.

Indicators cover child mortality, nutrition, education, child protection, WASH (water/sanitation/hygiene), HIV/AIDS, immunization, early childhood development, and more. Many align with SDG targets, but the dataset is broader than SDGs alone.

Data source: [UNICEF SDMX API](https://sdmx.data.unicef.org/ws/public/sdmxapi/rest)

### Identity

| Property | Value |
|---|---|
| **MCP identity** | `io.github.jpazvd/unicefstats-mcp` |
| **PyPI package** | [`unicefstats-mcp`](https://pypi.org/project/unicefstats-mcp/) |
| **Canonical source** | [github.com/jpazvd/unicefstats-mcp](https://github.com/jpazvd/unicefstats-mcp) |
| **Data source** | [UNICEF Data Warehouse](https://data.unicef.org/) via [SDMX REST API](https://sdmx.data.unicef.org/ws/public/sdmxapi/rest) |
| **Publisher** | Joao Pedro Azevedo ([`jpazvd`](https://github.com/jpazvd)) |

> **Mirror warning**: This MCP may appear on third-party directories (LobeHub, Smithery, mcp.so, Glama, etc.). Those listings are not controlled by the maintainer. Always verify against the canonical source above. See [How to Verify This MCP](#how-to-verify-this-mcp) below.

## Contents

- [How it relates to the unicefdata packages](#how-it-relates-to-the-unicefdata-packages)
- [How it compares to other data MCPs](#how-it-compares-to-other-data-mcps)
- [Landscape: MCP servers for official statistics](#landscape-mcp-servers-for-official-statistics)
- [Relationship to sdmx-mcp](#relationship-to-sdmx-mcp)
- [Quick Start](#quick-start)
- [Tools](#tools)
- [Demo](#demo)
- [Prompts](#prompts)
- [Benchmark Results](#benchmark-results)
- [Deployment](#deployment)
- [Development](#development)
- [Contributing](#contributing)
- [Provenance and Ownership](#provenance-and-ownership)
- [How to Verify This MCP](#how-to-verify-this-mcp)
- [License](#license)

### Key documents

| Document | Description |
|---|---|
| [PROVENANCE.md](https://github.com/jpazvd/unicefstats-mcp/blob/main/PROVENANCE.md) | Data origin, ownership, distribution pipeline, verification steps |
| [CHANGELOG.md](https://github.com/jpazvd/unicefstats-mcp/blob/main/CHANGELOG.md) | Version history (v0.1.0–v0.4.0) with sources cited |
| [RELEASE.md](https://github.com/jpazvd/unicefstats-mcp/blob/main/RELEASE.md) | Release process checklist and version management |
| [CONTRIBUTING.md](https://github.com/jpazvd/unicefstats-mcp/blob/main/CONTRIBUTING.md) | Development setup, code style, PR guidelines |
| [CODE_OF_CONDUCT.md](https://github.com/jpazvd/unicefstats-mcp/blob/main/CODE_OF_CONDUCT.md) | Contributor Covenant v2.1 |
| [examples/RESULTS.md](https://github.com/jpazvd/unicefstats-mcp/blob/main/examples/RESULTS.md) | Full 300-query benchmark analysis with EQA decomposition |
| [examples/LITERATURE_REVIEW.md](https://github.com/jpazvd/unicefstats-mcp/blob/main/examples/LITERATURE_REVIEW.md) | Literature review: MCP servers for official statistics — ecosystem, patterns, evaluation, 15 papers |
| [examples/LANDSCAPE.md](https://github.com/jpazvd/unicefstats-mcp/blob/main/examples/LANDSCAPE.md) | 20 official statistics MCP servers compared — timeline, feature matrix, strengths/weaknesses |
| [examples/results/related_work.md](https://github.com/jpazvd/unicefstats-mcp/blob/main/examples/results/related_work.md) | Annotated bibliography — 15 papers on tool-augmented hallucination |
| [examples/results/statistical_summary.md](https://github.com/jpazvd/unicefstats-mcp/blob/main/examples/results/statistical_summary.md) | Wilcoxon, bootstrap CI, McNemar tests on benchmark results |
| [examples/MCP-DIRECTORY-STATS.md](https://github.com/jpazvd/unicefstats-mcp/blob/main/examples/MCP-DIRECTORY-STATS.md) | Comprehensive directory of all official statistics MCP servers |

## How it relates to the unicefdata packages

`unicefstats-mcp` is **not** a replacement for the [`unicefdata`](https://github.com/unicef-drp/unicefData) packages in Python, R, or Stata. They serve different audiences:

| | unicefstats-mcp | unicefdata (Python/R/Stata) |
|---|---|---|
| **Audience** | AI assistants (Claude, Cursor, Copilot) | Data scientists, researchers, analysts |
| **Interface** | MCP protocol (tool calls via JSON) | Native language API (`library()`, `import`, `ssc install`) |
| **Use case** | Conversational data exploration, quick lookups, AI-assisted analysis | Reproducible research, ETL pipelines, statistical analysis |
| **Output** | JSON (compact or full) optimized for LLM context | DataFrames, tibbles, Stata matrices |
| **Scripting** | No — single queries via AI chat | Yes — full programmatic control, loops, joins, transforms |
| **Caching** | Delegates to unicefdata | Built-in SDMX response caching |
| **Bulk download** | Limited (max 500 rows per call) | Unlimited — designed for full dataset pulls |

**Under the hood**, `unicefstats-mcp` wraps the `unicefdata` Python package. Every tool call ultimately calls `unicefdata.unicefData()` or its metadata functions. Think of the MCP as a thin AI-friendly interface on top of the same data layer.

**When to use which:**
- Use **unicefstats-mcp** when you're chatting with an AI and want to quickly explore indicators, check values, or compare countries
- Use **unicefdata** (Python/R/Stata) when you're writing scripts, building dashboards, running regressions, or doing any reproducible analytical work

## How it compares to other data MCPs

| Feature | unicefstats-mcp | FRED MCP | World Bank MCP |
|---|---|---|---|
| **Tools** | 8 (search → metadata → data → code → identity) | 3 (browse → search → get) | 1 (get only) |
| **Indicators** | 790+ child-focused indicators | 800,000+ economic series | ~1,600 indicators |
| **Countries** | 200+ (ISO3) | US-focused (some intl) | 200+ (ISO2) |
| **Disaggregations** | Sex, age, wealth quintile, residence | Frequency, seasonal adjustment | None |
| **MCP Prompt** | `compare_indicators` | None | None |
| **Output modes** | Compact (5 cols) / Full (all cols) | JSON | CSV |
| **Data summary** | Value range, year range, country count | None | None |
| **Pagination metadata** | `total_rows_available` vs `rows_returned` | `limit`/`offset` | None (hardcoded 20K) |
| **Input validation** | ISO3, sex, wealth, residence validated | Zod schemas | None |
| **Error guidance** | `error` + `tip` with next steps | HTTP status text | Raw exception |
| **API key** | Not required | FRED_API_KEY required | Not required |
| **Truncation handling** | `rows_truncated` flag + filter tips | None | None |

## Landscape: MCP servers for official statistics

This project is part of a growing ecosystem of MCP servers for international and official statistics. As of March 2026:

### UN Agencies
| Server | Data Source | Tools | SDMX | Published |
|---|---|---|---|---|
| **unicefstats-mcp** (this repo) | UNICEF Data Warehouse | 7 | Yes | PyPI |
| [sdmx-mcp](https://github.com/unicef-drp/sdmx-mcp) | Any SDMX registry | 23 | Yes | No |
| [unicef-datawarehouse-mcp](https://github.com/tryolabs/unicef-datawarehouse-mcp) | UNICEF Data Warehouse | 3 | Yes | No |
| [mcp_unhcr](https://github.com/rvibek/mcp_unhcr) | UNHCR refugee data | 5 | No | No |
| [medical-mcp](https://github.com/JamesANZ/medical-mcp) | WHO GHO / FDA / PubMed | 18 | No | npm |

### International Organizations
| Server | Data Source | Tools | SDMX | Published |
|---|---|---|---|---|
| [fred-mcp-server](https://github.com/stefanoamorelli/fred-mcp-server) | FRED (800K+ series) | 3 | No | npm |
| [world_bank_mcp_server](https://github.com/anshumax/world_bank_mcp_server) | World Bank Open Data | 1 | No | No |
| [imf-data-mcp](https://github.com/c-cf/imf-data-mcp) | IMF (IFS, BOP, WEO) | 10 | Yes | PyPI |
| [OECD-MCP](https://github.com/isakskogstad/OECD-MCP) | OECD (5,000+ datasets) | 9 | Yes | npm |
| [eurostat-mcp](https://github.com/ano-kuhanathan/eurostat-mcp) | Eurostat EU statistics | 7 | Yes | No |

### National Statistics Offices
| Server | Data Source | Tools | Published |
|---|---|---|---|
| [us-census-bureau-data-api-mcp](https://github.com/uscensusbureau/us-census-bureau-data-api-mcp) | US Census Bureau (official) | 5 | No |
| [us-gov-open-data-mcp](https://github.com/lzinga/us-gov-open-data-mcp) | 40+ US Gov APIs | 300+ | npm |
| [ibge-br-mcp](https://github.com/SidneyBissoli/ibge-br-mcp) | Brazil IBGE (227 tests) | 22 | npm |
| [ukrainian-stats-mcp-server](https://github.com/VladyslavMykhailyshyn/ukrainian-stats-mcp-server) | Ukraine SDMX v3 | 8 | npm |
| [istat_mcp_server](https://github.com/ondata/istat_mcp_server) | Italy ISTAT SDMX | 7 | No |

### Known gaps
No MCP server exists for: **FAO/FAOSTAT**, **UNESCO/UIS** (4,000+ education indicators), **ILO/ILOSTAT**, **UNSD SDG API**, **UN DESA Population**, **UNDP/HDI**.

Full directory with install commands: [MCP-DIRECTORY-STATS.md](https://github.com/jpazvd/unicefstats-mcp/blob/main/examples/MCP-DIRECTORY-STATS.md)

## Relationship to sdmx-mcp

UNICEF also maintains [`sdmx-mcp`](https://github.com/unicef-drp/sdmx-mcp), a generic SDMX protocol MCP server. The two servers are **complementary, not competing**:

| | unicefstats-mcp (this repo) | [sdmx-mcp](https://github.com/unicef-drp/sdmx-mcp) |
|---|---|---|
| **Scope** | UNICEF child development data only | Any SDMX registry (UNICEF, Eurostat, OECD, ...) |
| **Tools** | 7 (analyst-friendly, 4-step workflow) | 23 (SDMX power-user, structural queries) |
| **Data layer** | Wraps `unicefdata` Python package | Direct SDMX REST API calls via `httpx` |
| **Output** | Formatted for LLMs (compact tables, summaries, tips) | Raw SDMX-JSON/CSV |
| **Accuracy (EQA)** | **0.990** | 0.074 |
| **Hallucination** | 7% T1 / 34% T2 | **0% T1 / 0% T2** |
| **Cost per query** | $0.018 | $0.087 |
| **Latency** | 9.8s avg | 60s avg |

**Key tradeoff**: unicefstats-mcp is dramatically more accurate (EQA 0.990 vs 0.074) because its formatted output is optimized for LLM parsing. sdmx-mcp has zero hallucination because its `assistant_guidance` fields and `validate_query_scope` pattern effectively prevent fabrication when data is absent.

**When to use which:**
- Use **unicefstats-mcp** for UNICEF child development analysis — it's simpler, faster, and far more accurate
- Use **sdmx-mcp** when you need to query non-UNICEF SDMX registries, explore dataflow structures, or work with hierarchical codelists

Full 3-way benchmark (LLM alone vs unicefstats-mcp vs sdmx-mcp): [examples/results/](https://github.com/jpazvd/unicefstats-mcp/tree/main/examples/results/)

## Quick Start

```bash
pip install unicefstats-mcp
```

### Claude Code

Add to `~/.claude/.mcp.json`:

```json
{
  "mcpServers": {
    "unicefstats": {
      "command": "unicefstats-mcp"
    }
  }
}
```

### Cursor / VS Code

Add to your MCP settings:

```json
{
  "unicefstats": {
    "command": "unicefstats-mcp"
  }
}
```

## Tools

| Tool | Purpose | API call? |
|---|---|---|
| `search_indicators(query, limit)` | Find indicators by keyword | No |
| `list_categories()` | Browse thematic groups (CME, NUTRITION, EDUCATION, ...) | No |
| `list_countries(region)` | List countries with ISO3 codes | No |
| `get_indicator_info(code)` | Full metadata, SDMX details, available disaggregations | No |
| `get_temporal_coverage(code)` | Available year range and country count | Yes (lightweight) |
| `get_data(indicator, countries, ...)` | Fetch observations with optional disaggregation filters | Yes |
| `get_api_reference(language, function)` | unicefdata package API reference (Python/R/Stata) | No |
| `get_server_metadata()` | Server identity, version, provenance, data source | No |

### Workflow

```
1. search_indicators("child mortality")     → find indicator codes
2. get_indicator_info("CME_MRY0T4")         → check disaggregations & SDMX details
3. get_temporal_coverage("CME_MRY0T4")      → check year range
4. get_data("CME_MRY0T4", ["BRA", "IND"])   → fetch data
5. get_api_reference("python", "unicefData") → get code template to continue in a script
```

## Demo

### Step 1: Search for indicators

```
>>> search_indicators("stunting", limit=3)
```
```json
{
  "query": "stunting",
  "total_matches": 11,
  "showing": 3,
  "results": [
    {"code": "FD_STUNTING", "name": "Moderate and severe stunting (Functional difficulties)"},
    {"code": "NT_ANT_HAZ_NE2", "name": "Height-for-age <-2 SD (stunting)"},
    {"code": "NT_ANT_HAZ_NE3", "name": "Height-for-age <-3 SD (severe stunting)"}
  ],
  "tip": "Use get_indicator_info('FD_STUNTING') for full details including available disaggregations."
}
```

### Step 2: Get indicator metadata

```
>>> get_indicator_info("CME_MRY0T4")
```
```json
{
  "code": "CME_MRY0T4",
  "name": "Under-five mortality rate",
  "description": "Probability of dying between birth and exactly 5 years of age, expressed per 1,000 live births",
  "dataflow": "GLOBAL_DATAFLOW",
  "sdmx_api": "https://sdmx.data.unicef.org/ws/public/sdmxapi/rest/data/UNICEF,GLOBAL_DATAFLOW,1.0/.CME_MRY0T4?format=csv",
  "disaggregation_filters": {
    "sex": ["_T (Total)", "M (Male)", "F (Female)"],
    "wealth_quintile": ["Q1 (Lowest)", "Q2", "Q3", "Q4", "Q5 (Highest)"],
    "residence": ["_T (Total)", "U (Urban)", "R (Rural)"]
  }
}
```

### Step 3: Check temporal coverage

```
>>> get_temporal_coverage("CME_MRY0T4")
```
```json
{
  "code": "CME_MRY0T4",
  "start_year": 1931,
  "end_year": 2024,
  "latest_year": 2024,
  "countries_with_data": 249,
  "note": "Not all countries have data for all years. Coverage varies by country."
}
```

### Step 4: Fetch data

```
>>> get_data("CME_MRY0T4", ["BRA", "IND", "NGA"], start_year=2018, end_year=2023)
```
```json
{
  "indicator": "CME_MRY0T4",
  "countries_requested": ["BRA", "IND", "NGA"],
  "total_rows_available": 18,
  "rows_returned": 18,
  "rows_truncated": false,
  "format": "compact",
  "summary": {
    "value_range": {"min": 14.42, "max": 117.56, "mean": 54.78},
    "year_range": {"earliest": 2018, "latest": 2023},
    "countries_in_result": 3
  },
  "data": [
    {"iso3": "BRA", "country": "Brazil",  "period": 2018, "indicator": "CME_MRY0T4", "value": 15.22},
    {"iso3": "BRA", "country": "Brazil",  "period": 2019, "indicator": "CME_MRY0T4", "value": 15.03},
    {"iso3": "BRA", "country": "Brazil",  "period": 2020, "indicator": "CME_MRY0T4", "value": 14.87},
    {"iso3": "BRA", "country": "Brazil",  "period": 2021, "indicator": "CME_MRY0T4", "value": 14.72},
    {"iso3": "BRA", "country": "Brazil",  "period": 2022, "indicator": "CME_MRY0T4", "value": 14.59},
    {"iso3": "BRA", "country": "Brazil",  "period": 2023, "indicator": "CME_MRY0T4", "value": 14.42},
    {"iso3": "IND", "country": "India",   "period": 2018, "indicator": "CME_MRY0T4", "value": 36.87},
    {"iso3": "IND", "country": "India",   "period": 2019, "indicator": "CME_MRY0T4", "value": 34.86},
    {"iso3": "IND", "country": "India",   "period": 2020, "indicator": "CME_MRY0T4", "value": 32.98},
    {"iso3": "IND", "country": "India",   "period": 2021, "indicator": "CME_MRY0T4", "value": 31.19},
    {"iso3": "IND", "country": "India",   "period": 2022, "indicator": "CME_MRY0T4", "value": 29.53},
    {"iso3": "IND", "country": "India",   "period": 2023, "indicator": "CME_MRY0T4", "value": 27.99},
    {"iso3": "NGA", "country": "Nigeria", "period": 2018, "indicator": "CME_MRY0T4", "value": 117.19},
    {"iso3": "NGA", "country": "Nigeria", "period": 2019, "indicator": "CME_MRY0T4", "value": 117.37},
    {"iso3": "NGA", "country": "Nigeria", "period": 2020, "indicator": "CME_MRY0T4", "value": 117.42},
    {"iso3": "NGA", "country": "Nigeria", "period": 2021, "indicator": "CME_MRY0T4", "value": 117.56},
    {"iso3": "NGA", "country": "Nigeria", "period": 2022, "indicator": "CME_MRY0T4", "value": 117.46},
    {"iso3": "NGA", "country": "Nigeria", "period": 2023, "indicator": "CME_MRY0T4", "value": 116.82}
  ]
}
```

Key insights an AI assistant would extract from this:
- **Brazil**: 14.4 per 1,000 — steadily declining, on track for SDG 3.2 target (≤25)
- **India**: 28.0 per 1,000 — rapid improvement (37→28 in 5 years), recently crossed SDG target
- **Nigeria**: 117 per 1,000 — essentially flat, 4.7× the SDG target, highest burden

### Step 5: Get code template to continue in a script

```
>>> get_api_reference("r", "unicefData")
```
```json
{
  "language": "r",
  "install": "install.packages(\"unicefdata\")",
  "import": "library(unicefdata)",
  "function": "unicefData",
  "signature": "unicefData(\n    indicator = NULL,        # character — indicator code(s)\n    countries = NULL,         # character vector — ISO3 codes, NULL = all\n    year = NULL,              # numeric, character (\"2015:2023\"), or vector\n    sex = \"_T\",               # character — \"_T\", \"M\", \"F\"\n    totals = FALSE,           # logical — only return aggregate totals\n    tidy = TRUE,              # logical — standardize column names\n    country_names = TRUE,     # logical — add country name column\n    format = \"long\",          # character — \"long\", \"wide\", \"wide_indicators\"\n    latest = FALSE,           # logical — most recent value per country\n    circa = FALSE,            # logical — closest available year\n    add_metadata = NULL,      # character vector — e.g. c('region', 'income_group')\n    dropna = FALSE,           # logical — drop rows with missing values\n    simplify = FALSE,         # logical — minimal columns\n    mrv = NULL,               # integer — most recent N values per country\n    raw = FALSE,              # logical — all disaggregations, no filtering\n)",
  "returns": "tibble with columns: indicator_code, iso3, country, period, value, sex, age, wealth_quintile, residence, ...",
  "examples": [
    {"description": "Under-5 mortality for Brazil, India, Nigeria (2015–2023)", "code": "df <- unicefData(\"CME_MRY0T4\", countries = c(\"BRA\", \"IND\", \"NGA\"), year = \"2015:2023\")"},
    {"description": "Latest stunting data for all countries", "code": "df <- unicefData(\"NT_ANT_HAZ_NE2\", latest = TRUE)"},
    {"description": "Wide format with region metadata", "code": "df <- unicefData(\"CME_MRY0T4\", format = \"wide\", add_metadata = c(\"region\", \"income_group\"))"}
  ]
}
```

This lets the AI generate correct R/Python/Stata code using the exact parameter names and syntax — no guessing from training data.

### get_data parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `indicator` | str | required | Indicator code |
| `countries` | list[str] | required | ISO3 codes (max 30) |
| `start_year` | int | None | Start of year range |
| `end_year` | int | None | End of year range |
| `sex` | str | "_T" | "_T" (total), "M" (male), "F" (female) |
| `wealth_quintile` | str | None | "Q1"–"Q5", "B20", "B40", "T20" |
| `residence` | str | None | "U" (urban), "R" (rural), "_T" (total) |
| `format` | str | "compact" | "compact" (5 cols) or "full" (all cols) |
| `limit` | int | 200 | Max rows (1–500) |

### Response features

- **`summary`**: Value range (min/max/mean), year range, country count
- **`disaggregations_in_data`**: Which dimensions have non-trivial variation
- **`total_rows_available`** vs **`rows_returned`**: Pagination metadata
- **`tip`**: Contextual guidance for next steps or narrowing results

## Prompts

### compare_indicators

Pre-built analysis workflow: fetches indicator metadata and data, then produces a structured comparison.

```
compare_indicators(indicator="CME_MRY0T4", countries="BRA,IND,NGA", start_year="2015", end_year="2023")
```

### write_unicefdata_code

Generate runnable Python, R, or Stata code using the `unicefdata` package. The AI will call `get_api_reference()` to get the exact function signatures, then write code matching the user's task.

```
write_unicefdata_code(
    task="Compare under-5 mortality for Brazil and India, 2015-2023, then plot the trends",
    language="r"
)
```

This bridges the gap between conversational exploration (via MCP tools) and reproducible analysis scripts (via unicefdata packages).

## Benchmark Results

We benchmarked the MCP against a bare LLM (Claude Sonnet 4, no tools) using the [EQA metric](https://github.com/jpazvd/unicefstats-mcp/blob/main/examples/RESULTS.md) from Azevedo (2025). 300 queries across 10 indicators, 20 countries, 2 prompt types, and 2 hallucination test categories.

### Headline numbers

| Metric | LLM alone | LLM + MCP | Improvement |
|---|---|---|---|
| EQA ("latest" prompt) | 0.172 | **0.984** | 5.7× |
| EQA ("direct" prompt) | 0.121 | **0.995** | 8.2× |
| Indicators at EQA >= 0.95 | 0/10 | **10/10** | — |
| T1 hallucination (gap years) | 9% | 7% | -2pp |
| T2 hallucination (never existed) | 11% | 37% raw / ~10% corrected | See analysis |
| Cost per query | $0.003 | $0.018 | 6× |

### EQA decomposition (baseline_latest prompt)

| Component | LLM alone | LLM + MCP | Gain |
|---|---|---|---|
| ER (extraction rate) | 0.50 | **1.00** | +0.50 |
| YA (year accuracy) | 0.24 | **0.99** | +0.75 |
| VA (value accuracy) | 0.37 | **1.00** | +0.63 |
| **EQA = ER × YA × VA** | **0.147** | **0.990** | **+0.843** |

### Key findings

1. **All 10 indicators at EQA >= 0.95** with MCP, replicated across 40 countries (R1 + R2 with zero overlap). 7 of 10 achieve perfect EQA = 1.000.

2. **Year accuracy is the bare LLM's biggest weakness** (YA = 0.24). It cites 2021-2022 as "latest" when IGME 2024 estimates exist. The MCP queries the API and returns the actual latest year.

3. **The direct prompt shows larger MCP gain** (+0.722 vs +0.613) because it eliminates YA and isolates pure retrieval accuracy.

4. **T2 hallucination (~37%) is inflated by ground truth misclassification**: the SDMX API has IGME mortality data for micro-states that the ground truth pipeline missed. After correction: MCP ~10%, LLM alone ~5%. The remaining hallucination is driven by the **confidence effect** — Claude overrides tool errors when it has strong domain priors.

5. **The confidence effect**: When the MCP tool returns "no data" but the LLM has strong domain priors (e.g., child mortality for well-known countries), it overrides the tool and fabricates anyway. This is a fundamental LLM behavior, not MCP-specific.

### 3-way comparison (vs sdmx-mcp)

| Metric | LLM alone | unicefstats-mcp | sdmx-mcp |
|---|---|---|---|
| **EQA (all positive)** | 0.147 | **0.990** | 0.074 |
| T1 hallucination | 9% | 7% | **0%** |
| T2 hallucination | 11% | 37% | **0%** |
| Cost (300 queries) | $0.89 | $5.47 | $26.20 |
| Avg latency | 5s | 9.8s | 60s |

sdmx-mcp's raw SDMX-JSON output is hard for LLMs to parse (VA = 0.11), but its anti-hallucination guardrails are highly effective (0% fabrication). See [Relationship to sdmx-mcp](#relationship-to-sdmx-mcp) for details.

Full analysis, per-indicator decomposition, and methodology: **[examples/RESULTS.md](https://github.com/jpazvd/unicefstats-mcp/blob/main/examples/RESULTS.md)**

Benchmark data (parquet with full LLM responses): **[examples/results/](https://github.com/jpazvd/unicefstats-mcp/tree/main/examples/results/)**

Benchmark design rationale: **[examples/DESIGN_ISSUES.md](https://github.com/jpazvd/unicefstats-mcp/blob/main/examples/DESIGN_ISSUES.md)**

### Reproducing the benchmark

```bash
# Build ground truth from UNICEF SDMX API
python examples/00_build_ground_truth.py

# Run 200-query benchmark (requires ANTHROPIC_API_KEY, ~$6)
python examples/benchmark_eqa.py

# Add 100 direct-prompt queries to existing run (~$3)
python examples/01_run_direct_supplement.py
```

### Citation

This benchmark uses the EQA metric from:

> Azevedo, J.P. (2025). "AI Reliability for Official Statistics: Benchmarking Large Language Models with the UNICEF Data Warehouse." UNICEF Chief Statistician Office. [github.com/jpazvd/unicef-sdg-llm-benchmark-dev](https://github.com/jpazvd/unicefstats-mcp/blob/main/examples/RESULTS.md)

## Deployment

### Local (stdio)

```bash
unicefstats-mcp
```

### Remote (SSE)

```bash
unicefstats-mcp --transport sse --port 8000
```

### Docker

```bash
docker build -t unicefstats-mcp .
docker run -p 8000:8000 unicefstats-mcp
```

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -v
ruff check src/ tests/
mypy src/unicefstats_mcp/
```

## Contributing

Contributions are welcome! This project is in alpha and there is plenty of room for improvement.

### Ways to contribute

- **Bug reports**: Open an [issue](https://github.com/jpazvd/unicefstats-mcp/issues) with steps to reproduce
- **Feature requests**: Suggest new tools, indicators, or output formats via issues
- **Code**: Fork, branch, submit a PR — see development setup below
- **Benchmark**: Run the EQA benchmark on different models and share results
- **Documentation**: Improve examples, fix typos, add use cases

### Development setup

```bash
git clone https://github.com/jpazvd/unicefstats-mcp.git
cd unicefstats-mcp
pip install -e ".[dev,benchmark]"
pytest tests/ -v
ruff check src/ tests/
mypy src/unicefstats_mcp/
```

### Pull request guidelines

1. **One concern per PR** — keep changes focused and reviewable
2. **Include tests** for new tools or bug fixes
3. **Run the linter** (`ruff check`) and type checker (`mypy`) before submitting
4. **Update the README** if you change tool signatures or add new features
5. **Do not commit API keys** or benchmark result parquets larger than 500KB

### Priority areas

See the [audit findings](https://github.com/jpazvd/unicefstats-mcp/blob/main/examples/RESULTS.md) for known issues. High-impact areas:

- **MNCH dataflow bug**: `MNCH_CSEC` and `MNCH_BIRTH18` return 0 EQA due to a dataflow resolution issue in the `unicefdata` package
- **Anti-hallucination**: Adopt sdmx-mcp's `assistant_guidance` pattern to reduce T2 hallucination
- **Test coverage**: `list_countries`, `get_api_reference`, and MCP prompts are untested
- **MCP Resources**: Add indicator registry and country list as MCP Resources (reduces tool calls)

## Provenance and Ownership

| Property | Value |
|---|---|
| **Publisher / maintainer** | Joao Pedro Azevedo ([`jpazvd`](https://github.com/jpazvd)) |
| **Canonical source** | [github.com/jpazvd/unicefstats-mcp](https://github.com/jpazvd/unicefstats-mcp) |
| **Canonical package** | [pypi.org/project/unicefstats-mcp](https://pypi.org/project/unicefstats-mcp/) |
| **Registry identity** | `io.github.jpazvd/unicefstats-mcp` |
| **Publishing** | GitHub Actions via [Trusted Publishing](https://docs.pypi.org/trusted-publishers/) (OIDC) |
| **Status** | Independent research prototype — not an official UNICEF product |

All releases are published exclusively from GitHub Actions using PyPI Trusted Publishing. No long-lived API tokens are used. To verify a release's provenance, check the [PyPI attestations](https://pypi.org/project/unicefstats-mcp/#files) for the release files.

For a detailed account of data origin, ownership, distribution pipeline, verification steps, and interpretation caveats, see [PROVENANCE.md](PROVENANCE.md).

## How to Verify This MCP

Use these steps to confirm you are using the authentic `unicefstats-mcp` and that versions are consistent across the supply chain.

### 1. Source repository

Verify the canonical repository owner and URL:
- Owner: [`jpazvd`](https://github.com/jpazvd) on GitHub
- Repository: [github.com/jpazvd/unicefstats-mcp](https://github.com/jpazvd/unicefstats-mcp)

### 2. PyPI package

```bash
pip show unicefstats-mcp
```

Check that `Home-page` points to `https://github.com/jpazvd/unicefstats-mcp`.

### 3. Version alignment

All version references should match:

```bash
# Python package version
python -c "import unicefstats_mcp; print(unicefstats_mcp.__version__)"

# PyPI published version
pip index versions unicefstats-mcp 2>/dev/null || pip show unicefstats-mcp | grep Version
```

Compare with the `version` field in [`server.json`](server.json) and [`pyproject.toml`](pyproject.toml).

### 4. Release provenance (PyPI attestations)

Visit [pypi.org/project/unicefstats-mcp/#files](https://pypi.org/project/unicefstats-mcp/#files) and check that release files have attestations linking to the GitHub Actions publishing workflow.

### 5. Runtime verification

Call the `get_server_metadata()` tool at runtime to get machine-readable identity and provenance:

```json
{
  "name": "io.github.jpazvd/unicefstats-mcp",
  "version": "0.4.0",
  "canonical_source": "https://github.com/jpazvd/unicefstats-mcp",
  "registry_identity": "io.github.jpazvd/unicefstats-mcp"
}
```

### 6. MCP registry (future)

When MCP registries become available, verify the `io.github.jpazvd/unicefstats-mcp` namespace is owned by the `jpazvd` GitHub account.

## License

MIT
