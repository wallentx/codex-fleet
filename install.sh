#!/usr/bin/env sh
set -eu

MIN_CODEX_VERSION="0.144.0"
MARKETPLACE_NAME="codex-fleet"
LEARN_PLUGIN_ID="learn@${MARKETPLACE_NAME}"

SCRIPT_DIR=$(CDPATH='' cd -P "$(dirname "$0")" && pwd)
MARKETPLACE_FILE="$SCRIPT_DIR/.agents/plugins/marketplace.json"
LEARN_PLUGIN_DIR="$SCRIPT_DIR/plugins/learn"
RUNBOOK_DIR="$SCRIPT_DIR/prompts/runbooks"
COMMON_RUNBOOK="$RUNBOOK_DIR/_common.md"

CODEX_BIN=${CODEX_BIN:-codex}
CODEX_HOME=${CODEX_HOME:-"$HOME/.codex"}
STATE_DIR="$CODEX_HOME/codex-fleet"
HISTORY_CACHE="$STATE_DIR/history-analysis.md"
HISTORY_META="$STATE_DIR/history-analysis.meta"
FEATURE_STATE="$STATE_DIR/features-enabled-by-fleet.txt"
AGENT_STATE="$STATE_DIR/agents-installed.txt"
LEARNING_STATE="$STATE_DIR/learning-installed.txt"

MODE=install
DRY_RUN=0
REFRESH_ANALYSIS=0
REPLACE_EXISTING_LEARN=0
COMPONENTS_ARG=
LEGACY_SKIP_LEARN=0
LEGACY_SKIP_CONFIGURE=0

SELECT_LEARN=1
SELECT_HISTORY=1
SELECT_FEATURES=1
SELECT_AGENTS=1
SELECT_LEARNING=1

HAS_LEARN=0
MARKETPLACE_ROOT=
UI_TTY=0
CHECKLIST_STARTED=0
CHECKLIST_RENDERED=0
CURRENT_TASK=0
ACTIVE_PID=
SPINNER_FRAME='|'
RUN_DIR=
INSTALL_LOG=
CONFIG_OUTPUT=
ROLES_TABLE=

TASK_1=pending
TASK_2=pending
TASK_3=pending
TASK_4=pending
TASK_5=pending
TASK_6=pending
TASK_7=pending

usage() {
  cat <<'EOF'
Usage: ./install.sh [options]

Interactively install or uninstall Codex Fleet components. In a non-interactive
shell, install defaults to every component; uninstall requires --components.

Options:
  --install                  Install selected components (default).
  --uninstall                Remove selected components in dependency-safe order.
  --components LIST          Comma-separated component IDs; skips the menu.
                             IDs: learn,history,features,agents,learning
  --refresh-analysis         Rebuild the sanitized history cache instead of reusing it.
  --dry-run                  Show resolved selections and runbooks without changes.
  --replace-existing-learn   Replace Learn installed from another marketplace.
  --skip-learn               Compatibility alias: omit Learn and learning pipeline.
  --skip-configure           Compatibility alias: install only Learn.
  -h, --help                 Show this help.

Dependencies:
  agents    -> history, features
  learning  -> learn, agents

Environment:
  CODEX_BIN   Codex executable to use (default: codex)
  CODEX_HOME  Codex state/config directory (default: ~/.codex)
EOF
}

show_command() {
  printf '+'
  for show_arg in "$@"; do
    printf ' '
    case "$show_arg" in
      ''|*[!A-Za-z0-9_./:@%+=,-]*)
        printf "'"
        printf '%s' "$show_arg" | sed "s/'/'\\\\''/g"
        printf "'"
        ;;
      *) printf '%s' "$show_arg" ;;
    esac
  done
  printf '\n'
}

log_command() {
  [ -n "$INSTALL_LOG" ] || return 0
  show_command "$@" >> "$INSTALL_LOG"
}

ui_open() {
  if ( : </dev/tty ) 2>/dev/null; then
    exec 3<>/dev/tty
    UI_TTY=1
  fi
}

ui_printf() {
  # The first argument is always an installer-owned literal format string.
  # shellcheck disable=SC2059
  if [ "$UI_TTY" -eq 1 ]; then
    printf "$@" >&3
  else
    printf "$@" >&2
  fi
}

selected_count() {
  printf '%s\n' "$((SELECT_LEARN + SELECT_HISTORY + SELECT_FEATURES + SELECT_AGENTS + SELECT_LEARNING))"
}

selection_box() {
  if [ "$1" -eq 1 ]; then printf 'x'; else printf ' '; fi
}

