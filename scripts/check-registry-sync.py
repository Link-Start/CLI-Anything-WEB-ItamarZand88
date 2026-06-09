#!/usr/bin/env python3
"""Guard against drift between registry.json, the generated CLI directories on
disk, and the CLI counts quoted in the docs.

This is the check that would have caught `youtube`/`hackernews` being absent
from registry.json while present on disk, and the stale "10 CLIs" claims in
QUICKSTART.md / CONTRIBUTING.md.

Run from the repo root:

    python scripts/check-registry-sync.py

Exit code 0 when everything is in sync, 1 otherwise.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY = REPO_ROOT / "registry.json"

# Repo-root directories that are not generated CLIs.
NON_CLI_DIRS = {
    "assets", "docs", "scripts", "cli-anything-web-plugin",
    ".git", ".github", ".claude", ".claude-plugin", ".playwright",
}


def discover_cli_dirs() -> dict[str, Path]:
    """Map directory name -> agent-harness path for every CLI on disk."""
    found: dict[str, Path] = {}
    for child in sorted(REPO_ROOT.iterdir()):
        if not child.is_dir() or child.name in NON_CLI_DIRS or child.name.startswith("."):
            continue
        if (child / "agent-harness" / "cli_web").is_dir():
            found[child.name] = child / "agent-harness"
    return found


def doc_count_claims() -> list[tuple[str, int, str]]:
    """Find 'N CLIs' / 'N generated CLIs' / 'currently have N' claims in docs.

    Returns (file, claimed_count, line_text) tuples.
    """
    pat = re.compile(r"\b(\d{1,3})\s+(?:generated\s+)?CLIs\b|currently have\s+(\d{1,3})\b")
    claims: list[tuple[str, int, str]] = []
    for doc in ("README.md", "QUICKSTART.md", "CONTRIBUTING.md"):
        path = REPO_ROOT / doc
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            m = pat.search(line)
            if m:
                n = int(m.group(1) or m.group(2))
                claims.append((doc, n, line.strip()))
    return claims


def main() -> int:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    # The directory field's first path segment is the on-disk directory name.
    reg_by_dir = {c["directory"].split("/", 1)[0]: c for c in registry["clis"]}
    disk = discover_cli_dirs()

    errors: list[str] = []

    for name in sorted(set(disk) - set(reg_by_dir)):
        errors.append(f"CLI '{name}/' exists on disk but is NOT in registry.json")
    for name in sorted(set(reg_by_dir) - set(disk)):
        errors.append(f"registry.json lists directory '{name}/' but it does not exist on disk")

    # Validate each registry entry's declared paths actually resolve.
    for entry in registry["clis"]:
        harness = REPO_ROOT / entry["directory"]
        if not harness.is_dir():
            errors.append(f"{entry['name']}: directory '{entry['directory']}' not found")
            continue
        pkg = harness / "cli_web" / entry["namespace"].split(".", 1)[1]
        if not pkg.is_dir():
            errors.append(
                f"{entry['name']}: namespace package '{pkg.relative_to(REPO_ROOT)}' not found"
            )

    expected = len(disk)
    if len(registry["clis"]) != expected:
        errors.append(
            f"registry.json has {len(registry['clis'])} entries but {expected} CLI dirs exist"
        )

    # Docs should quote the real count.
    for doc, claimed, line in doc_count_claims():
        if claimed != expected:
            errors.append(f"{doc}: claims {claimed} CLIs but {expected} exist  ->  {line!r}")

    if errors:
        for e in errors:
            print(f"ERROR {e}")
        print(f"\n✗ registry sync check failed: {len(errors)} error(s)")
        return 1
    print(f"✓ registry in sync: {expected} CLIs on disk match registry.json and docs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
