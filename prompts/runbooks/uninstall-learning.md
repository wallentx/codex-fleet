# Runbook: remove the reviewed learning pipeline

Read `$CODEX_HOME/codex-fleet/learning-installed.txt`. If absent and the marked
global guidance block is absent, report the component as already removed.

Back up affected files. Remove only roles listed in the valid ownership state,
their matching config declarations, and their matching role files. Remove only
the global `AGENTS.md` section between these exact markers:

```text
<!-- history-derived-fleet:learning-pipeline:start -->
<!-- history-derived-fleet:learning-pipeline:end -->
```

Preserve all surrounding guidance byte-for-byte. Remove
`learning-installed.txt` after successful cleanup. Validate TOML, role absence,
and marker absence. Do not uninstall the Learn plugin; the installer handles it
after dependent configuration is removed.
