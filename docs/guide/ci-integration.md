# CI Integration

This guide shows how to integrate Rude into your continuous integration
pipeline.

## GitHub Actions

A minimal workflow that runs Rude alongside Ruff:

```yaml
# .github/workflows/lint.yml
name: Lint
on: [push, pull_request]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install tools
        run: pip install ruff rude

      - name: Ruff (standard rules)
        run: ruff check src/ tests/

      - name: Rude (custom rules)
        run: rude check src/ tests/

      - name: Ruff format check
        run: ruff format --check src/ tests/
```

### Using JSON output for annotations

GitHub Actions can parse structured output. Use `--format json` to produce
machine-readable diagnostics:

```yaml
      - name: Rude lint
        run: |
          rude check --format json src/ > /tmp/rude.json || true
          # Parse and create annotations (example with jq)
          jq -r '"::error file=\(.file),line=\(.line),col=\(.column)::\(.code) \(.message)"' \
            /tmp/rude.json
          # Fail if any errors
          rude check src/
```

## GitLab CI

```yaml
# .gitlab-ci.yml
lint:
  image: python:3.12
  script:
    - pip install ruff rude
    - ruff check src/ tests/
    - rude check src/ tests/
    - ruff format --check src/ tests/
```

## Pre-commit

Rude does not yet provide an official
[pre-commit](https://pre-commit.com/) hook. You can use the `system` hook
type as a workaround:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: rude
        name: rude
        entry: rude check
        language: system
        types: [python]
        pass_filenames: true
```

This requires `rude` to be installed in the environment where pre-commit
runs (e.g., your project's virtualenv).

## Makefile integration

A common pattern for local development and CI:

```makefile
.PHONY: lint format check

lint:
	ruff check src/ tests/
	rude check src/ tests/

format:
	ruff format src/ tests/
	ruff check --fix src/ tests/
	rude check --fix src/ tests/

check: lint
	ruff format --check src/ tests/
```

## Parallel execution in CI

For large codebases, use `--jobs` to parallelize:

```yaml
      - name: Rude lint (parallel)
        run: rude check -j $(nproc) src/
```

This spawns one worker process per CPU, trading memory (~70 MB per worker)
for faster wall time. See the {doc}`quickstart` guide for details on the
parallelism model.

## Fail-fast mode

In CI, you may want to stop on the first error to get faster feedback:

```bash
rude check --fail-fast src/
```

Or limit the number of errors reported:

```bash
rude check --max-errors 20 src/
```
