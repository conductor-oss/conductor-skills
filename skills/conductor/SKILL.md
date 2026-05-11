---
name: conductor
description: "Create, run, monitor, manage, and review Conductor workflows and tasks. Use when the user wants to define workflows, start executions, check status, pause/resume/terminate/retry workflows, signal tasks, schedule recurring runs, or review/optimize an existing workflow. Uses the `conductor` CLI or falls back to bundled REST API script. Requires CONDUCTOR_SERVER_URL."
allowed-tools: Bash(conductor *), Bash(npx *conductor*), Bash(python3 *conductor_api.py*), Bash(npm install *), Bash(chmod *), Bash(* --version), Bash(* --help), Bash(echo *), Read, Write, Edit, Grep, Glob
---

# Conductor Workflows

## Rules

1. **Worker gate (most important).** Every time you create *or* update a workflow, list its `SIMPLE` tasks and verify each has a registered task definition (`conductor taskDef list`). For any unregistered SIMPLE task, **tell the user** the workflow will hang on that step and offer to (a) create the task definition or (b) scaffold a worker (see [references/workers.md](references/workers.md)). This applies to every workflow create/update — not just first-time setup.
2. **Never use `python3 -c` to construct, parse, format, or post-process Conductor data.** Write JSON to files via the Write tool or heredoc; format command output yourself in plain text. You can read JSON — don't spawn Python to interpret it. (Validation utilities run from script files are fine.)
3. **CLI resolution order:** (a) call `conductor` directly if installed; (b) otherwise `npx @conductor-oss/conductor-cli ...` for one-off use (no system change); (c) only run `npm install -g @conductor-oss/conductor-cli` after the user explicitly confirms — global installs modify the system; (d) fall back to `scripts/conductor_api.py` only when neither `conductor` nor `npm` is available. See [references/setup.md](references/setup.md).
4. **Use `--json` flags** when available; format the parsed result yourself.
5. **Never echo auth tokens, keys, or secrets.** Set them via env vars (`CONDUCTOR_AUTH_KEY`, `CONDUCTOR_AUTH_SECRET`, or `CONDUCTOR_AUTH_TOKEN`). Confirm credentials by name in output, never by value.

## Slash commands

Three structured procedures are exposed as slash commands. The skill itself handles everything else through natural language.

| Command | Purpose |
|---------|---------|
| `/conductor` | Menu — lists subcommands, shows examples of natural-language requests |
| `/conductor-setup` | First-time setup (CLI install, server, auth) |
| `/conductor-optimize` | Review an existing workflow against the optimization checklist |
| `/conductor-scaffold-worker` | Generate a worker stub in any supported language |

Anything else (run, status, schedule, pause, retry, signal, visualize, create) is fluid through plain English — no command needed.

## Setup check

If the user has nothing set up, walk them through **[references/setup.md](references/setup.md)** Steps 1–4. To verify a working environment:

```bash
conductor --version          # CLI present?
conductor workflow list      # Server reachable?
```

## Commands

Full verb-to-CLI lookup is in **[references/cli-index.md](references/cli-index.md)**. Python fallback equivalents (when neither `conductor` nor `npx` is available) are in **[references/fallback-cli.md](references/fallback-cli.md)**. Schedules (OSS) are in **[references/schedules.md](references/schedules.md)**. Enterprise commands (secrets, webhooks) are in **[references/orkes.md](references/orkes.md)**.

## Creating workflows

1. Consult **[references/workflow-definition.md](references/workflow-definition.md)** for task types, the `${...}` expression syntax, and the `$.var` rule for JS-evaluated tasks (INLINE, DO_WHILE, SWITCH/javascript).
2. Write the JSON to a file with the Write tool, then `conductor workflow create file.json`.
3. **Run the worker gate** (Rule 1).

For inputs to workflow start: use `-i '{"...":"..."}'` for small inline JSON, `-f input.json` for larger payloads.

## Examples

Operational:

