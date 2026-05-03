# Built-in Rules

Rude ships with 104 built-in rules (pyflakes, pycodestyle, McCabe). Additional
rules can be added via third-party plugins or local rules. Example rules
(templates, patterns, hygiene) are available in `examples/rules/` for use as
local rules.

All rules can be selected individually by code (e.g. `--select F401`) or by prefix
(e.g. `--select PAT` to enable all pattern rules). Rules marked with autofix support
can be applied automatically with `rude check --fix`. Configurable rules accept
per-rule options in `[tool.rude.rules.<CODE>]` sections of your `pyproject.toml`.

## Pyflakes (F) -- Logical errors

Pyflakes rules detect programming errors such as unused imports, undefined names,
and incorrect use of language features. These rules catch bugs that would otherwise
only surface at runtime.

| Code | Name | Description | Autofix |
|------|------|-------------|---------|
| F401 | UnusedImport | Module imported but unused | |
| F402 | ImportShadowedByLoopVar | Import name shadowed by a loop variable | |
| F403 | ImportStarUsed | `from module import *` used; unable to detect undefined names | |
| F404 | LateFutureImport | `from __future__` import is not at the top of the file | |
| F406 | ImportStarNotPermitted | `from module import *` only allowed at module level | |
| F407 | FutureFeatureNotDefined | Future feature not recognized by the Python interpreter | |
| F541 | FStringMissingPlaceholders | f-string without any placeholders | yes |
| F542 | TStringMissingPlaceholders | t-string without any placeholders | yes |
| F601 | MultiValueRepeatedKeyLiteral | Dictionary key literal repeated | |
| F602 | MultiValueRepeatedKeyVariable | Dictionary key variable repeated | |
| F621 | TooManyExpressionsInStarredAssignment | Too many expressions in starred assignment | |
| F622 | TwoStarredExpressions | More than one starred expression in an assignment | |
| F631 | AssertTuple | `assert` on a non-empty tuple is always true | |
| F632 | IsLiteral | Use `==` / `!=` to compare with literal values | yes |
| F634 | IfTuple | `if` on a non-empty tuple is always true | |
| F701 | BreakOutsideLoop | `break` outside of a `for` or `while` loop | |
| F702 | ContinueOutsideLoop | `continue` outside of a `for` or `while` loop | |
| F704 | YieldOutsideFunction | `yield` / `yield from` used outside of a function | |
| F706 | ReturnOutsideFunction | `return` used outside of a function | |
| F707 | DefaultExceptNotLast | `except:` (bare except) is not the last exception handler | |
| F811 | RedefinedWhileUnused | Name redefined from an unused import | |
| F821 | UndefinedName | Undefined name | |
| F822 | UndefinedExport | Name listed in `__all__` is not defined | |
| F823 | UndefinedLocal | Local variable referenced before assignment | |
| F831 | DuplicateArgument | Duplicate argument in function definition | |
| F841 | UnusedVariable | Local variable assigned but never used | yes |
| F842 | UnusedAnnotation | Local variable annotated but never used | |
| F901 | RaiseNotImplemented | `raise NotImplemented` should be `raise NotImplementedError` | yes |

Plus format string rules (F5xx) and annotation/docstring checks.

## Pycodestyle (E/W) -- Style

Pycodestyle rules enforce the PEP 8 style guide. They cover indentation, whitespace,
blank lines, imports, line length, and statement structure.

### Indentation (E1xx)

| Code | Name | Description | Autofix |
|------|------|-------------|---------|
| E101 | IndentationContainsMixedSpacesAndTabs | Indentation contains mixed spaces and tabs | |
| E111 | IndentationNotMultipleOfFour | Indentation is not a multiple of four spaces | |
| E117 | OverIndented | Over-indented code block | |
| W191 | IndentationContainsTabs | Indentation contains tabs | |

### Whitespace (E2xx)

