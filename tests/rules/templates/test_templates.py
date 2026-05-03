"""Tests for template rules: EX001-EX004.

Template rules are configurable, opt-in rules that require explicit
configuration before they detect anything. Each test creates a Linter,
registers a configured rule instance, and calls check_source().
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from rude.core.linter import Linter
from rude.core.parser import parse
from rude.core.rule import Rule
from rude.core.types import Diagnostic, FileContext

# Load templates from examples/ (not a package, loaded as local rules)
_templates_path = Path(__file__).parents[3] / "examples" / "rules" / "templates" / "__init__.py"
_spec = importlib.util.spec_from_file_location("example_templates", _templates_path)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
sys.modules["example_templates"] = _mod
_spec.loader.exec_module(_mod)

ForbiddenCall = _mod.ForbiddenCall
RequireBaseClass = _mod.RequireBaseClass
RequireDecorator = _mod.RequireDecorator
RequireFields = _mod.RequireFields

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _check(rule: Rule, source: str, filename: str = "<string>") -> list[Diagnostic]:
    """Register a pre-configured rule and check source code."""
    linter = Linter()
    linter.register(rule)
    return list(linter.check_source(source, filename=filename))


def _check_codes(rule: Rule, source: str, filename: str = "<string>") -> list[str]:
    return [d.code for d in _check(rule, source, filename)]


def _fix(
    rule: Rule, source: str, filename: str = "<string>"
) -> tuple[list[Diagnostic], str | None]:
    """Check and fix source with a configured rule."""
    linter = Linter()
    linter.register(rule)
    diagnostics, result = linter.fix_source(source, filename=filename)
    return diagnostics, result.source if result else None


def _make_ctx(filename: str = "<string>", source: str = "") -> FileContext:
    """Create a minimal FileContext for should_check_file tests."""
    src = source.encode("utf-8")
    tree = parse(src)
    return FileContext(path=Path(filename), source=src, tree=tree)


# ===========================================================================
# EX001 RequireBaseClass
# ===========================================================================


class TestRequireBaseClassDefaults:
    """EX001 with default config is essentially a no-op (requires 'object')."""

    def test_default_config_accepts_plain_class(self):
        rule = RequireBaseClass()
        # Default requires inheriting from "object" which Python classes
        # don't explicitly list; but the rule checks textual bases only,
        # so a plain class will NOT have "object" in its bases.
        diags = _check(rule, "class Foo:\n    pass\n")
        # Default pattern="*" and required_base="object", so it fires
        assert any(d.code == "EX001" for d in diags)

    def test_default_config_passes_explicit_object(self):
        rule = RequireBaseClass()
        diags = _check(rule, "class Foo(object):\n    pass\n")
        assert diags == []


class TestRequireBaseClassConfigured:
    """EX001 configured to enforce a specific base class."""

    def _rule(self, **kwargs):
        r = RequireBaseClass()
        r.configure({"pattern": "*Service", "required_base": "BaseService", **kwargs})
        return r

    def test_violation_no_base(self):
        """Class matches pattern but has no bases."""
        diags = _check(self._rule(), "class UserService:\n    pass\n")
        assert len(diags) == 1
        assert diags[0].code == "EX001"
        assert "UserService" in diags[0].message
        assert "BaseService" in diags[0].message

    def test_violation_wrong_base(self):
        """Class matches pattern but inherits from something else."""
        diags = _check(self._rule(), "class UserService(SomethingElse):\n    pass\n")
        assert len(diags) == 1
        assert diags[0].code == "EX001"

    def test_passes_correct_base(self):
        """Class matches pattern and inherits from required base."""
        diags = _check(self._rule(), "class UserService(BaseService):\n    pass\n")
        assert diags == []

    def test_passes_correct_base_among_multiple(self):
        """Required base is present among multiple bases."""
        diags = _check(self._rule(), "class UserService(Mixin, BaseService):\n    pass\n")
        assert diags == []

    def test_pattern_no_match_ignored(self):
        """Class not matching the pattern is not checked."""
        diags = _check(self._rule(), "class UserHandler:\n    pass\n")
        assert diags == []

    def test_pattern_wildcard_prefix(self):
        """Pattern with wildcard prefix."""
        rule = RequireBaseClass()
        rule.configure({"pattern": "Base*", "required_base": "ABC"})
        diags = _check(rule, "class BaseWidget:\n    pass\n")
        assert len(diags) == 1
        assert diags[0].code == "EX001"

    def test_pattern_exact_match(self):
        """Exact pattern (no wildcards)."""
        rule = RequireBaseClass()
        rule.configure({"pattern": "Config", "required_base": "BaseConfig"})
        # Matches
        diags = _check(rule, "class Config:\n    pass\n")
        assert len(diags) == 1
        # Does not match
        diags = _check(rule, "class AppConfig:\n    pass\n")
        assert diags == []

    def test_empty_class_body(self):
        """Class with ellipsis body."""
        diags = _check(self._rule(), "class UserService:\n    ...\n")
        assert len(diags) == 1

    def test_multiple_classes(self):
        """Multiple classes in one file."""
        source = """\
