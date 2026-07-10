# Runbook: remove the history-analysis cache

Back up and remove only:

- `$CODEX_HOME/codex-fleet/history-analysis.md`
- `$CODEX_HOME/codex-fleet/history-analysis.meta`

Do not read or modify session-history files. Do not remove roles, features,
plugins, guidance, or other state. Verify both cache files are absent.
