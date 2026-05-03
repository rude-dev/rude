"""
Linter engine - orchestrates rules, file processing, and autofixes.

Default (--jobs=1): single process with Rust rayon parallelism (all CPUs, low memory).
With --jobs=N (N>1): N subprocesses for parallel Python rules (higher memory).
"""

from __future__ import annotations

import contextlib
import heapq
import multiprocessing as mp
import os
import signal
import sys
from collections import defaultdict
from collections.abc import Iterator, Sequence
from concurrent.futures import Future, ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from rude.core.import_edits import compute_merged_import_edits
from rude.core.node import Node, NodeProxy
from rude.core.node_types import VALID_NODE_TYPES
from rude.core.parser import parse, parse_file
from rude.core.types import Diagnostic, Edit, FileContext, FixResult, Location, Severity
from rude.utils import atomic_write_text, find_comment_start

if TYPE_CHECKING:
    from rude.core.rule import LineRule, Rule, RuleBase


# ─────────────────────────────────────────────────────────────────────────────
# Options
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class _RuleConfig:
    """Serializable rule configuration for workers."""

    rule_class: type
    options: dict[str, Any]


@dataclass
class CheckOptions:
    """Options for parallel checking."""

    workers: int | None = None  # None/1 = single process, int = explicit
    fail_fast: bool = False  # Stop on first error
    max_errors: int | None = None  # Stop after N errors
    fail_on_warning: bool = False  # Treat warnings as errors
    timeout_per_file: float = 30.0  # Seconds per file


