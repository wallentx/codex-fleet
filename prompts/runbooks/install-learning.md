# Runbook: configure the reviewed learning pipeline

Read the sanitized history cache without rescanning sessions. Configure these
three fleet-owned trust stages:

- `learning_auditor`: read-only proposal generation; rejects secrets,
  transcript fragments, weak guesses, one-offs, and duplicates.
- `learning_reviewer`: independent read-only `APPROVE`, `REVISE`, or `REJECT`
  decision for every non-empty proposal.
- `automation_engineer`: workspace-write implementation only after reviewer
  approval and explicit user approval for the exact persistent change.

Create or update their role files and config declarations using verified models,
providers, efforts, and sandboxes. Do not alter other roles.

Merge an idempotent section into `$CODEX_HOME/AGENTS.md` delimited exactly by:

```text
<!-- history-derived-fleet:learning-pipeline:start -->
<!-- history-derived-fleet:learning-pipeline:end -->
```

The section must require proposal-only auditing, independent review, a concise
audit trail, and explicit user approval before any persistent memory, guidance,
skill, hook, plugin, script, MCP helper, or local-tool change.

Maintain `$CODEX_HOME/codex-fleet/learning-installed.txt` atomically with:

```text
# codex-fleet:learning:v1
learning_auditor
learning_reviewer
automation_engineer
```

Validate exact state/config/file correspondence and confirm the marked global
guidance block occurs exactly once.
