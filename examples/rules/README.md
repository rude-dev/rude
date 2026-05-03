# Example Rules

These rules demonstrate how to write custom rules for rude. They are not
included in the default rule set.

## Usage

Add them as local rules in your `pyproject.toml`:

```toml
[tool.rude]
local-rules = [
    "examples/rules/patterns",
    "examples/rules/hygiene",
    "examples/rules/templates",
]
```

## Available examples

### templates/ (EX001-EX004)
Configurable rule templates: require base class, require decorator, forbidden calls,
require fields. All require configuration in `[tool.rude.rules.EXNNN]` to do anything.

### patterns/ (PAT001-PAT010)
Configurable code pattern rules: function complexity, nesting depth, class size.

### hygiene/ (META001-META003)
Code hygiene rules: TODO tracking, blanket noqa, type: ignore without code.

## Writing your own rules

See the [Custom Rules Guide](https://rude.readthedocs.io/en/latest/guide/custom-rules.html).
