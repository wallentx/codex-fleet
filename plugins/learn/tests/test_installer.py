import fcntl
import os
import pty
import select
import stat
import subprocess
import tempfile
import termios
import textwrap
import time
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
INSTALLER = REPO_ROOT / "install.sh"


FAKE_CODEX = r"""#!/bin/sh
set -eu

printf 'CALL:%s\n' "$*" >> "$FAKE_CODEX_CALLS"

if [ "$1" = "--version" ]; then
  printf '%s\n' 'codex-cli 0.144.1'
  exit 0
fi

if [ "$1" = "plugin" ] && [ "$2" = "list" ]; then
  if [ "${FAKE_LEARN_INSTALLED:-0}" = "1" ]; then
    printf '%s\n' '[{"pluginId":"learn@codex-fleet"}]'
  else
    printf '%s\n' '[]'
  fi
  exit 0
fi

if [ "$1" = "plugin" ] && [ "$2" = "marketplace" ] && [ "$3" = "list" ]; then
  if [ "${FAKE_MARKETPLACE_REGISTERED:-0}" = "1" ]; then
    printf '[\n  {\n    "name": "codex-fleet",\n    "root": "%s"\n  }\n]\n' "$FAKE_REPO_ROOT"
  else
    printf '%s\n' '[]'
  fi
  exit 0
fi

if [ "$1" = "plugin" ]; then
  exit 0
fi

if [ "$1" = "-a" ] && [ "$2" = "never" ] && [ "$3" = "exec" ]; then
  prompt_count=0
  if [ -f "$FAKE_PROMPT_COUNT" ]; then prompt_count=$(sed -n '1p' "$FAKE_PROMPT_COUNT"); fi
  prompt_count=$((prompt_count + 1))
  printf '%s\n' "$prompt_count" > "$FAKE_PROMPT_COUNT"
  prompt_copy="$FAKE_TMP/prompt-$prompt_count.md"
  cat > "$prompt_copy"

  runbook=unknown
  if grep -q '^# Runbook: build the sanitized history-analysis cache' "$prompt_copy"; then runbook=analyze-history; fi
  if grep -q '^# Runbook: configure Codex Fleet features' "$prompt_copy"; then runbook=install-features; fi
  if grep -q '^# Runbook: configure history-derived specialist agents' "$prompt_copy"; then runbook=install-agents; fi
  if grep -q '^# Runbook: configure the reviewed learning pipeline' "$prompt_copy"; then runbook=install-learning; fi
  if grep -q '^# Runbook: remove the history-analysis cache' "$prompt_copy"; then runbook=uninstall-history; fi
  if grep -q '^# Runbook: remove Codex Fleet-owned feature changes' "$prompt_copy"; then runbook=uninstall-features; fi
  if grep -q '^# Runbook: remove Codex Fleet-owned specialist agents' "$prompt_copy"; then runbook=uninstall-agents; fi
  if grep -q '^# Runbook: remove the reviewed learning pipeline' "$prompt_copy"; then runbook=uninstall-learning; fi
  if grep -q '^# Runbook: validate and summarize Codex Fleet state' "$prompt_copy"; then runbook=validate; fi
  printf 'RUNBOOK:%s\n' "$runbook" >> "$FAKE_CODEX_CALLS"

  if [ "${FAKE_SLEEP_RUNBOOK:-}" = "$runbook" ]; then sleep 2; fi
  printf 'VERY_VERBOSE_STDERR:%s\n' "$runbook" >&2
  printf 'VERY_VERBOSE_STDOUT:%s\n' "$runbook"
  if [ "${FAKE_FAIL_RUNBOOK:-}" = "$runbook" ]; then exit 9; fi

  state_dir="$CODEX_HOME/codex-fleet"
  mkdir -p "$state_dir" "$CODEX_HOME/agents"
  case "$runbook" in
    analyze-history)
      printf '%s\n' '<!-- codex-fleet:history-analysis:v1 -->' '# Sanitized analysis' '## Candidate roles' '- code scout' \
        > "$state_dir/history-analysis.md"
      printf '%s\n' 'schema=1' 'generated_at=2026-07-10T00:00:00Z' 'codex_version=0.144.1' \
        'root_sessions=10' 'supporting_sessions=5' 'oldest_session=2026-06-01' 'newest_session=2026-07-10' \
        > "$state_dir/history-analysis.meta"
      ;;
    install-features)
      printf '%s\n' '# codex-fleet:features:v1' 'multi_agent_v2' > "$state_dir/features-enabled-by-fleet.txt"
      ;;
    install-agents)
      printf '%s\n' '# codex-fleet:agents:v1' 'code_scout' 'implementation_engineer' \
        > "$state_dir/agents-installed.txt"
      printf '%s\n' 'name = "code_scout"' > "$CODEX_HOME/agents/code_scout.toml"
      printf '%s\n' 'name = "implementation_engineer"' > "$CODEX_HOME/agents/implementation_engineer.toml"
      ;;
    install-learning)
      printf '%s\n' '# codex-fleet:learning:v1' 'learning_auditor' 'learning_reviewer' 'automation_engineer' \
        > "$state_dir/learning-installed.txt"
      for role in learning_auditor learning_reviewer automation_engineer; do
        printf 'name = "%s"\n' "$role" > "$CODEX_HOME/agents/$role.toml"
      done
      ;;
    uninstall-learning)
      rm -f "$state_dir/learning-installed.txt" "$CODEX_HOME/agents/learning_auditor.toml" \
        "$CODEX_HOME/agents/learning_reviewer.toml" "$CODEX_HOME/agents/automation_engineer.toml"
      ;;
    uninstall-agents)
      rm -f "$state_dir/agents-installed.txt" "$CODEX_HOME/agents/code_scout.toml" \
        "$CODEX_HOME/agents/implementation_engineer.toml"
      ;;
    uninstall-features)
      rm -f "$state_dir/features-enabled-by-fleet.txt"
      ;;
    uninstall-history)
      rm -f "$state_dir/history-analysis.md" "$state_dir/history-analysis.meta"
      ;;
    validate)
      roles_tmp="$FAKE_TMP/roles.txt"
      : > "$roles_tmp"
      for state_file in "$state_dir/agents-installed.txt" "$state_dir/learning-installed.txt"; do
        if [ -f "$state_file" ]; then sed '1d' "$state_file" >> "$roles_tmp"; fi
      done
      if [ -s "$roles_tmp" ]; then
        {
          printf '%s\n' '# History-Derived Codex Fleet' '' '## Roles' '' \
            '<!-- codex-fleet:roles:start -->' \
            '| Role | Model | Provider | Effort | Sandbox | Purpose |' \
            '| --- | --- | --- | --- | --- | --- |'
          while IFS= read -r role; do
            printf '| `%s` | `gpt-test` | `openai` | `high` | `read-only` | Test role |\n' "$role"
          done < "$roles_tmp"
          printf '%s\n' '<!-- codex-fleet:roles:end -->'
        } > "$CODEX_HOME/agents/FLEET.md"
      else
        rm -f "$CODEX_HOME/agents/FLEET.md"
      fi
      ;;
    *) exit 65 ;;
  esac
  exit 0
fi

printf 'unexpected fake Codex arguments: %s\n' "$*" >&2
exit 64
"""


