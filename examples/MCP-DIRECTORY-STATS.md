# MCP Server Directory

Comprehensive list of pre-built MCP servers researched March 2026, refreshed April 2026, and refreshed again for section 5 on 2026-10-26 (92 official-statistics servers in the tables, 9 official and 3 independent as defined under Status labels in the README; 4 research and other related sources in 5g; a long-tail list in 5f).
Trust levels (sections 1–4 and 6–24, general-purpose MCP servers): **Official** (maintained by the vendor of the product it connects to), **High** (1K+ stars, reputable org), **Medium** (100+ stars), **Low** (small/unaudited). Section 5 uses the status labels below instead.

---

## 1. OFFICIAL REFERENCE SERVERS (modelcontextprotocol/servers)

Repo: <https://github.com/modelcontextprotocol/servers> (81K stars)

| Server | Install | Purpose | Trust |
|--------|---------|---------|-------|
| Filesystem | `npx -y @modelcontextprotocol/server-filesystem /path` | Secure file read/write/search with dir access controls | Official |
| Git | `npx -y @modelcontextprotocol/server-git` | Clone, commit, branch, diff, log, status | Official |
| Memory | `npx -y @modelcontextprotocol/server-memory` | Knowledge graph persistent memory (local JSON) | Official |
| Fetch | `npx -y @modelcontextprotocol/server-fetch` | Web content fetching and conversion for LLMs | Official |
| Sequential Thinking | `npx -y @modelcontextprotocol/server-sequential-thinking` | Dynamic multi-step reasoning, branching, revision | Official |
| Time | `npx -y @modelcontextprotocol/server-time` | Time and timezone conversion | Official |
| PostgreSQL | `npx -y @modelcontextprotocol/server-postgres` | Read-only PostgreSQL access (archived, use DBHub) | Official |
| SQLite | `pip install mcp-server-sqlite` | SQLite queries + BI memo generation (archived) | Official |
| GitHub | `npx -y @modelcontextprotocol/server-github` | Repos, issues, PRs, search, file ops | Official |
| Slack | `npx -y @modelcontextprotocol/server-slack` | Channels, messages, threads, reactions | Official |

---

## 2. WEB SEARCH

| Server | Install | What it does | Stars | Trust |
|--------|---------|-------------|-------|-------|
| Brave Search | `npx -y @brave/brave-search-mcp-server` | Web/local/news/image search via Brave API | Official | Official |
| Tavily | `npx -y tavily-mcp` | LLM-optimized search + content extraction + crawling | — | High |
| Exa Search | `npx -y mcp-remote https://mcp.exa.ai/mcp` | AI-native semantic search, code search | — | High |
| mcp-omnisearch | `npm i mcp-omnisearch` | Multi-engine: Tavily + Perplexity + Kagi + Brave + Exa | — | Medium |

**API keys:** Brave (free tier), Tavily (free tier), Exa (paid)

---

## 3. ACADEMIC PAPERS & LITERATURE

| Server | Install | What it does | Stars | Trust |
|--------|---------|-------------|-------|-------|
| arxiv-mcp-server | `pip install arxiv-mcp-server` | Search/download arXiv papers, filter by date/category, cache locally | 2,400 | High |
| paper-search-mcp | `pip install paper-search-mcp` | 20+ sources: arXiv, PubMed, bioRxiv, SSRN, OpenAlex, Crossref, CORE, Zenodo | 853 | Medium |
| arxiv-latex-mcp | `pip install arxiv-latex-mcp` | Fetch arXiv papers as raw LaTeX (not PDF) for math accuracy | 112 | Medium |
| Academix | `pip install academix` | Unified search: OpenAlex, DBLP, Semantic Scholar, arXiv, CrossRef + BibTeX export | 4 | Low |
| mcp-for-research | `npx -y scholarly-research-mcp` | PubMed + Google Scholar + ArXiv + JSTOR with citation generation | 7 | Low |
| Google Scholar MCP | Clone github.com/JackKuo666/Google-Scholar-MCP-Server | Search articles, advanced search, author details | — | Low |
| Semantic Scholar MCP | Clone github.com/JackKuo666/semanticscholar-MCP-Server | Paper search, citations, references, author details | — | Low |

---

## 4. REFERENCE MANAGEMENT

| Server | Install | What it does | Stars | Trust |
|--------|---------|-------------|-------|-------|
| zotero-mcp | `pip install zotero-mcp-server` | Search Zotero library, extract PDF annotations, semantic search, BibTeX/RIS/APA export | 2,000 | High |

---

## 5. OFFICIAL STATISTICS & INTERNATIONAL DATA

