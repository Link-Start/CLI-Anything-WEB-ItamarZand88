"""``cli-web-devkit`` — fleet tooling entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .matrix import render_matrix
from .paths import repo_root
from .registry import validate as validate_registry
from .sync import drift, resync


def _cmd_registry_validate(args: argparse.Namespace) -> int:
    problems = validate_registry(args.root)
    if problems:
        print("registry.json validation FAILED:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    print("registry.json OK")
    return 0


def _cmd_matrix(args: argparse.Namespace) -> int:
    print(render_matrix(args.root))
    return 0


def _cmd_drift(args: argparse.Namespace) -> int:
    items = drift(args.root)
    bad = [i for i in items if i.status in ("drifted", "missing")]
    for item in items:
        if args.verbose or item.status != "ok":
            detail = f"  ({item.detail})" if item.detail else ""
            print(f"{item.status.upper():9} {item.cli:24} {item.file}{detail}")
    print(f"\n{len(items) - len(bad)} ok, {len(bad)} drifted/missing")
    return 1 if bad else 0


def _cmd_resync(args: argparse.Namespace) -> int:
    changed = resync(args.root, apps=args.app or None)
    if changed:
        print(f"resynced {len(changed)} file(s):")
        for path in changed:
            print(f"  {path}")
    else:
        print("fleet already in sync")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cli-web-devkit", description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Repo root (auto-detected from cwd by default)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_reg = sub.add_parser("registry", help="Registry operations")
    reg_sub = p_reg.add_subparsers(dest="registry_command", required=True)
    p_val = reg_sub.add_parser("validate", help="Validate registry.json against the fleet")
    p_val.set_defaults(func=_cmd_registry_validate)

    p_matrix = sub.add_parser("matrix", help="Emit GitHub Actions test matrix JSON")
    p_matrix.set_defaults(func=_cmd_matrix)

    p_drift = sub.add_parser("drift", help="Detect vendored shared files diverging from canon")
    p_drift.add_argument("--verbose", action="store_true", help="Also list in-sync files")
    p_drift.set_defaults(func=_cmd_drift)

    p_resync = sub.add_parser("resync", help="Rewrite vendored shared files from canon")
    p_resync.add_argument(
        "--app",
        action="append",
        help="Limit to specific app(s); default: whole fleet + plugin copy",
    )
    p_resync.set_defaults(func=_cmd_resync)

    args = parser.parse_args(argv)
    if args.root is None:
        args.root = repo_root(Path.cwd())
    result: int = args.func(args)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
