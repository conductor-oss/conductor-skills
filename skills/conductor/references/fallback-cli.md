# Fallback CLI Mapping

When the `conductor` CLI cannot be installed, use the bundled `scripts/conductor_api.py` (stdlib-only Python). Set `CONDUCTOR_API` to its path, e.g. `export CONDUCTOR_API="<skill-path>/scripts/conductor_api.py"`.

The fallback covers core CRUD and execution — not all CLI features. Limitations:

- **Auth:** `CONDUCTOR_AUTH_TOKEN` only. Key/secret exchange is **not** supported. Users on Orkes who need key/secret auth must obtain a token externally.
- **No profile support** — set `CONDUCTOR_SERVER_URL` directly.
- **No server auto-detection** — `CONDUCTOR_SERVER_URL` is required.
- **No `taskDef` CRUD** — cannot list/create/update/delete task definitions.
- **No time-range search** — `search-workflows` accepts `--query` and `--status` only.
- **No** `update-execution`, `restart --use-latest`, `rerun`, `skip-task`, `jump`, schedules, secrets, webhooks, server lifecycle.

## Verb → command mapping

| Verb | CLI | Fallback |
|------|-----|----------|
| List workflow definitions | `conductor workflow list` | `python3 "$CONDUCTOR_API" list-workflows` |
| Get workflow definition | `conductor workflow get {name}` | `python3 "$CONDUCTOR_API" get-workflow --name {name} --version {v}` |
| Create workflow | `conductor workflow create file.json` | `python3 "$CONDUCTOR_API" create-workflow --file file.json` |
| Update workflow | `conductor workflow update file.json` | `python3 "$CONDUCTOR_API" update-workflow --file file.json` |
| Delete workflow | `conductor workflow delete {name} {v}` | `python3 "$CONDUCTOR_API" delete-workflow --name {name} --version {v}` |
| Start workflow | `conductor workflow start -w {name} -i '{...}'` | `python3 "$CONDUCTOR_API" start-workflow --name {name} --input '{...}'` |
| Get execution | `conductor workflow get-execution {id} -c` | `python3 "$CONDUCTOR_API" get-execution --id {id} --include-tasks` |
| Search executions | `conductor workflow search -s RUNNING` | `python3 "$CONDUCTOR_API" search-workflows --status RUNNING --size 20` |
| Pause | `conductor workflow pause {id}` | `python3 "$CONDUCTOR_API" pause-workflow --id {id}` |
| Resume | `conductor workflow resume {id}` | `python3 "$CONDUCTOR_API" resume-workflow --id {id}` |
| Terminate | `conductor workflow terminate {id}` | `python3 "$CONDUCTOR_API" terminate-workflow --id {id} --reason "..."` |
| Restart | `conductor workflow restart {id}` | `python3 "$CONDUCTOR_API" restart-workflow --id {id}` |
| Retry | `conductor workflow retry {id}` | `python3 "$CONDUCTOR_API" retry-workflow --id {id}` |
| Signal task (async) | `conductor task signal --workflow-id {id} --task-ref {ref} --status COMPLETED --output '{...}'` | `python3 "$CONDUCTOR_API" signal-task --workflow-id {id} --task-ref {ref} --status COMPLETED --output '{...}'` |
| Signal task (sync) | `conductor task signal-sync ...` | `python3 "$CONDUCTOR_API" signal-task-sync --workflow-id {id} --task-ref {ref} --status COMPLETED --output '{...}'` |
| Poll task | `conductor task poll {type} --count 5` | `python3 "$CONDUCTOR_API" poll-task --task-type {type} --count 5` |
| Queue size | `conductor task queue-size --task-type {type}` | `python3 "$CONDUCTOR_API" queue-size --task-type {type}` |

For anything not in the table (taskDef CRUD, schedules, secrets, etc.), the user must install the CLI.
