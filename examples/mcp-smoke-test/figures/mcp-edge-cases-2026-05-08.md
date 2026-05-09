# MCP edge cases — what the unicefstats-mcp resolver can and CANNOT solve

- Generated: `2026-05-08T19:28:54Z` on `994560AL9022638`
- Invoked by: `Claude Opus 4.7 (1M context) via Claude Code`
- Source: `examples/mcp-smoke-test/mcp-figures.py --edge-cases`

Each case below sends a real `tools/call` request through the same JSON-RPC stdio path the figure rendering uses — no shortcuts to internal Python imports. The intent is to make the MCP's failure modes empirically visible: an LLM agent calling these MCPs naively will hit each case in the wild.

## Case 1 — Synonym-table gap (the table is hand-curated)

- **Tried:** `get_data({'indicator': 'under-5 mortality', 'countries': ['IND']})`
- **Expected:** FAIL — 'under-5 mortality' (with hyphen) isn't in the synonym table
- **Got:** `see Response below`
- **Response (truncated):**

```
{"status":"error","error":"Data fetch failed: Indicator 'under-5 mortality' not found in any dataflow.\n  Tried dataflows: GLOBAL_DATAFLOW\n  Browse available indicators at: https://data.unicef.org/","tip":"Check indicator code with search_indicators() and country codes with list_countries()."}
```

**Why it fails:** The resolver's `_SYNONYMS` table covers `'under five mortality' → CME_MRY0T4`, but the hyphen variant `'under-5 mortality'` isn't a key in the table after normalisation, so the resolver returns `unknown`.

**MCP-level mitigations that exist:** the resolver does normalise case and whitespace, and refuses-with-list when a query matches multiple candidates (see Case 3 below).

**MCP-level mitigations that don't exist (yet):** fuzzy matching, synonym-table mining from query logs (parking-lot item 3), or LLM-assisted normalisation upstream of the MCP.

---

## Case 2 — Code prefix is misleading (CME_ ≠ U5MR)

- **Tried:** `get_data({'indicator': 'CME_MRY0', 'countries': ['IND']})`
- **Expected:** PASS technically — but the value is IMR (0-1 yr), NOT U5MR, despite the 'CME' prefix
- **Got:** `see Response below`
- **Response (truncated):**

```
{"status":"ok","source":"UNICEF Data Warehouse via SDMX API","data_completeness":"complete","indicator":"CME_MRY0","indicator_resolution":{"original_input":"CME_MRY0","resolved_code":"CME_MRY0","canonical_name":"Infant mortality rate","status":"code_passthrough"},"countries_requested":["IND"],"countries_resolved_to":["IND"],"country_resolutions":{},"countries_returned_with_names":{"IND":"India"},"verify_country_directive":"Country resolution: see `country_resolutions` and `countries_returned_with_names`. If the names there match what the user asked about, proceed. If you passed an ISO3 code an...
```

**Why it's confusing:** UNICEF's *Child Mortality Estimates* (CME_) prefix groups four codes — `CME_MRM0` (NMR), `CME_MRY0` (IMR), `CME_MRY0T4` (U5MR), `CME_MRY1T4` (1-4 mortality). `CME_MRY0` is specifically *infant* mortality despite the 'child mortality' prefix.

**Why the MCP can't relabel:** UNICEF's API itself returns `indicator_name='Infant mortality rate'` for `CME_MRY0`. The MCP wraps upstream faithfully — relabelling would mask drift between MCP cache and upstream truth. See [CROSS-CHECK-imr-vs-u5mr.md](CROSS-CHECK-imr-vs-u5mr.md) for the empirical demonstration.

**MCP-level mitigation that exists:** the response includes `indicator_resolution.canonical_name`, which a careful agent can read to verify it got what it asked for.

---

## Case 3 — Refuse-with-disambiguation (the MCP doing well) ✓

- **Tried:** `get_data({'indicator': 'child mortality', 'countries': ['IND']})`
- **Expected:** REFUSE — server returns ambiguity error listing NMR/IMR/U5MR/MR1T4 candidates
- **Got:** `see Response below`
- **Response (truncated):**

```
{"status":"error","error":"Indicator 'child mortality' is ambiguous — it matches multiple codes. Pass one of these specific codes (or a more precise name):\n  - CME_MRM0: Neonatal mortality rate\n  - CME_MRY0: Infant mortality rate\n  - CME_MRY0T4: Under-five mortality rate\n  - CME_MRY1T4: Child mortality rate (aged 1-4 years)","tip":"Use search_indicators() if you need to browse further.","indicator_disambiguation":[{"code":"CME_MRM0","name":"Neonatal mortality rate"},{"code":"CME_MRY0","name":"Infant mortality rate"},{"code":"CME_MRY0T4","name":"Under-five mortality rate"},{"code":"CME_MRY1...
```