**Snapshot: 2026-10-26, second search pass 2026-10-27.** Stars and last push come from the GitHub API. Tools are taken from the README where it states a count or lists them, and otherwise from tool registrations in the code on the default branch. "—" means not stated and not reliably countable. **Status** uses the four labels defined in the README under [Status labels](https://github.com/jpazvd/unicefstats-mcp#status-labels): **Official** (with a *beta*, *lab* or *pilot* qualifier where the organisation states one), **Independent**, **Community** and **Commercial**. Status describes who maintains a server, not its quality. Where the evidence is ambiguous the row is labelled Community and the description says why. Servers whose data are not official statistics are listed separately in 5g and not counted in the totals. Corrections: open a [landscape-correction issue](https://github.com/jpazvd/unicefstats-mcp/issues/new?template=landscape_correction.md).

### 5a. UN System

| Server | Install | What it does | Tools | SDMX | Stars | Last push | Status |
|--------|---------|-------------|-------|------|-------|-----------|--------|
| [unicefstats-mcp](https://github.com/jpazvd/unicefstats-mcp) | `pip install unicefstats-mcp` | UNICEF 790+ child indicators, disaggregations, benchmarked (EQA=0.990, replicated) | 9 | Yes | 7 | 2026-06-08 | Independent |
| [sdmx-mcp](https://github.com/unicef-drp/sdmx-mcp) | Docker / Fly.io | Generic SDMX server, any registry (defaults UNICEF), guided-discovery resources (v0.9.0-beta) | 31 | Yes | 2 | 2026-10-26 | **Official** (UNICEF DRP, beta) |
| [unicef-datawarehouse-mcp](https://github.com/tryolabs/unicef-datawarehouse-mcp) | Clone + run | UNICEF dataflows via SDMX. Built by Tryolabs; UNICEF involvement not stated | 3 | Yes | 0 | 2025-11-10 | Community |
| [UN System Data Commons](https://github.com/UNStats/OpenSourceWeek2026) | Hosted endpoint (`{dc_base_url}/mcp`) | UN DESA / UNSD MCP endpoint for the UN System Data Commons: `search_indicators` + `get_observations`. First opened at UN Open Source Week (June 2026); the Data Commons launched at data.un.org on 17 September 2026 with public data from 26 UN entities | 2 | No | 4 | 2026-06-20 | **Official** (UN DESA / UNSD) |
| [faostat-mcp](https://github.com/berba-q/faostat-mcp) | `pip install faostat-mcp` | FAOSTAT, 245 countries, 1961–present, 3-tier caching | 23 | No | 18 | 2026-10-02 | Community |
| [faostat-mcp-server](https://github.com/cyanheads/faostat-mcp-server) | npm `@cyanheads/faostat-mcp-server` | FAOSTAT over a local SQLite mirror | 7 | No | 2 | 2026-10-25 | Community |
| [uis-mcp-server](https://github.com/SidneyBissoli/uis-mcp-server) | Remote (Cloudflare Workers) | UNESCO UIS education, science and culture statistics; provenance-first | 5 | No | 1 | 2026-10-26 | Community |
| [unesco-mcp](https://github.com/lpicci96/unesco-mcp) | `uvx unesco-mcp` | UNESCO UIS data API | — | No | 3 | 2026-05-04 | Community |
| [global-education-mcp](https://github.com/malkreide/global-education-mcp) | `uvx global-education-mcp` | UNESCO UIS (4,000+ indicators) + OECD Education at a Glance | 10 | No | 1 | 2026-10-04 | Community |
| [uis-sdg4-mcp](https://github.com/yifnli/uis-sdg4-mcp) | Clone + run | UNESCO UIS SDG 4 indicators | — | No | 2 | 2026-05-28 | Community |
| [ilo-mcp-server](https://github.com/SidneyBissoli/ilo-mcp-server) | Remote (Cloudflare Workers) | ILOSTAT labour statistics; provenance-first | 6 | No | 2 | 2026-10-26 | Community |
| [ilostat-mcp-server](https://github.com/cyanheads/ilostat-mcp-server) | npm `@cyanheads/ilostat-mcp-server` | ILOSTAT indicators, series comparison, country profiles; ILO SDMX API for breakdowns, default slices and units | 9 | Yes | 1 | 2026-10-17 | Community |
| [who-gho-mcp-server](https://github.com/cyanheads/who-gho-mcp-server) | npm `@cyanheads/who-gho-mcp-server` | WHO Global Health Observatory, 3,059 indicators, 194 member states | 6 | No | 3 | 2026-10-26 | Community |
| [gho-mcp](https://github.com/Decilion/gho-mcp) | Clone + run | WHO GHO OData API, comparative health systems | — | No | 0 | 2026-09-15 | Community |
| [un-comtrade-mcp-server](https://github.com/cyanheads/un-comtrade-mcp-server) | npm `@cyanheads/un-comtrade-mcp-server` | UN Comtrade trade flows, HS lookups, balances (public preview endpoint) | 9 | No | 4 | 2026-10-17 | Community |
| [unhcr-refugees-mcp-server](https://github.com/cyanheads/unhcr-refugees-mcp-server) | npm `@cyanheads/unhcr-refugees-mcp-server` | UNHCR refugee, IDP and stateless populations, asylum decisions | 8 | No | 1 | 2026-10-20 | Community |
| [unhcr-opendata-gateway-mcp](https://github.com/Edouard-Legoupil/unhcr-opendata-gateway-mcp) | Clone + run | Gateway federating domain-specific UNHCR open-data MCP servers; country and operation snapshots, funding gaps | 8 | No | 0 | 2026-08-24 | Independent (UNHCR staff) |
| [unhcr_iati_mcp](https://github.com/Edouard-Legoupil/unhcr_iati_mcp) | Clone + run | UNHCR IATI financial and programme data | — | No | 0 | 2026-08-28 | Independent (UNHCR staff) |
| [mcp_unhcr](https://github.com/rvibek/mcp_unhcr) | Clone + run | UNHCR refugee populations, demographics, asylum decisions | 5 | No | 0 | 2025-12-13 | Community |
| [UNCHR_MCP_Server](https://github.com/mhadeli/UNCHR_MCP_Server) | Clone + run | UNHCR statistics (demo) | — | No | 0 | 2025-10-29 | Community |
| [medical-mcp](https://github.com/JamesANZ/medical-mcp) | `npm install -g medical-mcp` | WHO GHO, FDA, PubMed, RxNorm | 18 | No | 119 | 2026-10-15 | Community |

### 5b. International Financial Institutions, OECD and EU

| Server | Install | What it does | Tools | SDMX | Stars | Last push | Status |
|--------|---------|-------------|-------|------|-------|-----------|--------|
| [data360-mcp](https://github.com/worldbank/data360-mcp) | `pip install data360-mcp` | World Bank Data360. 16 tools on the `dev` default branch (15 data/visualisation tools listed on the project site, plus the `data360_interactive_choices` UI tool; its README tool table lists 6), 11 resources, 7 prompts; per-observation `claim_id` provenance hash; first bank-official server with anti-hallucination templates | 16 | No | 43 | 2026-09-22 | **Official** (World Bank) |
| [world_bank_mcp_server](https://github.com/anshumax/world_bank_mcp_server) | via Smithery | Wrapper around the World Bank Open Data API. Not a World Bank product | 1 | No | 50 | 2026-09-04 | Community |
| [worldbank-mcp-server](https://github.com/cyanheads/worldbank-mcp-server) | npm `@cyanheads/worldbank-mcp-server` | 29,500+ World Bank Open Data indicators, 200+ countries | 9 | No | 3 | 2026-10-18 | Community |
| [world-bank-data-mcp](https://github.com/llnOrmll/world-bank-data-mcp) | Clone + `uv sync` | World Bank Data360: WDI, HNP, GDF, IDS (1,000+ indicators) | 5 | No | 1 | 2026-01-27 | Community |
| [imf-data-mcp](https://github.com/c-cf/imf-data-mcp) | `uvx --from git+https://github.com/c-cf/imf-data-mcp imf-data-mcp` | IMF IFS, BOP, WEO, CDIS, CPIS, MFS, FSI | 5 | Yes | 14 | 2026-04-05 | Community |
| [imf-mcp-server](https://github.com/cyanheads/imf-mcp-server) | npm `@cyanheads/imf-mcp-server` | IMF SDMX 3.0: 193 dataflows, WEO projections, 190 countries | 6 | Yes | 1 | 2026-10-17 | Community |
| [OECD-MCP](https://github.com/isakskogstad/OECD-MCP) | `npx -y oecd-mcp` | 5,000+ OECD datasets, 17 categories, 38 countries | 9 | Yes | 8 | 2026-04-22 | Community |
| [oecd-mcp-server](https://github.com/cyanheads/oecd-mcp-server) | npm `@cyanheads/oecd-mcp-server` | 1,500+ OECD datasets via SDMX, keyless | 8 | Yes | 2 | 2026-10-24 | Community |
| [eurostat-mcp](https://github.com/ano-kuhanathan/eurostat-mcp) | Clone + run | Eurostat via SDMX 3.0 + Comext SDMX 2.1 | 7 | Yes | 10 | 2026-01-09 | Community |
| [eurostat-mcp-server](https://github.com/cyanheads/eurostat-mcp-server) | `npx -y @cyanheads/eurostat-mcp-server` | 8,933 Eurostat datasets incl. NUTS regional data | 6 | No | 7 | 2026-10-26 | Community |
| [eurostat-mcp-suite](https://github.com/ManoloZocco/eurostat-mcp-suite) | Clone + run | Eurostat SDMX 3.0/2.1 + Comext with DuckDB | — | Yes | 1 | 2026-09-02 | Community |
| [ecb-mcp](https://github.com/scka-de/ecb-mcp) | `npx -y ecb-mcp` | ECB exchange rates, interest rates, yield curves, inflation | 8 | Yes | 4 | 2026-03-31 | Community |
| [mcp-nbb](https://github.com/lacausecrypto/mcp-nbb) | `uvx mcp-nbb` | National Bank of Belgium SDMX API: 221 dataflows | 6 | Yes | 3 | 2026-10-26 | Community |
| [fred-mcp-server](https://github.com/stefanoamorelli/fred-mcp-server) | `npm install fred-mcp-server` | 800,000+ FRED time series | 3 | No | 127 | 2026-08-22 | Community |
| [macronorm-mcp](https://github.com/donkachii/macronorm-mcp) | Clone + run | Unified IMF + World Bank + FRED interface | — | No | 0 | 2026-03-27 | Community |

### 5c. National and Subnational Statistics Offices

| Server | Install | What it does | Tools | SDMX | Stars | Last push | Status |
|--------|---------|-------------|-------|------|-------|-----------|--------|
| [us-census-bureau-data-api-mcp](https://github.com/uscensusbureau/us-census-bureau-data-api-mcp) | Clone + run | US Census Bureau data, demographics, FIPS codes | 5 | No | 106 | 2026-03-13 | **Official** (US Census Bureau) |
| [esankhyiki-mcp](https://github.com/nso-india/esankhyiki-mcp) | Clone + run | India MoSPI / NSO (beta launched 6 Feb 2026): PLFS, CPI, ASI, IIP, NAS, WPI, environment statistics; 4-tool sequential workflow | 4 | No | 147 | 2026-10-26 | **Official** (MoSPI, beta) |
| [datagouv-mcp](https://github.com/datagouv/datagouv-mcp) | Hosted `mcp.data.gouv.fr` | France data.gouv.fr national open-data platform | 10 | No | 1,602 | 2026-10-20 | **Official** (data.gouv.fr, platform operator) |
| [McpDiffusion](https://github.com/InseeFrLab/McpDiffusion) | Hosted beta `mcpdiffusion.lab.sspcloud.fr/mcp`, or self-host (needs Elasticsearch) | France INSEE: key indicators, publications, Melodi datasets and observations, RMES semantic graph (SPARQL) (beta; upstream says it is not yet an officially supported INSEE product) | 12 | No | 2 | 2026-10-26 | **Official** (INSEE, lab, beta) |
| [Idescat MCP](https://github.com/idescat/mcp) | Hosted (streamable HTTP) | Statistical Institute of Catalonia: statistics catalogue, table metadata, JSON-stat data, rendered tables; 3 resources + 4 resource templates | 7 | No | 0 | 2026-10-19 | **Official** (Idescat) |
| [open-census-mcp-server](https://github.com/brockwebb/open-census-mcp-server) | Clone + run | US Census, plain-English queries | 3 | No | 20 | 2026-10-20 | Community |
| [census-mcp-server](https://github.com/cyanheads/census-mcp-server) | npm `@cyanheads/census-mcp-server` | US Census data, variables and geography | 8 | No | 2 | 2026-10-25 | Community |
| [us-gov-open-data-mcp](https://github.com/lzinga/us-gov-open-data-mcp) | `npm install us-gov-open-data-mcp` | 40+ US Gov APIs (Treasury, FRED, BLS, BEA, FDA, EPA, SEC) | 300+ | No | 113 | 2026-10-26 | Community |
| [datagov-mcp-server](https://github.com/melaodoidao/datagov-mcp-server) | `npm install -g @melaodoidao/datagov-mcp-server` | Data.gov general access | — | No | 20 | 2025-04-09 | Community |
| [mcp-statcan](https://github.com/Aryan-Jhaveri/mcp-statcan) | `uvx statcan-mcp-server` | Statistics Canada, 7,000+ tables via WDS | — | No | 7 | 2026-10-26 | Community |
| [gov-ca-mcp](https://github.com/krunal16-c/gov-ca-mcp) | Clone + run | Canada Open Gov (250K+ datasets) + Statistics Canada | 7 | No | 5 | 2025-12-02 | Community |
| [maplestats-mcp](https://github.com/dsanchezp18/maplestats-mcp) | Clone + run | Canadian public data: StatCan, Census, PUMFs, Bank of Canada, CMHC | — | No | 1 | 2026-10-25 | Community |
| [uk-ons-mcp-server](https://github.com/dwain-barnes/uk-ons-mcp-server) | Clone + run | UK Office for National Statistics beta API | — | No | 0 | 2026-07-09 | Community |
| [cso-mcp](https://github.com/gav007/cso-mcp) | Clone + run | Ireland Central Statistics Office (PxStat) | — | No | 0 | 2026-09-19 | Community |
| [ibge-br-mcp](https://github.com/SidneyBissoli/ibge-br-mcp) | `npm install -g ibge-br-mcp` | Brazil IBGE: demographics, SIDRA, census; 227 tests | 23 | No | 12 | 2026-10-26 | Community |
| [bcb-br-mcp](https://github.com/SidneyBissoli/bcb-br-mcp) | `npm install -g bcb-br-mcp` | Banco Central do Brasil: Selic, IPCA, exchange rates, GDP | 17 | No | 10 | 2026-10-23 | Community |
| [inegi-mcp-server](https://github.com/gchavez83/inegi-mcp-server) | Clone + run | Mexico INEGI | 12 | — | 1 | 2026-09-08 | Community |
| [mcp-inegi (Itzamná)](https://github.com/itzamna-mx/mcp-inegi) | Clone + run | Mexico INEGI indicators: population, inflation, employment, GDP, IGAE | — | No | 0 | 2026-10-26 | Community |
| [vintage](https://github.com/tucunar-labs/vintage) | REST API + MCP | Chile point-in-time (vintage) macroeconomic data | — | No | 0 | 2026-10-22 | Community |
| [chilekit](https://github.com/ferando855/chilekit) | CLI + MCP | Chilean public data | — | No | 0 | 2026-10-26 | Community |
| [ukrainian-stats-mcp-server](https://github.com/VladyslavMykhailyshyn/ukrainian-stats-mcp-server) | `npm install -g ukrainian-stats-mcp-server` | Ukraine State Statistics via SDMX v3 | 8 | Yes | 50 | 2025-11-30 | Community |
| [istat_mcp_server](https://github.com/ondata/istat_mcp_server) | Clone + run | Italy ISTAT via SDMX, two-layer caching, rate limiting | 8 | Yes | 23 | 2026-10-25 | Community |
| [istat-mcp](https://github.com/SimonBerg255/istat-mcp) | Clone + run | Italy ISTAT, 4,700+ datasets via SDMX REST | — | Yes | 3 | 2026-03-24 | Community |
| [destatis-mcp](https://github.com/inooLabs/destatis-mcp) | Clone + run | Germany Destatis | 8 | — | 1 | 2025-12-09 | Community |
| [swiss-statistics-mcp](https://github.com/malkreide/swiss-statistics-mcp) | `uvx swiss-statistics-mcp` | Swiss Federal Statistical Office (BFS) STAT-TAB, 682 datasets | 15 | No | 2 | 2026-10-14 | Community |
| [mcp-ine (Spain)](https://github.com/AnCode666/ine-mcp) | Clone + run | Spain INE API | — | No | 2 | 2025-12-30 | Community |
| [tuik-mcp](https://github.com/orhoncan/tuik-mcp) | Clone + run | Türkiye TÜİK via SDMX REST | — | Yes | 16 | 2026-09-20 | Community |
| [evds-mcp](https://github.com/orhoncan/evds-mcp) | Clone + run | Central Bank of the Republic of Türkiye EVDS | — | No | 2 | 2026-10-26 | Community |
| [spoerg-dst](https://github.com/Juul94/spoerg-dst) | Clone + run | Statistics Denmark, plain-language queries | — | No | 0 | 2026-10-25 | Community |
| [Norway-Open-Data-MCP](https://github.com/iamkm1/Norway-Open-Data-MCP) | Clone + run | Norway open data (stdio) | — | No | 0 | 2026-10-16 | Community |
| [statsmapped-mcp](https://github.com/ActiveGuy/statsmapped-mcp) | Clone + run | Ireland CSO and UK public data via the StatsMapped API | — | No | 0 | 2026-10-23 | Community |
| [mcp-cbs-cijfers-open-data](https://github.com/dstotijn/mcp-cbs-cijfers-open-data) | Clone + run | Netherlands CBS Open Data (Go) | 7 | No | 9 | 2025-03-18 | Community |
| [SCB-MCP](https://github.com/isakskogstad/SCB-MCP) | Hosted (Render) | Statistics Sweden | — | No | 9 | 2026-04-22 | Community |
| [Kolada-MCP](https://github.com/isakskogstad/Kolada-MCP) | `npm install -g kolada-mcp-server` | Sweden Kolada municipal data | — | — | 12 | 2026-04-22 | Community |
| [israel-statistics-mcp](https://github.com/reuvenaor/israel-statistics-mcp) | `npx -y @reuvenorg/israel-statistics-mcp` | Israel CBS | — | — | 4 | 2026-10-07 | Community |
| [korea-stats-mcp](https://github.com/Dayoooun/korea-stats-mcp) | `npx -y @kimdayoun/korea-stats-mcp` | Statistics Korea KOSIS, natural-language queries | — | No | 16 | 2026-10-01 | Community |
| [data-go-mcp-servers](https://github.com/Koomook/data-go-mcp-servers) | `pip install data-go-mcp.<server>` | South Korea data.go.kr (multi-server monorepo) | 21 | No | 368 | 2025-09-16 | Community |
| [estat-mcp](https://github.com/ajtgjmdjp/estat-mcp) | `pip install estat-mcp` | Japan e-Stat government statistics | 4 | No | 10 | 2026-08-23 | Community |
| [cnbs-mcp-server](https://github.com/Eliseowzy/cnbs-mcp-server) | Clone + run | China National Bureau of Statistics | — | No | 0 | 2026-07-27 | Community |
| [nso1212-mcp](https://github.com/tsedenbaljir/nso1212-mcp) | Clone + run | Mongolia NSO (1212.mn) | 6 | — | 0 | 2026-04-23 | Community |
| [tnso-mcp-server](https://github.com/aard-ai/tnso-mcp-server) | Clone + run | Thailand National Statistical Office via SDMX | — | Yes | 0 | 2026-08-10 | Community |
| [mcp-server-abs](https://github.com/seansoreilly/mcp-server-abs) | Clone + run | Australia ABS via SDMX-ML | 1 | Yes | 9 | 2026-09-18 | Community |
| [australian-public-data-mcp](https://github.com/J-King-Dottie/australian-public-data-mcp) | Hosted | Australian, Pacific and global public data, live catalogue search | — | — | 4 | 2026-10-26 | Community |
| [ghana-data-mcp](https://github.com/epigos/ghana-data-mcp) | Hosted (Cloudflare Workers) | Ghana Statistical Service, Bank of Ghana, Ghana Stock Exchange | — | No | 3 | 2026-10-05 | Community |
| [cbn_mcp](https://github.com/Zfinix/cbn_mcp) | Clone + run | Central Bank of Nigeria data and circulars | — | No | 19 | 2025-09-22 | Community |
| [sl-economy-mcp](https://github.com/Akashwim/sl-economy-mcp) | Clone + run | Central Bank of Sri Lanka economic data (unofficial) | — | No | 1 | 2026-10-16 | Community |
| [shorkari-mcp](https://github.com/nadimtuhin/shorkari-mcp) | Edge connector | Bangladesh public data (unofficial) | — | No | 0 | 2026-10-22 | Community |

### 5d. Multi-Source Aggregators

| Server | Install | What it does | Tools | SDMX | Stars | Last push | Status |
|--------|---------|-------------|-------|------|-------|-----------|--------|
| [agent-toolkit (Data Commons)](https://github.com/datacommonsorg/agent-toolkit) | `pip install datacommons-mcp`; also hosted on Google Cloud | Google Data Commons knowledge graph: UN agencies, surveys, census, climate (PyPI since July 2025; launch announced 24 Sep 2025) | — | No | 149 | 2026-09-15 | **Official** (Google, platform operator) |
| [openecon-data](https://github.com/hanlulong/openecon-data) | Hosted (openecon.ai) | 330K indicators from FRED, World Bank, IMF, Eurostat and others | — | — | 91 | 2026-10-23 | Community |
| [cluster-mcp](https://github.com/baraninja/cluster-mcp) | Clone + run | Monorepo: World Bank, Eurostat, OECD, ILO, WHO, Comtrade | 29 | Yes | 1 | 2026-01-01 | Community |
| [econstats-mcp](https://github.com/joshfwaldman1/econstats-mcp) | `bunx econstats-mcp` | FRED, BLS, BEA, IMF, World Bank, ECB, with an economist's methodology guide | 11 | — | 0 | 2026-04-28 | Community |
| [socioeconomic-data-mcp](https://github.com/fpanier/socioeconomic-data-mcp) | Clone + run | Eurostat, World Bank, OECD, IMF, FRED | — | — | 2 | 2026-05-29 | Community |
| [development-data-mcp](https://github.com/lbruce-wq/development-data-mcp) | Clone + run | Discover, retrieve and compare international development data | — | — | 2 | 2026-09-16 | Community |
| [malja-mcp](https://github.com/marsaplatform/malja-mcp) | Clone + run | Humanitarian open data: UNHCR, World Bank, HDX, ReliefWeb | — | No | 0 | 2026-10-24 | Community |
| [sdmx-mcp-gateway](https://github.com/Baffelan/sdmx-mcp-gateway) | Clone + run | Gateway for SDMX endpoints that builds query paths. Maintained by Baffelan, a data consultancy; open source, not offered as a product or service, so labelled community | — | Yes | 1 | 2026-10-27 | Community |
| [Pipeworx servers](https://github.com/pipeworx-io) | Hosted | Per-source servers (IMF, UNESCO UIS, UN Comtrade, HDX, INEGI, Statistics Finland, Israel CBS, SDMX structure, …). Some are listed elsewhere as "Official IMF Data MCP Server"; Pipeworx is a third party | — | — | — | 2026-09-28 | Commercial |

### 5e. Registries and Discovery (not servers themselves)

| Resource | Type | What it does | Status |
|---|---|---|---|
| [fed-data-mcp-registry](https://github.com/GSA-TTS/fed-data-mcp-registry) | Curated registry | US GSA-TTS curated registry of federal-data MCP servers | **Official** (US GSA) |
| [Official MCP Registry](https://registry.modelcontextprotocol.io/) | Protocol registry | Queryable catalogue of published servers; several statistics servers above are listed there | Official (MCP project) |

### 5f. Also found, not reviewed (2026-10-27)

The tables above include every official and independent server, and the community servers that are either published (package or hosted endpoint), have five or more stars, or are the only server for their source. The servers below are further community or commercial implementations for sources that already have a listed server. They are named for completeness and have not been checked; most have 0–2 stars.

- **Eurostat:** dcerecedo/eurostat-mcp, alexwall1/eurostat-mcp, barrylecherous932/eurostat-mcp-server, dar4datascience/duckdb-eurostat-mcp, aethar-dev/eurostatapi-mcp, Taru0208/eurostat-mcp-server, Mich120232024/eurostat-mcp-server, linimeanie/eurostat-tam-mcp
- **IMF / OECD / World Bank:** jfeferman/imf-mcp, Mich120232024/imf-mcp-server, ToolOracle/oecdoracle, tianyuio/worldbank-mcp, guptaprakhariitr/world-bank-economic-mcp, MaykolMedrano/mcp_wbgapi360
- **US Census:** kaman1/mcp_census_server, shawndrake2/mcp-census, shawndrake2/mcp-tigerweb, georgemandis/mcp-census-data, hollandkevint/CensusChat, Taru0208/us-census-mcp-server
- **Statistics Canada:** hemaaanth/statcan2, MillstoneHomes/my-statcan-mcp, JoseJimenez-M/mcp-statcan-odcaf, dsanchezp18/maplestats-mcp (listed above)
- **Spain INE:** agmalaga2020/ine-universal-mcp, manalejandro/mcp-ine, dlbcodes/ine-mcp, dcerecedo/ine-mcp
- **Statistics Korea (KOSIS):** seolcoding/korean-stat-mcp, lucidwatper/Kosis-mcp, 042Jason/kosis-mcp, dodopd/kosis-mcp
- **Japan e-Stat:** koizumikento/e-stats-mcp; registry entries `io.github.easakura/japan-official-statistics-mcp`, `io.github.fujimura-ui/japan-official-statistics-mcp`
- **Statistics Sweden:** ashwinvis/scb-opendata-mcp
- **France INSEE:** Oshinsu/mcp-insee, aureTheDev/insee-mcp (business-register servers for SIRENE are out of scope)
- **Peru INEI:** JOSETRA44/INEI-mcp · **Brazil:** lucianoon/mcp-dados-br
- **Finland / Poland:** registry entries `io.github.Ukraine-Territorial-MCP/finland-statistics`, `.../poland-statistics`, `.../eurostat-statistics` (experimental); Pipeworx `mcp-statfin-fi`
- **UNHCR / WHO:** mhadeli/unhcr_mcp_server, Helloitsaman/unhcr-mcp-server, MaxMLang/who-sentinel-mcp
- **Multi-source (community or commercial):** dregon03/statisticsoftheworld, Adarsh4052/starwell-mcp, rabidlego25/macro-mcp, ContentWriterco (Economic-, Health- and Labour-Market-Statistics-MCP), nexusforge-tools/mcp-eu-finance, Azreus1991/government-data-mcp-servers, datavilleorg/dataville-mcp; Apify-hosted SDMX, Eurostat, OECD and Comtrade scrapers

### 5g. Research and other related sources (not official statistics)

Servers whose data are not official statistics, listed because users and agents often reach for them next to official series. They are not counted in the section totals above. **Type** says what the data are; **Status** still says who maintains the server, and for a research producer that maintains its own server we write "producer-maintained" rather than "official", so the label cannot be read as "official statistics".

| Server | Install | What it does | Type | Tools | Stars | Last push | Status |
|--------|---------|-------------|------|-------|-------|-----------|--------|
| [IHME GBD 2023 connector](https://www.healthdata.org/explore-gbd-2023-study-estimates-claude) | Hosted connector (currently Claude only) | IHME Global Burden of Disease 2023 results: child mortality, mortality probabilities, maternal mortality, fertility, life expectancy, population, coverage covariates, impairments, risk exposures, methods search; free for non-commercial use. Model estimates with 95% uncertainty intervals, not official statistics | Research estimates | 10+ | — | 2026 | Producer-maintained (IHME) |
| [wid-mcp-server](https://github.com/emmanueltsallis/wid-mcp-server) | Clone + run | Live queries to the World Inequality Database (income and wealth distribution) | Research dataset | — | 1 | 2026-06-26 | Community |
| [reliefweb-mcp-server](https://github.com/cyanheads/reliefweb-mcp-server) | npm `@cyanheads/reliefweb-mcp-server` | ReliefWeb (OCHA) reports, disasters, country profiles. Documents more than statistics | Humanitarian reports | — | 2 | 2026-10-26 | Community |
| [European-Parliament-MCP-Server](https://github.com/Hack23/European-Parliament-MCP-Server) | `npx -y european-parliament-mcp-server` | European Parliament open data | Parliamentary data | 63 | 29 | 2026-10-26 | Community |

### Removed since the April 2026 refresh

- `shahzadarain/unhcr-mcp-server`: repository no longer exists (HTTP 404, 2026-10-26).
- `Mich120232024/worldbank-mcp-server`: archived by its owner.
- `namiraprita/document-reports-mcp` (World Bank Documents & Reports API) moved out of scope: documents, not statistics.

### Known gaps (no MCP server found, 2026-10-26)

**Partly closed since April 2026, by community servers only:** UNESCO/UIS, ILO/ILOSTAT, WHO GHO (dedicated), UN Comtrade. None is maintained by the agency.

**Still open:** UNDP/HDI, UNSD SDG Global Database API (the UN System Data Commons endpoint covers some SDG series), UN DESA Population (WPP), UNAIDS, WFP, WTO, IAEA. BIS has no dedicated or official server, but its data is reachable through the community aggregator openecon-data. Official servers from Eurostat, the IMF, the OECD and central banks: none found; every server for these sources is community or commercial. National offices with no server found: Stats NZ, INDEC (Argentina), Statistics South Africa, Kenya KNBS, Nigeria NBS, Indonesia BPS.

**Official NSO servers so far:** US Census Bureau, India MoSPI, France (data.gouv.fr and INSEE Lab), Catalonia (Idescat). Every other national server listed is community-built.

---

## 6. STATA

| Server | Install | What it does | Stars | Trust |
|--------|---------|-------------|-------|-------|
| stata-mcp (SepineTam) | `pip install stata-mcp` | Execute Stata commands, run .do files, security guard, RAM monitoring | 116 | Medium |
| mcp-stata (tmonk/LSE) | `pip install mcp-stata` | Execute commands, inspect data, retrieve r()/e() results, view graphs | 41 | Low |

---

## 7. R PROGRAMMING

| Server | Install | What it does | Stars | Trust |
|--------|---------|-------------|-------|-------|
| posit-dev/mcptools | `install.packages("mcptools")` | Official Posit: run R code in active R sessions, full tidyverse/ggplot | 158 | High |
| finite-sample/rmcp | `pip install rmcp` | 52 statistical tools, 429 R packages (econometrics, ML, time series, Bayes) | 197 | Medium |
| IMNMV/ClaudeR | `remotes::install_github("IMNMV/ClaudeR")` | RStudio-to-LLM bridge, execute code + see plots real-time | 141 | Medium |
| devOpifex/mcpr | `remotes::install_github("devOpifex/mcpr")` | MCP protocol SDK for R: build custom MCP servers from R functions | 62 | Low |

---

## 8. PYTHON CODE EXECUTION

| Server | Install | What it does | Stars | Trust |
|--------|---------|-------------|-------|-------|
| pydantic/mcp-run-python | `npx @pydantic/mcp-run-python` | WASM-sandboxed Python execution (Pyodide/Deno), auto-deps | 15,400 | High |
| bazinga012/mcp_code_executor | `pip install mcp-code-executor` | Execute Python in conda/venv/uv environments | 183 | Medium |
| evalstate/mcp-py-repl | Docker-based | Persistent Python REPL with pandas/matplotlib/seaborn | — | Low |
| chrishayuk/mcp-code-sandbox | pip install (see repo) | E2B cloud sandbox / Firecracker microVM execution | 16 | Low |
| E2B Code Sandbox | `pip install e2b-code-interpreter` | Cloud-sandboxed Python/JS execution | 1,000+ | High |

---

## 9. PYTHON TESTING & LINTING

| Server | Install | What it does | Stars | Trust |
|--------|---------|-------------|-------|-------|
| python-lft-mcp | `pip install python-lft-mcp` | All-in-one: ruff + black + pytest + mypy + pylint (70+ config files) | — | Medium |
| mcp-server-analyzer | `pip install mcp-server-analyzer` | Ruff linting + Vulture dead code detection, quality scores 0-100 | — | Low |
| ruff-mcp-server | Clone github.com/drewsonne/ruff-mcp-server | Pure Ruff: check, format, fix tools | — | Low |
| mcp-code-checker | Clone github.com/MarcusJellinghaus/mcp-code-checker | Pylint + pytest with LLM-friendly prompts | — | Low |
| pytest-mcp-server | Clone github.com/tosin2013/pytest-mcp-server | Pytest failure tracking + debugging principles | — | Low |

---

## 10. PYTHON DEBUGGING

| Server | Install | What it does | Stars | Trust |
|--------|---------|-------------|-------|-------|
| mcp-pdb | `pip install mcp-pdb` | Python debugger via pdb: breakpoints, step, inspect variables | 44 | Low |
| mcp-debugpy | Clone github.com/markomanninen/mcp-debugpy | AI-assisted debugging via DAP + pytest JSON reports | — | Low |
| mcp-debugger | Clone github.com/debugmcp/mcp-debugger | General LLM-driven step-through debugger | — | Low |

---

## 11. PYTHON PACKAGE MANAGEMENT

| Server | Install | What it does | Stars | Trust |
|--------|---------|-------------|-------|-------|
| uv-mcp | `pip install uv-mcp` | uv environment inspection, dependency resolution, venv management | 4 | Low |
| uv-docs-mcp | Clone github.com/StevenBtw/uv-docs-mcp | uv documentation access via MCP | — | Low |
| python-dependency-manager | Clone (KemingHe) | Cross-references pip/conda/poetry/uv/pixi/pdm docs | — | Low |

---

## 12. JUPYTER NOTEBOOKS

| Server | Install | What it does | Stars | Trust |
|--------|---------|-------------|-------|-------|
| jupyter-mcp-server | `pip install jupyter-mcp-server` | Create/edit/execute cells, multimodal output, JupyterHub support | 950 | High |

---

## 13. DATABASES

| Server | Install | What it does | Stars | Trust |
|--------|---------|-------------|-------|-------|
| DBHub (Bytebase) | `npx @bytebase/dbhub@latest --dsn "postgres://..."` | PostgreSQL, MySQL, MariaDB, SQL Server, SQLite; SSH tunneling, SSL | 2,400 | High |
| mcp-server-sqlite | `pip install mcp-server-sqlite` | SQLite interaction + BI memos (official, archived) | Official | Official |
| server-postgres | `npx -y @modelcontextprotocol/server-postgres` | Read-only PostgreSQL (official, archived — use DBHub) | Official | Official |

---

## 14. BROWSER AUTOMATION

| Server | Install | What it does | Stars | Trust |
|--------|---------|-------------|-------|-------|
| Playwright MCP | `npx -y @playwright/mcp@latest` | Microsoft: accessibility-tree browsing, LLM-friendly, fast | 28,500 | Official |
| Puppeteer MCP | `npx -y @modelcontextprotocol/server-puppeteer` | Navigation, forms, screenshots, JS execution (archived) | Official | Official |
| mcp-playwright (EA) | `npm install -g @executeautomation/playwright-mcp-server` | Browser + API automation for Claude/Cursor | — | Medium |

---

## 15. GITHUB / GIT

| Server | Install | What it does | Stars | Trust |
|--------|---------|-------------|-------|-------|
| GitHub (Official) | `npx -y @modelcontextprotocol/server-github` | Repos, issues, PRs, search, file operations | Official | Official |
| Git (Official) | `npx -y @modelcontextprotocol/server-git` or `pip install mcp-server-git` | Clone, commit, branch, diff, log | Official | Official |
| Git (cyanheads) | `npx @cyanheads/git-mcp-server@latest` | Enhanced: worktree management, HTTP transport | — | Medium |

---

## 16. SOCIAL MEDIA

| Server | Install | What it does | Stars | Trust |
|--------|---------|-------------|-------|-------|
| mcp-twitter (PyPI) | `pip install mcp-twitter` | Search tweets, retrieve profiles, post, analyze trends | — | Low |
| mcp-twitter-server (npm) | `npm i mcp-twitter-server` | 33 Twitter API tools + 20 SocialData research tools | — | Low |
| twitter-mcp-server | Clone github.com/taazkareem/twitter-mcp-server | Post, search, manage followers via natural language | — | Low |
| linkedin-mcp-server (npm) | `npx linkedin-mcp-server` | LinkedIn data access with OAuth 2.0 | — | Low |
| linkedin-mcp-server (scraper) | uvx-based (stickerdaniel) | Scrape profiles, companies, jobs | — | Low |
| social-cli-mcp | Clone github.com/Alemusica/social-cli-mcp | Multi-platform: Twitter/X, Reddit, LinkedIn, Instagram | — | Low |
| social-media-mcp-server | `npm i @muhammadhamidraza/social-media-mcp-server` | YouTube, LinkedIn, Facebook, Instagram, TikTok, X (549 tools) | — | Low |

---

## 17. CLOUD STORAGE

| Server | Install | What it does | Stars | Trust |
|--------|---------|-------------|-------|-------|
| Google Drive (community) | Clone github.com/felores/gdrive-mcp-server | List, read, search files + Sheets | — | Low |
| Google Drive + Docs/Sheets | Clone github.com/piotr-agier/google-drive-mcp | Drive + Docs + Sheets + Slides + Calendar | — | Low |
| Dropbox (Official Remote) | URL: `https://mcp.dropbox.com/mcp` (beta) | Direct Dropbox integration | Official | Official |
| OneDrive | `pip install git+https://github.com/MrFixit96/onedrive-mcp-server.git` | Browse, read, upload via Microsoft Graph API | — | Low |

---

## 18. NOTE-TAKING / KNOWLEDGE

| Server | Install | What it does | Stars | Trust |
|--------|---------|-------------|-------|-------|
| Notion (Official) | `npx @notionhq/notion-mcp-server` | Full Notion API: pages, databases, blocks, search | Official | Official |
| Notion (community) | `npm install --global mcp-notion-server` | Notion + Markdown conversion for token efficiency | 799 | Medium |
| Obsidian | `npm install obsidian-mcp-server` | Read/write/search notes, tags, frontmatter | 299 | Medium |
| Memory (Official) | `npx -y @modelcontextprotocol/server-memory` | Knowledge graph: entities, relations, observations | Official | Official |
| mcp-knowledge-graph | `npx -y mcp-knowledge-graph` | Enhanced persistent memory via knowledge graph | — | Low |
| memento-mcp | `npm install @gannonh/memento-mcp` | Knowledge graph memory system | — | Low |
| mcp-memory-service | `pip install mcp-memory-service` | Persistent memory for agent pipelines (LangGraph, CrewAI) | — | Low |

---

## 19. DOCUMENTS / PDF

| Server | Install | What it does | Stars | Trust |
|--------|---------|-------------|-------|-------|
| PDF Reader (SylphxAI) | `npx @sylphx/pdf-reader-mcp` | Text/image extraction, metadata, parallel processing | 518 | Medium |
| AWS Document Loader | Part of awslabs/mcp | PDF, Word, Excel, PowerPoint, images | 4,700 | High |

---

## 20. AI / ML / HUGGING FACE

| Server | Install | What it does | Stars | Trust |
|--------|---------|-------------|-------|-------|
| Hugging Face MCP | `pip install huggingface-mcp-server` | Search models/datasets/Spaces/papers, compare performance, run Gradio tools | Official | Official |
| mcp-hfspace | `npx -y @llmindset/mcp-hfspace` | Use HF Spaces directly from Claude Desktop | — | Low |

---

## 21. LaTeX / OVERLEAF

| Server | Install | What it does | Stars | Trust |
|--------|---------|-------------|-------|-------|
| OverleafMCP | Clone github.com/mjyoo2/OverleafMCP + npm install | Access Overleaf projects via Git, parse LaTeX structure | 78 | Low |

---

## 22. CLOUD PROVIDERS

| Server | Install | What it does | Stars | Trust |
|--------|---------|-------------|-------|-------|
| AWS MCP | `uvx awslabs.aws-api-mcp-server@latest` | Suite: AWS API, docs, CDK, Terraform, pricing | 4,700 | Official |
| Azure MCP | `npx -y @azure/mcp@latest server start` | Cosmos DB, Storage, Monitor/Log Analytics | Official | Official |
| Google Cloud MCP | `npx @google-cloud/gcloud-mcp` | gcloud CLI interaction | Official | Official |
| Docker MCP Gateway | Built into Docker Desktop 4.59+ | Container/compose management | Official | Official |
| Kubernetes (Flux159) | `npx mcp-server-kubernetes` | Multi-cluster K8s management, non-destructive mode | 1,100 | High |
| Kubernetes (Red Hat) | npm/pip/binary/Docker | 40+ K8s/OpenShift tools, Helm support | Official | High |

---

## 23. COMMUNICATION

| Server | Install | What it does | Stars | Trust |
|--------|---------|-------------|-------|-------|
| Slack (Official) | `npx -y @modelcontextprotocol/server-slack` | Channels, messages, threads, reactions, users | Official | Official |
| Slack (korotovsky) | Clone github.com/korotovsky/slack-mcp-server | No special permissions, DMs, Group DMs, GovSlack | — | Medium |
| Google Calendar | Clone github.com/nspady/google-calendar-mcp | Manage Google Calendar events | — | Low |
| Unified Calendar | Clone github.com/MarimerLLC/calendar-mcp | Microsoft 365 + Outlook + Google Calendar | — | Low |
| Outlook Calendar | `npm install -g outlook-calendar-mcp` | Local Outlook calendars (Windows only) | — | Low |

---

## 24. SECURITY / AUDITING

| Server | Install | What it does | Stars | Trust |
|--------|---------|-------------|-------|-------|
| MCP Server Audit | github.com/ModelContextProtocol-Security/mcpserver-audit | Community audit database for MCP servers | — | Medium |

---

## RESOURCES

- **Official MCP Registry:** <https://registry.modelcontextprotocol.io/>
- **Awesome MCP Servers:** <https://github.com/punkpeye/awesome-mcp-servers>
- **Awesome MCP (wong2):** <https://github.com/wong2/awesome-mcp-servers>
- **Smithery.ai:** <https://smithery.ai/> (6,000+ servers)
- **PulseMCP:** <https://www.pulsemcp.com/>
- **mcpservers.org:** <https://mcpservers.org/>
- **MCP Security Audits:** <https://github.com/ModelContextProtocol-Security>
- **Vulnerable MCP Database:** <https://vulnerablemcp.info/>
