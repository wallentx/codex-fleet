# Configure this device as a history-derived Codex agent fleet

Configure this device's Codex CLI as an optimized, history-derived multi-agent system. Complete the work end-to-end; do not stop after analysis or merely show example configuration.

## Authorization and safety

- You are authorized to inspect local Codex configuration and session history, enable supported Codex features, and create or update files beneath the active `CODEX_HOME`.
- Preserve existing configuration, roles, instructions, providers, plugins, and unrelated settings.
- Before editing, create a timestamped backup of every file or directory you will modify.
- Never modify, delete, compact, or relocate session-history files.
- Never expose session contents, secrets, tokens, credentials, or private source text in your final response or generated reports.
- Redact secret-like values encountered during analysis.
- Do not install plugins, change repositories, create commits, or modify project code.
- Follow existing `AGENTS.md` and local shell-command requirements.
- Request narrowly scoped filesystem permission if `CODEX_HOME` is outside the current writable area.
- Make reasonable decisions autonomously. Ask only when a genuinely consequential choice cannot be inferred locally.

## Goal

Discover what this device is regularly used for by analyzing its local Codex session history. Build a compact fleet of clearly differentiated specialist agents optimized for those workloads. Enable supported features needed for effective delegation, concurrency, permissions, long-running work, history-based improvement, and specialist tooling.

## Phase 1: Inspect current Codex environment

Run and inspect:

- `codex --version`
- `codex features list`
- `codex debug models`
- `codex doctor --json`
- Active `config.toml`
- Existing global `AGENTS.md`
- Existing `$CODEX_HOME/agents/`
- Existing profiles, model providers, skills, plugins, hooks, and MCP configuration relevant to agent work

Determine `CODEX_HOME` from environment or Codex diagnostics; default to `~/.codex` only when no explicit location exists.

Determine:

- Active model and provider
- Available model IDs
- Supported reasoning levels for each model
- Multi-agent protocol/version compatibility
- Available sandbox modes
- Config schema supported by this installed Codex version
- Existing agent declarations and role files

Never invent model IDs, provider IDs, reasoning levels, feature names, or config keys.

## Phase 2: Analyze local session history

Locate local rollout/session history using Codex diagnostics, state metadata, and `CODEX_HOME`.

Analyze a representative sample:

- Prefer up to 120 recent root sessions or roughly 90 days of history.
- Include older sessions only when needed to establish recurrence.
- Weight root user sessions more heavily than spawned sub-agent sessions.
- Treat sub-agent sessions as supporting evidence about delegated workload.
- Ignore system prompts, duplicated context, social filler, generated boilerplate, and one-off transient state.

Extract and aggregate:

- Recurring user-request categories
- Repositories and environments commonly used
- Languages, frameworks, platforms, and tools
- Read-only investigation versus implementation work
- Debugging, review, testing, documentation, release, research, security, performance, UI, data, infrastructure, and platform-specific work
- Frequently repeated command sequences
- Common failure and recovery workflows
- User corrections and stable preferences
- Typical task complexity, risk, duration, and tool requirements
- Tasks benefiting from parallel investigation
- Tasks needing specialized judgment
- Repetitive work that could become a skill, script, plugin, hook, MCP tool, or local command

Build an evidence table internally containing:

- Work category
- Approximate recurrence
- Complexity
- Risk
- Common tools
- Required permissions
- Candidate specialist role
- Evidence confidence

Do not quote private session content. Store only sanitized aggregate findings.

If an installed learning/proposal skill exists, use it to help classify durable patterns. Do not require it and do not install one when absent.

## Phase 3: Select base model and provider

Use the strongest locally available model that supports the best available multi-agent protocol and automatic delegation.

Selection order:

1. A model supporting multi-agent v2 and an `ultra` effort explicitly described as automatic delegation.
2. Strongest multi-agent-v2 model at `max`.
3. Strongest multi-agent-v2 model at `high`.
4. Current strongest compatible model if catalog metadata is incomplete.

If `gpt-5.6-sol` with `ultra` is available, prefer:

- `model = "gpt-5.6-sol"`
- `model_reasoning_effort = "ultra"`

