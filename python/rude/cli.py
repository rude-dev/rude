"""Command-line interface for Rude."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rude import __version__
from rude.core import CheckOptions, Linter, discover_rules, load_config, resolve_paths
from rude.core.rule import RuleBase
from rude.core.types import Diagnostic, Severity
from rude.utils import atomic_write_text

_COMMANDS = frozenset({"check", "lint", "list"})
_GLOBAL_FLAGS = frozenset({"-h", "--help", "-V", "--version"})


def main(argv: list[str] | None = None) -> int:
    raw = argv if argv is not None else sys.argv[1:]

    # Prepend "check" unless the first positional is a known subcommand
    # or all args are global flags (--version, --help)
    first_pos = next((a for a in raw if not a.startswith("-")), None)
    if first_pos not in _COMMANDS:
        if raw and set(raw).issubset(_GLOBAL_FLAGS):
            pass  # Global flags only (e.g. rude --version)
        else:
            raw = ["check", *raw]

    parser = create_parser()
    args = parser.parse_args(raw)

    if args.command in ("check", "lint"):
        return cmd_check(args)
    elif args.command == "list":
        return cmd_list(args)
    else:
        parser.print_help()
        return 1


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rude", description="Fast, extensible Python linter")
    parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")

    sub = parser.add_subparsers(dest="command", metavar="command")

    # check (canonical command, "lint" kept as permanent alias)
    check = sub.add_parser("check", aliases=["lint"], help="Check files (default command)")
    _add_check_arguments(check)

    # list
    lst = sub.add_parser("list", help="List available rules")
    lst.add_argument("-v", "--verbose", action="store_true", help="Show descriptions")

    return parser


def _add_check_arguments(parser: argparse.ArgumentParser) -> None:
    """Add check-specific arguments to a parser."""
    parser.add_argument(
        "paths", nargs="*", type=Path, default=[Path(".")], help="Files or directories (default: .)"
    )
    parser.add_argument("--fix", action="store_true", help="Apply fixes")
    parser.add_argument("--select", help="Rules to enable (comma-separated)")
    parser.add_argument("--ignore", help="Rules to ignore (comma-separated)")
    parser.add_argument("--format", choices=["text", "json", "compact"], default="text")
    parser.add_argument("-q", "--quiet", action="store_true", help="Only show errors")
    parser.add_argument("--config", type=Path, help="Config file path")
    parser.add_argument("-j", "--jobs", type=int, default=1, help="Worker processes (default: 1)")
    parser.add_argument("--fail-fast", action="store_true", help="Stop on first error")
    parser.add_argument("--max-errors", type=int, default=None, help="Stop after N errors")
    parser.add_argument("--debug", action="store_true", help="Show full tracebacks on rule errors")

    # Rule-specific overrides
    parser.add_argument(
        "--max-line-length",
        type=int,
        default=None,
        help="Maximum line length for E501 (default: 79)",
    )
    parser.add_argument(
        "--max-complexity", type=int, default=None, help="Maximum complexity for C901 (default: 10)"
    )


def cmd_check(args: argparse.Namespace) -> int:
    # Load config
    config = load_config(args.config)

    # Override with CLI args
    select = args.select.split(",") if args.select else config.select or None
    ignore = args.ignore.split(",") if args.ignore else config.ignore or None

    # Discover and configure rules
    rules = discover_rules(
        select=select,
        ignore=ignore,
        plugins=config.plugins,
        local_rules=[str(config.resolve_path(p)) for p in config.local_rules],
    )

    if not rules:
        print("No rules selected", file=sys.stderr)
        return 1

    # Build CLI overrides for rule options
    cli_overrides: dict[str, dict[str, object]] = {}
    if args.max_line_length is not None:
        cli_overrides["E501"] = {"max_line_length": args.max_line_length}
    if args.max_complexity is not None:
        cli_overrides["C901"] = {"max_complexity": args.max_complexity}

    # Configure rules (config file merged with CLI overrides)
    for rule in rules:
        opts = config.get_rule_options(rule.code)
        override = cli_overrides.get(rule.code)
        if override:
            opts = {**(opts or {}), **override}
        if opts:
            rule.configure(opts)

    # Create linter
    linter = Linter(debug=getattr(args, "debug", False))
    linter.register_all(rules)

    # Collect files
    files = list(resolve_paths(args.paths))
    if not files:
        print("No Python files found", file=sys.stderr)
        return 1

    errors = warnings = fixed = 0

    if args.fix:
        # Fix mode: sequential (need to write files)
        for path in files:
            diagnostics, fix_result = linter.fix_file(path)
            if fix_result:
                atomic_write_text(path, fix_result.source)
                fixed += len(fix_result.applied)
                applied_ids = {id(d) for d in fix_result.applied}
            else:
                applied_ids = set()

            for d in diagnostics:
                if id(d) in applied_ids:
                    continue  # Suppress applied fixes from output
                _print_diagnostic(path, d, args)
                if d.severity == Severity.ERROR:
                    errors += 1
                else:
                    warnings += 1

    else:
        options = CheckOptions(
            workers=args.jobs,
            fail_fast=args.fail_fast,
            max_errors=args.max_errors,
        )

        for path, d in linter.check_paths_parallel(files, options, already_resolved=True):
            if args.quiet and d.severity != Severity.ERROR:
                continue
            _print_diagnostic(path, d, args)
            if d.severity == Severity.ERROR:
                errors += 1
            else:
                warnings += 1

            # Manual fail-fast check for display
            if args.fail_fast and errors > 0:
                break

    # Summary
    if not args.quiet and args.format == "text":
        print()
        if args.fix and fixed:
            print(f"Fixed {fixed} issue(s)")
        if errors + warnings:
            print(f"Found {errors} error(s) and {warnings} warning(s)")
        else:
            print("All checks passed")

    return 1 if errors else 0


_stdout_write = sys.stdout.buffer.write


def _print_diagnostic(path: Path, d: Diagnostic, args: argparse.Namespace) -> None:
    """Print a diagnostic in the requested format."""
    if args.format == "compact":
        _stdout_write(
            f"{path}:{d.location.line}:{d.location.column}: {d.code} {d.message}\n".encode()
        )
    elif args.format == "json":
        import json

        _stdout_write(
            json.dumps(
                {
                    "file": str(path),
                    "line": d.location.line,
                    "column": d.location.column,
                    "code": d.code,
                    "message": d.message,
                    "severity": d.severity.value,
                    "fixable": d.is_fixable,
                }
            ).encode()
            + b"\n"
        )
    else:
        fix_mark = " [fix]" if d.fix else ""
        _stdout_write(
            f"{path}:{d.location.line}:{d.location.column}: \033[1m{d.code}\033[0m {d.message}{fix_mark}\n".encode()
        )


def cmd_list(args: argparse.Namespace) -> int:
    from rude.core.rule_discovery import RuleDiscovery

    rd = RuleDiscovery()
    ALL_RULES = rd.load_builtin() + rd.load_entry_points()

    _PREFIX_CATEGORIES = [
        ("UP", "Pyupgrade (UP)"),
        ("C4", "Comprehensions (C4)"),
        ("C9", "McCabe (C)"),
        ("EX", "Templates (EX)"),
        ("META", "Hygiene (META)"),
        ("PAT", "Patterns (PAT)"),
        ("E", "Pycodestyle errors (E)"),
        ("W", "Pycodestyle warnings (W)"),
        ("F", "Pyflakes (F)"),
        ("B", "Bugbear (B)"),
    ]

    categories: dict[str, list[type[RuleBase]]] = {}
    for cls in ALL_RULES:
        code = cls.code
        cat = "Other"
        for prefix, category in _PREFIX_CATEGORIES:
            if code.startswith(prefix):
                cat = category
                break
        categories.setdefault(cat, []).append(cls)

    for cat, rules in sorted(categories.items()):
        print(f"\n\033[1m{cat}\033[0m")
        for cls in rules:
            if args.verbose:
                doc = (cls.__doc__ or "").strip().split("\n")[0]
                print(f"  {cls.code:10} {cls.__name__:25} {doc}")
            else:
                print(f"  {cls.code:10} {cls.__name__}")

    return 0


def cli() -> None:
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(file=sys.stderr)  # newline after ^C
        sys.exit(130)


if __name__ == "__main__":
    cli()