**Why this works:** The resolver's `_AMBIGUOUS` table maps known-confusing terms (`'child mortality'`, `'vaccination'`, etc.) to a list of candidate codes. When the agent submits such a term, `get_data` returns an error listing the candidates instead of silently picking one. This is the v0.7.0 resolver's headline contribution.

**The trade-off:** refuse-with-list trades POS-EQA accuracy for hallucination reduction. The clean v0.7.1-vs-v0.6.4 benchmark (this PR's same-day re-run) showed this is approximately neutral on POS-EQA and slightly better on hallucination rate — net positive for the use case.

---

## Case 4 — Cross-provider taxonomy mismatch (no MCP can fix)

- **Tried:** `get_data({'indicator': 'MortalityRate_Person_Upto5Years', 'countries': ['IND']})`
  (passing Data Commons' code to the UNICEF MCP)
- **Expected:** FAIL — Data Commons code passed to UNICEF MCP; each provider has its own taxonomy
- **Got:** `see Response below`
- **Response (truncated):**

```
{"status":"error","error":"Data fetch failed: Indicator 'MortalityRate_Person_Upto5Years' not found in any dataflow.\n  Tried dataflows: GLOBAL_DATAFLOW\n  Browse available indicators at: https://data.unicef.org/","tip":"Check indicator code with search_indicators() and country codes with list_countries()."}
```

**Why it fails:** Same concept, different codes per provider:

- UNICEF:        `CME_MRY0T4`
- World Bank:    `SH.DYN.MORT`
- Data Commons:  `MortalityRate_Person_Upto5Years`
- Data360:       `WB_WDI_SH_DYN_MORT`

**Why MCPs can't fix this:** each MCP wraps one provider's API and faithfully exposes its native taxonomy. Reconciling across providers requires a meta-layer above the MCPs (e.g., a Data Commons-style knowledge graph that maps cross-provider codes), which is a fundamentally different artifact.

**Empirical bound:** when the SAME concept (U5MR) is queried from UNICEF and WB, the values agree within ±0.04 across 70 years (see CROSS-CHECK-imr-vs-u5mr.md). So providers ARE consistent on the same concept — they just call it different codes.

---

## Case 5 — search_indicators bypass (resolver doesn't help)

- **Tried:** `search_indicators({'query': 'mortality'})`
- **Expected:** AMBIGUOUS — returns multiple results; agent must disambiguate without the resolver's help
- **Got:** `see Response below`
- **Response (truncated):**

```
{"status":"ok","source":"UNICEF Data Warehouse via SDMX API","data_completeness":"complete","query":"mortality","total_matches":24,"showing":20,"results":[{"code":"CME","name":"Child mortality","description":"Child mortality","category":""},{"code":"CME_ARR_10T19","name":"Annual Rate of Reduction in Mortality Rate Age 10-19","description":"","category":""},{"code":"CME_MRM0","name":"Neonatal mortality rate","description":"Probability of dying during the first 28 days of life, expressed per 1,000 live births","category":""},{"code":"CME_MRM1T11","name":"Mortality rate age 1-11 months","descript...
```

**Why MCP can't fully fix this:** the resolver's disambiguation pattern (Case 3) only fires when the agent calls `get_data` with a string argument. If the agent instead calls `search_indicators` to discover codes, then picks the first one and feeds it to `get_data`, the resolver sees only a valid code (passthrough) and has no opportunity to flag ambiguity.

**MCP-level mitigation that exists:** `search_indicators` returns canonical names from UNICEF metadata, so a careful agent can read the names and notice when two results have similar codes but different concepts (e.g., `CME_MRY0` = 'Infant mortality' vs `CME_MRY0T4` = 'Under-five mortality').

**MCP-level mitigation that doesn't exist:** `search_indicators` doesn't refuse-with-disambiguation when the query matches multiple high-similarity codes. Adding that would require carrying the disambiguation table into the search path — non-trivial since search_indicators returns ranked results, not exact-match candidates.

---

## Summary table

| # | Case | What MCP does | What MCP CAN'T do |
|---|---|---|---|
| 1 | Hyphen-variant synonym | Normalises case/whitespace; refuses-with-list on multi-match | Catch every phrasing humans invent |
| 2 | Misleading code prefix | Returns the upstream `canonical_name` so agent can verify | Relabel codes that upstream itself labels confusingly |
| 3 | True ambiguity | Refuses-with-list (the v0.7.0 headline feature) ✓ | n/a — this is what the MCP does well |
| 4 | Cross-provider codes | Stays faithful to its own provider's taxonomy | Reconcile across providers (needs a meta-layer) |
| 5 | search_indicators path | Returns canonical names alongside codes | Refuse-with-list on search-path queries |
