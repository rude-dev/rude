.DEFAULT_GOAL := check

.PHONY: install build dev rust-fmt rust-lint python-fmt python-lint fmt lint \
        typecheck test test-fast test-all bench bench-rust bench-python \
        bench-comparative bench-save check all clean docs docs-serve \
        docs-clean generate changelog help

install:  ## Sync Python dependencies
	uv sync

build:  ## Build Rust extension (release)
	uv run maturin develop --release

dev:  ## Build Rust extension (debug, faster compile)
	uv run maturin develop

rust-fmt:
	cargo fmt

rust-lint:
	cargo fmt --check
	cargo clippy --all-targets -- -D warnings

python-fmt:
	uv run ruff format python tests examples scripts
	uv run ruff check --fix python tests examples scripts

python-lint:
	uv run ruff format --check python tests examples scripts
	uv run ruff check python tests examples scripts

fmt: rust-fmt python-fmt  ## Auto-format Python + Rust

lint: rust-lint python-lint  ## Run all linters

typecheck:  ## Run mypy type checking
	uv run mypy

check: build lint typecheck test  ## Run full verification (default)

all: lint typecheck test

test: build  ## Run tests
	uv run pytest -x -q

test-fast: dev  ## Run tests with debug build (faster iteration)
	uv run pytest -x -q

bench: bench-rust bench-python  ## Run all benchmarks
	@echo "All benchmarks complete."

bench-rust: build  ## Run Rust benchmarks (criterion)
	cargo bench

bench-python: build  ## Run Python benchmarks (pytest-benchmark)
	uv run --group bench pytest benches/python/ --benchmark-only -q

bench-comparative: build  ## Run comparative benchmark (rude vs flake8 vs ruff)
	uv run --group bench python benches/comparative/compare.py

bench-save: build  ## Run Python benchmarks and save baseline
	uv run --group bench pytest benches/python/ --benchmark-only --benchmark-save=baseline -q

clean:  ## Remove build artifacts and caches
	rm -rf .cache .coverage htmlcov dist build *.egg-info target/release target/debug
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

docs:  ## Build Sphinx documentation
	uv run --group docs sphinx-build -b html docs docs/_build/html

docs-serve:  ## Serve docs with live-reload
	uv run --group docs sphinx-autobuild docs docs/_build/html --open-browser

docs-clean:  ## Remove built documentation
	rm -rf docs/_build

generate:  ## Regenerate node type mappings
	uv run python scripts/generate_node_types.py

changelog:  ## Generate the changelog from conventional commits
	git cliff -o CHANGELOG.md

help:  ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | \
		awk -F ':.*## ' '{printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
