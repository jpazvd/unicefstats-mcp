# Concept Note: MCP as Reference Architecture for AI-Ready Official Statistics

**Version:** 1.1 — April 2026
**Author:** Joao Pedro Azevedo
**Status:** Working draft for discussion

---

## 1. The Problem: AI Systems Are Making Up Statistics

UNICEF publishes that 4.9 million children under five died in 2022. WHO publishes vaccination rates for 195 countries. ILO tracks child labour across decades. These numbers shape policy. Governments allocate budgets based on them.

Now AI systems — ChatGPT, Claude, Copilot, and the autonomous agents built on them — retrieve and present these statistics to users. When the data exists, this works well. When it doesn't, AI systems fill the gap. They fabricate plausible-sounding numbers and present them with the same confidence as real data.

This is not hypothetical. In benchmark testing of an LLM querying UNICEF data, approximately 10% of queries where the API returned no data still produced fabricated statistics in the AI's response. The fabricated numbers looked authoritative because they came from a conversation about real UNICEF data.

Current data APIs were built for human analysts who can spot a missing value. They return empty results and trust the user to notice. AI systems do not notice. They fill the silence.

**The core question this project addresses:** Can we build a data interface that *tells* AI systems when data is missing, partial, or unreliable — in a format they are designed to obey?

## 2. What We Built

The `unicefstats-mcp` server connects AI systems to the UNICEF Data Warehouse (200+ indicators, 200+ countries) using the Model Context Protocol (MCP) — an open standard that lets AI assistants call external tools, much like a web browser calls APIs.

