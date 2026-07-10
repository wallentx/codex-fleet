#!/usr/bin/env sh
set -eu

# Optional hook entrypoint. Codex installations can wire this into a post-session
# hook runner and pass the session log on stdin.
ROOT="${CODEX_LEARN_ROOT:-$(pwd)}"
OUTPUT="${CODEX_LEARN_OUTPUT:-learning_proposal.md}"
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/../scripts" && pwd)"

python3 "$SCRIPT_DIR/learn.py" learn --root "$ROOT" --output "$OUTPUT"
