# Runbook: validate and summarize Codex Fleet state

Validate the selected operation and every remaining fleet-owned component using
the ownership files under `$CODEX_HOME/codex-fleet/`. Do not rescan session
history and do not add new components.

## Validation

- Parse active TOML and use strict Codex diagnostics when supported.
- Verify every state-file marker and reject duplicate or malformed entries.
- Verify every fleet-owned role has one config declaration and one role file,
  with supported model/provider/effort/sandbox values.
- Verify owned features are supported and enabled after install, or absent from
  ownership state after uninstall.
- Fail if `multi_agent_v2` and `agents.max_threads` coexist.
- Verify the history cache marker and metadata when the cache remains selected.
- Preserve unrelated agents, features, guidance, plugins, and MCP settings.

## Fleet manifest

If any fleet-owned roles remain, write `$CODEX_HOME/agents/FLEET.md` with a
sanitized evidence summary sourced only from the cache, feature decisions,
routing examples, learning-pipeline status, validation commands, date, and Codex
version. Include this exact block with one row per role named in the union of
`agents-installed.txt` and `learning-installed.txt`, and no extra content inside
the markers:

```markdown
<!-- codex-fleet:roles:start -->
| Role | Model | Provider | Effort | Sandbox | Purpose |
| --- | --- | --- | --- | --- | --- |
| `<role_name>` | `<model>` | `<provider>` | `<effort>` | `<sandbox>` | <concise purpose> |
<!-- codex-fleet:roles:end -->
```

If no fleet-owned roles remain, back up and remove only the fleet-owned
`FLEET.md`. Finish with pass/fail status and any limitation.