component_status() {
  case "$1" in
    learn)
      if [ "$HAS_LEARN" -eq 1 ]; then printf 'installed'; else printf 'not installed'; fi
      ;;
    history)
      if history_cache_valid; then printf 'cached'; else printf 'not cached'; fi
      ;;
    features)
      if state_file_valid "$FEATURE_STATE" '# codex-fleet:features:v1'; then printf 'configured'; else printf 'not configured'; fi
      ;;
    agents)
      if state_file_valid "$AGENT_STATE" '# codex-fleet:agents:v1'; then printf 'configured'; else printf 'not configured'; fi
      ;;
    learning)
      if state_file_valid "$LEARNING_STATE" '# codex-fleet:learning:v1'; then printf 'configured'; else printf 'not configured'; fi
      ;;
  esac
}

select_none() {
  SELECT_LEARN=0
  SELECT_HISTORY=0
  SELECT_FEATURES=0
  SELECT_AGENTS=0
  SELECT_LEARNING=0
}

select_all() {
  SELECT_LEARN=1
  SELECT_HISTORY=1
  SELECT_FEATURES=1
  SELECT_AGENTS=1
  SELECT_LEARNING=1
}

toggle_component() {
  case "$1" in
    1|learn) SELECT_LEARN=$((1 - SELECT_LEARN)) ;;
    2|history) SELECT_HISTORY=$((1 - SELECT_HISTORY)) ;;
    3|features) SELECT_FEATURES=$((1 - SELECT_FEATURES)) ;;
    4|agents) SELECT_AGENTS=$((1 - SELECT_AGENTS)) ;;
    5|learning) SELECT_LEARNING=$((1 - SELECT_LEARNING)) ;;
    *) return 1 ;;
  esac
}

select_component() {
  case "$1" in
    learn) SELECT_LEARN=1 ;;
    history) SELECT_HISTORY=1 ;;
    features) SELECT_FEATURES=1 ;;
    agents) SELECT_AGENTS=1 ;;
    learning) SELECT_LEARNING=1 ;;
    *) return 1 ;;
  esac
}

resolve_dependencies() {
  if [ "$MODE" = install ]; then
    if [ "$SELECT_LEARNING" -eq 1 ]; then
      SELECT_LEARN=1
      SELECT_AGENTS=1
    fi
    if [ "$SELECT_AGENTS" -eq 1 ]; then
      SELECT_HISTORY=1
      SELECT_FEATURES=1
    fi
  else
    if [ "$SELECT_LEARN" -eq 1 ]; then
      SELECT_LEARNING=1
    fi
    if [ "$SELECT_FEATURES" -eq 1 ]; then
      SELECT_AGENTS=1
    fi
    if [ "$SELECT_AGENTS" -eq 1 ]; then
      SELECT_LEARNING=1
    fi
  fi
}

parse_components() {
  select_none
  old_ifs=$IFS
  IFS=,
  for component_name in $COMPONENTS_ARG; do
    IFS=$old_ifs
    select_component "$component_name" \
      || die "unknown component '$component_name'; use learn,history,features,agents,learning"
    IFS=,
  done
  IFS=$old_ifs
  resolve_dependencies
}

selection_summary() {
  selection_text=
  for component_name in learn history features agents learning; do
    case "$component_name" in
      learn) component_selected=$SELECT_LEARN ;;
      history) component_selected=$SELECT_HISTORY ;;
      features) component_selected=$SELECT_FEATURES ;;
      agents) component_selected=$SELECT_AGENTS ;;
      learning) component_selected=$SELECT_LEARNING ;;
    esac
    if [ "$component_selected" -eq 1 ]; then
      if [ -n "$selection_text" ]; then selection_text="$selection_text,"; fi
      selection_text="$selection_text$component_name"
    fi
  done
  printf '%s' "$selection_text"
}

render_menu() {
  ui_printf '\033[2J\033[H'
  if [ "$MODE" = install ]; then
    menu_title='Install Codex Fleet components'
  else
    menu_title='Uninstall Codex Fleet components'
  fi
  ui_printf '%s\n\n' "$menu_title"
  ui_printf '  1. [%s] Learn plugin                 (%s)\n' "$(selection_box "$SELECT_LEARN")" "$(component_status learn)"
  ui_printf '  2. [%s] History analysis cache       (%s)\n' "$(selection_box "$SELECT_HISTORY")" "$(component_status history)"
  ui_printf '  3. [%s] Multi-agent features         (%s)\n' "$(selection_box "$SELECT_FEATURES")" "$(component_status features)"
  ui_printf '  4. [%s] Specialist agent fleet       (%s; requires 2,3)\n' "$(selection_box "$SELECT_AGENTS")" "$(component_status agents)"
  ui_printf '  5. [%s] Reviewed learning pipeline   (%s; requires 1,4)\n' "$(selection_box "$SELECT_LEARNING")" "$(component_status learning)"
  ui_printf '\nToggle: 1-5 (space/comma separated)   a: all   n: none\n'
  ui_printf 'Enter: continue   q: quit\n\nSelection> '
}

