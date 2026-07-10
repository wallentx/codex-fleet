---
name: consolidate
description: Merge overlapping Codex guidance into crisp low-token rules. Use when the user invokes `/consolidate`, asks to reduce duplicate guidance, combine semantically similar rules, or shrink learned memories without losing behavior.
---

# Consolidate

## Inputs

- Active guidance files in the repository.
- Repository root, defaulting to the current working directory.

## Output

Write `learning_consolidation_proposal.md` with replacement proposals. Do not edit guidance directly.

## Workflow

```bash
python3 ../../scripts/learn.py consolidate --root .
```

Use a custom output when requested:

```bash
python3 ../../scripts/learn.py consolidate --root . --output consolidation.md
```

## Merge Rules

- Preserve behavioral constraints exactly.
- Prefer the shortest clear wording among duplicate rules.
- Propose replacements in markdown; apply accepted replacements through `/apply-learning`.
- Treat low similarity as unique guidance and leave it alone.
