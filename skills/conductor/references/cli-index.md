# CLI Command Index

Flat verb-to-CLI lookup. For fallback equivalents see [fallback-cli.md](fallback-cli.md).

## Definitions

| Verb | CLI |
|------|-----|
| List | `conductor workflow list` |
| Get | `conductor workflow get {name}` |
| Create | `conductor workflow create file.json` |
| Update | `conductor workflow update file.json` |
| Delete | `conductor workflow delete {name} {version}` |
| List task defs | `conductor task list --json` |
| Get task def | `conductor task get {name}` |
| Create task def | `conductor task create file.json` |
| Update task def | `conductor task update file.json` |
| Delete task def | `conductor task delete {name}` |

## Execution

| Verb | CLI |
|------|-----|
| Start (async) | `conductor workflow start -w {name} -i '{...}'` |
| Start (sync, wait for completion) | `conductor workflow start -w {name} -i '{...}' --sync` |
| Start (sync, wait until task) | `conductor workflow start -w {name} -i '{...}' --sync -u {taskRef}` |
| Start with file input | `conductor workflow start -w {name} -f input.json` |
| Start with version + correlation | `conductor workflow start -w {name} --version {v} --correlation {id} -i '{...}'` |
| Get execution | `conductor workflow get-execution {id} -c` |
| Quick status | `conductor workflow status {id}` |
| Search by status | `conductor workflow search -s RUNNING -c 20` |
| Search by name + status | `conductor workflow search -w {name} -s FAILED -c 10` |
| Search by time | `conductor workflow search -s COMPLETED --start-time-after "2024-01-01" --start-time-before "2024-01-31"` |

Statuses: `RUNNING`, `COMPLETED`, `FAILED`, `TIMED_OUT`, `TERMINATED`, `PAUSED`.

## Lifecycle

| Verb | CLI |
|------|-----|
| Pause | `conductor workflow pause {id}` |
| Resume | `conductor workflow resume {id}` |
| Terminate | `conductor workflow terminate {id}` |
| Restart | `conductor workflow restart {id}` |
| Restart on latest | `conductor workflow restart {id} --use-latest` |

## Intervention

| Verb | CLI |
|------|-----|
| Retry last failed task | `conductor workflow retry {id}` |
| Rerun from task | `conductor workflow rerun {id} --task-id {taskId}` |
| Skip a task | `conductor workflow skip-task {id} {taskRef}` |
| Jump to task | `conductor workflow jump {id} {taskRef}` |
| Signal task (async) | `conductor task signal --workflow-id {id} --task-ref {ref} --status COMPLETED --output '{...}'` |
| Signal task (sync, returns workflow) | `conductor task signal-sync --workflow-id {id} --task-ref {ref} --status COMPLETED --output '{...}'` |

Use **signal-sync** when you need the updated workflow back in one round-trip; **signal** is fire-and-forget.

Task statuses for signaling: `COMPLETED`, `FAILED`, `FAILED_WITH_TERMINAL_ERROR`.

## Tasks & queues

| Verb | CLI |
|------|-----|
| Poll | `conductor task poll {taskType} --count 5` |
| Update execution | `conductor task update-execution --workflow-id {id} --task-ref-name {ref} --status COMPLETED --output '{...}'` |
| Queue size | `conductor task queue-size --task-type {type}` |

## Schedules

| Verb | CLI |
|------|-----|
| List | `conductor schedule list` |
| Get | `conductor schedule get {name}` |
| Create | `conductor schedule create file.json` |
| Update | `conductor schedule update file.json` |
| Delete | `conductor schedule delete {name}` |
| Pause | `conductor schedule pause {name}` |
| Resume | `conductor schedule resume {name}` |

Schedules are part of OSS. See [schedules.md](schedules.md) for the JSON schema, cron format, and patterns.

## Agents (deployed Conductor Agents and their executions)

Contract and lifecycle in [agents.md](agents.md); per-language SDK verbs (`plan / run / deploy / serve`) in [agent-sdks.md](agent-sdks.md).

| Verb | CLI |
|------|-----|
| List deployed agents | `conductor agent list` |
| Get / delete a definition | `conductor agent get {name} [--version N]` · `conductor agent delete {name} [--version N]` |
| Compile a config file (dry run) | `conductor agent compile {config.yaml\|json}` |
| Scaffold a config file (no server) | `conductor agent init {name} --model provider/model [-s strategy] [-f yaml\|json]` |
| Run a deployed agent (streams) | `conductor agent run --name {name} "prompt" [--session {id}] [--no-stream]` |
| Run a config file | `conductor agent run --config {file} "prompt"` |
| Search executions | `conductor agent execution [--name {agent}] [--status RUNNING\|COMPLETED\|FAILED] [--since 1h] [--window now-7d] [--json]` |
| Status of one execution | `conductor agent status {executionId}` |
| Live events (SSE) | `conductor agent stream {executionId} [--last-event-id N]` |
| Answer a human gate | `conductor agent respond {executionId} --approve\|--deny [--reason "..."]` · `conductor agent respond {executionId} -m "answer text"` |
| Prune old executions | `conductor agent prune --older-than 30 [--archive] [--dry-run]` |
| Cancel / pause / inspect the compiled run | `conductor workflow terminate\|pause\|resume\|get-execution {executionId}` — an agent execution id **is** a workflow id |

Not available as CLI verbs (use REST or the fallback script): deploy (`runtime.deploy()` in the SDK, or `python3 "$CONDUCTOR_API" agent-deploy-config --file {file}`), cancel (`python3 "$CONDUCTOR_API" agent-cancel --id {id}` / `DELETE /api/agent/{id}/cancel`), stop, signal, provider status (`python3 "$CONDUCTOR_API" providers-status`). **Do not use `conductor deploy`** — it shells to a module that does not ship with the SDKs (SKILL.md Rule 13).

## Skills (agentskills.io `SKILL.md` packages run as agents)

Requires `agentspan.skills.enabled=true` on the server (off by default). A skill *is* an agent (`framework: "skill"`); `skill load` deploys it, after which `conductor agent run --name {skill}` works.

| Verb | CLI |
|------|-----|
| List / get / pull / delete | `conductor skill list [--all-versions]` · `skill get {name} [version]` · `skill pull {name} [dest]` · `skill delete {name} [version]` |
| Register a package | `conductor skill register {path} [--version v] [--model provider/model] [--agent-model name=model]` |
| Deploy as an agent (no run) | `conductor skill load {path} --model provider/model [--agent-model ...] [--search-path ...]` |
| Run once with local tool workers | `conductor skill run {path-or-name} "prompt" --model provider/model [--param k=v] [--workspace dir]` |
| Serve a skill's tools (run from UI/elsewhere) | `conductor skill serve {path-or-name}` |

## Server (local)

| Verb | CLI |
|------|-----|
| Start | `conductor server start` (or `--port 3000`) |
| Status | `conductor server status` |
| Logs | `conductor server logs -f` |
| Stop | `conductor server stop` |

## Enterprise (Orkes only)

See [orkes.md](orkes.md) for `secret` and `webhook` commands.
