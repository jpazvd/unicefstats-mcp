---
name: Bug Report
about: Report incorrect data, tool errors, or unexpected behavior
title: "[BUG] "
labels: bug
assignees: ''
---

## Describe the bug

A clear description of what went wrong.

## To reproduce

1. Tool called: `get_data(...)` / `search_indicators(...)` / ...
2. Parameters used:
   ```json
   {
     "indicator": "...",
     "countries": ["..."],
     "start_year": ...
   }
   ```
3. What happened:
4. What you expected:

## Environment

- Python version:
- unicefstats-mcp version:
- MCP client (Claude Code / Cursor / other):
- OS:

## Response received

```json
(paste the tool response here)
```

## Additional context

- Is the data correct on [data.unicef.org](https://data.unicef.org/)?
- Does the same query work with the `unicefdata` Python package directly?
