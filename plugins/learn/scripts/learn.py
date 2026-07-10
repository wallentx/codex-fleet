#!/usr/bin/env python3
"""Codex learn plugin engine.

The script is intentionally dependency-free so plugin skills can run it in a
fresh checkout or constrained environment. It favors conservative proposals:
candidate learnings must be explicit, non-secret, and non-duplicate before they
are written to a proposal.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DATA_START = "<!-- codex-learn-data:v1"
DATA_END = "codex-learn-data:end -->"
STATE_VERSION = 1
DEFAULT_STATE = {
    "version": STATE_VERSION,
    "processed_sessions": {},
    "processed_item_hashes": {},
    "ignored_patterns": {},
    "applied_items": {},
}

SECRET_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{30,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9]{24,}\b"),
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\b\s*[:=]\s*['\"]?[^'\"\s]{8,}"),
]

DIRECT_RULE_RE = re.compile(
    r"(?i)\b("
    r"always|never|do not|don't|dont|must|must not|should not|shouldn't|"
    r"prefer|avoid|use .{1,80} instead of|rather than"
    r")\b"
)
REPO_FACT_RE = re.compile(
    r"(?i)\b(this repo|this project|this checkout|dev container|container|termux|ci|"
    r"github actions|workspace|environment|toolchain)\b"
)
SKILL_RE = re.compile(
    r"(?i)\b(workflow|procedure|steps?|run .+ then|first .+ then|deploy|release|"
    r"triage|debugging sequence|playbook)\b"
)
SUCCESS_RE = re.compile(r"(?i)\b(that fixed it|works now|that worked|successful|passed now)\b")
TRANSIENT_RE = re.compile(
    r"(?i)\b(print\(\"?here|temporary|temp hack|scratch|line \d+|fixed bug|one-off|"
    r"for this session|just for now|debug log|console\.log)\b"
)
VAGUE_RE = re.compile(r"(?i)\b(be careful|best practices|as needed|where appropriate|nice|better)\b")
LEARNING_EXAMPLE_RE = re.compile(r"^`?(Rule|Skill|Repository Note|Ignore)`?\s*:\s*[\"']")
SPEC_OR_SCHEMA_RE = re.compile(
    r"(?i)\b("
    r"codex /learn plugin prompt|high-level architecture|commands & workflows|"
    r"proposal generation|learning heuristics|heuristic & confidence scoring|"
    r"safety & guardrails|testing & verification|deliverables|"
    r"classification engine|patching/updating mechanism|mock repository layout|"
    r"standard codex cli plugin specification|workflow preferences|"
    r"universal rule|strong convention"
    r")\b"
)
SPEC_INSTRUCTION_RE = re.compile(
    r"(?i)^(the command|the proposal|each skill|the purpose|this should feel|"
    r"implement the project|create a complete|build a plugin|assign a confidence score|"
    r"run an entropy-based|test that|verify that|include a .*tests.* directory|"
    r"do not modify any persistent rules|output a structured proposal|detect overlapping)"
)
SCHEMA_LINE_RE = re.compile(
    r"(?i)^[a-z_][a-z0-9_.-]*\??:\s*"
    r"(string|integer|boolean|number|array|object|null|true|false|\"|')"
)
STATUS_COMPLAINT_RE = re.compile(r"(?i)\b(i|we)\s+(do not|don't|dont)\s+have\b")


@dataclass
class LearningItem:
    kind: str
    text: str
    evidence: str
    confidence: int
    rationale: str
    target_path: str
    action: str = "append"
    old_text: str = ""
    replacement: str = ""
    item_id: str = ""
    item_hash: str = ""
    reason: str = ""

    def finalize(self) -> "LearningItem":
        basis = f"{self.kind}\n{normalize_text(self.text)}\n{self.target_path}\n{self.action}"
        self.item_hash = sha256_text(basis)
        self.item_id = self.item_id or f"L-{self.item_hash[:12]}"
        return self

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.item_id,
            "hash": self.item_hash,
            "kind": self.kind,
            "text": self.text,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "target_path": self.target_path,
            "action": self.action,
            "old_text": self.old_text,
            "replacement": self.replacement,
            "reason": self.reason,
        }

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> "LearningItem":
        return cls(
            kind=str(payload.get("kind", "")),
            text=str(payload.get("text", "")),
            evidence=str(payload.get("evidence", "")),
            confidence=int(payload.get("confidence", 0)),
            rationale=str(payload.get("rationale", "")),
            target_path=str(payload.get("target_path", "")),
            action=str(payload.get("action", "append")),
            old_text=str(payload.get("old_text", "")),
            replacement=str(payload.get("replacement", "")),
            item_id=str(payload.get("id", "")),
            item_hash=str(payload.get("hash", "")),
            reason=str(payload.get("reason", "")),
        ).finalize()


@dataclass
class AnalysisResult:
    source_digest: str
    proposed: list[LearningItem] = field(default_factory=list)
    ignored: list[LearningItem] = field(default_factory=list)
    summary: str = ""


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def normalize_text(text: str) -> str:
    lowered = text.lower()
    lowered = re.sub(r"`([^`]+)`", r"\1", lowered)
    lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def token_set(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9][a-z0-9_-]{2,}", normalize_text(text)))


def jaccard(left: str, right: str) -> float:
    a = token_set(left)
    b = token_set(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def slugify(text: str, fallback: str = "learned-skill") -> str:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    stop = {"always", "never", "prefer", "avoid", "use", "when", "then", "with", "from"}
    kept = [token for token in tokens if token not in stop][:6]
    slug = "-".join(kept) or fallback
    return slug[:64].strip("-") or fallback


def is_secret_like(text: str) -> bool:
    if any(pattern.search(text) for pattern in SECRET_PATTERNS):
        return True
    for token in re.findall(r"[A-Za-z0-9_+=/.-]{24,}", text):
        if entropy(token) >= 4.2 and len(set(token)) >= 12:
            return True
    return False


def entropy(value: str) -> float:
    if not value:
        return 0.0
    counts = {char: value.count(char) for char in set(value)}
    return -sum((count / len(value)) * math.log2(count / len(value)) for count in counts.values())


def redact_secrets(text: str) -> str:
    redacted = text
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED_SECRET]", redacted)
    redacted = re.sub(r"[A-Za-z0-9_+=/.-]{32,}", "[REDACTED_TOKEN]", redacted)
    return redacted


def read_text(path: Path, limit: int = 1_000_000) -> str:
    data = path.read_bytes()
    if len(data) > limit:
        data = data[-limit:]
    return data.decode("utf-8", errors="replace")


def path_is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def history_belongs_to_root(path: Path, root: Path) -> bool:
    if path_is_under(path, root):
        return True
    root_text = str(root.resolve())
    try:
        data = read_text(path, limit=1_000_000)
    except OSError:
        return False
    return root_text in data


def content_to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(content_to_text(item) for item in value if content_to_text(item))
    if isinstance(value, dict):
        for key in ("text", "content", "message", "value"):
            if key in value:
                return content_to_text(value[key])
        if "parts" in value:
            return content_to_text(value["parts"])
        return " ".join(content_to_text(item) for item in value.values())
    return str(value)


def extract_messages(raw: str) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []

    def visit(obj: Any) -> None:
        if isinstance(obj, dict):
            role = obj.get("role") or obj.get("speaker") or obj.get("author")
            if role is not None and any(key in obj for key in ("content", "text", "message", "parts")):
                messages.append(
                    {
                        "role": str(role).lower(),
                        "content": content_to_text(obj.get("content", obj.get("text", obj.get("message", obj.get("parts"))))).strip(),
                    }
                )
                return
            for value in obj.values():
                visit(value)
        elif isinstance(obj, list):
            for item in obj:
                visit(item)

    try:
        visit(json.loads(raw))
    except json.JSONDecodeError:
        pass

    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            visit(json.loads(stripped))
            continue
        except json.JSONDecodeError:
            pass
        match = re.match(r"(?i)^(user|assistant|system|tool)\s*:\s*(.+)$", stripped)
        if match:
            messages.append({"role": match.group(1).lower(), "content": match.group(2).strip()})

    if not messages and raw.strip():
        messages.append({"role": "user", "content": raw.strip()})
    return [message for message in messages if message["content"]]


def split_observations(text: str) -> list[str]:
    chunks: list[str] = []
    for line in text.splitlines():
        line = line.strip(" -\t")
        if not line:
            continue
        parts = re.split(r"(?<=[.!?])\s+", line)
        for part in parts:
            part = part.strip()
            if 8 <= len(part) <= 600:
                chunks.append(part)
    return chunks


def is_non_learning_context(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if stripped.startswith(("#", "```", "---", "<")):
        return True
    if stripped.startswith("**"):
        return True
    if stripped.startswith(("├──", "└──", "│", "```text")):
        return True
    if LEARNING_EXAMPLE_RE.search(stripped):
        return True
    if SPEC_OR_SCHEMA_RE.search(stripped) or SPEC_INSTRUCTION_RE.search(stripped):
        return True
    if SCHEMA_LINE_RE.search(stripped):
        return True
    return False


def clean_learning_text(text: str) -> str:
    cleaned = re.sub(
        r"(?i)^(please|for future reference|remember that|remember|going forward[:,]?)\s+",
        "",
        text.strip(),
    )
    cleaned = cleaned.strip("` ")
    if cleaned and cleaned[-1] not in ".!?":
        cleaned += "."
    return cleaned


def target_for(kind: str, text: str) -> str:
    if kind == "Rule":
        return "AGENTS.md"
    if kind == "Skill":
        return f".codex/skills/{slugify(text)}/SKILL.md"
    if kind == "Repository Note":
        return ".codex/learn/repository-notes.md"
    return ""


def classify_sentence(sentence: str) -> LearningItem:
    raw = sentence.strip()
    if is_non_learning_context(raw):
        return LearningItem(
            kind="Ignore",
            text=redact_secrets(raw),
            evidence="",
            confidence=0,
            rationale="Observation is prompt, spec, or schema scaffolding rather than reusable guidance.",
            target_path="",
            reason="non-learning context",
        ).finalize()
    if STATUS_COMPLAINT_RE.search(raw):
        return LearningItem(
            kind="Ignore",
            text=redact_secrets(raw),
            evidence="",
            confidence=35,
            rationale="Observation reports missing current functionality rather than durable guidance.",
            target_path="",
            reason="status complaint",
        ).finalize()
    if is_secret_like(raw):
        return LearningItem(
            kind="Ignore",
            text="[redacted secret-like observation]",
            evidence="",
            confidence=0,
            rationale="Secret detector matched token or credential pattern.",
            target_path="",
            reason="secret",
        ).finalize()
    if TRANSIENT_RE.search(raw):
        return LearningItem(
            kind="Ignore",
            text=redact_secrets(raw),
            evidence="",
            confidence=25,
            rationale="Observation looks session-specific or temporary.",
            target_path="",
            reason="transient",
        ).finalize()

    cleaned = clean_learning_text(raw)
    direct = DIRECT_RULE_RE.search(raw) is not None
    repo_fact = REPO_FACT_RE.search(raw) is not None
    sequenceish = bool(
        re.search(r"(?i)\b(run .+ then|first .+ then|then .+ then)\b", raw)
        or re.search(r"\b1\.\s+.+\b2\.\s+", raw)
    )
    skillish = SKILL_RE.search(raw) is not None or sequenceish

    if direct and not sequenceish:
        kind = "Rule"
        confidence = 96
        rationale = "Direct user correction or explicit preference detected."
    elif skillish and len(raw.split()) >= 7:
        kind = "Skill"
        confidence = 86 if direct else 82
        rationale = "Multi-step workflow or repeatable procedure detected."
    elif repo_fact:
        kind = "Repository Note"
        confidence = 72
        rationale = "Repository or environment-specific fact detected."
    else:
        return LearningItem(
            kind="Ignore",
            text=redact_secrets(raw),
            evidence="",
            confidence=45,
            rationale="No durable learning signal was strong enough.",
            target_path="",
            reason="low confidence",
        ).finalize()

    return LearningItem(
        kind=kind,
        text=cleaned,
        evidence=redact_secrets(raw[:280]),
        confidence=confidence,
        rationale=rationale,
        target_path=target_for(kind, cleaned),
    ).finalize()


def extract_commands(text: str) -> list[str]:
    commands: list[str] = []
    in_fence = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if not stripped:
            continue
        if stripped.startswith("$ "):
            commands.append(stripped[2:])
        elif in_fence and re.match(r"^[a-zA-Z0-9_.-]+(\s+|$)", stripped):
            commands.append(stripped)
    return commands[:8]


def classify_messages(messages: list[dict[str, str]]) -> list[LearningItem]:
    candidates: list[LearningItem] = []
    previous_assistant = ""
    for message in messages:
        role = message["role"]
        content = message["content"]
        if role == "assistant":
            previous_assistant = content
            continue
        if role not in {"user", "unknown"}:
            continue
        if SUCCESS_RE.search(content) and previous_assistant:
            commands = extract_commands(previous_assistant)
            if len(commands) >= 2:
                text = "Successful workflow: " + " ; ".join(commands)
                candidates.append(
                    LearningItem(
                        kind="Skill",
                        text=clean_learning_text(text),
                        evidence=redact_secrets(content[:220]),
                        confidence=84,
                        rationale="User confirmed a multi-command sequence succeeded.",
                        target_path=target_for("Skill", text),
                    ).finalize()
                )
        for sentence in split_observations(content):
            candidates.append(classify_sentence(sentence))
    return candidates


def guidance_paths(root: Path) -> list[Path]:
    names = ["AGENTS.md", "CLAUDE.md", "GEMINI.md", "README.md"]
    paths = [root / name for name in names]
    for folder in (root / ".codex", root / ".claude", root / "skills"):
        if folder.exists():
            paths.extend(path for path in folder.rglob("*.md") if ".git" not in path.parts)
    home = Path.home()
    for path in (home / ".codex" / "AGENTS.md", home / ".codex" / "AGENTS.override.md"):
        paths.append(path)
    for folder in (home / ".codex" / "rules", home / ".agents" / "skills"):
        if folder.exists():
            paths.extend(path for path in folder.rglob("*.md") if ".git" not in path.parts)
    return sorted({path.resolve() for path in paths if path.is_file()})


def load_guidance(root: Path) -> list[tuple[Path, str]]:
    entries: list[tuple[Path, str]] = []
    for path in guidance_paths(root):
        try:
            entries.append((path, read_text(path, limit=500_000)))
        except OSError:
            continue
    return entries


def is_duplicate(item: LearningItem, guidance: list[tuple[Path, str]]) -> tuple[bool, str]:
    normalized = normalize_text(item.text)
    if not normalized:
        return True, "empty"
    for path, content in guidance:
        existing = normalize_text(content)
        if normalized in existing:
            return True, f"already present in {path.name}"
        if jaccard(item.text, content) > 0.84:
            return True, f"similar to {path.name}"
    return False, ""


def load_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return json.loads(json.dumps(DEFAULT_STATE))
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return json.loads(json.dumps(DEFAULT_STATE))
    state = json.loads(json.dumps(DEFAULT_STATE))
    if isinstance(payload, dict):
        state.update(payload)
    return state


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def analyze_text(raw: str, root: Path, state: dict[str, Any], force: bool = False) -> AnalysisResult:
    source_digest = sha256_text(raw)[:16]
    if not force and source_digest in state.get("processed_sessions", {}):
        ignored = [
            LearningItem(
                kind="Ignore",
                text=f"Session {source_digest} was already processed.",
                evidence="",
                confidence=0,
                rationale="State file marks this session digest as processed.",
                target_path="",
                reason="processed session",
            ).finalize()
        ]
        return AnalysisResult(source_digest=source_digest, proposed=[], ignored=ignored, summary="No new learnings. Session already processed.")

    messages = extract_messages(raw)
    candidates = classify_messages(messages)
    guidance = load_guidance(root)
    proposed: list[LearningItem] = []
    ignored: list[LearningItem] = []
    seen_hashes: set[str] = set()
    state_hashes = set(state.get("processed_item_hashes", {}).keys())
    ignored_hashes = set(state.get("ignored_patterns", {}).keys())

    for candidate in candidates:
        candidate.finalize()
        if candidate.item_hash in seen_hashes:
            candidate.kind = "Ignore"
            candidate.reason = "duplicate candidate"
            candidate.rationale = "Same candidate appeared more than once in the session."
            ignored.append(candidate)
            continue
        seen_hashes.add(candidate.item_hash)

        if candidate.kind == "Ignore":
            ignored.append(candidate)
            continue
        if candidate.item_hash in ignored_hashes:
            candidate.kind = "Ignore"
            candidate.reason = "explicitly ignored"
            candidate.rationale = "State file marks this pattern ignored."
            ignored.append(candidate)
            continue
        if candidate.item_hash in state_hashes and not force:
            candidate.kind = "Ignore"
            candidate.reason = "already proposed"
            candidate.rationale = "State file marks this item hash as already proposed."
            ignored.append(candidate)
            continue
        if candidate.confidence < 60 and not force:
            candidate.kind = "Ignore"
            candidate.reason = "below confidence threshold"
            ignored.append(candidate)
            continue
        duplicate, reason = is_duplicate(candidate, guidance)
        if duplicate and not force:
            candidate.kind = "Ignore"
            candidate.reason = reason
            candidate.rationale = "Candidate overlaps existing guidance."
            ignored.append(candidate)
            continue
        proposed.append(candidate)

    summary = f"{len(proposed)} proposed, {len(ignored)} ignored from {len(messages)} messages."
    return AnalysisResult(source_digest=source_digest, proposed=proposed, ignored=ignored, summary=summary)


def render_proposal(result: AnalysisResult, title: str = "Learning Proposal") -> str:
    generated_at = utc_now()
    payload = {
        "version": 1,
        "title": title,
        "generated_at": generated_at,
        "source_digest": result.source_digest,
        "summary": result.summary,
        "items": [item.to_json() for item in result.proposed],
        "ignored": [item.to_json() for item in result.ignored],
    }
    lines = [
        f"# {title}",
        "",
        DATA_START,
        json.dumps(payload, indent=2, sort_keys=True),
        DATA_END,
        "",
        "## Executive Summary",
        "",
        result.summary or "No actionable learnings found.",
        "",
        "## Proposed Additions",
        "",
    ]
    additions = [item for item in result.proposed if item.action in {"append", "create"}]
    if not additions:
        lines.extend(["No proposed additions.", ""])
    else:
        for kind in ("Rule", "Skill", "Repository Note"):
            group = [item for item in additions if item.kind == kind]
            if not group:
                continue
            lines.extend([f"### {kind}", ""])
            for item in group:
                lines.extend(render_item_markdown(item))

    updates = [item for item in result.proposed if item.action == "replace"]
    lines.extend(["## Proposed Updates", ""])
    if not updates:
        lines.extend(["No proposed updates.", ""])
    else:
        for item in updates:
            lines.extend(render_item_markdown(item))

    deletions = [item for item in result.proposed if item.action == "delete"]
    lines.extend(["## Proposed Deletions/Deprecations", ""])
    if not deletions:
        lines.extend(["No proposed deletions.", ""])
    else:
        for item in deletions:
            lines.extend(render_item_markdown(item))

    lines.extend(["## Metadata", ""])
    for item in result.proposed:
        lines.extend(
            [
                f"- `{item.item_id}` `{item.kind}` confidence `{item.confidence}` target `{item.target_path}`",
                f"  Rationale: {item.rationale}",
            ]
        )
    if not result.proposed:
        lines.append("- No proposed items.")
    lines.extend(["", "### Ignored Observations", ""])
    if not result.ignored:
        lines.extend(["No ignored observations.", ""])
    else:
        for item in result.ignored:
            reason = item.reason or item.rationale
            if item.reason == "secret":
                lines.append(f"- `{item.item_id}` filtered secret observation.")
            else:
                lines.append(f"- `{item.item_id}` {reason}: {item.text}")
        lines.append("")

    proposal = "\n".join(lines).rstrip() + "\n"
    findings = secret_findings(proposal)
    if findings:
        joined = ", ".join(findings[:3])
        raise ValueError(f"proposal failed secret scan: {joined}")
    return proposal


def render_item_markdown(item: LearningItem) -> list[str]:
    lines = [
        f"- ID: `{item.item_id}`",
        f"  Type: `{item.kind}`",
        f"  Target: `{item.target_path}`",
        f"  Confidence: `{item.confidence}`",
        f"  Rationale: {item.rationale}",
        "",
        "```diff",
    ]
    if item.action == "delete":
        lines.append(f"- {item.old_text or item.text}")
    elif item.action == "replace":
        lines.append(f"- {item.old_text}")
        lines.append(f"+ {item.replacement or item.text}")
    elif item.kind == "Skill":
        lines.append(f"+ create {item.target_path}")
        lines.append(f"+ {item.text}")
    else:
        lines.append(f"+ {item.text}")
    lines.extend(["```", ""])
    return lines


def secret_findings(text: str) -> list[str]:
    findings: list[str] = []
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            findings.append(pattern.pattern[:60])
    for token in re.findall(r"[A-Za-z0-9_+=/.-]{32,}", text):
        if "codex-learn-data" in token:
            continue
        if re.fullmatch(r"[a-f0-9]{32,64}", token):
            continue
        if "/" in token and token.endswith((".md", ".json", ".yaml", ".yml", ".txt", ".log")):
            continue
        if entropy(token) >= 4.4 and len(set(token)) >= 12:
            findings.append("high-entropy token")
            break
    return findings


def write_proposal(path: Path, proposal: str) -> None:
    path.write_text(proposal, encoding="utf-8")


def parse_proposal(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    start = text.find(DATA_START)
    end = text.find(DATA_END)
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"{path} does not contain codex-learn proposal metadata")
    json_start = text.find("\n", start) + 1
    data = text[json_start:end].strip()
    payload = json.loads(data)
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise ValueError("unsupported proposal metadata version")
    return payload


def state_path_for(root: Path, raw: str | None) -> Path:
    return Path(raw).expanduser().resolve() if raw else root / ".codex" / "learn" / "state.json"


def read_session_input(args: argparse.Namespace, root: Path) -> str:
    chunks: list[str] = []
    for raw_path in args.file or []:
        chunks.append(read_text(Path(raw_path).expanduser()))
    if not sys.stdin.isatty():
        stdin = sys.stdin.read()
        if stdin.strip():
            chunks.append(stdin)
    if not chunks:
        chunks.extend(read_recent_history(root))
    return "\n".join(chunks)


def read_recent_history(root: Path, max_files: int = 5) -> list[str]:
    home = Path.home()

    def collect_files(folders: list[Path]) -> list[Path]:
        found: list[Path] = []
        for folder in folders:
            if not folder.is_dir():
                continue
            for pattern in ("*.jsonl", "*.json", "*.log", "*.md", "*.txt"):
                found.extend(folder.rglob(pattern))
        return found

    local_candidates = collect_files([root / ".codex" / "history", root / ".codex" / "sessions"])
    local_candidates.extend(
        db_path
        for db_path in [root / ".codex" / "history.db", root / ".codex" / "codex.sqlite"]
        if db_path.is_file()
    )

    if local_candidates:
        candidates = local_candidates
    else:
        home_candidates = collect_files([home / ".codex" / "history", home / ".codex" / "sessions"])
        candidates = [path for path in home_candidates if history_belongs_to_root(path, root)]
        for db_path in [home / ".codex" / "history.db", home / ".codex" / "codex.sqlite"]:
            if db_path.is_file() and history_belongs_to_root(db_path, root):
                candidates.append(db_path)

    candidates = sorted(set(candidates), key=lambda path: path.stat().st_mtime if path.exists() else 0, reverse=True)
    chunks: list[str] = []
    for path in candidates[:max_files]:
        try:
            if path.suffix in {".db", ".sqlite", ".sqlite3"}:
                chunks.append(read_sqlite_history(path))
            else:
                chunks.append(read_text(path))
        except OSError:
            continue
    return [chunk for chunk in chunks if chunk.strip()]


def read_sqlite_history(path: Path) -> str:
    parts: list[str] = []
    con = sqlite3.connect(str(path))
    try:
        tables = [row[0] for row in con.execute("select name from sqlite_master where type='table'")]
        for table in tables[:20]:
            cols = con.execute(f'pragma table_info("{table}")').fetchall()
            text_cols = [row[1] for row in cols if str(row[2]).upper() in {"TEXT", ""}]
            if not text_cols:
                continue
            selected = ", ".join(f'"{col}"' for col in text_cols[:6])
            for row in con.execute(f'select {selected} from "{table}" limit 200'):
                parts.append(" ".join(str(cell) for cell in row if cell))
    finally:
        con.close()
    return "\n".join(parts)


def cmd_learn(args: argparse.Namespace) -> int:
    root = Path(args.root).expanduser().resolve()
    raw = read_session_input(args, root)
    if not raw.strip():
        raise SystemExit("No session history found. Pass --file, pipe stdin, or run from a repo with .codex history.")
    state_path = state_path_for(root, args.state)
    state = load_state(state_path)
    result = analyze_text(raw, root, state, force=args.force)
    proposal = render_proposal(result)
    output = Path(args.output).expanduser()
    write_proposal(output, proposal)

    if not args.no_state_write:
        now = utc_now()
        state.setdefault("processed_sessions", {})[result.source_digest] = {
            "processed_at": now,
            "proposal": str(output),
            "item_ids": [item.item_id for item in result.proposed],
        }
        for item in result.proposed:
            state.setdefault("processed_item_hashes", {})[item.item_hash] = {
                "item_id": item.item_id,
                "kind": item.kind,
                "target_path": item.target_path,
                "processed_at": now,
            }
        for item in result.ignored:
            if item.reason in {"secret", "transient"}:
                state.setdefault("ignored_patterns", {})[item.item_hash] = {
                    "reason": item.reason,
                    "processed_at": now,
                }
        save_state(state_path, state)

    print(f"Wrote {output}: {result.summary}")
    return 0


def safe_target(root: Path, target_path: str) -> Path:
    target = (root / target_path).resolve()
    root_resolved = root.resolve()
    try:
        target.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(f"target path escapes root: {target_path}") from exc
    return target


def ensure_backup(root: Path, target: Path, backup_root: Path) -> None:
    if target.exists():
        rel = target.relative_to(root)
        backup = backup_root / rel
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, backup)


def append_guidance(path: Path, heading: str, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    block = f"- {text.strip()}\n"
    if not path.exists():
        path.write_text(f"# Guidance\n\n## {heading}\n\n{block}", encoding="utf-8")
        return
    current = path.read_text(encoding="utf-8")
    if f"## {heading}" not in current:
        separator = "\n" if current.endswith("\n") else "\n\n"
        current = f"{current}{separator}## {heading}\n\n"
    if block.strip() not in current:
        current = current.rstrip() + "\n" + block
    path.write_text(current, encoding="utf-8")


def skill_body(item: LearningItem) -> str:
    name = Path(item.target_path).parent.name or slugify(item.text)
    title = " ".join(part.capitalize() for part in name.split("-"))
    description = item.text.replace("\n", " ")
    if len(description) > 220:
        description = description[:217].rstrip() + "..."
    return (
        f"---\n"
        f"name: {name}\n"
        f"description: {description} Use when this repeatable workflow appears in a future task.\n"
        f"---\n\n"
        f"# {title}\n\n"
        f"## Workflow\n\n"
        f"{item.text.strip()}\n\n"
        f"## Evidence\n\n"
        f"{item.evidence or 'Derived from a prior successful session.'}\n"
    )


def apply_item(root: Path, item: LearningItem, backup_root: Path) -> Path:
    target = safe_target(root, item.target_path)
    ensure_backup(root, target, backup_root)
    if item.action in {"append", "create"}:
        if item.kind == "Skill":
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                append_guidance(target, "Learned Workflow", item.text)
            else:
                target.write_text(skill_body(item), encoding="utf-8")
        elif item.kind == "Repository Note":
            append_guidance(target, "Repository Notes", item.text)
        else:
            append_guidance(target, "Learned Guidance", item.text)
    elif item.action == "replace":
        current = target.read_text(encoding="utf-8")
        if item.old_text not in current:
            raise ValueError(f"old text not found in {item.target_path} for {item.item_id}")
        target.write_text(current.replace(item.old_text, item.replacement or item.text, 1), encoding="utf-8")
    elif item.action == "delete":
        current = target.read_text(encoding="utf-8")
        old = item.old_text or item.text
        if old not in current:
            raise ValueError(f"text not found in {item.target_path} for {item.item_id}")
        target.write_text(current.replace(old, "", 1), encoding="utf-8")
    else:
        raise ValueError(f"unsupported action {item.action}")
    return target


def git_status(root: Path) -> tuple[bool, str]:
    try:
        inside = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if inside.returncode != 0:
            return True, "not a git repository"
        status = subprocess.run(
            ["git", "status", "--short", "--branch"],
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        lines = status.stdout.splitlines()
        dirty = any(line and not line.startswith("##") for line in lines)
        return not dirty, status.stdout.strip()
    except OSError as exc:
        return True, f"git unavailable: {exc}"


def git_add(root: Path, paths: list[Path]) -> None:
    if not paths:
        return
    inside = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if inside.returncode != 0:
        return
    rels = [str(path.relative_to(root)) for path in paths]
    subprocess.run(["git", "add", "--", *rels], cwd=root, check=False)


def selected_items(payload: dict[str, Any], args: argparse.Namespace) -> list[LearningItem]:
    items = [LearningItem.from_json(item) for item in payload.get("items", [])]
    if args.all_items:
        return items
    if args.classification:
        allowed = set(args.classification)
        items = [item for item in items if item.kind in allowed]
    if args.item:
        allowed_ids = set(args.item)
        items = [item for item in items if item.item_id in allowed_ids]
    if args.classification or args.item:
        return items
    if not sys.stdin.isatty():
        raise SystemExit("Non-interactive apply requires --all, --classification, or --item.")
    chosen: list[LearningItem] = []
    for item in items:
        answer = input(f"Apply {item.item_id} ({item.kind}) to {item.target_path}? [y/N] ").strip().lower()
        if answer in {"y", "yes"}:
            chosen.append(item)
    return chosen


def cmd_apply(args: argparse.Namespace) -> int:
    root = Path(args.root).expanduser().resolve()
    payload = parse_proposal(Path(args.proposal).expanduser())
    items = selected_items(payload, args)
    if not items:
        print("No proposal items selected.")
        return 0
    clean, status = git_status(root)
    print(status)
    if not clean and not args.allow_dirty:
        if args.yes or not sys.stdin.isatty():
            raise SystemExit("Worktree has uncommitted changes. Re-run with --allow-dirty to apply anyway.")
        answer = input("Worktree is dirty. Continue after creating backups? [y/N] ").strip().lower()
        if answer not in {"y", "yes"}:
            return 1
    backup_root = root / ".codex" / "learn" / "backups" / dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    changed: list[Path] = []
    for item in items:
        changed.append(apply_item(root, item, backup_root))
    git_add(root, sorted(set(changed)))

    state_path = state_path_for(root, args.state)
    state = load_state(state_path)
    now = utc_now()
    for item in items:
        state.setdefault("applied_items", {})[item.item_id] = {
            "applied_at": now,
            "target_path": item.target_path,
            "hash": item.item_hash,
        }
    save_state(state_path, state)
    print(f"Applied {len(items)} item(s). Backups: {backup_root}")
    return 0


def extract_guidance_lines(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path, content in load_guidance(root):
        in_fence = False
        for number, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            match = re.match(r"^[-*]\s+(.+)$", stripped) or re.match(r"^\d+[.)]\s+(.+)$", stripped)
            if match:
                text = match.group(1).strip()
                if len(text) >= 8:
                    records.append({"path": path, "line": number, "text": text})
    return records


def proposal_from_items(items: list[LearningItem], ignored: list[LearningItem], title: str) -> str:
    result = AnalysisResult(source_digest=sha256_text(title + json.dumps([item.to_json() for item in items], sort_keys=True))[:16])
    result.proposed = [item.finalize() for item in items]
    result.ignored = [item.finalize() for item in ignored]
    result.summary = f"{len(items)} proposed, {len(ignored)} ignored."
    return render_proposal(result, title=title)


def cmd_forget(args: argparse.Namespace) -> int:
    root = Path(args.root).expanduser().resolve()
    items: list[LearningItem] = []
    ignored: list[LearningItem] = []
    for record in extract_guidance_lines(root):
        text = record["text"]
        if TRANSIENT_RE.search(text) or "obsolete" in text.lower() or "deprecated" in text.lower():
            target = str(record["path"].relative_to(root))
            items.append(
                LearningItem(
                    kind="Repository Note",
                    text=text,
                    evidence=f"{target}:{record['line']}",
                    confidence=78,
                    rationale="Guidance appears stale, deprecated, or session-specific.",
                    target_path=target,
                    action="delete",
                    old_text=text,
                ).finalize()
            )
        else:
            ignored.append(
                LearningItem(
                    kind="Ignore",
                    text=text,
                    evidence=str(record["path"].relative_to(root)),
                    confidence=0,
                    rationale="No decay signal detected.",
                    target_path="",
                    reason="active",
                ).finalize()
            )
    write_proposal(Path(args.output).expanduser(), proposal_from_items(items, ignored, "Learning Forget Proposal"))
    print(f"Wrote {args.output}: {len(items)} deletion candidate(s).")
    return 0


def cmd_consolidate(args: argparse.Namespace) -> int:
    root = Path(args.root).expanduser().resolve()
    records = extract_guidance_lines(root)
    used: set[int] = set()
    items: list[LearningItem] = []
    ignored: list[LearningItem] = []
    for index, record in enumerate(records):
        if index in used:
            continue
        group = [record]
        for other_index, other in enumerate(records[index + 1 :], start=index + 1):
            if other_index in used:
                continue
            if jaccard(record["text"], other["text"]) >= 0.66:
                group.append(other)
                used.add(other_index)
        if len(group) < 2:
            ignored.append(
                LearningItem(
                    kind="Ignore",
                    text=record["text"],
                    evidence=str(record["path"].relative_to(root)),
                    confidence=0,
                    rationale="No overlapping rule found.",
                    target_path="",
                    reason="unique",
                ).finalize()
            )
            continue
        canonical = shortest_clear_text([entry["text"] for entry in group])
        first = group[0]
        target = str(first["path"].relative_to(root))
        items.append(
            LearningItem(
                kind="Rule",
                text=canonical,
                evidence=", ".join(f"{entry['path'].relative_to(root)}:{entry['line']}" for entry in group),
                confidence=82,
                rationale=f"Consolidates {len(group)} overlapping guidance lines.",
                target_path=target,
                action="replace",
                old_text=first["text"],
                replacement=canonical,
            ).finalize()
        )
    write_proposal(Path(args.output).expanduser(), proposal_from_items(items, ignored, "Learning Consolidation Proposal"))
    print(f"Wrote {args.output}: {len(items)} consolidation candidate(s).")
    return 0


def shortest_clear_text(values: list[str]) -> str:
    values = sorted((value.strip().rstrip(".") for value in values), key=lambda value: (len(value), value))
    chosen = values[0]
    return chosen + "." if chosen and chosen[-1] not in ".!?" else chosen


def conflict_pairs(records: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for left_index, left in enumerate(records):
        left_norm = normalize_text(left["text"])
        for right in records[left_index + 1 :]:
            right_norm = normalize_text(right["text"])
            if jaccard(left_norm, right_norm) < 0.45:
                continue
            left_negative = bool(re.search(r"\b(never|do not|avoid|must not)\b", left_norm))
            right_positive = bool(re.search(r"\b(always|must|prefer|use)\b", right_norm))
            right_negative = bool(re.search(r"\b(never|do not|avoid|must not)\b", right_norm))
            left_positive = bool(re.search(r"\b(always|must|prefer|use)\b", left_norm))
            if (left_negative and right_positive) or (right_negative and left_positive):
                pairs.append((left, right))
    return pairs


def cmd_lint(args: argparse.Namespace) -> int:
    root = Path(args.root).expanduser().resolve()
    records = extract_guidance_lines(root)
    duplicates: list[tuple[dict[str, Any], dict[str, Any], float]] = []
    for index, left in enumerate(records):
        for right in records[index + 1 :]:
            score = jaccard(left["text"], right["text"])
            if score >= 0.78:
                duplicates.append((left, right, score))
    conflicts = conflict_pairs(records)
    vague = [record for record in records if VAGUE_RE.search(record["text"])]
    skill_missing_examples = []
    for path in (root / "skills").glob("*/SKILL.md") if (root / "skills").is_dir() else []:
        content = read_text(path, limit=200_000)
        if "```" not in content and "example" not in content.lower():
            skill_missing_examples.append(path)

    lines = [
        "# Learning Lint Report",
        "",
        "## Health Metrics",
        "",
        f"- Guidance lines scanned: {len(records)}",
        f"- Duplicate candidates: {len(duplicates)}",
        f"- Conflict candidates: {len(conflicts)}",
        f"- Vague lines: {len(vague)}",
        f"- Skills missing examples: {len(skill_missing_examples)}",
        "",
        "## Duplicate Rules",
        "",
    ]
    if duplicates:
        for left, right, score in duplicates:
            lines.append(f"- {left['path'].relative_to(root)}:{left['line']} overlaps {right['path'].relative_to(root)}:{right['line']} ({score:.2f})")
    else:
        lines.append("- None detected.")
    lines.extend(["", "## Conflicting Rules", ""])
    if conflicts:
        for left, right in conflicts:
            lines.append(f"- {left['path'].relative_to(root)}:{left['line']} conflicts with {right['path'].relative_to(root)}:{right['line']}")
    else:
        lines.append("- None detected.")
    lines.extend(["", "## Vague/Ambiguous Guidance", ""])
    if vague:
        for record in vague:
            lines.append(f"- {record['path'].relative_to(root)}:{record['line']} {record['text']}")
    else:
        lines.append("- None detected.")
    lines.extend(["", "## Missing Examples", ""])
    if skill_missing_examples:
        for path in skill_missing_examples:
            lines.append(f"- {path.relative_to(root)}")
    else:
        lines.append("- None detected.")
    Path(args.output).expanduser().write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="learn.py", description="Codex learn plugin engine")
    sub = parser.add_subparsers(dest="command", required=True)

    learn = sub.add_parser("learn", help="analyze session history and write learning_proposal.md")
    learn.add_argument("--file", action="append", help="Session history file. Can be passed multiple times.")
    learn.add_argument("--root", default=".", help="Repository root to inspect and target.")
    learn.add_argument("--state", help="State file path. Defaults to <root>/.codex/learn/state.json.")
    learn.add_argument("--output", default="learning_proposal.md")
    learn.add_argument("--force", action="store_true", help="Bypass state and confidence suppression.")
    learn.add_argument("--no-state-write", action="store_true", help="Do not update .codex/learn/state.json.")
    learn.set_defaults(func=cmd_learn)

    apply = sub.add_parser("apply-learning", help="apply selected proposal items")
    apply.add_argument("--proposal", default="learning_proposal.md")
    apply.add_argument("--root", default=".")
    apply.add_argument("--state", help="State file path. Defaults to <root>/.codex/learn/state.json.")
    apply.add_argument("--all", dest="all_items", action="store_true", help="Apply every proposed item.")
    apply.add_argument("--classification", action="append", choices=["Rule", "Skill", "Repository Note"])
    apply.add_argument("--item", action="append", help="Apply a specific item ID. Can be repeated.")
    apply.add_argument("--yes", action="store_true", help="Non-interactive confirmation for selected items.")
    apply.add_argument("--allow-dirty", action="store_true", help="Apply despite uncommitted changes.")
    apply.set_defaults(func=cmd_apply)

    forget = sub.add_parser("forget", help="propose stale guidance deletion")
    forget.add_argument("--root", default=".")
    forget.add_argument("--output", default="learning_forget_proposal.md")
    forget.set_defaults(func=cmd_forget)

    consolidate = sub.add_parser("consolidate", help="propose semantic consolidation")
    consolidate.add_argument("--root", default=".")
    consolidate.add_argument("--output", default="learning_consolidation_proposal.md")
    consolidate.set_defaults(func=cmd_consolidate)

    lint = sub.add_parser("lint-learning", help="audit active guidance")
    lint.add_argument("--root", default=".")
    lint.add_argument("--output", default="learning_lint_report.md")
    lint.set_defaults(func=cmd_lint)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
