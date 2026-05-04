# Hermes Local Agent Gateway Operations

This plugin is the governed Feishu -> Hermes -> Codex execution lane.

Use this source checkout as the maintenance source of truth:

```text
<hermes-agent-source>/plugins/hermes-local-agent-gateway
```

Deploy it into the active Hermes user plugin directory:

```text
~/.hermes/plugins/hermes-local-agent-gateway
```

Do not deploy this custom plugin into the Hermes bundled plugin directory:

```text
~/.hermes/hermes-agent/plugins/hermes-local-agent-gateway
```

That directory is for plugins shipped with the Hermes source tree. This gateway
is a user plugin at runtime, even if its source is maintained in a local Hermes
checkout.

The plugin owns Codex task policy, queueing, approval, worktree isolation,
verification, and result delivery. The Hermes core patch surface is deliberately
small and generic: Feishu card action callbacks and interactive-card updates.

## One-Time Install Or Update

From the Hermes source checkout:

```bash
scripts/hermes-local-agent-gateway install --enable --restart
```

If you run the installed copy of this script from `~/.hermes/hermes-agent`,
pass the maintenance checkout explicitly:

```bash
~/.hermes/hermes-agent/scripts/hermes-local-agent-gateway \
  --source-root /mnt/e/module/py/hermes-agent \
  install --enable --restart
```

What it does:

1. Copies `plugins/hermes-local-agent-gateway/` into `~/.hermes/plugins/`.
2. Creates `~/.hermes/plugins/hermes-local-agent-gateway/config.json` if missing.
3. Syncs the generic Feishu hook files into `~/.hermes/hermes-agent`.
4. Backs up overwritten core files under `~/.hermes/backups/hermes-local-agent-gateway/<timestamp>/`.
5. Optionally enables the plugin and restarts `hermes-gateway.service`.

It does not create or require
`~/.hermes/hermes-agent/plugins/hermes-local-agent-gateway`.

Use `--no-core` if the installed Hermes already contains the Feishu hook patch.

## Status And Doctor

```bash
scripts/hermes-local-agent-gateway status
scripts/hermes-local-agent-gateway doctor
```

`status` prints JSON with:

- source and runtime plugin paths
- the forbidden bundled-plugin path and whether it exists
- plugin config presence
- whether `~/.hermes/config.yaml` mentions the plugin
- required Feishu hook markers
- queue and worktree counts
- systemd gateway state

`doctor` returns non-zero when required runtime deployment pieces are missing.
It also fails if the custom plugin exists under the Hermes bundled plugin
directory, because that indicates the user-plugin boundary has been violated.
The source plugin path is reported for operator visibility, but it is only
required for `install`.

## Config

The runtime config lives at:

```text
~/.hermes/plugins/hermes-local-agent-gateway/config.json
```

Create it without reinstalling:

```bash
scripts/hermes-local-agent-gateway write-config
```

Important fields:

- `workspace_roots`: allowed project roots, normally `["/home/projects"]`
- `repo_aliases`: convenient aliases such as `data-agent`
- `artifact_root`: queued task artifacts
- `worktree_root`: isolated Codex worktrees
- `worktree_archive_root`: archived/removed worktrees
- `session_root`: saved Codex session ids
- `approval_allowed_user_ids`: optional Feishu open_id allowlist
- `approval_allowed_chat_ids`: optional Feishu chat allowlist

For a personal Feishu bot, leave the approval allowlists empty unless stricter
approval routing is needed later.

## Upgrade Recovery

After upgrading Hermes:

```bash
scripts/hermes-local-agent-gateway doctor
scripts/hermes-local-agent-gateway install --enable --restart
scripts/hermes-local-agent-gateway doctor
```

If an upstream Hermes release eventually includes the generic Feishu hooks, use:

```bash
scripts/hermes-local-agent-gateway install --no-core --enable --restart
```

## Worktree Hygiene

Preview old managed worktrees that would be removed while keeping the newest
five per repository:

```bash
scripts/hermes-local-agent-gateway cleanup-worktrees --keep 5
```

Apply the cleanup:

```bash
scripts/hermes-local-agent-gateway cleanup-worktrees --keep 5 --apply
```

The plugin tool `manage_codex_workspace` remains the preferred path when you
need archive/quota/conflict details. The script is for simple operational
hygiene.

## Feishu Commands

Read task:

```text
/codex repo=data-agent mode=read workspace=data-agent-read-001
只读分析项目结构，不修改任何文件。
```

Write task:

```text
/codex repo=data-agent mode=write workspace=docs-small-change verify=file:docs/example.md allow=docs/example.md
更新 docs/example.md，不修改其他文件。
```

Fallback text controls:

```text
/codex approve queued_...
/codex reject queued_...
/codex status queued_...
```

Normal write approval should use the Feishu card buttons.

## Ownership Rules

- Keep Codex queue, approval, runner, worktree, verification, and delivery logic
  in this plugin.
- Keep Hermes core changes generic and Feishu-adapter scoped.
- Keep the runtime plugin under `~/.hermes/plugins/`; never under
  `~/.hermes/hermes-agent/plugins/`.
- Do not put Feishu tokens or Codex credentials in this plugin config.
- Do not edit valuable project repositories without `mode=write`, approval,
  `allow=...`, and a verification template.
