#!/usr/bin/env sh
set -eu

MIN_CODEX_VERSION="0.144.0"
MARKETPLACE_NAME="codex-fleet"
LEARN_PLUGIN_ID="learn@${MARKETPLACE_NAME}"

SCRIPT_DIR=$(CDPATH='' cd -P "$(dirname "$0")" && pwd)
PROMPT_FILE="$SCRIPT_DIR/prompts/configure-fleet.md"
MARKETPLACE_FILE="$SCRIPT_DIR/.agents/plugins/marketplace.json"
LEARN_PLUGIN_DIR="$SCRIPT_DIR/plugins/learn"

CODEX_BIN=${CODEX_BIN:-codex}
CODEX_HOME=${CODEX_HOME:-"$HOME/.codex"}

DRY_RUN=0
INSTALL_LEARN=1
CONFIGURE_FLEET=1
REPLACE_EXISTING_LEARN=0

usage() {
  cat <<'EOF'
Usage: ./install.sh [options]

Install the bundled Learn plugin and ask Codex to derive a specialized agent
fleet from this device's local session history.

Options:
  --dry-run                 Verify prerequisites and show intended actions.
  --skip-learn              Do not install the bundled Learn plugin.
  --skip-configure          Install Learn without running fleet configuration.
  --replace-existing-learn  Replace Learn installed from another marketplace.
  -h, --help                Show this help.

Environment:
  CODEX_BIN   Codex executable to use (default: codex)
  CODEX_HOME  Codex state/config directory (default: ~/.codex)
EOF
}

die() {
  printf 'codex-fleet: %s\n' "$*" >&2
  exit 1
}

version_at_least() {
  awk -v have="$1" -v need="$2" 'BEGIN {
    have_prerelease = index(have, "-") > 0
    need_prerelease = index(need, "-") > 0
    sub(/^v/, "", have)
    sub(/^v/, "", need)
    sub(/[-+].*$/, "", have)
    sub(/[-+].*$/, "", need)
    split(have, h, ".")
    split(need, n, ".")
    for (i = 1; i <= 3; i++) {
      hv = h[i] + 0
      nv = n[i] + 0
      if (hv > nv) exit 0
      if (hv < nv) exit 1
    }
    if (have_prerelease && !need_prerelease) exit 1
    exit 0
  }'
}

show_command() {
  printf '+'
  for arg in "$@"; do
    printf ' %s' "$arg"
  done
  printf '\n'
}

json_marketplace_root() {
  awk -v target="\"name\": \"$MARKETPLACE_NAME\"" '
    index($0, target) { found = 1; next }
    found && /"root"[[:space:]]*:/ {
      line = $0
      sub(/^[^:]*:[[:space:]]*"/, "", line)
      sub(/".*$/, "", line)
      print line
      exit
    }
  '
}

json_other_learn_id() {
  sed -n 's/.*"pluginId"[[:space:]]*:[[:space:]]*"\(learn@[^"[:space:]]*\)".*/\1/p' \
    | awk -v target="$LEARN_PLUGIN_ID" '$0 != target { print; exit }'
}

json_has_plugin_id() {
  sed -n 's/.*"pluginId"[[:space:]]*:[[:space:]]*"\([^"[:space:]]*\)".*/\1/p' \
    | awk -v target="$1" '$0 == target { found = 1 } END { exit !found }'
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      ;;
    --skip-learn)
      INSTALL_LEARN=0
      ;;
    --skip-configure)
      CONFIGURE_FLEET=0
      ;;
    --replace-existing-learn)
      REPLACE_EXISTING_LEARN=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown option: $1"
      ;;
  esac
  shift
done

command -v "$CODEX_BIN" >/dev/null 2>&1 \
  || die "Codex CLI not found. Install Codex 0.144.0 or newer first."

version_output=$("$CODEX_BIN" --version 2>/dev/null) \
  || die "could not read Codex version"
