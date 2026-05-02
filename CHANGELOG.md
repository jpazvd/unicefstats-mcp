# Changelog

All notable changes to unicefstats-mcp are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/).

**Package:** [pypi.org/project/unicefstats-mcp](https://pypi.org/project/unicefstats-mcp/) · **Source:** [github.com/jpazvd/unicefstats-mcp](https://github.com/jpazvd/unicefstats-mcp)

## [Unreleased]

## [0.6.2] — 2026-05-01

Server-side country-name resolver. The structural fix for the
country-substitution failure mode that v0.6.1 only patched with a
post-hoc directive.

The v0.6.0 full pilot (mcp060_full) showed the model calls `get_data`
with the WRONG ISO3 code on ~85% of hallucination-tier queries (asked
about Burundi, calls `get_data(countries=['BEL'])`). The mistake is
inside the model — it's converting the country name to an ISO3 code
from memory before the tool is called. v0.6.1 tried to catch this after
the fact (echo back the name, ask the model to verify); v0.6.2
prevents it by removing the model's need to do the mapping at all.

### Changed

- **`get_data` `countries` parameter now accepts ISO3 codes OR full
  country names** (case-insensitive). Pass whichever you have from the
  user's question; the server canonicalises:
  - `countries=['Burundi']` → resolves to `['BDI']`
  - `countries=['BDI', 'Belgium']` → `['BDI', 'BEL']`
  - `countries=['Cote d'Ivoire']` → `['CIV']`
  - `countries=['USA', 'UK']` → `['USA', 'GBR']`
- **Synonyms accepted**: `'USA'`/`'United States'`, `'UK'`/`'Great Britain'`,
  `'Ivory Coast'`, `'South Korea'`/`'North Korea'`, `'DRC'`,
  `'Czech Republic'`, `'Burma'`, `'Vatican'`, `'Eswatini'`/`'Swaziland'`,
  etc. (15 common alternates).
- The validator's "Invalid ISO3 code: 'X'" error is replaced with a
  resolver error: "Could not resolve country/countries: 'X'".

### Added

- **`country_resolutions` field on `get_data`**: dict of
  `{user_input: resolved_iso3}` showing every name → code resolution
  the server performed. Empty if the caller passed only ISO3 codes.
  The model can confirm "Burundi → BDI" matched the user's question.
- **`countries_resolved_to`**: the list of canonical ISO3 codes the
  server actually queried with, separate from `countries_requested`
  which keeps the original user input.
- New module `unicefstats_mcp.country_resolver` with `resolve_country`
  and `resolve_countries` helpers. Builds a name → ISO3 index from the
  unicefdata `_unicefdata_countries.yaml` file (450+ countries, SDMX
  CL_COUNTRY codelist).

### Deprecated

- The v0.6.1 `verify_country_directive` field stays for backward
  compatibility but is now informational rather than load-bearing —
  the resolver eliminates the failure mode it was designed to flag.

### Tested

- 3 new tests in `test_get_data.py`:
  `test_country_name_input_resolved`,
  `test_country_mixed_iso3_and_name_input`,
  `test_unresolvable_country_returns_error`.
- Resolver smoke-tested on the v0.6.0 mcp060_full failure cases:
  Burundi/BEL, Costa Rica/HND, Cote d'Ivoire/CIV all resolve correctly.

## [0.6.1] — 2026-05-01

Country-substitution hardening for `get_data`. The full n=500 pilot of v0.6.0
(mcp060_full) revealed that v0.6.0's frontier check works as designed (0 true
forward-of-frontier fabrications among correct-country calls), but the model
has an ~85% rate of calling `get_data` with the WRONG country code on
hallucination-tier queries (e.g., asked about Burundi, calls
`get_data(countries=['BEL'])` and reports Belgium). The MCP returned valid
data — for the wrong country.

This release adds a single, targeted fix: `get_data` now emits the resolved
country names prominently at the top of the response with an explicit
verify-country directive so the model sees "you got Belgium" when it asked
about Burundi and can self-correct.

### Added

- **`countries_returned_with_names` field on `get_data`**: dict of
  `{ISO3: full_name}` for every country in the response. Surfaces
  immediately under `countries_requested` so the model literally sees
  "I called this with BEL → I got Belgium" in plain text.
- **`verify_country_directive`**: instruction to compare returned country
  names against the user's question and retry with a different ISO3 code if
  there's a mismatch.

### Why not just refuse the call?

