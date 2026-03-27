# Changelog

All notable changes to unicefstats-mcp are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/).

## [0.3.0] — 2026-03-26

### Benchmark Results (v0.3.0 + unicefdata v2.4.0)
- **EQA = 0.990** across 400 positive queries (200 R1 + 200 R2, 40 countries, 0 overlap)
- **All 10 indicators at EQA >= 0.95** — 7 of 10 at perfect 1.000
- **Replicated**: R1 EQA = 0.990, R2 EQA = 0.990 (independent country samples)
- **T1 hallucination**: 7% (down from 14% in v0.2.0)
- **T2 hallucination**: 37% raw / ~10% corrected (down from 38% in v0.2.0)
- **Cost**: $0.018/query (down 24% from $0.024 in v0.2.0, due to fewer tool rounds)
- **3-way comparison**: unicefstats-mcp (EQA 0.990) vs sdmx-mcp (0.074) vs bare LLM (0.147)

### Added
- **4 MCP Resources** — preloaded reference data, no tool call needed ([OECD-MCP](https://github.com/isakskogstad/OECD-MCP) pattern)
  - `unicef://llm-instructions` — DO/DON'T rules, workflow guide, common mistakes, indicator families
  - `unicef://categories` — all indicator categories with counts
  - `unicef://countries` — ISO3 codes and names
  - `unicef://glossary` — disaggregation codes, indicator prefixes, data notes
- **Source citations** in every `get_data()` response — verifiable SDMX API URL and web link to data.unicef.org ([US Census Bureau MCP](https://github.com/uscensusbureau/us-census-bureau-data-api-mcp) pattern)
- **Retry with exponential backoff** for SDMX API calls — 3 attempts, 1s/2s/4s delays, skips 404s ([IBGE Brazil MCP](https://github.com/SidneyBissoli/ibge-br-mcp) pattern)
- **SSE transport** option for remote deployment (`--transport sse --port 8000`)
- **Status field** in all responses — `status: "ok"` or `status: "error"` for unambiguous LLM parsing
- **Indicator code validation** — rejects empty/whitespace/too-long codes before API call
- **Year range validation** — rejects years outside 1900–2100
- **NaN/inf cleaning** — `_clean_nans()` ensures valid JSON in all DataFrame-based responses
- **Type annotations** — `_get_ud() -> types.ModuleType`, mypy overrides for unicefdata/fastmcp
- **3-way benchmark** — Condition C (sdmx-mcp) added to existing A/B benchmark
- **Synonym expansion** in `search_indicators` — "births under 18" → MNCH_BIRTH18, "caesarean" → MNCH_CSEC, "teenage pregnancy" → MNCH_BIRTH18, plus 20+ common term mappings
- **Configurable benchmark** — `BENCHMARK_SEED`, `BENCHMARK_OUTPUT_DIR`, `BENCHMARK_COUNTRIES=R2` environment variables for reproducible replication runs
- **B-only benchmark script** (`03_rerun_condition_b.py`) — reuses existing A responses, runs only MCP condition

### Fixed
- `if start_year` → `if start_year is not None` — year=0 was silently ignored
- Non-numeric period values in `get_temporal_coverage` — now extracts 4-digit year prefix as fallback
- Tool extraction took oldest row instead of latest in `_extract_from_tool_calls`

### Changed
- Country column detection extracted to `country_col()` helper (was duplicated in 3 places)
- Version bump: `__init__.py`, `server.py`, `pyproject.toml` all at 0.3.0

### Documentation
- **Experimental/Research Prototype** disclaimer with human-in-the-loop warning
- **CONTRIBUTING.md** — dev setup, code style, commit conventions, PR template
- **CODE_OF_CONDUCT.md** — Contributor Covenant v2.1
- **Issue/PR templates** — bug report, feature request, PR checklist
- **Landscape section** in README — 20 official statistics MCP servers compared
- **Relationship to sdmx-mcp** section with 3-way benchmark table
- **Related work bibliography** — 15 papers on tool-augmented hallucination
- **5 publication figures** (PNG + SVG) and statistical analysis script
- **MCP-DIRECTORY-STATS.md** — comprehensive directory of all stats MCP servers

## [0.2.0] — 2026-03-23

### Added
- **EQA benchmark pipeline** — ground truth from UNICEF SDMX API, Anthropic API calls for both conditions
  - `00_build_ground_truth.py` — fetches, classifies, samples 300 queries
  - `benchmark_eqa.py` — runs A/B benchmark, saves to parquet
  - `01_run_direct_supplement.py` — adds direct-prompt queries to existing run
- **Parquet output** with 48 columns including full LLM responses
- **Anti-hallucination directive** — `confirmed_absent` status with explicit instruction not to fabricate
- **Semantic context** in `get_indicator_info()` — related indicators, disambiguation, SDG targets, methodology
- **Trend computation** — 5-year annualized rate of change (AARC) in `get_data()` responses
- **Balanced sampling** — 20 queries per indicator (10 latest + 5 T1 + 5 T2)
- **Refusal detection** in value extraction pipeline

### Results
- **v1.3 definitive**: EQA = 0.785 (latest), 0.843 (direct) — 7/10 indicators at perfect 1.000
- **Wilcoxon signed-rank**: p = 1.64e-14, Cohen's d = 1.34 (large effect)
- **T2 hallucination**: 38% (MCP) vs 12% (alone) — driven by ground truth misclassification

## [0.1.0] — 2026-03-22

### Added
- Initial scaffold — 7 MCP tools + 2 prompts wrapping the `unicefdata` Python package
- Tools: `search_indicators`, `list_categories`, `list_countries`, `get_indicator_info`, `get_temporal_coverage`, `get_data`, `get_api_reference`
- Prompts: `compare_indicators`, `write_unicefdata_code`
- `formatters.py` — compact/full output, truncation, pagination, data summary
- `validators.py` — ISO3, sex, residence, wealth quintile validation
- `indicator_context.py` — related indicators, SDG targets, methodology
- `reference.py` — unicefdata API reference for Python, R, Stata
- Tests (pytest), linting (ruff), type checking (mypy)
- Docker support, PyPI packaging
- README with demo, comparison tables, deployment guide

### Sources and influences
- **EQA metric**: Azevedo, J.P. (2025). "AI Reliability for Official Statistics." [RESULTS.md](https://github.com/jpazvd/unicefstats-mcp/blob/main/examples/RESULTS.md)
- **MCP design**: [FastMCP](https://github.com/jlowin/fastmcp) framework
- **Data layer**: [unicefdata](https://github.com/unicef-drp/unicefData) Python package
