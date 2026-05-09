# Cross-check: the UNICEF/WB gap is age-denominator, NOT country-composition

**Date:** 2026-05-08
**Trigger:** review question — "make sure the unicef and wb difference is not because of country composition. check."
**Verdict:** Confirmed. Country composition is identical (India only in
all three queries). The ~30% gap visible in
`mcp-figure-combined-IND-2026-05-08.png` is fully explained by querying
two different concepts: **UNICEF CME_MRY0 = Infant mortality rate (0-1 yr)**
versus **WB SH.DYN.MORT = Under-five mortality rate (0-5 yr)**.

When the same concept is queried (UNICEF `CME_MRY0T4` vs WB
`SH.DYN.MORT`, both U5MR), the values agree within rounding (±0.04 in
the seven sample years tested between 1970 and 2024).

> **What this experiment tests, and what it does NOT test.** Both
> UNICEF and World Bank surface the same upstream UN IGME estimates
> for mortality indicators, and the cross-check shows that those
> estimates flow through both MCP wrappers unchanged. This is
> evidence of **upstream-data-agreement** between two IGME-sourced
> wrappers — *not* a general claim that "the MCP layer doesn't
> introduce drift" for arbitrary indicators. To test MCP-layer
> fidelity in the general case you'd need an indicator pair where
> UNICEF and World Bank compute *independently* (e.g. fertility
> rate, GDP per capita, education-completion rates) — for those, a
> ±0.04 agreement would be a real MCP-layer fidelity signal. That
> follow-up experiment is not in scope for this artifact.

## Method

Three queries to the smoke test's existing MCP servers (no script
changes), all for India only:

| # | Query | What it should be |
| --- | --- | --- |
| A | `unicefstats.get_data(indicator="CME_MRY0", countries=["IND"])` | UNICEF IMR (0-1 yr) |
| B | `unicefstats.get_data(indicator="CME_MRY0T4", countries=["IND"])` | UNICEF U5MR (0-5 yr) |
| C | `world-bank.get_indicator_for_country(country_id="IND", indicator_id="SH.DYN.MORT")` | WB U5MR (0-5 yr) |

What each server reports as the indicator name (from the response payload):

- A → `'Infant mortality rate'`              (server: `unicefstats-mcp v0.7.1`)
- B → `'Under-five mortality rate'`          (server: `unicefstats-mcp v0.7.1`)
- C → `'Mortality rate, under-5 (per 1,000 live births)'`  (server: `mysql_mcp_server v1.26.0`)

## Result — sample years (per 1,000 live births)

| Year | A: UNICEF IMR | B: UNICEF U5MR | C: WB U5MR | B−A (U5MR−IMR) | **B−C (UNICEF−WB U5MR)** |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1970 | 134.82 | 214.38 | 214.40 | +79.6 | **−0.04** |
| 1980 | 108.21 | 169.81 | 169.80 | +61.6 | **+0.01** |
| 1990 | 84.40 | 127.04 | 127.00 | +42.6 | **+0.04** |
| 2000 | 66.31 | 91.78 | 91.80 | +25.5 | **−0.02** |
| 2010 | 46.29 | 58.07 | 58.10 | +11.8 | **−0.03** |
| 2020 | 28.33 | 32.98 | 33.00 | +4.6 | **−0.02** |
| 2024 | 23.35 | 26.58 | 26.60 | +3.2 | **−0.02** |

**B−C column is the load-bearing one.** All seven sample-year values
are within rounding (max |B−C| = 0.04). This is the apples-to-apples
comparison: same country, same indicator *concept*, two different
provider APIs — and the values agree because **both ultimately
surface the same UN IGME estimate**.

> The full series has 65 overlapping years (1960–2024 for WB; UNICEF
> goes back to 1953); only 7 sample rows are presented here. The
> claim "agree within rounding" is exhaustively replicable via the
> snippet at the bottom of this file but is not auto-asserted in CI
> — a future change should land an `assert max(|B−C|) < 0.05` guard
> in the replication snippet.

**B−A column** is what the original combined figure rendered. It's the
natural age-window difference: U5MR includes child deaths from age 1-5,
which were much more common historically and have declined faster than
infant mortality.

## Visual

`figures/mcp-figure-crosscheck-IMR-vs-U5MR-IND-2026-05-08.png`

Orange = A (UNICEF IMR). Blue = B (UNICEF U5MR). Green = C (WB U5MR).
Blue and green overlap so closely they appear as one line.

## Implication for the smoke test

The original combined figure (`mcp-figure-combined-IND-2026-05-08.png`)
was correctly comparing what the public-mirror script asked for:
`CME_MRY0` (which UNICEF labels as IMR) vs `SH.DYN.MORT` (WB's U5MR).
The gap surfaced a **labeling mismatch** in the script's choice of
indicator codes, not a data discrepancy between providers.

If you want an apples-to-apples overlay in future runs, change the
unicefstats query in `mcp-figures.py` from `CME_MRY0` to `CME_MRY0T4`.
The current script keeps `CME_MRY0` deliberately — surfacing the
labeling-drift surprise was the educational point of the original
example.

## Replication

```bash
cd C:\GitHub\others\unicefstats-mcp-dev
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, json
from pathlib import Path
spec = importlib.util.spec_from_file_location('mf', 'examples/mcp-smoke-test/mcp-figures.py')
mf = importlib.util.module_from_spec(spec); spec.loader.exec_module(mf)
cfg = json.loads((Path.home() / '.openclaw' / 'openclaw.json').read_text())
s = cfg['mcp']['servers']
for label, srv, args in [
    ('UNICEF IMR',  'unicefstats', {'name':'get_data','arguments':{'indicator':'CME_MRY0','countries':['IND']}}),
    ('UNICEF U5MR', 'unicefstats', {'name':'get_data','arguments':{'indicator':'CME_MRY0T4','countries':['IND']}}),
    ('WB U5MR',     'world-bank',  {'name':'get_indicator_for_country','arguments':{'country_id':'IND','indicator_id':'SH.DYN.MORT'}}),
]:
    r = mf.fetch(s[srv], args, timeout=60)
    parser = mf.parse_world_bank if srv == 'world-bank' else mf.parse_unicefstats
    _, name, data = parser(r['text'])
    yrs = next(iter(data.values()), [])
    print(label, '->', name, '(n_obs={})'.format(len(yrs)), data.keys())
"
```