The MCP server cannot know what the user *meant*. The model's tool call has
no provenance of the original user query, so the server can't validate
intent. The fix is to make the country name visible enough that the model
itself catches the substitution.

### Tested

- `tests/test_get_data.py::test_countries_returned_with_names` asserts the
  new field is populated correctly for multi-country queries.
- All 134 existing tests still pass.

## [0.6.0] — 2026-05-01

Server-side hardening for the forward-of-frontier hallucination failure mode. v0.5.1 shipped the
skill-side approach (`unicef://system-prompt` + `unicef://context` resources); v0.6.0 moves the
load-bearing enforcement INTO the server so it works regardless of whether the client loads the
resources or follows the directive. The skill resources stay (now thinner) — the server is now
the structural enforcement layer.

### Added

- **Pre-flight year-frontier check on `get_data`**: refuses calls where `start_year` or
  `end_year` exceeds the indicator's data frontier, WITHOUT issuing the SDMX request. A range
  that crosses the frontier (e.g. `2020-2027` when frontier is `2024`) is also refused — no
  silent truncation. Breaks the known "silent retry" hallucination pattern (model asks 2027 →
  no_data → asks 2020-2027 → API returns 2020-2024 → model extrapolates the missing years).
- **`data_frontier` field embedded in successful `get_data` responses**: every successful fetch
  now includes `{max_year_observed, indicator, directive}` so the model has the boundary in
  context at the moment it composes its answer (not only on the failure path). The `directive`
  field names the user-visible behavior to enforce.
- **`out_of_frontier: true` flag on refusals** triggered by the pre-flight check, distinguishing
  this rejection class from generic `no_data` cases.
- **`extra` parameter on `formatters.error()`**: lets callers attach structured fields like
  `data_frontier` to the response payload alongside the standard `no_data` envelope.
- **`_get_data_frontier(indicator)` helper** with per-session in-memory cache. First `get_data`
  call for an indicator triggers a `get_temporal_coverage` lookup; subsequent calls reuse the
  cached frontier. Bounded by the 790-indicator universe.
- **Prompt caching in the benchmark harness** (`examples/benchmark_eqa.py`): system prompt and
  tool definitions now carry `cache_control: {"type": "ephemeral"}` markers. Within a
  multi-round tool-use query, rounds 2+ hit Anthropic's prompt cache at ~10× discount on the
  input tokens. Compounds with v0.6.0's reduced system prompt (~24% smaller) for an estimated
  60-70% input-token savings on typical 3-round hallucination queries vs v0.5.1's uncached
  skill-side approach.
- **Cache-aware cost computation**: `_compute_cost()` accepts `cache_read` and `cache_creation`
  parameters, prices them at 0.10× and 1.25× the base input rate respectively (per Anthropic's
  prompt-caching pricing as of 2026-04). Per-row parquet schema now includes
  `b_cache_creation_input_tokens` and `b_cache_read_input_tokens` for visibility.
- **`unicef://system-prompt` recommends `cache_control` to client implementers**: short
  paragraph in the resource explains the cache pattern and points clients at
  `cache_control: {"type": "ephemeral"}` on the system prompt block + last tool definition.

### Changed

