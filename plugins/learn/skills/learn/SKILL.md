---
name: learn
description: Analyze recent Codex session history and create a learning proposal. Use when the user invokes `/learn`, asks Codex to learn from recent interactions, wants reusable rules or skills proposed from logs, or wants Claude Code style learning without modifying persistent guidance.
---

# Learn

## Inputs

- Session history from stdin, one or more `--file` paths, or auto-discovered recent Codex history.
- Repository root, defaulting to the current working directory.
- Existing guidance in `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `README.md`, `.codex/`, `.claude/`, and `skills/**/SKILL.md`.

## Output

Write `learning_proposal.md` in the current directory. Do not edit persistent guidance files.

## Workflow

Run the engine:

```bash
python3 ../../scripts/learn.py learn --root .
```

When the user supplies a log file:

```bash
python3 ../../scripts/learn.py learn --root . --file session.jsonl
```

When history is piped on stdin:

```bash
python3 ../../scripts/learn.py learn --root . < session.jsonl
```

## Rules

- Treat `/learn` as proposal-only. Do not apply changes to `AGENTS.md`, `SKILL.md`, `.codex/`, `.claude/`, or README files.
- Preserve idempotence through `.codex/learn/state.json`; use `--force` only when the user explicitly wants regeneration.
- Include ignored observations and reasons, but redact secret-like content.
- If the proposal fails the secret scan, stop and report the failure instead of writing guidance.

## Classification

- `Rule`: explicit corrections, "always/never/prefer/avoid" guidance, or broad guardrails.
- `Skill`: reusable multi-step procedures, successful debugging sequences, deploy/release playbooks, or repeatable command workflows.
- `Repository Note`: local constraints such as unsupported tools, project-specific commands, or environment facts.
- `Ignore`: secrets, temporary hacks, social filler, one-off bug state, or low-confidence guesses.