| Code | Name | Description | Autofix |
|------|------|-------------|---------|
| E201 | WhitespaceAfterOpenBracket | Whitespace after `(`, `[`, or `{` | |
| E202 | WhitespaceBeforeCloseBracket | Whitespace before `)`, `]`, or `}` | |
| E203 | WhitespaceBeforeColon | Whitespace before `:`, `;`, or `,` | |
| E211 | WhitespaceBeforeParameters | Whitespace before `(` or `[` in function call | |
| E221 | MultipleSpacesBeforeOperator | Multiple spaces before operator | yes |
| E222 | MultipleSpacesAfterOperator | Multiple spaces after operator | yes |
| E223 | TabBeforeOperator | Tab before operator | yes |
| E224 | TabAfterOperator | Tab after operator | yes |
| E225 | MissingWhitespaceAroundOperator | Missing whitespace around operator | |
| E226 | MissingWhitespaceAroundArithmeticOperator | Missing whitespace around arithmetic operator | |
| E227 | MissingWhitespaceAroundBitwiseOperator | Missing whitespace around bitwise or shift operator | |
| E228 | MissingWhitespaceAroundModuloOperator | Missing whitespace around modulo operator | |
| E231 | MissingWhitespaceAfterComma | Missing whitespace after `,`, `;`, or `:` | |
| E241 | MultipleSpacesAfterComma | Multiple spaces after comma | yes |
| E242 | TabAfterComma | Tab after comma | yes |
| E251 | UnexpectedSpacesAroundKeywordEquals | Unexpected spaces around keyword / parameter default | |
| E261 | LeastTwoSpacesBeforeInlineComment | At least two spaces before inline comment | yes |
| E262 | InlineCommentShouldStartWithHash | Inline comment should start with `# ` | yes |
| E265 | BlockCommentShouldStartWithHash | Block comment should start with `# ` | yes |
| E266 | TooManyLeadingHashesForBlockComment | Too many leading `#` for block comment | yes |
| E271 | MultipleSpacesAfterKeyword | Multiple spaces after keyword | yes |
| E272 | MultipleSpacesBeforeKeyword | Multiple spaces before keyword | yes |
| E273 | TabAfterKeyword | Tab after keyword | yes |
| E274 | TabBeforeKeyword | Tab before keyword | yes |
| E275 | MissingWhitespaceAfterKeyword | Missing whitespace after keyword | yes |

### Blank lines (E3xx)

| Code | Name | Description | Autofix |
|------|------|-------------|---------|
| E301 | ExpectedOneBlankLine | Expected 1 blank line before a nested definition | |
| E302 | ExpectedTwoBlankLines | Expected 2 blank lines before a function or class definition | |
| E303 | TooManyBlankLines | Too many blank lines | |
| E304 | BlankLinesAfterDecorator | Unexpected blank lines after decorator | |
| E305 | ExpectedTwoBlankLinesAfterClassOrFunction | Expected 2 blank lines after end of function or class | |
| E306 | ExpectedOneBlankLineBeforeNestedDef | Expected 1 blank line before a nested definition | |

### Imports (E4xx)

| Code | Name | Description | Autofix |
|------|------|-------------|---------|
| E401 | MultipleImportsOnOneLine | Multiple imports on one line | |
| E402 | ModuleLevelImportNotAtTop | Module-level import not at top of file | |

### Line length (E5xx)

| Code | Name | Description | Autofix |
|------|------|-------------|---------|
| E501 | LineTooLong | Line too long (default: 79 characters) | |

### Statements (E7xx)