class Linter:
    """
    Main linter engine.

    Example::

        linter = Linter()
        linter.register(NoEval())

        for diag in linter.check_file("src/main.py"):
            print(diag)

        # With autofix
        diagnostics, result = linter.fix_file("src/main.py")
        if result:
            Path("src/main.py").write_text(result.source)
    """

    def __init__(self, *, debug: bool = False) -> None:
        self._rules: list[Rule] = []
        self._rules_by_type: dict[str, list[Rule]] = defaultdict(list)
        self._line_rules: list[LineRule] = []
        self._registered_codes: set[str] = set()
        self._debug: bool = debug

    # ─────────────────────────────────────────────────────────────────────────
    # Rule registration
    # ─────────────────────────────────────────────────────────────────────────

    def register(self, rule: RuleBase) -> None:
        from rude.core.rule import LineRule, Rule

        if rule.code in self._registered_codes:
            return
        if isinstance(rule, LineRule):
            self._line_rules.append(rule)
        elif isinstance(rule, Rule):
            if rule.node_types is None:
                raise ValueError(f"Rule {rule.code} must define explicit node_types")
            unknown = rule.node_types - VALID_NODE_TYPES
            if unknown:
                raise ValueError(
                    f"Unknown node type(s) {unknown!r} in rule {rule.code}. "
                    f"If valid, add to VALID_NODE_TYPES via node_type_names()."
                )
            self._rules.append(rule)
            for t in rule.node_types:
                self._rules_by_type[t].append(rule)
        else:
            raise TypeError(f"Unknown rule type: {type(rule)}")
        self._registered_codes.add(rule.code)

    def register_all(self, rules: list[RuleBase]) -> None:
        for r in rules:
            self.register(r)

    def unregister(self, code: str) -> bool:
        from rude.core.rule import LineRule, Rule

        rule = self.get_rule(code)
        if not rule:
            return False
        if isinstance(rule, Rule) and rule in self._rules:
            self._rules.remove(rule)
            for lst in self._rules_by_type.values():
                if rule in lst:
                    lst.remove(rule)
        elif isinstance(rule, LineRule) and rule in self._line_rules:
            self._line_rules.remove(rule)
        self._registered_codes.discard(code)
        return True

    # ─────────────────────────────────────────────────────────────────────────
    # Linting
    # ─────────────────────────────────────────────────────────────────────────

    def check_file(self, path: Path | str) -> Iterator[Diagnostic]:
        path = Path(path)
        try:
            ctx = parse_file(path)
        except FileNotFoundError:
            yield Diagnostic(
                code="E000",
                message=f"File not found: {path}",
                location=Location(1, 0),
                severity=Severity.ERROR,
            )
            return
        except PermissionError:
            yield Diagnostic(
                code="E000",
                message=f"Permission denied: {path}",
                location=Location(1, 0),
                severity=Severity.ERROR,
            )
            return
        except Exception as e:
            yield Diagnostic(
                code="E000",
                message=f"Read error: {e}",
                location=Location(1, 0),
                severity=Severity.ERROR,
            )
            return
        yield from self._check_context(ctx)

    def check_source(self, source: str | bytes, filename: str = "<string>") -> Iterator[Diagnostic]:
        if isinstance(source, str):
            source = source.encode("utf-8")
        tree = parse(source)
        ctx = FileContext(path=Path(filename), source=source, tree=tree)
        yield from self._check_context(ctx)

    def _check_context(self, ctx: FileContext) -> Iterator[Diagnostic]:
        active_line_rules = [r for r in self._line_rules if r.should_check_file(ctx)]

        # Memoize should_check_file per rule (avoids redundant calls for
        # rules registered on multiple node types)
        rule_eligible = {id(r): r.should_check_file(ctx) for r in self._rules}

        # Build filtered indexes only for active rules
        active_by_type: dict[str, list[Rule]] = {}
        has_active_ast_rules = False

        for node_type, rules in self._rules_by_type.items():
            active_rules = [r for r in rules if rule_eligible[id(r)]]
            if active_rules:
                active_by_type[node_type] = active_rules
                has_active_ast_rules = True

        if not has_active_ast_rules and not active_line_rules:
            return

        # ─────────────────────────────────────────────────────────────────────
        # Phase 1: Run line-based rules (single pass over all lines)
        # ─────────────────────────────────────────────────────────────────────
        if active_line_rules:
            for lineno, line in enumerate(ctx.text_lines, start=1):
                # Pre-compute comment position once (ignores # in strings)
                comment_pos = find_comment_start(line)
                for line_rule in active_line_rules:
                    try:
                        for diag in line_rule.check_line(
                            line, lineno, ctx, comment_pos=comment_pos
                        ):
                            if not ctx.has_noqa(diag.location.line, diag.code):
                                yield diag
                    except Exception as e:
                        if self._debug:
                            raise
                        yield Diagnostic(
                            code="E001",
                            message=f"Rule {line_rule.code} error: {e}",
                            location=Location(lineno, 0),
                            severity=Severity.ERROR,
                        )

        # ─────────────────────────────────────────────────────────────────────
        # Phase 2: Run AST-based rules (batch dispatch)
        # ─────────────────────────────────────────────────────────────────────
        if not has_active_ast_rules:
            return

        # Collect all needed node types (aliases already pre-merged at register)
        needed_types = set(active_by_type.keys())

        # Try batch dispatch via grouped_nodes (avoids tree-sitter Query overhead)
        yield from self._dispatch_batch(ctx, needed_types, active_by_type)

    def _dispatch_batch(
        self,
        ctx: FileContext,
        needed_types: set[str],
        active_by_type: dict[str, list[Rule]],
        groups: Any = None,
    ) -> Iterator[Diagnostic]:
        """Batch dispatch using grouped_nodes + NodeProxy."""
        from rude.providers import ScopeProvider

        filter_types = set(needed_types)
        filter_types.add("ERROR")

        if groups is None:
            # Determine if any active rule needs scope analysis
            active_rules_flat = {id(r): r for rules in active_by_type.values() for r in rules}
            needs_semantic = any(
                ScopeProvider in getattr(type(r), "metadata_dependencies", set())
                for r in active_rules_flat.values()
            )

            if needs_semantic:
                # Single-pass: analyze + group in one AST traversal
                from rude._rust import analyze_and_group

                model, groups = analyze_and_group(ctx.tree, sorted(filter_types))
                scope_prov = ScopeProvider.from_model(model)
                ctx.set_metadata(ScopeProvider, scope_prov)
            else:
                from rude._rust import group_nodes

                groups = group_nodes(ctx.source, sorted(filter_types), tree=ctx.tree)

        syntax_error_found = False

        # Check for syntax errors first
        for entry in groups.get("ERROR", ()):
            if not syntax_error_found:
                text = ctx.source[entry.start_byte : entry.end_byte]
                yield Diagnostic(
                    code="E999",
                    message=f"SyntaxError: {text[:50].decode('utf-8', errors='replace') if text else 'unknown'}",
                    location=Location(entry.start_row, entry.start_col),
                    severity=Severity.ERROR,
                )
                syntax_error_found = True

        # Dispatch rules by node type (aliases pre-merged at register)
        for node_type, node_entries in groups.items():
            if node_type == "ERROR":
                continue

            rules_list = active_by_type.get(node_type)
            if not rules_list:
                continue

            for entry in node_entries:
                proxy = NodeProxy(node_type, entry, ctx)

                for rule in rules_list:
                    try:
                        for diag in rule.check(cast(Node, proxy)):
                            if not ctx.has_noqa(diag.location.line, diag.code):
                                yield diag
                    except Exception as e:
                        if self._debug:
                            raise
                        yield Diagnostic(
                            code="E001",
                            message=f"Rule {rule.code} error: {e}",
                            location=proxy.location,
                            severity=Severity.ERROR,
                        )

    def _check_files_streaming(
        self,
        files: Sequence[Path | str],
        options: CheckOptions | None = None,
    ) -> Iterator[tuple[Path, Diagnostic]]:
        """Batch-check files using a streaming Rust iterator.

        Uses batch_analyze_iter which streams results one at a time through
        a bounded channel (capacity 8). Rayon uses all CPUs by default.
        """
        from rude._rust import batch_analyze_iter
        from rude.providers import ScopeProvider

        options = options or CheckOptions()

        # Compute filter_types once from registered rules (aliases pre-merged)
        needed_types: set[str] = set(self._rules_by_type.keys())
        needed_types.add("ERROR")
        filter_types = sorted(needed_types)

        # Pre-compute active rules once: separate always-eligible from
        # per-file overriders (only templates/patterns override should_check_file)
        from rude.core.rule import RuleBase

        _base_check = RuleBase.should_check_file

        # Line rules: split static (always True) vs per-file
        static_line_rules = [
            r for r in self._line_rules if type(r).should_check_file is _base_check
        ]
        dynamic_line_rules = [
            r for r in self._line_rules if type(r).should_check_file is not _base_check
        ]

        # AST rules: compute active_by_type for static rules once
        static_rules = {id(r) for r in self._rules if type(r).should_check_file is _base_check}
        dynamic_rules = [r for r in self._rules if type(r).should_check_file is not _base_check]

        base_active_by_type: dict[str, list[Rule]] = {}
        for node_type, rules in self._rules_by_type.items():
            static = [r for r in rules if id(r) in static_rules]
            if static:
                base_active_by_type[node_type] = static
        has_static_ast_rules = bool(base_active_by_type)

        str_paths = [str(p) for p in files]
        succeeded: set[str] = set()

        for path_str, source_bytes, tree, model, groups in batch_analyze_iter(
            str_paths, filter_types
        ):
            succeeded.add(path_str)
            path = Path(path_str)
            ctx = FileContext.from_analysis(
                path=path,
                source=source_bytes,
                tree=tree,
                string_lines=frozenset(model.string_lines),
                noqa_map={
                    line: True if codes is None else {c.upper() for c in codes}
                    for line, codes in model.noqa_lines.items()
                },
                line_infos=model.line_infos,
            )

            # Inject pre-built SemanticModel so rules don't re-analyze
            scope_prov = ScopeProvider.from_model(model)
            ctx.set_metadata(ScopeProvider, scope_prov)

            # Per-file rules: only recompute the few that override should_check_file
            active_line_rules = static_line_rules + [
                r for r in dynamic_line_rules if r.should_check_file(ctx)
            ]

            # Merge dynamic AST rules into the pre-computed base
            if dynamic_rules:
                dyn_eligible = {id(r) for r in dynamic_rules if r.should_check_file(ctx)}
                if dyn_eligible:
                    active_by_type = dict(base_active_by_type)
                    for node_type, rules in self._rules_by_type.items():
                        extra = [r for r in rules if id(r) in dyn_eligible]
                        if extra:
                            active_by_type[node_type] = active_by_type.get(node_type, []) + extra
                    has_active_ast_rules = True
                else:
                    active_by_type = base_active_by_type
                    has_active_ast_rules = has_static_ast_rules
            else:
                active_by_type = base_active_by_type
                has_active_ast_rules = has_static_ast_rules

            if not has_active_ast_rules and not active_line_rules:
                continue

            # Phase 1: Line rules — split fast (line_infos) vs slow (decode)
            if active_line_rules:
                line_infos = ctx._line_infos
                if line_infos is not None:
                    fast_rules = [r for r in active_line_rules if r.uses_line_infos]
                    slow_rules = [r for r in active_line_rules if not r.uses_line_infos]
                else:
                    fast_rules = []
                    slow_rules = active_line_rules

                # Fast path: pre-computed integer checks, no decode
                if fast_rules:
                    assert line_infos is not None  # guarded by the split above
                    for lineno, info in enumerate(line_infos, start=1):
                        for rule in fast_rules:
                            try:
                                for diag in rule.check_line_info(lineno, info, ctx):
                                    if not ctx.has_noqa(diag.location.line, diag.code):
                                        yield (path, diag)
                            except Exception as e:
                                if self._debug:
                                    raise
                                yield (
                                    path,
                                    Diagnostic(
                                        code="E001",
                                        message=f"Rule {rule.code} error: {e}",
                                        location=Location(lineno, 0),
                                        severity=Severity.ERROR,
                                    ),
                                )

                # Slow path: decode text lines, compute comment_start
                if slow_rules:
                    for lineno, line_text in enumerate(ctx.text_lines, start=1):
                        comment_pos = (
                            line_infos[lineno - 1].comment_start
                            if line_infos
                            else find_comment_start(line_text)
                        )
                        for line_rule in slow_rules:
                            try:
                                for diag in line_rule.check_line(
                                    line_text, lineno, ctx, comment_pos=comment_pos
                                ):
                                    if not ctx.has_noqa(diag.location.line, diag.code):
                                        yield (path, diag)
                            except Exception as e:
                                if self._debug:
                                    raise
                                yield (
                                    path,
                                    Diagnostic(
                                        code="E001",
                                        message=f"Rule {line_rule.code} error: {e}",
                                        location=Location(lineno, 0),
                                        severity=Severity.ERROR,
                                    ),
                                )

            # Phase 2: AST rules using pre-computed groups
            if has_active_ast_rules:
                for diag in self._dispatch_batch(
                    ctx, set(active_by_type.keys()), active_by_type, groups=groups
                ):
                    yield (path, diag)

        # Handle files that failed in batch (silently skipped by Rust)
        for p_str in str_paths:
            if p_str not in succeeded:
                p = Path(p_str)
                for d in self.check_file(p):
                    yield (p, d)

    # ─────────────────────────────────────────────────────────────────────────
    # Autofix
    # ─────────────────────────────────────────────────────────────────────────

    def fix_file(self, path: Path | str) -> tuple[list[Diagnostic], FixResult | None]:
        """Lint and fix a file. Returns (diagnostics, FixResult or None)."""
        path = Path(path)
        try:
            ctx = parse_file(path)
        except Exception:
            return list(self.check_file(path)), None

        diagnostics = list(self._check_context(ctx))
        fixable = [d for d in diagnostics if d.fix]
        if not fixable:
            return diagnostics, None

        result = self._apply_fixes(ctx, fixable)
        return diagnostics, result

    def fix_source(
        self, source: str | bytes, filename: str = "<string>"
    ) -> tuple[list[Diagnostic], FixResult | None]:
        """Lint and fix source code."""
        if isinstance(source, str):
            source = source.encode("utf-8")
        tree = parse(source)
        ctx = FileContext(path=Path(filename), source=source, tree=tree)

        diagnostics = list(self._check_context(ctx))
        fixable = [d for d in diagnostics if d.fix]
        if not fixable:
            return diagnostics, None

        result = self._apply_fixes(ctx, fixable)
        return diagnostics, result

    def fix_file_in_place(self, path: Path | str) -> tuple[list[Diagnostic], FixResult | None]:
        """Fix file and write back."""
        path = Path(path)
        diagnostics, result = self.fix_file(path)
        if result:
            atomic_write_text(path, result.source)
        return diagnostics, result

    def _apply_fixes(
        self,
        ctx: FileContext,
        diagnostics: list[Diagnostic],
    ) -> FixResult:
        """Apply fixes from diagnostics to source.

        Three-phase algorithm:
        1. Filter regular edits atomically per-diagnostic (first-in-file wins)
        2. Compute merged imports from surviving diagnostics only
        3. Apply all edits from end to start
        """
        # Phase 1: Filter regular edits -- atomic per-diagnostic
        sorted_diags = sorted(
            diagnostics,
            key=lambda d: d.fix.edits[0].start_byte if d.fix and d.fix.edits else 0,
        )

        accepted: list[Diagnostic] = []
        dropped: list[Diagnostic] = []
        occupied: list[tuple[int, int]] = []

        for diag in sorted_diags:
            fix = diag.fix
            if not fix:
                continue

            conflict = False
            for edit in fix.edits:
                for occ_start, occ_end in occupied:
                    if edit.start_byte < occ_end and edit.end_byte > occ_start:
                        conflict = True
                        break
                if conflict:
                    break

            if conflict:
                dropped.append(diag)
            else:
                accepted.append(diag)
                for edit in fix.edits:
                    if edit.start_byte < edit.end_byte:
                        occupied.append((edit.start_byte, edit.end_byte))

        # Phase 2: Compute imports from survivors only
        accepted_fixes = [d.fix for d in accepted if d.fix]
        import_edits = compute_merged_import_edits(ctx, accepted_fixes)

        # Collect all edits
        all_edits: list[Edit] = []
        for fix in accepted_fixes:
            all_edits.extend(fix.edits)
        all_edits.extend(import_edits)

        # Phase 3: Apply edits from end to start
        all_edits.sort(key=lambda e: e.start_byte, reverse=True)

        # Convert to bytearray for in-place slice assignment; avoids the
        # O(N*M) copy that per-edit concatenation incurs on large files.
        source_buf = bytearray(ctx.source)
        for edit in all_edits:
            source_buf[edit.start_byte : edit.end_byte] = edit.new_text.encode("utf-8")

        return FixResult(
            source=bytes(source_buf).decode("utf-8", errors="replace"),
            applied=tuple(accepted),
            dropped=tuple(dropped),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Parallel execution (single process — Rust rayon handles parallelism)
    # ─────────────────────────────────────────────────────────────────────────

    def _check_files_multiprocess(
        self,
        files: Sequence[Path | str],
        options: CheckOptions,
        workers: int,
    ) -> Iterator[tuple[Path, Diagnostic]]:
        """Check files using multiprocessing (N subprocesses).

        Each worker gets a chunk of files and runs the full streaming path
        (batch_analyze_iter + line_infos + noqa) so all pre-computed Rust
        metadata is used.  Chunks are split via LPT scheduling.
        """
        # Sort largest files first for LPT scheduling
        sorted_files = [Path(f) for f in files]
        with contextlib.suppress(OSError):
            sorted_files.sort(key=lambda f: f.stat().st_size, reverse=True)

        chunks = _split_lpt(sorted_files, workers)

        # Prepare serializable rule configs
        all_rules: list[RuleBase] = [*self._rules, *self._line_rules]
        rule_configs = [
            _RuleConfig(rule_class=type(r), options=getattr(r, "__dict__", {})) for r in all_rules
        ]

        error_count = 0
        shutdown_requested = False

        def handle_signal(sig: int, frame: object) -> None:
            nonlocal shutdown_requested
            shutdown_requested = True

        old_sigint = signal.signal(signal.SIGINT, handle_signal)
        old_sigterm = signal.signal(signal.SIGTERM, handle_signal)

        try:
            with ProcessPoolExecutor(
                max_workers=workers,
                mp_context=_get_mp_context(),
                initializer=_init_worker,
                initargs=(rule_configs, workers),
            ) as executor:
                pending: dict[Future[list[tuple[Path, list[Diagnostic]]]], list[Path]] = {
                    executor.submit(_check_files_worker, chunk): chunk for chunk in chunks
                }

                for future in as_completed(pending):
                    if shutdown_requested:
                        executor.shutdown(wait=False, cancel_futures=True)
                        return

                    chunk = pending[future]

                    try:
                        file_results = future.result(timeout=options.timeout_per_file * len(chunk))

                        for path, diagnostics in file_results:
                            for diag in diagnostics:
                                yield (path, diag)
                                is_error = diag.severity == Severity.ERROR or (
                                    options.fail_on_warning and diag.severity == Severity.WARNING
                                )
                                if is_error:
                                    error_count += 1

                        if options.fail_fast and error_count > 0:
                            executor.shutdown(wait=False, cancel_futures=True)
                            return
                        if options.max_errors and error_count >= options.max_errors:
                            executor.shutdown(wait=False, cancel_futures=True)
                            return

                    except TimeoutError:
                        yield (
                            chunk[0],
                            Diagnostic(
                                code="E002",
                                message=f"Timeout processing chunk of {len(chunk)} files",
                                location=Location(1, 0),
                                severity=Severity.ERROR,
                            ),
                        )
                        error_count += 1

                    except Exception as e:
                        if self._debug:
                            raise
                        yield (
                            chunk[0],
                            Diagnostic(
                                code="E001",
                                message=f"Worker error: {e}",
                                location=Location(1, 0),
                                severity=Severity.ERROR,
                            ),
                        )
                        error_count += 1

        finally:
            signal.signal(signal.SIGINT, old_sigint)
            signal.signal(signal.SIGTERM, old_sigterm)

    def check_paths_parallel(
        self,
        paths: Sequence[Path | str],
        options: CheckOptions | None = None,
        *,
        already_resolved: bool = False,
    ) -> Iterator[tuple[Path, Diagnostic]]:
        """
        Lint paths with parallel execution.

        Default (workers=None or 1): Rust rayon in a single Python process.
        workers > 1: N subprocesses, each running Rust rayon + Python rules.

        Args:
            paths: Files or directories to check
            options: Check options (workers, fail_fast, max_errors, etc.)
            already_resolved: If True, skip resolve_paths (paths are already .py files)

        Yields:
            (path, diagnostic) tuples
        """
        options = options or CheckOptions()

        if already_resolved:
            files = list(paths) if not isinstance(paths, list) else paths
        else:
            from rude.core.file_finder import resolve_paths

            files = list(resolve_paths(paths))

        if not files:
            return

        workers = _resolve_workers(len(files), options.workers)
        if workers > 1:
            inner: Iterator[tuple[Path, Diagnostic]] = self._check_files_multiprocess(
                files, options, workers
            )
        else:
            inner = self._check_files_streaming(files, options)

        error_count = 0
        for path, diag in inner:
            yield (path, diag)
            is_error = diag.severity == Severity.ERROR or (
                options.fail_on_warning and diag.severity == Severity.WARNING
            )
            if is_error:
                error_count += 1
                if options.fail_fast:
                    break
                if options.max_errors and error_count >= options.max_errors:
                    break

    # ─────────────────────────────────────────────────────────────────────────
    # Introspection
    # ─────────────────────────────────────────────────────────────────────────

    @property
    def rules(self) -> list[Rule]:
        return self._rules.copy()

    def get_rule(self, code: str) -> RuleBase | None:
        for r in self._rules:
            if r.code == code:
                return r
        for lr in self._line_rules:
            if lr.code == code:
                return lr
        return None

    @property
    def rule_codes(self) -> list[str]:
        return [r.code for r in self._rules]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────────
# LPT scheduling
# ─────────────────────────────────────────────────────────────────────────────


def _split_lpt(files: list[Path], n: int) -> list[list[Path]]:
    """Split files into n chunks using Longest Processing Time scheduling.

    Sorts files by size descending and round-robin assigns each to the
    lightest worker, producing balanced chunks for multiprocessing.
    """
    sized = sorted(
        ((f.stat().st_size, f) for f in files),
        reverse=True,
    )
    heap: list[tuple[int, int]] = [(0, i) for i in range(n)]
    chunks: list[list[Path]] = [[] for _ in range(n)]
    for size, path in sized:
        total, idx = heapq.heappop(heap)
        chunks[idx].append(path)
        heapq.heappush(heap, (total + size, idx))
    return [c for c in chunks if c]


# ─────────────────────────────────────────────────────────────────────────────
# Worker functions (run in separate processes)
# ─────────────────────────────────────────────────────────────────────────────


def _rebuild_linter(rule_configs: list[_RuleConfig]) -> Linter:
    """Rebuild a Linter in worker process from serialized configs."""
    linter = Linter()
    for cfg in rule_configs:
        rule = cfg.rule_class()
        for k, v in cfg.options.items():
            setattr(rule, k, v)
        linter.register(rule)
    return linter


_worker_linter: Linter | None = None


def _init_worker(rule_configs: list[_RuleConfig], n_workers: int = 1) -> None:
    """Called once per worker process at startup."""
    if "RUDE_RAYON_THREADS" not in os.environ:
        cpus = os.cpu_count() or 4
        rayon_threads = max(1, cpus // n_workers)
        os.environ["RUDE_RAYON_THREADS"] = str(rayon_threads)
    global _worker_linter
    _worker_linter = _rebuild_linter(rule_configs)


def _check_files_worker(paths: list[Path]) -> list[tuple[Path, list[Diagnostic]]]:
    """Worker: check a chunk of files using the streaming path."""
    if _worker_linter is None:
        raise RuntimeError("Worker linter not initialized -- _init_worker was not called")
    try:
        result: dict[Path, list[Diagnostic]] = {}
        for path, diag in _worker_linter._check_files_streaming(paths):
            result.setdefault(path, []).append(diag)
        return list(result.items())
    except Exception as e:
        return [
            (
                paths[0],
                [
                    Diagnostic(
                        code="E001",
                        message=f"Worker crashed: {e}",
                        location=Location(1, 0),
                        severity=Severity.ERROR,
                    )
                ],
            )
        ]


def _get_mp_context() -> mp.context.BaseContext:
    """Pick the safest multiprocessing start method.

    - Linux: forkserver (fork unsafe with rayon threads)
    - macOS: spawn (fork unsafe with CoreFoundation)
    """
    if sys.platform == "linux":
        return mp.get_context("forkserver")
    return mp.get_context("spawn")


def _resolve_workers(file_count: int, requested: int | None) -> int:
    """Return worker count (capped at cpu_count and file_count)."""
    if requested is None or requested <= 1:
        return 1
    cpus = os.cpu_count() or 4
    return min(requested, file_count, cpus)


__all__ = ["CheckOptions", "Linter"]
