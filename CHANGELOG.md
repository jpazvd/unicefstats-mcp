# Changelog

All notable changes to unicefstats-mcp are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/).

**Package:** [pypi.org/project/unicefstats-mcp](https://pypi.org/project/unicefstats-mcp/) · **Source:** [github.com/jpazvd/unicefstats-mcp](https://github.com/jpazvd/unicefstats-mcp)

## [Unreleased]

## [1.2.2] — 2026-06-01

### Added

- **Tool annotations on all 9 `@mcp.tool` functions**: `readOnlyHint` (true), `destructiveHint` (false), `idempotentHint` (true), `openWorldHint` (true for SDMX-calling tools, false for local-metadata tools), plus human-readable `title`. Closes the gap identified by the MCP best-practices rubric (see [modelcontextprotocol.io](https://modelcontextprotocol.io/specification/)) — clients now have machine-readable hints for parallelization, approval flow, and tool discoverability.
  - `openWorldHint=true` (touch the live SDMX API): `get_data`, `get_temporal_coverage`.
  - `openWorldHint=false` (local YAML / cached metadata only): `search_indicators`, `list_categories`, `list_countries`, `get_indicator_info`, `lookup_by_code`, `get_api_reference`, `get_server_metadata`.
- **Inline Pydantic `Field()` constraints on every tool parameter** via `typing.Annotated`. Adds `description`, `min_length` / `max_length` for strings, `ge` / `le` for ints, `Literal[...]` enums where applicable. FastMCP picks up these constraints and validates inputs before dispatch — closes the Python MCP Quality Checklist's "All Pydantic Fields have explicit types and descriptions with constraints" line item without changing any tool signature (zero test-side churn). Constraints are mirror-aligned with the runtime limits enforced by `validators.py` (`MIN_QUERY_LEN=2`, `MAX_QUERY_LEN=200`, `MAX_COUNTRIES=30`, `MAX_LIMIT=500`, indicator `max_length=50`) so the advertised schema never promises inputs the tool will reject.
  - Examples: `search_indicators(query=Annotated[str, Field(min_length=1, max_length=200)], limit=Annotated[int, Field(ge=1, le=100)] = 20)`; `get_data` covers all 11 params including the v1.1.x deprecated `wealth_quintile` / `residence` (marked `deprecated=True` in the Field metadata so clients render the migration warning).

### Notes

- Zero source-logic, zero test changes — pure schema decoration. 458 tests pass.
- Direct Python callers can keep using `search_indicators(query="...", limit=10)` exactly as before — the `Annotated` style preserves the signature; only the JSON schema FastMCP exposes to MCP clients gains the new constraints.
- v1.2.3 (queued): pagination metadata (`has_more` / `next_offset` / `total_count`) + `offset` param on `list_*` tools.
- v1.2.4 (queued): `evaluation/unicefstats_mcp_eval.xml` per the MCP evaluation rubric (10 read-only, independent, stable QA pairs verifiable by direct string comparison).

## [1.2.1] — 2026-06-01

### Fixed

- **LLM-instructions resource did not document any v1.2.0 envelope field.** The MCP server shipped a rich response envelope in v1.2.0 (`mode`, `units`, `dimensions_available`, `tier_reason`, `failed_validation`, `filter_requested_no_data`, `alert`, `dataflow_used`, `truncated`) but neither the `unicef://llm-instructions` resource nor the `unicef://system-prompt` resource told the LLM these fields existed. Without documentation, the LLM could not exploit the v1.2.0 work at the consumer surface — the server-side fixes were doing nothing for end-users until the prompt-layer caught up.
- `LLM_INSTRUCTIONS` now includes a `## v1.2.0 envelope fields — dimension-aware responses (READ THESE)` section with one paragraph per field naming the concrete behavior change required of the LLM. Notably: `units.interpretation` must be applied BEFORE reporting any number (the v1.1.x `DM_POP_U5` misinterpretation failure mode); `mode == "totals_fallback"` requires explicitly telling the user that the filtered slice was empty and totals were substituted; `tier: 2` requires a pivot to `search_indicators` for the leaf code.
- `SYSTEM_PROMPT` gets a tighter mirror section covering the same fields with one-line rules.

### Notes

- No source-logic or test changes. Pure prompt-layer release.
- The two resources are also accessible to clients via `unicef://llm-instructions` and `unicef://system-prompt` URIs.

## [1.2.0] — 2026-05-30

### Breaking

- **`get_data` signature**: the typed `wealth_quintile=` and `residence=` kwargs no longer route to the SDMX call. They remain in the signature only as deprecation trip-wires; passing a non-`None` value returns a structured migration error pointing at the new `filters={"WEALTH_QUINTILE": "Q1", "RESIDENCE": "U"}` shape (mirrors `data360-mcp`'s `disaggregation_filters` pattern). The v1.1.x silent-drop hazard — validated kwargs that were never forwarded — is closed permanently.
- **Numeric change for v1.1.x callers**: a call like `get_data(indicator='NT_BF_EXBF', countries=['BDI'], filters={'WEALTH_QUINTILE': 'Q1'})` now returns the Q1-filtered slice via `mode='raw_filtered'`. v1.1.x silently returned the totals slice for the same intent. Same call → different number. The `mode` envelope field gives strict consumers a trip-wire.
- **`get_indicator_info` + `lookup_by_code` envelope**: `disaggregation_filters` is now grounded in the unicefdata-shipped YAML for the indicator's primary dataflow, not the v1.1.x hardcoded `{sex, wealth_quintile, residence}` triple. Per-indicator results are honest:
  - `HVA_EPI_INF_RT` returns `{AGE, SEX, WEALTH_QUINTILE, RESIDENCE, DATA_SOURCE}` (the actual HIV_AIDS dataflow dims).
  - `CME_MRY0T4` does NOT advertise AGE (U5MR is age-restricted by construction — pins the v1.1.1 forensic finding).
  - Tier-2 family codes return `{"_source": "fallback_unknown", "dimensions": null}` instead of a fabricated triple.
- **Curated catalog phantom-code fix**: `CME_U5MR` / `CME_IMR` / `CME_NMR` in `curated.py` pointed at codes that don't exist in the unicefdata registry. Real canonical codes are `CME_MRY0T4` / `CME_MRY0` / `CME_MRM0`. v1.1.x callers who hit the curated path for these queries got back a phantom code that 404s on `get_data`. Fixed; alt_synonyms route to the real codes. The 5-char min-length guard in `lookup_preferred` is preserved (v1.1.1 collision protection intact).
- **Dependency floor unchanged**: still `unicefdata>=2.4,<3`. v1.2.0 routes AGE through `raw=True` + post-filter, so it does not require `unicefdata>=2.5.0`'s first-class `age=` kwarg. When 2.5.0 publishes, AGE moves into `FIRST_CLASS_UD_DIMS` in `dimensions.py`.

### Added

- **`get_data(age=, filters=...)`**: new typed `age` kwarg (routed through `raw=True` + post-filter) and free-form `filters: dict[str, str | None]` for every dim that isn't first-class via `unicefData()`. Auto-engages `mode='raw_filtered'` when any non-`_T` filter is present. Validates `(dim, value)` against the indicator's actual dataflow before the SDMX call; refuses unsupported pairs with a structured `failed_validation` envelope listing `available_dimensions` and `available_values`.
- **New `src/unicefstats_mcp/dimensions.py`** module reading the unicefdata-shipped YAML (reuses `unicefdata.unicefdata.INDICATORS_METADATA` for ~9 ms import — was 687 ms when re-parsing). Surfaces `primary_dataflow(code)` (coerces string-vs-list — fixes the 122-indicator silent-corruption hazard), `dimensions_for_indicator(code)` (graceful tier-2), `dimension_supported(code, dim, value)` (pre-flight validator), `build_disaggregation_filters(code)`, `filter_by_dimensions(df, filters)`, and the inverted index `indicators_supporting(dim, value)`. Module-level startup self-test fails fast on YAML schema drift.
- **New envelope fields**:
  - `get_data`: `mode` (`first_class` | `raw_filtered` | `totals_fallback`), `dataflow_used`, `applied_filters`, `truncated`, `failed_validation`, `tier`, `tier_reason`, **`dimensions_available`** (Commit 6 — v1.3.0 candidate pulled forward; surfaces the full dim menu on every successful response so the LLM can pick a valid disaggregation without a `get_indicator_info` round-trip), **`alert`** (Commit 6 — totals_fallback only; UX message naming the substitution), **`filter_requested_no_data`** (Commit 6 — totals_fallback only; preserves the original request so the LLM can retry with a valid slice), **`units`** (PR #84 — `measure` / `measure_name` / `multiplier` / `multiplier_name` / `interpretation`; closes the model-level unit-interpretation drift surfaced by the v9 A/B replay on `DM_POP_U5`).
  - `get_indicator_info` + `lookup_by_code`: `dataflow_used`, `variants` (same-family sibling codes, capped at 10), `tier`, `dimension_source` (`yaml_grounded` | `no_dataflow_metadata`).
- **Tier-2 refusal**: `get_data` refuses for the 258 tier-2 family codes with `tier_reason: 'no_dataflow_metadata'` and points to `search_indicators` for an alternative.
- **Multi-dataflow routing**: forces `dataflow=primary_dataflow(code)` on the SDMX call. HVA queries hit `HIV_AIDS` instead of the v1.1.x `GLOBAL_DATAFLOW` fallback. Envelope's `dataflow_used` surfaces which dataflow served the response.
- **`get_indicator_info` ≡ `lookup_by_code`**: both tools route through a shared `_build_indicator_envelope(code, info)` helper, so the `disaggregation_filters` block is literally identical across both. Closes the v1.1.x copy-paste hazard at the source.
- **Multi-word synonym + acronym coverage** (`_SYNONYMS` in `server.py`): `IMR` / `NMR` / `under 5 mortality` / `under-five mortality` / etc. now all resolve to their real canonical codes in `search_indicators.recommended`.
- **Methodology-phrase boost**: new `METHOD_MOD` entry in `_DIM_TOKEN_MAP` + `_DIM_QUERY_PHRASES`. Queries containing `"modelled estimates"` / `"modeled estimates"` (UK + US spellings, singular + plural) surface `_MOD`-suffixed codes in the top results.
- **Synonym-resolver fallback in `search_indicators`** decision logic: when the curated catalog returns `None` (e.g. the 5-char guard rejects bare 4-char acronyms like `U5MR`) and `resolve_indicator` gives a confident `synonym_match` / `code_passthrough`, surface that code as `recommended`. Load-bearing for `U5MR` queries where the scoring gap is below the v1.1.1 confident-match threshold.

### Fixed

- **Silent-drop**: v1.1.x validated `wealth_quintile` / `residence` kwargs then dropped them at the SDMX call. v1.2.0's migration error makes the drop loud (see Breaking above).
- **String-vs-list `dataflows`**: 122 tier-1 indicators in unicefdata 2.4.x store `dataflows` as a bare string (`"HIV_AIDS"`) instead of a list. `dataflows[0]` returned the first character (`'H'`). `primary_dataflow()` in the new `dimensions.py` module coerces both shapes. (Fix tracked upstream as `jpazvd/unicefData-dev#94`.)
- **`get_dataflow_for_indicator` mis-routing**: upstream's helper returns `GLOBAL_DATAFLOW` for indicators whose actual primary is something else (e.g. `HVA_EPI_INF_RT` → `HIV_AIDS`). v1.2.0 uses `dimensions.primary_dataflow` everywhere it routes a dataflow. (Tracked upstream as `jpazvd/unicefData-dev#95`.)
- **Phantom curated codes** (`CME_U5MR` / `CME_IMR` / `CME_NMR`) — see Breaking section above.
- **`get_indicator_info` and `lookup_by_code` envelope drift** — both functions previously held independent copies of the hardcoded triple and could drift. Both now route through `_build_indicator_envelope`.

#### Commit 6–9 (post-merge sanity-check fixes folded into the same PR)

- **Bug A — country filter silently dropped on `ud.unicefData(raw=True)`**: upstream's `raw=True` path doesn't honor the `countries=[...]` kwarg; it returns ALL countries in the dataflow (173 for `HIV_AIDS`). The MCP now post-filters by `REF_AREA` after the raw fetch. (Commit 6 / `04bdef7`.)
- **Bug B — `to_compact` / `to_full` zeroed records on raw=True**: the raw path returns SDMX-grade uppercase columns (`REF_AREA`, `INDICATOR`, `TIME_PERIOD`, `OBS_VALUE`); the v1.1.x formatters knew only `iso3` / `country_code` / `period` / `indicator_code` / `value` and silently produced 0 records. Now: `COLUMN_ALIASES` extended + canonical rename. (Commit 6 / `04bdef7`.)
- **Auto-totals fallback** (user-directed UX): when the post-filter yields 0 rows in `raw_filtered` mode, the MCP auto-substitutes the indicator's totals slice (re-fetch without filter) and returns it with `mode='totals_fallback'`, `alert` field naming the substitution, `filter_requested_no_data` preserving the original request, and `dimensions_available` for the LLM to pick a valid slice on the next wave. Saves +1 LLM wave per affected query at +1 SDMX call (~$0). (Commit 6 / `04bdef7`.)
- **Bug C — downstream summary helpers silently no-op on raw=True column shape**: `summarize_data`, `summarize_disaggregations`, `compute_trend`, `_seed_data_frontier_cache`, the sparse-year warning, and the `data_frontier` observation all looked for lowercase canonical column names and silently produced empty summaries on raw=True data. Fix: new `formatters.normalize_columns(df)` applied once after the raw_filtered pipeline; all helpers now work transparently for both fetch paths. (Commit 7 / `29dc7ea`.)
- **Bug D — `OBS_VALUE` is a STRING in raw=True; `summarize_data.mean()` crashed**: the SDMX raw payload's `OBS_VALUE` carries both clean strings (`"0.35"`) and censored cells (`"<0.01"`). `summarize_data` and `compute_trend` now safe-coerce via `pd.to_numeric(errors='coerce')` so censored cells drop to NaN cleanly. (Commit 7 / `29dc7ea`.)
- **Bug E — `countries_returned_with_names` empty on raw=True**: raw payload has no country-name column. New `country_resolver.lookup_country_name(iso3)` helper fills the v0.6.1 mitigation field from the cached country index. (Commit 7 / `29dc7ea`.)
- **Bug F — `sex` silently bypassed on `raw_filtered` (silent broadening)**: upstream's `raw=True` ignores the `sex=` kwarg; without an MCP-side post-filter the response included EVERY SEX value (F, M, _T) instead of the requested slice (default `_T`). Fix has two parts: (1) `dimensions.filter_by_dimensions` no longer treats `'_T'` as a no-op (it's a real SDMX totals code; the raw payload contains both `'_T'` rows AND `F`/`M` rows); (2) `server.get_data` folds the typed `sex` value into `effective_filters` when raw_filtered mode engages, UNLESS SEX is already present in the user's `filters` dict (the more-explicit channel wins — closes a derived silent-overwrite of explicit user filters by the typed default). (Commits 8 + 9 / `566fe76`, `c491381`.)

#### Post-merge fixes (PRs #83 + #84 — folded into v1.2.0 before tag)

- **Tier-2 refusal fires unconditionally** (PR [#83](https://github.com/jpazvd/unicefstats-mcp-dev/pull/83), `d3063e6`). The Commit-2 tier-2 refusal only fired when `effective_filters` was non-empty; unfiltered tier-2 calls (e.g. `get_data('CME', countries=['BDI'])`) fell through to a generic SDMX 404 instead of the structured `tier: 2` envelope. The refusal now fires regardless of filter presence. Also distinguishes KNOWN tier-2 codes (have metadata, `tier=2`, `tier_reason='metadata_only_no_data'`) from UNKNOWN codes (no metadata — typos): UNKNOWN codes called with `filters={...}` return `metadata_status='unknown_code'` with no `tier` field; UNKNOWN codes called unfiltered fall through to the v1.1.x SDMX 404 handler (intentional — preserves the existing typo-routing path). Pre-fix the same "no associated dataflow metadata" error mislabeled mistyped codes as tier-2, which misled the LLM's pivot path. Surfaced by the live SDMX smoke run after PR #82 merged.
- **`units` envelope field** on every successful `get_data` response (PR [#84](https://github.com/jpazvd/unicefstats-mcp-dev/pull/84), `536ce29`, closes [#77](https://github.com/jpazvd/unicefstats-mcp-dev/issues/77)). The v1.1.x simplified path used by `first_class` mode strips `UNIT_MEASURE` and `UNIT_MULTIPLIER` from the SDMX payload, so model-level unit-interpretation drift was invisible to the wave-count / cost / ambiguity gates but visible in final-text rendering — the v9 A/B replay caught Haiku 4.5 reading `DM_POP_U5 = 0.188` as "188 children" on v1.0.0 and "~188,000 people" on v1.1.0; the right answer is `188 Persons` via `0.188 × 10^3 Persons`. New `units: {measure, measure_name, multiplier, multiplier_name, interpretation}` block surfaces the SDMX convention `value × 10^UNIT_MULTIPLIER UNIT_MEASURE` explicitly. Two source paths: `raw_filtered` / `totals_fallback` modes extract units from the raw df directly (zero extra SDMX round-trips); `first_class` mode uses a new cached `dimensions.unit_info_for(indicator, dataflow)` resolver (one `raw=True` call per indicator per process lifetime). Unit-measure codes (`PS`, `RATE_1000`, `PCNT`, `USD`, …) resolved via the shipped `CL_UNIT_MEASURE` codelist (`_unicefdata_codelists.yaml`, 80+ entries); unit-multiplier names via a hardcoded `-3..9` lookup covering thousandths through billions.

### Notes (v1.3.0 candidates)

v1.3.0 (separate PR after empirical LLM-consultation-rate study):

- **Dim menu in `get_data` envelope**: `dimensions_in_response` + `dimensions_available` carried on every successful `get_data` response so the LLM doesn't have to call `get_indicator_info` separately.
- **`recommended_filter`** field on `search_indicators` responses, gated by `dimension_supported`, lets the LLM go from query to filtered `get_data` in one tool round-trip.
- **`dimension_mismatch`** envelope with same-family `siblings_supporting` when the top result doesn't expose a dim the query asked for.
- **`_DIM_LABEL_TO_SDMX`** mapping (natural-language → SDMX dim id) — `"residential area"` → `"RESIDENCE"`, etc.
- **`_strip_trivial_dim_values`** — drop `_T` / `_Z` columns from compact-format rows to save LLM tokens.
- **`lookup_dimension_value`** helper to translate codes like `Y15T19` → `"15-19 years"` inline.

### Verification

Per-commit gates + a final integration gate (see the v1.2.0 plan in the matching PR description; PR #82 ran 11 commits over its lifecycle — the 5 originally-planned + 4 post-merge Bug A–F fixes + Copilot review-pin; PRs #83 and #84 added two more focused commits each). 458 tests pass after the PR #82 + #83 + #84 cycle (was 429 at the PR #82 cutpoint; +1 from PR #83 tier-2 distinction, +3 from PR #84 units envelope, +25 from PR #82 Copilot review-pin file). Ruff + mypy clean. Wave-count benchmark target: ≤2.0 mean tool-call count on the v9 30-edge stratum (stretch 1.8); paired typical-stratum result vs v1.1.2 = 0.00 Δwaves (no regression on non-stuck queries — issue #76).

### Related upstream work

Plan PR [`jpazvd/unicefData-dev#92`](https://github.com/jpazvd/unicefData-dev/pull/92) bundles 11 wrapper-side enhancement proposals + 1 dual-cache finding into 5 sprints (v2.6.0 → v3.0.0). Issues `#93–#104` track individual items. The wrapper-side workarounds documented in this CHANGELOG (e.g. `dimensions.primary_dataflow` for the string-vs-list coercion) shrink to ~10 LoC apiece once those land upstream.

## [1.1.2] — 2026-05-30

### Added

- **README "Understanding UNICEF indicator codes" section** — comprehensive semantic-clarity surface exposing the segment-level grammar of UNICEF SDMX codes. SDMX codes are cryptic by design; the MCP's value-add is making the structure legible so the assistant can disambiguate without guessing.
  - Why-it-matters opener framing semantic structure as the MCP's primary differentiator.
  - "Anatomy of a UNICEF code" walkthrough with three real examples decomposed segment-by-segment:
    - `PT_F_20-24_MRD_U18` — population restriction + age band + indicator class + marriage cutoff.
    - `NT_ANT_HAZ_NE2` — family + sub-family + metric + threshold.
    - `TRGT_2030_IM_DTP3` — derived metric + target year + family + dose.
  - Topic prefixes table covering 15+ families (CME, NT, ED, WS, IM, MNCH, ECD, PT, HVA, PV, COD, DM, MG, GN, TRGT, HAZARD).
  - Methodology and provenance suffixes table (`_MOD`, `_MERGE`, `_PRXY`, `_NEW`, `_NUMTH`, `_AGG`, `_UIS`).
  - "Population restrictions vs sex disaggregation" — clarifies that the `F` in `PT_F_*` is built into the code (female-only indicator), while sex-stratified values of a sex-neutral indicator are accessed via the `SEX` dimension filter (`get_data(..., sex='F')`).
  - Age band token grammar (`M0`, `Y0`, `Y0T4`, `Y1T4`, `Y5T14`, `Y10T19`, ...) with `M`/`Y`/`T` decoding (M=months, Y=years, T=to).
  - Wealth quintiles (`Q1`–`Q5`) and residence (`U`/`R`/`_T`) tokens.
  - Education levels — `L1`/`L2`/`L3` = ISCED 1/2/3 **in the `ED_*` family only**; outside `ED_*`, `L<n>` may encode severity (`PV_CHLD_MPI_L1`) or pre-primary (`L01`/`L02`).
  - Derived metrics (`TRGT_` / `_ARR_` / `_PRJ`) tied to v1.1.1 query-aware scoring.
  - Pointer to where the grammar lives in the codebase (`differentiator.py`, `indicator_resolver._SYNONYMS`, `CURATED_PREFERRED.dimension_hint`).
- **Catalog survey script** at `internal/v1.1.0_design/v112_catalog_survey.py` — programmatic inventory of the 738-indicator catalog supporting the README claims with reproducible pattern counts.

### Changed

- **Inline semantic anchors in `server.py`** (commit d0082b7):
  - `_DERIVED_METRIC_CODE_PATTERNS` — each prefix now carries its expansion inline (`TRGT` = target, `_ARR` = Annual Rate of Reduction, `_PRJ` = projected).
  - `_DERIVED_METRIC_NAME_PATTERNS` — lead-in comment notes these are the NAME-level mirror of the code-level patterns.
  - `_is_derived_metric` docstring — pointer to the README grammar section.
  - `_TARGET_QUERY_TOKENS` and `_query_seeks_target` — natural-language tokens explicitly tied to the `TRGT_` code prefix.
- **`curated.py` `IM_DTP3` `dimension_hint`** — now leads with the `TRGT` = target expansion so the semantic anchor reaches downstream consumers.

### Notes

- **Backward compatibility:** zero behaviour change. Pure documentation and inline comments.
- **Adversarial review caught a fabricated example:** the first README draft included a hallucinated code (`NT_ANT_HAZ_NE2_F`); the v1.1.1 adversarial-review workflow's fix-agent flagged and corrected it against the catalog before merge.

## [1.1.1] — 2026-05-30

> **Scoring + catalog refinement** on top of v1.1.0, driven by the v9
> edge-test forensic study (`internal/v1.1.0_design/ambiguity_forensic.md`).
> Closes the IM_DTP3 TYPE-C pathology (v9 query "DTP3 vaccine coverage
> national programme" was returning 5 TRGT_2030_IM_* codes instead of
> the canonical IM_DTP3), removes two v1.1.0 catalog-injection bugs in
> the HVA_EPI family, tightens lookup_preferred against short-substring
> collisions, and reorders the decision logic so curated picks
> authoritatively override heuristic ambiguity.

### Added

- **TRGT penalty** (`-35` relevance) on `TRGT_*` codes when the query
  does NOT contain target-intent tokens (`target`, `targets`, `goal`,
  `goals`, `objective`, `objectives`, `aspiration`, `aspirations`,
  `milestone`, `milestones`). Token matching uses set-intersection on
  the pre-tokenised query, NEVER substring — so "targeting children" /
  "on-target" / "no target group" do NOT unmask `TRGT_*` codes.
  Penalty is skipped when `_is_derived_metric` already ate the code
  (no double-counting).
- **Dimension-token boost** (`+15` relevance) for indicators whose
  CODE carries the SDMX dimension suffix matching query tokens:
  - sex: `female` / `girls` / `women` / `woman` / `girl` → `_F_`
  - sex: `male` / `boys` / `men` / `man` / `boy` → `_M_`
  - wealth: `poorest` / `q1` → `_Q1_`; `richest` / `q5` → `_Q5_`
  - wealth phrases: `lowest quintile` / `highest quintile`
  - residence: `urban` / `city` / `town` → `_U_`; `rural` / `village`
    → `_R_`
  Gated on the CODE suffix only — name-side matching was dropped per
  adversarial review (PT_F_20-24_MRD_U18 says "women" but is not a
  literacy indicator; query "women's literacy" must not boost it).
- **`CURATED_PREFERRED` entries** for `IM_DTP3` and `IM_DTP1` with
  target-vs-actual differentiator wording in `dimension_hint` so
  the assistant knows when to use the canonical code vs the
  `TRGT_2030_IM_*` target variant.
- **Consolidated `HVA_EPI_INF_RT` curated entry** with the
  age-band-limitation `dimension_hint` (replaces the two v1.1.0
  entries that pointed at non-existent codes — see Fixed below).
- **README section `Scope: UNICEF DW indicators only`** documenting
  the catalog boundary that the v9 edge-test forensic surfaced
  (World Bank `SI.*`/`NY.*`/`SE.*`, ILO `EIP_*`/`EAP_*`, ASPIRE
  `per_*`, UIS `UIS.*`, WHO `WHO_*` are out of scope). Links to
  sister tools (data360-mcp, worldbank-mcp) for cross-source work.
- **`tests/test_v111_scoring.py`** — 8 new pytest cases pinning the
  TRGT penalty, dimension boost, curated short-circuit, 5-char floor
  on `lookup_preferred`, false-positive guard, HVA consolidation, and
  backward compat against the LIVE unicefdata registry (no mocking).

### Changed

- **Decision-logic reorder in `server.search_indicators`** (was 1-2-3-4
  with ambiguity as Stage 1; now curated as Stage 1):
  - Stage 1 (NEW): `CURATED_PREFERRED` lookup on the raw query.
    If a curated entry matches, `requires_confirmation=False` with
    the curated canonical pick + category + `dimension_hint`. Wins
    over heuristic ambiguity because the catalog match is a
    deliberate human-curated signal, not a pattern guess on noisy
    similar-score results.
  - Stage 2: `ambiguity_flag` still set on the payload AND no
    curated hit → `requires_confirmation=True` (stop-and-ask).
  - Stage 3: confident in-results top match → result-side
    `recommended`.
  - Stage 4: otherwise → all four locals stay None
    (v1.0.0 wire-equivalent).
- **`lookup_preferred` substring rule tightened** — the v1.1.0
  bidirectional `q in syn.lower() or syn.lower() in q` rule fired
  `CME_IMR` on any query containing the 3-letter substring `imr`
  (e.g. "imrish"). The new `_substring_match` helper requires a
  5-char minimum on the syn-in-query direction. The query-in-syn
  direction (long query → short synonym) remains permissive.

### Fixed

- **Removed v1.1.0 catalog-injection bugs** in `HVA_EPI_INF_RT_0_14`
  and `HVA_EPI_INF_RT_15_19` — both pointed at codes that do NOT
  exist in the UNICEF SDMX catalog (verified via `_get_indicators()`).
  Consolidated into a single entry for the base `HVA_EPI_INF_RT`
  code (which exists with sex / wealth_quintile / residence
  dimensions but NO age band) whose `dimension_hint` explicitly
  names the age-band limitation and points at sibling codes
  (HVA_EPI_LHIV_0-19 / HVA_EPI_LHIV_15-24 / HVA_EPI_DTH_RT_0-14 /
  HVA_EPI_DTH_RT_10-19) that DO carry an age band.

### Backward compatibility

- Queries that contain neither target-intent tokens NOR dimension
  tokens produce byte-identical search responses to v1.1.0. The
  scoring layers only fire when their gating tokens are present.
- One v1.1.0 regression test
  (`test_v110_requires_confirmation.py::TestRequiresConfirmationTrue::
  test_curated_ambiguous_sets_flag_true`) was renamed and rewritten
  to assert the v1.1.1 contract: when a query triggers resolver
  `_AMBIGUOUS` AND matches a `CURATED_PREFERRED` entry, the curated
  pick wins (`requires_confirmation=False`, `recommended` set). The
  ambiguity_flag remains in the payload for downstream callers.
  This is the IM_DTP3 forensic motivation: the catalog must be
  authoritative when it matches.

### Notes

- Companion issue #78 filed against the benchmark repo flagging the
  3 v9 edge-sample custom_ids whose ground-truth codes are
  WB-dotted (`SI.POV.DDAY`, `NY.GDP.PCAP.PP.KD`,
  `per_allsp.cov_pop_tot`) and therefore out of UNICEF DW scope.
- Companion issue #79 will be filed for v1.2.0 "dimension-aware
  search" — when a query mentions an age band (or other
  disaggregation) and the indicator code lacks that disaggregation,
  check whether the indicator has the dimension as an SDMX attribute
  and surface either the filter recipe or the closest sibling code.
- Full suite: 375 passing (8 new v1.1.1 + 367 existing minus 1
  rewritten regression).

## [1.1.0] — 2026-05-29

> **Layered assistant-guidance surface on top of v1.0.0's ambiguity
> machinery.** Adds three patterns observed in peer official-stats MCPs
> (faostat-mcp / inegi-mcp / sdmx-mcp) — `requires_confirmation` as a
> machine-readable blocking signal (Pattern A), a 30-entry
> `CURATED_PREFERRED` catalog covering the four v9 gap families and the
> high-frequency Arm B cluster (Pattern B), and `assistant_guidance` +
> literal `next_step` strings (Pattern D). All changes are strictly
> additive — v1.0.0 callers see byte-identical responses when none of
> the new fields fire.
>
> Design provenance: `internal/v1.1.0_pattern_review.md` (comparison
> across 17 official-stats MCPs) + `internal/v1.1.0_design/` (parallel
> schema + curated-catalog design brief, locked decisions). A/B replay
> verdict: ALLOW (see ab_results.md).

### Added

- **`requires_confirmation` field on `search_indicators` responses**
  (bool | absent). `True` = assistant MUST stop and ask the user to
  disambiguate before calling `get_data`. `False` = safe to proceed
  with the `recommended` payload. Field is absent (not `null`) when no
  signal fires — preserves v1.0.0 wire format for callers that don't
  hit the new branches.
- **`recommended` dict** with `{code, category, why}` — populated
  only when `requires_confirmation=False`. `code` is the canonical
  pick; `category` carries the indicator's category label (e.g.
  `CME`, `NUTRITION`) — kept as `category`, not `dataflow_id`, so the
  field name does not over-claim (SDMX dataflow IDs are resolved
  separately by `get_indicator_info`); `why` records the relevance
  score + gap to runner-up so the assistant can show its work.
- **`assistant_guidance` field** — plain-English directive (<200 chars,
  no markdown, English-only). Names the exact next tool call when a
  recommendation fires, or the disambiguation imperative when ambiguity
  fires.
- **`next_step` field** — literal string naming the next tool
  invocation, e.g. `"get_indicator_info(code='CME_MRY0T4')"`. Single
  string, not a structured object — meant to be either copy-pasted or
  consumed by a simple regex.
- **`src/unicefstats_mcp/curated.py`** — 30-entry `CURATED_PREFERRED`
  catalog across 12 families. Gap families (ED_ANAR, NT_ANE, SPP_CHLD,
  PV_CHLD) come first; high-frequency Arm B cluster (PT_F, WS_PPL,
  HVA_EPI, ECD_CHLD, DM_POP, NT_ANT, CME, IM) follows. Each entry pins
  family / dataflow_id / canonical code / canonical label / synonym
  list / dimension hint / validation date. Shape pinned by a TypedDict
  (`CuratedEntry`). Exposes a `lookup_preferred(query)` helper used by
  `search_indicators` Stage 2 before the heuristic resolver.
- **`tests/test_v110_requires_confirmation.py`** — 7 test cases across
  four classes (`TestRequiresConfirmationTrue`,
  `TestRequiresConfirmationFalse`, `TestCuratedPreferred`,
  `TestBackwardCompat`).

### Changed

- **`formatters.ok()` signature** accepts four new optional keyword-only
  parameters: `requires_confirmation`, `recommended`, `assistant_guidance`,
  `next_step`. Each is gated by a presence check at output time so
  omitted kwargs do not pollute the response dict.
- **`server.search_indicators` decision logic** — a four-stage block
  inserted before the final `ok()` call, evaluated
  top-down:
  - **Stage 1 (curated ambiguity)**: resolver `_AMBIGUOUS` hit →
    `requires_confirmation=True` with `assistant_guidance`.
  - **Stage 2 (CURATED_PREFERRED catalog hit)**: `lookup_preferred(query)`
    returns an entry → `requires_confirmation=False` with `recommended`
    sourced from the catalog, `assistant_guidance`, and `next_step`.
  - **Stage 3 (confident in-results match)**: top relevance ≥ 90 OR
    gap to runner-up ≥ 15 → `requires_confirmation=False` with
    `recommended` sourced from results, `assistant_guidance`, and
    `next_step`.
  - **Stage 4 (otherwise)**: all four locals stay None — wire-equivalent
    to v1.0.0.
- **Py3.12 registry-drift skip** — `test_v090_ambiguity_flag.py` and
  `test_v110_requires_confirmation.py` skip cleanly when the active
  unicefdata YAML vintage drops `ECD_CHLD_LMPSL` _MERGE/_NEW siblings;
  heuristic precondition cannot hold.

### Backward compatibility

- All v1.0.0 response keys preserved unchanged. `relevance` still on
  every match (v0.9.0 contract). Full test suite (366 tests, incl. the
  73-test v0.9.0 / issue-#64 regression suite) passes without
  modification.
- New fields are additive. Clients that ignore unknown keys see no
  behavior change. A v1.0.0-pinned benchmark (e.g. the v9 OSF deposit's
  follow-on against v1.0.0) remains valid.

### Notes

- A/B replay completed 2026-05-29 (`internal/v1.1.0_design/ab_results.md`).
  Gate revised from EQA-improvement to behavioural-regression +
  advisory-emission. Verdict: ALLOW — no behavioural regression on
  either model (paired Δwaves +0.033 Sonnet, −0.033 Haiku);
  requires_confirmation_seen 0/30 -> 23/30 Sonnet, 0/30 -> 26/30 Haiku;
  final_text identical 22/30 Sonnet, 19/30 Haiku.
- Q5 / locked decisions: Pattern A is the *primary blocking signal*
  (faostat-mcp semantics, NOT sdmx-mcp advisory). `assistant_guidance`
  is English-only (Q4). `next_step` is a literal string (Q3).
  `CURATED_PREFERRED` is narrow (Q2 — 30 entries, not 100+; coverage
  expands in v1.2.0 based on triangulation gaps).

## [1.0.0] — 2026-05-28

> **First stable release.** Promotes the package from `Development Status :: 3 - Alpha`
> to `Development Status :: 5 - Production/Stable`. Closes the dominant tool-use
> loop pathology observed in the v9 Arm B benchmark (7,422 queries against
> Claude Sonnet 4.5 + Haiku 4.5): **96.3% of deep-iteration (≥10 wave) queries
> got stuck on `search_indicators`** because the response gave no machine-
> readable signal to stop. Models called `search_indicators` 14–17 times with
> different keyword guesses, never converging on a canonical answer. This was
> the dominant failure mode by a wide margin — hallucinated codes (0.04%),
> access-denied 403s (13.4%), and missing data (22.2%) were minor categories.
>
> The pathology was **disambiguation, not hallucination**. v1.0.0 closes it
> with a three-layer defense: machine-readable ambiguity flag (curated +
> heuristic detection), plain-English candidate differentiators, and a
> strict-canonical sibling tool for code lookups. All changes are strictly
> additive — no breaking changes from v0.8.0. The v9 OSF benchmark (which
> sha256-pinned the v0.8.0 surface in `config/v9/mcp_arm.yaml`) stays
> reproducible against v0.8.0; v1.0.0 is the basis for a follow-on
> registered comparison.

### Added

- **`ambiguity_flag` field on `search_indicators` results** with two
  detection paths:
  - **Curated** (`ambiguity_source: "curated"`): query matches a known-
    ambiguous entry in `indicator_resolver._AMBIGUOUS` (child mortality →
    CME_MRM0/CME_MRY0/CME_MRY0T4/CME_MRY1T4; vaccination coverage →
    IM_BCG/IM_DTP1/IM_DTP3/IM_MCV1/IM_MCV2; child marriage; etc.).
  - **Heuristic** (`ambiguity_source: "heuristic"`): resolver returned
    `unknown` but the search yields ≥3 candidates with similar relevance
    (within 10 points of top) and no canonical-threshold winner (≥90).
    Catches novel ambiguities not in the curated dict — e.g., the
    `ECD_CHLD_LMPSL` family (developmentally on track + `_MERGE` /
    `_PRXY` / `_NEW` variants) which was the empirical pathology from
    the v9 Arm B run.
- **`candidates` field** with `{code, name, differentiator}` entries.
  The `differentiator` is a one-line plain-English explanation of what
  makes each candidate different from its siblings — derived from a
  60+ entry curated suffix table covering UNICEF code conventions
  (mortality age brackets M0/Y0T4/Y1T4, vaccine doses DTP1/DTP3,
  methodology variants MOD/MERGE/PRXY, marriage cutoffs U15/U18,
  ISCED education levels, sex splits, etc.). Falls back to surfacing
  the raw suffix when no curated meaning applies; never invents
  semantics.
- **`abstain_instruction` field**: plain-English directive telling the
  model to STOP, list the candidates, and ask the requester to specify
  a code — explicitly NOT to call `search_indicators` again. The
  intended caller behavior is to mark the query done immediately on
  seeing `ambiguity_flag=True`; see the benchmark repo's
  `batch_arm_b.py::collect_wave` for the reference handler.
- **`ambiguity_source` field**: `"curated"` or `"heuristic"` so
  downstream analysis can distinguish the two trigger paths.
- **`relevance` score preserved in `search_indicators` results**. The
  score was already computed but dropped before returning. Exposing it
  lets the model rank candidates without a second tool call.
- **New tool: `lookup_by_code(code: str)`.** Strict canonical-code
  lookup sibling to `get_indicator_info`. Accepts only exact UNICEF
  codes (e.g. `CME_MRY0T4`); rejects natural-language descriptions,
  synonyms, and ambiguous phrases with an `abstain_instruction`
  redirecting to `search_indicators`. The two-tool separation gives
  the LLM a self-describing choice at tool-selection time:
  - have a CODE? → `lookup_by_code(code)`
  - have WORDS?  → `search_indicators(query)`
  Never falls back to search internally — guarantees deterministic
  behavior on canonical inputs.

### Fixed

- **`_AMBIGUOUS['child marriage']` realigned with the live unicefdata
  YAML.** The previous entry pointed at `PT_F_18-19_MRD` and
  `PT_F_15-49_MRD_18`, neither of which actually exist in the
  registry. Updated to `PT_F_15-19_MRD` + `PT_F_20-24_MRD_U15` +
  `PT_F_20-24_MRD_U18` (the canonical SDG 5.3.1 headline). The
  disambiguation_tip text was updated to match.

### Architecture

The MCP server delegates all data fetches (metadata + observations)
to `unicefdata`. Search relevance scoring remains MCP-internal
(`unicefdata` does not currently expose an equivalent). The two
new pieces (`lookup_by_code` and the ambiguity-flag detection) sit
strictly above `unicefdata` — they add LLM-orchestration semantics
without changing the canonical data layer. See the `differentiator`
module for the standalone suffix-mapping helper.

### Compatibility

- **Non-breaking from v0.8.0.** All four pre-existing tools
  (`search_indicators`, `get_indicator_info`, `get_data`,
  `get_temporal_coverage`) keep their existing input schemas and
  success shapes. The new fields are additive.
- **v0.8.0 callers see no change in behavior** unless they explicitly
  opt in by inspecting the new fields.

### Tests

- New `tests/test_v090_ambiguity_flag.py` (24 tests: curated, heuristic,
  self-describing-tool-boundary).
- New `tests/test_differentiator.py` (13 tests: mortality / methodology /
  immunization / fallback / edge cases).
- Existing 324 tests still pass.
- Full suite: **360 passing**.

### Known follow-ups (v1.1.0 candidates)

The empirical A/B replay against Claude Sonnet 4.5 on n=30 deep-iter
stuck queries from the v9 Arm B benchmark showed v1.0.0 closes 47% of
the pathology (Sonnet complies 14/14 when `ambiguity_flag` fires) but
misses 53% — concentrated in the ED_ANAR, NT_ANE, SPP_CHLD, PV_CHLD
families where the heuristic returns a clear top match but the model
keeps iterating with different keywords. A review of 17 official-
statistics MCP servers (data360, sdmx-mcp, fred, ecb, imf, oecd,
eurostat, faostat, agent-toolkit, nso1212, kolada, destatis, inegi,
ibge, mcp_unhcr, unicef-datawarehouse, plus this server) identified
three high-leverage patterns from faostat-mcp and inegi-mcp that
directly address the 53% gap:

- **Pattern A: `requires_confirmation` boolean as a hard ambiguity gate**
  (faostat-mcp `server.py:471-490`). Three-state branching on candidate
  count: 1 hit → `False` + commit-this-code signal; multiple hits →
  `True` + STOP-and-ask; zero hits → broaden-your-search. Pairs with
  the existing v1.0.0 `ambiguity_flag` field.
- **Pattern B: `CURATED_PREFERRED` catalog (~35 entries)** for the four
  demonstrated-gap families plus the ~30 highest-frequency v9 Arm B
  queries (inegi-mcp `config.py:104-170` pattern, ~51 entries with
  `✅ validado` markers).
- **Pattern D: `assistant_guidance` + `next_step` plain-English fields**
  on every successful tool response (sdmx-mcp `lines 2128-2543` +
  faostat-mcp `AGENT INSTRUCTION` docstring pattern).

Full review including comparison matrix, verified code citations, and
proposed code/schema shapes for v1.1.0: `internal/v1.1.0_pattern_review.md`.

The previously-listed candidates (move scoring upstream to unicefdata,
`get_value` convenience tool, caller-side code-shape detection) are
deferred to v1.2.0 — A + B + D should close the demonstrated gap first.

## [0.8.0] — 2026-05-11

> **Minor bump rationale:** this is the first release where MCP demonstrably
> makes the model safer on absent-data queries than the no-tools baseline
> (`hall_b 1.00%` < `hall_a 2.50%` on mcp060, `hall_b 2.25%` < `hall_a 2.50%`
> on a disjoint 20-country validation sample mcp073). That is a substantive
> behavior change relative to v0.7.x — the safety architecture was necessary
> through v0.7.2 but not yet sufficient; with the four post-fix corrections
> below it becomes sufficient. Minor (0.7 → 0.8) reflects this empirical
> property, not a breaking API change. No public API change vs v0.7.3.
>
> Also ships a new cross-model smoke test (`examples/mcp-smoke-test/
> mcp-multimodel-smoketest.py`) for validating the cross-provider
> generalisation question on the new safety property.

### Fixed (post-v0.7.3 release-cycle corrections)

Four atomic fixes for issues introduced or surfaced by v0.7.3's
release-prep hardening pass. The combined effect: POS_EQA recovers from
0.639 (the v0.7.3 PRE-FIX number documented in the [0.7.3] §Validation
block below) to **0.891**, and honestly-scored hallucination drops from
12.25% to **1.00%** on n=500 (v1.4 extractor rules). The four commits:

- **`_seed_data_frontier_cache` is now monotonic-up only.** v0.7.3's
  perf optimisation overwrote the per-session frontier cache with
  `df["period"].max()` from every successful response. Because `df`
  is filtered by the request's countries and start_year/end_year, that
  max year reflected the user's bounded slice — not the indicator's
  true frontier. Year-bounded queries early in a benchmark wave
  poisoned the cache downward, then later queries with year-args
  greater than the poisoned frontier were refused at the v0.6.0
  pre-flight check. Fix: only update the cache when the new max_year
  is strictly greater than what's already cached. Two regression
  tests in `tests/test_get_data.py::TestFrontierCacheSeeding` lock
  in the contract.
- **`_extract_from_tool_calls` no longer re-dispatches against the
  live MCP at analysis time.** Tool results are now persisted at
  dispatch time as `tc["result"]`; the post-run extractor reads from
  the persisted result first, falling back to re-dispatch only for
  legacy parquets that predate this commit. This eliminates the
  failure mode where post-run scoring stalled for 20+ minutes
  walking upstream-`unicefdata` cascade chains under burst load
  (v3 post-fix attempt) — analysis-time scoring is now decoupled
  from upstream availability long after the benchmark completed.
  Four regression tests in `tests/test_harness_tool_extraction.py`.
- **`unicefdata` cascade exception is classified as `no_data`.** When
  the upstream package walks its hardcoded fallback dataflow chain
  and exhausts all 5–7 candidates, it raises
  `SDMXNotFoundError: Indicator 'X' not found in any dataflow.` (with
  lowercase "not found"). The pre-fix `is_not_found` heuristic in
  `get_data`'s exception handler matched only "Not Found" (Title
  Case from HTTP responses), so the cascade-end exception was
  returned as a generic `Data fetch failed:` error. Fix: lower-case
  the heuristic and add an explicit branch for the cascade message.
  Tracking the upstream root cause at
  [jpazvd/unicefData-dev#91](https://github.com/jpazvd/unicefData-dev/issues/91).
  Two regression tests in `tests/test_get_data.py::TestUnicefdataCascadeIsNoData`.
- **v1.4 extractor — refusal language overrides tool-call extraction.**
  Per-row audit of the v0.7.3 v4 post-cache-fix run found that 45 of
  49 scored hallucinations were context-capture artifacts: the model
  correctly refused ("No data is available for stunting prevalence
  in Sierra Leone for 2020.") then provided surrounding-year data
  points as conversational context ("2019: 29.4872%, 2021: 26.2586%"),
  and the extractor pulled the context number as if it were the
  answer. Fix: when `_detect_refusal(text)` is True, force value/year
  to None regardless of `_extract_from_tool_calls` output — the
  model's stated refusal is authoritative; tool data offered as
  context is not the answer. `EXTRACTOR_VERSION` bumped to v1.4.
  Four regression tests in `tests/test_harness_tool_extraction.py`.

Final post-fix benchmark numbers (n=500, v1.4 rules, all rescored at $0
from existing parquets):

| Version | POS EQA (B) | hall_b T1 | hall_b T2 | hall_b combined | MCP makes safer? |
|---|---:|---:|---:|---:|:---:|
| v0.6.4 | 0.901 | 3.50% | 8.50% | 6.00% | ✗ |
| v0.7.1 / v0.7.2 | 0.793 | 1.00% | 6.50% | 3.75% | ✗ |
| v0.7.3 PRE-FIX (tainted) | 0.639 | 0.50% | 4.00% | 2.25% | ✓ (over-refusal artifact) |
| **v0.7.3 + fixes** | **0.891** | **0.00%** | **2.00%** | **1.00%** | **✓** |

Versus v0.7.1/v0.7.2 baseline: +12.4% accuracy, −73% hallucination
(combined), zero direct-prompt fabrications. Cost $9.20 (batch-priced).
Full write-up in `internal/v0_7_3_validation.md`. Pre-fix artifacts
are quarantined at `examples/results/_TAINTED_v073_prefix/` for
audit-trail.

**Second-sample validation (mcp073, 2026-05-10):** the headline result
was re-tested on a fifth independent ground-truth round (same 10
indicators, 20 NEW countries fully disjoint from prior pools, seed
`20260510`, $8.67 batch-priced, 49 min). POS_EQA_b = 0.9093 (vs 0.8908
on mcp060), hall_b combined = 2.25% (vs 1.00%). Both validation gates
clear (POS_EQA ≥ 0.85 AND hall_b ≤ 3%). 9 of 10 indicators score
0.984-1.000 on POSITIVE EQA; the single outlier (MNCH_BIRTH18 = 0.114)
is jpazvd/unicefstats-mcp-dev#64 reproducing on a different country
pool — confirms #64 is a deterministic resolver bug, not sample noise.
Full write-up: `internal/v0_7_3_second_sample_validation.md`.

### Added

- **`examples/BENCHMARK.md`** — comprehensive replicability guide for
  the EQA benchmark. Covers: every script in `examples/`, environment
  setup from a fresh clone, ground-truth construction, A/B benchmark
  runs (live + batch), per-wave checkpoint resume, salvage from
  already-completed batches, scoring, and analysis. Designed so a
  new contributor can clone the repo and reproduce the benchmark
  end-to-end without scripts breaking on missing dependencies.
- **`.gitattributes`** — Git LFS configuration for new
  `examples/results/*.{parquet,csv}` and `analysis/figures/*.{png,svg}`
  files. Existing files stay in regular git history (no `git lfs
  migrate` rewrite — would diverge clones); future runs use LFS.
  Ground-truth inputs (sample.csv, ground_truth_values.csv) stay in
  regular git so they remain diffable for replication.

### Changed

- **`pyproject.toml [benchmark]` optional extra** — added missing
  third-party deps (`numpy>=1.26,<3`, `matplotlib>=3.8,<4`,
  `scipy>=1.11`). The previous extra had `anthropic`, `python-dotenv`,
  `pandas`, `pyarrow` only — but `examples/statistical_analysis.py`,
  `examples/plot_results.py`, and the ground-truth scripts also
  import the three additions. Running `pip install -e ".[benchmark]"`
  on a fresh clone now installs everything needed for end-to-end
  replication.
- **`sync-to-public.yml`** — `rsync` now excludes
  `examples/results/*.parquet` and `examples/results/*.csv` from
  the public-mirror sync. Raw per-query LLM responses (1.0+ MB each)
  stay dev-only; the public mirror keeps headline-summary JSONs,
  ground-truth inputs, all benchmark scripts, and all docs. Per the
  dev-only-data convention added 2026-05-09.

### Fixed

- **Stale `.gitignore` entry** — removed `examples/ground_truth/`
  (a directory that never existed; the actual ground-truth dirs are
  `examples/ground_truth_mcp060/` and `examples/ground_truth_r2/`,
  both tracked). Replaced with a comment so a future contributor's
  `examples/ground_truth/` work is not silently ignored.

## [0.7.3] — 2026-05-09

> **Note (2026-05-10):** the §Validation block below documents the
> n=500 numbers from the as-tagged code (POS_EQA=0.639, hall_b=3.0%,
> attributed below to "model drift / wave-cap clipping"). Subsequent
> investigation localised the drop to a cache-contamination regression
> in `_seed_data_frontier_cache` introduced by this same release. Four
> post-discovery fixes — see [Unreleased] above — recover POS_EQA to
> 0.891 and drop honestly-scored hallucination to 1.00%. The "drift"
> hypothesis was wrong; the bug was in this release's own commit
> `8e073a1`. The §Validation prose below is preserved as historical
> record; the [Unreleased] section is the corrected reading.

Code-review hardening pass: structural fixes to the retry helper, the
frontier-cache lifecycle, period parsing, and MCP-boundary input limits.
Builds on the v0.7.2 tooling/docs release shipped earlier the same day —
this is the runtime correctness pass on top of v0.7.2's harness work.
No user-facing API change.

### Fixed

- **`_retry` no longer misclassifies error bodies as 4xx.** The v0.7.1
  substring matching against `str(exc).lower()` for `"404"` would fire
  on any message containing those characters — e.g. `"upstream returned
  4040 chars of HTML"`, causing transient 5xx responses to be re-raised
  instead of retried. Replaced with `_is_client_error()` which prefers
  structured signals (`exc.status_code`, `exc.response.status_code`,
  `exc.code`) and falls back to a *word-bounded* substring match for
  the standalone HTTP-status tokens. Also raises `ValueError` for
  `max_attempts < 1` (was a latent `raise None` path).
- **Retry log lines no longer leak embedded newlines** — exception
  messages are `\n`/`\r`-stripped before `logger.info()`, closing a
  minor log-injection vector when an upstream error body contains a
  forged `INFO ...` second line.
- **`get_data` no longer issues a duplicate SDMX round-trip** to
  `get_temporal_coverage` when called with year arguments after a
  successful prior fetch. The frontier cache is now seeded from
  `df["period"].max()` immediately after the main fetch, so the
  next call's pre-flight check hits the cache instead of paying
  ~one full request of latency to re-learn the same frontier.
- **Non-numeric SDMX periods (`"2019-Q1"`, `"2019-M03"`) no longer
  crash four downstream sites:** the gap-detection block in `get_data`,
  the frontier-from-response extraction, `formatters.summarize_data`
  (`int(periods.min())`), and `formatters.compute_trend`
  (`float(latest["period"])`). All four now fall back to the
  four-character year prefix when numeric coercion fails. Matches
  the defensive behavior `get_temporal_coverage` already had.
  (The `summarize_data` and `compute_trend` regressions were latent
  in v0.7.1 and only surfaced when the new non-numeric-period test
  was added — fixing the `get_data` block alone left them unguarded.)
- **`compare_indicators` MCP prompt now uses repr-safe formatting**
  for the country list literal it embeds in the rendered prompt body
  (`json.dumps` instead of `f"{country_list}"`), preventing any
  embedded quote in user input from breaking the rendered Python
  literal in the prompt.
- **Removed dead branch in `_get_data_frontier`** — `cov.get("data")`
  could never be a dict because `formatters.ok()` flattens with
  `**data`. Tightened to read `cov.get("end_year")` directly.
- **Removed unused `validate_countries` validator** — superseded by
  `country_resolver.resolve_countries` (v0.6.2) which accepts both
  ISO3 codes and country names. The old validator rejected names
  with a strict `len==3 && isalpha()` check, so it was actively
  wrong on the v0.6.2+ surface. The list-level checks (empty,
  `MAX_COUNTRIES`) stay in `get_data` itself.

### Added

- **MCP-boundary length limits on free-text inputs** —
  `validate_query` (≤200 chars), `validate_region` (≤100 chars),
  `validate_country_inputs` (≤100 chars per entry). Stops a 1 MB
  blob from landing in log lines / cost amplification while
  leaving room for any plausible legitimate query.
- **Test coverage for `_retry`** — backoff, early-exit on 4xx,
  the `4040`/`404` substring regression, log-injection guard,
  `max_attempts=0` validation. Previously the helper was untested.
- **Test coverage for hyphenated indicator codes** — `ED_15-24_LR`
  and `PT_F_15-49_FGM` round-trip through both code-passthrough
  and synonym-match paths. Locks in the YAML codelist contract:
  if `unicefdata` ever drops a hyphen, the synonym entry's
  `if code in code_to_name` guard would silently fall through
  to "unknown" and the failure would only surface as a 404 at
  the SDMX layer with no resolver hint.
- **Test coverage for non-numeric periods** — quarterly periods
  in a successful response no longer break gap detection or
  frontier extraction.
- **Test coverage for frontier-cache seeding** — verifies that
  a successful `get_data` populates the cache and that subsequent
  year-bounded calls reuse the cached frontier instead of issuing
  an extra coverage round-trip.
- **`tests/test_get_data.py` now uses an autouse `monkeypatch`
  fixture** to isolate the per-test view of `_data_frontier_cache`,
  replacing the v0.7.1 pattern of mutating the module global
  directly (which leaked between tests).

### Changed

- **`pyproject.toml`** — pinned `fastmcp>=3.0,<4` (was `>=2.0`
  with no upper bound). CI has been resolving fastmcp 3.x for a
  while even with the old `>=2.0` floor, so 3.x is what's actually
  tested. fastmcp 2.x wraps `@mcp.tool()`-decorated functions in
  a non-callable `FunctionTool`, which silently breaks the unit
  test pattern of importing `get_data` and calling it directly.
  The lower-bound bump closes that latent incompatibility; the
  `<4` upper bound blocks an unannounced future major.
- **`Dockerfile`** — copies only `pyproject.toml`, `README.md`,
  and `src/` into the image (was `COPY . .`, which shipped
  `internal/`, `analysis/`, `examples/`, `tests/`, `.git/`,
  fattening the image with no runtime value). Drops to a
  non-root user (`mcp`, uid 10001) before runtime.
- **Added `.dockerignore`** mirroring the build-context exclusion
  list, so any future `COPY .` would still respect the same
  boundary.
- **`server.py` reads `__version__` from the package** instead
  of a hardcoded literal in the `FastMCP(...)` constructor,
  removing a second source of truth.

### Validation (2026-05-09)

- **Unit + lint + mypy + version-consistency: all green.** 232 tests
  pass / 1 skipped post-rebase on develop (gained 17 tests from
  develop's harness-hardening + smoke-parser additions).
- **Free local benchmark** (`examples/benchmark.py`): 5/5 use cases
  pass against live UNICEF SDMX.
- **Sync EQA smoke (n=9)** against Anthropic API: POS EQA A=0.300,
  B=1.000; T1+T2 hall A=0%, B=0%; 23 MCP tool calls, 0 tool errors;
  $0.30 total spend. Saved to `examples/results/eqa_..._smoke_v073.*`.
- **Stdio MCP smoke** (`examples/mcp-smoke-test/mcp-figures.py`)
  against v0.7.3 dev tree: 200 obs across IND/KEN/BRA via CME_MRY0;
  server identity correctly stamped as `unicefstats-mcp v0.7.3` on
  the figures (validates the `version=__version__` refactor — the
  hardcoded `"0.7.2"` from develop would have lied here). Figures
  in `examples/mcp-smoke-test/figures/*-2026-05-09.png`.
- **Full n=500 batch EQA — completed 2026-05-09 17:20 UTC** after the
  morning's UNICEF rate-limit (403 from `awselb/2.0`) cleared.
  Direct `curl` confirmed the morning block was upstream (not a
  v0.7.3 bug); first attempt was killed to stop wasting Anthropic
  budget on doomed requests. Second attempt: 8 waves, 57 min wall
  clock, $11.09 cost (batch-discounted), 0 tool errors,
  0 5xx/403 contamination in the saved parquet. Headline numbers:

  | Version | POS EQA (B) | Halluc rate (B) | 1st-call OK |
  | --- | --- | --- | --- |
  | v0.6.4 (May 4) | 0.894 | 16.25% | 99.8% |
  | v0.7.2 (CHANGELOG) | 0.897 | 13.0% | n/a |
  | **v0.7.3 (May 9)** | **0.639** | **3.0%** | **100.0%** |

  v0.7.3 **halves the headline hallucination rate** (16.25% → 3.0%)
  by shifting "graceful fallback" responses into "clean refusal" —
  the refined classifier (separates real fabrication from
  graceful-fallback text the headline metric over-counts) shows
  true fabrication essentially unchanged (0.50% → 0.75%, within
  sampling noise on n=400). 1st-call success hits 100.0%.

  But POS EQA drops 0.255 (0.894 → 0.639). Source: 16/100 POSITIVE
  queries returned NaN extracted_value, 14 went refused, 2 had
  empty responses (vs 0 / 0 / [unchecked] for v0.6.4). This is a
  quality trade-off, **not a code regression** — v0.7.3's diff is
  non-behavioural on the EQA test surface. Most likely cause:
  Anthropic Sonnet-4 deployment drift between 2026-05-04 (v0.6.4
  baseline) and 2026-05-09 (this run); `analysis/CROSS_VERSION_
  ANALYSIS.md` §1 already documented model drift moving the v0.6.2
  → v0.6.4 numbers in the *positive* direction — drift can move the
  other way too. Secondary contributor: the 8-wave cap clipped
  long tool-use chains. Two follow-up tests would isolate the cause:
  v0.6.4-source replay on today's snapshot, and a `MAX_WAVES=12`
  sensitivity test. Full analysis + raw data + figures:
  `internal/v0_7_3_validation.md`,
  `analysis/tables/headline_may2026_progression.md`,
  `analysis/figures/01_pos_eqa_progression.png`.
- **Verified live**: `_is_client_error()` correctly classified the
  403 responses as non-retryable during the morning's incident,
  so v0.7.3's `_retry` did not consume the exponential-backoff
  budget on doomed requests. Now pinned by
  `tests/test_retry.py::test_403_via_word_bounded_substring`
  and `test_403_access_denied_phrase_is_client_error` (added in
  response to the incident).

## [0.7.2] — 2026-05-09

Tooling-and-documentation patch release. No API or behavioural change
to the runtime server (no `src/unicefstats_mcp/` diffs since v0.7.1) —
this release captures four weeks of substantive work in `examples/`,
`tests/`, `internal/`, and the public README that accumulated since
v0.7.1 shipped on 2026-05-05.

The headline empirical addition is a **v0.7.2 same-day clean
reproduction** of the original 600-query benchmark on a 500-query
subset, with the v0.6.4 baseline run same-day to control for
upstream-model snapshot drift. It confirms the original 6.7×/8.2×
accuracy headline at ~7× and shows the v0.4.0 safety layer + v0.7.0
indicator resolver brought T2 fabrication from 37% (v0.3.0) → 13%
(v0.7.2) — a 24-of-26 pp reduction. The residual ~11 pp gap appears
structural and matches what the broader tool-augmented LLM and RAG
literature documents.

### Added

- **v0.7.2 same-day clean benchmark reproduction (2026-05-08).** Re-ran a
  500-query subset (100 POS + 200 T1 + 200 T2) on the per-wave
  checkpoint architecture (PR #53), with the v0.6.4 baseline run
  same-day to control for upstream-model snapshot drift. Results:
  POS EQA 0.121 (no tools) vs 0.897 (with v0.7.2 MCP, +77.6 pp,
  ~7×); T1+T2 hallucination 2.0% (no tools) vs 13.0% (with MCP,
  +11.0 pp). A-side EQA was within 0.3 pp across runs — same-day
  discipline confirmed; the B-side delta is real, not snapshot drift.
  Confirms the original 6.7× / 8.2× accuracy headline at ~7× and
  shows the v0.4.0 safety layer + v0.7.0 indicator resolver brought
  T2 fabrication from 37% (v0.3.0) → 13% combined T1+T2 (v0.7.2) —
  a 24-of-26 pp reduction. The residual ~11 pp gap appears
  structural, matching what the broader tool-augmented LLM and
  RAG literature documents (see README §Limitations for citations
  to *The Reasoning Trap* (ICLR 2025), *Reducing Tool Hallucination
  via Reliability Alignment* (Cao et al., 2024), and *ReDeEP* (Sun
  et al., 2024)).
- **README and LinkedIn-series drafts** updated with v0.7.2 numbers
  plus literature citations grounding the residual-hallucination
  finding (PR #58 for series; PR #59 for README + CHANGELOG).
  Original 600-query / 40-country benchmark numbers are preserved
  as primary evidence (broader external validity); v0.7.2 is
  positioned as cleaner-methodology reproduction (per-wave
  checkpoint, fresh-dispatch rescoring, same-day v0.6.4 baseline).
- **Per-wave state checkpoint architecture** for the EQA harness
  (PR #53). Closes the resume row-alignment bug discovered during
  v0.7.0 validation. `benchmark_eqa_batch.py` now writes a JSON
  checkpoint after each wave; `resume_batch_run.py --load-state`
  loads from checkpoint without live tool re-dispatch (the bug's
  root cause). Includes 10 round-trip tests in
  `tests/test_state_checkpoint.py`.
- **`examples/salvage_batches.py`** (PR #54) — one-shot script to
  rebuild a parquet from already-completed Anthropic batch results
  without live tool re-dispatch. Covers the case where a benchmark
  crashed mid-flight and the legacy resume path produced a
  row-misaligned parquet. Cost: $0 (re-fetching batch results is
  free for ~29 days post-completion).
- **`examples/mcp-smoke-test/`** (PR #57) — self-contained
  `uv run --script` Python program that exercises five stdio-MCP
  servers (unicefstats, world-bank, fred, data360, data-commons)
  against real `tools/call` requests and renders one matplotlib
  figure per source. Includes:
  - **Variable-code + server-version + execution-provenance footnote**
    on every figure (UTC timestamp, host, invoking agent).
  - **`--edge-cases` mode** demonstrating five known MCP failure
    modes (synonym-table gap, misleading code prefix,
    refuse-with-disambiguation, cross-provider taxonomy mismatch,
    `search_indicators` bypass) via real MCP calls.
  - **20 parser unit tests** covering all five per-source response
    parsers (`tests/test_smoke_parsers.py`).
  - **Cross-check artefact** confirming the UNICEF/WB U5MR gap is
    age-denominator (IMR vs U5MR), not country-composition or
    methodology — UNICEF and WB agree within ±0.04 when the same
    concept is queried.
  - **Comprehensive in-line documentation** (~370 lines) for
    readers unfamiliar with MCP or Python.
- **`internal/PARKED_post_v0_7_review_concerns.md`** (PR #56) —
  parking-lot doc for five post-v0.7 stakeholder-review follow-ups,
  with a 2026-05-08 postscript marking Item 4 (Validation pilot)
  RESOLVED by the same-day clean baseline. Re-anchors Item 1's
  magnitude estimate to the clean number. `internal/` is
  sync-excluded from the public mirror.

### Fixed

- **Harness structural hardening** (PR #55) — three classes of
  recurrence eliminated: shared `load_sample_in_benchmark_order()`
  helper for the canonical pos+T1+T2 reorder (was duplicated across
  four scripts); `line_buffering=True` on stdout wrappers in three
  background-runnable scripts (was silently defeating `python -u`);
  7 alignment regression tests in `tests/test_harness_alignment.py`
  including a NEGATIVE test asserting misalignment IS detectable
  when ordering is wrong.

## [0.7.1] — 2026-05-05

Hardening pass on the v0.7.0 indicator resolver, addressing four
review comments from PR #46. Correctness/contract improvements only —
no functional change to the resolver's lift on valid queries.

### Fixed

- **`get_data` now canonicalizes indicator codes on `code_passthrough`** —
  the resolver returned the canonicalized form (e.g., `"  cme_mrm0  "` →
  `"CME_MRM0"`) in `r.code` for the `code_passthrough` status, but the
  integration only adopted that form for `synonym_match` /
  `name_index_hit`. Code-passthrough rows previously flowed through with
  the user's quirky form, so `result["indicator"]` echoed the lowercase /
  whitespace-padded original. Now the SDMX call and response envelope
  carry the canonical code regardless of input shape.
- **Dropped dead `_SYNONYMS["anc 1+"]` key** — `_normalize` strips `+`
  as a separator, so the lookup key could never match. Replaced with
  `"anc 1"` (the post-normalize form).
- **`resolve_indicator()` docstring contract** — said `"unknown" → fall
  back to error`, but `get_data` actually passes unknown through to SDMX
  for backward compat with codes added upstream after the YAML snapshot.
  Updated docstring to document `"unknown" → caller decides`.

### Added

- **3 integration tests in `TestIndicatorResolverIntegration`** covering
  the `get_data` resolver wiring (canonicalization, response echo,
  ambiguous-error envelope shape). Resolver itself was already fully
  unit-tested in `tests/test_indicator_resolver.py`; these new tests
  cover the integration boundary.
- **`internal/BUG_resume_batch_row_alignment.md`** — tracking note for a
  separate bug discovered during v0.7.1 validation: `resume_batch_run.py`
  produces row-misaligned parquets. Not a v0.7.1 blocker; affects only
  the resume-script code path. Direct `benchmark_eqa_batch.py` runs are
  unaffected.

## [0.7.0] — 2026-05-05

### Added

- **Indicator-name resolver (`get_data` accepts names)** — extends the
  v0.6.2 country-resolver pattern to indicators. The model can now pass
  human-readable names like `"neonatal mortality"`, `"U5MR"`, `"stunting"`,
  `"LBW"` instead of guessing canonical codes from training data. Genuinely
  ambiguous queries (`"child mortality"` matches NMR/IMR/U5MR/1-4 mortality)
  are refused server-side with a disambiguation list rather than silently
  picking one. Closes the §5.3 known failure mode where the model recalls
  a similar-but-wrong code and the server returns the wrong indicator's
  data. Backward-compatible — codes still pass through unchanged. Loads
  the 738-indicator metadata YAML shipped by `unicefdata`.
- **`indicator_resolution` echo in get_data response** — every successful
  call now carries `{original_input, resolved_code, canonical_name, status}`
  so the model can confirm the resolved indicator matches the user's intent.

## [0.6.4] — 2026-05-02

Release-flow consolidation. The v0.6.3 release surfaced three
adjacent issues with the dev → public → PyPI → registry chain:

  1. The MCP registry rejected v0.6.3's `server.json` with
     `expected length <= 100` on the `description` field
     (was 225 chars).
  2. The public repo (`jpazvd/unicefstats-mcp`) had a stale
     `publish.yml` synced from earlier dev versions, redundant now
     that PyPI publishing happens from `unicefstats-mcp-dev` only.
  3. GitHub Releases were missing on the public repo for v0.6.2
     and v0.6.3 (only v0.3.3 / v0.4.0 / v0.5.1 had Release pages),
     because nothing in the release flow created them.

### Changed

- **`server.json` description shortened to 100 chars** — fixes the
  registry validation error so future releases publish successfully.
- **`sync-to-public.yml` no longer copies `publish.yml` to public.**
  PyPI publishing is now exclusively a dev-repo responsibility.
  cpina/github-action-push-to-another-repository's force-mirror push
  removes any stale `publish.yml` from the public repo on next sync.

### Added

- **`.github/workflows-public/release.yml`** — a workflow that lives
  under a non-standard path in dev (so GitHub Actions does NOT execute
  it on dev) but gets copied to public's `.github/workflows/release.yml`
  by the sync workflow. On tag push, public's release.yml extracts
  notes from CHANGELOG.md and creates a GitHub Release on public using
  its own `GITHUB_TOKEN` — no PAT or cross-repo secrets required.
  Also supports `workflow_dispatch` with a `tag` input for retroactive
  Release creation on existing tags (used to backfill v0.6.2 / v0.6.3).
- **`sync-to-public.yml` now copies `.github/workflows-public/*.yml`**
  into `sync-staging/.github/workflows/`. The mechanism is generic —
  future public-only workflows can be added by dropping a YAML in
  `.github/workflows-public/` on dev.

### Why a release-only-for-CI-fixes (again)

Same reason as v0.6.3: the new `registry-publish` job (introduced in
v0.6.3 via PR #35) only fires on new tags. v0.6.3 itself failed at
the registry step because of the description length, so v0.6.4 is the
first tag where the full chain (PyPI + registry + sync + public Release)
should run end-to-end.

No code, API, or behavioural changes vs v0.6.3.

## [0.6.3] — 2026-05-02

Patch release whose sole purpose is to activate the new
`registry-publish` CI job (added in #35) for the first time. No
functional / API / behavioural changes vs v0.6.2.

### Why this exists

v0.6.2 shipped to PyPI successfully but never made it to the official
MCP registry at <https://registry.modelcontextprotocol.io>. That gap
left downstream catalogues (lobehub, smithery, claude.ai/mcp, etc.)
showing stale information — lobehub was still serving v0.2.0 from
March 26 even after v0.6.2 published.

The natural fix is to run `mcp-publisher publish` once locally to
backfill v0.6.2 to the registry, but that path is blocked on the
maintainer's UNICEF-managed laptop by corporate AppLocker policy
(unsigned binary execution refused at the kernel level).

PR #35 added a `registry-publish` job to publish.yml that runs the
publisher CLI inside a GitHub Actions runner — no AppLocker, no local
cert dance. That job only fires for new tags, so this v0.6.3 release
exists to be that first new tag.

### Changed

- Version bumped 0.6.2 → 0.6.3 across the 5 canonical sites
  (`__init__.py`, `pyproject.toml`, `server.json` × 2, `server.py`
  FastMCP instance). No other code changes.

### Tested

- `pytest tests/`: 137/137 pass
- `scripts/check_version_consistency.py`: OK
- `ruff check`: clean
- `mypy src/unicefstats_mcp/`: no issues

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
