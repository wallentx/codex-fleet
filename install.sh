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
INSTALL_LOG=
CONFIG_OUTPUT=
CURRENT_TASK=0
CHECKLIST_STARTED=0
CHECKLIST_TTY=0
CHECKLIST_RENDERED=0
TASK_1=pending
TASK_2=pending
TASK_3=pending
TASK_4=pending
TASK_5=pending
ROLES_TABLE=

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

task_label() {
  case "$1" in
    1) printf '%s' 'Verify prerequisites' ;;
    2) printf '%s' 'Register local marketplace' ;;
    3) printf '%s' 'Install Learn plugin' ;;
    4) printf '%s' 'Analyze history and configure fleet' ;;
    5) printf '%s' 'Validate and summarize agents' ;;
  esac
}

render_task_line() {
  state=$1
  label=$2
  marker=' '
  suffix=
  case "$state" in
    loading)
      marker='~'
      suffix=' (loading)'
      ;;
    done)
      marker='x'
      ;;
    skipped)
      marker='-'
      suffix=' (skipped)'
      ;;
    failed)
      marker='!'
      suffix=' (failed)'
      ;;
  esac
  if [ "$CHECKLIST_TTY" -eq 1 ]; then
    printf '\033[2K[%s] %s%s\n' "$marker" "$label" "$suffix" >&2
  else
    printf '[%s] %s%s\n' "$marker" "$label" "$suffix" >&2
  fi
}

render_checklist() {
  if [ "$CHECKLIST_RENDERED" -eq 1 ]; then
    printf '\033[5A' >&2
  fi
  render_task_line "$TASK_1" "$(task_label 1)"
  render_task_line "$TASK_2" "$(task_label 2)"
  render_task_line "$TASK_3" "$(task_label 3)"
  render_task_line "$TASK_4" "$(task_label 4)"
  render_task_line "$TASK_5" "$(task_label 5)"
  CHECKLIST_RENDERED=1
}

begin_checklist() {
  if [ -t 2 ] 2>/dev/null && [ "${TERM:-dumb}" != dumb ]; then
    CHECKLIST_TTY=1
  fi
  CHECKLIST_STARTED=1
  printf 'Codex Fleet setup\n\n' >&2
  render_checklist
}

set_task_state() {
  task=$1
  state=$2
  case "$task" in
    1) TASK_1=$state ;;
    2) TASK_2=$state ;;
    3) TASK_3=$state ;;
    4) TASK_4=$state ;;
    5) TASK_5=$state ;;
  esac
  if [ "$CHECKLIST_TTY" -eq 1 ]; then
    render_checklist
  else
    render_task_line "$state" "$(task_label "$task")"
  fi
}

task_loading() {
  CURRENT_TASK=$1
  set_task_state "$1" loading
}

task_done() {
  set_task_state "$1" "done"
  CURRENT_TASK=0
}

task_skipped() {
  set_task_state "$1" skipped
}

task_failed() {
  set_task_state "$1" failed
  CURRENT_TASK=0
}

die() {
  if [ "$CHECKLIST_STARTED" -eq 1 ] && [ "$CURRENT_TASK" -ne 0 ]; then
    task_failed "$CURRENT_TASK"
  fi
  printf '\n' >&2
  printf 'codex-fleet: %s\n' "$*" >&2
  if [ -n "$INSTALL_LOG" ]; then
    printf 'Detailed log: %s\n' "$INSTALL_LOG" >&2
  fi
  if [ -n "$CONFIG_OUTPUT" ] && [ -s "$CONFIG_OUTPUT" ]; then
    printf 'Codex final output: %s\n' "$CONFIG_OUTPUT" >&2
  fi
  exit 1
}

interrupted() {
  status=$1
  if [ "$CHECKLIST_STARTED" -eq 1 ] && [ "$CURRENT_TASK" -ne 0 ]; then
    task_failed "$CURRENT_TASK"
  fi
  printf '\ncodex-fleet: interrupted; completed changes were not rolled back.\n' >&2
  if [ -n "$INSTALL_LOG" ]; then
    printf 'Detailed log: %s\n' "$INSTALL_LOG" >&2
  fi
  if [ -n "$CONFIG_OUTPUT" ] && [ -s "$CONFIG_OUTPUT" ]; then
    printf 'Codex final output: %s\n' "$CONFIG_OUTPUT" >&2
  fi
  exit "$status"
}

trap 'interrupted 130' INT
trap 'interrupted 143' TERM
trap 'interrupted 129' HUP

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
    printf ' '
    case "$arg" in
      ''|*[!A-Za-z0-9_./:@%+=,-]*)
        printf "'"
        printf '%s' "$arg" | sed "s/'/'\\\\''/g"
        printf "'"
        ;;
      *)
        printf '%s' "$arg"
        ;;
    esac
  done
  printf '\n'
}