interactive_menu() {
  [ "$UI_TTY" -eq 1 ] || return 1
  while :; do
    resolve_dependencies
    render_menu
    if IFS= read -r menu_answer <&3; then :; else return 1; fi
    case "$menu_answer" in
      '')
        ui_printf '\n'
        return 0
        ;;
      q|Q) exit 0 ;;
      a|A) select_all ;;
      n|N) select_none ;;
      *)
        menu_items=$(printf '%s' "$menu_answer" | tr ',' ' ')
        for menu_item in $menu_items; do
          toggle_component "$menu_item" || :
        done
        ;;
    esac
  done
}

task_label() {
  case "$1" in
    1) printf '%s' 'Verify prerequisites' ;;
    2) if [ "$MODE" = install ]; then printf '%s' 'Install Learn plugin'; else printf '%s' 'Remove Learn plugin'; fi ;;
    3) if [ "$MODE" = install ]; then printf '%s' 'Prepare history analysis'; else printf '%s' 'Remove history cache'; fi ;;
    4) if [ "$MODE" = install ]; then printf '%s' 'Configure multi-agent features'; else printf '%s' 'Remove fleet-owned features'; fi ;;
    5) if [ "$MODE" = install ]; then printf '%s' 'Configure specialist agents'; else printf '%s' 'Remove specialist agents'; fi ;;
    6) if [ "$MODE" = install ]; then printf '%s' 'Configure learning pipeline'; else printf '%s' 'Remove learning pipeline'; fi ;;
    7) printf '%s' 'Validate and summarize state' ;;
  esac
}

render_task_line() {
  render_state=$1
  render_label=$2
  render_marker=' '
  render_suffix=
  case "$render_state" in
    loading) render_marker=$SPINNER_FRAME; render_suffix=' (loading)' ;;
    done) render_marker='x' ;;
    cached) render_marker='='; render_suffix=' (cached)' ;;
    absent) render_marker='='; render_suffix=' (already absent)' ;;
    skipped) render_marker='-'; render_suffix=' (not selected)' ;;
    failed) render_marker='!'; render_suffix=' (failed)' ;;
  esac
  if [ "$UI_TTY" -eq 1 ]; then
    ui_printf '\033[2K[%s] %s%s\n' "$render_marker" "$render_label" "$render_suffix"
  else
    ui_printf '[%s] %s%s\n' "$render_marker" "$render_label" "$render_suffix"
  fi
}

render_checklist() {
  if [ "$CHECKLIST_RENDERED" -eq 1 ]; then ui_printf '\033[7A'; fi
  render_task_line "$TASK_1" "$(task_label 1)"
  render_task_line "$TASK_2" "$(task_label 2)"
  render_task_line "$TASK_3" "$(task_label 3)"
  render_task_line "$TASK_4" "$(task_label 4)"
  render_task_line "$TASK_5" "$(task_label 5)"
  render_task_line "$TASK_6" "$(task_label 6)"
  render_task_line "$TASK_7" "$(task_label 7)"
  CHECKLIST_RENDERED=1
}

begin_checklist() {
  CHECKLIST_STARTED=1
  if [ "$UI_TTY" -eq 1 ]; then
    ui_printf '\033[2J\033[HCodex Fleet %s\n\n' "$MODE"
    render_checklist
  else
    ui_printf 'Codex Fleet %s\n\n' "$MODE"
  fi
}

set_task_state() {
  set_task=$1
  set_state=$2
  case "$set_task" in
    1) TASK_1=$set_state ;;
    2) TASK_2=$set_state ;;
    3) TASK_3=$set_state ;;
    4) TASK_4=$set_state ;;
    5) TASK_5=$set_state ;;
    6) TASK_6=$set_state ;;
    7) TASK_7=$set_state ;;
  esac
  if [ "$CHECKLIST_STARTED" -eq 1 ]; then
    if [ "$UI_TTY" -eq 1 ]; then
      render_checklist
    else
      render_task_line "$set_state" "$(task_label "$set_task")"
    fi
  fi
}