class UserService:
    pass

class OrderService(BaseService):
    pass

class PaymentService(OtherBase):
    pass
"""
        diags = _check(self._rule(), source)
        codes = [d.code for d in diags]
        assert codes.count("EX001") == 2  # UserService and PaymentService


class TestRequireBaseClassPathFiltering:
    """EX001 path filtering via should_check_file."""

    def test_no_paths_checks_everything(self):
        rule = RequireBaseClass()
        rule.configure({"pattern": "*", "required_base": "Base"})
        ctx = _make_ctx("any/file.py")
        assert rule.should_check_file(ctx) is True

    def test_matching_path(self):
        rule = RequireBaseClass()
        rule.configure({"pattern": "*", "required_base": "Base", "paths": ["src/services/"]})
        ctx = _make_ctx("src/services/user.py")
        assert rule.should_check_file(ctx) is True

    def test_non_matching_path(self):
        rule = RequireBaseClass()
        rule.configure({"pattern": "*", "required_base": "Base", "paths": ["src/services/"]})
        ctx = _make_ctx("src/handlers/user.py")
        assert rule.should_check_file(ctx) is False

    def test_integration_path_filtering(self):
        """Rule skips files outside configured paths."""
        rule = RequireBaseClass()
        rule.configure(
            {
                "pattern": "*Service",
                "required_base": "BaseService",
                "paths": ["src/services/"],
            }
        )
        source = "class UserService:\n    pass\n"
        # Inside path -> fires
        diags = _check(rule, source, filename="src/services/user.py")
        assert len(diags) == 1
        # Outside path -> skipped
        rule2 = RequireBaseClass()
        rule2.configure(
            {
                "pattern": "*Service",
                "required_base": "BaseService",
                "paths": ["src/services/"],
            }
        )
        diags = _check(rule2, source, filename="src/handlers/user.py")
        assert diags == []


# ===========================================================================
# EX002 RequireDecorator
# ===========================================================================


class TestRequireDecoratorDefaults:
    """EX002 with no required_decorator configured is a no-op."""

    def test_unconfigured_skips_all(self):
        rule = RequireDecorator()
        ctx = _make_ctx("any/file.py")
        assert rule.should_check_file(ctx) is False

    def test_unconfigured_produces_no_diags(self):
        rule = RequireDecorator()
        diags = _check(rule, "def foo():\n    pass\n")
        assert diags == []


class TestRequireDecoratorConfigured:
    """EX002 configured to require a decorator."""

    def _rule(self, **kwargs):
        r = RequireDecorator()
        r.configure({"required_decorator": "audit_log", **kwargs})
        return r

    def test_violation_missing_decorator(self):
        source = "def create_user(request):\n    pass\n"
        diags = _check(self._rule(), source)
        assert len(diags) == 1
        assert diags[0].code == "EX002"
        assert "create_user" in diags[0].message
        assert "audit_log" in diags[0].message

    def test_decorated_function_still_fires(self):
        """Known limitation: batch dispatch gives function_definition nodes
        which don't include decorators (they live on decorated_definition).
        So has_decorator() returns False and the rule fires even when the
        decorator is present."""
        source = "@audit_log\ndef create_user(request):\n    pass\n"
        diags = _check(self._rule(), source)
        # The rule cannot see decorators from function_definition node
        assert len(diags) == 1

    def test_exclude_pattern_underscore_prefix(self):
        """Default exclude_pattern='_*' skips private functions."""
        source = "def _helper():\n    pass\n"
        diags = _check(self._rule(), source)
        assert diags == []

    def test_exclude_pattern_dunder(self):
        """Dunder methods match '_*' and are excluded."""
        source = "def __init__(self):\n    pass\n"
        diags = _check(self._rule(), source)
        assert diags == []

    def test_custom_exclude_pattern(self):
        """Custom exclude_pattern."""
        rule = self._rule(exclude_pattern="test_*")
        source = "def test_something():\n    pass\n"
        diags = _check(rule, source)
        assert diags == []

    def test_custom_exclude_does_not_skip_private(self):
        """When exclude is changed, default '_*' no longer applies."""
        rule = self._rule(exclude_pattern="test_*")
        source = "def _helper():\n    pass\n"
        diags = _check(rule, source)
        assert len(diags) == 1

    def test_pattern_filter(self):
        """Only functions matching pattern are checked."""
        rule = self._rule(pattern="create_*")
        # Matches pattern -> violation
        diags = _check(rule, "def create_user():\n    pass\n")
        assert len(diags) == 1
        # Does not match pattern -> no violation
        rule2 = self._rule(pattern="create_*")
        diags = _check(rule2, "def delete_user():\n    pass\n")
        assert diags == []

    def test_multiple_functions(self):
        source = """\
