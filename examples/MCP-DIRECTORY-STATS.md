# MCP Server Directory

Comprehensive list of pre-built MCP servers researched March 2026.
Trust levels: **Official** (vendor-maintained), **High** (1K+ stars, reputable org), **Medium** (100+ stars), **Low** (small/unaudited).

---

## 1. OFFICIAL REFERENCE SERVERS (modelcontextprotocol/servers)

Repo: https://github.com/modelcontextprotocol/servers (81K stars)

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

### 5a. UN Agencies

| Server | Install | What it does | Tools | SDMX | Stars | Trust |
|--------|---------|-------------|-------|------|-------|-------|
| [unicefstats-mcp](https://github.com/jpazvd/unicefstats-mcp) | `pip install unicefstats-mcp` | UNICEF 790+ child indicators, disaggregations, benchmarked (EQA=0.990, replicated) | 7 | Yes | — | Low |
| [sdmx-mcp](https://github.com/unicef-drp/sdmx-mcp) | Clone + run | Generic SDMX server, any registry (defaults UNICEF), 0% hallucination | 23 | Yes | — | Low |
| [unicef-datawarehouse-mcp](https://github.com/tryolabs/unicef-datawarehouse-mcp) | Clone + run | UNICEF dataflows via SDMX (by Tryolabs) | 3 | Yes | 0 | Low |
| [mcp_unhcr](https://github.com/rvibek/mcp_unhcr) | Clone + run | UNHCR refugee populations, demographics, asylum decisions | 5 | No | 0 | Low |
| [medical-mcp](https://github.com/JamesANZ/medical-mcp) | `npm install medical-mcp` | WHO GHO, FDA, PubMed, RxNorm — 18 medical/health tools | 18 | No | 78 | Medium |

### 5b. International Organizations

| Server | Install | What it does | Tools | SDMX | Stars | Trust |
|--------|---------|-------------|-------|------|-------|-------|
| [fred-mcp-server](https://github.com/stefanoamorelli/fred-mcp-server) | `npm install fred-mcp-server` | 800,000+ FRED time series (GDP, CPI, rates) | 3 | No | 72 | Medium |
| [world_bank_mcp_server](https://github.com/anshumax/world_bank_mcp_server) | via Smithery | World Bank Open Data: population, poverty, GDP (200+ countries) | 1 | No | 45 | Low |
| [world-bank-data-mcp](https://github.com/llnOrmll/world-bank-data-mcp) | Clone + `uv sync` | World Bank Data360: WDI, HNP, GDF, IDS (1,000+ indicators) | 5 | No | 0 | Low |
| [imf-data-mcp](https://github.com/c-cf/imf-data-mcp) | `pip install imf-data-mcp` | IMF datasets: IFS, BOP, WEO, CDIS, CPIS, MFS, FSI via SDMX | 10 | Yes | 7 | Low |
| [OECD-MCP](https://github.com/isakskogstad/OECD-MCP) | `npm install oecd-mcp` | 5,000+ OECD datasets, 17 categories, 38 countries via SDMX | 9 | Yes | 1 | Low |
| [eurostat-mcp](https://github.com/ano-kuhanathan/eurostat-mcp) | Clone + run | Eurostat EU statistics via SDMX 3.0 + Comext SDMX 2.1 | 7 | Yes | 2 | Low |

### 5c. National Statistics Offices

| Server | Install | What it does | Tools | SDMX | Stars | Trust |
|--------|---------|-------------|-------|------|-------|-------|
| [us-census-bureau-data-api-mcp](https://github.com/uscensusbureau/us-census-bureau-data-api-mcp) | Clone + run | **Official** US Census Bureau data, demographics, FIPS codes | 5 | No | 57 | **High** |
| [us-gov-open-data-mcp](https://github.com/lzinga/us-gov-open-data-mcp) | `npm install us-gov-open-data-mcp` | 40+ US Gov APIs (Treasury, FRED, BLS, BEA, FDA, EPA, SEC) | 300+ | No | 91 | Medium |
| [ibge-br-mcp](https://github.com/SidneyBissoli/ibge-br-mcp) | `npm install ibge-br-mcp` | Brazil IBGE: demographics, SIDRA, census, 227 tests, 97% coverage | 22 | No | — | Low |
| [ukrainian-stats-mcp-server](https://github.com/VladyslavMykhailyshyn/ukrainian-stats-mcp-server) | `npm install ukrainian-stats-mcp-server` | Ukraine State Statistics via SDMX v3 | 8 | Yes | 49 | Low |
| [istat_mcp_server](https://github.com/ondata/istat_mcp_server) | Clone + run | Italy ISTAT via SDMX, two-layer caching, rate limiting | 7 | Yes | 1 | Low |
| [mcp-server-abs](https://github.com/seansoreilly/mcp-server-abs) | Clone + run | Australia ABS via SDMX-ML | 1 | Yes | 7 | Low |
| [mcp-cbs-cijfers-open-data](https://github.com/dstotijn/mcp-cbs-cijfers-open-data) | Clone + run | Netherlands CBS Open Data (Go) | 7 | No | 7 | Low |
| [gov-ca-mcp](https://github.com/krunal16-c/gov-ca-mcp) | Clone + run | Canada Open Gov: 250K+ datasets + Statistics Canada | 7 | No | 1 | Low |

### 5d. Multi-Source

| Server | Install | What it does | Tools | SDMX | Stars | Trust |
|--------|---------|-------------|-------|------|-------|-------|
| [cluster-mcp](https://github.com/baraninja/cluster-mcp) | Clone + run | 6-server monorepo: World Bank, Eurostat, OECD, ILO, WHO, Comtrade | 29 | Yes | 1 | Low |

### Known gaps (no MCP server exists)

FAO/FAOSTAT, UNESCO/UIS, ILO/ILOSTAT (dedicated), UNDP/HDI, UNSD SDG API, UN DESA Population, UNAIDS, WFP.

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

- **Official MCP Registry:** https://registry.modelcontextprotocol.io/
- **Awesome MCP Servers:** https://github.com/punkpeye/awesome-mcp-servers
- **Awesome MCP (wong2):** https://github.com/wong2/awesome-mcp-servers
- **Smithery.ai:** https://smithery.ai/ (6,000+ servers)
- **PulseMCP:** https://www.pulsemcp.com/
- **mcpservers.org:** https://mcpservers.org/
- **MCP Security Audits:** https://github.com/ModelContextProtocol-Security
- **Vulnerable MCP Database:** https://vulnerablemcp.info/