current_version=$(printf '%s\n' "$version_output" | awk '
  {
    for (i = 1; i <= NF; i++) {
      if ($i ~ /^v?[0-9]+\.[0-9]+\.[0-9]+/) {
        print $i
        exit
      }
    }
  }
')

[ -n "$current_version" ] \
  || die "could not parse Codex version from: $version_output"

version_at_least "$current_version" "$MIN_CODEX_VERSION" \
  || die "Codex $current_version is too old; upgrade to $MIN_CODEX_VERSION or newer and rerun."

[ -f "$PROMPT_FILE" ] || die "missing fleet prompt: $PROMPT_FILE"
[ -f "$MARKETPLACE_FILE" ] || die "missing marketplace manifest: $MARKETPLACE_FILE"
[ -f "$LEARN_PLUGIN_DIR/.codex-plugin/plugin.json" ] \
  || die "missing bundled Learn plugin manifest"

printf 'Codex %s satisfies minimum %s.\n' "$current_version" "$MIN_CODEX_VERSION"
printf 'CODEX_HOME: %s\n' "$CODEX_HOME"

if [ "$DRY_RUN" -eq 1 ]; then
  if [ "$INSTALL_LEARN" -eq 1 ]; then
    show_command "$CODEX_BIN" plugin marketplace add "$SCRIPT_DIR" --json
    show_command "$CODEX_BIN" plugin add "$LEARN_PLUGIN_ID" --json
  fi
  if [ "$CONFIGURE_FLEET" -eq 1 ]; then
    show_command "$CODEX_BIN" exec --ephemeral --skip-git-repo-check \
      --color never -C "$CODEX_HOME" -s workspace-write -a never -
    printf 'stdin: %s\n' "$PROMPT_FILE"
  fi
  exit 0
fi

mkdir -p "$CODEX_HOME"

if [ "$INSTALL_LEARN" -eq 1 ]; then
  plugin_json=$("$CODEX_BIN" plugin list --json)
  existing_learn=$(printf '%s\n' "$plugin_json" | json_other_learn_id)
  if [ -n "$existing_learn" ] && [ "$existing_learn" != "$LEARN_PLUGIN_ID" ] \
    && [ "$REPLACE_EXISTING_LEARN" -ne 1 ]; then
    die "Learn is already installed as $existing_learn; rerun with --replace-existing-learn to replace it"
  fi

  marketplace_json=$("$CODEX_BIN" plugin marketplace list --json)
  registered_root=$(printf '%s\n' "$marketplace_json" | json_marketplace_root)

  if [ -n "$registered_root" ]; then
    registered_root_canonical=$(CDPATH='' cd -P "$registered_root" 2>/dev/null && pwd) \
      || die "registered $MARKETPLACE_NAME marketplace root is unavailable: $registered_root"
    if [ "$registered_root_canonical" != "$SCRIPT_DIR" ]; then
      die "$MARKETPLACE_NAME already points to $registered_root_canonical; remove or rename that marketplace before continuing"
    fi
    printf 'Marketplace %s already registered.\n' "$MARKETPLACE_NAME"
  else
    show_command "$CODEX_BIN" plugin marketplace add "$SCRIPT_DIR" --json
    "$CODEX_BIN" plugin marketplace add "$SCRIPT_DIR" --json
  fi

  show_command "$CODEX_BIN" plugin add "$LEARN_PLUGIN_ID" --json
  "$CODEX_BIN" plugin add "$LEARN_PLUGIN_ID" --json

  installed_json=$("$CODEX_BIN" plugin list --json)
  printf '%s\n' "$installed_json" | json_has_plugin_id "$LEARN_PLUGIN_ID" \
    || die "bundled Learn installation did not appear in Codex plugin inventory"

  if [ -n "$existing_learn" ]; then
    show_command "$CODEX_BIN" plugin remove "$existing_learn"
    "$CODEX_BIN" plugin remove "$existing_learn"
  fi
fi

if [ "$CONFIGURE_FLEET" -eq 1 ]; then
  printf 'Launching Codex fleet configuration. This can take several minutes.\n'
  show_command "$CODEX_BIN" exec --ephemeral --skip-git-repo-check \
    --color never -C "$CODEX_HOME" -s workspace-write -a never -
  "$CODEX_BIN" exec --ephemeral --skip-git-repo-check \
    --color never -C "$CODEX_HOME" -s workspace-write -a never - \
    < "$PROMPT_FILE"
fi

printf '\nCodex Fleet installation complete. Start a new Codex thread to load the new plugin and agent-role schema.\n'