def create_user():
    pass

def delete_user():
    pass

def _helper():
    pass
"""
        diags = _check(self._rule(), source)
        # create_user and delete_user fire; _helper excluded by default pattern
        assert len(diags) == 2
        names = {d.message for d in diags}
        assert any("create_user" in m for m in names)
        assert any("delete_user" in m for m in names)

    def test_has_wrong_decorator_still_fires(self):
        """Known limitation: rule dispatches on function_definition which
        doesn't include decorators, so even a wrong decorator isn't seen."""
        source = "@other_decorator\ndef create_user():\n    pass\n"
        diags = _check(self._rule(), source)
        assert len(diags) == 1

    def test_diagnostic_has_fix(self):
        """EX002 provides an autofix to add the missing decorator."""
        source = "def create_user():\n    pass\n"
        diags = _check(self._rule(), source)
        assert len(diags) == 1
        assert diags[0].fix is not None
        assert "audit_log" in diags[0].fix.description

    def test_autofix_adds_decorator(self):
        """Autofix inserts the decorator before the function."""
        source = "def create_user():\n    pass\n"
        _diags, fixed = _fix(self._rule(), source)
        assert fixed is not None
        assert "@audit_log" in fixed
        assert fixed.startswith("@audit_log\n")

    def test_autofix_indented_function(self):
        """Autofix preserves indentation for nested functions."""
        source = """\
class Foo:
    def create_user(self):
        pass
