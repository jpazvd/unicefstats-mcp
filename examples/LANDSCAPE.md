# MCP Servers for Official Statistics: Landscape Analysis

**Date:** March 2026
**Scope:** 20 MCP servers across UN agencies, international organizations, and national statistics offices

---

## Evolution Timeline

The MCP ecosystem for official statistics emerged in late 2024 and accelerated rapidly through early 2026.

```
2024-Q4  ┊  MCP protocol released (Anthropic, Nov 2024)
         ┊  First economic data MCPs appear
         ├── fred-mcp-server (stefanoamorelli) — FRED, 72★
         ├── world_bank_mcp_server (anshumax) — World Bank, 45★
         ┊
2025-Q1  ┊  National statistics offices begin adopting
         ├── mcp-cbs-cijfers-open-data — Netherlands CBS (Go)
         ├── mcp-server-abs — Australia ABS (SDMX-ML)
         ├── cluster-mcp — multi-source monorepo (WB/OECD/ILO/WHO)
         ┊
2025-Q2  ┊  SDMX-native servers emerge
         ├── ukrainian-stats-mcp-server — Ukraine (SDMX v3), 49★
         ├── imf-data-mcp — IMF (SDMX), PyPI published
         ├── eurostat-mcp — Eurostat (dual SDMX 3.0 + 2.1)
         ┊
2025-Q3  ┊  Quality bar rises — tests, caching, resources
         ├── istat_mcp_server — Italy (2-layer cache, blacklist, SDMX)
         ├── ibge-br-mcp — Brazil (227 tests, 97% coverage, 22 tools)
         ├── OECD-MCP — OECD (9 tools + 7 resources + 7 prompts)
         ┊
2025-Q4  ┊  Official government adoption
         ├── us-census-bureau-data-api-mcp — first official gov MCP, 57★
         ├── us-gov-open-data-mcp — 40+ US APIs, 300+ tools, 91★
         ┊
2026-Q1  ┊  UN agencies and benchmarking
         ├── sdmx-mcp (unicef-drp) — generic SDMX for any registry
         ├── unicef-datawarehouse-mcp (Tryolabs) — UNICEF SDMX
         ├── unicefstats-mcp (this repo) — UNICEF with EQA benchmark
         ├── mcp_unhcr — UNHCR refugee data
         └── medical-mcp — WHO GHO + FDA + PubMed, 78★
```

---

## Architectural Generations

### Generation 1: Direct API wrappers (2024-Q4)
**Pattern:** Thin wrapper around a single REST API. One tool = one endpoint.

| Server | Approach | Limitation |
|---|---|---|
| fred-mcp-server | 3 tools wrapping FRED API | No output formatting for LLMs |
| world_bank_mcp_server | 1 tool wrapping WB API | Minimal — essentially `curl` via MCP |

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
- Weaknesses: 23 tools overwhelm LLMs (EQA=0.074), raw SDMX output, no tests, monolithic 2,700-line file

**unicef-datawarehouse-mcp** (Tryolabs)
- Strengths: Clean code (146 lines), professional quality, `input_arguments` echo in responses
- Weaknesses: Only 3 tools (minimal), no formatting, no anti-hallucination, no tests beyond basic

**mcp_unhcr**
- Strengths: Covers unique data domain (refugee statistics, not available elsewhere)
- Weaknesses: No tests, no validation, no error guidance, basic implementation

**medical-mcp** (WHO partial)
- Strengths: 18 tools across WHO GHO, FDA, PubMed, RxNorm. npm published. 78 stars.
- Weaknesses: Medical focus (not general statistics), WHO coverage is partial

### International Organizations

**OECD-MCP** — Best overall design
- Strengths: 7 Resources (including `llm-instructions` — most effective anti-hallucination), 7 Prompts with concrete tool call examples, curated known dataflows, interactive Data Explorer URLs, npm published
- Weaknesses: No caching, OECD-specific, 1 star

**imf-data-mcp**
- Strengths: Natural language formatted output, per-dataset tools, PyPI published, SDMX, Resources
- Weaknesses: No caching, limited to 8 IMF datasets

**fred-mcp-server** — Most popular
- Strengths: 72 stars, npm published, tests, simple 3-tool design, well-documented
- Weaknesses: US-focused, no SDMX, no LLM formatting, no anti-hallucination

**eurostat-mcp**
- Strengths: Dual SDMX 3.0 + 2.1 support, multi-fallback strategy, row truncation
- Weaknesses: No tests, no caching beyond simple 1h TTL, no anti-hallucination

### National Statistics Offices

**ibge-br-mcp** — Best testing
- Strengths: 227 tests (97% coverage), structured errors with `relatedTools`, tiered TTL cache, Markdown table output, exponential backoff retry, 22 tools, npm published
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

No MCP server exists for:

| Data Source | Indicators | API Available | Opportunity |
|---|---|---|---|
| **FAO/FAOSTAT** | 20,000+ food/agriculture | REST API | High |
| **UNESCO/UIS** | 4,000+ education | REST API | High |
| **ILO/ILOSTAT** | 1,000+ labor | SDMX API | High |
| **UNSD SDG API** | 232 SDG indicators | REST API | High |
| **UN DESA Population** | Population projections | Data portal | Medium |
| **UNDP/HDI** | Human Development Index | Bulk download only | Low |

---

## Citation

This landscape analysis was conducted as part of the unicefstats-mcp project. All repos were cloned and analyzed from source code, not just README descriptions.

Methodology: Deep code review of 20 MCP server repositories (Python 11, TypeScript 8, Go 1), totaling approximately 15,000 lines of server code. Feature extraction focused on tool design, output formatting, error handling, anti-hallucination patterns, caching, testing, and MCP Resources/Prompts.

For the EQA benchmark methodology, see: Azevedo, J.P. (2025). "AI Reliability for Official Statistics: Benchmarking Large Language Models with the UNICEF Data Warehouse." [RESULTS.md](https://github.com/jpazvd/unicefstats-mcp/blob/main/examples/RESULTS.md)