Otherwise choose from actual catalog evidence.

Set `model_provider` explicitly. Never rely on implicit inheritance in generated role files.

Preserve the active provider unless another configured provider is demonstrably required. A custom provider key is valid only when present under `[model_providers.<key>]`.

## Phase 4: Enable relevant features

Parse `codex features list` into feature name, stage, and effective state.

Rules:

- Enable a feature only when this installed version lists it.
- Never enable features marked removed or deprecated.
- Do not copy obsolete feature keys from another device.
- Use `codex features enable <name>` where supported.
- Preserve unrelated enabled features.
- Do not disable anything unless it directly conflicts with multi-agent operation and the conflict is verified.
- If `multi_agent_v2` is unavailable, configure the strongest supported `multi_agent` fallback and clearly report the limitation.

Core multi-agent candidates:

- `multi_agent`
- `multi_agent_v2`
- `enable_fanout`
- `deferred_executor`
- `code_mode`

Supporting candidates to enable when listed and compatible:

- `concurrent_reasoning_summaries`
- `request_permissions_tool`
- `exec_permission_approvals`
- `runtime_metrics`
- `token_budget`
- `local_thread_store_compression`
- `standalone_web_search`
- `memories`
- `goals`
- `hooks`
- `current_time_reminder`
- `default_mode_request_user_input`
- `terminal_visualization_instructions`
- `artifact`
- `chronicle`
- `apply_patch_streaming_events`
- `mentions_v2`

Conditionally enable these only when session history supports their use:

- Browser-use features for recurring browser testing or research
- Image-generation features for recurring visual work
- Computer-use features for recurring GUI automation
- Apps or MCP-app features for recurring connected-service workflows
- Workspace-dependency features for recurring multi-repository work

Do not assume every experimental feature is beneficial. Enable only listed capabilities with a concrete role in this system.

## Phase 5: Design the fleet

Create a fleet based on evidence from this device, not a fixed copied fleet.

Target approximately 8-18 total roles. More roles are acceptable only when each has a distinct routing boundary. Merge overlapping specialties.

Every role must have:

- A unique snake_case role name
- A short router-facing description explaining when to use it
- A distinct responsibility
- An explicit config file
- Explicit `model`
- Explicit `model_provider`
- Explicit `model_reasoning_effort`
- Explicit `sandbox_mode`
- Focused `developer_instructions`
- Clear rules about whether it may edit files
- A model selected from the actual local catalog
- The cheapest capable model and effort for its task class

Use allocation principles:

- Fast/cheap model at low or medium effort for narrow search and simple fixes.
- Balanced model at medium or high for routine implementation, tests, docs, and CI.
- Strongest model at high or xhigh for architecture, hard debugging, security, deep review, and risky changes.
- Maximum effort only for genuinely difficult ambiguous reasoning.
- Ultra effort only for orchestration roles or models explicitly supporting automatic delegation.
- Leaf agents may use a non-v2 model only when they never need to delegate recursively.
- Orchestration agents must use a model compatible with the active multi-agent protocol.

Default sandbox principles:

- Research, architecture, review, security, performance analysis, and learning review: `read-only`.
- Implementation, testing, documentation, CI repair, tooling, and automation: `workspace-write`.
- Never use `danger-full-access` in generated roles.

Always include these cross-device support roles unless equivalent existing roles already cover them:

1. A fast read-only scout for narrow codebase questions.
2. A strong read-only correctness reviewer.
3. An orchestrator for large decomposable work.
4. A proposal-only `learning_auditor`.
5. An independent read-only `learning_reviewer`.
6. A writable `automation_engineer`.

Generate additional specialists from history, such as platform, language, release, security, UI, infrastructure, data, or repository-maintenance roles only when evidence supports them.

Place role files under:

- `$CODEX_HOME/agents/<role-name>.toml`

Role-file shape:

```toml
model = "<verified-model-id>"
model_provider = "<verified-provider-id>"
model_reasoning_effort = "<supported-effort>"
sandbox_mode = "<read-only-or-workspace-write>"
developer_instructions = """
Role-specific instructions grounded in discovered workload.
"""
```

Declare each role in the active config:

