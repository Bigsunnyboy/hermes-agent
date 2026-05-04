# Hermes Local Agent Gateway

External Hermes plugin for governed local Codex task execution.

## Current Phase

Current implemented slice:

1. Resolve task target by `repo` alias or absolute `path`.
2. Enforce workspace root boundaries.
3. Reject sensitive target paths such as `.env`, `*.key`, `*secret*`, `auth.json`, and `credentials*`.
4. Create or reuse an isolated worktree under `~/.hermes/worktrees/<repo>/<workspace_id>`.
5. Build `codex exec` commands with explicit sandbox mode.
6. Capture task artifacts under `~/.hermes/agent_tasks/<task_id>/`.
7. Detect read-mode workspace changes inside the execution directory with git status plus a non-sensitive workspace fingerprint.
8. Parse Feishu-style `/codex` commands into governed task payloads.
9. Persist queued tasks under `~/.hermes/agent_queue`.
10. Require approval before write-mode Codex execution.
11. Expand verification templates and run verification only for approved write tasks.
12. Register a `pre_gateway_dispatch` hook so Feishu `/codex` messages enqueue directly before normal agent dispatch.
13. Connect queue draining to Hermes' real cron scheduler through `ensure_codex_worker_cron`.
14. Classify write risk as low/medium/high/critical and block critical sensitive/destructive prompts.
15. Inspect, remove, archive, quota-check, and conflict-check managed worktree workspaces.
16. Deliver completed queued task results back to the original Feishu chat saved at enqueue time.
17. Register Hermes tools for task creation, command submission, queue worker/status/approval, result delivery, cron setup, and workspace management.
18. Validate queued write-mode smoke flow: approval gate, worker execution, isolated worktree diff, verification command, artifacts, and clean original repository.
19. Enforce optional write-mode changed-path allowlists with `allow=...`; changes outside the allowlist fail the task after Codex and verification run.
20. Run Codex with a managed `CODEX_HOME` under `~/.hermes/codex_home` so user-level Codex hooks do not mutate target worktrees.
21. Send Feishu interactive approval cards for write tasks when the live Feishu adapter exposes raw interactive-message sending; card button callbacks are routed back as `/card button ...` synthetic commands.
22. Return inline Feishu card callback responses for Codex approve/reject buttons through the adapter's `feishu_card_action_response` plugin hook, while keeping queue mutation in the existing `/card` synthetic-command path.
23. Persist the Feishu approval card `message_id` in the queue record, update that same card to RUNNING when the worker claims the task, and prefer updating it to DONE/FAILED for final delivery. Text delivery remains the fallback when card update is unavailable.
24. Replace raw Feishu `open_id` operator text with the resolved sender name when the synthetic `/card` command path has a sender profile; raw `ou_...` identifiers are omitted from the immediate callback card.
25. Block critical write tasks that target protected governance paths such as `.hermes`, `.codex`, `.omx`, `.git`, the Hermes official source tree, or this gateway plugin.
26. Enforce optional Feishu approval policy with `approval_allowed_user_ids` and `approval_allowed_chat_ids`; when either list is non-empty, approve/reject commands and card clicks must match the configured users/chats.

## Enable

```bash
hermes plugins enable hermes-local-agent-gateway
systemctl restart hermes-gateway.service
```

## Tool Arguments

## Routing Model

The plugin is a governed Codex execution lane, not a replacement for Hermes' general chat ability.

Use the plugin as the default path for Feishu project tasks:

```text
Feishu /codex command -> pre_gateway_dispatch hook -> queue -> cron worker -> isolated worktree -> Codex -> Feishu result delivery
```

Direct `terminal(codex exec ...)` remains useful for developer-local debugging, scratch experiments, and emergency diagnosis, but it bypasses the gateway's queueing, approval, worktree/session isolation, artifact capture, verification, and Feishu callback delivery. It should not be recommended as the normal path for governed Feishu project work.

The registered tools serve different operational roles:

- `create_codex_task`: low-level governed execution primitive used by the worker path.
- `submit_codex_command`: parse and enqueue `/codex ...` text.
- `run_next_codex_task`: worker entry point that consumes one queued task.
- `approve_codex_task`: approval gate for write tasks.
- `get_codex_task_status`: queue status inspection.
- `deliver_codex_task_result`: manual final-result delivery retry.
- `manage_codex_workspace`: inspect/archive/remove/quota/conflict operations for managed worktrees.

`create_codex_task` accepts:

```json
{
  "repo": "data-agent",
  "path": null,
  "mode": "read",
  "workspace_id": "data-agent-browser-fix",
  "codex_session_id": null,
  "prompt": "Read-only analyze the project. Do not modify files."
}
```

Use exactly one of `repo` or `path`.

Feishu-style queue submission accepts text like:

```text
/codex repo=data-agent mode=write workspace=data-agent-browser-fix verify=pytest,ruff allow=app/,tests/
修复浏览器 ask 成功路径。
```

Write tasks submitted through the queue enter `APPROVAL_REQUIRED` until `approve_codex_task` marks them approved.
Critical write tasks that mention sensitive credential targets or destructive operations enter `BLOCKED`.
When `allow=` is provided, the worker compares post-run `git status --short` paths against the comma-separated allowlist. Exact file paths and directory prefixes are supported; unexpected paths make the task `FAILED` even if Codex returns 0 and verification passes.

Feishu write approvals use an interactive card when the live adapter supports Feishu `interactive` messages. The card includes task id, target, workspace, risk, verification, allowlist, and approve/reject buttons. Button callbacks are handled as synthetic `/card button ...` commands by the existing Hermes Feishu adapter, then intercepted by this plugin before normal agent dispatch.

