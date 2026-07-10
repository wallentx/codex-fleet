---
name: lint-learning
description: Audit Codex learning guidance health. Use when the user invokes `/lint-learning`, asks for duplicate rules, conflicting guidance, vague instructions, missing examples, or diagnostics for AGENTS/SKILL learning content.
---

# Lint Learning

## Inputs

- Active guidance files in the repository.
- Repository root, defaulting to the current working directory.

## Output

Write `learning_lint_report.md`. Do not modify guidance.

## Workflow

```bash
python3 ../../scripts/learn.py lint-learning --root .
```

Use a custom output when requested:

```bash
python3 ../../scripts/learn.py lint-learning --root . --output learning_health.md
```

## Report Sections

- Health metrics.
- Duplicate rules.
- Conflicting rules.
- Vague or ambiguous guidance.
- Skills missing examples.

Use `/consolidate` for merge proposals and `/forget` for deletion proposals after reviewing the report.
