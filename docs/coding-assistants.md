# AI Coding Assistants

Rude welcomes contributions that involve AI coding assistants (Claude, Codex,
Cursor, Copilot, and similar tools). This page documents how to use them
responsibly so the project stays healthy.

This guidance complements the general [Contributing](contributing.md) guide --
all standard rules still apply.

## Process

AI-assisted changes go through the same pipeline as any other contribution:

- Development setup: see [Contributing](contributing.md) for Python, Rust,
  and `uv` requirements.
- Code style: enforced by `ruff` and `clippy`, runnable via `make check`.
- Tests: `make test`.

Open a pull request when `make check && make test` passes locally.

## Commit conventions

Commit messages follow
[Conventional Commits v1.0.0](https://www.conventionalcommits.org/en/v1.0.0/).
The subject line stays under 50 characters; the body wraps at 72. Examples
already in the repo:

- `feat: add F-code severity overrides`
- `fix(analyzer): handle __future__ imports`
- `refactor(scope): simplify binding lookup`

## Human responsibility

An AI assistant is a tool, not a contributor. The human who submits a patch
is responsible for:

- **Review** -- reading every line of generated code and understanding it.
- **Verification** -- running `make check && make test` and confirming the
  output, not just trusting the assistant's "all green" claim.
- **Licensing** -- Rude is MIT-licensed; contributions must be compatible.
- **Commit message and PR description** -- these must accurately describe
  the change and the human's understanding of it.

Don't ship code you can't explain.

## Attribution

When an AI tool materially contributed to a patch, add an `Assisted-by`
trailer at the end of the commit message:

```
Assisted-by: AGENT_NAME:MODEL_VERSION [TOOL1] [TOOL2]
```

Where:

- `AGENT_NAME` is the AI tool or framework (`Claude`, `Codex`, `Cursor`...).
- `MODEL_VERSION` is the specific model (`claude-opus-4-7`, `gpt-5`...).
- `[TOOL1] [TOOL2]` are optional specialized analysis tools used
  (e.g., `ruff`, `mypy`, `clippy`). Basic development tools (git, uv, cargo,
  make, editors) are not listed.

Full example:

```
feat(rules): add E999 catch-all for syntax errors

Fall back to a generic diagnostic when tree-sitter reports ERROR nodes
that don't match any existing rule, so users get actionable output
instead of silent skips.

Assisted-by: Claude:claude-opus-4-7 ruff
```

## Prohibited behaviors

AI agents must not:

- **Set `Author:` or `Committer:` fields.** These identify the human
  responsible for the contribution. Use `Assisted-by` instead.
- **Add `Signed-off-by:` on behalf of anyone.** Rude does not currently
  require a DCO, but authorship signatures must reflect real humans.
- **Embed session metadata.** Internal agent IDs, reasoning chains, memory
  dumps, or harness-specific trailers don't belong in commit messages, PR
  descriptions, or committed files.
- **Act without authorization.** Opening issues, PRs, or comments on
  Rude's GitHub without explicit permission from the submitter is not OK.

## Why this exists

AI tools scale quickly -- small quality problems become large ones fast. By
being explicit about attribution and human responsibility, Rude keeps a
clear audit trail of what AI contributed, while making sure contributions
still go through a human who understands them.