task_loading() { CURRENT_TASK=$1; set_task_state "$1" loading; }
task_done() { set_task_state "$1" "done"; CURRENT_TASK=0; }
task_cached() { set_task_state "$1" cached; CURRENT_TASK=0; }
task_absent() { set_task_state "$1" absent; CURRENT_TASK=0; }
task_failed() { set_task_state "$1" failed; CURRENT_TASK=0; }

advance_spinner() {
  case "$SPINNER_FRAME" in
    '|') SPINNER_FRAME='/' ;;
    '/') SPINNER_FRAME='-' ;;
    '-') SPINNER_FRAME="\\" ;;
    *) SPINNER_FRAME='|' ;;
  esac
  [ "$UI_TTY" -eq 1 ] && render_checklist
}

die() {
  if [ "$CHECKLIST_STARTED" -eq 1 ] && [ "$CURRENT_TASK" -ne 0 ]; then task_failed "$CURRENT_TASK"; fi
  printf '\ncodex-fleet: %s\n' "$*" >&2
  if [ -n "$RUN_DIR" ]; then printf 'Detailed run directory: %s\n' "$RUN_DIR" >&2; fi
  if [ -n "$CONFIG_OUTPUT" ] && [ -s "$CONFIG_OUTPUT" ]; then printf 'Codex final output: %s\n' "$CONFIG_OUTPUT" >&2; fi
  exit 1
}

interrupted() {
  interrupt_status=$1
  if [ -n "$ACTIVE_PID" ]; then
    kill -TERM "$ACTIVE_PID" 2>/dev/null || :
    wait "$ACTIVE_PID" 2>/dev/null || :
    ACTIVE_PID=
  fi
  if [ "$CHECKLIST_STARTED" -eq 1 ] && [ "$CURRENT_TASK" -ne 0 ]; then task_failed "$CURRENT_TASK"; fi
  printf '\ncodex-fleet: interrupted; completed changes were not rolled back.\n' >&2
  if [ -n "$RUN_DIR" ]; then printf 'Detailed run directory: %s\n' "$RUN_DIR" >&2; fi
  exit "$interrupt_status"
}

trap 'interrupted 130' INT
trap 'interrupted 143' TERM
trap 'interrupted 129' HUP

version_at_least() {
  awk -v have="$1" -v need="$2" 'BEGIN {
    have_prerelease = index(have, "-") > 0
    need_prerelease = index(need, "-") > 0
    sub(/^v/, "", have); sub(/^v/, "", need)
    sub(/[-+].*$/, "", have); sub(/[-+].*$/, "", need)
    split(have, h, "."); split(need, n, ".")
    for (i = 1; i <= 3; i++) {
      if (h[i] + 0 > n[i] + 0) exit 0
      if (h[i] + 0 < n[i] + 0) exit 1
    }
    if (have_prerelease && !need_prerelease) exit 1
    exit 0
  }'
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

state_file_valid() {
  state_path=$1
  state_marker=$2
  [ -f "$state_path" ] || return 1
  [ "$(sed -n '1p' "$state_path")" = "$state_marker" ]
}

history_cache_valid() {
  [ -f "$HISTORY_CACHE" ] && [ -f "$HISTORY_META" ] \
    && [ "$(sed -n '1p' "$HISTORY_CACHE")" = '<!-- codex-fleet:history-analysis:v1 -->' ] \
    && awk '$0 == "schema=1" { found = 1 } END { exit !found }' "$HISTORY_META"
}

state_entries() {
  entries_path=$1
  entries_marker=$2
  state_file_valid "$entries_path" "$entries_marker" || return 0
  sed '1d' "$entries_path" | sed '/^[[:space:]]*$/d'
}

fleet_owned_roles() {
  {
    state_entries "$AGENT_STATE" '# codex-fleet:agents:v1'
    state_entries "$LEARNING_STATE" '# codex-fleet:learning:v1'
  } | LC_ALL=C sort -u
}

