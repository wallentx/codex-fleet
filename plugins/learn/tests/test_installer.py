import os
import stat
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
INSTALLER = REPO_ROOT / "install.sh"
PROMPT = REPO_ROOT / "prompts" / "configure-fleet.md"


FAKE_CODEX = r"""#!/bin/sh
set -eu

printf '%s\n' "$*" >> "$FAKE_CODEX_CALLS"

if [ "$1" = "--version" ]; then
  printf '%s\n' 'codex-cli 0.144.1'
  exit 0
fi

if [ "$1" = "plugin" ] && [ "$2" = "list" ]; then
  printf '%s\n' '[{"pluginId":"learn@codex-fleet"}]'
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

if [ "$1" = "plugin" ] && [ "$2" = "marketplace" ] && [ "$3" = "add" ]; then
  printf '%s\n' '{"marketplaceName":"codex-fleet"}'
  exit 0
fi

if [ "$1" = "plugin" ] && [ "$2" = "add" ]; then
  printf '%s\n' '{"pluginId":"learn@codex-fleet"}'
  exit 0
fi

if [ "$1" = "plugin" ] && [ "$2" = "remove" ]; then
  exit 0
fi

if [ "$1" = "-a" ] && [ "$2" = "never" ] && [ "$3" = "exec" ]; then
  cat > "$FAKE_PROMPT_COPY"
  printf '%s\n' 'VERY_VERBOSE_STDOUT_FROM_CODEX'
  printf '%s\n' 'VERY_VERBOSE_STDERR_FROM_CODEX' >&2
  if [ "${FAKE_FAIL_EXEC:-0}" = "1" ]; then
    exit 9
  fi
  if [ "${FAKE_NO_MANIFEST:-0}" != "1" ]; then
    mkdir -p "$CODEX_HOME/agents"
    printf '%s\n' \
      '# History-Derived Codex Fleet' \
      '' \
      '## Roles' \
      '' \
      '<!-- codex-fleet:roles:start -->' \
      '| Role | Model | Provider | Effort | Sandbox | Purpose |' \
      '| --- | --- | --- | --- | --- | --- |' \
      '| `code_scout` | `gpt-test-mini` | `openai` | `low` | `read-only` | Find code quickly |' \
      '| `implementation_engineer` | `gpt-test` | `openai` | `high` | `workspace-write` | Implement scoped changes |' \
      '<!-- codex-fleet:roles:end -->' \
      > "$CODEX_HOME/agents/FLEET.md"
    printf '%s\n' \
      '[agents.code_scout]' \
      'description = "Find code quickly"' \
      '' \
      '[agents.implementation_engineer]' \
      'description = "Implement scoped changes"' \
      > "$CODEX_HOME/config.toml"
    if [ "${FAKE_MISMATCHED_ROLES:-0}" = "1" ]; then
      printf '%s\n' '' '[agents.extra_role]' 'description = "Missing from table"' \
        >> "$CODEX_HOME/config.toml"
    fi
  fi
  exit 0
fi

printf 'unexpected fake Codex arguments: %s\n' "$*" >&2
exit 64
"""