When the Hermes Feishu adapter exposes the `feishu_card_action_response` plugin hook, the same approve/reject click also receives an inline callback card that replaces the original approval card with an approved or rejected state. The inline response is visual only; the authoritative queue update still happens through the synthetic `/card` command so Codex task governance remains inside this plugin.

When the Feishu adapter also supports `edit_interactive_card`, the gateway stores the approval card's `message_id` under `payload.delivery.approval_card`. The queue worker updates that card to `Codex task running` after claiming the task, then `Codex task done` or `Codex task failed` after execution. If the card update fails or no approval card was saved, the existing final text-message delivery path is used.

For card clicks, the synchronous callback may only receive a Feishu `open_id`. The plugin avoids showing raw `ou_...` identifiers there, then the synthetic `/card` command path updates the saved approval card again with the resolved Feishu sender display name when Hermes has one.

Text commands remain deterministic fallbacks, so approval and status checks do not depend on the chat agent choosing the right tool:

```text
/codex approve queued_20260503T000000Z_deadbeef
/codex approve task=queued_20260503T000000Z_deadbeef
/codex reject queued_20260503T000000Z_deadbeef
/codex deny queued_20260503T000000Z_deadbeef
/codex status queued_20260503T000000Z_deadbeef
```

Run this once after enabling the plugin to install the real Hermes cron worker:

```text
ensure_codex_worker_cron
```

The created cron job uses `~/.hermes/scripts/codex_queue_worker_wake.py` as a wake gate. Empty queues return `{"wakeAgent": false}` so Hermes skips the agent run; non-empty queues wake the cron job and call `run_next_codex_task` once. When a task came from Feishu, the queue record contains the original chat target, and `run_next_codex_task` sends the final summary back to that chat after Codex finishes.

Codex subprocesses launched by this gateway use a managed `CODEX_HOME` at `~/.hermes/codex_home`. The gateway links the existing Codex authentication file and writes a sanitized config with only model-related settings. It intentionally does not load user-level `hooks.json`, `notify`, OMX MCP servers, or OMX developer instructions, because those hooks can create `.omx/` and `.gitignore` inside the target worktree before the task itself runs.

## Default Config

If `config.json` is absent, defaults are:

```json
{
  "workspace_roots": ["/home/projects"],
  "repo_aliases": {
    "data-agent": "/home/projects/data-agent"
  },
  "artifact_root": "~/.hermes/agent_tasks",
  "worktree_root": "~/.hermes/worktrees",
  "worktree_archive_root": "~/.hermes/worktree_archives",
  "session_root": "~/.hermes/agent_sessions",
  "codex_executable": "codex",
  "max_workspaces": 20,
  "max_worktree_bytes": 5368709120,
  "worker_cron_name": "codex-queue-worker",
  "worker_cron_schedule": "every 1m",
  "approval_allowed_user_ids": [],
  "approval_allowed_chat_ids": []
}
```

## Artifacts

Each task writes:

```text
task.json
codex_stdout.jsonl
codex_stderr.log
before_status.txt
before_diff_stat.txt
before_diff.txt
after_status.txt
after_diff_stat.txt
after_diff.txt
```

`task.json` includes the resolved project path, actual execution path, isolation mode, workspace id, Codex session id, command, return code, duration, `workspace_changed`, and any error. Runner failures still produce `task.json` and best-effort after-state artifacts.

For Git repositories with a valid `HEAD`, Codex runs in a persistent isolated worktree, so concurrent changes in the main workspace do not affect task success. The worktree is created from `HEAD`; uncommitted files in the main workspace are not included unless they were committed first.

If `workspace_id` is provided, later tasks with the same `workspace_id` reuse that worktree. If the first Codex run reports a thread id, Hermes stores it in `~/.hermes/agent_sessions/<workspace_id>.json`; later tasks resume it with `codex exec ... resume <codex_session_id> ...`. You may also pass `codex_session_id` explicitly to switch to a different saved Codex context.

`manage_codex_workspace` supports `inspect`, `remove`, `archive`, `quota`, and `conflicts`. Archives are written under `worktree_archive_root` and skip sensitive files such as `.env`, `*.key`, `*secret*`, `auth.json`, and `credentials*`.

For direct-mode tasks, `workspace_changed=true` means the execution directory changed during the task window. That can be caused by Codex, another concurrent Codex session, or any external process touching the same project. The fingerprint ignores common local tooling state directories such as `.git`, `.omx`, `.playwright-cli`, `.idea`, caches, virtualenvs, build outputs, and `node_modules`.

## Known Limitations

1. Cron execution drains one queued task per scheduler tick; it is intentionally serialized.
2. Worktree isolation currently uses the target repository `HEAD`; dirty/untracked main-workspace files are intentionally not copied.
3. Verification still runs an allowlisted subprocess after template expansion.
4. The plugin does not read or manage Feishu tokens; final result delivery uses Hermes' live gateway adapter first and falls back to Hermes' `send_message` tool.
5. Inline card update requires a Hermes Feishu adapter with the `feishu_card_action_response` hook; lifecycle card updates require `edit_interactive_card`. Without those adapter extensions, approve/reject and final delivery still work through text/card follow-up messages.
6. Write-mode E2E coverage includes automated temporary Git repository tests and a Feishu disposable-repo smoke. Valuable repositories should still use explicit `allow=` paths plus review before merging worktree changes.
7. Feishu approval identity policy is list-based. Display names are still best-effort; directory-backed role/group resolution should be added later if approvals need organization-level roles instead of explicit open_id/chat_id lists.