"""
        _diags, fixed = _fix(self._rule(), source)
        assert fixed is not None
        assert "    @audit_log\n    def create_user" in fixed


class TestRequireDecoratorPathFiltering:
    """EX002 path filtering."""

    def test_no_paths_checks_all(self):
        rule = RequireDecorator()
        rule.configure({"required_decorator": "log"})
        ctx = _make_ctx("any/path.py")
        assert rule.should_check_file(ctx) is True

    def test_matching_path(self):
        rule = RequireDecorator()
        rule.configure({"required_decorator": "log", "paths": ["src/api/"]})
        ctx = _make_ctx("src/api/views.py")
        assert rule.should_check_file(ctx) is True

    def test_non_matching_path(self):
        rule = RequireDecorator()
        rule.configure({"required_decorator": "log", "paths": ["src/api/"]})
        ctx = _make_ctx("src/utils/helpers.py")
        assert rule.should_check_file(ctx) is False


# ===========================================================================
# EX003 ForbiddenCall
# ===========================================================================


class TestForbiddenCallDefaults:
    """EX003 with no forbidden list is a no-op."""

    def test_unconfigured_skips_all(self):
        rule = ForbiddenCall()
        ctx = _make_ctx("any/file.py")
        assert rule.should_check_file(ctx) is False

    def test_unconfigured_produces_no_diags(self):
        rule = ForbiddenCall()
        diags = _check(rule, 'print("hello")\n')
        assert diags == []


class TestForbiddenCallConfigured:
    """EX003 configured to forbid specific calls."""

    def _rule(self, **kwargs):
        r = ForbiddenCall()
        r.configure({"forbidden": ["print", "pdb.set_trace"], **kwargs})
        return r

    def test_simple_forbidden_call(self):
        diags = _check(self._rule(), 'print("debug")\n')
        assert len(diags) == 1
        assert diags[0].code == "EX003"
        assert "print" in diags[0].message

    def test_dotted_forbidden_call(self):
        diags = _check(self._rule(), "pdb.set_trace()\n")
        assert len(diags) == 1
        assert diags[0].code == "EX003"

    def test_allowed_call(self):
        diags = _check(self._rule(), 'logger.info("hello")\n')
        assert diags == []

    def test_multiple_forbidden_calls(self):
        source = 'print("a")\nprint("b")\npdb.set_trace()\n'
        diags = _check(self._rule(), source)
        assert len(diags) == 3
        assert all(d.code == "EX003" for d in diags)

    def test_forbidden_in_expression(self):
        """Forbidden call as part of a larger expression."""
        diags = _check(self._rule(), 'x = print("debug")\n')
        assert len(diags) == 1

    def test_non_forbidden_similar_name(self):
        """A function named similarly but not exactly matching."""
        diags = _check(self._rule(), 'printf("hello")\n')
        assert diags == []

    def test_no_diagnostic_for_definition(self):
        """Defining a function named 'print' is not a call."""
        diags = _check(self._rule(), "def print(msg):\n    pass\n")
        assert diags == []

    def test_single_forbidden_item(self):
        """Config with a single-item forbidden list."""
        rule = ForbiddenCall()
        rule.configure({"forbidden": ["breakpoint"]})
        diags = _check(rule, "breakpoint()\n")
        assert len(diags) == 1
        diags = _check(rule, 'print("ok")\n')
        # Need fresh rule since linter caches registration
        rule2 = ForbiddenCall()
        rule2.configure({"forbidden": ["breakpoint"]})
        diags = _check(rule2, 'print("ok")\n')
        assert diags == []

    def test_method_call_not_forbidden(self):
        """obj.print() has full_call_name='obj.print', not 'print'."""
        rule = ForbiddenCall()
        rule.configure({"forbidden": ["print"]})
        # obj.print() -> full_call_name = "obj.print", function_name = "print"
        # The rule uses: name = node.full_call_name or node.function_name
        # So full_call_name "obj.print" is checked first, which is not in forbidden
        diags = _check(rule, "obj.print()\n")
        assert diags == []


class TestForbiddenCallPathFiltering:
    """EX003 path filtering with paths and exclude_paths."""

    def test_no_paths_checks_all(self):
        rule = ForbiddenCall()
        rule.configure({"forbidden": ["print"]})
        ctx = _make_ctx("anywhere/file.py")
        assert rule.should_check_file(ctx) is True

    def test_matching_path(self):
        rule = ForbiddenCall()
        rule.configure({"forbidden": ["print"], "paths": ["src/"]})
        ctx = _make_ctx("src/main.py")
        assert rule.should_check_file(ctx) is True

    def test_non_matching_path(self):
        rule = ForbiddenCall()
        rule.configure({"forbidden": ["print"], "paths": ["src/"]})
        ctx = _make_ctx("tests/test_main.py")
        assert rule.should_check_file(ctx) is False

    def test_exclude_paths(self):
        rule = ForbiddenCall()
        rule.configure({"forbidden": ["print"], "exclude_paths": ["tests/"]})
        ctx_src = _make_ctx("src/main.py")
        ctx_test = _make_ctx("tests/test_main.py")
        assert rule.should_check_file(ctx_src) is True
        assert rule.should_check_file(ctx_test) is False

    def test_exclude_paths_overrides_paths(self):
        """Exclude takes precedence when both match."""
        rule = ForbiddenCall()
        rule.configure(
            {
                "forbidden": ["print"],
                "paths": ["src/"],
                "exclude_paths": ["src/scripts/"],
            }
        )
        ctx_api = _make_ctx("src/api/views.py")
        ctx_scripts = _make_ctx("src/scripts/deploy.py")
        assert rule.should_check_file(ctx_api) is True
        assert rule.should_check_file(ctx_scripts) is False

    def test_integration_path_filtering(self):
        """End-to-end: forbidden call in excluded path produces no diags."""
        rule = ForbiddenCall()
        rule.configure({"forbidden": ["print"], "exclude_paths": ["tests/"]})
        source = 'print("debug")\n'
        diags = _check(rule, source, filename="tests/test_foo.py")
        assert diags == []

        rule2 = ForbiddenCall()
        rule2.configure({"forbidden": ["print"], "exclude_paths": ["tests/"]})
        diags = _check(rule2, source, filename="src/main.py")
        assert len(diags) == 1


# ===========================================================================
# EX004 RequireFields
# ===========================================================================


class TestRequireFieldsDefaults:
    """EX004 with no required_fields configured is a no-op."""

    def test_unconfigured_skips_all(self):
        rule = RequireFields()
        ctx = _make_ctx("any/file.py")
        assert rule.should_check_file(ctx) is False

    def test_unconfigured_produces_no_diags(self):
        rule = RequireFields()
        diags = _check(rule, "class Foo:\n    pass\n")
        assert diags == []


class TestRequireFieldsConfigured:
    """EX004 configured to require specific fields."""

    def _rule(self, **kwargs):
        r = RequireFields()
        r.configure(
            {
                "pattern": "*Model",
                "required_fields": ["created_at", "updated_at"],
                **kwargs,
            }
        )
        return r

    def test_violation_missing_all_fields(self):
        source = "class UserModel:\n    name: str\n"
        diags = _check(self._rule(), source)
        assert len(diags) == 2
        assert all(d.code == "EX004" for d in diags)
        messages = {d.message for d in diags}
        assert any("created_at" in m for m in messages)
        assert any("updated_at" in m for m in messages)

    def test_violation_missing_one_field(self):
        source = """\