load_roles_table() {
  roles_manifest="$CODEX_HOME/agents/FLEET.md"
  [ -f "$roles_manifest" ] || return 1
  ROLES_TABLE=$(awk '
    /^<!-- codex-fleet:roles:start -->$/ { inside = 1; started = 1; next }
    /^<!-- codex-fleet:roles:end -->$/ { if (inside) { ended = 1; exit } }
    inside { print }
    END { if (!started || !ended) exit 1 }
  ' "$roles_manifest") || return 1
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
  table_roles=$(printf '%s\n' "$table_roles" | LC_ALL=C sort -u)
  owned_roles=$(fleet_owned_roles)
  [ -n "$owned_roles" ] && [ "$table_roles" = "$owned_roles" ]
}

prepare_run_dir() {
  umask 077
  run_stamp=$(date '+%Y%m%dT%H%M%S')
  RUN_DIR="$CODEX_HOME/log/codex-fleet-${MODE}-${run_stamp}-$$"
  INSTALL_LOG="$RUN_DIR/install.log"
  if ! (set -C && mkdir -p "$RUN_DIR" && : > "$INSTALL_LOG"); then
    die "could not create private run directory $RUN_DIR"
  fi
  chmod 700 "$RUN_DIR" || die "could not secure $RUN_DIR"
  chmod 600 "$INSTALL_LOG" || die "could not secure $INSTALL_LOG"
  mkdir -p "$STATE_DIR" || die "could not create state directory $STATE_DIR"
  chmod 700 "$STATE_DIR" || die "could not secure state directory $STATE_DIR"
  printf 'Codex Fleet %s\nCodex: %s\nCODEX_HOME: %s\nComponents: %s\n' \
    "$MODE" "$current_version" "$CODEX_HOME" "$(selection_summary)" >> "$INSTALL_LOG"
}

prepare_prompt() {
  prompt_runbook=$1
  prompt_slug=$2
  prompt_path="$RUN_DIR/$prompt_slug.prompt.md"
  {
    cat "$COMMON_RUNBOOK"
    printf '\n\n'
    cat "$prompt_runbook"
    printf '\n\n## Runtime inputs\n\n'
    printf -- '- %s: %s\n' 'Operation' "$MODE"
    printf -- '- %s: %s\n' 'Codex version' "$current_version"
    printf -- '- %s: %s\n' 'CODEX_HOME' "$CODEX_HOME"
    printf -- '- %s: %s\n' 'State directory' "$STATE_DIR"
    printf -- '- %s: %s\n' 'History cache' "$HISTORY_CACHE"
    printf -- '- %s: %s\n' 'Selected components' "$(selection_summary)"
    printf -- '- %s: %s\n' 'Refresh analysis' "$REFRESH_ANALYSIS"
    printf -- '- %s: %s\n' 'Run log directory' "$RUN_DIR"
  } > "$prompt_path"
  chmod 600 "$prompt_path" || return 1
  printf '%s' "$prompt_path"
}

run_runbook() {
  run_task=$1
  run_file=$2
  run_slug=$3
  [ -f "$run_file" ] || die "missing runbook: $run_file"
  run_prompt=$(prepare_prompt "$run_file" "$run_slug") \
    || die "could not prepare runbook $run_slug"
  CONFIG_OUTPUT="$RUN_DIR/$run_slug.final.txt"
  run_status_file="$RUN_DIR/$run_slug.status"
  : > "$CONFIG_OUTPUT"
  chmod 600 "$CONFIG_OUTPUT" || die "could not secure $CONFIG_OUTPUT"
  task_loading "$run_task"
  log_command "$CODEX_BIN" -a never exec --ephemeral --skip-git-repo-check \
    --color never -C "$CODEX_HOME" -s workspace-write -
  (
    run_child=
    trap 'if [ -n "$run_child" ]; then kill -TERM "$run_child" 2>/dev/null || :; wait "$run_child" 2>/dev/null || :; fi; exit 143' TERM HUP
    trap 'if [ -n "$run_child" ]; then kill -INT "$run_child" 2>/dev/null || :; wait "$run_child" 2>/dev/null || :; fi; exit 130' INT
    "$CODEX_BIN" -a never exec --ephemeral --skip-git-repo-check \
      --color never -C "$CODEX_HOME" -s workspace-write - \
      < "$run_prompt" > "$CONFIG_OUTPUT" 2>> "$INSTALL_LOG" &
    run_child=$!
    if wait "$run_child"; then run_status=0; else run_status=$?; fi
    printf '%s\n' "$run_status" > "$run_status_file"
    exit "$run_status"
  ) &
  ACTIVE_PID=$!

  if [ "$UI_TTY" -eq 1 ]; then
    while [ ! -s "$run_status_file" ]; do
      sleep 1
      advance_spinner
    done
  fi

  if wait "$ACTIVE_PID"; then run_status=0; else run_status=$?; fi
  ACTIVE_PID=
  if [ -s "$run_status_file" ]; then run_status=$(sed -n '1p' "$run_status_file"); fi
  if [ "$run_status" -ne 0 ]; then
    die "runbook $run_slug failed with exit status $run_status"
  fi
  task_done "$run_task"
}

install_learn() {
  task_loading 2
  existing_learn=$(printf '%s\n' "$PLUGIN_JSON" | json_other_learn_id)
  if [ -n "$existing_learn" ] && [ "$REPLACE_EXISTING_LEARN" -ne 1 ]; then
    die "Learn is already installed as $existing_learn; use --replace-existing-learn"
  fi

  if [ -n "$MARKETPLACE_ROOT" ]; then
    if marketplace_canonical=$(CDPATH='' cd -P "$MARKETPLACE_ROOT" 2>/dev/null && pwd); then :; else
      die "registered marketplace root is unavailable: $MARKETPLACE_ROOT"
    fi
    [ "$marketplace_canonical" = "$SCRIPT_DIR" ] \
      || die "$MARKETPLACE_NAME already points to $marketplace_canonical"
  else
    log_command "$CODEX_BIN" plugin marketplace add "$SCRIPT_DIR" --json
    "$CODEX_BIN" plugin marketplace add "$SCRIPT_DIR" --json >> "$INSTALL_LOG" 2>&1 \
      || die "could not register $MARKETPLACE_NAME"
  fi

  log_command "$CODEX_BIN" plugin add "$LEARN_PLUGIN_ID" --json
  "$CODEX_BIN" plugin add "$LEARN_PLUGIN_ID" --json >> "$INSTALL_LOG" 2>&1 \
    || die "could not install $LEARN_PLUGIN_ID"

  if [ -n "$existing_learn" ]; then
    log_command "$CODEX_BIN" plugin remove "$existing_learn" --json
    "$CODEX_BIN" plugin remove "$existing_learn" --json >> "$INSTALL_LOG" 2>&1 \
      || die "installed $LEARN_PLUGIN_ID but could not remove $existing_learn"
  fi
  HAS_LEARN=1
  task_done 2
}

uninstall_learn() {
  if [ "$HAS_LEARN" -eq 0 ]; then task_absent 2; return 0; fi
  task_loading 2
  log_command "$CODEX_BIN" plugin remove "$LEARN_PLUGIN_ID" --json
  "$CODEX_BIN" plugin remove "$LEARN_PLUGIN_ID" --json >> "$INSTALL_LOG" 2>&1 \
    || die "could not remove $LEARN_PLUGIN_ID"
  if [ -n "$MARKETPLACE_ROOT" ]; then
    if marketplace_canonical=$(CDPATH='' cd -P "$MARKETPLACE_ROOT" 2>/dev/null && pwd); then
      if [ "$marketplace_canonical" = "$SCRIPT_DIR" ]; then
        log_command "$CODEX_BIN" plugin marketplace remove "$MARKETPLACE_NAME" --json
        "$CODEX_BIN" plugin marketplace remove "$MARKETPLACE_NAME" --json >> "$INSTALL_LOG" 2>&1 \
          || die "removed Learn but could not remove $MARKETPLACE_NAME marketplace"
      fi
    fi
  fi
  HAS_LEARN=0
  task_done 2
}

print_learn_usage() {
  cat <<'EOF'

Using Learn

1. Start a fresh Codex thread in the repository you want to learn from.
2. Run `$learn Analyze recent work in this repository.` after substantial work.
   It creates `learning_proposal.md` without changing persistent guidance.
3. Review the proposal and explicitly approve only the item IDs you want.
4. Run `$apply-learning Apply only the approved IDs from learning_proposal.md.`

Applied changes are backed up under `.codex/learn/backups/` and staged for
review. Optional workflows: `$lint-learning`, `$forget`, and `$consolidate`.
EOF
}

print_dry_run() {
  printf 'Codex Fleet %s dry run\n\n' "$MODE"
  printf 'Selected components: %s\n' "$(selection_summary)"
  if [ "$MODE" = install ]; then
    if [ "$SELECT_LEARN" -eq 1 ]; then
      show_command "$CODEX_BIN" plugin marketplace add "$SCRIPT_DIR" --json
      show_command "$CODEX_BIN" plugin add "$LEARN_PLUGIN_ID" --json
    fi
    if [ "$SELECT_HISTORY" -eq 1 ]; then
      if history_cache_valid && [ "$REFRESH_ANALYSIS" -eq 0 ]; then
        printf '= reuse %s\n' "$HISTORY_CACHE"
      else
        printf '+ runbook %s\n' "$RUNBOOK_DIR/analyze-history.md"
      fi
    fi
    [ "$SELECT_FEATURES" -eq 0 ] || printf '+ runbook %s\n' "$RUNBOOK_DIR/install-features.md"
    [ "$SELECT_AGENTS" -eq 0 ] || printf '+ runbook %s\n' "$RUNBOOK_DIR/install-agents.md"
    [ "$SELECT_LEARNING" -eq 0 ] || printf '+ runbook %s\n' "$RUNBOOK_DIR/install-learning.md"
  else
    [ "$SELECT_LEARNING" -eq 0 ] || printf '+ runbook %s\n' "$RUNBOOK_DIR/uninstall-learning.md"
    [ "$SELECT_AGENTS" -eq 0 ] || printf '+ runbook %s\n' "$RUNBOOK_DIR/uninstall-agents.md"
    [ "$SELECT_FEATURES" -eq 0 ] || printf '+ runbook %s\n' "$RUNBOOK_DIR/uninstall-features.md"
    [ "$SELECT_HISTORY" -eq 0 ] || printf '+ runbook %s\n' "$RUNBOOK_DIR/uninstall-history.md"
    if [ "$SELECT_LEARN" -eq 1 ]; then
      show_command "$CODEX_BIN" plugin remove "$LEARN_PLUGIN_ID" --json
      show_command "$CODEX_BIN" plugin marketplace remove "$MARKETPLACE_NAME" --json
    fi
  fi
  if [ "$SELECT_HISTORY" -eq 1 ] || [ "$SELECT_FEATURES" -eq 1 ] \
    || [ "$SELECT_AGENTS" -eq 1 ] || [ "$SELECT_LEARNING" -eq 1 ]; then
    printf '+ runbook %s\n' "$RUNBOOK_DIR/validate.md"
  fi
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --install) MODE=install ;;
    --uninstall) MODE=uninstall ;;
    --components)
      shift
      [ "$#" -gt 0 ] || die '--components requires a comma-separated value'
      COMPONENTS_ARG=$1
      ;;
    --components=*) COMPONENTS_ARG=${1#*=} ;;
    --refresh-analysis) REFRESH_ANALYSIS=1 ;;
    --dry-run) DRY_RUN=1 ;;
    --replace-existing-learn) REPLACE_EXISTING_LEARN=1 ;;
    --skip-learn) LEGACY_SKIP_LEARN=1 ;;
    --skip-configure) LEGACY_SKIP_CONFIGURE=1 ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
  shift
