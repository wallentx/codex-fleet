# Runbook: remove Codex Fleet-owned specialist agents

Read `$CODEX_HOME/codex-fleet/agents-installed.txt`. If absent, report the
component as already absent and do nothing.

For each valid listed role, back up config and its role file, remove exactly its
`[agents.<role>]` declaration, and remove exactly its owned role file. Never
remove a role not listed in the ownership state. Do not touch learning-pipeline
roles; their separate runbook owns them. Remove `agents-installed.txt` after
successful cleanup.

Remove fleet-level `agents.max_depth` or job-timeout settings only when no
fleet-owned agents of either class remain and their removal is safe. Never add
`max_threads`. Validate TOML and confirm no listed declaration or file remains.
