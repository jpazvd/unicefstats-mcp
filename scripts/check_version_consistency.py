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
        m = re.search(r'^version\s*=\s*"([^"]+)"', pyproject.read_text(), re.MULTILINE)
        versions["pyproject.toml"] = m.group(1) if m else None
    else:
        versions["pyproject.toml"] = None

    # server.json (top-level version + each package version)
    server_json = ROOT / "server.json"
    if server_json.exists():
        data = json.loads(server_json.read_text())
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
        m = re.search(r'__version__\s*=\s*"([^"]+)"', init.read_text())
        versions["__init__.py"] = m.group(1) if m else None
    else:
        versions["__init__.py"] = None

    # server.py FastMCP constructor
    server = ROOT / "src" / "unicefstats_mcp" / "server.py"
    if server.exists():
        m = re.search(r'FastMCP\([^)]*version="([^"]+)"', server.read_text(), re.DOTALL)
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
        content = pyproject.read_text()
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
        data = json.loads(server_json.read_text())
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
        content = server_py.read_text()
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
    content = changelog.read_text()
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

    actual = len(re.findall(r"@mcp\.tool\(\s*\)", server_py.read_text()))
    if actual == 0:
        errors.append("server.py: no @mcp.tool() decorators found")
        return errors

    # server.json `tools` field
    server_json = ROOT / "server.json"
    if server_json.exists():
        data = json.loads(server_json.read_text())
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
        content = readme.read_text()
        for line_no, line in enumerate(content.splitlines(), 1):
            m = re.match(r"\s*\|\s*\*\*Tools\*\*\s*\|\s*(\d+)\s*\(([^|]*)", line)
            if not m:
                continue
            claimed = int(m.group(1))
            description = m.group(2).lower()
            # Heuristic: the unicefstats-mcp row mentions `search` and either
            # `metadata` or `data` (the project's own workflow keywords).
            if "search" in description and ("metadata" in description or "data" in description):
                if claimed != actual:
                    errors.append(
                        f"README.md:{line_no} claims {claimed} tools "
                        f"(unicefstats-mcp row); server.py has {actual}"
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

    data = json.loads(server_json.read_text())
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