done

command -v "$CODEX_BIN" >/dev/null 2>&1 \
  || die "Codex CLI not found. Install Codex $MIN_CODEX_VERSION or newer first."
version_output=$("$CODEX_BIN" --version 2>/dev/null) || die 'could not read Codex version'
current_version=$(printf '%s\n' "$version_output" | awk '
  { for (i = 1; i <= NF; i++) if ($i ~ /^v?[0-9]+\.[0-9]+\.[0-9]+/) { print $i; exit } }
')
[ -n "$current_version" ] || die "could not parse Codex version from: $version_output"
version_at_least "$current_version" "$MIN_CODEX_VERSION" \
  || die "Codex $current_version is too old; upgrade to $MIN_CODEX_VERSION or newer"

[ -f "$MARKETPLACE_FILE" ] || die "missing marketplace manifest: $MARKETPLACE_FILE"
[ -f "$LEARN_PLUGIN_DIR/.codex-plugin/plugin.json" ] || die 'missing bundled Learn manifest'
for required_runbook in "$COMMON_RUNBOOK" \
  "$RUNBOOK_DIR/analyze-history.md" "$RUNBOOK_DIR/install-features.md" \
  "$RUNBOOK_DIR/install-agents.md" "$RUNBOOK_DIR/install-learning.md" \
  "$RUNBOOK_DIR/uninstall-history.md" "$RUNBOOK_DIR/uninstall-features.md" \
  "$RUNBOOK_DIR/uninstall-agents.md" "$RUNBOOK_DIR/uninstall-learning.md" \
  "$RUNBOOK_DIR/validate.md"; do
  [ -f "$required_runbook" ] || die "missing runbook: $required_runbook"
done

if PLUGIN_JSON=$("$CODEX_BIN" plugin list --json 2>/dev/null); then :; else
  die 'could not read installed plugin inventory'
fi
if printf '%s\n' "$PLUGIN_JSON" | json_has_plugin_id "$LEARN_PLUGIN_ID"; then HAS_LEARN=1; fi
if marketplace_json=$("$CODEX_BIN" plugin marketplace list --json 2>/dev/null); then
  MARKETPLACE_ROOT=$(printf '%s\n' "$marketplace_json" | json_marketplace_root)
else
  die 'could not read marketplace inventory'
fi

ui_open
if [ "$MODE" = uninstall ]; then select_none; else select_all; fi
if [ -n "$COMPONENTS_ARG" ]; then
  parse_components
elif [ "$LEGACY_SKIP_CONFIGURE" -eq 1 ]; then
  select_none
  SELECT_LEARN=1
elif [ "$LEGACY_SKIP_LEARN" -eq 1 ]; then
  select_all
  SELECT_LEARN=0
  SELECT_LEARNING=0
elif [ "$UI_TTY" -eq 1 ]; then
  interactive_menu || die 'could not read component selection from the terminal'
else
  [ "$MODE" = install ] \
    || die 'non-interactive uninstall requires --components'
fi
resolve_dependencies

if [ "$(selected_count)" -eq 0 ]; then
  printf 'No components selected; nothing to do.\n'
  exit 0
fi

if [ "$DRY_RUN" -eq 1 ]; then
  print_dry_run
  exit 0
fi

prepare_run_dir

TASK_1="done"
[ "$SELECT_LEARN" -eq 1 ] || TASK_2=skipped
[ "$SELECT_HISTORY" -eq 1 ] || TASK_3=skipped
[ "$SELECT_FEATURES" -eq 1 ] || TASK_4=skipped
[ "$SELECT_AGENTS" -eq 1 ] || TASK_5=skipped
[ "$SELECT_LEARNING" -eq 1 ] || TASK_6=skipped
begin_checklist

if [ "$MODE" = install ]; then
  if [ "$SELECT_LEARN" -eq 1 ]; then install_learn; fi
  if [ "$SELECT_HISTORY" -eq 1 ]; then
    if history_cache_valid && [ "$REFRESH_ANALYSIS" -eq 0 ]; then
      task_cached 3
    else
      run_runbook 3 "$RUNBOOK_DIR/analyze-history.md" analyze-history
      history_cache_valid || die 'history runbook did not produce a valid cache'
    fi
  fi
  if [ "$SELECT_FEATURES" -eq 1 ]; then run_runbook 4 "$RUNBOOK_DIR/install-features.md" install-features; fi
  if [ "$SELECT_AGENTS" -eq 1 ]; then run_runbook 5 "$RUNBOOK_DIR/install-agents.md" install-agents; fi
  if [ "$SELECT_LEARNING" -eq 1 ]; then run_runbook 6 "$RUNBOOK_DIR/install-learning.md" install-learning; fi
else
  if [ "$SELECT_LEARNING" -eq 1 ]; then
    if state_file_valid "$LEARNING_STATE" '# codex-fleet:learning:v1' \
      || { [ -f "$CODEX_HOME/AGENTS.md" ] && awk '
        /history-derived-fleet:learning-pipeline:start/ { found = 1 }
        END { exit !found }
      ' "$CODEX_HOME/AGENTS.md"; }; then
      run_runbook 6 "$RUNBOOK_DIR/uninstall-learning.md" uninstall-learning
    else task_absent 6; fi
  fi
  if [ "$SELECT_AGENTS" -eq 1 ]; then
    if state_file_valid "$AGENT_STATE" '# codex-fleet:agents:v1'; then
      run_runbook 5 "$RUNBOOK_DIR/uninstall-agents.md" uninstall-agents
    else task_absent 5; fi
  fi
  if [ "$SELECT_FEATURES" -eq 1 ]; then
    if state_file_valid "$FEATURE_STATE" '# codex-fleet:features:v1'; then
      run_runbook 4 "$RUNBOOK_DIR/uninstall-features.md" uninstall-features
    else task_absent 4; fi
  fi
  if [ "$SELECT_HISTORY" -eq 1 ]; then
    if [ -f "$HISTORY_CACHE" ] || [ -f "$HISTORY_META" ]; then
      run_runbook 3 "$RUNBOOK_DIR/uninstall-history.md" uninstall-history
    else task_absent 3; fi
  fi
  if [ "$SELECT_LEARN" -eq 1 ]; then uninstall_learn; fi
fi

if [ "$SELECT_HISTORY" -eq 1 ] || [ "$SELECT_FEATURES" -eq 1 ] \
  || [ "$SELECT_AGENTS" -eq 1 ] || [ "$SELECT_LEARNING" -eq 1 ]; then
  run_runbook 7 "$RUNBOOK_DIR/validate.md" validate
else
  task_done 7
fi

printf '\nCodex Fleet %s complete.\n' "$MODE"
printf 'Selected components: %s\n' "$(selection_summary)"
if history_cache_valid; then printf 'History analysis cache: %s\n' "$HISTORY_CACHE"; fi
if load_roles_table; then
  printf '\nConfigured agents\n\n%s\n' "$ROLES_TABLE"
  printf '\nFull fleet manifest: %s/agents/FLEET.md\n' "$CODEX_HOME"
fi
if [ "$HAS_LEARN" -eq 1 ]; then print_learn_usage; fi
printf '\nDetailed run directory: %s\n' "$RUN_DIR"
printf 'Start a new Codex thread to load changed plugin or agent configuration.\n'
