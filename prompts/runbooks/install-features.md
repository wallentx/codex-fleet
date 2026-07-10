# Runbook: configure Codex Fleet features

Read the installed Codex feature inventory, model catalog, active config, and
the sanitized history cache. Configure only supported features that materially
help the selected fleet.

## Required behavior

- Prefer the strongest available multi-agent-v2 model whose documented effort
  supports automatic delegation; otherwise use the strongest verified fallback.
- Set `model_provider` explicitly and preserve unrelated model-provider config.
- Before enabling `multi_agent_v2`, remove `agents.max_threads` after backing up
  the config, validate its absence, and only then enable v2.
- Never configure `agents.max_threads` while v2 is enabled or planned.
- Consider supported multi-agent, fanout, deferred execution, code mode,
  permissions, runtime metrics, token budgeting, memories, goals, hooks, web
  search, terminal guidance, and related capabilities only when listed by this
  Codex build and justified by the history cache.
- Never enable removed or deprecated features.

## Ownership state

Maintain `$CODEX_HOME/codex-fleet/features-enabled-by-fleet.txt` atomically.
Its first line must be:

```text
# codex-fleet:features:v1
```

List one feature per subsequent line, sorted. Record only features changed from
disabled to enabled by Codex Fleet. Preserve entries from an earlier run while
the fleet still owns them. Never record a feature that was already enabled
before Codex Fleet first changed it.

Validate strict config loading, model/effort/provider compatibility, feature
stages, and the hard `multi_agent_v2`/`max_threads` incompatibility.