| Code | Name | Description | Autofix |
|------|------|-------------|---------|
| E701 | MultipleStatementsOnOneLineColon | Multiple statements on one line (colon) | |
| E702 | MultipleStatementsOnOneLineSemicolon | Multiple statements on one line (semicolon) | |
| E703 | StatementEndsWithSemicolon | Statement ends with a semicolon | yes |
| E704 | MultipleStatementsOnOneLineDef | Statement on same line as `def` | |
| E711 | ComparisonToNone | Comparison to `None` (use `is` or `is not`) | yes |
| E712 | ComparisonToTrueFalse | Comparison to `True` or `False` (use `if x:` or `if not x:`) | |
| E713 | NotInTest | Test for membership should be `not in x` | yes |
| E714 | NotIsTest | Test for object identity should be `is not` | yes |
| E721 | TypeComparison | Do not compare types, use `isinstance()` | |
| E722 | BareExcept | Do not use bare `except` | yes |
| E731 | LambdaAssignment | Do not assign a `lambda` expression, use a `def` | |
| E741 | AmbiguousVariableName | Ambiguous variable name (e.g. `l`, `O`, `I`) | |
| E742 | AmbiguousClassName | Ambiguous class name | |
| E743 | AmbiguousFunctionName | Ambiguous function name | |

### Warnings (Wxxx)

| Code | Name | Description | Autofix |
|------|------|-------------|---------|
| W291 | TrailingWhitespace | Trailing whitespace | |
| W292 | NoNewlineAtEndOfFile | No newline at end of file | |
| W293 | BlankLineContainsWhitespace | Blank line contains whitespace | |
| W391 | BlankLineAtEndOfFile | Blank line at end of file | |
| W605 | InvalidEscapeSequence | Invalid escape sequence | |

## McCabe (C) -- Complexity

McCabe rules measure cyclomatic complexity of functions and methods. High complexity
indicates code that is harder to understand and test.

| Code | Name | Description | Default | Autofix |
|------|------|-------------|---------|---------|
| C901 | FunctionTooComplex | Function has too high cyclomatic complexity | threshold: 10 | |

## Patterns (PAT) -- Code smells

Pattern rules detect structural code smells such as overly long functions, deeply
nested code, and dangerous built-in calls. Thresholds are configurable via
`[tool.rude.rules.<CODE>]` in your `pyproject.toml`.

| Code | Name | Description | Default | Autofix |
|------|------|-------------|---------|---------|
| PAT001 | TooManyParameters | Function has too many parameters | max: 5 | |
| PAT002 | TooManyBranches | Function has too many branches (cyclomatic complexity) | max: 12 | |
| PAT003 | DeepNesting | Code block is nested too deeply | max: 4 | |
| PAT004 | LongFunction | Function body is too long | max: 50 lines | |
| PAT005 | GodClass | Class has too many methods | max: 20 | |
| PAT006 | NoPassInExcept | Bare `pass` in `except` block silently swallows errors | | |
| PAT007 | BareExcept | Use `except Exception:` instead of bare `except:` | | yes |
| PAT008 | NoEval | `eval()` is dangerous; avoid dynamic code execution | | yes |
| PAT009 | NoExec | `exec()` is dangerous; avoid dynamic code execution | | |
| PAT010 | NoAssertInProduction | `assert` statements are removed with `python -O` | | |

## Hygiene (META) -- Code hygiene

Hygiene rules enforce documentation and annotation discipline. They help teams
maintain consistent code review practices by requiring ticket references in TODOs
and specific suppression codes in `noqa` and `type: ignore` comments.

| Code | Name | Description | Configurable | Autofix |
|------|------|-------------|--------------|---------|
| META001 | TodoWithoutTicket | TODO/FIXME comments must include a ticket reference | `ticket_pattern` | |
| META002 | BlanketNoqa | `# noqa` comments must specify rule codes (e.g. `# noqa: F401`) | | |
| META003 | TypeIgnoreWithoutCode | `# type: ignore` must specify error codes (e.g. `# type: ignore[attr-defined]`) | | |

## Example Rules

Templates (EX001-EX004), patterns (PAT001-PAT010), and hygiene (META001-META003)
are available in `examples/rules/`. Load them via local rules:

```toml
[tool.rude]
local-rules = ["examples/rules/templates", "examples/rules/patterns"]
```

See `examples/rules/README.md` for details.
