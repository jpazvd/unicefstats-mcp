#!/usr/bin/env python3
"""Check that version strings are consistent across all project files.

Exits with code 1 if any version mismatch is found.

Checked locations:
  - pyproject.toml        [project] version
  - server.json           version + packages[].version
  - src/unicefstats_mcp/__init__.py   __version__
  - src/unicefstats_mcp/server.py     FastMCP(version=...)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


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


def main() -> int:
    versions = extract_versions()

    print("Version consistency check")
    print("=" * 50)

    found_values = set()
    errors = []

    for location, version in versions.items():
        status = version or "NOT FOUND"
        print(f"  {location}: {status}")
        if version:
            found_values.add(version)
        else:
            errors.append(f"  MISSING: {location}")

    print()

    if len(found_values) == 0:
        print("ERROR: No version strings found.")
        return 1
    elif len(found_values) > 1:
        # No "canonical" anchor: string max mis-ranks "0.10.0" < "0.9.0".
        print(f"ERROR: Inconsistent versions found: {sorted(found_values)}")
        for location, version in versions.items():
            if version:
                errors.append(f"  {location} = {version}")
        for e in errors:
            print(e)
        return 1
    else:
        canonical = found_values.pop()
        print(f"OK: All versions consistent at {canonical}")
        if errors:
            print("\nWarnings:")
            for e in errors:
                print(e)
        return 0


if __name__ == "__main__":
    sys.exit(main())