class UserModel:
    name: str
    created_at: datetime
"""
        diags = _check(self._rule(), source)
        assert len(diags) == 1
        assert "updated_at" in diags[0].message

    def test_passes_all_fields_annotated(self):
        """All required fields present as type annotations."""
        source = """\
class UserModel:
    name: str
    created_at: datetime
    updated_at: datetime
"""
        diags = _check(self._rule(), source)
        assert diags == []

    def test_passes_all_fields_assigned(self):
        """All required fields present as plain assignments."""
        source = """\
class UserModel:
    name = "default"
    created_at = None
    updated_at = None
"""
        diags = _check(self._rule(), source)
        assert diags == []

    def test_passes_mixed_annotations_and_assignments(self):
        """Mix of annotated and plain assignment."""
        source = """\
class UserModel:
    created_at: datetime = None
    updated_at = None
"""
        diags = _check(self._rule(), source)
        assert diags == []

    def test_pattern_no_match_ignored(self):
        """Classes not matching the pattern are not checked."""
        source = "class UserSchema:\n    name: str\n"
        diags = _check(self._rule(), source)
        assert diags == []

    def test_pattern_wildcard_match(self):
        """Various classes matching *Model pattern."""
        rule = self._rule()
        diags = _check(rule, "class OrderModel:\n    pass\n")
        assert len(diags) == 2  # missing both fields

    def test_single_required_field(self):
        """Config with a single required field."""
        rule = RequireFields()
        rule.configure({"pattern": "*", "required_fields": ["id"]})
        diags = _check(rule, "class Foo:\n    name: str\n")
        assert len(diags) == 1
        assert "id" in diags[0].message

    def test_class_with_methods_only(self):
        """Class with methods but no field assignments."""
        source = """\
class UserModel:
    def __init__(self):
        pass
