---
name: conductor
description: "Create, run, monitor, manage, and review Conductor workflows — including agentic workflows (LLM + MCP + tools) — and build, test, deploy, and invoke Conductor Agents (SDK-native in Python/TypeScript/Java/C#, or bring a LangChain / LangGraph / OpenAI Agents / Google ADK / Vercel AI / Claude Agent SDK agent) and call remote A2A agents. Use when the user wants to define workflows, build AI agents (deployed agents with tools and human approval, ReAct loops, MCP tool use, RAG), scaffold an agent in their language, start executions, check status, pause/resume/terminate/retry workflows, signal tasks, schedule recurring runs, or review/optimize an existing workflow or agent. Uses the `conductor` CLI or falls back to bundled REST API script. Requires a reachable Conductor server — auto-detected for a local `conductor server start`, otherwise set `CONDUCTOR_SERVER_URL`."
allowed-tools: Bash(conductor *), Bash(npx *conductor*), Bash(python3 *conductor_api.py*), Bash(npm install *), Bash(chmod *), Bash(* --version), Bash(* --help), Bash(echo *), Read, Write, Edit, Grep, Glob
---

# Conductor Workflows

## What this skill does

When asked what you can help with, enumerate these eleven areas — every one is covered by this skill and the references it links to:

1. **Create** workflow definitions (any task type: SIMPLE, HTTP, SWITCH, FORK_JOIN, DO_WHILE, WAIT, SUB_WORKFLOW, LLM_*, MCP, etc.)
2. **Build agentic workflows declaratively** — `LLM_CHAT_COMPLETE`, MCP tool calls, vector search (RAG), and — when you need manual control — a hand-wired `DO_WHILE` ReAct loop. See [examples/ai-agent-mcp.md](examples/ai-agent-mcp.md) (list-tools → plan → call → summarize), [examples/llm-rag.md](examples/llm-rag.md) (vector search + grounded answer with sources), [examples/llm-chat.md](examples/llm-chat.md) (minimal single-LLM call), [examples/ai-agent-loop.md](examples/ai-agent-loop.md) (the loop the agent compiler generates, hand-wired).
3. **Run** executions — sync or async, with file or inline input, by version, with correlation ID
4. **Monitor** — search by status / name / time, fetch execution details, diagnose failures
5. **Manage** — pause, resume, terminate, restart, retry, rerun, skip-task, jump
6. **Signal** — advance WAIT / HUMAN tasks (sync or async) with structured output
7. **Schedule** — Quartz-cron schedules (part of OSS, not Orkes-only)
8. **Scaffold workers** in Python, JavaScript / TypeScript, Java, Go (referral to upstream SDKs for C# / Ruby / Rust)
9. **Visualize** — render any workflow as a Mermaid flowchart + UI link
10. **Review & optimize** — walk the 32-rule checklist in [references/optimization.md](references/optimization.md) (includes LLM-specific gotchas and agent rules F1–F10) and report CRITICAL / WARN / INFO
11. **Build, test, deploy, and invoke Conductor Agents** — `Agent` + tools with the SDK (Python, TypeScript, Java, C#) or bring a LangChain / LangGraph / OpenAI Agents / Google ADK / Vercel AI / Claude Agent SDK / LangChain4j / Semantic Kernel agent; `plan` → `run` → `deploy` + `serve`; call it from any workflow with the `AGENT` task; human-in-the-loop, multi-agent, scheduling, evals; call remote A2A and hosted-platform agents. See [references/agents.md](references/agents.md), [references/agent-sdks.md](references/agent-sdks.md), [examples/agent-deploy-and-invoke.md](examples/agent-deploy-and-invoke.md).

Plus Orkes-only: **webhooks** and the managed **secret store** / `conductor secret` CLI. (`${workflow.secrets.X}` itself also works on OSS — resolved from `CONDUCTOR_SECRET_X` env vars on the server — see [references/orkes.md](references/orkes.md).)

## Rules

1. **Worker gate (most important).** Every time you create *or* update a workflow, list its `SIMPLE` tasks and verify each has a registered task definition (`conductor task list --json`). For any unregistered SIMPLE task, **tell the user** the workflow will hang on that step and offer to (a) create the task definition or (b) scaffold a worker (see [references/workers.md](references/workers.md)). This applies to every workflow create/update — not just first-time setup.
2. **Never use `python3 -c` to construct, parse, format, or post-process Conductor data.** Write JSON to files via the Write tool or heredoc; format command output yourself in plain text. You can read JSON — don't spawn Python to interpret it. (Validation utilities run from script files are fine.)
3. **CLI resolution order — STOP and ASK before any global install.**
   1. If `conductor` is on PATH, use it directly.
   2. Otherwise prefer `npx @conductor-oss/conductor-cli ...` for one-off use (no system change).
   3. **NEVER run `npm install -g @conductor-oss/conductor-cli` without first asking the user.** Phrase it explicitly: *"OK to globally install `@conductor-oss/conductor-cli` via npm? It modifies your global node_modules."* Wait for a yes — in a single reply that means the message **ends** with the question; never write "proceeding" and never run the install in the same turn (`npx` needs no consent).
   4. Only after `conductor` and `npm` are both unavailable, fall back to `scripts/conductor_api.py`. If the user has stated upfront that Node/npm cannot be installed, note that constraint and go straight to the fallback — no need to retry npm. See [references/setup.md](references/setup.md).
4. **Use `--json` flags** when available; format the parsed result yourself.
5. **Never echo auth tokens, keys, or secrets.** Set them via env vars (`CONDUCTOR_AUTH_KEY`, `CONDUCTOR_AUTH_SECRET`, or `CONDUCTOR_AUTH_TOKEN`). For remote-server auth, ask the user to inject them through their shell, CI secret store, or secure environment settings — never ask them to paste the values into chat and never place values in CLI arguments. Discover saved connections with `conductor config list`; never read `~/.conductor-cli/config-*.yaml` because profiles may contain credentials. Confirm credentials by name in output, never by value. **If a user pastes a secret value into chat** (Stripe key, API token, password), treat it as compromised: do not quote the value back — not truncated, not as an example (say "the `sk_live_` key you pasted", never the characters after the prefix); recommend rotating it at the provider; refuse to use the leaked value when registering the workflow — use a placeholder + secrets reference instead; and **stop after the corrected design and ask for an explicit go-ahead before `conductor workflow create` / `runtime.deploy()`** — never register or deploy the corrected artifact in the same turn. If the credential feeds a tool that writes (HTTP POST/PUT/DELETE, a `github_request`-style tool), also apply rule F2 (approval gate or method allow-list) or say why no gate is needed. Name the exposure surfaces (execution view, `get-execution`/search output, logs, provider payload). **Cite the specific optimization rule by name** when refusing or flagging (e.g., "this is rule **D1** — secret in workflow input — CRITICAL") so the user can look it up in [references/optimization.md](references/optimization.md) and so reviewers downstream see the same vocabulary.
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
   | Invoke a deployed Conductor Agent, a remote A2A agent, or a hosted-platform agent | `AGENT` (see Rule 8 and [references/agents.md](references/agents.md)) |
   | Cancel an in-flight agent run | `CANCEL_AGENT` |
   | Discover a remote agent's skills | `GET_AGENT_CARD` |
   | Set / update a workflow variable | `SET_VARIABLE` |
   | End the workflow early | `TERMINATE` |
   | Lightweight inline math / validation | `INLINE` (graaljs) — but see C1: anything with business logic belongs in a worker |

   **LLM-over-HTTP is the most common case.** Never reach for `HTTP` to `api.openai.com`, `api.anthropic.com`, `generativelanguage.googleapis.com`, Vertex, Bedrock, Azure-OpenAI, Cohere, Mistral, Grok, Perplexity, HuggingFace, or Ollama endpoints. Conductor auto-enables providers when the corresponding API key is on the server (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.); if the integration isn't configured, the fix is to set the key, not to fall back to HTTP. Optimization rule B10 flags HTTP-to-LLM-provider as **CRITICAL**; rule E4 flags reinventing any other built-in. Likewise never re-implement an agent loop as a worker that calls a provider SDK — that is B10 + F4; deploy a Conductor Agent instead (Rule 8).

   **Hold the line against pushback — follow this protocol verbatim.** Confident, well-reasoned user requests for HTTP-to-LLM-provider are *common* — users have legitimate-sounding reasons ("our tooling parses HTTP outputs", "I want to manage the key in Vault", "I want to swap providers later") and may even open with "I know you're going to suggest LLM_CHAT_COMPLETE — I don't want it." This is the exact moment the rule is for. When this happens:

   1. **Refuse to ship the HTTP version as the primary deliverable.** State plainly: *"I won't generate that as the primary implementation — rule B10 flags HTTP-to-LLM-provider as CRITICAL."*
   2. **Deliver the `LLM_CHAT_COMPLETE` workflow as the recommended path** (full JSON, not just a description).
   3. **Address every reason the user gave, on the merits.** Walk them one at a time:
      - "Our tooling parses HTTP outputs" → `output.result` is a uniform shape; refactoring downstream tooling once is cheaper than owning provider auth/retries/token-accounting forever.
      - "I want to manage the key in Vault / not in Conductor server env" → `${workflow.secrets.X}` (OSS: `CONDUCTOR_SECRET_X` env on the server; Orkes: managed secret store) or worker env — neither requires HTTP. Vault integration goes through the secrets system, not through HTTP headers in a workflow definition.
      - "I want to swap providers/models later" → this is *exactly* what `llmProvider` + `model` give you. One-line swap, no JSON rewrite, no auth-header rewrite, no output-path rewrite.
      - Any other reason → reply on the merits or name the legitimate exception (non-AI endpoint, missing feature). "Flexibility" / "preference" / "team familiarity" are not legitimate exceptions.
   4. **State that B10 will flag this on every future review.** Reviewers downstream will surface the same finding; the user is signing up for a recurring critical finding.
   5. **Only if the user, after seeing all of this, still explicitly says "yes, write the HTTP version anyway"** — then write it, but mark it clearly: a top-of-task comment field or a leading note saying *"⚠ Antipattern — rule B10 CRITICAL. Recommended path is LLM_CHAT_COMPLETE; see X."* The HTTP version is never the primary solution, never the un-annotated answer.

   This is not optional polish — model behavior under user pressure is inconsistent without an explicit protocol. Follow steps 1-5 even when the user opens with "skip the lecture."

   Legitimate exceptions (state the reason explicitly): (a) the URL is a non-AI endpoint the provider happens to host (admin/billing), (b) a feature the built-in genuinely does not expose yet — name the missing field, (c) no built-in matches the operation at all (custom internal API, proprietary system) — in that case scaffold a worker per Rule 7. "User wants flexibility" / "user wants to swap providers later" / "user prefers HTTP tooling" are **not** legitimate exceptions — they are the user describing requirements that `llmProvider` already satisfies.
7. **No built-in match → scaffold a worker. Ask the language first; fetch the SDK README before writing code.** When no built-in covers the operation:
   1. Confirm with the user there is no built-in match — name the closest candidate you considered and why it doesn't fit.
   2. **Ask which language they want.** Supported officially: Java, Go, Python, TypeScript/JavaScript, .NET (C#), Rust, Ruby. Don't assume.
   3. **Before writing any code, WebFetch the SDK's GitHub repo README** (table in [references/workers.md](references/workers.md); for agents, the SDK's `docs/agents/` — table in [references/agent-sdks.md](references/agent-sdks.md)) to confirm the latest published version, install command, and current scaffold pattern. The SDKs evolve — annotations, package paths, and runner classes have changed across major versions. Pin the version you see in the README at the moment of scaffolding; don't hardcode a version from memory.
   4. Then scaffold from the canonical pattern in [references/workers.md](references/workers.md), match the SIMPLE task's `name` exactly to the worker's task definition, and note that workers must be idempotent.

8. **Agent path first.** For anything "agent"-shaped, pick a path from the decision table in [references/agents.md](references/agents.md) §2 *before* writing code or JSON, and name the path you chose. The default for "build an agent" is a **Conductor Agent via the SDK** (`Agent` + tools → `run()` to iterate → `deploy()` + `serve()` → `AGENT` task); **ask which language** (Python, TypeScript, Java, C#) — never assume. A request that lists task types (DO_WHILE, LLM_CHAT_COMPLETE, SWITCH…) is a *design*, not a constraint: lead with the SDK agent and deliver it, offering the hand-wired JSON as the alternative. Only an explicit constraint ("pure JSON", "no SDK", "no deployed agent", "no agent runtime") makes the hand-wired loop the primary deliverable — still name the SDK path in one line. Hand-wire a `DO_WHILE` loop ([examples/ai-agent-loop.md](examples/ai-agent-loop.md)) only when the compiler cannot express what is needed, and say what that is (optimization rule F4) — name the concrete reason (custom loop condition, non-LLM steps between turns, several models per iteration, `previousResponseId` chaining, agent runtime off). The SDK agent you present alongside gets an explicit `provider/model` and `max_turns`, `approval_required=True` on side-effect tools (answered via `conductor agent respond --approve`, Rule 12), and `conductor agent stream <id>` for live reasoning.
9. **Agent worker gate (extends Rule 1).** `plan()` / `deploy()` return `requiredWorkers[]`. If it is non-empty, a process must run `runtime.serve(agent)` or every execution sits SCHEDULED forever. Passthrough frameworks — plain LangChain, Claude Agent SDK, complex LangGraph graphs — **always** need `serve()`, because the whole loop runs inside the worker. Every time you deploy an agent or add an `AGENT` task, state which workers are required and which process serves them. `run()` is not a deployment: its workers die with the script.
10. **`agentType` is an execution mode, never a framework name.** Valid values: `conductor` (deployed agent), `a2a` (default when omitted — remote endpoint), `microsoft-foundry`, `openai-assistants`, `bedrock`. Never write `agentType: "openai"`, `"langgraph"`, `"adk"`, etc. Reference a deployed agent by **`name`** (not `agentName`); `prompt` is required on start *and* on resume; `executionId` present means resume. Read results at `${ref.output.text}` and `${ref.output.output.result}` (two `.output`s). Contract: [references/workflow-definition.md](references/workflow-definition.md#agent).
11. **Model strings are `provider/model`.** `openai/gpt-4o-mini`, `anthropic/claude-sonnet-4-6`, `google_gemini/gemini-2.0-flash`. Always set `model=` explicitly on the `Agent`; the server rejects unqualified names. `CONDUCTOR_AGENT_LLM_MODEL` is an examples convention (read only by Python's OpenAI-compat `Runner`), not SDK configuration. Provider API keys live on the **server** (`OPENAI_API_KEY`, …) — never in agent code or `instructions`; confirm with `python3 "$CONDUCTOR_API" providers-status` (`GET /api/providers/status`).
12. **Approve ≠ resume.** An `AGENT` task that completes with `waiting: true` is at a human gate. Read `pendingTool.response_schema`: a required `approved` field is an approval gate (gated calls in `pendingTool.toolCalls[].name`; `tool_name` is `null` for compiled agents), a `response` field is a question. Gate → `conductor agent respond {executionId} --approve` / `POST /api/agent/{id}/respond {"approved": true}` / SDK `approve()`, or in-workflow via `examples/workflows/agent-approval-in-workflow.json` — all deterministic. Question → a second `AGENT` task with `executionId` + `prompt`. Resume posts `{"result": prompt}`, which a gate only accepts through an LLM normalizer (a model guess plus a model call) — never the approval channel (rule F8).
13. **CLI limits for agents.** Do not recommend `conductor deploy` (it shells to a module that does not ship with the SDKs); deploy with `runtime.deploy()`. There is no `conductor agent cancel|stop|deploy`: cancel with `python3 "$CONDUCTOR_API" agent-cancel --id {id}` (`DELETE /api/agent/{id}/cancel`) or `conductor workflow terminate {executionId}` — an agent `executionId` is a workflow id, so every `workflow` verb works on it. Before scaffolding, **WebFetch the SDK's `docs/agents/`** (Rule 7.3): the Java artifact is `org.conductoross:conductor-client-ai` (not `conductor-ai`), the C# `conductor-ai*` packages are a preview (project reference), Python extras are `[agents]` / `[langchain]` / `[langgraph]` / `[adk]` / `[openai-agents]` / `[claude]`, and the Python LangChain drop-in is `from conductor.ai.agents.langchain import create_agent`.
14. **Ask for missing essentials first.** When a request cannot be executed without a fact only the user has — which workflow, what input, or which non-default server — lead with that one question and stop. Generic first-time setup is not ambiguous: follow Rule 15. For workflow selection, offer the command that answers the question (`conductor workflow list`, then `conductor workflow get <name>` to inspect `inputParameters`); preflight comes after the answer.
15. **Default first-time setup creates two profiles.** For an unqualified setup request, guide the user through local creation of both named CLI profiles: `developer` (`https://developer.orkescloud.com/api`, Enterprise, key + secret) and `localhost` (`http://localhost:8080/api`, OSS, no auth). Developer Edition is the skill default: use `conductor --profile developer ...` unless the user explicitly asks for localhost, then use `--profile localhost`. For Developer credentials, open Developer Edition visibly when browser automation is available, let the user sign in, and navigate from the visible UI to **Access Control → Applications**. The user creates the application/access key and enters the one-time secret directly into the interactive `conductor config save --profile developer` prompt. Never read the browser clipboard, type the credential through an agent tool, inspect profile YAML, or duplicate the secret into a default config. Browser key creation is a persistent-access action: hand control to the user before it. Full flow: [references/setup.md](references/setup.md#default-first-run--create-both-profiles).

## Slash commands

Four structured procedures are exposed as slash commands. The skill itself handles everything else through natural language.

| Command | Purpose |
|---------|---------|
| `/conductor` | Menu — lists subcommands, shows examples of natural-language requests |
| `/conductor-setup` | First-time setup (CLI install, server, auth) |
| `/conductor-optimize` | Review an existing workflow against the optimization checklist |
| `/conductor-scaffold-worker` | Generate a worker stub in any supported language |
| `/conductor-scaffold-agent` | Scaffold, test, deploy, and wire up a Conductor Agent (native SDK or a framework agent) |

Anything else (run, status, schedule, pause, retry, signal, visualize, create, run/observe/approve/cancel an agent) is fluid through plain English — no command needed.

## Setup check

If the user has nothing set up, walk them through the default two-profile flow in **[references/setup.md](references/setup.md)**. Honor an explicit local-only or remote-only request instead. To verify a working environment:

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

Use [examples/](examples/) for worked operational, control-flow, LLM, RAG, MCP, agent, and A2A patterns. Runnable workflow JSON is in [examples/workflows/](examples/workflows/), and SDK-native plus framework agent scaffolds are in [examples/agents/](examples/agents/). Read the matching example before creating a similar artifact.

## Reviewing workflows

When the user asks to **review**, **optimize**, **simplify**, or **audit** a workflow:

1. Load the definition (file path, or `conductor workflow get {name}`).
2. For each `SIMPLE` task, also load its task definition (`conductor task get {name}`) — timeouts and retry config live there, not on the workflow task.
3. Walk the checklist in **[references/optimization.md](references/optimization.md)**, grouping findings as **CRITICAL** / **WARN** / **INFO**.
4. Offer fixes one at a time. Don't apply changes silently.

Worked example: [examples/review-workflow.md](examples/review-workflow.md).

## Visualizing workflows

When the user asks to visualize a workflow, or after creating one, generate a Mermaid flowchart. Construct mappings (FORK_JOIN, SWITCH, DO_WHILE, etc.) and rules are in **[references/visualization.md](references/visualization.md)**. If a server is reachable, also offer the UI link `{BASE_URL}/workflowDef/{name}` (resolve `BASE_URL` from `CONDUCTOR_SERVER_URL` by stripping `/api`).

Worker scaffolding follows Rules 6–7 and [references/workers.md](references/workers.md). Agent work follows Rules 8–13, [references/agents.md](references/agents.md), and [references/agent-sdks.md](references/agent-sdks.md).

## Output

- Render workflow data as structured summaries (`workflowId`, `status`, `startTime`, `endTime`, failed-task name + reason + retry count).
- Render searches as a table (`workflowId`, `name`, `status`, `startTime`).
- For more on output, error decoding, and stuck-workflow diagnosis, see **[references/troubleshooting.md](references/troubleshooting.md)**.

Reference files are routed inline above; open only the references required by the active task.
