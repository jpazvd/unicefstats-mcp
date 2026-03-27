# Contributing to unicefstats-mcp

Thank you for your interest in contributing to unicefstats-mcp! This project is an experimental research prototype and we welcome contributions of all kinds — bug reports, feature requests, documentation improvements, and code.

## Getting started

### Prerequisites

- Python 3.10+
- Git

### Development setup

```bash
git clone https://github.com/jpazvd/unicefstats-mcp.git
cd unicefstats-mcp
pip install -e ".[dev,benchmark]"
```

### Running checks

Before submitting any code change, run all three:

```bash
pytest tests/ -v              # tests pass
ruff check src/ tests/        # linter clean
mypy src/unicefstats_mcp/     # type checker clean
```

## How to contribute

### Bug reports

Open an [issue](https://github.com/jpazvd/unicefstats-mcp/issues) using the **Bug Report** template. Include:

- Steps to reproduce
- Expected vs actual behavior
- Your Python version and OS
- The indicator code and country (if data-related)

### Feature requests

Open an [issue](https://github.com/jpazvd/unicefstats-mcp/issues) using the **Feature Request** template. Describe the use case, not just the solution.

### Code contributions

1. **Fork** the repository
2. **Branch** from `main` — use a descriptive name (e.g., `fix/mnch-dataflow`, `feat/add-mcp-resources`)
3. **Make your changes** — keep commits atomic and focused
4. **Run checks** — tests, linter, type checker (see above)
5. **Submit a PR** — fill out the pull request template

### Documentation

- Fix typos, improve examples, add use cases
- No PR template needed for docs-only changes
- Keep the README concise — detailed analysis belongs in `examples/RESULTS.md`

### Benchmark contributions

Run the EQA benchmark on different models and share results:

```bash
# Requires ANTHROPIC_API_KEY (or modify for other providers)
python examples/00_build_ground_truth.py
python examples/benchmark_eqa.py
```

Submit your parquet results via PR to `examples/results/` with a descriptive filename.

## Code style

### Python

- **Formatter**: `ruff format` (line length 100)
- **Linter**: `ruff check` with rules E, F, W, I, UP, B, SIM
- **Type hints**: All function signatures must have full type annotations (params + return)
- **Imports**: Use `from __future__ import annotations` in all files
- **Docstrings**: Required for public functions. Describe what the function does, not how.

### Commits

- Use [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `data:`
- One concern per commit — don't mix bug fixes with features
- Write the commit message in imperative mood ("add X", not "added X")

### Tools and responses

- Every MCP tool must return structured JSON via `ok()` or `error()` — never raise exceptions to the LLM
- Every `error()` must include a `tip` field guiding the user to a valid next step
- Input validation goes in `validators.py`, output formatting in `formatters.py`
- New tools must have tests covering: happy path, invalid input, API error, and empty result

## Priority areas

These are the highest-impact areas for contribution:

| Area | Issue | Impact |
|------|-------|--------|
| MNCH dataflow | `MNCH_CSEC` and `MNCH_BIRTH18` return EQA=0 | Fixes 2/10 benchmark indicators |
| Anti-hallucination | Adopt sdmx-mcp's `assistant_guidance` pattern | Reduces T2 hallucination from 38% |
| Test coverage | `list_countries`, `get_api_reference`, prompts untested | 3 tools with 0% coverage |
| MCP Resources | Indicator registry + country list as Resources | Reduces unnecessary tool calls |
| Formatters tests | `compute_trend`, `summarize_data` untested | Complex logic without coverage |
| Validators tests | `validate_wealth_quintile` edge cases | Validation gaps |

## Questions?

Open a [discussion](https://github.com/jpazvd/unicefstats-mcp/issues) or reach out via the issue tracker.
