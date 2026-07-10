# Repository Guidelines

## Project Structure & Module Organization

The root `install.sh` provides componentized install and uninstall flows driven by the bounded prompts in `prompts/runbooks/`. Marketplace metadata lives in `.agents/plugins/marketplace.json`. The bundled Learn plugin is under `plugins/learn/`: its dependency-free Python engine is `scripts/learn.py`, workflow instructions are in `skills/*/SKILL.md`, manifests are in `.codex-plugin/plugin.json` and `plugin.yaml`, and proposal assets are in `templates/`. Tests live in `plugins/learn/tests/`; `examples/` contains fixtures and sample output, not production state.

## Build, Test, and Development Commands

There is no compilation step or package manager.

- `./install.sh --dry-run` verifies prerequisites and prints the resolved components and runbooks without changing Codex state.
- `./install.sh` installs the plugin and runs fleet configuration; use an authenticated Codex CLI 0.144.0 or newer.
- `./install.sh --uninstall --components <ids>` removes fleet-owned components in reverse dependency order.
- `cd plugins/learn && python3 -m unittest discover -s tests` runs all tests.
- `sh -n install.sh` and `sh -n plugins/learn/hooks/post-session.sh` check POSIX shell syntax.
- `cd plugins/learn && python3 scripts/learn.py learn --file examples/mock_history.jsonl --root examples/mock_repo --output /tmp/learning_proposal.md --no-state-write` exercises the learning workflow without adding generated output to the checkout.

## Coding Style & Naming Conventions

Keep shell code POSIX-compatible: use `set -eu`, quote expansions, indent bodies by two spaces, name functions in `snake_case`, and reserve `UPPER_SNAKE_CASE` for configuration and environment variables. Python uses four spaces, type hints, standard-library imports, `snake_case` functions, `PascalCase` classes, and uppercase constants. Name skill directories and commands in kebab-case, such as `apply-learning`. JSON and YAML use two-space indentation. No formatter or linter is configured, so match nearby code and keep the canonical plugin JSON aligned with human-readable YAML metadata.

## Testing Guidelines

Tests use `unittest`; add methods named `test_<behavior>` to the relevant `test_*.py` module. Prefer `TemporaryDirectory` and mocks so tests never alter real guidance or Codex state. Add regression coverage for both successful behavior and safety boundaries such as secret filtering, path handling, backups, ownership, dependency resolution, and explicit-selection requirements. No numeric coverage threshold is defined.

## Commit & Pull Request Guidelines

Follow the repository's observed Conventional Commit style: concise, imperative subjects such as `feat: add history filter`, `fix: preserve plugin state`, or `docs: clarify dry-run`. Keep pull requests focused. Explain motivation and user-visible effects, link relevant issues, and list exact validation commands and results. Include screenshots only for visual changes; for CLI or workflow changes, include representative terminal output instead.

## Security & Generated Files

Never commit credentials, raw private session history, `.codex/` state, generated learning proposals, logs, or temporary files. Run installer changes with `--dry-run` before testing mutations against a real `CODEX_HOME`.
