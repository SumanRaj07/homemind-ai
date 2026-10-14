# Contributing to HomeMind AI

Thanks for your interest! HomeMind AI is a community-driven, local-first
project.

## Getting started

1. Read `INSTALL.md` and get the app running locally.
2. Run the test suite: `pytest` (uses the mock provider — no model needed).
3. Run the linter: `ruff check src tests frontend desktop`.

## Ground rules

- **Local-first, always.** No cloud fallbacks, no telemetry, no accounts.
- **Privacy is a feature.** New features must not log prompts, document
  contents or memory contents. Add a test in `tests/privacy/` if your change
  touches data handling.
- **Security is a feature.** New inputs get validation + tests in
  `tests/security/`. New tools default to `read` permission.
- **Small, verifiable PRs.** One feature per PR, with tests.
- **No secrets in commits.** API keys, tokens and private datasets do not
  belong in the repo.

## Pull request checklist

- [ ] `pytest` passes (all 78+ tests)
- [ ] `ruff check src tests frontend desktop` passes
- [ ] New behavior has tests (unit + integration where it fits)
- [ ] Docs updated (`README.md`, `docs/`, or docstrings)
- [ ] No new cloud dependencies

## Code style

- Type hints on public functions; docstrings on modules and public APIs.
- Keep modules small and single-purpose; avoid circular imports.
- Follow the existing layered layout (`api → services → providers/storage`).

## Reporting bugs / requesting features

Open a GitHub issue with: what you did, what you expected, what happened,
and your environment (OS, Python version, `pip freeze` excerpt). For security
issues, see `SECURITY.md` — report privately.
