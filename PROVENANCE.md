# Provenance and Trust

This document describes the data origin, ownership, distribution pipeline, and verification steps for `unicefstats-mcp`. It is intended for users, auditors, and downstream systems that need to assess the trustworthiness of data served through this MCP.

## 1. Data Origin

All statistical data served by this MCP originates from the **UNICEF Data Warehouse**, accessed via the SDMX REST API:

| Property | Value |
|---|---|
| **Data provider** | UNICEF (United Nations Children's Fund) |
| **API endpoint** | `https://sdmx.data.unicef.org/ws/public/sdmxapi/rest` |
| **Protocol** | SDMX REST v2.1 |
| **Authentication** | None required (public API) |
| **Data coverage** | 790+ child-focused indicators, 200+ countries |
| **Update frequency** | Varies by indicator; IGME mortality estimates are annual, survey-based indicators (DHS/MICS) update every 3-5 years |

The MCP does **not** store, cache, or modify the underlying data. Every `get_data()` call results in a live query to the UNICEF SDMX API. The `unicefdata` Python package handles the SDMX protocol details.

### Data pipeline

```
UNICEF Data Warehouse (primary source)
  --> SDMX REST API (public, read-only)
    --> unicefdata Python package (SDMX client)
      --> unicefstats-mcp (MCP protocol layer)
        --> AI assistant (Claude, Cursor, Copilot, etc.)
```

No transformation is applied to the data values. The MCP reformats the output for LLM consumption (compact/full JSON) and adds metadata (summaries, pagination, tips), but the underlying numbers are passed through as received from the API.

## 2. Ownership and Status

| Property | Value |
|---|---|
| **Publisher / maintainer** | Joao Pedro Azevedo ([`jpazvd`](https://github.com/jpazvd)) |
| **Status** | Experimental — not an official UNICEF product |
| **Relationship to UNICEF** | The maintainer is affiliated with UNICEF but this is **not an official UNICEF product** |
| **License** | MIT |

This MCP server is an experimental project. It does not represent the views or policies of UNICEF. The "UNICEF" in the name refers to the data source, not to institutional endorsement.

### What this means for users

- **Data authority**: The data comes from UNICEF's official API, but the MCP's interpretation layer (formatting, summaries, tips) is not UNICEF-reviewed.
- **No warranty**: The software is provided "as is". See the disclaimer in [README.md](README.md).
- **Citation**: When citing data obtained through this MCP, cite the UNICEF Data Warehouse as the primary source, not this MCP server.

## 3. Distribution Pipeline

### Source code

| Channel | URL | Status |
|---|---|---|
| **Canonical repository** | [github.com/jpazvd/unicefstats-mcp](https://github.com/jpazvd/unicefstats-mcp) | Primary |
| **Development repository** | [github.com/jpazvd/unicefstats-mcp-dev](https://github.com/jpazvd/unicefstats-mcp-dev) | Internal |

### Package distribution

| Channel | URL | Publishing method |
|---|---|---|
| **PyPI** | [pypi.org/project/unicefstats-mcp](https://pypi.org/project/unicefstats-mcp/) | GitHub Actions via [Trusted Publishing](https://docs.pypi.org/trusted-publishers/) (OIDC) |
| **Docker** | `docker build` from source | Manual |

### Publishing integrity

- All PyPI releases are built and published exclusively by GitHub Actions using **PyPI Trusted Publishing** (OIDC). No long-lived API tokens are used.
- The publishing workflow ([`.github/workflows/publish.yml`](.github/workflows/publish.yml)) triggers only on version tags (`v*`).
- PyPI attestations are available at [pypi.org/project/unicefstats-mcp/#files](https://pypi.org/project/unicefstats-mcp/#files).

### Third-party mirrors and aggregators

This MCP may appear in third-party directories (LobeHub, Smithery, mcp.so, Glama, etc.). These listings are **not controlled by the maintainer**. Always verify against the canonical sources listed above.

## 4. Verification Steps

### For users installing the package

1. **Verify the PyPI package**:
   ```bash
   pip show unicefstats-mcp
   ```
   Check that `Home-page` points to `https://github.com/jpazvd/unicefstats-mcp`.

2. **Verify the source repository**:
   - Repository owner: [`jpazvd`](https://github.com/jpazvd)
   - Check commit history and release tags match PyPI versions.

3. **Verify release provenance**:
   - Visit [pypi.org/project/unicefstats-mcp/#files](https://pypi.org/project/unicefstats-mcp/#files).
   - Check that release files have attestations linking back to the GitHub Actions workflow.

4. **Verify version alignment**:
   ```bash
   python -c "import unicefstats_mcp; print(unicefstats_mcp.__version__)"
   ```
   Compare with the version shown on PyPI and in `server.json`.

### For MCP registry operators

- **Canonical MCP identity**: `io.github.jpazvd/unicefstats-mcp`
- **Registry metadata**: See [`server.json`](server.json) in the repository root.
- **Namespace ownership**: The `io.github.jpazvd` namespace is derived from the GitHub username `jpazvd`, which owns the canonical repository.

### Runtime verification

The `get_server_metadata()` tool returns machine-readable identity and provenance information at runtime. AI assistants can call this tool to verify they are connected to the authentic server.

## 5. Limitations and Interpretation Caveats

### Data limitations

- **Not all indicators are available for all countries or years.** Coverage varies significantly. Survey-based indicators (nutrition, education) have gaps of 3-5 years between data points.
- **Values are estimates, not census counts.** Mortality indicators (CME_*) are modeled estimates from the UN Inter-agency Group for Child Mortality Estimation (IGME). They carry uncertainty intervals not exposed by default in the compact format.
- **Disaggregation availability varies.** Not all indicators support all disaggregation dimensions (sex, age, wealth quintile, residence).

### MCP-specific limitations

- **The MCP adds a formatting layer.** Compact output (5 columns) omits disaggregation details, observation status, and confidence intervals available in the full SDMX response.
- **Row limits apply.** `get_data()` returns a maximum of 500 rows per call. Large queries require filtering or multiple calls.
- **AI interpretation is not guaranteed.** The MCP improves LLM accuracy (EQA 0.990) but does not eliminate hallucination. The LLM may fabricate data when the API returns no results (~10% T2 hallucination rate after correction).

### Principles alignment

This project aims to align with the [UN Fundamental Principles of Official Statistics](https://unstats.un.org/unsd/dnss/gp/fundprinciples.aspx), specifically:

- **Principle 1 (Relevance)**: Serving data that meets user needs via an accessible interface.
- **Principle 2 (Professional standards)**: Transparent methodology, reproducible benchmarks, source citations.
- **Principle 5 (Sources)**: Data sourced from the official UNICEF statistical system.
- **Principle 6 (Confidentiality)**: No personal or confidential data is collected or transmitted.

However, as an independent project, it operates outside UNICEF's official statistical governance framework. Users requiring authoritative data for policy decisions should verify against the [UNICEF Data Warehouse](https://data.unicef.org/) directly.
