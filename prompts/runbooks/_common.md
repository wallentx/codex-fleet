# Codex Fleet runbook contract

Execute only the runbook appended below. Complete it end-to-end; do not broaden
scope or merely describe commands.

Runtime paths and selected components are appended by the installer. Treat those
values as authoritative.

## Safety

- Preserve unrelated configuration, roles, providers, plugins, hooks, MCP
  servers, skills, memories, and project settings.
- Before modifying a pre-existing file, create a timestamped backup beneath
  `$CODEX_HOME/backups/codex-fleet/` and report its path.
- Never modify, delete, compact, or relocate session-history files.
- Never copy raw conversation text, private source, credentials, tokens, or
  secret-like values into cache, state, logs, manifests, or the final response.
- Use actual `codex` diagnostics, feature inventory, model catalog, and strict
  configuration validation. Never invent keys, feature names, models, efforts,
  or provider IDs.
- Do not install or remove plugins, change repositories, create commits, or
  modify the Codex Fleet checkout.
- Writes are restricted to the active `CODEX_HOME` and `/tmp`.
- State files under `$CODEX_HOME/codex-fleet/` describe only artifacts owned by
  Codex Fleet. Never claim ownership of a pre-existing setting or file.
- Use restrictive permissions for sanitized cache and state files.

Finish with a concise result: changed files, backups, validations, and any
blocker. Do not dump file contents or session text.
