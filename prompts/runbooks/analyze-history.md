# Runbook: build the sanitized history-analysis cache

Create or refresh these files:

- `$CODEX_HOME/codex-fleet/history-analysis.md`
- `$CODEX_HOME/codex-fleet/history-analysis.meta`

This runbook is the only phase allowed to perform the expensive session-history
analysis. Later runbooks consume its sanitized output and must not rescan history.

## Analyze

1. Inspect the active Codex version, diagnostics, state metadata, and available
   rollout files without changing them.
2. Prefer up to 120 recent root sessions or roughly 90 days. Weight root user
   sessions more heavily than guardian, review, or spawned-agent sessions.
3. Support the history formats the installed Codex version actually uses,
   including compressed rollouts when readable with local tools.
4. Ignore system prompts, duplicated context, boilerplate, social filler, raw
   tool noise, secrets, transient failures, and one-off state.
5. Aggregate recurring workloads, repositories and environments, languages,
   tools, task complexity, risk, permissions, validation patterns, delegation
   opportunities, stable user corrections, and candidate specialist boundaries.

## Cache contract

Write `history-analysis.md` atomically with this exact first line:

```text
<!-- codex-fleet:history-analysis:v1 -->
```

Include sanitized sections for source inventory, workload evidence, stable
preferences, common tools, risk/permission patterns, candidate roles, and
confidence/limitations. Use aggregates only; never quote conversations.

Write `history-analysis.meta` atomically as simple `key=value` lines with:

```text
schema=1
generated_at=<UTC ISO-8601 timestamp>
codex_version=<version>
root_sessions=<integer>
supporting_sessions=<integer>
oldest_session=<YYYY-MM-DD or unknown>
newest_session=<YYYY-MM-DD or unknown>
```

Set both files to user-read/write only. Validate the marker, metadata schema,
integer counts, secret filtering, and non-empty candidate-role evidence.
