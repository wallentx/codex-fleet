---
name: forget
description: Audit active Codex guidance for stale, contradictory, obsolete, or session-specific learnings and write a deletion proposal. Use when the user invokes `/forget`, asks to prune learned rules, remove outdated repository notes, or clean up decayed agent guidance without immediately deleting anything.
---

# Forget

## Inputs

- Existing guidance in `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `README.md`, `.codex/`, `.claude/`, and `skills/**/SKILL.md`.
- Repository root, defaulting to the current working directory.

## Output

Write `learning_forget_proposal.md`. Do not delete files or edit guidance.

## Workflow

```bash
python3 ../../scripts/learn.py forget --root .
```

Use a custom output when requested:

```bash
python3 ../../scripts/learn.py forget --root . --output stale_guidance.md
```

## Detection Targets

- Temporary hacks, debug-only notes, or line-specific fix memories.
- Deprecated or obsolete repository notes.
- Rules that clearly refer to a past session instead of future behavior.

Apply accepted deletions through `/apply-learning`, not this skill.
