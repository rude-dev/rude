# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in rude, please report it
**privately** via [GitHub Security Advisories](https://github.com/rude-dev/rude/security/advisories/new).

Do not open a public issue for security vulnerabilities.

## Scope

rude is a developer CLI tool that reads Python source files and outputs
diagnostics. It runs with the user's filesystem permissions.

Security-relevant areas include:

- **Unsafe Rust code** (`src/ts.rs`) -- tree-sitter FFI with `transmute` and `from_raw_parts`
- **Local rule loading** -- `local-rules` config executes arbitrary Python via `importlib`
- **Plugin system** -- entry point plugins run with full process privileges
- **File operations** -- `--fix` mode writes to files (symlink protection in place)
- **CI/CD** -- GitHub Actions workflows with trusted publishing

## Trust Model

rude executes third-party code in two situations:

1. **Plugins** declared via Python entry points (`rude.plugins`). Any
   package installed in the current environment with a `rude.plugins`
   entry point will have its rule classes loaded on the next `rude check`
   invocation. Installing a plugin is equivalent to installing any other
   Python package: you are granting its code the same privileges your
   interpreter has. Only install plugins you trust.

2. **Local rules** declared via `[tool.rude] local-rules = ["..."]` in
   `pyproject.toml`. Any file listed here is imported at startup and its
   `Rule` / `LineRule` subclasses are loaded. A malicious `pyproject.toml`
   combined with a malicious local-rule file is functionally equivalent
   to running arbitrary Python. Review `pyproject.toml` and all
   referenced files the same way you would a `setup.py`.

If either of these execution paths are a concern in your CI environment,
run rude against untrusted repositories without installing their
plugins or local rules (for example, pass `--select` to limit to
built-in rule codes).

## Reporting

Use GitHub's private security advisory workflow linked above. I read
these within a working day on weekdays.

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |
