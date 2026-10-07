# Fallback CLI Mapping

When the `conductor` CLI cannot be installed, use the bundled `scripts/conductor_api.py` (stdlib-only Python). Set `CONDUCTOR_API` to its path, e.g. `export CONDUCTOR_API="<skill-path>/scripts/conductor_api.py"`.

The fallback covers core CRUD and execution — not all CLI features. Limitations:

- **Auth:** accepts `CONDUCTOR_AUTH_TOKEN`, or exchanges
  `CONDUCTOR_AUTH_KEY` + `CONDUCTOR_AUTH_SECRET` at `POST /api/token`. An
  explicit token takes precedence. The exchanged JWT remains in memory and is
  never printed.
- **No profile support** — set `CONDUCTOR_SERVER_URL` directly. A root URL is
  normalized to `/api`; an existing `/api` or custom non-root path is preserved.
- **No server auto-detection** — `CONDUCTOR_SERVER_URL` is required.
- **No task-definition CRUD** — cannot list/create/update/delete task definitions.
- **No time-range search** — `search-workflows` accepts `--query` and `--status` only.
- **No** `update-execution`, `restart --use-latest`, `rerun`, `skip-task`, `jump`, schedules, secrets, webhooks, server lifecycle.
- **Agents:** the fallback covers the agent REST verbs that have **no CLI equivalent** (provider status, cancel, stop, deploy-from-config) plus the basics; it does not stream SSE or run agents locally — that needs the CLI or the SDK.

## Verb → command mapping

| Verb | CLI | Fallback |
|------|-----|----------|
| List workflow definitions | `conductor workflow list` | `python3 "$CONDUCTOR_API" list-workflows` |
| Get workflow definition | `conductor workflow get {name}` | `python3 "$CONDUCTOR_API" get-workflow --name {name} --version {v}` |
| Create workflow | `conductor workflow create file.json` | `python3 "$CONDUCTOR_API" create-workflow --file file.json [--overwrite]` (keeps `metadata`; `--overwrite` = `?overwrite=true`) |
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

## Agent verbs (also usable alongside the CLI — SKILL.md `allowed-tools` has no `curl`)

| Verb | CLI | Fallback |
|------|-----|----------|
| Provider status (which LLM keys the server has) | — | `python3 "$CONDUCTOR_API" providers-status` |
| List deployed agents | `conductor agent list` | `python3 "$CONDUCTOR_API" agent-list` |
| Get an agent definition | `conductor agent get {name}` | `python3 "$CONDUCTOR_API" agent-get --name {name} [--version N]` |
| Deploy a config file | — | `python3 "$CONDUCTOR_API" agent-deploy-config --file agent.json` (`POST /agent/deploy {"agentConfig": ...}`) |
| Start a deployed agent | `conductor agent run --name {name} "prompt"` | `python3 "$CONDUCTOR_API" agent-start --name {name} --prompt "..." [--session-id {id}]` |
| Execution status | `conductor agent status {id}` | `python3 "$CONDUCTOR_API" agent-status --id {id}` |
| Search executions | `conductor agent execution --name {n} --status {s}` | `python3 "$CONDUCTOR_API" agent-executions [--name {n}] [--status {s}] [--size 20]` |
| Execution detail + token usage | — | `python3 "$CONDUCTOR_API" agent-execution --id {id}` |
| Answer a human gate | `conductor agent respond {id} --approve` | `python3 "$CONDUCTOR_API" agent-respond --id {id} --approve` / `--deny --reason "..."` / `--message "..."` |
| Cancel | `conductor workflow terminate {id}` | `python3 "$CONDUCTOR_API" agent-cancel --id {id} --reason "..."` (`DELETE /agent/{id}/cancel`) |
| Graceful stop | — | `python3 "$CONDUCTOR_API" agent-stop --id {id}` |

## Orkes integrations (no CLI equivalent — use these even when the CLI is installed; see [orkes-integrations.md](orkes-integrations.md))

| Verb | Fallback |
|------|----------|
| Integration types + config fields | `python3 "$CONDUCTOR_API" integration-defs --category AI_MODEL` |
| List / get integrations (secrets masked) | `python3 "$CONDUCTOR_API" integration-list --category AI_MODEL` · `integration-get --name {name}` |
| Create / update an integration | `python3 "$CONDUCTOR_API" integration-save --name {name} --type openai --config-env api_key=OPENAI_API_KEY` |
| Delete an integration | `python3 "$CONDUCTOR_API" integration-delete --name {name}` |
| List / add / remove models | `python3 "$CONDUCTOR_API" model-list --provider {name}` · `model-save --provider {name} --model {id}` · `model-delete --provider {name} --model {id}` |
| Associate a prompt template | `python3 "$CONDUCTOR_API" prompt-associate --provider {name} --model {id} --prompt {template}` |
| Grant / list access | `python3 "$CONDUCTOR_API" grant-access --subject-type group --subject-id {group} --target-id {name}` · `access-list --target-id {name}` |

For anything not in the tables (task-definition CRUD, schedules, secrets, SSE streaming, etc.), the user must install the CLI.
