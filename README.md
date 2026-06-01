<!-- mcp-name: io.github.jpazvd/unicefstats-mcp -->
[![MCP Badge](https://lobehub.com/badge/mcp/jpazvd-unicefstats-mcp?style=for-the-badge)](https://lobehub.com/mcp/jpazvd-unicefstats-mcp)

[![PyPI](https://img.shields.io/pypi/v/unicefstats-mcp.svg)](https://pypi.org/project/unicefstats-mcp/)
[![Python](https://img.shields.io/pypi/pyversions/unicefstats-mcp.svg)](https://pypi.org/project/unicefstats-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Downloads](https://static.pepy.tech/badge/unicefstats-mcp)](https://pepy.tech/projects/unicefstats-mcp)

# unicefstats-mcp

> Experimental — not an official UNICEF product. Verify retrieved values against the [UNICEF Data Warehouse](https://data.unicef.org/) before citing in publications. See [Limitations](#limitations-and-hallucination-risks).

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
| **Maintainer** | Joao Pedro Azevedo ([`jpazvd`](https://github.com/jpazvd)) |
| **Status** | Experimental — not endorsed by UNICEF |

> Third-party aggregator listings (LobeHub, Smithery, mcp.so, Glama) are not controlled by the maintainer. Verify against the canonical source above.

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
- [Limitations and Hallucination Risks](#limitations-and-hallucination-risks)
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
| [examples/mcp-smoke-test/MULTIMODEL_SMOKETEST.md](https://github.com/jpazvd/unicefstats-mcp/blob/main/examples/mcp-smoke-test/MULTIMODEL_SMOKETEST.md) | Cross-model smoke test (Anthropic / OpenAI / Google / OpenRouter) for the v0.7.3 cross-provider generalisation question — design, rubric, ~$1 default run, path to full mini-EQA |

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
| **Tools** | 9 (search → metadata → data → code → identity + strict canonical lookup) | 3 (browse → search → get) | 1 (get only) |
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
| **Accuracy (EQA)** | **0.891** (v0.7.3 + fixes) | 0.074 |
| **Hallucination** | hall_b 1.00% (mcp060) / 2.25% (mcp073) — below the no-tools hall_a baseline (2.50%) | **0% T1 / 0% T2** |
| **Cost per query** | ~$0.04 | $0.087 |
| **Latency** | ~10s avg | 60s avg |

**Key tradeoff**: unicefstats-mcp is dramatically more accurate (EQA 0.891 vs 0.074) because its formatted output is optimized for LLM parsing. sdmx-mcp achieves zero hallucination on absent-data queries through aggressive `assistant_guidance` fields and a `validate_query_scope` pattern; its accuracy floor is too low to be useful, but the refusal discipline is exemplary. unicefstats-mcp v0.7.3 + fixes is the first version where MCP demonstrably makes the model safer than the no-tools baseline on absent-data queries (hall_b < hall_a), achieved without sdmx-mcp's accuracy cost.

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

## What v1.1.0 adds

v1.1.0 is **additive**: v1.0.0's `ambiguity_flag`, `candidates`, and `abstain_instruction` still fire unchanged on ambiguous queries. v1.1.0 layers four new advisory envelope fields on top:

- `requires_confirmation` — true when the server wants the assistant to pause for user input
- `recommended` — the server's preferred next action (code, country, year, or tool)
- `assistant_guidance` — short natural-language hint the LLM can paraphrase
- `next_step` — a structured tool/parameter suggestion the LLM can chain into

**Decision order** (4 stages): strict canonical lookup → ambiguity check (v1.0.0 fields) → confirmation gate (`requires_confirmation`) → advisory hints (`recommended` / `assistant_guidance` / `next_step`).

**Verdict: ALLOW** (no behavioural regression; advisory fields fire on 23/30 Sonnet and 26/30 Haiku paired stuck queries; see `internal/v1.1.0_design/ab_results.md`).

## Tools

| Tool | Purpose | API call? |
|---|---|---|
| `search_indicators(query, limit)` | Find indicators by keyword | No |
| `list_categories()` | Browse thematic groups (CME, NUTRITION, EDUCATION, ...) | No |
| `list_countries(region)` | List countries with ISO3 codes | No |
| `get_indicator_info(code)` | Full metadata, SDMX details, available disaggregations | No |
| `lookup_by_code(code)` | **v1.0.0** Strict canonical-code lookup (rejects natural-language input with abstain instruction) | No |
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

## Resources

The server exposes six MCP resources clients can load for guidance and reference data:

| URI | Purpose |
|---|---|
| `unicef://system-prompt` | Recommended system prompt — operating loop + temporal-frontier check + anti-extrapolation directive (load at session start) |
| `unicef://llm-instructions` | Full DO/DON'T rules, common mistakes, and anti-fabrication guidance |
| `unicef://context` | Runtime context — `current_date` / `current_year` for temporal-query sanity checks |
| `unicef://categories` | All indicator categories with counts |
| `unicef://countries` | ISO3 codes and country names |
| `unicef://glossary` | Disaggregation codes and indicator-prefix legend |

The `system-prompt` and `context` resources address the T2 hallucination failure mode (model fabricating values for years beyond the data frontier). Pattern adopted from the World Bank [data360-mcp](https://github.com/worldbank/data360-mcp) server. See CHANGELOG entry for v0.5.0.

## Scope: UNICEF DW indicators only

`unicefstats-mcp` searches and serves the **UNICEF Data Warehouse SDMX catalog** — approximately 790 child-focused indicators across mortality, nutrition, education, child protection, WASH, HIV/AIDS, immunization, and early childhood development. Indicator codes follow UNICEF conventions (e.g. `CME_MRY0T4`, `NT_ANT_HAZ_NE2`, `ED_ANAR_L1`).

**Codes from other organisations are out of scope.** The MCP cannot find, resolve, or fetch them because they do not exist in the UNICEF SDMX catalog. Examples of out-of-scope code families:

| Source organisation | Prefix examples | Typical content |
|---|---|---|
| World Bank WDI | `SI.POV.DDAY`, `NY.GDP.PCAP.PP.KD`, `SE.PRM.NENR` | Poverty, GDP, broader education |
| World Bank ASPIRE | `per_allsp.cov_pop_tot`, `per_*` | Social protection coverage |
| ILO / ILOSTAT | `EIP_*`, `EAP_*`, `DF_*_SEX_RT` | Labour, employment, NEET |
| UNESCO UIS | `UIS.*` | Education finance, learning outcomes |

These codes will return no hits from `search_indicators` and a not-found error from `get_data`. The refusal is correct behaviour, not a bug.

**For cross-organisation queries, use a sister MCP:**

- [`data360-mcp`](https://github.com/worldbank/data360-mcp) — World Bank's multi-source aggregator covering WDI, ILO, UN, and other official providers under one tool surface.
- [`worldbank-mcp`](https://github.com/anshumax/world_bank_mcp_server) — World Bank Open Data only.

For SDMX power-user queries against arbitrary registries (Eurostat, OECD, national NSOs), see [`sdmx-mcp`](https://github.com/unicef-drp/sdmx-mcp) — the generic SDMX protocol server discussed under [Relationship to sdmx-mcp](#relationship-to-sdmx-mcp).

The scope boundary was sharpened in v1.1.1 after the v9 edge-test sample surfaced three prompts whose ground-truth codes (`SI.POV.DDAY`, `NY.GDP.PCAP.PP.KD`, `per_allsp.cov_pop_tot`) sit in the World Bank universe rather than the UNICEF Data Warehouse. Full write-up: `internal/v1.1.0_design/ambiguity_forensic.md` sections C-4 to C-6 (dev repo only).

## Understanding UNICEF indicator codes

### Why this matters — the MCP's semantic layer

UNICEF SDMX indicator codes look cryptic on first contact — `PT_F_20-24_MRD_U18`,
`NT_ANT_HAZ_NE2`, `TRGT_2030_IM_DTP3` — and most of an LLM's failure modes on this
data start with picking the wrong code. The single biggest piece of added value
this MCP offers over a raw SDMX endpoint is **exposing the semantic structure
inside those codes** so the assistant can disambiguate without guessing. The
implementation lives in `src/unicefstats_mcp/differentiator.py` (segment-level
suffix meanings and base/variant explanation) and
`src/unicefstats_mcp/indicator_resolver.py` (natural-language synonyms and known
ambiguous tokens). v1.1.1 added a query-aware `CURATED_PREFERRED` dimension_hint
that tells the resolver which code from a family to surface for a given phrasing
(e.g. "target" → `TRGT_*`, "modelled" → `*_MOD`, "child" → `_T` total rather
than a sex-disaggregated variant).

This section documents the conventions the MCP relies on so users and downstream
agents can read codes directly, and so reviewers can audit the resolver's choices.

### Anatomy of a UNICEF code

UNICEF DW codes are concatenations of dot-free, underscore-delimited segments,
read left-to-right from broadest to most specific. Take a layered protection
indicator from the catalog:

```
PT_F_20-24_MRD_U18
│  │ │     │   │
│  │ │     │   └── Marriage cutoff:        U18   = first union before age 18 (SDG 5.3.1)
│  │ │     └────── Indicator class:        MRD   = ever-married / in-union
│  │ └──────────── Age band (cohort):      20-24 = women 20-24 (retrospective denominator)
│  └────────────── Population restriction: F     = female-only indicator (women/girls)
└───────────────── Family prefix:          PT    = Child Protection
```

Read out loud: "Child Protection / female respondents / cohort aged 20-24 /
ever-married / before age 18" — i.e. the share of women aged 20-24 who were first
married before 18. Note that the `F` here is **not** a sex-disaggregation suffix
appended to a sex-neutral parent; it is a population-restriction marker built
into a family of indicators that only exist for female respondents (FGM, child
marriage, anaemia in women, antenatal care). See "Population restrictions vs sex
disaggregation" below.

The same left-to-right reading applies to the nutrition anthropometric pattern:

```
NT_ANT_HAZ_NE2
│  │   │   │
│  │   │   └── Threshold:    NE2 = below -2 SD (NE = "negative end", 2 = SD count)
│  │   └────── Metric:       HAZ = Height-for-Age Z-score
│  └────────── Sub-family:   ANT = Anthropometry
└───────────── Family:       NT  = Nutrition
```

`NT_ANT_HAZ_NE2` is the stunting prevalence indicator for children under 5. To
get the sex-stratified value, query the indicator with the `SEX` dimension
filter (`get_data(indicator='NT_ANT_HAZ_NE2', sex='F')`), not by appending `_F`
to the code — see the next subsection.

And the derived-metric pattern, which the v1.1.1 query-aware scoring is
specifically tuned for:

```
TRGT_2030_IM_DTP3
│    │    │  │
│    │    │  └──── Antigen / dose: DTP3 = third dose of DTP
│    │    └─────── Family:         IM   = Immunization
│    └──────────── Target year:    2030 = SDG horizon
└───────────────── Derived metric: TRGT = country-set target value
```

The combinatorial reading — family → sub-family → metric → threshold/age band →
disaggregation token — is the unwritten contract behind almost every code in the
catalog. The tables below enumerate the parts.

### Topic prefixes (families)

The first segment is the topical family. The top 10–12 prefixes in the catalog
cover the vast majority of child-focused indicators:

| Prefix | Meaning | Example code |
|---|---|---|
| `CME` | Child Mortality Estimates — mortality rates by age bracket (neonatal, infant, under-5, childhood, stillbirth) | `CME_MRY0T4` (under-5 mortality), `CME_SBR` (stillbirth rate) |
| `NT` | Nutrition — anthropometry, anaemia, birthweight, micronutrients | `NT_ANT_HAZ_NE2` (stunting), `NT_BW_LBW` (low birthweight) |
| `ED` | Education — completion rates, literacy, attendance by ISCED level | `ED_CR_L1` (primary completion), `ED_15-24_LR` (youth literacy) |
| `WS` | WASH — water, sanitation, hygiene; population-level access | `WS_PPL_W-SM` (safely managed water) |
| `IM` | Immunization — vaccine coverage by antigen / dose | `IM_BCG`, `IM_DTP3`, `IM_MCV1` |
| `MNCH` | Maternal, Newborn & Child Health — antenatal care, skilled birth attendance, early childbearing | `MNCH_ANC1`, `MNCH_SAB`, `MNCH_BIRTH18` |
| `ECD` | Early Childhood Development — learning materials, parental stimulation, attendance | `ECD_CHLD_LMPSL` (learning materials) |
| `PT` | Child Protection — FGM, child marriage, violent discipline | `PT_F_20-24_MRD_U18` (married before 18) |
| `HVA` | HIV/AIDS — ART coverage, prevalence, adolescent indicators | `HVA_ADOL_ART_RECEIVE` |
| `PV` | Child poverty — monetary and multidimensional | `PV` family |
| `COD` | Causes of death — disease- and condition-specific mortality / morbidity | `COD_ACUTE_HEPATITIS_A` |
| `DM` | Demography — household composition, population structure | `DM_HH_U18` (households with member under 18) |
| `MG` | Migration — child migrants, displacement | `MG` family |
| `GN` | Gender / adolescent girls (often cross-cuts NT) | `GN_ANEMIA_ADOL_GRL` |
| `TRGT` | Country-set targets (see "Derived metrics" below) | `TRGT_2030_*` |
| `HAZARD` | Hazard exposure (climate, conflict, disaster) | `HAZARD` family |

The full mapping of natural-language phrases to these prefixes lives in
`indicator_resolver._SYNONYMS` — e.g. "stunting" → `NT_ANT_HAZ_NE2`, "child
marriage" → `PT_F_20-24_MRD_U18`, "BCG" → `IM_BCG`.

### Methodology and provenance suffixes

A trailing segment often signals **how the value was produced**, not what was
measured. These suffixes are central to the v1.1.1 query-aware scoring because
users almost always want either "survey" or "modelled" but rarely both.

| Suffix | Meaning | Example code |
|---|---|---|
| `_MOD` | Modelled estimate (joint-estimation group output, e.g. UIS for education, IGME for mortality) | `ED_CR_L1_UIS_MOD` (modelled primary completion) |
| `_MERGE` | Merged across multiple source surveys / years into a single comparable series | `ECD_CHLD_LMPSL_MERGE` |
| `_PRXY` | Proxy indicator — a related variable used in lieu of the conceptually exact one | `ECD_CHLD_LMPSL_PRXY` |
| `_NEW` | New / revised methodology series (often runs alongside a legacy series for one cycle) | `*_NEW` |
| `_NUMTH` | Numerator / threshold variant — alternate cut used by some agencies | `*_NUMTH` |
| `_AGG` | Aggregate (regional or income-group rollup rather than country observation) | `*_AGG` |
| `_UIS` | UNESCO Institute for Statistics source / methodology | `ED_CR_L1_UIS_MOD` |

The MCP's `differentiator.py:_SUFFIX_MEANINGS` table is the canonical source.
When two codes differ only in this trailing segment, `explain_difference()`
reports them as **base vs. variant** (e.g. `ECD_CHLD_LMPSL` as base, `_MERGE`
and `_PRXY` as derivation variants).

### Population restrictions vs sex disaggregation

This distinction is easy to miss and routinely trips up downstream agents.

**Population restriction (built into the code).** Some UNICEF indicators only
exist for one sex because the underlying measurement only applies to one sex:
FGM prevalence, child-marriage cohorts, anaemia in women of reproductive age,
antenatal care coverage. In those families, an `F` segment near the start of
the code (`PT_F_*`, `NT_ANE_WOM_*`, `MNCH_BIRTH18`, antenatal-care codes) is a
**population-restriction marker** that is part of the indicator's identity.
There is no `PT_M_20-24_MRD_U18` counterpart for child marriage; the indicator
is defined on female respondents. Treat the `F` here as part of the indicator
name, not as a disaggregation switch.

**Sex disaggregation (SEX dimension filter, at query time).** For indicators
that are defined on both sexes (under-5 mortality, primary completion, stunting,
literacy), sex is not encoded in the code. It is a separate SDMX dimension —
the `SEX` dimension — with values `F`, `M`, `_T` (total). You select a slice
at query time:

```python
get_data(indicator='CME_MRY0T4', sex='F')   # under-5 mortality, girls
get_data(indicator='CME_MRY0T4', sex='M')   # under-5 mortality, boys
get_data(indicator='CME_MRY0T4', sex='_T')  # under-5 mortality, total
```

The `differentiator.py:_SUFFIX_MEANINGS` table lists `F`, `M`, `_T`, `MF` as
sex-token meanings; those entries describe the **values** of the `SEX`
dimension, not a suffix you append to an arbitrary code. Appending `_F` to a
code that does not already carry it (e.g. inventing `NT_ANT_HAZ_NE2_F`) will
not resolve — the catalog does not contain such codes.

### Age / wealth / residence disaggregation tokens

Disaggregation tokens appear either embedded in the code (when they are part of
the canonical definition, e.g. `PT_F_20-24_MRD_U18`) or applied at query time
via `get_data()` filters. The tokens below are the same in both places.

#### Age bands

Age is encoded as `LOW-HIGH` (inclusive) in the embedded form, or as a bound
token at the end of the code.

| Token | Meaning |
|---|---|
| `15-19`, `20-24`, `15-49` | Inclusive age band in years |
| `Y0` | Under 1 year (neonatal / infant variants) |
| `Y0T4` | 0 through 4 years inclusive (under-5) |
| `Y1T4` | 1 through 4 years inclusive (childhood, post-infant) |
| `U5`, `U15`, `U18` | "Under" threshold — strictly below the named age |
| `ADOL` | Adolescent (10–19, occasionally 10–24) |

#### Wealth quintile (query-time filter)

| Token | Meaning |
|---|---|
| `Q1` | Lowest quintile (poorest 20%) |
| `Q2`, `Q3`, `Q4` | Middle quintiles |
| `Q5` | Highest quintile (richest 20%) |
| `B20` / `B40` | Bottom 20% / bottom 40% |
| `T20` | Top 20% |

#### Residence (query-time filter)

| Token | Meaning |
|---|---|
| `_T` | Total |
| `U` | Urban |
| `R` | Rural |

#### Anthropometric Z-score thresholds

These appear in the `NT_ANT_*` family and need their own table because the
convention is non-obvious:

| Token | Meaning |
|---|---|
| `NE2` | Below -2 SD ("negative end, 2 SD") — moderate-or-severe form |
| `NE3` | Below -3 SD — severe form |
| `NE2_T_NE3` | Between -3 SD and -2 SD — moderate-only form |
| `PO2` | Above +2 SD — overweight side |
| `HAZ` / `WAZ` / `WHZ` / `BAZ` | Height-for-age / Weight-for-age / Weight-for-height / BMI-for-age Z-scores |

### Derived metrics: `TRGT_` / `_ARR_` / `_PRJ`

Three special grammars flag values that are **not observations** but
transformations of them. These are the cases where v1.1.1's query-aware
`CURATED_PREFERRED` scoring matters most. Note that `ARR` is a **middle-segment**
token (e.g. `CME_ARR_U5MR`, `CME_ARR_SBR`), not a trailing suffix.

| Pattern | Meaning | Example |
|---|---|---|
| `TRGT_<year>_<indicator>` | Country-set target value for the named indicator at the named horizon year. `TRGT_2030_IM_DTP3` is the country's 2030 target for DTP3 coverage, not the observed value. | `TRGT_2030_IM_DTP3` |
| `*_ARR_*` | Annual Rate of Reduction — annualised percentage change derived from the underlying series; appears as a middle-segment token | `CME_ARR_U5MR`, `CME_ARR_SBR` |
| `*_PRJ` / `*_PRJ_*` | Projected / forecast value rather than observed | `PT_F_20-24_MRD_U15_PRJ` |

**v1.1.1 query-aware scoring (commit `7112e1d`)**: the MCP only surfaces
`TRGT_*` codes when your natural-language query mentions *target*, *goal*,
*objective*, or a horizon year. A bare "DTP3 coverage in Brazil" question will
resolve to the observation series; "Brazil's 2030 DTP3 target" will resolve to
`TRGT_2030_IM_DTP3`. This is implemented as a hint field on `CURATED_PREFERRED`
entries in `differentiator.py`, not as a hard exclusion — the target code is
still discoverable via direct lookup, just demoted in resolver ranking unless
the query signals intent.

The same query-aware demotion applies to `_MOD` (modelled) variants: queries
mentioning *survey*, *raw*, or *observed* prefer the un-suffixed code; queries
mentioning *modelled*, *estimate*, *joint estimation* prefer `_MOD`.

### Education levels

In the `ED_*` family, ISCED levels are abbreviated `L1` / `L2` / `L3`:

| Token | ISCED level | Conventional name |
|---|---|---|
| `L1` | ISCED 1 | Primary education |
| `L2` | ISCED 2 | Lower-secondary education |
| `L3` | ISCED 3 | Upper-secondary education |

Examples: `ED_ANAR_L1` (adjusted net attendance rate, primary), `ED_ANAR_L2`
(lower-secondary), `ED_CR_L1` (completion rate, primary). Where a code stops at
`L1` it is primary-only; where two levels are reported jointly the codes are
listed separately rather than concatenated.

**Scope caveat.** The `L<n>` = ISCED `<n>` mapping holds **only inside the
`ED_*` family**. Outside `ED_*`, `L<n>` may encode a non-ISCED level — for
example `PV_CHLD_MPI_L1` and `PV_CHLD_MPI_L2` use `L1` / `L2` to mean severe
and moderate multidimensional-poverty deprivation respectively. Some `ED_*`
codes also use the two-digit form `L01` / `L02` to encode early-childhood or
pre-primary levels that sit below ISCED 1. Always check the indicator's name
before assuming `L<n>` means primary / lower-secondary / upper-secondary.

### Where this is encoded in the MCP

The conventions documented above are not folklore — they are encoded in the
MCP source and can be audited directly:

- **`src/unicefstats_mcp/differentiator.py`** is the canonical reference for
  segment-level meaning. The `_SUFFIX_MEANINGS` table maps every recognised
  trailing token to a human-readable gloss; `explain_difference()` walks two
  codes side-by-side and labels each diverging segment; the `CURATED_PREFERRED`
  table carries per-indicator `dimension_hint` strings that drive the v1.1.1
  query-aware scoring.
- **`src/unicefstats_mcp/indicator_resolver.py`** maps natural-language phrases
  to canonical codes. `_SYNONYMS` covers the routine cases ("stunting",
  "under-5 mortality", "child marriage"); `_AMBIGUOUS` flags phrases that
  legitimately map to more than one code and require user disambiguation;
  `_DISAMBIGUATION_TIPS` carries the short hints surfaced in the
  `assistant_guidance` envelope field added in v1.1.0.
- **`unicef://glossary` MCP resource** — clients that load resources at session
  start get the disaggregation-code and indicator-prefix legend without having
  to parse this README.

When the resolver picks a code, the chain is: natural-language query →
`indicator_resolver` lookup → if ambiguous, `_AMBIGUOUS` hit fires the v1.0.0
`ambiguity_flag` + candidate list → if a `CURATED_PREFERRED` entry matches, the
`dimension_hint` re-ranks candidates → the chosen code is annotated by
`differentiator.py` for the `assistant_guidance` field. Every step is
inspectable in the source; nothing in this section is heuristic on the LLM side.

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

### Current canonical numbers (v0.7.3 + fixes, May 2026)

The numbers below are the current canonical scoreboard. They reflect (a) four engineering fixes in the v0.7.3 cycle (see CHANGELOG) and (b) a scoring correction from the v1.4 extractor that respects refusal language. Both samples (mcp060: 40 countries; mcp073: disjoint 20-country validation sample) score under the same v1.4 rules.

| Metric | LLM alone (no tools) | LLM + MCP (v0.7.3 + fixes) | Sample |
|---|---|---|---|
| POS EQA mean | 0.121 | **0.891** | mcp060 (40 ctry) |
| POS EQA mean | 0.121 | **0.909** | mcp073 (20 disjoint ctry) |
| hall_b combined (T1+T2) | 2.50% (hall_a) | **1.00%** | mcp060 |
| hall_b combined (T1+T2) | 2.50% (hall_a) | **2.25%** | mcp073 |
| MCP makes model safer (hall_b < hall_a) | — | **Yes — both samples** | both |

**v0.7.3 + fixes is the first version where MCP demonstrably makes the model safer than the no-tools baseline on absent-data queries.** Through v0.7.2, hall_b ≥ hall_a — the safety layer was reducing magnitude but not direction. The four fixes that flipped the property:

1. `server.py:_seed_data_frontier_cache` — monotonic max instead of unconditional overwrite (a probe-induced regression of the cached frontier was telling the LLM that current data was unavailable).
2. `server.py:get_data` exception handler — `unicefdata` cascade exhaustion reclassified as `no_data` (not `error`), so the LLM treats it as authoritative absence rather than tool failure.
3. `benchmark_eqa_batch.py` — persist tool `result_str` on `state.tool_calls` so the v1.4 extractor can see refusals.
4. `benchmark_eqa_batch.py` — refusal-respect parity with the sync runner.

Canonical scoreboard: see the **[Unreleased] §Fixed** block at the top of [CHANGELOG.md](CHANGELOG.md) for the full cross-version table, including the four post-fix corrections and the mcp073 second-sample validation. Full per-run write-ups live in `internal/v0_7_3_validation.md` and `internal/v0_7_3_second_sample_validation.md` in the dev repo (`jpazvd/unicefstats-mcp-dev`, dev-only and not synced to this public mirror).

### Historical: v0.3.0 (n=600, 2025) and v0.7.2 (n=500 same-day, 2026-05-08)

The original v0.3.0 benchmark reported POS EQA 0.147 → 0.990 (6.7×) and T2 hallucination 11% → 37%. Two corrections since:

- The "37%" headline was substantially a **v1.3 extractor scoring artefact**: the extractor counted any numeric value mentioned in the response as a "claim," including values quoted from `no_data` tool results inside an explicit refusal. The v1.4 extractor (`_detect_refusal`) reclassifies those as appropriate refusals. We did not rescore the v0.3.0 parquets under v1.4 (they're archived); the v1.4-equivalent of "37%" is unknown but substantially lower.
- The v0.7.2 reproduction (n=500, 2026-05-08) under v1.3 scoring reported POS EQA 0.897 and combined T1+T2 hallucination 13%. Under v1.4 scoring the same parquets report POS EQA 0.793 and hall_b 3.75%.

The accuracy headline (~7× lift) has held up across every rescoring. The hallucination headline required both a scoring fix (v1.4 extractor) and a server fix (v0.7.3 cache + cascade fixes) before MCP actually reduced hallucination below the no-tools baseline.

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

| Metric | LLM alone | unicefstats-mcp (v0.7.3 + fixes) | sdmx-mcp |
|---|---|---|---|
| **EQA (POS)** | 0.121 | **0.891** | 0.074 |
| hall_b combined (T1+T2) | hall_a 2.50% | **1.00% (mcp060) / 2.25% (mcp073)** | **0%** |
| MCP safer than no-tools? | — | **Yes** | Yes (zero by construction) |
| Cost per query | ~$0.003 | ~$0.04 | $0.087 |
| Avg latency | ~5s | ~10s | 60s |

sdmx-mcp's raw SDMX-JSON output is hard for LLMs to parse (VA ≈ 0.11), but its anti-hallucination guardrails are highly effective (0% fabrication). See [Relationship to sdmx-mcp](#relationship-to-sdmx-mcp) for details.

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

Contributions are welcome.

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
- **T2 hallucination reduction**: Further reduce fabrication when API returns no results (currently ~10%; see [Limitations](#limitations-and-hallucination-risks))

## Limitations and Hallucination Risks

### Data limitations

- Coverage is uneven across indicators, countries, and years. Survey-based indicators (nutrition, education, protection) have 3-5 year gaps between data points by design.
- Mortality indicators (CME_*) are modeled estimates from the UN Inter-agency Group (IGME), with uncertainty intervals not surfaced in compact output.
- Not all indicators support all disaggregation dimensions; `get_indicator_info()` lists what's available per indicator.
- `get_data()` caps at 500 rows per call.

### Hallucination risks

Benchmark testing across multiple country samples (v0.7.3 + fixes, May 2026):

| Type | Description | Rate (LLM alone, hall_a) | Rate (LLM + MCP, hall_b) | Notes |
|---|---|---|---|---|
| **T1 (gap-year)** | LLM cites a value for a year when the indicator has data but not for that specific year | ~1.0% | 0.00% (mcp060) / 0.50% (mcp073) | Below the no-tools rate |
| **T2 (forward-of-frontier)** | LLM fabricates a value for a year beyond the data frontier | ~3.5% | 2.00% (mcp060) / 4.00% (mcp073) | Below the no-tools rate |
| **Combined** | T1 + T2 | hall_a 2.50% | **1.00% (mcp060) / 2.25% (mcp073)** | **hall_b < hall_a** — MCP makes safer |

**v0.7.3 + fixes is the first release where MCP makes the model safer than the no-tools baseline.** Through v0.7.2 (v1.4 scoring), hall_b ≥ hall_a — the safety layer was reducing magnitude relative to a no-safety-layer baseline but never enough to put MCP under the no-tools floor.

What changed:
1. **Cache contamination in `_seed_data_frontier_cache`** — a probe routine was overwriting the cached max-year for an indicator with whatever year happened to come back, sometimes lower than the cached value. The LLM was being told frontiers were 2018 for indicators whose real frontier was 2023, then answering about 2023 from parametric memory. Fix: monotonic `max()` only.
2. **`unicefdata` cascade as `no_data`, not `error`** — the underlying wrapper's fallback-dataflow exhaustion was leaking as a tool exception, which the LLM read as "tool failed, fall back to my own knowledge." Now classified as a clean `no_data` signal that the safety layer converts into "do not estimate." Filed [`unicefdata-dev#74`](https://github.com/unicef-drp/unicefData-dev/issues/74) for an upstream fix.
3. **v1.4 extractor** (`_detect_refusal`) — corrected the long-standing scoring artefact in which any numeric value in a response was counted as a "claim," including values the LLM was quoting from `no_data` tool results inside an explicit refusal. This dropped hall_b in the v0.7.3 PRE-FIX rescoring from ~37% to 2.25% — most of the historical "MCP-makes-it-worse" finding was extractor, not behaviour.
4. **Batch runner parity** — `result_str` persistence and refusal-respect in the async batch runner.

This finding still leaves room for the broader tool-augmented LLM literature on the structural cost of giving models an answer-producing pathway:

- *The Reasoning Trap: How Enhancing LLM Reasoning Amplifies Tool Hallucination* (ICLR 2025) — shows the relationship is causal: as models get better at tool use, tool hallucination rises *proportionally* with capability.
- *Reducing Tool Hallucination via Reliability Alignment* (Cao et al., 2024, [arXiv:2412.04141](https://arxiv.org/abs/2412.04141)) — formalises the failure as *tool-selection* errors (wrong tool, failed refusal) and *tool-usage* errors (fabricated parameters).
- *ReDeEP: Detecting Hallucination in Retrieval-Augmented Generation via Mechanistic Interpretability* (Sun et al., 2024) — shows mechanistically that an LLM's parametric knowledge can override retrieved context inside the residual stream.

These results show the structural tendency is real; the v0.7.3 + fixes result shows it can be reversed for a specific data domain through (a) safety-layer architecture, (b) server-side discipline (no stale frontier cache, no leaking of no-data as tool errors), and (c) honest scoring.

The takeaway for users:

1. Load the `unicef://system-prompt` and `unicef://context` resources at session start (handles forward-of-frontier fabrication).
2. Treat MCP results as best-effort retrieval, not infallible truth — verify load-bearing values against the [UNICEF Data Warehouse](https://data.unicef.org/) before citing.
3. Prefer queries with explicit years ("under-five mortality in Nigeria in 2023") over open-ended ones ("the latest under-five mortality in Nigeria") — the former triggers refusal more reliably when data is absent.
4. The 1.00% / 2.25% residuals were measured on Sonnet 4 only. Cross-model generalisation is the next benchmark.

Full benchmark methodology: [examples/RESULTS.md](https://github.com/jpazvd/unicefstats-mcp/blob/main/examples/RESULTS.md)

## Provenance and Ownership

All data served by this MCP originates from the [UNICEF Data Warehouse](https://data.unicef.org/), accessed live via the public SDMX REST API. No observation data is stored or cached — every `get_data()` call results in a live SDMX request. The indicator and country registries are cached in memory at first access for performance; these are catalogue metadata, not statistical values. The MCP reformats output for LLM consumption but does not alter values.

All releases are published from GitHub Actions using [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/) (OIDC). No long-lived API tokens exist. Release provenance is verifiable via [PyPI attestations](https://pypi.org/project/unicefstats-mcp/#files).

For full details on data origin, ownership, distribution pipeline, and interpretation caveats, see [PROVENANCE.md](PROVENANCE.md).

## How to Verify This MCP

| Check | How |
|---|---|
| **Source** | Repository is [`jpazvd/unicefstats-mcp`](https://github.com/jpazvd/unicefstats-mcp) on GitHub |
| **Package** | `pip show unicefstats-mcp` — verify `Home-page` points to the canonical repo |
| **Version** | `python -c "import unicefstats_mcp; print(unicefstats_mcp.__version__)"` — compare with `server.json` and PyPI |
| **Provenance** | [PyPI attestations](https://pypi.org/project/unicefstats-mcp/#files) link each release to a GitHub Actions workflow |
| **Runtime** | Call `get_server_metadata()` — returns canonical name, version, publisher, and data source |

## License

MIT