```toml
[agents.<role_name>]
description = "<clear routing description>"
config_file = "./agents/<role-name>.toml"
```

Merge these declarations safely. Do not create duplicate `[agents]` tables.

Configure general agent limits when supported by this version:

- Prefer `max_depth = 2`.
- Prefer `job_max_runtime_seconds = 1800`.
- Set `max_threads` only if the current schema accepts it with the selected multi-agent version.
- Choose a conservative concurrency limit based on device resources and workload; avoid unlimited fanout on constrained devices.

## Phase 6: Continuous-improvement pipeline

Configure these three roles as separate trust stages.

### `learning_auditor`

- Read-only.
- Reviews complex, high-value, corrected, or visibly repetitive work.
- Classifies candidates as memory, rule, repository note, skill, plugin/hook, or local tool.
- Checks existing artifacts before proposing anything.
- Reports evidence, recurrence, expected value, recommended scope, confidence, risks, and estimated executions saved.
- Rejects secrets, transient facts, one-off fixes, generic advice, and weak guesses.
- Never persists changes.

### `learning_reviewer`

- Read-only and stronger than or equal to auditor.
- Independently verifies evidence, durability, recurrence, novelty, scope, value, safety, and implementability.
- Assigns exactly one decision per candidate: `APPROVE`, `REVISE`, or `REJECT`.
- Records concise reasons and safeguards.
- Never persists changes.
- Agent approval alone is not authorization to modify memory or guidance.

### `automation_engineer`

- Workspace-write.
- Runs only after learning-reviewer approval and explicit user approval.
- Implements approved rules, notes, skills, scripts, plugins, hooks, MCP helpers, or local commands.
- Extends existing artifacts instead of duplicating them.
- Defines stable inputs, outputs, failures, safety boundaries, and documentation.
- Runs proportionate validation and a real smoke test for executable tooling.
- Never broadens approved scope.

Append or merge an idempotent global guidance section into `$CODEX_HOME/AGENTS.md`:

- Consider a learning retrospective only after high-value, complex, corrected, or repetitive work.
- Skip routine and one-off tasks.
- Route proposals through `learning_auditor`.
- Route every non-empty proposal through `learning_reviewer`.
- Surface approved items to the user.
- Preserve a brief audit trail for revised or rejected items.
- Require explicit user approval before persistent memory, guidance, skill, hook, plugin, or tool changes.
- Use `automation_engineer` only after both agent review and user approval.

## Phase 7: Produce a sanitized fleet manifest

Write `$CODEX_HOME/agents/FLEET.md` containing:

- Sanitized workload categories and recurrence levels
- Feature decisions
- Base model/provider decision
- Role table with model, provider, effort, sandbox, and purpose
- Routing examples
- Continuous-improvement pipeline
- Validation commands
- Date and Codex version

Do not include raw session text, secrets, private repository content, or credentials.

## Phase 8: Validate

Run:

- `codex features list`
- `codex --strict-config doctor --json` when supported
- Normal `codex doctor --json` otherwise
- TOML parsing or equivalent config validation
- Checks that every declared role file exists
- Checks that every role has explicit model/provider/effort/sandbox
- Checks that every selected model and effort appears in the local catalog
- Checks for malformed or ignored agent-role warnings
- Checks for duplicate role names and duplicate TOML tables
- Checks that removed/deprecated feature keys were not newly enabled

If collaboration tools are already active, ask an independent reviewer agent to inspect the proposed fleet for overlap, missing workload categories, excessive cost, unsafe permissions, unsupported models, and ambiguous descriptions. Apply only verified corrections.

If collaboration tools are unavailable until restart, do not fake agent review. Complete local validation and record that fleet review should occur in the first fresh session.

## Final response

Report only:

- Codex version and `CODEX_HOME`
- History sample size and sanitized workload categories
- Features enabled, already enabled, skipped, and unavailable
- Base model/provider/effort
- Created or updated roles
- Files changed and backup paths
- Validation results
- Any limitations
- Whether a new Codex session is required

Do not dump config files or session text unless specifically requested.

Finish the configuration now. A fresh Codex session will be used afterward to load the updated plugin and agent-role schema.
