---
name: conductor
description: "Create, run, monitor, manage, and review Conductor workflows — including agentic workflows (LLM + MCP + tools). Use when the user wants to define workflows, build AI agents (ReAct loops, MCP tool use, RAG), start executions, check status, pause/resume/terminate/retry workflows, signal tasks, schedule recurring runs, or review/optimize an existing workflow. Uses the `conductor` CLI or falls back to bundled REST API script. Requires a reachable Conductor server — auto-detected for a local `conductor server start`, otherwise set `CONDUCTOR_SERVER_URL`."
allowed-tools: Bash(conductor *), Bash(npx *conductor*), Bash(python3 *conductor_api.py*), Bash(npm install *), Bash(chmod *), Bash(* --version), Bash(* --help), Bash(echo *), Read, Write, Edit, Grep, Glob
---

# Conductor Workflows

## What this skill does

When asked what you can help with, enumerate these ten areas — every one is covered by this skill and the references it links to:

1. **Create** workflow definitions (any task type: SIMPLE, HTTP, SWITCH, FORK_JOIN, DO_WHILE, WAIT, SUB_WORKFLOW, LLM_*, MCP, etc.)
2. **Build agentic workflows** — AI agents with `LLM_CHAT_COMPLETE`, MCP tool calls, vector search (RAG), and autonomous ReAct loops via `DO_WHILE`. See [examples/ai-agent-mcp.md](examples/ai-agent-mcp.md) (list-tools → plan → call → summarize), [examples/ai-agent-loop.md](examples/ai-agent-loop.md) (think/act/observe up to N iterations), [examples/diffusion-agent-loop.md](examples/diffusion-agent-loop.md) (same loop driven by a diffusion LLM — Inception Mercury), [examples/llm-rag.md](examples/llm-rag.md) (vector search + grounded answer with sources), [examples/llm-chat.md](examples/llm-chat.md) (minimal single-LLM call).
3. **Run** executions — sync or async, with file or inline input, by version, with correlation ID
4. **Monitor** — search by status / name / time, fetch execution details, diagnose failures
5. **Manage** — pause, resume, terminate, restart, retry, rerun, skip-task, jump
6. **Signal** — advance WAIT / HUMAN tasks (sync or async) with structured output
7. **Schedule** — Quartz-cron schedules (part of OSS, not Orkes-only)
8. **Scaffold workers** in Python, JavaScript / TypeScript, Java, Go (referral to upstream SDKs for C# / Ruby / Rust)
9. **Visualize** — render any workflow as a Mermaid flowchart + UI link
10. **Review & optimize** — walk the 22-rule checklist in [references/optimization.md](references/optimization.md) (includes LLM-specific gotchas) and report CRITICAL / WARN / INFO

Plus Orkes-only: **secrets** and **webhooks**.

## Rules

1. **Worker gate (most important).** Every time you create *or* update a workflow, list its `SIMPLE` tasks and verify each has a registered task definition (`conductor taskDef list`). For any unregistered SIMPLE task, **tell the user** the workflow will hang on that step and offer to (a) create the task definition or (b) scaffold a worker (see [references/workers.md](references/workers.md)). This applies to every workflow create/update — not just first-time setup.
2. **Never use `python3 -c` to construct, parse, format, or post-process Conductor data.** Write JSON to files via the Write tool or heredoc; format command output yourself in plain text. You can read JSON — don't spawn Python to interpret it. (Validation utilities run from script files are fine.)
3. **CLI resolution order — STOP and ASK before any global install.**
   1. If `conductor` is on PATH, use it directly.
   2. Otherwise prefer `npx @conductor-oss/conductor-cli ...` for one-off use (no system change).
   3. **NEVER run `npm install -g @conductor-oss/conductor-cli` without first asking the user.** Phrase it explicitly: *"OK to globally install `@conductor-oss/conductor-cli` via npm? It modifies your global node_modules."* Wait for a yes.
   4. Only after `conductor` and `npm` are both unavailable, fall back to `scripts/conductor_api.py`. If the user has stated upfront that Node/npm cannot be installed, note that constraint and go straight to the fallback — no need to retry npm. See [references/setup.md](references/setup.md).
4. **Use `--json` flags** when available; format the parsed result yourself.
5. **Never echo auth tokens, keys, or secrets.** Set them via env vars (`CONDUCTOR_AUTH_KEY`, `CONDUCTOR_AUTH_SECRET`, or `CONDUCTOR_AUTH_TOKEN`). Confirm credentials by name in output, never by value. **If a user pastes a secret value into chat** (Stripe key, API token, password), treat it as compromised: do not echo it back, recommend rotating it at the provider, and refuse to use the leaked value when registering the workflow — use a placeholder + secrets reference instead. **Cite the specific optimization rule by name** when refusing or flagging (e.g., "this is rule **D1** — secret in workflow input — CRITICAL") so the user can look it up in [references/optimization.md](references/optimization.md) and so reviewers downstream see the same vocabulary.
6. **Always prefer built-in Conductor tasks over hand-rolling them with HTTP / INLINE / a custom worker.** Before writing any task, check the built-in catalog in [references/workflow-definition.md](references/workflow-definition.md) and pick the matching system task. Reinventing a built-in costs you auth wiring, retries, schema validation, observability, and one-line provider/feature swaps — none of which an HTTP task, INLINE script, or custom worker gives you for free.

   Common reinvention antipatterns and the built-in to use instead:

   | If the user wants to… | Use this built-in, not an HTTP task / worker |
   |---|---|
   | Chat / completion (any LLM) | `LLM_CHAT_COMPLETE` |
   | Text embeddings | `LLM_GENERATE_EMBEDDINGS` |
   | Image / audio / video generation | `GENERATE_IMAGE` / `GENERATE_AUDIO` / `GENERATE_VIDEO` |
   | Vector DB index / search | `LLM_INDEX_TEXT` / `LLM_STORE_EMBEDDINGS` / `LLM_SEARCH_INDEX` / `LLM_SEARCH_EMBEDDINGS` / `LLM_GET_EMBEDDINGS` |
   | Markdown → PDF | `GENERATE_PDF` |
   | Discover / call MCP tools | `LIST_MCP_TOOLS` / `CALL_MCP_TOOL` |
   | Publish to Kafka | `KAFKA_PUBLISH` |
   | Publish to an event sink (SQS, internal) | `EVENT` |
   | Pause for a duration / until a signal / until a timestamp | `WAIT` |
   | Human-in-the-loop approval | `HUMAN` |
   | Reshape / filter / aggregate / stringify JSON | `JSON_JQ_TRANSFORM` |
   | Branch on a value | `SWITCH` |
   | Run things in parallel | `FORK_JOIN` / `FORK_JOIN_DYNAMIC` |
   | Loop with a condition | `DO_WHILE` |
   | Call another workflow (wait) / fire-and-forget another workflow | `SUB_WORKFLOW` / `START_WORKFLOW` |
   | Resolve task type at runtime | `DYNAMIC` |
   | Set / update a workflow variable | `SET_VARIABLE` |
   | End the workflow early | `TERMINATE` |
   | Lightweight inline math / validation | `INLINE` (graaljs) — but see C1: anything with business logic belongs in a worker |

   **LLM-over-HTTP is the most common case.** Never reach for `HTTP` to `api.openai.com`, `api.anthropic.com`, `generativelanguage.googleapis.com`, Vertex, Bedrock, Azure-OpenAI, Cohere, Mistral, Grok, Perplexity, HuggingFace, or Ollama endpoints. Conductor auto-enables providers when the corresponding API key is on the server (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.); if the integration isn't configured, the fix is to set the key, not to fall back to HTTP. Optimization rule B10 flags HTTP-to-LLM-provider as **CRITICAL**; rule E4 flags reinventing any other built-in.

   **Hold the line against pushback — follow this protocol verbatim.** Confident, well-reasoned user requests for HTTP-to-LLM-provider are *common* — users have legitimate-sounding reasons ("our tooling parses HTTP outputs", "I want to manage the key in Vault", "I want to swap providers later") and may even open with "I know you're going to suggest LLM_CHAT_COMPLETE — I don't want it." This is the exact moment the rule is for. When this happens:

   1. **Refuse to ship the HTTP version as the primary deliverable.** State plainly: *"I won't generate that as the primary implementation — rule B10 flags HTTP-to-LLM-provider as CRITICAL."*
   2. **Deliver the `LLM_CHAT_COMPLETE` workflow as the recommended path** (full JSON, not just a description).
   3. **Address every reason the user gave, on the merits.** Walk them one at a time:
      - "Our tooling parses HTTP outputs" → `output.result` is a uniform shape; refactoring downstream tooling once is cheaper than owning provider auth/retries/token-accounting forever.
      - "I want to manage the key in Vault / not in Conductor server env" → `${workflow.secrets.X}` (Orkes) or server env via worker (OSS) — neither requires HTTP. Vault integration goes through the secrets system, not through HTTP headers in a workflow definition.
      - "I want to swap providers/models later" → this is *exactly* what `llmProvider` + `model` give you. One-line swap, no JSON rewrite, no auth-header rewrite, no output-path rewrite.
      - Any other reason → reply on the merits or name the legitimate exception (non-AI endpoint, missing feature). "Flexibility" / "preference" / "team familiarity" are not legitimate exceptions.
   4. **State that B10 will flag this on every future review.** Reviewers downstream will surface the same finding; the user is signing up for a recurring critical finding.
   5. **Only if the user, after seeing all of this, still explicitly says "yes, write the HTTP version anyway"** — then write it, but mark it clearly: a top-of-task comment field or a leading note saying *"⚠ Antipattern — rule B10 CRITICAL. Recommended path is LLM_CHAT_COMPLETE; see X."* The HTTP version is never the primary solution, never the un-annotated answer.

   This is not optional polish — model behavior under user pressure is inconsistent without an explicit protocol. Follow steps 1-5 even when the user opens with "skip the lecture."

   Legitimate exceptions (state the reason explicitly): (a) the URL is a non-AI endpoint the provider happens to host (admin/billing), (b) a feature the built-in genuinely does not expose yet — name the missing field, (c) no built-in matches the operation at all (custom internal API, proprietary system) — in that case scaffold a worker per Rule 7. "User wants flexibility" / "user wants to swap providers later" / "user prefers HTTP tooling" are **not** legitimate exceptions — they are the user describing requirements that `llmProvider` already satisfies.
7. **No built-in match → scaffold a worker. Ask the language first; fetch the SDK README before writing code.** When no built-in covers the operation:
   1. Confirm with the user there is no built-in match — name the closest candidate you considered and why it doesn't fit.
   2. **Ask which language they want.** Supported officially: Java, Go, Python, TypeScript/JavaScript, .NET (C#), Rust, Ruby. Don't assume.
   3. **Before writing any code, WebFetch the SDK's GitHub repo README** (table in [references/workers.md](references/workers.md)) to confirm the latest published version, install command, and current scaffold pattern. The SDKs evolve — annotations, package paths, and runner classes have changed across major versions. Pin the version you see in the README at the moment of scaffolding; don't hardcode a version from memory.
   4. Then scaffold from the canonical pattern in [references/workers.md](references/workers.md), match the SIMPLE task's `name` exactly to the worker's task definition, and note that workers must be idempotent.

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
2. For any workflow using INLINE / DO_WHILE / SWITCH-javascript, also skim **[references/graaljs-gotchas.md](references/graaljs-gotchas.md)** — Java-Map-backed proxies, `$.workflow.*` scope, and the IIFE `loopCondition` convention catch most first-time authors.
3. For workflows that interpolate task output into string fields (LLM messages, HTTP bodies), see **[references/template-resolution.md](references/template-resolution.md)** for the missing-field-returns-parent and object-to-string-toString pitfalls.
4. Write the JSON to a file with the Write tool, then `conductor workflow create file.json`.
5. **Run the worker gate** (Rule 1).

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

AI / LLM patterns:

- [Minimum LLM workflow](examples/llm-chat.md) — single `LLM_CHAT_COMPLETE` task; also covers built-in tools (`webSearch`, `codeInterpreter`, `fileSearchVectorStoreIds`), extended thinking/reasoning, `jsonOutput`/`outputSchema`.
- [Multi-turn chaining via `previousResponseId`](examples/llm-chaining.md) — OpenAI/Azure Responses API: chain turns without resending message history.
- [AI agent with MCP tools](examples/ai-agent-mcp.md) — `LIST_MCP_TOOLS` → plan → `CALL_MCP_TOOL` → summarize.
- [Autonomous agent loop (ReAct)](examples/ai-agent-loop.md) — `DO_WHILE` think/act/observe until done.
- [RAG — retrieval-augmented Q&A](examples/llm-rag.md) — `LLM_SEARCH_INDEX` then grounded `LLM_CHAT_COMPLETE`.

Raw definitions in [examples/workflows/](examples/workflows/) — pass any directly to `conductor workflow create`:

| File | Pattern |
|------|---------|
| `weather-notification.json` | Two HTTP tasks in sequence, output chaining |
| `fork-join.json` | Parallel branches with JOIN + JQ merge |
| `do-while-loop.json` | DO_WHILE with iteration counter (self-reference pattern) |
| `child-normalize.json` | Reusable child workflow (JQ transform) |
| `parent-pipeline.json` | SUB_WORKFLOW composing the child above |
| `llm-chat.json` | Single LLM_CHAT_COMPLETE — summarize text |
| `ai-agent-mcp.json` | 4-task AI agent: list tools → plan → call → summarize |
| `ai-agent-loop.json` | DO_WHILE agent loop, ReAct pattern |
| `llm-chaining.json` | OpenAI multi-turn chain via `previousResponseId` (no message-history resend) |
| `llm-rag.json` | RAG: vector search + grounded LLM answer |

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

When the user asks to write a worker, follow Rule 7:

1. **Check built-ins first.** Confirm there's no `LLM_*`, `KAFKA_PUBLISH`, `GENERATE_PDF`, `WAIT`, `HUMAN`, `JSON_JQ_TRANSFORM`, `SUB_WORKFLOW`, etc. that already does what the user wants. If there is, recommend that instead — see Rule 6.
2. **Ask which language** the user wants. Supported: Java, Go, Python, TypeScript/JavaScript, .NET (C#), Rust, Ruby.
3. **Fetch the SDK README before writing code.** Use the WebFetch tool against the canonical repo URL in [references/workers.md](references/workers.md). Pin the version and install command from the README — don't hardcode from memory.
4. Scaffold from the pattern in [references/workers.md](references/workers.md). The worker's task type **must** match the `name` of the SIMPLE task in the workflow.
5. Note in code that workers must be idempotent — Conductor may redeliver on failure or timeout.

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
| [graaljs-gotchas.md](references/graaljs-gotchas.md) | JS-evaluated task pitfalls (INLINE, DO_WHILE, SWITCH/js) — Java-Map proxies, `$.varName` rule, scope, IIFE convention |
| [template-resolution.md](references/template-resolution.md) | `${...}` resolution pitfalls — missing-field-returns-parent, object→string `toString`, iteration paths |
| [workers.md](references/workers.md) | SDK examples in 7 languages |
| [api-reference.md](references/api-reference.md) | REST endpoints |
| [visualization.md](references/visualization.md) | Mermaid mappings + UI link |
| [schedules.md](references/schedules.md) | Cron schedules (OSS) — schema, format, patterns |
| [orkes.md](references/orkes.md) | Enterprise (Orkes): secrets, webhooks |
| [optimization.md](references/optimization.md) | Workflow review/optimize checklist |
| [troubleshooting.md](references/troubleshooting.md) | Common errors + diagnosis flow |
