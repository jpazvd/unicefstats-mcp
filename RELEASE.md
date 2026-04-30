# Release Process

This document describes how to publish a new version of `unicefstats-mcp` to PyPI.

## Prerequisites

- Push access to [`jpazvd/unicefstats-mcp`](https://github.com/jpazvd/unicefstats-mcp)
- PyPI Trusted Publishing configured for this repository (already set up)
- No long-lived API tokens are needed — publishing uses OIDC

## Release Checklist

### 1. Prepare the release

- [ ] **Decide version number** following [semantic versioning](https://semver.org/):
  - `MAJOR.MINOR.PATCH` (e.g., `0.5.0`)
  - MAJOR: breaking changes to tool signatures or response formats
  - MINOR: new tools, prompts, resources, or features
  - PATCH: bug fixes, documentation, internal improvements

- [ ] **Update version in all 4 locations** (must be identical):
  - `pyproject.toml` — `version = "X.Y.Z"`
  - `server.json` — top-level `"version"` AND each `packages[].version`
  - `src/unicefstats_mcp/__init__.py` — `__version__ = "X.Y.Z"`
  - `src/unicefstats_mcp/server.py` — `FastMCP(version="X.Y.Z", ...)`

- [ ] **Run version consistency check**:
  ```bash
  python scripts/check_version_consistency.py --check-changelog
  ```

- [ ] **Update CHANGELOG.md** — add a section for `[X.Y.Z]` with date and changes

- [ ] **Run full test suite**:
  ```bash
  ruff check src/ tests/
  mypy src/unicefstats_mcp/
  python -m pytest tests/ -v
  ```

### 2. Commit and tag

- [ ] **Commit version bump**:
  ```bash
  git add pyproject.toml server.json src/unicefstats_mcp/__init__.py src/unicefstats_mcp/server.py CHANGELOG.md
  git commit -m "release: vX.Y.Z"
  ```

- [ ] **Create annotated tag**:
  ```bash
  git tag -a vX.Y.Z -m "Release vX.Y.Z"
  ```

- [ ] **Push commit and tag**:
  ```bash
  git push origin main
  git push origin vX.Y.Z
  ```

### 3. Automated pipeline (hands-off)

Pushing the tag triggers the `publish.yml` workflow, which:

1. **Validates** version consistency, semver format, tag alignment, changelog entry
2. **Checks** that the version does not already exist on PyPI
3. **Builds** sdist + wheel via `python -m build`
4. **Publishes** to PyPI via Trusted Publishing (OIDC, no tokens)
5. **Verifies** the published package installs correctly from PyPI

Monitor the workflow at: `https://github.com/jpazvd/unicefstats-mcp/actions/workflows/publish.yml`

### 4. Post-release verification

- [ ] **Check PyPI**: [pypi.org/project/unicefstats-mcp](https://pypi.org/project/unicefstats-mcp/)
- [ ] **Check attestations**: [pypi.org/project/unicefstats-mcp/#files](https://pypi.org/project/unicefstats-mcp/#files)
- [ ] **Test installation**:
  ```bash
  pip install unicefstats-mcp==X.Y.Z
  python -c "import unicefstats_mcp; print(unicefstats_mcp.__version__)"
  ```

## What Can Go Wrong

| Problem | Cause | Fix |
|---|---|---|
| Workflow fails at "Validate" | Version mismatch across files | Fix all 4 locations, re-commit, delete and re-push tag |
| Workflow fails at "Check PyPI" | Version already published | Bump to next version |
| Workflow fails at "Publish" | Trusted Publishing not configured | Set up OIDC publisher at pypi.org for this repo |
| Workflow fails at "Verify" | PyPI index delay | Re-run the verify job after a few minutes |

## Deleting and Re-pushing a Tag

If you need to fix the release after tagging:

```bash
# Delete remote tag
git push origin --delete vX.Y.Z

# Delete local tag
git tag -d vX.Y.Z

# Fix, commit, re-tag, re-push
git commit -m "fix: correct version for vX.Y.Z release"
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin main
git push origin vX.Y.Z
```

## Version Locations Quick Reference

| File | Field | Example |
|---|---|---|
| `pyproject.toml` | `version = "..."` | `version = "0.4.0"` |
| `server.json` | `"version": "..."` | `"version": "0.4.0"` |
| `server.json` | `"packages[*].version"` | `"version": "0.4.0"` |
| `__init__.py` | `__version__ = "..."` | `__version__ = "0.4.0"` |
| `server.py` | `FastMCP(version="...")` | `version="0.4.0"` |
| Git tag | `vX.Y.Z` | `v0.4.0` |
