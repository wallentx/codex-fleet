# Learning Proposal

<!-- codex-learn-data:v1
{
  "generated_at": "2026-07-04T18:06:20+00:00",
  "ignored": [
    {
      "action": "append",
      "confidence": 45,
      "evidence": "",
      "hash": "fa961ddc1913ab52a3c4a449dbe6adab04494ca1235405e63cf9a94096b8cbe9",
      "id": "L-fa961ddc1913",
      "kind": "Ignore",
      "old_text": "",
      "rationale": "No durable learning signal was strong enough.",
      "reason": "low confidence",
      "replacement": "",
      "target_path": "",
      "text": "That worked."
    },
    {
      "action": "append",
      "confidence": 25,
      "evidence": "",
      "hash": "9890a662128bc13b74a33c27bc127cb3f771af94063848af0bcc91b1f727df03",
      "id": "L-9890a662128b",
      "kind": "Ignore",
      "old_text": "",
      "rationale": "Observation looks session-specific or temporary.",
      "reason": "transient",
      "replacement": "",
      "target_path": "",
      "text": "Temporary debug print(\"here\") fixed line 42 for now."
    }
  ],
  "items": [
    {
      "action": "append",
      "confidence": 96,
      "evidence": "Never use grep in this repository; always use rg because it is faster and matches our workflow.",
      "hash": "eb05a3feb4f9fe73e7c95c9b8deeff7af0974629d723e83a3e67b7972b1f99c8",
      "id": "L-eb05a3feb4f9",
      "kind": "Rule",
      "old_text": "",
      "rationale": "Direct user correction or explicit preference detected.",
      "reason": "",
      "replacement": "",
      "target_path": "AGENTS.md",
      "text": "Never use grep in this repository; always use rg because it is faster and matches our workflow."
    },
    {
      "action": "append",
      "confidence": 84,
      "evidence": "That worked. For future staging deploys, run build-docker, then terraform plan, then terraform apply.",
      "hash": "a084dc55ddd7c8cc44e519cb9caeef994123af9ba536221bccb0ec11a02438e2",
      "id": "L-a084dc55ddd7",
      "kind": "Skill",
      "old_text": "",
      "rationale": "User confirmed a multi-command sequence succeeded.",
      "reason": "",
      "replacement": "",
      "target_path": ".codex/skills/successful-workflow-build-docker-staging-terraform/SKILL.md",
      "text": "Successful workflow: build-docker staging ; terraform plan -out staging.plan ; terraform apply staging.plan."
    },
    {
      "action": "append",
      "confidence": 82,
      "evidence": "For future staging deploys, run build-docker, then terraform plan, then terraform apply.",
      "hash": "23ab34ddb73b036de78f4fc67e94bc8428f47c2954aceb1700e29f08efd27ee9",
      "id": "L-23ab34ddb73b",
      "kind": "Skill",
      "old_text": "",
      "rationale": "Multi-step workflow or repeatable procedure detected.",
      "reason": "",
      "replacement": "",
      "target_path": ".codex/skills/for-future-staging-deploys-run-build/SKILL.md",
      "text": "For future staging deploys, run build-docker, then terraform plan, then terraform apply."
    },
    {
      "action": "append",
      "confidence": 72,
      "evidence": "This dev container does not support sudo commands.",
      "hash": "715fbfa500fb911bfb32d87ceae2fd138695163665cea6469383b14105fbdec3",
      "id": "L-715fbfa500fb",
      "kind": "Repository Note",
      "old_text": "",
      "rationale": "Repository or environment-specific fact detected.",
      "reason": "",
      "replacement": "",
      "target_path": ".codex/learn/repository-notes.md",
      "text": "This dev container does not support sudo commands."
    }
  ],
  "source_digest": "50eabbbe2928d04d",
  "summary": "4 proposed, 2 ignored from 5 messages.",
  "title": "Learning Proposal",
  "version": 1
}
codex-learn-data:end -->

## Executive Summary

4 proposed, 2 ignored from 5 messages.

## Proposed Additions

### Rule

- ID: `L-eb05a3feb4f9`
  Type: `Rule`
  Target: `AGENTS.md`
  Confidence: `96`
  Rationale: Direct user correction or explicit preference detected.

```diff
+ Never use grep in this repository; always use rg because it is faster and matches our workflow.
```

### Skill

- ID: `L-a084dc55ddd7`
  Type: `Skill`
  Target: `.codex/skills/successful-workflow-build-docker-staging-terraform/SKILL.md`
  Confidence: `84`
  Rationale: User confirmed a multi-command sequence succeeded.

```diff
+ create .codex/skills/successful-workflow-build-docker-staging-terraform/SKILL.md
+ Successful workflow: build-docker staging ; terraform plan -out staging.plan ; terraform apply staging.plan.
```

- ID: `L-23ab34ddb73b`
  Type: `Skill`
  Target: `.codex/skills/for-future-staging-deploys-run-build/SKILL.md`
  Confidence: `82`
  Rationale: Multi-step workflow or repeatable procedure detected.

```diff
+ create .codex/skills/for-future-staging-deploys-run-build/SKILL.md
+ For future staging deploys, run build-docker, then terraform plan, then terraform apply.
```

### Repository Note

- ID: `L-715fbfa500fb`
  Type: `Repository Note`
  Target: `.codex/learn/repository-notes.md`
  Confidence: `72`
  Rationale: Repository or environment-specific fact detected.

```diff
+ This dev container does not support sudo commands.
```

## Proposed Updates

No proposed updates.

## Proposed Deletions/Deprecations

No proposed deletions.

## Metadata

- `L-eb05a3feb4f9` `Rule` confidence `96` target `AGENTS.md`
  Rationale: Direct user correction or explicit preference detected.
- `L-a084dc55ddd7` `Skill` confidence `84` target `.codex/skills/successful-workflow-build-docker-staging-terraform/SKILL.md`
  Rationale: User confirmed a multi-command sequence succeeded.
- `L-23ab34ddb73b` `Skill` confidence `82` target `.codex/skills/for-future-staging-deploys-run-build/SKILL.md`
  Rationale: Multi-step workflow or repeatable procedure detected.
- `L-715fbfa500fb` `Repository Note` confidence `72` target `.codex/learn/repository-notes.md`
  Rationale: Repository or environment-specific fact detected.

### Ignored Observations

- `L-fa961ddc1913` low confidence: That worked.
- `L-9890a662128b` transient: Temporary debug print("here") fixed line 42 for now.
