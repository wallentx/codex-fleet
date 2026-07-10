# Codex Fleet

Codex Fleet configures each device from its own local Codex session history. It discovers recurring workloads, enables supported multi-agent capabilities, selects locally available models, and creates a device-specific specialist fleet under `CODEX_HOME`.

The repository also bundles the dependency-free Learn plugin used for proposal-only learning workflows, independent learning review, and explicitly approved application.

## Requirements

- Codex CLI 0.144.0 or newer
- An authenticated Codex installation
- POSIX `sh`, `awk`, and `sed`

## Install

```sh
./install.sh
```

The installer:

1. Rejects Codex versions older than 0.144.0.
2. Registers this checkout as the `codex-fleet` local marketplace.
3. Installs `learn@codex-fleet`.
4. Runs `prompts/configure-fleet.md` through an ephemeral `codex exec` session.
5. Asks Codex to analyze local history and safely merge the resulting fleet into the active `CODEX_HOME`.

Installation is quiet by default. A five-step checklist shows the active step as
`[~] ... (loading)` while detailed Codex progress is captured in a private log
under `$CODEX_HOME/log/`. On success, the installer prints the configured-agent
table from `$CODEX_HOME/agents/FLEET.md`.

If Learn is already installed from another marketplace:

```sh
./install.sh --replace-existing-learn
```

Inspect actions without modifying anything:

```sh
./install.sh --dry-run
```

Install only Learn:

```sh
./install.sh --skip-configure
```

Configure only the fleet:

```sh
./install.sh --skip-learn
```

Override Codex paths when needed:

```sh
CODEX_BIN=/path/to/codex CODEX_HOME=/path/to/.codex ./install.sh
```

Start a new Codex thread after installation. Plugin skills and the generated agent-role schema are loaded at thread start.

## Bundled Learn workflows

Start a fresh Codex thread in the repository you want to learn from, then invoke
the installed skills through their actual names:

1. Run `$learn Analyze recent work in this repository.` after substantial work.
   It writes `learning_proposal.md` without changing persistent guidance.
2. Review the proposal. Non-empty proposals should pass through
   `learning_auditor` and `learning_reviewer`.
3. Explicitly approve only the item IDs you want, then run
   `$apply-learning Apply only L-... from learning_proposal.md.`

Applied changes are backed up under `.codex/learn/backups/` and staged for
review. Use `$lint-learning` to audit guidance health, `$forget` to propose stale
guidance removal, and `$consolidate` to propose merging overlapping guidance.
Learn remains proposal-only until the separate apply workflow receives an
explicit selection.

## Repository layout

```text
.
|-- .agents/plugins/marketplace.json
|-- install.sh
|-- plugins/learn/
`-- prompts/configure-fleet.md
```