- [Create and run](examples/create-and-run-workflow.md) — define, register, execute end-to-end.
- [Monitor and retry](examples/monitor-and-retry.md) — search failures, distinguish retryable from terminal, batch retry.
- [Signal a WAIT task](examples/signal-wait-task.md) — human-in-the-loop signaling.
- [Review and optimize a workflow](examples/review-workflow.md) — apply the optimization checklist.

Design patterns:

- [FORK_JOIN parallel branches](examples/fork-join.md)
- [DO_WHILE loop with iteration counter](examples/do-while-loop.md)
- [SUB_WORKFLOW composition](examples/sub-workflow.md)

Raw definitions in [examples/workflows/](examples/workflows/) — pass any directly to `conductor workflow create`:

| File | Pattern |
|------|---------|
| `weather-notification.json` | Two HTTP tasks in sequence, output chaining |
| `fork-join.json` | Parallel branches with JOIN + JQ merge |
| `do-while-loop.json` | DO_WHILE with iteration counter (self-reference pattern) |
| `child-normalize.json` | Reusable child workflow (JQ transform) |
| `parent-pipeline.json` | SUB_WORKFLOW composing the child above |

## Reviewing workflows

When the user asks to **review**, **optimize**, **simplify**, or **audit** a workflow:

1. Load the definition (file path, or `conductor workflow get {name}`).
2. For each `SIMPLE` task, also load its task definition (`conductor taskDef get {name}`) — timeouts and retry config live there, not on the workflow task.
3. Walk the checklist in **[references/optimization.md](references/optimization.md)**, grouping findings as **CRITICAL** / **WARN** / **INFO**.
4. Offer fixes one at a time. Don't apply changes silently.

Worked example: [examples/review-workflow.md](examples/review-workflow.md).

## Visualizing workflows

When the user asks to visualize a workflow, or after creating one, generate a Mermaid flowchart. Construct mappings (FORK_JOIN, SWITCH, DO_WHILE, etc.) and rules are in **[references/visualization.md](references/visualization.md)**. If a server is reachable, also offer the UI link `{BASE_URL}/workflowDef/{name}` (resolve `BASE_URL` from `CONDUCTOR_SERVER_URL` by stripping `/api`).

## Workers

When the user asks to write a worker:

1. Ask which language (Python, JS/TS, Java, Go, C#, Ruby, Rust).
2. Install the SDK and scaffold from the pattern in **[references/workers.md](references/workers.md)**.
3. The worker's task type **must** match the `name` of the SIMPLE task in the workflow.
4. Note in code that workers must be idempotent — Conductor may redeliver on failure or timeout.

## Output

- Render workflow data as structured summaries (`workflowId`, `status`, `startTime`, `endTime`, failed-task name + reason + retry count).
- Render searches as a table (`workflowId`, `name`, `status`, `startTime`).
- For more on output, error decoding, and stuck-workflow diagnosis, see **[references/troubleshooting.md](references/troubleshooting.md)**.

## References at a glance

| File | Purpose |
|------|---------|
| [setup.md](references/setup.md) | Install CLI, configure server, auth, profiles |
| [cli-index.md](references/cli-index.md) | Verb → CLI command lookup |
| [fallback-cli.md](references/fallback-cli.md) | Python fallback equivalents (subset of CLI) |
| [workflow-definition.md](references/workflow-definition.md) | JSON schema, all task types, expression syntax |
| [workers.md](references/workers.md) | SDK examples in 7 languages |
| [api-reference.md](references/api-reference.md) | REST endpoints |
| [visualization.md](references/visualization.md) | Mermaid mappings + UI link |
| [schedules.md](references/schedules.md) | Cron schedules (OSS) — schema, format, patterns |
| [orkes.md](references/orkes.md) | Enterprise (Orkes): secrets, webhooks |
| [optimization.md](references/optimization.md) | Workflow review/optimize checklist |
| [troubleshooting.md](references/troubleshooting.md) | Common errors + diagnosis flow |
