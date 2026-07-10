import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "learn.py"
SPEC = importlib.util.spec_from_file_location("learn_engine", MODULE_PATH)
learn_engine = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["learn_engine"] = learn_engine
SPEC.loader.exec_module(learn_engine)


class LearningEngineTests(unittest.TestCase):
    def test_user_correction_becomes_rule(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = json.dumps(
                [
                    {
                        "role": "user",
                        "content": "Never use grep in this repo; always use rg instead.",
                    }
                ]
            )
            result = learn_engine.analyze_text(raw, root, learn_engine.load_state(root / ".codex/learn/state.json"))
            self.assertEqual(len(result.proposed), 1)
            item = result.proposed[0]
            self.assertEqual(item.kind, "Rule")
            self.assertGreaterEqual(item.confidence, 95)
            self.assertEqual(item.target_path, "AGENTS.md")

    def test_secret_observation_is_ignored_and_redacted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = "User: Always use token ghp_abcdefghijklmnopqrstuvwxyzABCDE12345 for tests."
            result = learn_engine.analyze_text(raw, root, learn_engine.load_state(root / ".codex/learn/state.json"))
            self.assertEqual(result.proposed, [])
            self.assertTrue(result.ignored)
            self.assertNotIn("ghp_", result.ignored[0].text)
            self.assertEqual(result.ignored[0].reason, "secret")

    def test_secret_ignored_observation_does_not_fail_proposal_scan(self):
        item = learn_engine.LearningItem(
            kind="Ignore",
            text="[redacted secret-like observation]",
            evidence="",
            confidence=0,
            rationale="Secret detector matched token or credential pattern.",
            target_path="",
            reason="secret",
        ).finalize()
        result = learn_engine.AnalysisResult(
            source_digest="abc123",
            proposed=[],
            ignored=[item],
            summary="0 proposed, 1 ignored.",
        )
        proposal = learn_engine.render_proposal(result)
        self.assertIn("filtered secret observation", proposal)

    def test_plugin_prompt_examples_are_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = '\n'.join(
                [
                    "User: # Codex /learn Plugin Prompt",
                    'User: - `Rule`: "Always use rg instead of grep inside this repository."',
                    "User: The command must support reading session history from stdin.",
                    "User: Include a `tests/` directory with robust test suites.",
                ]
            )
            result = learn_engine.analyze_text(raw, root, learn_engine.load_state(root / ".codex/learn/state.json"))
            self.assertEqual(result.proposed, [])
            self.assertTrue(result.ignored)
            self.assertTrue(all(item.reason == "non-learning context" for item in result.ignored))

    def test_missing_feature_complaint_is_not_a_rule(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = "User: i dont have the slash commands"
            result = learn_engine.analyze_text(raw, root, learn_engine.load_state(root / ".codex/learn/state.json"))
            self.assertEqual(result.proposed, [])
            self.assertEqual(result.ignored[0].reason, "status complaint")

    def test_deduplicates_against_user_codex_guidance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            home = Path(tmp) / "home"
            root.mkdir()
            (home / ".codex").mkdir(parents=True)
            (home / ".codex" / "AGENTS.md").write_text(
                "- Always prefix shell commands with `rtk`.\n",
                encoding="utf-8",
            )
            raw = "User: Always prefix shell commands with `rtk`."
            with mock.patch.object(learn_engine.Path, "home", return_value=home):
                result = learn_engine.analyze_text(raw, root, learn_engine.load_state(root / ".codex/learn/state.json"))
            self.assertEqual(result.proposed, [])
            self.assertEqual(result.ignored[0].reason, "already present in AGENTS.md")

    def test_home_history_must_match_current_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "current"
            other = Path(tmp) / "other"
            root.mkdir()
            other.mkdir()
            matching = Path(tmp) / "matching.jsonl"
            unrelated = Path(tmp) / "unrelated.jsonl"
            matching.write_text(json.dumps({"cwd": str(root), "role": "user", "content": "Always use rg."}), encoding="utf-8")
            unrelated.write_text(json.dumps({"cwd": str(other), "role": "user", "content": "Always use grep."}), encoding="utf-8")

            self.assertTrue(learn_engine.history_belongs_to_root(matching, root))
            self.assertFalse(learn_engine.history_belongs_to_root(unrelated, root))

    def test_deduplicates_against_existing_guidance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "AGENTS.md").write_text("- Never use grep in this repo; always use rg instead.\n", encoding="utf-8")
            raw = "User: Never use grep in this repo; always use rg instead."
            result = learn_engine.analyze_text(raw, root, learn_engine.load_state(root / ".codex/learn/state.json"))
            self.assertEqual(result.proposed, [])
            self.assertEqual(result.ignored[0].reason, "already present in AGENTS.md")

    def test_apply_append_preserves_existing_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "AGENTS.md"
            target.write_text("# Existing\n\n- Keep this rule.\n", encoding="utf-8")
            backup = root / ".codex" / "learn" / "backups" / "test"
            item = learn_engine.LearningItem(
                kind="Rule",
                text="Always run focused verification after script edits.",
                evidence="user correction",
                confidence=96,
                rationale="Direct correction.",
                target_path="AGENTS.md",
            ).finalize()
            changed = learn_engine.apply_item(root, item, backup)
            content = changed.read_text(encoding="utf-8")
            self.assertIn("- Keep this rule.", content)
            self.assertIn("## Learned Guidance", content)
            self.assertIn("- Always run focused verification after script edits.", content)
            self.assertTrue((backup / "AGENTS.md").is_file())

    def test_proposal_round_trip(self):
        item = learn_engine.LearningItem(
            kind="Repository Note",
            text="This dev container does not support sudo commands.",
            evidence="user message",
            confidence=72,
            rationale="Repository environment fact.",
            target_path=".codex/learn/repository-notes.md",
        ).finalize()
        result = learn_engine.AnalysisResult(source_digest="abc123", proposed=[item], ignored=[], summary="1 proposed, 0 ignored.")
        proposal = learn_engine.render_proposal(result)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "learning_proposal.md"
            path.write_text(proposal, encoding="utf-8")
            parsed = learn_engine.parse_proposal(path)
            self.assertEqual(parsed["items"][0]["id"], item.item_id)
            self.assertEqual(parsed["items"][0]["kind"], "Repository Note")


if __name__ == "__main__":
    unittest.main()
