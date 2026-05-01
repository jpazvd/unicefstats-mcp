#!/usr/bin/env python3
"""Validate version, identity, and doc-vs-code consistency across project files.

Exits with code 1 if any check fails.

Checks (deterministic, always run):
  1. Version present in all canonical locations
  2. All versions are identical
  3. Version follows semantic versioning (MAJOR.MINOR.PATCH with optional pre-release)
  6. Identity consistency: author name, GitHub handle, MCP namespace, and repo URL
     are consistent across pyproject.toml, server.json, and server.py
  7. Tool-count drift: README claim + server.json `tools` list ≡ count of
     `@mcp.tool()` decorators in server.py
  8. Manifest packages[] sanity: known registryType, identifier present,
     version matches canonical
  9. Resource-count drift: server.json `resources` list ≡ count of
     `@mcp.resource()` decorators in server.py (symmetric to check #7)
 10. Publisher-vocab consistency: get_server_metadata().publisher block,
     server.json provenance.institutional_affiliation, and PROVENANCE.md
     §2 Ownership row use the same vocabulary. Catches mid-rename drift
     (e.g. PR #19's `affiliation` → `status` rename was incomplete:
     server.py used the new key while server.json + PROVENANCE.md still
     held the old vocabulary).
 11. No `internal/` links in public docs: examples/*.md and synced root
     .md files must not reference `internal/` paths (which the
     sync-to-public workflow excludes). Catches broken-link regressions
     in the public mirror (e.g. PR #20 review).

Optional checks (gated by flags):
  4. If --check-tag is passed, validates that the git tag matches the package version
  5. If --check-pypi is passed, validates that the version is not already published

Canonical locations:
  - pyproject.toml        [project] version
  - server.json           version + packages[].version + tools[]
  - src/unicefstats_mcp/__init__.py   __version__
  - src/unicefstats_mcp/server.py     FastMCP(version=...) + @mcp.tool() decorators
  - README.md             tool-count claim in the comparison table
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# PEP 440 compatible semver: MAJOR.MINOR.PATCH with optional pre-release/dev
SEMVER_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<pre>[a-zA-Z0-9]+(?:\.[a-zA-Z0-9]+)*))?"
    r"(?:\.(?P<dev>dev\d+))?$"
)


def extract_versions() -> dict[str, str | None]:
    """Extract version strings from all canonical locations."""
    versions: dict[str, str | None] = {}

    # pyproject.toml
    pyproject = ROOT / "pyproject.toml"
    if pyproject.exists():
        content = pyproject.read_text(encoding="utf-8")
        m = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
        versions["pyproject.toml"] = m.group(1) if m else None
    else:
        versions["pyproject.toml"] = None

    # server.json (top-level version + each package version)
    server_json = ROOT / "server.json"
    if server_json.exists():
        data = json.loads(server_json.read_text(encoding="utf-8"))
        versions["server.json (version)"] = data.get("version")
        for i, pkg in enumerate(data.get("packages", [])):
            v = pkg.get("version")
            if v:
                versions[f"server.json (packages[{i}].version)"] = v
    else:
        versions["server.json"] = None

    # __init__.py
    init = ROOT / "src" / "unicefstats_mcp" / "__init__.py"
    if init.exists():
        m = re.search(r'__version__\s*=\s*"([^"]+)"', init.read_text(encoding="utf-8"))
        versions["__init__.py"] = m.group(1) if m else None
    else:
        versions["__init__.py"] = None

    # server.py FastMCP constructor
    server = ROOT / "src" / "unicefstats_mcp" / "server.py"
    if server.exists():
        content = server.read_text(encoding="utf-8")
        m = re.search(r'FastMCP\([^)]*version="([^"]+)"', content, re.DOTALL)
        versions["server.py (FastMCP)"] = m.group(1) if m else None
    else:
        versions["server.py"] = None

    return versions


def check_consistency(versions: dict[str, str | None]) -> tuple[str | None, list[str]]:
    """Return (canonical_version, errors)."""
    errors: list[str] = []
    found_values: set[str] = set()

    for location, version in versions.items():
        if version:
            found_values.add(version)
        else:
            errors.append(f"MISSING: {location}")

    if len(found_values) == 0:
        errors.append("No version strings found in any location")
        return None, errors
    elif len(found_values) > 1:
        # No canonical anchor: string max mis-ranks "0.10.0" < "0.9.0".
        errors.append(f"Inconsistent versions: {sorted(found_values)}")
        return None, errors

    return found_values.pop(), errors


def check_identity() -> list[str]:
    """Validate identity consistency across project files.

    Checks that the canonical author name, GitHub handle, MCP namespace,
    and repository URL are consistent across pyproject.toml, server.json,
    and the get_server_metadata() tool in server.py.
    """
    errors: list[str] = []

    CANONICAL_AUTHOR = "Joao Pedro Azevedo"
    CANONICAL_GITHUB = "jpazvd"
    CANONICAL_MCP_NAME = "io.github.jpazvd/unicefstats-mcp"
    CANONICAL_REPO = "https://github.com/jpazvd/unicefstats-mcp"

    # pyproject.toml author
    pyproject = ROOT / "pyproject.toml"
    if pyproject.exists():
        content = pyproject.read_text(encoding="utf-8")
        authors_idx = content.find("authors")
        if authors_idx == -1:
            errors.append(
                "pyproject.toml: [project].authors not found — check_identity cannot validate"
            )
        else:
            m = re.search(r'name\s*=\s*"([^"]+)"', content[authors_idx:])
            if not m:
                errors.append(
                    "pyproject.toml: could not parse author name from authors block"
                )
            elif m.group(1) != CANONICAL_AUTHOR:
                errors.append(
                    f"pyproject.toml author is '{m.group(1)}', expected '{CANONICAL_AUTHOR}'"
                )

    # server.json author + name
    server_json = ROOT / "server.json"
    if server_json.exists():
        data = json.loads(server_json.read_text(encoding="utf-8"))
        sj_name = data.get("name", "")
        if sj_name != CANONICAL_MCP_NAME:
            errors.append(f"server.json name is '{sj_name}', expected '{CANONICAL_MCP_NAME}'")
        author = data.get("author", {})
        if author.get("name") != CANONICAL_AUTHOR:
            errors.append(
                f"server.json author.name is '{author.get('name')}', "
                f"expected '{CANONICAL_AUTHOR}'"
            )
        if author.get("github") != CANONICAL_GITHUB:
            errors.append(
                f"server.json author.github is '{author.get('github')}', "
                f"expected '{CANONICAL_GITHUB}'"
            )
        repo_url = data.get("repository", {}).get("url", "")
        if repo_url != CANONICAL_REPO:
            errors.append(
                f"server.json repository.url is '{repo_url}', expected '{CANONICAL_REPO}'"
            )

    # server.py get_server_metadata publisher block
    server_py = ROOT / "src" / "unicefstats_mcp" / "server.py"
    if server_py.exists():
        content = server_py.read_text(encoding="utf-8")
        m = re.search(r'"publisher":\s*\{[^}]*"name":\s*"([^"]+)"', content)
        if m and m.group(1) != CANONICAL_AUTHOR:
            errors.append(
                f"server.py publisher.name is '{m.group(1)}', expected '{CANONICAL_AUTHOR}'"
            )
        m = re.search(r'"publisher":\s*\{[^}]*"github":\s*"([^"]+)"', content)
        if m and m.group(1) != CANONICAL_GITHUB:
            errors.append(
                f"server.py publisher.github is '{m.group(1)}', expected '{CANONICAL_GITHUB}'"
            )
        m = re.search(r'"registry_identity":\s*"([^"]+)"', content)
        if m and m.group(1) != CANONICAL_MCP_NAME:
            errors.append(
                f"server.py registry_identity is '{m.group(1)}', expected '{CANONICAL_MCP_NAME}'"
            )

    return errors


def check_semver(version: str) -> list[str]:
    """Validate semantic versioning format."""
    if SEMVER_RE.match(version):
        return []
    return [f"Version '{version}' does not follow semantic versioning (MAJOR.MINOR.PATCH)"]


def check_tag(version: str, tag: str) -> list[str]:
    """Validate that the git tag matches the package version."""
    expected = f"v{version}"
    if tag == expected:
        return []
    return [f"Git tag '{tag}' does not match expected 'v{version}'"]


def check_changelog(version: str) -> list[str]:
    """Validate that CHANGELOG.md has an entry for this version."""
    changelog = ROOT / "CHANGELOG.md"
    if not changelog.exists():
        return ["CHANGELOG.md not found"]
    content = changelog.read_text(encoding="utf-8")
    pattern = rf"## \[{re.escape(version)}\]"
    if re.search(pattern, content):
        return []
    return [f"CHANGELOG.md has no entry for version [{version}]"]


def check_pypi(version: str) -> list[str]:
    """Check if version already exists on PyPI (requires network).

    Uses the PyPI JSON API for an exact key match against published releases.
    Fails closed on network or unexpected HTTP errors — a release gate that
    can't reach PyPI must not silently allow a duplicate upload.
    """
    import urllib.error
    import urllib.request

    url = "https://pypi.org/pypi/unicefstats-mcp/json"
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            data = json.loads(response.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            # Project doesn't exist on PyPI yet — first publish is fine.
            return []
        return [f"PyPI check failed: HTTP {e.code} for {url}"]
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return [f"PyPI check failed: {e}"]

    if version in data.get("releases", {}):
        return [f"Version {version} already exists on PyPI — bump version before publishing"]
    return []


def check_tool_count() -> list[str]:
    """Validate that tool counts claimed in README and listed in server.json
    match the actual @mcp.tool()-decorated function count in server.py.

    This catches a specific class of doc-vs-code drift: the README or
    server.json gets stale when a tool is added or removed without updating
    the documentation.
    """
    errors: list[str] = []

    server_py = ROOT / "src" / "unicefstats_mcp" / "server.py"
    if not server_py.exists():
        errors.append("server.py: not found — cannot count @mcp.tool() decorators")
        return errors

    actual = len(re.findall(r"@mcp\.tool\(\s*\)", server_py.read_text(encoding="utf-8")))
    if actual == 0:
        errors.append("server.py: no @mcp.tool() decorators found")
        return errors

    # server.json `tools` field
    server_json = ROOT / "server.json"
    if server_json.exists():
        data = json.loads(server_json.read_text(encoding="utf-8"))
        listed = data.get("tools", [])
        if isinstance(listed, list) and len(listed) != actual:
            errors.append(
                f"server.json tools[] has {len(listed)} entries; "
                f"server.py has {actual} @mcp.tool() decorators"
            )

    # README claim — only fire on the unicefstats-mcp self-row, identified by
    # the `search → metadata` workflow signature in the same line. Other
    # comparison rows (FRED MCP, World Bank MCP, etc.) are skipped.
    readme = ROOT / "README.md"
    if readme.exists():
        content = readme.read_text(encoding="utf-8")
        for line_no, line in enumerate(content.splitlines(), 1):
            m = re.match(r"\s*\|\s*\*\*Tools\*\*\s*\|\s*(\d+)\s*\(([^|]*)", line)
            if not m:
                continue
            claimed = int(m.group(1))
            description = m.group(2).lower()
            # Heuristic: the unicefstats-mcp row mentions `search` and either
            # `metadata` or `data` (the project's own workflow keywords).
            is_unicefstats_row = (
                "search" in description
                and ("metadata" in description or "data" in description)
            )
            if is_unicefstats_row and claimed != actual:
                errors.append(
                    f"README.md:{line_no} claims {claimed} tools "
                    f"(unicefstats-mcp row); server.py has {actual}"
                )

    return errors


def check_resource_count() -> list[str]:
    """Validate that server.json `resources` list matches the actual
    `@mcp.resource()`-decorated function count in server.py.

    Symmetric to check_tool_count(): catches the same class of doc-vs-code
    drift for resources. PR #19 added two new resources
    (`unicef://system-prompt`, `unicef://context`) and the manifest was
    extended manually — without this check, future additions could land
    in code while the manifest stays stale.
    """
    errors: list[str] = []

    server_py = ROOT / "src" / "unicefstats_mcp" / "server.py"
    if not server_py.exists():
        errors.append("server.py: not found — cannot count @mcp.resource() decorators")
        return errors

    actual = len(re.findall(r'@mcp\.resource\("[^"]+"\s*\)', server_py.read_text(encoding="utf-8")))
    if actual == 0:
        errors.append("server.py: no @mcp.resource() decorators found")
        return errors

    server_json = ROOT / "server.json"
    if server_json.exists():
        data = json.loads(server_json.read_text(encoding="utf-8"))
        listed = data.get("resources", [])
        if isinstance(listed, list) and len(listed) != actual:
            errors.append(
                f"server.json resources[] has {len(listed)} entries; "
                f"server.py has {actual} @mcp.resource() decorators"
            )

    return errors


def check_no_internal_links_in_public_docs() -> list[str]:
    """Validate that public-facing docs don't link to `internal/` paths.

    The sync-to-public workflow whitelists `examples/`, root-level Markdown
    files (README, CHANGELOG, PROVENANCE, RELEASE, etc.), and `src/` — but
    excludes `internal/`. Any link from a synced doc to an `internal/` path
    will 404 for users browsing the public mirror. This caught a real
    regression on PR #20 where examples/LANDSCAPE.md linked to
    internal/LANDSCAPE_REFERENCE.md via the public-repo URL.

    Scans examples/*.md plus root-level synced .md files for two patterns:
      1. Markdown link target ](internal/...)
      2. Absolute URL pointing to jpazvd/unicefstats-mcp/.../internal/...
         (the public mirror; matches negative-lookahead to allow
         jpazvd/unicefstats-mcp-dev/.../internal/, which is the private
         dev repo and IS a valid reference for this project).
    """
    errors: list[str] = []

    public_files: list[Path] = []
    examples_dir = ROOT / "examples"
    if examples_dir.exists():
        public_files.extend(sorted(examples_dir.glob("*.md")))
    for fname in [
        "README.md", "CHANGELOG.md", "PROVENANCE.md", "RELEASE.md",
        "CONCEPT_NOTE.md", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md", "SECURITY.md",
    ]:
        path = ROOT / fname
        if path.exists():
            public_files.append(path)

    md_link_pattern = re.compile(r"\]\(internal/")
    public_url_pattern = re.compile(
        r"github\.com/jpazvd/unicefstats-mcp(?!-dev)/[^)]*?/internal/",
        re.IGNORECASE,
    )

    for path in public_files:
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as e:
            errors.append(f"{path.relative_to(ROOT)}: read failed ({e})")
            continue

        for line_no, line in enumerate(content.splitlines(), 1):
            if md_link_pattern.search(line):
                errors.append(
                    f"{path.relative_to(ROOT)}:{line_no} links to internal/ "
                    f"path — will 404 in public mirror (sync-to-public.yml "
                    f"excludes internal/)"
                )
            if public_url_pattern.search(line):
                errors.append(
                    f"{path.relative_to(ROOT)}:{line_no} URL points to "
                    f"jpazvd/unicefstats-mcp/.../internal/ — that path does "
                    f"not exist in the public mirror"
                )

    return errors


def check_publisher_vocab_consistency() -> list[str]:
    """Validate that publisher / institutional-status vocabulary is consistent
    across server.py, server.json, and PROVENANCE.md.

    Background: PR #19 (v0.5.0) renamed the `get_server_metadata()` publisher
    field from `affiliation` → `status` and changed the value from
    "Independent researcher (not an official UNICEF product)" to
    "Experimental — not an official UNICEF product". The rename was applied
    to server.py only; server.json kept `institutional_affiliation` (old key)
    with the new value, and PROVENANCE.md kept the old key AND old value
    ("Institutional affiliation | Independent researcher"). The whole point
    of get_server_metadata() (per README §"How to Verify This MCP") is
    cross-source identity verification — three vocabularies break that
    invariant.

    This check defines the canonical value (CANONICAL_PUBLISHER_VALUE) and
    verifies all three files carry it. Vocabulary update procedure: bump
    CANONICAL_PUBLISHER_VALUE here, then update server.py, server.json,
    PROVENANCE.md to match. The check fires until all four agree.
    """
    errors: list[str] = []

    # The canonical publisher status string. Update this when the project's
    # institutional posture changes; then update the three files below to match.
    CANONICAL_PUBLISHER_VALUE = "Experimental — not an official UNICEF product"

    # 1. server.py — the publisher block in get_server_metadata().
    #    Look for the value somewhere inside the publisher dict. The key name
    #    can be `status` (current canonical) or `affiliation` (legacy); we
    #    intentionally don't enforce the key name here so renames can land in
    #    one place and propagate via the value.
    server_py = ROOT / "src" / "unicefstats_mcp" / "server.py"
    if server_py.exists():
        content = server_py.read_text(encoding="utf-8")
        # Match the publisher block and check the canonical value appears in it.
        m = re.search(r'"publisher":\s*\{([^}]+)\}', content, re.DOTALL)
        if not m:
            errors.append("server.py: publisher block not found in get_server_metadata()")
        elif CANONICAL_PUBLISHER_VALUE not in m.group(1):
            errors.append(
                f"server.py publisher block does not contain canonical value "
                f"'{CANONICAL_PUBLISHER_VALUE}' — possible rename drift"
            )

    # 2. server.json — provenance.institutional_affiliation (legacy key kept
    #    for now; check is on the value).
    server_json = ROOT / "server.json"
    if server_json.exists():
        data = json.loads(server_json.read_text(encoding="utf-8"))
        provenance = data.get("provenance", {})
        # Accept either `status` or `institutional_affiliation` as the key —
        # whichever holds the canonical value.
        candidate_keys = ["status", "institutional_affiliation", "affiliation"]
        found = False
        for key in candidate_keys:
            if provenance.get(key) == CANONICAL_PUBLISHER_VALUE:
                found = True
                break
        if not found:
            actual_values = {
                k: provenance.get(k) for k in candidate_keys if k in provenance
            }
            errors.append(
                f"server.json provenance: canonical publisher value "
                f"'{CANONICAL_PUBLISHER_VALUE}' not found under any of "
                f"{candidate_keys}; actual: {actual_values}"
            )

    # 3. PROVENANCE.md — §2 Ownership and Status row should reflect the
    #    same canonical posture. We require the EXACT CANONICAL_PUBLISHER_VALUE
    #    string to appear (substring matches like "Experimental" alone would
    #    let drift through if the canonical posture changes), AND the legacy
    #    "Independent researcher" string must not appear.
    provenance_md = ROOT / "PROVENANCE.md"
    if provenance_md.exists():
        content = provenance_md.read_text(encoding="utf-8")
        # The exact canonical value must appear at least once.
        if CANONICAL_PUBLISHER_VALUE not in content:
            errors.append(
                f"PROVENANCE.md: does not contain the exact canonical "
                f"posture string '{CANONICAL_PUBLISHER_VALUE}' — possible "
                f"stale vocabulary or drift from the canonical value"
            )
        # The legacy value must not appear (would indicate an incomplete rename).
        if "Independent researcher" in content:
            # Find line numbers for actionable error.
            lines = [
                str(i + 1)
                for i, line in enumerate(content.splitlines())
                if "Independent researcher" in line
            ]
            errors.append(
                f"PROVENANCE.md: legacy vocabulary 'Independent researcher' still "
                f"present at line(s) {','.join(lines)} — should be replaced with "
                f"the canonical posture '{CANONICAL_PUBLISHER_VALUE}'"
            )

    return errors


def check_manifest_packages(version: str | None) -> list[str]:
    """Sanity-check server.json packages[] entries (deterministic).

    For each package: known registryType, identifier present, version matches
    the canonical version. Catches manifest-vs-reality drift like the dropped
    Docker entry from PR #2 (advertised an image that was never published).
    Network-level verification (PyPI duplicate, Docker registry) is gated
    behind --check-pypi via the existing check_pypi() function.
    """
    errors: list[str] = []
    server_json = ROOT / "server.json"
    if not server_json.exists():
        return errors

    data = json.loads(server_json.read_text(encoding="utf-8"))
    packages = data.get("packages", [])
    if not packages:
        errors.append("server.json: packages[] is empty")
        return errors

    KNOWN_REGISTRIES = {"pypi", "docker", "npm", "ghcr"}
    for i, pkg in enumerate(packages):
        prefix = f"server.json packages[{i}]"
        rt = pkg.get("registryType")
        if rt not in KNOWN_REGISTRIES:
            errors.append(f"{prefix}: unknown registryType {rt!r}")
        if not pkg.get("identifier"):
            errors.append(f"{prefix}: missing identifier")
        v = pkg.get("version")
        if version and v and v != version:
            errors.append(
                f"{prefix}: version {v!r} does not match canonical {version!r}"
            )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate version consistency and format")
    parser.add_argument("--check-tag", metavar="TAG", help="Validate git tag matches version")
    parser.add_argument("--check-pypi", action="store_true", help="Check if version exists on PyPI")
    parser.add_argument("--check-changelog", action="store_true", help="Check CHANGELOG.md entry")
    args = parser.parse_args()

    versions = extract_versions()

    print("Version consistency check")
    print("=" * 60)

    for location, version in versions.items():
        status = version or "NOT FOUND"
        print(f"  {location}: {status}")
    print()

    all_errors: list[str] = []

    # 1. Consistency
    canonical, errors = check_consistency(versions)
    all_errors.extend(errors)

    if canonical:
        print(f"Canonical version: {canonical}")

        # 2. Semver
        all_errors.extend(check_semver(canonical))

        # 3. Tag alignment (optional)
        if args.check_tag:
            all_errors.extend(check_tag(canonical, args.check_tag))

        # 4. Changelog entry (optional)
        if args.check_changelog:
            all_errors.extend(check_changelog(canonical))

        # 5. PyPI duplicate (optional)
        if args.check_pypi:
            all_errors.extend(check_pypi(canonical))

    # 6. Identity consistency (always runs)
    identity_errors = check_identity()
    all_errors.extend(identity_errors)

    # 7. Tool-count drift (always runs; deterministic)
    all_errors.extend(check_tool_count())

    # 8. Manifest packages[] sanity (always runs; deterministic — the
    #    PyPI / network-level check stays gated by --check-pypi above)
    all_errors.extend(check_manifest_packages(canonical))

    # 9. Resource-count drift (always runs; symmetric to check #7)
    all_errors.extend(check_resource_count())

    # 10. Publisher-vocab consistency (always runs; catches mid-rename drift
    #     across server.py, server.json, PROVENANCE.md — see PR #19 regression)
    all_errors.extend(check_publisher_vocab_consistency())

    # 11. No `internal/` links in public-facing docs (always runs; catches
    #     broken-link regressions in the public mirror — see PR #20 review)
    all_errors.extend(check_no_internal_links_in_public_docs())

    print()
    if all_errors:
        print("ERRORS:")
        for e in all_errors:
            print(f"  {e}")
        return 1
    else:
        print("OK: All checks passed")
        return 0


if __name__ == "__main__":
    sys.exit(main())