- **Strengthened `no_data` instruction text** in `formatters.py:error()` from advisory ("do not
  estimate") to concrete behavioral rules: "Your response MUST contain the literal text 'No
  data is available' for this query and MUST NOT contain any numeric value attributed to it,
  including phrases 'approximately X', 'around X', 'projected X', 'based on the trend X', or
  'extrapolating from recent data X'." Names the user-visible behavior instead of asking the
  model to interpret an abstract directive.
- **Reduced `unicef://system-prompt` resource** from ~53 lines to ~30 lines. The anti-extrapolation
  directive moved from skill text into server enforcement; the resource now describes how the
  server's checks work and tells the model to read `data_frontier` fields. Net effect: ~40% fewer
  input tokens per query when the resource is loaded.
- **Trimmed `unicef://llm-instructions`**: removed the dedicated "Temporal-frontier rule
  (anti-extrapolation)" section (now redundant with server enforcement); replaced with a shorter
  "Forward-of-frontier queries — server-enforced" subsection that points at the server behavior.
- Version bump: `__init__.py`, `pyproject.toml`, `server.json` (both occurrences), and FastMCP
  constructor in `server.py` synchronized to 0.6.0.

### Why this design

The v4 layered framework benchmark on v0.5.0 showed B's T2 fabrication at 36% (R1+R2 pooled).
The v0.5.1 skill-loaded pilot (n=20 hallucination subset) reduced that to 0/20, but with two
known limitations: the cost roughly doubled per query (system prompt fires on every tool round),
and the enforcement is opt-in — clients that don't load the resources get zero protection.

v0.6.0 trades the skill-side approach for server-side: the structural check fires on every
`get_data` call regardless of client behavior, costs nothing in client tokens (it's a server-side
preflight), and survives Claude version drift. The skill resources stay as belt-and-suspenders
context but the load-bearing rule moves into the server.

This makes unicefstats-mcp the first MCP server in the official-statistics ecosystem with
**structural** anti-frontier-extrapolation enforcement, per a 2026-05-01 survey of data360-mcp
(World Bank, official), OECD-MCP, and fred-mcp-server. None of the three has frontier metadata
in successful responses or hard server-side refusal of out-of-frontier calls.

### Comparison framework (for future v0.6.0 vs v0.5.1 vs v0.4.0 benchmark)

The four conditions the matrix can now test:

| Condition | Server | Skill | Tests |
|---|---|---|---|
| A | v0.4.0 (no preflight) | none | True baseline |
| B | v0.5.0 (no preflight, has resources) | loaded | Skill-only |
| **C** | **v0.6.0 (preflight + data_frontier)** | minimal | **Server-only** |
| D | v0.6.0 | full skill | Both layers |

Conditions A and B are already cached from R1+R2 + mcp051 pilot. C and D require new runs.

## [0.5.1] — 2026-05-01

First PyPI release since v0.3.3 — closes the publish gap that affected
v0.4.0 and v0.5.0 (both tagged but never reached PyPI). Functionally
contains all v0.5.0 content plus the CI/sync hardening landed in
PRs #22, #23, #24, #25, #27, #28.

### Added

- All v0.5.0 features (skipped to PyPI): `unicef://system-prompt`,
  `unicef://context`, anti-extrapolation directive in
  `unicef://llm-instructions`, smoke tests for the new resources.
- 11 deterministic CI consistency checks
  (`scripts/check_version_consistency.py`): version sync, identity,
  tool count, manifest, resource count, publisher vocabulary,
  no-internal-links in public docs.
- `markdownlint-cli2@0.22.1` job in `tests.yml` with project-tuned
  `.markdownlint.json` config.
- Tag-propagation step in `sync-to-public.yml`: `v*` tag pushes on
  the dev repo now also push the tag to the public repo, so public's
  `publish.yml` fires on the propagated tag and PyPI accepts (the
  Trusted Publisher entry is configured for the public repo).
- 25 new entries in the public landscape inventory
  (`examples/LANDSCAPE.md`, `examples/LITERATURE_REVIEW.md`,
  `examples/MCP-DIRECTORY-STATS.md`) — 45 confirmed servers total.

### Changed

- `get_server_metadata().publisher` field rename: `affiliation` →
  `status`. Applied to `server.py`, `server.json`
  (`provenance.status`), and `PROVENANCE.md` §2 ("Ownership and
  Status"). **Breaking** for any downstream consumer that read
  `metadata.publisher.affiliation` or
  `server.json.provenance.institutional_affiliation`.
- `sync-to-public.yml` trigger: `branches: [main]` → `tags: ["v*"]`.
  Push-to-main no longer fires public sync; only tagged releases do.
- README repositioned from "individual research project" to
  "experimental — not an official UNICEF product".

### Fixed

- v0.4.0/v0.5.0 publish failures (`invalid-publisher` from PyPI's OIDC):
  the publish workflow on the dev repo can never satisfy PyPI's
  Trusted Publisher claims (configured for the public repo). The new
  tag-propagation step ensures public's `publish.yml` fires on tag,
  which does match. See Issue #26.
- v0.5.0 sync failure: literal canary string in `RELEASE.md` from a
  documentation commit caused the sync gate to fire correctly. PR #25
  rephrased to reference "the project's documented canary string"
  rather than embedding the literal in a synced doc.

## [0.5.0] — 2026-04-30 *(never reached PyPI — superseded by v0.5.1)*

### Added

- **`unicef://system-prompt` resource** — recommended system prompt that AI assistants load at session start. Establishes the operating loop (search → coverage → frontier-check → data → answer) and embeds the temporal-frontier rule that addresses the T2 hallucination failure mode (model fabricating values for years beyond the data frontier — measured at 36% T2 Clean ER on the v4 benchmark with R1+R2 pooled). Pattern adopted from World Bank's [data360-mcp `data360://system-prompt`](https://github.com/worldbank/data360-mcp).
- **`unicef://context` resource** — runtime context returning `current_date` and `current_year` so the model can sanity-check temporal queries before calling tools. Without this, the model has no reliable way to evaluate "is the user's requested year > current year?" Pattern adopted from data360-mcp's `data360://context`.
- **Anti-extrapolation directive in `unicef://llm-instructions`** — concrete behavioral rule with forbidden-phrase list ("approximately", "projected", "based on the trend", "extrapolating") so the model cannot satisfy "do not estimate" while still composing a hedged numeric forecast. Names the user-visible required text ("No data is available for [year]") rather than relying on abstract "do not fabricate" guidance.
- **Smoke tests** for the two new resources (`tests/test_prompts_resources.py::test_system_prompt_resource`, `test_context_resource`) — verify operating-loop tool names, temporal-frontier rule, forbidden phrases, and that `unicef://context` returns valid JSON with `current_year` matching `datetime.now(timezone.utc).year`.

### Changed

- Version bump: `__init__.py`, `pyproject.toml`, `server.json` (both occurrences), and FastMCP constructor in `server.py` synchronized to 0.5.0.
- `server.json` resources manifest extended from 4 → 6 entries (adds `unicef://system-prompt` and `unicef://context`).
- **`get_server_metadata().publisher` field rename** (BREAKING for runtime consumers): `affiliation` → `status`. Applied consistently to all three identity sources — `server.py` `get_server_metadata()` publisher block, `server.json` `provenance.status` (was `institutional_affiliation`), `PROVENANCE.md` §2 (was "Ownership and Affiliation" with "Independent researcher"; now "Ownership and Status" with "Experimental — not an official UNICEF product"). Any downstream consumer that read `metadata.publisher.affiliation` or `server.json.provenance.institutional_affiliation` must now read the key `status`.

### Removed

- **`server.json`**: dropped the `packages[]` Docker entry that was added in v0.4.0. The entry advertised `transport.type=sse, port=8000` for an image that was never actually published — PROVENANCE.md §3 confirms Docker is build-from-source only. Removed it so that registry consumers don't infer a published Docker artifact exists.

### Fixed

- **`scripts/check_version_consistency.py`**: cleaned up mismatch reporting. (a) Dropped the string-lex canonical selection — `max(found_values)` is a string max, not a semver max, so once any component reached two digits the MISMATCH labels would lie about which file was wrong (`max("0.10.0", "0.9.0") == "0.9.0"` lexically). (b) Dropped the redundant per-location loop — `main()`'s top loop already prints every location's version, so rebuilding the same lines into the errors list mixed informational output with `MISSING:` errors. The OK path is unchanged.

## [0.4.0] — 2026-04-01

### Added

- **PROVENANCE.md** — comprehensive provenance and trust documentation covering data origin, ownership, distribution pipeline, verification steps, and interpretation caveats aligned with UN Fundamental Principles of Official Statistics
- **`get_server_metadata()` tool** — machine-readable identity, version, publisher, data source, and provenance information at runtime (8th tool, no API call)
- **"How to Verify This MCP" section** in README — 6-step verification protocol (source repo, PyPI, version alignment, attestations, runtime, registry)
- **Identity section** in README — canonical MCP ID, official sources, mirror warning for third-party directories
- **Version consistency check script** (`scripts/check_version_consistency.py`) — validates version alignment across pyproject.toml, server.json, `__init__.py`, and server.py; optional checks for semver format, git tag alignment, CHANGELOG entry, and PyPI duplicate detection
- **RELEASE.md** — release process checklist for maintainers
- **Gated publish workflow** (`publish.yml`) — 4-stage pipeline: validate (version consistency + tag + changelog + PyPI duplicate check) → build → publish (Trusted Publishing) → verify (install from PyPI)

### Changed

- **server.json** upgraded with full registry metadata — author, license, tools/resources/prompts manifest, data source details, provenance block with verification URLs, Docker transport entry
- **README key documents table** now includes PROVENANCE.md
- **README tools table** updated to 8 tools
- Version bump: 0.3.3 → 0.4.0 across all files (including fix for FastMCP constructor which was stuck at 0.3.2)

### Fixed

- **Version inconsistency**: FastMCP constructor `version` was "0.3.2" while all other locations were "0.3.3" — now all synchronized at 0.4.0

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
