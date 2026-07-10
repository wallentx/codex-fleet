# Runbook: remove Codex Fleet-owned feature changes

Read `$CODEX_HOME/codex-fleet/features-enabled-by-fleet.txt`. If it is absent,
report the component as already absent and make no feature changes.

For each valid listed feature, disable it only because the ownership state proves
Codex Fleet changed it from disabled to enabled. Never disable an unlisted
feature. Back up config first, use supported Codex feature commands, preserve all
unrelated settings, then remove the ownership file.

Validate strict config loading and confirm `agents.max_threads` is not
reintroduced. Report features disabled and features already absent.