log_command() {
  if [ -n "$INSTALL_LOG" ]; then
    show_command "$@" >> "$INSTALL_LOG"
  fi
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

load_roles_table() {
  manifest="$CODEX_HOME/agents/FLEET.md"
  [ -f "$manifest" ] || return 1
  ROLES_TABLE=$(awk '
    /^<!-- codex-fleet:roles:start -->$/ { inside = 1; started = 1; next }
    /^<!-- codex-fleet:roles:end -->$/ {
      if (inside) {
        ended = 1
        exit
      }
    }
    inside { print }
    END { if (!started || !ended) exit 1 }
  ' "$manifest") || return 1
  case "$ROLES_TABLE" in
    *'| Role | Model | Provider | Effort | Sandbox | Purpose |'*) ;;
    *) return 1 ;;
  esac
  table_roles=$(printf '%s\n' "$ROLES_TABLE" | awk -F '|' '
    /^\|[[:space:]]*Role[[:space:]]*\|/ { next }
    /^\|[[:space:]]*---/ { next }
    /^\|/ {
      if (NF != 8) exit 1
      role = $2
      gsub(/^[[:space:]`]+|[[:space:]`]+$/, "", role)
      if (role !~ /^[a-z][a-z0-9_]*$/) exit 1
      print role
      next
    }
    NF { exit 1 }
  ') || return 1
  [ -n "$table_roles" ] || return 1
  table_roles=$(printf '%s\n' "$table_roles" | LC_ALL=C sort)

  config_file="$CODEX_HOME/config.toml"
  [ -f "$config_file" ] || return 1
  declared_roles=$(awk '
    /^\[agents\.[a-z][a-z0-9_]*\][[:space:]]*$/ {
      role = $0
      sub(/^\[agents\./, "", role)
      sub(/\][[:space:]]*$/, "", role)
      print role
    }
  ' "$config_file") || return 1
  [ -n "$declared_roles" ] || return 1
  declared_roles=$(printf '%s\n' "$declared_roles" | LC_ALL=C sort)
  [ "$table_roles" = "$declared_roles" ]
}

print_learn_usage() {
  cat <<'EOF'

Using Learn

1. Start a fresh Codex thread in the repository you want to learn from.
2. Run `$learn Analyze recent work in this repository.` after substantial work.
   It creates `learning_proposal.md` without changing persistent guidance.
3. Review the proposal. Route non-empty proposals through `learning_auditor`
   and `learning_reviewer`, then explicitly approve only the item IDs you want.
4. Run `$apply-learning Apply only L-... from learning_proposal.md.`

Applied changes are backed up under `.codex/learn/backups/` and staged for
review. Optional proposal and audit workflows are `$lint-learning`, `$forget`,
and `$consolidate`.
EOF
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

begin_checklist
task_loading 1

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

if [ "$DRY_RUN" -eq 1 ]; then
  task_done 1
  task_skipped 2
  task_skipped 3
  task_skipped 4
  task_skipped 5
  printf '\nDry-run commands for Codex %s with CODEX_HOME=%s:\n' "$current_version" "$CODEX_HOME"
  if [ "$INSTALL_LEARN" -eq 1 ]; then
    show_command "$CODEX_BIN" plugin marketplace add "$SCRIPT_DIR" --json
    show_command "$CODEX_BIN" plugin add "$LEARN_PLUGIN_ID" --json
  fi
  if [ "$CONFIGURE_FLEET" -eq 1 ]; then
    show_command "$CODEX_BIN" -a never exec --ephemeral --skip-git-repo-check \
      --color never -C "$CODEX_HOME" -s workspace-write -
    printf 'stdin: %s\n' "$PROMPT_FILE"
  fi
  exit 0
fi

log_dir="$CODEX_HOME/log"
log_stamp=$(date '+%Y%m%dT%H%M%S')
INSTALL_LOG="$log_dir/codex-fleet-install-${log_stamp}-$$.log"
CONFIG_OUTPUT="$log_dir/codex-fleet-install-${log_stamp}-$$.final.txt"
if ! (umask 077 && mkdir -p "$log_dir" && set -C && : > "$INSTALL_LOG" && : > "$CONFIG_OUTPUT"); then
  die "could not create private install log under $log_dir"
fi
chmod 600 "$INSTALL_LOG" "$CONFIG_OUTPUT" \
  || die "could not secure private install logs under $log_dir"
printf 'Codex Fleet install\nCodex: %s\nCODEX_HOME: %s\n' \
  "$current_version" "$CODEX_HOME" >> "$INSTALL_LOG"
task_done 1

if [ "$INSTALL_LEARN" -eq 1 ]; then
  task_loading 2
  log_command "$CODEX_BIN" plugin list --json
  if plugin_json=$("$CODEX_BIN" plugin list --json 2>> "$INSTALL_LOG"); then
    :
  else
    die "could not read installed plugin inventory"
  fi
  existing_learn=$(printf '%s\n' "$plugin_json" | json_other_learn_id)
  if [ -n "$existing_learn" ] && [ "$existing_learn" != "$LEARN_PLUGIN_ID" ] \
    && [ "$REPLACE_EXISTING_LEARN" -ne 1 ]; then
    die "Learn is already installed as $existing_learn; rerun with --replace-existing-learn to replace it"
  fi

  log_command "$CODEX_BIN" plugin marketplace list --json
  if marketplace_json=$("$CODEX_BIN" plugin marketplace list --json 2>> "$INSTALL_LOG"); then
    :
  else
    die "could not read marketplace inventory"
  fi
  registered_root=$(printf '%s\n' "$marketplace_json" | json_marketplace_root)

  if [ -n "$registered_root" ]; then
    if registered_root_canonical=$(CDPATH='' cd -P "$registered_root" 2>/dev/null && pwd); then
      :
    else
      die "registered $MARKETPLACE_NAME marketplace root is unavailable: $registered_root"
    fi
    if [ "$registered_root_canonical" != "$SCRIPT_DIR" ]; then
      die "$MARKETPLACE_NAME already points to $registered_root_canonical; remove or rename that marketplace before continuing"
    fi
  else
    log_command "$CODEX_BIN" plugin marketplace add "$SCRIPT_DIR" --json
    if marketplace_add_output=$("$CODEX_BIN" plugin marketplace add "$SCRIPT_DIR" --json 2>> "$INSTALL_LOG"); then
      printf '%s\n' "$marketplace_add_output" >> "$INSTALL_LOG"
    else
      die "could not register the $MARKETPLACE_NAME marketplace"
    fi
  fi
  task_done 2

  task_loading 3
  log_command "$CODEX_BIN" plugin add "$LEARN_PLUGIN_ID" --json
  if plugin_add_output=$("$CODEX_BIN" plugin add "$LEARN_PLUGIN_ID" --json 2>> "$INSTALL_LOG"); then
    printf '%s\n' "$plugin_add_output" >> "$INSTALL_LOG"
  else
    die "could not install $LEARN_PLUGIN_ID"
  fi

  log_command "$CODEX_BIN" plugin list --json
  if installed_json=$("$CODEX_BIN" plugin list --json 2>> "$INSTALL_LOG"); then
    :
  else
    die "could not verify the Learn installation"
  fi
  printf '%s\n' "$installed_json" | json_has_plugin_id "$LEARN_PLUGIN_ID" \
    || die "bundled Learn installation did not appear in Codex plugin inventory"

  if [ -n "$existing_learn" ]; then
    log_command "$CODEX_BIN" plugin remove "$existing_learn"
    if "$CODEX_BIN" plugin remove "$existing_learn" >> "$INSTALL_LOG" 2>&1; then
      :
    else
      die "installed $LEARN_PLUGIN_ID but could not remove $existing_learn"
    fi
  fi
  task_done 3
else
  task_skipped 2
  task_skipped 3
fi

if [ "$CONFIGURE_FLEET" -eq 1 ]; then
  task_loading 4
  log_command "$CODEX_BIN" -a never exec --ephemeral --skip-git-repo-check \
    --color never -C "$CODEX_HOME" -s workspace-write -
  if "$CODEX_BIN" -a never exec --ephemeral --skip-git-repo-check \
    --color never -C "$CODEX_HOME" -s workspace-write - \
    < "$PROMPT_FILE" > "$CONFIG_OUTPUT" 2>> "$INSTALL_LOG"; then
    task_done 4
  else
    config_status=$?
    die "fleet configuration failed with exit status $config_status"
  fi
else
  task_skipped 4
fi

if [ "$CONFIGURE_FLEET" -eq 1 ]; then
  task_loading 5
  load_roles_table \
    || die "fleet configuration completed but agents/FLEET.md has no valid roles table"
  task_done 5
else
  task_skipped 5
fi

printf '\nCodex Fleet installation complete.\n'
printf 'Codex %s; CODEX_HOME=%s\n' "$current_version" "$CODEX_HOME"
printf 'Start a new Codex thread to load the plugin and agent-role schema.\n'

if [ "$CONFIGURE_FLEET" -eq 1 ]; then
  printf '\nConfigured agents\n\n%s\n' "$ROLES_TABLE"
  printf '\nFull fleet manifest: %s/agents/FLEET.md\n' "$CODEX_HOME"
fi

if [ "$INSTALL_LEARN" -eq 1 ]; then
  print_learn_usage
fi

printf '\nDetailed log: %s\n' "$INSTALL_LOG"
if [ -s "$CONFIG_OUTPUT" ]; then
  printf 'Codex final output: %s\n' "$CONFIG_OUTPUT"
fi
