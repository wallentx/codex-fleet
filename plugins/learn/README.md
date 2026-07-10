# learn

`learn` is a Codex CLI plugin that brings a `/learn` style workflow to Codex. It analyzes recent sessions, proposes durable rules or skills, and keeps persistent guidance untouched until the user explicitly applies selected items.

## Install

Use this directory as a local Codex plugin source. The canonical manifest is `.codex-plugin/plugin.json`; `plugin.yaml` is included for human-readable command metadata and compatibility with plugin tooling that expects YAML.

For a personal local install, place or symlink this checkout at `~/plugins/learn`, make sure `~/.agents/plugins/marketplace.json` has a `learn` entry pointing to `./plugins/learn`, then run `codex plugin add learn@personal` where `personal` is the marketplace name.

For direct script testing from this checkout:

```bash
python3 scripts/learn.py learn --file examples/mock_history.jsonl --root examples/mock_repo
python3 scripts/learn.py apply-learning --proposal learning_proposal.md --root examples/mock_repo --all --yes
```

## Workflows

### `/learn`

Runs the `learn` skill. It reads session history from stdin, `--file`, or recent Codex history locations, then writes `learning_proposal.md` in the current directory.

It classifies observations as:

- `Rule`: broad guardrails or explicit user preferences.
- `Skill`: reusable multi-step procedures.
- `Repository Note`: local project or environment facts.
- `Ignore`: secrets, temporary state, low-confidence guesses, and one-off bug fixes.

The command writes runtime state to `.codex/learn/state.json` so re-running on the same session produces a zero-change proposal. It does not edit `AGENTS.md`, `SKILL.md`, or other guidance files.

### `/apply-learning`

Reads `learning_proposal.md`, lets the user apply everything, selected classifications, or individual item IDs, then:

- checks git state and warns when the worktree is dirty,
- writes lightweight backups under `.codex/learn/backups/`,
- edits only selected target files,
- stages changed files with `git add` for review.

### `/forget`

Audits active guidance and writes a deletion/deprecation proposal for stale, contradictory, or session-specific rules.

### `/consolidate`

Finds overlapping guidance and proposes lower-token replacements.

### `/lint-learning`

Writes a markdown health report for duplicate rules, conflicts, vague instructions, and skills missing examples.

## CLI Reference

```bash
python3 scripts/learn.py learn [--file PATH] [--output learning_proposal.md] [--force]
python3 scripts/learn.py apply-learning [--proposal learning_proposal.md] [--all] [--classification Rule] [--item ITEM_ID]
python3 scripts/learn.py forget [--output learning_forget_proposal.md]
python3 scripts/learn.py consolidate [--output learning_consolidation_proposal.md]
python3 scripts/learn.py lint-learning [--output learning_lint_report.md]
```

All commands accept `--root PATH` to operate on a repository other than the current directory.

## Safety Model

- Proposal-only by default: `/learn`, `/forget`, and `/consolidate` generate markdown proposals.
- Secret filters run before proposal writing and again on the final proposal body.
- `apply-learning` is the only workflow that edits guidance files.
- Applying changes requires an explicit selection mode: `--all`, `--classification`, `--item`, or interactive prompts.
- Backups are created before each file edit.

## Tests

```bash
python3 -m unittest discover -s tests
```
