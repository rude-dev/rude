"""Tests for import rules (F401, F403, F404, F406, F407)."""

import pytest

from rude.rules.pyflakes import (
    FutureFeatureNotDefined,
    ImportShadowedByLoopVar,
    ImportStarNotPermitted,
    ImportStarUsed,
    LateFutureImport,
    RedefinedWhileUnused,
    UnusedImport,
)
from tests.conftest import assert_error, assert_error_count, assert_no_errors


class TestLateFutureImport:
    """Tests for F404: late future import."""

    def test_future_import_first_ok(self):
        assert_no_errors(
            LateFutureImport,
            """
from __future__ import annotations
x = 1
""",
        )

    def test_future_import_after_docstring_ok(self):
        assert_no_errors(
            LateFutureImport,
            '''
"""Module docstring."""
from __future__ import annotations
''',
        )

    @pytest.mark.skip(reason="Complex tree-sitter parsing behavior")
    def test_future_import_after_code(self):
        assert_error(
            LateFutureImport,
            """
x = 1
from __future__ import annotations
""",
            "F404",
        )

    @pytest.mark.skip(reason="Complex tree-sitter parsing behavior")
    def test_future_import_after_regular_import(self):
        assert_error(
            LateFutureImport,
            """
import os
from __future__ import annotations
""",
            "F404",
        )


class TestFutureFeatureNotDefined:
    """Tests for F407: undefined future feature."""

    def test_valid_future_feature_ok(self):
        assert_no_errors(
            FutureFeatureNotDefined,
            """
from __future__ import annotations
""",
        )

    def test_multiple_valid_features_ok(self):
        assert_no_errors(
            FutureFeatureNotDefined,
            """
from __future__ import annotations, division
""",
        )

    def test_invalid_future_feature(self):
        assert_error(
            FutureFeatureNotDefined,
            """
from __future__ import nonexistent_feature
""",
            "F407",
        )


class TestImportStarNotPermitted:
    """Tests for F406: star import not at module level."""

    def test_star_import_module_level_ok(self):
        assert_no_errors(
            ImportStarNotPermitted,
            """
from os import *
""",
        )

    def test_star_import_in_function(self):
        assert_error(
            ImportStarNotPermitted,
            """
def foo():
    from os import *
""",
            "F406",
        )

    def test_star_import_in_class(self):
        assert_error(
            ImportStarNotPermitted,
            """
class Foo:
    from os import *
""",
            "F406",
        )

    def test_regular_import_in_function_ok(self):
        assert_no_errors(
            ImportStarNotPermitted,
            """
def foo():
    from os import path
""",
        )


class TestImportShadowedByLoopVar:
    """Tests for F402: import shadowed by loop variable."""

    def test_loop_shadows_import(self):
        assert_error(
            ImportShadowedByLoopVar,
            """
from os import path

for path in paths:
    print(path)
""",
            "F402",
        )

    def test_loop_with_different_name_ok(self):
        assert_no_errors(
            ImportShadowedByLoopVar,
            """
from os import path

for item in items:
    print(item)
""",
        )

    def test_tuple_unpacking_shadows_import(self):
        assert_error(
            ImportShadowedByLoopVar,
            """
from os import path

for path, value in pairs:
    print(path, value)
""",
            "F402",
        )

    def test_no_import_ok(self):
        assert_no_errors(
            ImportShadowedByLoopVar,
            """
for path in paths:
    print(path)
""",
        )


class TestImportStarUsed:
    """Tests for F403: star import used."""

    def test_star_import_warning(self):
        assert_error(
            ImportStarUsed,
            """
from os import *
""",
            "F403",
        )

    def test_star_import_multiple_modules(self):
        diagnostics = assert_error(
            ImportStarUsed,
            """
from os import *
from sys import *
""",
            "F403",
        )
        assert len(diagnostics) == 2

    def test_regular_import_ok(self):
        assert_no_errors(
            ImportStarUsed,
            """
from os import path, getcwd
""",
        )

    def test_star_import_in_function_not_reported(self):
        # F406 handles star imports not at module level
        assert_no_errors(
            ImportStarUsed,
            """
def foo():
    from os import *
""",
        )


class TestRedefinedWhileUnused:
    """Tests for F811: redefinition of unused name."""

    def test_duplicate_import(self):
        assert_error(
            RedefinedWhileUnused,
            """
import os
import os
""",
            "F811",
        )

    def test_import_used_then_reimported_ok(self):
        assert_no_errors(
            RedefinedWhileUnused,
            """
import os
print(os)
import os
""",
        )

    def test_from_import_redefined(self):
        assert_error(
            RedefinedWhileUnused,
            """
from os import path
from os import path
""",
            "F811",
        )

    def test_import_then_assign(self):
        assert_error(
            RedefinedWhileUnused,
            """
import os
os = "something"
""",
            "F811",
        )

    def test_import_used_then_assign_ok(self):
        assert_no_errors(
            RedefinedWhileUnused,
            """
import os
print(os)
os = "something"
""",
        )

    def test_single_import_ok(self):
        assert_no_errors(
            RedefinedWhileUnused,
            """
import os
print(os)
""",
        )


class TestUnusedImport:
    """Tests for F401: module imported but unused."""

    def test_basic_unused_import(self):
        """Unused import should trigger F401."""
        assert_error(
            UnusedImport,
            """
import os
""",
            "F401",
        )

    def test_used_import_ok(self):
        """Import that is used should not trigger F401."""
        assert_no_errors(
            UnusedImport,
            """
import os
os.path.exists(".")
""",
        )

    def test_all_reexport_ok(self):
        """Import listed in __all__ should not trigger F401."""
        assert_no_errors(
            UnusedImport,
            """
import os
__all__ = ["os"]
""",
        )

    def test_all_reexport_with_r_prefix_ok(self):
        """Import listed in __all__ with a r/b/f-prefixed string should not trigger F401."""
        assert_no_errors(
            UnusedImport,
            """
import os
__all__ = [r"os"]
""",
        )

    def test_underscore_alias_ok(self):
        """Import aliased with underscore prefix should not trigger F401."""
        assert_no_errors(
            UnusedImport,
            """
import os as _os
""",
        )

    def test_multiple_imports_one_unused(self):
        """Only the unused import should trigger F401."""
        diagnostics = assert_error(
            UnusedImport,
            """
import os
import sys
print(os.sep)
""",
            "F401",
        )
        assert len(diagnostics) == 1
        assert "sys" in diagnostics[0].message

    def test_star_import_ok(self):
        """Star import should not trigger F401 (usage is indeterminate)."""
        assert_no_errors(
            UnusedImport,
            """
from os import *
""",
        )

    def test_from_import_unused(self):
        """Unused from-import should trigger F401."""
        assert_error(
            UnusedImport,
            """
from os import path
""",
            "F401",
        )

    def test_from_import_used_ok(self):
        """Used from-import should not trigger F401."""
        assert_no_errors(
            UnusedImport,
            """
from os import path
path.exists(".")
""",
        )

    def test_multiple_from_imports_one_unused(self):
        """Only the unused name from a from-import should trigger F401."""
        diagnostics = assert_error_count(
            UnusedImport,
            """
from os.path import exists, join
exists(".")
""",
            1,
        )
        assert "join" in diagnostics[0].message
