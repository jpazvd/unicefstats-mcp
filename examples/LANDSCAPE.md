# MCP Servers for Official Statistics: Landscape Analysis

**Date:** March 2026 (refreshed April 2026; inventory refreshed October 2026)
**Scope:** 92 MCP servers for official statistics across UN agencies, international organizations, and national statistics offices as of 27 October 2026 (9 official), plus 4 research and other related sources listed separately; see the [directory](https://github.com/jpazvd/unicefstats-mcp/blob/main/examples/MCP-DIRECTORY-STATS.md). The analysis sections cover the 45 servers catalogued by April 2026. The original cohort (March 2026, ~20 servers) received deep code review; the April 2026 refresh added 25 catalogued entries — see "Citation" section below for review-depth disclosure.

**October 2026:** the [server directory](https://github.com/jpazvd/unicefstats-mcp/blob/main/examples/MCP-DIRECTORY-STATS.md) now lists 92 servers for official statistics with a dated status label for each, plus research and other related sources listed separately ([definitions](https://github.com/jpazvd/unicefstats-mcp#status-labels)). The analysis below still describes the April 2026 cohort, except where a row or gap is marked as updated in October.

**Help keep this current.** If you maintain an MCP server for official statistics, or know one that is missing, out of date or mis-labelled, please [open a landscape-correction issue](https://github.com/jpazvd/unicefstats-mcp/issues/new?template=landscape_correction.md). Additions, updates and clarifications are all welcome; each is applied with the date it was verified.

---

## Evolution Timeline

The MCP ecosystem for official statistics emerged in early 2025, a few months after the protocol's release, and accelerated through 2026. Each quarter below gives the number of servers launched in it (91 with a public date) and a selection of them; the [directory](https://github.com/jpazvd/unicefstats-mcp/blob/main/examples/MCP-DIRECTORY-STATS.md) lists them all. Dates are launch dates as reviewed on 27 October 2026: the organisation's announcement where one exists, otherwise the earliest proof of public availability (first release, package, outside fork or inventory listing), otherwise repository creation. IHME's hosted connector has no public date.

```
2024-Q4  ┊  MCP protocol released (Anthropic, Nov 2024); no server for official statistics yet
         ┊
2025-Q1  ┊  3 new servers for official statistics
         ├── world_bank_mcp_server (anshumax, community) — World Bank Open Data API
         └── mcp-cbs-cijfers-open-data — Netherlands CBS (Go)
         ┊
2025-Q2  ┊  5 new servers for official statistics
         ├── mcp-server-abs — Australia ABS (SDMX-ML)
         ├── imf-data-mcp — IMF (SDMX)
         ├── fred-mcp-server (stefanoamorelli) — FRED
         └── mcp_unhcr — UNHCR refugee data (rvibek)
         ┊
2025-Q3  ┊  7 new servers for official statistics
         ├── israel-statistics-mcp (Israel CBS)
         ├── medical-mcp — WHO GHO + FDA + PubMed
         ├── data-go-mcp-servers (South Korea data.go.kr)
         ├── open-census-mcp-server (US Census community alt)
         ├── agent-toolkit (datacommonsorg, official, platform operator; announced 24 Sep 2025) — Google Data Commons graph: UN agencies, surveys, census, climate
         └── us-census-bureau-data-api-mcp — first official gov MCP
         ┊
2025-Q4  ┊  7 new servers for official statistics
         ├── uk-ons-mcp-server — UK ONS, community
         ├── Kolada-MCP (Sweden Kolada — municipal)
         ├── datagouv-mcp (France data.gouv.fr, public Nov 2025; launch reported Feb 2026) — official national open-data MCP
         ├── ukrainian-stats-mcp-server — Ukraine (SDMX v3)
         ├── OECD-MCP — OECD (9 tools + 7 resources + 7 prompts)
         └── data360-mcp (worldbank, public by Dec 2025) — first bank-official server, anti-hallucination templates
         ┊
2026-Q1  ┊  21 new servers for official statistics
         ├── ibge-br-mcp — Brazil (227 tests, 97% coverage)
         ├── eurostat-mcp — Eurostat (dual SDMX 3.0 + 2.1)
         ├── esankhyiki-mcp (nso-india, beta launched 6 Feb 2026) — first developing-country NSO official
         ├── estat-mcp — Japan e-Stat, community
         ├── unesco-mcp (Feb 2026), global-education-mcp (Mar 2026) — UNESCO UIS, community; missed in the April inventory
         ├── mcp-statcan — Statistics Canada, community
         ├── sdmx-mcp (unicef-drp, official, beta) — generic SDMX for any registry
         ├── us-gov-open-data-mcp — 40+ US APIs, 300+ tools
         ├── cluster-mcp — multi-source monorepo (WB/OECD/ILO/WHO)
         ├── istat_mcp_server — Italy (2-layer cache, blacklist, SDMX)
         ├── unicef-datawarehouse-mcp (Tryolabs) — UNICEF SDMX
         ├── faostat-mcp (berba-q, v1.2.2 April 2026) — FAOSTAT 245 countries, 21 tools, 3-tier caching
         ├── unicefstats-mcp (this repo) — UNICEF with EQA benchmark
         ├── ecb-mcp (scka-de) — European Central Bank
         ├── swiss-statistics-mcp — Switzerland BFS, community
         └── unhcr-mcp-server — UNHCR alternative (shahzadarain; listed in March 2026, deleted by its owner by Oct 2026)
         ┊
2026-Q2  ┊  21 new servers for official statistics
         ├── korea-stats-mcp — Statistics Korea (KOSIS), community
         ├── UNCHR_MCP_Server — UNHCR third implementation (mhadeli)
         ├── destatis-mcp (Germany Destatis)
         ├── inegi-mcp-server (Mexico INEGI)
         ├── macronorm-mcp (donkachii) — unified IMF + WB + FRED
         ├── nso1212-mcp (Mongolia NSO)
         ├── WHO GHO, UN Comtrade, World Bank, IMF, OECD, Eurostat servers (cyanheads, May–Jun 2026) — community
         ├── UN System Data Commons (Jun 2026) — official MCP endpoint, first opened at UN Open Source Week; the Data Commons launched at data.un.org on 17 Sep 2026
         ├── tnso-mcp-server — Thailand TNSO, community
         └── fed-data-mcp-registry (GSA-TTS — official curated registry, not a server)
         ┊
2026-Q3  ┊  22 new servers for official statistics
         ├── tuik-mcp — Türkiye TÜİK, community
         ├── cnbs-mcp-server — China NBS, community
         ├── Idescat MCP (Catalonia, Jul 2026) — official, hosted
         ├── McpDiffusion (INSEE Lab, Aug 2026) — official, beta
         ├── ghana-data-mcp — Ghana, community
         ├── ilo-mcp-server, ilostat-mcp-server (Aug–Sep 2026) — ILOSTAT, community
         ├── unhcr-opendata-gateway-mcp (Aug 2026) — independent (UNHCR staff)
         ├── cso-mcp — Ireland CSO, community
         ├── uis-mcp-server (Sep 2026) — UNESCO UIS, community
         └── maplestats-mcp — Statistics Canada, community
         ┊
2026-Q4  ┊  5 new servers to 27 October; inventory refresh: 92 servers for official statistics, 9 official, 3 independent
         └── IHME GBD 2023 connector — research estimates, producer-maintained, hosted; listed with related sources
```

---

## Architectural Generations

### Generation 1: Direct API wrappers (2025-H1)

**Pattern:** Thin wrapper around a single REST API. One tool = one endpoint.

| Server | Approach | Limitation |
|---|---|---|
| fred-mcp-server | 3 tools wrapping FRED API | No output formatting for LLMs |
| world_bank_mcp_server (community) | 1 tool wrapping WB Open Data API | Minimal — essentially `curl` via MCP |

**Strengths:** Simple, fast, easy to build.
**Weaknesses:** Raw API responses overwhelm LLM context. No validation, no error guidance.

### Generation 2: SDMX-native servers (2025-Q1–Q2)

**Pattern:** Direct SDMX protocol implementation. Expose structural queries (dataflows, dimensions, codelists) as tools.

| Server | Approach | Innovation |
|---|---|---|
| ukrainian-stats-mcp-server | 8 SDMX v3 tools | `check_data_availability` preflight |
| eurostat-mcp | Dual SDMX 3.0 + 2.1 | Multi-fallback API strategy |
| imf-data-mcp | Per-dataset tools | Natural language formatting |
| sdmx-mcp | 23 tools, any registry | `assistant_guidance`, `validate_query_scope` |

**Strengths:** Full access to SDMX structural model. Registry-agnostic.
**Weaknesses:** Many tools → LLM tool selection confusion. Raw SDMX-JSON is hard for LLMs to parse (VA=0.11 in our benchmark).

### Generation 3: Quality-engineered servers (2025-Q3)

**Pattern:** Structured caching, comprehensive testing, modular architecture.

| Server | Innovation | Impact |
|---|---|---|
| istat_mcp_server | Two-layer cache (memory + disk), dataflow blacklist | Production reliability |
| ibge-br-mcp | 227 tests, structured errors with `relatedTools` | Gold standard testing |
| OECD-MCP | 7 MCP Resources + 7 Prompts | Best anti-hallucination via `llm-instructions` resource |

**Strengths:** Production-ready. Tested. Reliable.
**Weaknesses:** Higher complexity. Still limited output formatting for LLMs.

### Generation 4: Benchmarked + LLM-optimized (2026-Q1)

**Pattern:** Output designed for LLM consumption. Quantified accuracy. Anti-hallucination directives.

| Server | Innovation | Impact |
|---|---|---|
| unicefstats-mcp | EQA benchmark (300 queries), compact format, summaries, trends, source citations | First MCP with quantified accuracy (EQA=0.990) |
| us-census-bureau-data-api-mcp | Citation/provenance on every response | Verifiable outputs |

**Strengths:** Measurably accurate. Output optimized for LLMs. Human-verifiable.
**Weaknesses:** Domain-specific (not generic). Benchmark methodology still evolving.

---

## Feature Matrix

Figures from the March 2026 deep review. Tool counts have moved since: as of October 2026, IMF 5, ISTAT 8, IBGE 23, sdmx-mcp 31, unicefstats-mcp 9 (see the [directory](https://github.com/jpazvd/unicefstats-mcp/blob/main/examples/MCP-DIRECTORY-STATS.md)).

| Feature | fred | WB | IMF | OECD | Eurostat | ISTAT | IBGE | Census | Ukraine | sdmx | **unicefstats** |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **Tools** | 3 | 1 | 10 | 9 | 7 | 7 | 22 | 5 | 8 | 23 | **7** |
| **Resources** | — | — | 2 | **7** | — | — | — | — | — | — | **4** |
| **Prompts** | — | — | 1 | **7** | — | — | — | 1 | — | — | **2** |
| **Tests** | Yes | — | Yes | Yes | — | Yes | **227** | Yes | — | — | **Yes** |
| **SDMX** | — | — | Yes | Yes | Yes | Yes | — | — | Yes | Yes | **Yes** |
| **Published** | npm | — | PyPI | npm | — | — | npm | — | npm | — | **PyPI** |
| **Caching** | — | — | JSON | — | 1h TTL | **2-layer** | **Tiered TTL** | PgSQL | — | 6h TTL | — |
| **LLM output** | Raw | Raw | NL text | JSON | Truncated | TSV | **Markdown** | Text | Raw | Raw | **Compact+summary** |
| **Validation** | Zod | — | — | Zod | — | Pydantic | Zod | Zod | — | — | **Custom** |
| **Error tips** | — | — | Text | Centralized | Fallback | Decorator | **+relatedTools** | Centralized | Express | Text | **+tip field** |
| **Anti-halluc.** | — | — | Prompt | **Resource** | — | Blacklist | Implicit | **Citation** | — | **Guidance** | **Resource+absent** |
| **Benchmark** | — | — | — | — | — | — | — | — | — | — | **EQA (300q)** |
| **Retry** | — | — | — | — | — | Rate limit | **Exp. backoff** | — | — | — | **Exp. backoff** |

---

## Strengths and Weaknesses by Server

### UN Agencies

**unicefstats-mcp** (this repo)
- Strengths: Benchmarked accuracy (EQA=0.990), LLM-optimized output, source citations, MCP Resources, anti-hallucination, code bridge to Python/R/Stata
- Weaknesses: UNICEF-only, no generic SDMX, 500-row limit, T2 hallucination ~37% raw (~10% corrected)

**sdmx-mcp** (unicef-drp)
- Strengths: Generic SDMX (any registry), 0% hallucination, `assistant_guidance`, `validate_query_scope`, hierarchy resolution
- Weaknesses: 23 tools at the March review (31 by October 2026) overwhelm LLMs (EQA=0.074), raw SDMX output, no tests, monolithic 2,700-line file

**unicef-datawarehouse-mcp** (Tryolabs)
- Strengths: Clean code (146 lines), professional quality, `input_arguments` echo in responses
- Weaknesses: Only 3 tools (minimal), no formatting, no anti-hallucination, no tests beyond basic

**mcp_unhcr** (rvibek), **unhcr-mcp-server** (shahzadarain, deleted by its owner by October 2026), **UNCHR_MCP_Server** (mhadeli); since then also **unhcr-refugees-mcp-server** (cyanheads) and the independent **unhcr-opendata-gateway-mcp** and **unhcr_iati_mcp** (built by UNHCR staff)
- Strengths: Three separate UNHCR implementations cover unique data domain (refugee statistics, not available elsewhere). Multiple implementations suggest demand.
- Weaknesses: No tests, no validation, no error guidance, basic implementations across all three. Coordination opportunity — none has emerged as canonical.

**agent-toolkit (Google Data Commons)** — Officially maintained, Sept 2025
- Strengths: Connects AI to the full Data Commons graph — UN agencies, government surveys, census, climate data — at scale. Major-AI-company investment in authoritative data access.
- Weaknesses: Cross-domain (not statistics-specific), Google ecosystem.

**faostat-mcp** (community, v1.2.2 April 2026) — Closes the long-standing FAO gap
- Strengths: 245 countries, 1961-present, 21 tools at release (23 by October 2026), 3-tier caching. Active maintenance.
- Weaknesses: Community (not FAO-official), no published accuracy benchmark.

**UN System Data Commons** (UN DESA / UNSD, official; MCP endpoint first opened at UN Open Source Week, June 2026; the Data Commons launched at data.un.org on 17 September 2026)
- Strengths: The widest UN coverage of any server: public data from 26 UN entities in one knowledge graph, built under Work Package 16 of the UN80 Initiative. For UNICEF indicators (247 codes, at full precision) it carries the newest custodian vintages (UN IGME, JME, WUENIC, JMP, MMEIG).
- Metadata: series-level metadata (definitions, release dates and attribution to the producing agency) are being completed. This is a known issue, addressed through the federated governance arrangement among the chief statisticians of the participating entities.

**Community servers for the remaining UN agencies (May–September 2026)**: WHO GHO (who-gho-mcp-server, gho-mcp), UN Comtrade (un-comtrade-mcp-server), ILOSTAT (ilostat-mcp-server, ilo-mcp-server), UNESCO UIS (uis-mcp-server, unesco-mcp, global-education-mcp). None is maintained by the agency.

**medical-mcp** (WHO partial)
- Strengths: 18 tools across WHO GHO, FDA, PubMed, RxNorm. npm published. 119 stars (October 2026).
- Weaknesses: Medical focus (not general statistics), WHO coverage is partial

### International Organizations

**OECD-MCP** — Best overall design
- Strengths: 7 Resources (including `llm-instructions` — most effective anti-hallucination), 7 Prompts with concrete tool call examples, curated known dataflows, interactive Data Explorer URLs, npm published
- Weaknesses: No caching, OECD-specific, 1 star

**data360-mcp** (World Bank, official) — First bank-official server with anti-hallucination templates
- Strengths: Officially maintained (last push 2026-09-22; 16 tools, 11 resources and 7 prompts on the `dev` default branch; visualization, compliance logging, load-testing). Per-observation `claim_id` provenance hash. In the October 2026 cross-platform comparison, the only platform of three that gives a definition, source, release date and licence for every series. System-prompt resource (`data360://system-prompt`) and runtime context resource (`data360://context`) — pattern adopted in unicefstats-mcp v0.5.0.
- Weaknesses: No published accuracy benchmark. Its README tool table lists 6 of the 16 tools; values are rounded to one decimal.

**IHME GBD 2023 connector** (research estimates, producer-maintained by IHME, hosted, currently Claude only; listed under related sources)
- Strengths: 95% uncertainty intervals, complete annual series, sex and age disaggregation, retrievable methods text.
- Weaknesses: Model estimates, not official statistics. Differs from the UN custodian series by a median 7% for child mortality and 30% for maternal mortality, with no consistent sign across countries (October 2026 comparison).

**ecb-mcp** — European Central Bank (community)
- Strengths: Covers ECB statistics, SDMX-native.
- Weaknesses: Community, basic implementation, low visibility.

**macronorm-mcp** — Unified IMF + World Bank + FRED (March 2026)
- Strengths: Single normalized interface across three major economic data providers. Useful for cross-source macroeconomic queries.
- Weaknesses: Community, no published benchmark, narrow scope.

**imf-data-mcp**
- Strengths: Natural language formatted output, per-dataset tools, SDMX, Resources (installed from source with `uvx`; not on PyPI as of October 2026)
- Weaknesses: No caching, limited to 8 IMF datasets

**fred-mcp-server** — Most popular
- Strengths: 72 stars, npm published, tests, simple 3-tool design, well-documented
- Weaknesses: US-focused, no SDMX, no LLM formatting, no anti-hallucination

**eurostat-mcp**
- Strengths: Dual SDMX 3.0 + 2.1 support, multi-fallback strategy, row truncation
- Weaknesses: No tests, no caching beyond simple 1h TTL, no anti-hallucination

### National Statistics Offices

**ibge-br-mcp** — Best testing
- Strengths: 227 tests (97% coverage), structured errors with `relatedTools`, tiered TTL cache, Markdown table output, exponential backoff retry, 22 tools (23 by October 2026), npm published
- Weaknesses: Brazil-specific, no MCP Resources or Prompts, no anti-hallucination

**us-census-bureau-data-api-mcp** — First official government MCP
- Strengths: Official government project, citation/provenance in every response, PostgreSQL-backed caching, Zod validation, 57 stars
- Weaknesses: Complex setup (requires PostgreSQL + migrations), US-only

**istat_mcp_server** — Best caching
- Strengths: Two-layer cache (memory + persistent disk), tiered TTLs (7d metadata, 1h data), dataflow blacklist, cache diagnostics tool, rate limiting
- Weaknesses: Italy-specific, no MCP Resources or Prompts, TSV output (not ideal for LLMs)

**ukrainian-stats-mcp-server**
- Strengths: SDMX v3 implementation, `check_data_availability` preflight tool, 49 stars, npm published
- Weaknesses: Raw JSON output, no tests, Express REST (not native MCP stdio)

**esankhyiki-mcp** (India MoSPI, official, Feb 2026 beta) — First developing-country NSO with an official MCP server
- Strengths: Officially maintained by India's National Statistical Office. Covers PLFS, CPI, GDP, and five other core datasets.
- Weaknesses: Beta, no published benchmark, recent release.

**datagouv-mcp** (France data.gouv.fr, official; public since November 2025, launch reported February 2026) — official national open-data MCP
- Strengths: Officially maintained, free, no API key required. Marketed as the first official national-platform MCP.
- Weaknesses: Recent release, no published benchmark.

**Official NSO servers added in October 2026**: **McpDiffusion** (France INSEE, INSEE Lab, beta: key indicators, publications, Melodi datasets, RMES semantic graph; 12 tools) and **Idescat MCP** (Catalonia, hosted: statistics catalogue, table metadata, JSON-stat data; 7 tools).

**Community NSO servers added in October 2026**: Statistics Canada (mcp-statcan, maplestats-mcp), UK ONS, Ireland CSO, Switzerland BFS, Statistics Korea (KOSIS), Japan e-Stat, Türkiye TÜİK, China NBS, Thailand TNSO, Statistics Denmark, Norway, Ghana, Chile, Bangladesh, plus central-bank servers for Brazil, Türkiye, Belgium, Nigeria and Sri Lanka. Full list in the [directory](https://github.com/jpazvd/unicefstats-mcp/blob/main/examples/MCP-DIRECTORY-STATS.md).

**Cohort of newer community NSO servers (April 2026 audit, all community-maintained)**:

- **mcp-server-abs** (Australia ABS) — SDMX-ML
- **destatis-mcp** (Germany Destatis)
- **inegi-mcp-server** (Mexico INEGI)
- **Kolada-MCP** (Sweden Kolada — municipal-level)
- **nso1212-mcp** (Mongolia NSO, 1212.mn)
- **israel-statistics-mcp** (Israel CBS)
- **data-go-mcp-servers** (South Korea data.go.kr — multi-server monorepo)
- **open-census-mcp-server** (US Census community alternative)
- **fed-data-mcp-registry** (US GSA-TTS — official curated registry, not a server itself; useful for further discovery)

These cover smaller markets and developing-country NSOs that earlier surveys missed. None has a published accuracy benchmark; most have basic test coverage. They reflect the rapid expansion in 2026 — the ecosystem doubled from ~20 confirmed in early 2026 to 45+ by mid-2026.

---

## What unicefstats-mcp Has Adopted

| Feature | Source | Version | Impact |
|---|---|---|---|
| LLM Instructions Resource | OECD-MCP | v0.3.0 | Anti-hallucination |
| Source citations | US Census Bureau | v0.3.0 | Verifiability |
| Retry with backoff | IBGE Brazil | v0.3.0 | Reliability |
| MCP Resources | OECD-MCP + IMF | v0.3.0 | Cost reduction |
| Status field in responses | ms-mcp-builder audit | v0.2.x | Unambiguous parsing |
| Anti-hallucination directive | sdmx-mcp (concept) | v0.2.0 | T2 reduction |
| Compact output format | Original design | v0.1.0 | EQA=0.990 |
| EQA benchmark | Original design | v0.2.0 | Quantified accuracy |
| `system-prompt` resource | World Bank data360-mcp | v0.5.0 | Anti-extrapolation skill |
| `context` resource (current_year) | World Bank data360-mcp | v0.5.0 | Temporal-frontier check |

## What Remains to Adopt

| Feature | Source | Priority | Expected impact |
|---|---|---|---|
| `check_data_availability` preflight | Ukraine MCP | High | Reduce T1 hallucination |
| Tiered TTL caching | ISTAT | Medium | Performance, API load |
| Structured errors with `relatedTools` | IBGE | Medium | Better error recovery |
| Dataflow blacklist | ISTAT | Low | Skip known-broken flows |
| Markdown table output option | IBGE | Low | Alternative to JSON |
| Interactive Data Explorer URLs | OECD | Low | Visual exploration |
| `input_arguments` echo | Tryolabs | Low | Audit trail |

---

## Key Gaps in the Ecosystem

The April 2026 audit closed one major gap (FAO). The October 2026 refresh found community servers for four more, launched between February and August 2026; none is maintained by the agency, and the UNESCO servers predate the April audit that called UIS a gap:

| Data Source | Indicators | API Available | Status |
|---|---|---|---|
| ~~FAO/FAOSTAT~~ | ~~20,000+ food/agriculture~~ | ~~REST API~~ | **Closed April 2026** — community [faostat-mcp](https://github.com/berba-q/faostat-mcp) v1.2.2 (245 countries, 1961-present, 21 tools, 3-tier caching) |
| **UNESCO/UIS** | 4,000+ education | REST API | **Closed by community servers since Feb 2026** (found in the October refresh; the April inventory missed them) — [uis-mcp-server](https://github.com/SidneyBissoli/uis-mcp-server), [unesco-mcp](https://github.com/lpicci96/unesco-mcp), [global-education-mcp](https://github.com/malkreide/global-education-mcp) |
| **ILO/ILOSTAT** | 1,000+ labor | SDMX API | **Closed by community servers since Aug 2026** — [ilostat-mcp-server](https://github.com/cyanheads/ilostat-mcp-server), [ilo-mcp-server](https://github.com/SidneyBissoli/ilo-mcp-server) |
| **UNSD SDG API** | 232 SDG indicators | REST API | Open — partly covered by the official [UN System Data Commons](https://github.com/UNStats/OpenSourceWeek2026) endpoint |
| **UN DESA Population** | Population projections | Data portal | Open — medium |
| **UNDP/HDI** | Human Development Index | Bulk download only | Open — low (no live API) |
| **WHO (dedicated)** | GHO indicators | REST | **Closed by community servers since May 2026** — [who-gho-mcp-server](https://github.com/cyanheads/who-gho-mcp-server), [gho-mcp](https://github.com/Decilion/gho-mcp) |
| **UN Comtrade** | Trade flows | REST | **Closed by community servers since May 2026** — [un-comtrade-mcp-server](https://github.com/cyanheads/un-comtrade-mcp-server) |
| **BIS, WTO, IAEA** | Financial / trade / nuclear stats | REST/SDMX | Open — no dedicated server found (2026-10-26); BIS data reachable via the community aggregator [openecon-data](https://github.com/hanlulong/openecon-data) |

---

## Citation

This landscape analysis was conducted in two phases with **different review depths**. Specific findings (feature matrix, strengths/weaknesses sections, EQA benchmark comparisons) cite servers from the original deep-review cohort; entries from the April 2026 refresh appear in coverage tables and timeline only.

**Phase 1 — March 2026, deep review (20 servers):** Repositories cloned and analyzed from source code, not just README descriptions. Python 11, TypeScript 8, Go 1; approximately 15,000 lines of server code. Feature extraction covered tool design, output formatting, error handling, anti-hallucination patterns, caching, testing, and MCP Resources/Prompts.

**Phase 2 — April 2026 refresh, catalogue-only (25 servers):** Inventory extended from ~20 → 45 confirmed servers. Added entries: cohort of newer community NSO servers (Australia ABS, Germany Destatis, Mexico INEGI, Sweden Kolada, Mongolia NSO, Israel CBS, South Korea data.go.kr, US Census community alt, France data.gouv.fr official, India MoSPI esankhyiki official) + ECB + 2 additional UNHCR implementations + FAO + Google Data Commons + MacroNorm + World Bank data360 official + GSA-TTS fed-data-mcp-registry. **These entries are catalogued from README + manifest only** — they did not receive the Phase 1 source-code review. Quality-metrics tables in Section 3.4 of [LITERATURE_REVIEW.md](LITERATURE_REVIEW.md) preserve the Phase 1 fractions and note this depth distinction explicitly.

**Phase 3 — October 2026 refresh (27 October):** every listed repository re-checked through the GitHub API and a shallow clone (stars, last push, tool registrations); new servers found through the official MCP Registry, GitHub search and web search. Result: 92 servers for official statistics in the directory tables (39 → 92 against the published v1.5.5 directory: 2 dropped, 34 of 37 updated, 56 new; the European Parliament server moved to related sources), 9 official, 3 independent; 4 research and other related sources listed separately; and 52 further implementations listed but not reviewed. Status labels follow the README definitions.

For the EQA benchmark methodology, see: Azevedo, J.P. (2025). "AI Reliability for Official Statistics: Benchmarking Large Language Models with the UNICEF Data Warehouse." [RESULTS.md](https://github.com/jpazvd/unicefstats-mcp/blob/main/examples/RESULTS.md)
