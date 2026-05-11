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
| List task defs | `conductor taskDef list` |
| Create task def | `conductor taskDef create file.json` |

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

## Server (local)

| Verb | CLI |
|------|-----|
| Start | `conductor server start` (or `--port 3000`) |
| Status | `conductor server status` |
| Logs | `conductor server logs -f` |
| Stop | `conductor server stop` |

## Enterprise (Orkes only)

See [orkes.md](orkes.md) for `secret` and `webhook` commands.