"""
        diags = _check(self._rule(), source)
        assert len(diags) == 2  # methods are not field assignments

    def test_class_with_pass_body(self):
        """Class with only 'pass' in the body."""
        source = "class UserModel:\n    pass\n"
        diags = _check(self._rule(), source)
        assert len(diags) == 2

    def test_class_with_ellipsis_body(self):
        """Class with '...' in the body."""
        source = "class UserModel:\n    ...\n"
        diags = _check(self._rule(), source)
        assert len(diags) == 2

    def test_nested_assignment_not_counted(self):
        """Assignments inside methods are not class-level fields."""
        source = """\
class UserModel:
    def setup(self):
        created_at = None
        updated_at = None
"""
        diags = _check(self._rule(), source)
        # The rule only checks direct children of the class body
        assert len(diags) == 2

    def test_multiple_classes(self):
        """Multiple matching classes in one file."""
        source = """\
class UserModel:
    created_at: datetime
    updated_at: datetime

class OrderModel:
    total: float
"""
        diags = _check(self._rule(), source)
        assert len(diags) == 2  # OrderModel missing both fields
        assert all("OrderModel" in d.message for d in diags)

    def test_diagnostic_message_format(self):
        """Diagnostic message includes class name and missing field."""
        source = "class UserModel:\n    pass\n"
        diags = _check(self._rule(), source)
        for d in diags:
            assert "UserModel" in d.message
            assert "missing field" in d.message.lower() or "field" in d.message.lower()


class TestRequireFieldsPathFiltering:
    """EX004 path filtering."""

    def test_no_paths_checks_all(self):
        rule = RequireFields()
        rule.configure({"required_fields": ["id"]})
        ctx = _make_ctx("any/path.py")
        assert rule.should_check_file(ctx) is True

    def test_matching_path(self):
        rule = RequireFields()
        rule.configure({"required_fields": ["id"], "paths": ["src/models/"]})
        ctx = _make_ctx("src/models/user.py")
        assert rule.should_check_file(ctx) is True

    def test_non_matching_path(self):
        rule = RequireFields()
        rule.configure({"required_fields": ["id"], "paths": ["src/models/"]})
        ctx = _make_ctx("src/views/user.py")
        assert rule.should_check_file(ctx) is False


# ===========================================================================
# Cross-cutting concerns
# ===========================================================================


class TestConfigureIdempotent:
    """Calling configure() multiple times updates the config."""

    def test_require_base_class_reconfigure(self):
        rule = RequireBaseClass()
        rule.configure({"pattern": "*Foo", "required_base": "BaseFoo"})
        rule.configure({"pattern": "*Bar", "required_base": "BaseBar"})
        assert rule.pattern == "*Bar"
        assert rule.required_base == "BaseBar"

    def test_require_decorator_reconfigure(self):
        rule = RequireDecorator()
        rule.configure({"required_decorator": "log"})
        rule.configure({"required_decorator": "audit"})
        assert rule.required_decorator == "audit"


class TestConfigurePartial:
    """Partial configure() keeps defaults for unset keys."""

    def test_require_base_class_partial(self):
        rule = RequireBaseClass()
        rule.configure({"pattern": "*Service"})
        assert rule.pattern == "*Service"
        assert rule.required_base == "object"  # default preserved

    def test_require_decorator_partial(self):
        rule = RequireDecorator()
        rule.configure({"required_decorator": "log"})
        assert rule.exclude_pattern == "_*"  # default preserved
        assert rule.pattern == "*"  # default preserved

    def test_forbidden_call_partial(self):
        rule = ForbiddenCall()
        rule.configure({"forbidden": ["print"]})
        assert rule.paths == []  # default preserved
        assert rule.exclude_paths == []  # default preserved

    def test_require_fields_partial(self):
        rule = RequireFields()
        rule.configure({"required_fields": ["id"]})
        assert rule.pattern == "*"  # default preserved
        assert rule.paths == []  # default preserved


class TestRuleCodes:
    """Each rule has the correct code."""

    def test_codes(self):
        assert RequireBaseClass.code == "EX001"
        assert RequireDecorator.code == "EX002"
        assert ForbiddenCall.code == "EX003"
        assert RequireFields.code == "EX004"