class InstallerTests(unittest.TestCase):
    def make_fixture(
        self,
        *,
        cached: bool = False,
        configured: bool = False,
        learn_installed: bool = False,
        fail_runbook: str = "",
        sleep_runbook: str = "",
    ):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        codex_home = root / "codex home"
        fake_codex = root / "fake codex"
        calls = root / "calls.log"
        prompt_count = root / "prompt-count"
        fake_codex.write_text(textwrap.dedent(FAKE_CODEX), encoding="utf-8")
        fake_codex.chmod(fake_codex.stat().st_mode | stat.S_IXUSR)

        state_dir = codex_home / "codex-fleet"
        if cached or configured:
            state_dir.mkdir(parents=True)
            (state_dir / "history-analysis.md").write_text(
                "<!-- codex-fleet:history-analysis:v1 -->\n# Cached\n",
                encoding="utf-8",
            )
            (state_dir / "history-analysis.meta").write_text("schema=1\n", encoding="utf-8")
        if configured:
            (state_dir / "features-enabled-by-fleet.txt").write_text(
                "# codex-fleet:features:v1\nmulti_agent_v2\n",
                encoding="utf-8",
            )
            (state_dir / "agents-installed.txt").write_text(
                "# codex-fleet:agents:v1\ncode_scout\nimplementation_engineer\n",
                encoding="utf-8",
            )
            (state_dir / "learning-installed.txt").write_text(
                "# codex-fleet:learning:v1\nlearning_auditor\nlearning_reviewer\nautomation_engineer\n",
                encoding="utf-8",
            )

        environment = os.environ.copy()
        environment.update(
            {
                "CODEX_BIN": str(fake_codex),
                "CODEX_HOME": str(codex_home),
                "FAKE_CODEX_CALLS": str(calls),
                "FAKE_PROMPT_COUNT": str(prompt_count),
                "FAKE_REPO_ROOT": str(REPO_ROOT),
                "FAKE_TMP": str(root),
                "FAKE_LEARN_INSTALLED": "1" if learn_installed else "0",
                "FAKE_MARKETPLACE_REGISTERED": "1" if learn_installed else "0",
                "FAKE_FAIL_RUNBOOK": fail_runbook,
                "FAKE_SLEEP_RUNBOOK": sleep_runbook,
                "TERM": "xterm-256color",
            }
        )
        return root, codex_home, calls, environment

    def run_installer(self, *args: str, **fixture_options):
        root, codex_home, calls, environment = self.make_fixture(**fixture_options)
        result = subprocess.run(
            [str(INSTALLER), *args],
            cwd=REPO_ROOT,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )
        return result, root, codex_home, calls

    @staticmethod
    def runbooks(calls: Path):
        return [
            line.removeprefix("RUNBOOK:")
            for line in calls.read_text(encoding="utf-8").splitlines()
            if line.startswith("RUNBOOK:")
        ]

    def test_full_install_runs_independent_runbooks_and_is_quiet(self):
        result, _, codex_home, calls = self.run_installer()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.runbooks(calls),
            ["analyze-history", "install-features", "install-agents", "install-learning", "validate"],
        )
        self.assertNotIn("VERY_VERBOSE", result.stdout)
        self.assertNotIn("VERY_VERBOSE", result.stderr)
        self.assertNotIn("\x1b", result.stderr)
        self.assertIn("Configured agents", result.stdout)
        self.assertIn("`code_scout`", result.stdout)
        self.assertIn("Using Learn", result.stdout)
        self.assertTrue((codex_home / "codex-fleet" / "history-analysis.md").is_file())
        run_dirs = list((codex_home / "log").glob("codex-fleet-install-*"))
        self.assertEqual(len(run_dirs), 1)
        self.assertEqual(stat.S_IMODE(run_dirs[0].stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((run_dirs[0] / "install.log").stat().st_mode), 0o600)

    def test_valid_history_cache_is_reused(self):
        result, _, _, calls = self.run_installer(cached=True)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("analyze-history", self.runbooks(calls))
        self.assertIn("[=] Prepare history analysis (cached)", result.stderr)

    def test_refresh_analysis_ignores_valid_cache(self):
        result, _, _, calls = self.run_installer("--refresh-analysis", cached=True)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.runbooks(calls)[0], "analyze-history")

    def test_install_dependencies_are_resolved(self):
        result, _, codex_home, calls = self.run_installer("--components", "agents")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.runbooks(calls),
            ["analyze-history", "install-features", "install-agents", "validate"],
        )
        self.assertNotIn("plugin add", calls.read_text(encoding="utf-8"))
        self.assertNotIn("Using Learn", result.stdout)
        self.assertTrue((codex_home / "codex-fleet" / "agents-installed.txt").is_file())

    def test_uninstall_dependencies_run_in_reverse_order(self):
        result, _, codex_home, calls = self.run_installer(
            "--uninstall",
            "--components",
            "features",
            configured=True,
            learn_installed=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.runbooks(calls),
            ["uninstall-learning", "uninstall-agents", "uninstall-features", "validate"],
        )
        state_dir = codex_home / "codex-fleet"
        self.assertFalse((state_dir / "features-enabled-by-fleet.txt").exists())
        self.assertFalse((state_dir / "agents-installed.txt").exists())
        self.assertFalse((state_dir / "learning-installed.txt").exists())
        self.assertTrue((state_dir / "history-analysis.md").exists())
        self.assertNotIn("plugin remove learn@codex-fleet", calls.read_text(encoding="utf-8"))

    def test_uninstall_learn_also_removes_learning_pipeline(self):
        result, _, _, calls = self.run_installer(
            "--uninstall",
            "--components=learn",
            configured=True,
            learn_installed=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.runbooks(calls), ["uninstall-learning", "validate"])
        call_text = calls.read_text(encoding="utf-8")
        self.assertIn("plugin remove learn@codex-fleet --json", call_text)
        self.assertIn("plugin marketplace remove codex-fleet --json", call_text)

    def test_noninteractive_uninstall_requires_components(self):
        result, _, _, _ = self.run_installer("--uninstall")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("non-interactive uninstall requires --components", result.stderr)

    def test_dry_run_does_not_create_codex_home(self):
        result, _, codex_home, calls = self.run_installer("--dry-run", "--components=agents")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(codex_home.exists())
        self.assertEqual(
            [line for line in calls.read_text(encoding="utf-8").splitlines() if line.startswith("CALL:")],
            ["CALL:--version", "CALL:plugin list --json", "CALL:plugin marketplace list --json"],
        )
        self.assertIn("Selected components: history,features,agents", result.stdout)

    def test_runbook_failure_is_quiet_and_reports_run_directory(self):
        result, _, _, _ = self.run_installer(fail_runbook="install-agents")

        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("VERY_VERBOSE", result.stdout)
        self.assertNotIn("VERY_VERBOSE", result.stderr)
        self.assertIn("runbook install-agents failed with exit status 9", result.stderr)
        self.assertIn("Detailed run directory:", result.stderr)

    def test_interactive_menu_resolves_dependencies(self):
        output, returncode = self.run_in_pty(
            ["--dry-run"],
            input_bytes=b"n\n4\n\n",
        )

        self.assertEqual(returncode, 0, output)
        self.assertIn("Install Codex Fleet components", output)
        self.assertIn("Selected components: history,features,agents", output)

    def test_tty_checklist_animates_in_place(self):
        output, returncode = self.run_in_pty(
            ["--components=history"],
            fixture_options={"sleep_runbook": "analyze-history"},
        )

        self.assertEqual(returncode, 0, output)
        self.assertIn("\x1b[7A", output)
        self.assertRegex(output, r"\[[/\\|~-]\] Prepare history analysis \(loading\)")
        self.assertIn("[x] Prepare history analysis", output)

    def run_in_pty(self, args, input_bytes=b"", fixture_options=None):
        fixture_options = fixture_options or {}
        _, _, _, environment = self.make_fixture(**fixture_options)
        master_fd, slave_fd = pty.openpty()

        def child_setup():
            os.setsid()
            fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)

        process = subprocess.Popen(
            [str(INSTALLER), *args],
            cwd=REPO_ROOT,
            env=environment,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            preexec_fn=child_setup,
            close_fds=True,
        )
        os.close(slave_fd)
        if input_bytes:
            os.write(master_fd, input_bytes)

        chunks = []
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            ready, _, _ = select.select([master_fd], [], [], 0.2)
            if ready:
                try:
                    chunk = os.read(master_fd, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                chunks.append(chunk)
            if process.poll() is not None and not ready:
                break
        if process.poll() is None:
            process.kill()
        returncode = process.wait(timeout=5)
        os.close(master_fd)
        return b"".join(chunks).decode("utf-8", errors="replace"), returncode


if __name__ == "__main__":
    unittest.main()