class InstallerTests(unittest.TestCase):
    def run_installer(
        self,
        *args: str,
        fail_exec: bool = False,
        no_manifest: bool = False,
        marketplace_registered: bool = False,
        mismatched_roles: bool = False,
    ):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        codex_home = root / "codex home"
        fake_codex = root / "fake codex"
        calls = root / "calls.log"
        prompt_copy = root / "prompt.md"
        fake_codex.write_text(textwrap.dedent(FAKE_CODEX), encoding="utf-8")
        fake_codex.chmod(fake_codex.stat().st_mode | stat.S_IXUSR)

        environment = os.environ.copy()
        environment.update(
            {
                "CODEX_BIN": str(fake_codex),
                "CODEX_HOME": str(codex_home),
                "FAKE_CODEX_CALLS": str(calls),
                "FAKE_PROMPT_COPY": str(prompt_copy),
                "FAKE_REPO_ROOT": str(REPO_ROOT),
                "FAKE_FAIL_EXEC": "1" if fail_exec else "0",
                "FAKE_NO_MANIFEST": "1" if no_manifest else "0",
                "FAKE_MARKETPLACE_REGISTERED": "1" if marketplace_registered else "0",
                "FAKE_MISMATCHED_ROLES": "1" if mismatched_roles else "0",
                "TERM": "dumb",
            }
        )
        result = subprocess.run(
            [str(INSTALLER), *args],
            cwd=REPO_ROOT,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )
        return result, codex_home, calls, prompt_copy

    def test_quiet_install_prints_checklist_roles_and_learn_help(self):
        result, codex_home, calls, prompt_copy = self.run_installer()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("VERY_VERBOSE", result.stdout)
        self.assertNotIn("VERY_VERBOSE", result.stderr)
        self.assertNotIn("\x1b", result.stderr)
        self.assertIn("[~] Analyze history and configure fleet (loading)", result.stderr)
        self.assertIn("[x] Analyze history and configure fleet", result.stderr)
        self.assertIn("Configured agents", result.stdout)
        self.assertIn("`code_scout`", result.stdout)
        self.assertIn("`implementation_engineer`", result.stdout)
        self.assertIn("Using Learn", result.stdout)
        self.assertIn("$learn Analyze recent work", result.stdout)
        self.assertIn("$apply-learning Apply only", result.stdout)
        self.assertIn("Detailed log:", result.stdout)
        self.assertIn("Codex final output:", result.stdout)

        self.assertEqual(prompt_copy.read_text(encoding="utf-8"), PROMPT.read_text(encoding="utf-8"))
        self.assertIn("-a never exec", calls.read_text(encoding="utf-8"))

        logs = list((codex_home / "log").glob("*.log"))
        reports = list((codex_home / "log").glob("*.final.txt"))
        self.assertEqual(len(logs), 1)
        self.assertEqual(len(reports), 1)
        self.assertEqual(stat.S_IMODE(logs[0].stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(reports[0].stat().st_mode), 0o600)
        self.assertIn("VERY_VERBOSE_STDERR_FROM_CODEX", logs[0].read_text(encoding="utf-8"))
        self.assertIn("VERY_VERBOSE_STDOUT_FROM_CODEX", reports[0].read_text(encoding="utf-8"))

    def test_dry_run_does_not_create_codex_home(self):
        result, codex_home, calls, _ = self.run_installer("--dry-run")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(codex_home.exists())
        self.assertEqual(calls.read_text(encoding="utf-8").strip(), "--version")
        self.assertIn("-a never exec", result.stdout)
        self.assertIn("codex home' -s", result.stdout)
        self.assertIn("[-] Analyze history and configure fleet (skipped)", result.stderr)

    def test_configuration_failure_is_quiet_and_reports_log(self):
        result, codex_home, _, _ = self.run_installer(fail_exec=True)

        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("VERY_VERBOSE", result.stdout)
        self.assertNotIn("VERY_VERBOSE", result.stderr)
        self.assertIn("[!] Analyze history and configure fleet (failed)", result.stderr)
        self.assertIn("fleet configuration failed with exit status 9", result.stderr)
        self.assertIn("Detailed log:", result.stderr)
        self.assertIn("Codex final output:", result.stderr)
        log = next((codex_home / "log").glob("*.log"))
        self.assertIn("VERY_VERBOSE_STDERR_FROM_CODEX", log.read_text(encoding="utf-8"))

    def test_missing_roles_table_fails_summary(self):
        result, _, _, _ = self.run_installer(no_manifest=True)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("[!] Validate and summarize agents (failed)", result.stderr)
        self.assertIn("has no valid roles table", result.stderr)

    def test_roles_table_must_match_configured_agents(self):
        result, _, _, _ = self.run_installer(mismatched_roles=True)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("[!] Validate and summarize agents (failed)", result.stderr)
        self.assertIn("has no valid roles table", result.stderr)

    def test_registered_marketplace_is_reused(self):
        result, _, calls, _ = self.run_installer(marketplace_registered=True)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("plugin marketplace add", calls.read_text(encoding="utf-8"))

    def test_skip_configure_omits_agent_summary(self):
        result, _, calls, prompt_copy = self.run_installer("--skip-configure")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(prompt_copy.exists())
        self.assertNotIn("-a never exec", calls.read_text(encoding="utf-8"))
        self.assertIn("[-] Analyze history and configure fleet (skipped)", result.stderr)
        self.assertNotIn("Configured agents", result.stdout)
        self.assertIn("Using Learn", result.stdout)

    def test_skip_learn_configures_without_plugin_commands(self):
        result, _, calls, _ = self.run_installer("--skip-learn")

        self.assertEqual(result.returncode, 0, result.stderr)
        call_text = calls.read_text(encoding="utf-8")
        self.assertNotIn("plugin list", call_text)
        self.assertNotIn("plugin marketplace", call_text)
        self.assertNotIn("plugin add", call_text)
        self.assertIn("-a never exec", call_text)
        self.assertIn("[-] Install Learn plugin (skipped)", result.stderr)
        self.assertIn("Configured agents", result.stdout)
        self.assertNotIn("Using Learn", result.stdout)


if __name__ == "__main__":
    unittest.main()
