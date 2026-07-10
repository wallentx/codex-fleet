# Runbook: configure history-derived specialist agents

Read `$CODEX_HOME/codex-fleet/history-analysis.md`; do not rescan session
history. Inspect the live model catalog and active config, then create a compact
fleet whose routing boundaries follow the cached evidence.

## Roles

- Always include a fast read-only scout, a strong read-only correctness
  reviewer, an orchestrator for genuinely decomposable work, a routine
  implementation role, and a build/validation role unless equivalent
  fleet-owned roles already cover them.
- Add platform, shell, infrastructure, performance, MCP, or other specialists
  only when the cache supports a distinct routing boundary.
- Do not create `learning_auditor`, `learning_reviewer`, or
  `automation_engineer`; those belong to the learning-pipeline runbook.
- Each role uses a verified model and effort, explicit provider, explicit
  `read-only` or `workspace-write` sandbox, a concise router description, and
  focused developer instructions. Never use `danger-full-access`.
- Orchestrators may delegate; leaf roles must not recursively delegate.

Write role files under `$CODEX_HOME/agents/<role>.toml` and merge matching
`[agents.<role>]` declarations into config without duplicate tables. Prefer
`agents.max_depth = 2` and a verified job timeout. Never add `max_threads` under
multi-agent v2.

## Ownership state and reruns

Maintain `$CODEX_HOME/codex-fleet/agents-installed.txt` atomically with this
first line and one sorted role name per subsequent line:

```text
# codex-fleet:agents:v1
```

On rerun, compare the prior state with the newly selected roles. Back up and
remove stale config declarations and role files only when the prior state proves
Codex Fleet owns them. Preserve every unrelated agent.

Validate TOML, role-file existence, exact state/config correspondence, unique
role names, and every model/provider/effort/sandbox value against live Codex.