What makes this server different from a standard data API is not the data access. It is the **safety layer** — a set of features that reduce the chance of an AI system misrepresenting what the data says (or doesn't say).

### Seven features, and what each one prevents

| Feature | What it prevents | How |
|---|---|---|
| **Structured status field** | AI treats empty results as "I don't know" rather than "I should guess" | Every response includes a `status` flag: `ok`, `no_data`, or `error`. When status is `no_data`, it includes an explicit instruction: "Do NOT provide an estimate." |
| **Completeness tracking** | AI presents partial data as if it were complete | Every response declares whether the data is `complete`, `partial` (some requested countries missing), `truncated` (row limit hit), or `empty`. |
| **Missing-country detection** | AI invents values for countries that lack data | If you ask for Brazil, India, and Nigeria but Nigeria has no data, the response names Nigeria as missing and warns: "Do not estimate values for missing countries." |
| **Anti-fabrication directives** | AI generates plausible numbers when the real answer is "no data" | Three layers: standing instructions loaded at startup, per-response warnings, and a hard `no_data` status that tells the AI to stop. |
| **Provenance metadata** | AI cites the wrong source or an unverifiable one | Every data response includes a structured citation with the API URL that produced it, so the claim is checkable. A metadata tool returns the server's identity, publisher, and source documentation. |
| **Tamper-resistant publishing** | A modified or impersonated copy of the server gets trusted | The server is published from GitHub to PyPI using cryptographic attestation (no stored passwords). Anyone can verify that the installed package matches the source code. |
| **Accuracy benchmark (EQA)** | No way to know if the safety features actually work | A 300-query test suite measures three things: Did the AI find the right indicator? Did it report the right year? Did it report the right value? The composite score (Extraction Quality Assessment) provides a repeatable, quantitative measure. |

None of these features depend on UNICEF's specific data. Any organization that publishes statistics and wants AI systems to use them honestly can adopt the same patterns.

## 3. Design Principles

Five rules guided the design. They apply to any data server that AI systems will query.

### 1. Silence is dangerous — make absence explicit

When an API returns nothing, most systems return an empty list. To a human, that means "no data." To an AI, it often means "I should figure it out myself."

The fix: when a query finds no data, return a status code (`no_data`) with a written directive: "This data does not exist in the source. Do NOT provide an estimate." This is not a suggestion — it is a structured field that AI systems are trained to follow.

### 2. Say how complete the answer is

A response that returns data for 3 of 5 requested countries looks like a normal response unless it says otherwise. The server must label every response: *complete* (you got everything you asked for), *partial* (some countries or years are missing), *truncated* (the result was cut off by a row limit), or *empty* (nothing matched).

### 3. Make provenance machine-readable, not just human-readable

"Source: UNICEF" in a footnote does not help an AI system verify a claim. A structured citation — with the exact API URL, the indicator code, and the list of countries — lets anyone (human or machine) re-run the query and check the number.

### 4. Make identity verifiable from code to installation

If someone publishes a modified copy of this server under the same name, users have no way to tell. The defense: the server has a fixed identity (`io.github.jpazvd/unicefstats-mcp`) that is checked automatically across the source code, package registry, and runtime. The publishing pipeline uses cryptographic attestation to link the installed package back to the exact source code that produced it.

### 5. The server must constrain the AI, not trust it

Traditional APIs assume the consumer will interpret data responsibly. AI systems do not have this discipline. They will confidently present fabricated numbers if the server does not stop them. The server must actively flag gaps, attach warnings to partial results, and embed directives that the AI is trained to obey.

## 4. What Other Organizations Can Reuse

Three tiers:

**Copy directly** (no changes needed):
- The response envelope pattern (status + completeness + warnings on every response)
- Missing-entity detection (compare what was requested vs. what came back)
- The anti-fabrication directive templates
- The publishing pipeline with cryptographic attestation
- The version/identity consistency checker (a CI script that prevents accidental drift)

**Adapt** (swap in your own data source):
- The SDMX client wrapper (replace UNICEF's client with WHO's, ILO's, or your own)
- Indicator search and categorization (adapt to your taxonomy)
- The accuracy benchmark methodology (write test cases for your data)

**Not reusable** (UNICEF-specific):
- Indicator codes, category names, disaggregation dimensions
- Prompt templates that reference specific UNICEF indicators

## 5. Scaling Strategy

### Phase 1: Extract the template (near-term)
Pull the reusable components into a standalone repository — `mcp-official-stats-template` — with placeholder slots where an agency plugs in its own data source. Include the response envelope, anti-fabrication layer, provenance model, CI checks, and publishing pipeline.

### Phase 2: Pilot with 2–3 agencies (medium-term)
Test the template against other SDMX-based data warehouses:
- **WHO Global Health Observatory** — similar indicator structure, SDMX-based
- **ILO ILOSTAT** — labour statistics, SDMX REST API
- **World Bank WDI** — World Development Indicators, REST API (not SDMX, but adaptable)

Each pilot answers: Do the safety patterns generalize? What breaks?

### Phase 3: Propose standards for a UN MCP Registry (longer-term)
Once multiple agencies have working servers, propose the response envelope and provenance model as minimum requirements for a curated "UN MCP Registry" — a directory of AI-ready data servers that meet shared trust standards. This aligns with ongoing UN Data Commons efforts.

### Phase 4: National statistical offices
Extend to national statistical offices that publish via SDMX or similar APIs. The same problem applies at the national level: an AI querying Brazil's IBGE should not fabricate state-level data any more than it should fabricate country-level UNICEF data.

## 6. Next Features, Ranked by Impact

1. **Uncertainty metadata.** Where the source provides confidence intervals, expose them. An AI that says "child mortality in Nigeria is 114 per 1,000 (95% CI: 81–166)" is far more honest than one that says "114 per 1,000" as if it were exact.

2. **Pre-query coverage map.** Before an AI asks for data, let it check which countries and years actually have data for a given indicator. This prevents the request-partial-result-then-fabricate-the-rest pattern.

3. **Cross-indicator consistency flags.** When two indicators for the same country and year use different methodologies (survey-based vs. model-based), flag the conflict so the AI doesn't silently combine them.

4. **Audit logging.** Record what data was served to which AI system, so AI-generated reports can be verified after the fact.

5. **Multi-language prompts.** Extend instructions to French, Spanish, and Arabic — the other UN working languages — to reduce English-centric bias.

6. **Federated cross-agency queries.** Let one query pull comparable indicators from UNICEF and WHO simultaneously, with explicit provenance for each data point.

## 7. Recommendations

**For the MCP ecosystem:**
- Establish a minimum metadata standard for MCP servers that serve official or authoritative data. The `server.json` format used here — with provenance, verification, and data source fields — is a working starting point.
- Create a "trusted data" tier in the MCP registry for servers that implement structured status, provenance, and anti-fabrication safeguards.

**For UN agencies:**
- Treat AI data interfaces as data governance decisions, not just technical projects. Choosing what completeness labels to attach, what warnings to emit, and what directives to embed are policy choices that affect how millions of AI-generated outputs represent your data.
- Measure whether AI systems actually use your data correctly. Without a benchmark like EQA, there is no evidence that safeguards work.
- Coordinate on a shared response format so that AI systems querying multiple UN sources get consistent signals about what is complete and what is missing.

**For this project:**
- Publish the template (Phase 1) as a standalone open-source repository, documented for data engineers at statistical offices who may not have MCP experience.
- Seek review from UNICEF's data governance team on the anti-fabrication approach.
- Submit the EQA methodology and architecture to a relevant forum (e.g., UN World Data Forum, IAOS conference) for peer review.

---

## References

- Azevedo, J. P. (2025). *unicefstats-mcp: UNICEF Statistics MCP Server.* GitHub. https://github.com/jpazvd/unicefstats-mcp
- Model Context Protocol Specification. https://spec.modelcontextprotocol.io/
- UNICEF Data Warehouse. https://data.unicef.org/
- SDMX REST API v2.1. https://sdmx.data.unicef.org/
- UN Fundamental Principles of Official Statistics. https://unstats.un.org/unsd/dnss/gp/fundprinciples.aspx
