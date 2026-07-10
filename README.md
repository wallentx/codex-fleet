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

Invoke installed skills through their actual skill names:

- `$learn`
- `$apply-learning`
- `$forget`
- `$consolidate`
- `$lint-learning`

Learn remains proposal-only by default. Persistent guidance changes require the separate apply workflow and explicit selection.

## Repository layout

```text
.
|-- .agents/plugins/marketplace.json
|-- install.sh
|-- plugins/learn/
`-- prompts/configure-fleet.md
```

