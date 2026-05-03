"""
Pycodestyle rules for Rude.

E: Errors - style errors
W: Warnings - style warnings

Categories:
- E1xx: Indentation
- E2xx: Whitespace
- E3xx: Blank lines
- E4xx: Imports
- E5xx: Line length
- E7xx: Statements
- W1xx-W6xx: Warnings
"""

from rude.rules.pycodestyle.blank_lines import (
    BLANK_LINES_RULES,
    BlankLinesAfterDecorator,
    ExpectedOneBlankLine,
    ExpectedOneBlankLineBeforeNestedDef,
    ExpectedTwoBlankLines,
    ExpectedTwoBlankLinesAfterClassOrFunction,
    TooManyBlankLines,
)

# Re-export individual rules
from rude.rules.pycodestyle.comparison import (
    COMPARISON_RULES,
    ComparisonToNone,
    ComparisonToTrueFalse,
    NotInTest,
    NotIsTest,
    TypeComparison,
)
from rude.rules.pycodestyle.imports import (
    IMPORT_RULES,
    ModuleLevelImportNotAtTop,
    MultipleImportsOnOneLine,
)
from rude.rules.pycodestyle.indentation import (
    INDENTATION_RULES,
    IndentationContainsMixedSpacesAndTabs,
    IndentationContainsTabs,
    IndentationNotMultipleOfFour,
    OverIndented,
)
from rude.rules.pycodestyle.line_length import (
    LINE_LENGTH_RULES,
    LineTooLong,
)
from rude.rules.pycodestyle.statements import (
    STATEMENT_RULES,
    AmbiguousClassName,
    AmbiguousFunctionName,
    AmbiguousVariableName,
    BareExcept,
    LambdaAssignment,
    MultipleStatementsOnOneLineColon,
    MultipleStatementsOnOneLineDef,
    MultipleStatementsOnOneLineSemicolon,
    StatementEndsWithSemicolon,
)
from rude.rules.pycodestyle.warnings import (
    WARNING_RULES,
    BlankLineAtEndOfFile,
    BlankLineContainsWhitespace,
    InvalidEscapeSequence,
    NoNewlineAtEndOfFile,
    TrailingWhitespace,
)
from rude.rules.pycodestyle.whitespace import (
    WHITESPACE_RULES,
    BlockCommentShouldStartWithSpace,
    InlineCommentShouldStartWithSpace,
    MissingWhitespaceAfterComma,
    MissingWhitespaceAfterKeyword,
    MissingWhitespaceAroundArithmeticOperator,
    MissingWhitespaceAroundBitwiseOperator,
    MissingWhitespaceAroundModuloOperator,
    # E225-E228
    MissingWhitespaceAroundOperator,
    # E241-E242
    MultipleSpacesAfterComma,
    # E271-E275
    MultipleSpacesAfterKeyword,
    MultipleSpacesAfterOperator,
    MultipleSpacesBeforeKeyword,
    # E221-E224
    MultipleSpacesBeforeOperator,
    TabAfterComma,
    TabAfterKeyword,
    TabAfterOperator,
    TabBeforeKeyword,
    TabBeforeOperator,
    TooManyHashesForBlockComment,
    TwoSpacesBeforeInlineComment,
    UnexpectedSpacesAroundKeywordEquals,
    WhitespaceAfterOpenBracket,
    WhitespaceBeforeCloseBracket,
    WhitespaceBeforeColon,
    WhitespaceBeforeParameters,
)

PYCODESTYLE_RULES = (
    COMPARISON_RULES
    + STATEMENT_RULES
    + IMPORT_RULES
    + LINE_LENGTH_RULES
    + WARNING_RULES
    + INDENTATION_RULES
    + WHITESPACE_RULES
    + BLANK_LINES_RULES
)

__all__ = [
    "BLANK_LINES_RULES",
    "COMPARISON_RULES",
    "IMPORT_RULES",
    "INDENTATION_RULES",
    "LINE_LENGTH_RULES",
    "PYCODESTYLE_RULES",
    "STATEMENT_RULES",
    "WARNING_RULES",
    "WHITESPACE_RULES",
    "AmbiguousClassName",
    "AmbiguousFunctionName",
    "AmbiguousVariableName",
    "BareExcept",
    "BlankLineAtEndOfFile",
    "BlankLineContainsWhitespace",
    "BlankLinesAfterDecorator",
    "BlockCommentShouldStartWithSpace",
    # Comparison
    "ComparisonToNone",
    "ComparisonToTrueFalse",
    # Blank lines
    "ExpectedOneBlankLine",
    "ExpectedOneBlankLineBeforeNestedDef",
    "ExpectedTwoBlankLines",
    "ExpectedTwoBlankLinesAfterClassOrFunction",
    # Indentation
    "IndentationContainsMixedSpacesAndTabs",
    "IndentationContainsTabs",
    "IndentationNotMultipleOfFour",
    "InlineCommentShouldStartWithSpace",
    "InvalidEscapeSequence",
    "LambdaAssignment",
    # Line length
    "LineTooLong",
    "MissingWhitespaceAfterComma",
    "MissingWhitespaceAfterKeyword",
    "MissingWhitespaceAroundArithmeticOperator",
    "MissingWhitespaceAroundBitwiseOperator",
    "MissingWhitespaceAroundModuloOperator",
    # E225-E228
    "MissingWhitespaceAroundOperator",
    "ModuleLevelImportNotAtTop",
    # Imports
    "MultipleImportsOnOneLine",
    # E241-E242
    "MultipleSpacesAfterComma",
    # E271-E275
    "MultipleSpacesAfterKeyword",
    "MultipleSpacesAfterOperator",
    "MultipleSpacesBeforeKeyword",
    # E221-E224
    "MultipleSpacesBeforeOperator",
    # Statements
    "MultipleStatementsOnOneLineColon",
    "MultipleStatementsOnOneLineDef",
    "MultipleStatementsOnOneLineSemicolon",
    "NoNewlineAtEndOfFile",
    "NotInTest",
    "NotIsTest",
    "OverIndented",
    "StatementEndsWithSemicolon",
    "TabAfterComma",
    "TabAfterKeyword",
    "TabAfterOperator",
    "TabBeforeKeyword",
    "TabBeforeOperator",
    "TooManyBlankLines",
    "TooManyHashesForBlockComment",
    # Warnings
    "TrailingWhitespace",
    "TwoSpacesBeforeInlineComment",
    "TypeComparison",
    "UnexpectedSpacesAroundKeywordEquals",
    # Whitespace
    "WhitespaceAfterOpenBracket",
    "WhitespaceBeforeCloseBracket",
    "WhitespaceBeforeColon",
    "WhitespaceBeforeParameters",
]
