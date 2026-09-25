# Conductor Agents

A **Conductor Agent** is an agent you author in code — with the Conductor SDK's own `Agent` class or by bringing an OpenAI Agents / LangChain / LangGraph / Google ADK / Vercel AI / Claude Agent SDK / LangChain4j / LangGraph4j / Semantic Kernel agent — that the **server compiles into an ordinary workflow** named after the agent. Every LLM turn, tool call, guardrail, human pause and retry is a task in the execution view. Compiled shape (this is what the hand-wired loop in [../examples/ai-agent-loop.md](../examples/ai-agent-loop.md) reproduces by hand):

```
{name}_init_state (SET_VARIABLE)
{name}_loop (DO_WHILE, iteration < maxTurns && !_stop_requested && (toolCalls || LENGTH))
    {name}_llm (LLM_CHAT_COMPLETE) → guardrails → tool-routing SWITCH → [HUMAN approval] → FORK_JOIN_DYNAMIC tools → JOIN → state merge
{name}_synth_output (INLINE)   → outputs {result, finishReason, context, rejectionReason}
```

An agent **execution id is a workflow id** — every `conductor workflow ...` verb (get-execution, terminate, pause, retry) works on it. The deployed agent is a registered workflow definition with `metadata.classifier = "AGENT"`, so schedules, `SUB_WORKFLOW`, `FORK_JOIN` and the `AGENT` task all compose with it.

This page is the contract and the operating manual. Per-language code lives in [agent-sdks.md](agent-sdks.md); the `AGENT` / `CANCEL_AGENT` / `GET_AGENT_CARD` task JSON is in [workflow-definition.md](workflow-definition.md#agent); the end-to-end walk-through is [../examples/agent-deploy-and-invoke.md](../examples/agent-deploy-and-invoke.md).

## 1. Prerequisite check (run before anything else)

```bash
conductor workflow list                                  # server reachable?
conductor agent list                                     # agent runtime on? (table or "No agents found." = yes)
python3 "$CONDUCTOR_API" providers-status                # which LLM providers are configured on the SERVER
```

`CONDUCTOR_API` is the path to this skill's `scripts/conductor_api.py` (`export CONDUCTOR_API="<skill-path>/scripts/conductor_api.py"`). It is used **alongside** the CLI for the agent verbs the CLI lacks — provider status, cancel, stop, deploy-from-config — because SKILL.md's `allowed-tools` has no `curl`. Set it once per session even when `conductor` is installed.

- `conductor agent list` returning 404 / HTML / connection error means the agent runtime is off. `conductor server start` enables it (`--conductor.integrations.ai.enabled=true --agentspan.embedded=true`). For a remote server the admin sets `conductor.integrations.ai.enabled=true` (and `agentspan.embedded=true`, `spring.main.allow-bean-definition-overriding=true`). **Stop here if it fails** — an `AGENT` task with `agentType: "conductor"` on such a server fails with the misleading `AGENT requires 'agentUrl'`.
- Provider keys live on the **server** (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `XAI_API_KEY`, `OLLAMA_BASE_URL`, …), never in agent code. Pick a `provider/model` whose provider reports `configured: true` (provider names: `openai`, `anthropic`, `gemini`, `azureopenai`, `aws_bedrock`, `mistral`, `cohere`, `grok`, `perplexity`, `huggingface`, `ollama`; the Gemini model prefix is `google_gemini/`).
- MCP / OpenAPI tool discovery is outbound **deny-all** by default: the admin lists origins in `conductor.ai.outbound.allowed-origins` (`conductor.ai.outbound.allow-private-networks=true` for localhost in dev).

## 2. Which path? (SKILL.md Rule 8)

| Signals in the request | Path | You produce | Read |
|---|---|---|---|
| Fixed step order; "call an LLM then X"; one MCP call; summarize / classify / embed / RAG; orchestration *is* the product; must be editable as JSON | **1. Declarative LLM graph** | workflow JSON (`LLM_CHAT_COMPLETE`, `LIST_MCP_TOOLS`/`CALL_MCP_TOOL`, `LLM_SEARCH_INDEX`, SWITCH/HUMAN) | workflow-definition.md, ../examples/llm-chat.md, ai-agent-mcp.md, llm-rag.md |
| "build an agent", tools chosen by the model, "until done", multi-agent / handoff / router, approval before it acts, reusable by name from several workflows, scheduled agent, needs tests/evals, a language named or a code repo open | **2. Conductor Agent via SDK (default)** | agent code + release/serve entry points + optional `AGENT` workflow | this page, agent-sdks.md, ../examples/agent-deploy-and-invoke.md |
| "I already have a LangGraph / LangChain / OpenAI Agents / ADK / Vercel AI / Claude Agent SDK / LangChain4j / LangGraph4j / Semantic Kernel agent", or those imports are in the repo | **3. Bring your framework** | 1–3 line change + serve process | agent-sdks.md §4 |
| "call an external agent at URL", A2A, agent card, agent owned by another team/vendor | **4. Remote A2A agent** | workflow JSON (`AGENT` a2a, `GET_AGENT_CARD`) | workflow-definition.md#agent, ../examples/agent-a2a-remote.md |
| Agent already lives in Microsoft Foundry / OpenAI Assistants / AWS Bedrock | **4b. Hosted platform agent** | workflow JSON (`AGENT` + `credentials{}` + `rawConfig`) | §9 below |
| "turn this SKILL.md / agentskills.io folder into an agent" | **4c. Skill agent** | `conductor skill run|load|serve` (needs `agentspan.skills.enabled=true`) | cli-index.md |
| Custom loop condition, non-LLM steps between turns, several models per iteration, OpenAI `previousResponseId` chaining, agents disabled on the server, single-JSON deliverable | **5. Hand-wired `DO_WHILE` loop (escape hatch)** | workflow JSON | ../examples/ai-agent-loop.md, graaljs-gotchas.md |

Tie-breakers: reusable-by-name or scheduled → 2; step order fixed → 1; repo already imports a framework → 3; nothing named → 2 and **ask the language**. Paths 2, 3, 4 and 4b all end in the same `AGENT` task; paths 1 and 5 never need an SDK process. Name the path you chose.

Phrasing → path: "workflow that summarizes a ticket with Claude and posts to Slack" → 1 · "agent that looks up orders and issues refunds after approval" → 2 (`approval_required=True`) · "list MCP tools, pick one, call it" → 1 (add "loop until done" → 2 with `mcp_tool(url)`) · "run my LangGraph graph durably" → 3 · "call the currency agent at https://agents.example.com" → 4 · "ReAct loop, but each iteration must write an audit row and stop when confidence > 0.9" → 2 first (custom `@tool` + `termination`/`stop_when`), 5 only if JSON-only is a hard requirement.

## 3. Lifecycle verbs (identical in Python / TypeScript / Java / C#)

| Verb | Registers definition? | Starts an execution? | Runs local tool workers? | Blocks? | Use |
|---|---|---|---|---|---|
| `plan(agent)` | no | no | no | no | dev / CI — returns `{workflowDef, requiredWorkers}` |
| `run(agent, prompt)` | if needed | yes | yes, until it returns | yes → `AgentResult` | your desk; **not a deployment** — its workers die with the script |
| `start(agent, prompt)` / `stream(agent, prompt)` | if needed | yes | yes | no → `AgentHandle` / `AgentStream` | apps, live UIs |
| `deploy(agent, ...)` | **yes** (named, versioned) | no | no | no | release pipeline; returns `requiredWorkers[]` |
| `serve(agent, ...)` | yes | no | **yes, forever** (`blocking=False` for tests) | yes | production worker process for the agent's `worker` tools (and the whole loop for passthrough frameworks) |
| `resume(executionId, agent)` | — | re-attaches | yes | — | after a worker restart |
| handle / runtime control | — | — | — | — | `get_status`, `respond`, `approve`, `reject`, `send_message`, `signal`, `pause`, `resume`, `stop`, `cancel(reason)` |

Production split: `release.py` → `runtime.deploy(agent)` once in CI; `worker.py` → `runtime.serve(agent)` as a long-lived service; workflows call the agent by name with the `AGENT` task.

**Agent worker gate (SKILL.md Rule 9).** `plan()`/`deploy()` return `requiredWorkers[]`. If it is non-empty, or the framework is passthrough (§6), a `serve()` process must be running or every execution sits IN_PROGRESS with a tool task stuck SCHEDULED. State which workers are required and which process serves them, every time.

## 4. Agent definition and run settings

Definition fields (SDK snake_case; wire camelCase in `AgentConfig`, the body of `POST /api/agent/deploy` and what every bridge serializes to):

| Field | Default | Meaning |
|---|---|---|
| `name` * | — | deployed agent name = workflow name (`^[a-zA-Z_][a-zA-Z0-9_-]*$`) |
| `model` * | — | **`provider/model`** (`openai/gpt-4o-mini`, `anthropic/claude-sonnet-4-6`, `google_gemini/gemini-2.0-flash`); bare names are rejected (`Invalid model format`). `""` = external agent reference |
| `instructions` | `""` | system prompt (string, callable, or prompt template) |
| `tools[]` | `[]` | see §5 |
| `guardrails[]` | `[]` | see §5 |
| `agents[]` + `strategy` | `handoff` | sub-agents; `handoff` · `router` · `sequential` · `parallel` · `swarm` · `round_robin` · `random` · `plan_execute` (needs `planner=`, optional `fallback=`) · `manual` |
| `max_turns` (`maxTurns`) | 25 | hard cap on model turns — the main runaway-loop control |
| `max_tokens`, `temperature`, `reasoning_effort`, `thinking_budget_tokens`, `context_window_budget` | — | per-call model knobs / proactive context condensation |
| `output_type` (wire: `outputType.schema`) | — | structured final answer: **Python takes a Pydantic `BaseModel` subclass** (not a JSON-schema dict — that raises `TypeError: ... is not a Pydantic BaseModel`); TS takes a Zod schema or JSON Schema; Java `.outputType(Class)`; C# `WithOutputType<T>()`. Sets `jsonOutput` on the LLM task; read it at `${ref.output.output.result}` |
| `memory`, `termination`, `handoffs`, `callbacks`, `allowed_transitions`, `required_tools`, `prefill_tools`, `gate`, `stop_when` | — | conversation memory, composable termination (`text_mention`/`stop_message`/`max_message`/`token_usage`/`and`/`or`), handoff rules, before/after agent/model/tool hooks, transition allow-list, tool pre-seeding, loop predicate |
| `cli_commands` / `cli_allowed_commands` / `cli_config` | off | sandboxed `run_command` tool with an allow-list |
| `local_code_execution` / `allowed_languages` / `code_execution` | off | code execution (local / docker / jupyter / serverless executors) |
| `credentials[]` | `[]` | secret **names** the server injects at call time (see §8 secrets) |
| `masked_fields[]`, `metadata`, `timeout_seconds` | — | redaction in history/UI (server-side application is a known no-op in TS today), labels, agent wall-clock (compiled default 60 s → set it) |
| advanced: `before_agent_callback` / `after_agent_callback` / `before_model_callback` / `after_model_callback`, `introduction`, `include_contents` (`"none"` = fresh sub-agent context), `enable_planning`, `planner_context`, `plan_source`, `fallback_max_turns`, `synthesize` (False = specialist speaks last), `stateful`, `base_url`, `allowed_commands`, `dependencies` | — | hooks, plan-execute knobs, per-agent LLM base URL |

Run settings (per call): `prompt`, `version`, `session_id`, `idempotency_key`, `media[]`, `context{}`, `timeout`, `credentials`, `on_event`, `RunSettings(model, temperature, max_tokens, reasoning_effort, thinking_budget_tokens)`. Run wins over definition for model/temperature/max_tokens; `max_turns`, `tools`, `guardrails`, `agents`, `strategy` are definition-only (redeploy to change). `session_id` correlates executions (it becomes `contextId`) but does not replay earlier turns into a new run — for multi-turn continuity set `memory=` (`ConversationMemory` / `SemanticMemory`) or feed the previous result back in `prompt` / `context`.

## 5. Tools and guardrails

| Tool type (SDK constructor) | Compiles to | Needs `serve()`? |
|---|---|---|
| `worker` — `@tool` / `tool()` / `@Tool` / `[Tool]` functions, existing `@worker_task` workers, framework function tools | `SIMPLE` | **yes** |
| `http_tool(url, method, headers, input_schema)` | `HTTP` | no |
| `api_tool(url)` — OpenAPI 3.x / Swagger / Postman discovery → many tools | `HTTP` + discovery pre-tasks | no |
| `mcp_tool(server_url, tool_names=...)` | `LIST_MCP_TOOLS` at compile + `CALL_MCP_TOOL` | no |
| `agent_tool(agent)` — another agent as a tool | `SUB_WORKFLOW` | no (the sub-agent's own workers still need serving) |
| `human_tool(name, description, input_schema)` | `HUMAN` (pauses with `waiting: true`) | no |
| `wait_for_message_tool` | `PULL_WORKFLOW_MESSAGES` | no |
| `image_tool` / `audio_tool` / `video_tool` / `pdf_tool`, `index_tool` / `search_tool` | `GENERATE_*`, `LLM_INDEX_TEXT` / `LLM_SEARCH_INDEX` | no |
| `cli` (`cli_commands=True`) | server-side sandbox | no |

Per-tool knobs on `@tool(...)`: `approval_required` (→ HUMAN gate before the call), `timeout_seconds`, `max_calls`, `guardrails=[...]`, `credentials=[...]`, `stateful`, `retry_count`/`retry_delay_seconds`. The constructors `agent_tool()`, `http_tool()`, `api_tool()`, `mcp_tool()`, `human_tool()` do **not** accept `max_calls`/`timeout_seconds`/`approval_required` (TypeError, verified against SDK 2.0.0) — set the attribute on the returned `ToolDef` instead (`t = agent_tool(child); t.max_calls = 3` → wire `maxCalls`). `${NAME}` placeholders in HTTP headers are resolved server-side. Generated tool task defs get `retryCount=2, retryDelaySeconds=2, LINEAR_BACKOFF, responseTimeoutSeconds=3600` — make tools idempotent. Tool `description` is the routing contract the model reads; write it plainly.

Guardrails: `RegexGuardrail(patterns, mode=block|allow, position=Position.INPUT|OUTPUT, on_fail=OnFail.RETRY|RAISE|FIX|HUMAN, max_retries=3, message)` (compiles to `INLINE`, no worker) · `LLMGuardrail(model, policy, position, on_fail)` (second model, temperature 0) · `@guardrail` function returning `GuardrailResult(passed, message)` wrapped as `Guardrail(fn, on_fail=...)` (compiles to a `SIMPLE` worker) · external worker by name. Put the strongest guardrail directly before a consequential tool.

Other building blocks (Python names; TS/Java/C# mirror them): termination `TextMentionTermination` / `StopMessageTermination` / `MaxMessageTermination` / `TokenUsageTermination` composed with `&` / `|`; handoff conditions `OnToolResult`, `OnTextMention`, `OnCondition`; `CallbackHandler`; memory `ConversationMemory`, `SemanticMemory(max_results=...)`, `MemoryStore`; code execution `CodeExecutionConfig` with `LocalCodeExecutor` / `DockerCodeExecutor` / `JupyterCodeExecutor` / `ServerlessCodeExecutor`, `CliConfig`; `PromptTemplate` instructions; `scatter_gather(name, worker, model, instructions, ...)`; `skill(path, model)` / `load_skills(...)`; `Schedule` + `deploy(..., schedules=[...])`; async twins `run_async` / `start_async` / `stream_async` / `deploy_async` / `resume_async`; `discover_agents(packages)`; credentials `get_secret` / `resolve_credentials`; errors `AgentNotFoundError`, `AgentAPIError`, `ConfigurationError`, `CredentialNotFoundError`.

## 6. Framework execution model

| Framework (SDK ids: `openai`, `google_adk`, `langgraph`, `langchain`, `vercel_ai`, `claude_agent_sdk`, `skill`) | Languages | Execution | `serve()` needed |
|---|---|---|---|
| Native `Agent` | Py · TS · Java · C# | **compiled** — LLM turns are server-side `LLM_CHAT_COMPLETE` | only for `worker` tools |
| OpenAI Agents SDK (+ Java/C# OpenAI-style builders) | Py · TS · Java · C# | compiled; handoffs → sub-agents, `WebSearchTool` → `webSearch`, `CodeInterpreterTool` → code execution, guardrails → custom | for `@function_tool` tools |
| Google ADK (`LlmAgent`, Sequential/Parallel/Loop agents) | Py · TS · Java · C# | compiled; sub_agents → strategies, callbacks preserved, model → `google_gemini/` | for function tools |
| Vercel AI SDK (AI-SDK ≤ 4 `tool()` objects in `Agent.tools`; AI-SDK 5+ → native `tool()` with `inputSchema`; or `generateText`/`streamText` drop-ins) | TS | compiled | for `execute` functions |
| LangGraph `create_react_agent` with an extractable chat model | Py · TS | compiled | for tools |
| LangGraph custom `StateGraph` | Py · TS | **passthrough** — whole loop runs inside the SDK worker; server sees one SIMPLE task | **always** |
| LangChain — `conductor.ai.agents.langchain.create_agent` (Py) / `createAgentExecutor` (TS) | Py · TS | compiled when the drop-in import is used; plain `langchain.agents.create_agent` is detected as LangGraph and may fall to passthrough | tools / always in passthrough |
| Claude Agent SDK (`Agent(model=ClaudeCode("sonnet"), tools=["Read","Glob","Grep"])`) | Py | **passthrough** | **always** |
| LangChain4j / LangGraph4j | Java | compiled | for `@Tool` objects |
| Semantic Kernel | C# | compiled (`[KernelFunction]` plugins run as local worker tools) | yes |

In compiled mode the provider key must be on the server; in passthrough mode the key is needed where `serve()` runs. `agentType` on the `AGENT` task is **always `conductor`** for any of these once deployed — never the framework id. Framework builders take no `max_turns`, `approval_required` or guardrail arguments: the compiled loop runs with the server default `maxTurns=100` (ADK `LoopAgent.max_iterations`, Vercel `maxSteps` and LangGraph `recursion_limit` are honored), so bound them from the caller (`maxDurationSeconds`, `run(timeout=)`, workflow timeout) or wrap a native `Agent` when you need turn caps or approval gates.

## 7. Human-in-the-loop contract

An agent pauses when it hits a `human_tool`, an `approval_required` tool, or a guardrail with `on_fail=HUMAN`. From a parent workflow the `AGENT` task then **completes** with:

```json
{"executionId": "...", "state": "input-required", "waiting": true,
 "pendingTool": {"taskRefName": "<agent>_approval_human__1", "tool_name": null, "parameters": null,
                 "toolCalls": [{"name": "notify_ops", "args": {"message": "..."}}],
                 "response_schema": {"type": "object", "required": ["approved"], "properties": {"approved": {"type": "boolean"}, "reason": {"type": "string"}}}}}
```

Verified live: for compiled agents `pendingTool.tool_name`/`parameters` are **always `null`** — read `toolCalls[]` (hosted agents, §9, do fill `tool_name`); `text` is absent while waiting; a `human_tool` question lives only in the child HUMAN task's `question` input (`conductor workflow get-execution <executionId>`, UI `/agentExecutions/{id}`).

Branch with a `value-param` SWITCH on `${ref.output.waiting}` (case `"true"`, `defaultCase: []`), then pick the answer channel by `pendingTool.response_schema`:

| Pause kind | How to tell | Answer with |
|---|---|---|
| Conversational question (`human_tool`) | `response_schema.properties.response`; `taskRefName` starts with `call_`; no `toolCalls` | second `AGENT` task with `executionId` + `prompt` (posts `{"result": prompt}`), `conductor agent respond <id> -m "text"`, or SDK `handle.respond({...})` |
| Tool approval (`approval_required`) | `response_schema.required` has `approved`; `taskRefName` ends `_approval_human__N`; `toolCalls[].name` = gated tools | `conductor agent respond <id> --approve|--deny --reason "..."`, `POST /api/agent/{id}/respond {"approved": true}`, SDK `approve()` / `reject(reason)`; in a workflow: [agent-approval-in-workflow.json](../examples/workflows/agent-approval-in-workflow.json) (HUMAN → `HTTP` respond → poll `/status`, verified) |
| Human guardrail review | `guardrail_fail` event, pending HUMAN | as tool approval |

**Approve ≠ resume (SKILL.md Rule 12):** the `AGENT`-resume path sends `{"result": "<prompt>"}`; at an approval gate the compiled agent runs an LLM normalizer (`<agent>_approval_human_normalizer`) over that text — a model judgment plus a model call — so use the explicit approve channel for gates and keep resume for answers. In a parent workflow the operator completes the HUMAN task (`conductor task update-execution --workflow-id <wf> --task-ref-name collect_answer_ref --status COMPLETED --output '{"answer":"..."}'`) and the resume `AGENT` task carries `prompt: "${collect_answer_ref.output.answer}"`.

SSE event types (`conductor agent stream <id>`, `GET /api/agent/stream/{id}`, `Last-Event-ID` reconnect): `thinking`, `tool_call`, `tool_result`, `handoff`, `waiting`, `guardrail_pass`, `guardrail_fail`, `error`, `done`, `context_condensed`, `subagent_start`, `subagent_stop`.

## 8. Operate

| Need | CLI | REST (`$CONDUCTOR_SERVER_URL` ends in `/api`) | UI (`BASE_URL` = server URL minus `/api`) |
|---|---|---|---|
| list / inspect definitions | `conductor agent list`, `agent get <name> [--version N]`, `agent delete <name>` | `GET /agent/list`, `GET|DELETE /agent/{name}?version=` | `/agents`, `/agents/{name}/{version}` |
| compile / dry run | `conductor agent compile <config.yaml|json>` | `POST /agent/compile` | — |
| deploy | SDK `runtime.deploy()`; config file → `python3 "$CONDUCTOR_API" agent-deploy-config --file <file>` | `POST /agent/deploy {"agentConfig": {...}}` → `{agentName, requiredWorkers[]}` | — |
| run ad hoc | `conductor agent run --name <n> "prompt"` (streams; `--no-stream`, `--session <id>`, or `--config <file>`) | `POST /agent/start` | `/runAgent` |
| find executions | `conductor agent execution [--name <n>] [--status RUNNING|COMPLETED|FAILED] [--since 1h] [--window now-7d] [--json]` | `GET /agent/executions?agentName&status&sessionId&classifier` | `/agentExecutions` |
| one execution | `conductor agent status <id>`; `conductor workflow get-execution <id> -c` (compiled tasks) | `GET /agent/{id}/status`, `/agent/executions/{id}`, `/agent/execution/{id}` (token usage) | `/agentExecutions/{id}` |
| live events | `conductor agent stream <id> [--last-event-id N]` | `GET /agent/stream/{id}` (SSE) | execution page |
| answer HITL | `conductor agent respond <id> --approve|--deny --reason "..."` or `-m "text"` | `POST /agent/{id}/respond` | execution page |
| inject context | — | `POST /agent/{id}/signal {"message": "..."}` | — |
| pause / resume | `conductor workflow pause|resume <id>` | `PUT /agent/{id}/pause`, `PUT /agent/{id}/resume` | — |
| retry / rerun / restart a failed run | `conductor workflow retry|rerun|restart <id>` | `POST /agent/executions/{id}/retry`, `/executions/{id}/rerun`, `/executions/{id}/restart`; bulk `PUT /agent/executions/bulk/pause|resume`, `POST .../bulk/restart|retry|terminate` | — |
| inspect tasks / plan | `conductor workflow get-execution <id> -c` | `GET /agent/executions/{id}/tasks`, `GET /agent/executions/search?query=`, `POST /agent/inspect-plan`, `GET /agent/definitions/{name}` (compiled WorkflowDef), `DELETE /agent/executions/{id}/record` (hard delete) | — |
| stop gracefully | — | `POST /agent/{id}/stop` | — |
| cancel | `conductor workflow terminate <id>`; `python3 "$CONDUCTOR_API" agent-cancel --id <id> --reason "..."` (no `conductor agent cancel`) | `DELETE /agent/{id}/cancel?reason=` | — |
| housekeeping | `conductor agent prune --older-than 30 [--archive] [--dry-run]` | `POST /agent/executions/prune` | — |
| secrets for agents | `conductor secret ...` (Orkes) | `GET /secrets`, `PUT /secrets/{key}` (501 when the store is env-backed/read-only), `GET /secrets/{key}/exists` | `/agentSecrets` |

Secrets: put **names** in `credentials=["NAME"]` (agent or tool) and values in the server store — `CONDUCTOR_SECRET_NAME` env var on the server (OSS default, `conductor.secrets.type=env`), `/api/secrets` when writable, or the Orkes secret manager. Workflow task input can reference `${workflow.secrets.NAME}` and `${workflow.secrets.NAME.sub_key}` (JSON secret) on OSS and Orkes alike. Never put a value in `instructions`, `prompt`, tool config or workflow input (rules D1 / F5).

## 9. Hosted platform agents (`agentType: microsoft-foundry | openai-assistants | bedrock`)

The agent stays on its platform; Conductor supplies durability, HITL and cancellation. Common inputs: `prompt` (required, validated at save), `credentials{}` with **values** via `${workflow.secrets.CRED.key}` (the secret must be a JSON object for sub-keys; flat value for `${workflow.secrets.KEY}`), `agentUrl` (endpoint + agent in one field, e.g. `bedrock://AGENTID/ALIASID?region=us-west-2`, `https://<res>.openai.azure.com/openai/assistants/asst_x`) or `rawConfig` (Foundry: `endpoint`, `assistantId`, `apiVersion`, `scope`, `surface: assistants|responses|inference`, `agentVersion`, `conversation`; OpenAI Assistants: `assistantId`, `baseUrl`; Bedrock: `agentId`, `agentAliasId`, `region`), `executionId` (resume), plus the poll knobs. Auth is chosen by which credential keys are present (Foundry: `apiKey` | `client_id`+`client_secret`+`tenant_id` | `managedIdentityClientId` | none → default chain; Bedrock: `apiKey` | `accessKeyId`+`secretAccessKey` | `roleArn` | none). `azure-foundry` is a deprecated alias of `microsoft-foundry`; there is **no** `vertex` runtime — call Vertex agents with `agentType: "a2a"`.

Function tools the platform cannot run come back as `pendingTools`. **`autoRunTools` is on by default**: the `AGENT` task stays `IN_PROGRESS`, schedules each call as a SIMPLE task named after the tool (inputs = the tool's arguments flattened + `_toolCallId`, `_toolName`, `_agentExecutionId`; tasks are `optional`), and resumes the agent with the results — so a worker registered for `get_revenue` serves the agent's `get_revenue` tool with no configuration. `maxToolTurns` (default 10) bounds the rounds; `toolTaskNames` remaps names; `autoRunTools: false` hands the calls back (`waiting: true` + `pendingTools`) for a manual resume with `toolResults` keyed by `tool_call_id`. Outputs add `pendingTools`, `executedTools` (platform-run built-ins), `toolDispatchId`. Bedrock has no status or cancel API (terminal on first call); Foundry runs expire 10 minutes after creation, total.

## 10. Schedule a deployed agent

The agent *is* a workflow named after it, so the ordinary scheduler applies ([schedules.md](schedules.md)): `conductor schedule create -n <agent>-<purpose> -c "0 0 2 * * ?" -w <agent> -i '{"prompt":"..."}' [-p]` (six-field Quartz cron). Pin `--version` for production callers. Something must be `serve()`-ing the agent's worker tools when it fires, or runs pile up unserved.

## 11. Test

| SDK | Offline (no server, no LLM) | Live |
|---|---|---|
| Python (`conductor.ai.agents.testing`) | `mock_run(agent, prompt, events=[MockEvent.tool_call("get_weather", {...}), MockEvent.done("...")], auto_execute_tools=True)` (also `MockEvent.thinking / tool_result / handoff / waiting / guardrail_pass / guardrail_fail / error / message`); `expect(result).completed().used_tool("get_weather").did_not_use_tool(...).no_errors().output_contains(...).handoff_to(...).max_turns(n)`; asserts `assert_tool_used / assert_tool_not_used / assert_tool_called_with / assert_tool_call_order / assert_tools_used_exactly / assert_output_contains / assert_output_matches / assert_output_type / assert_status / assert_no_errors / assert_max_turns / assert_events_contain / assert_event_sequence / assert_handoff_to / assert_agent_ran / assert_guardrail_passed / assert_guardrail_failed`; `validate_strategy` (raises `StrategyViolation`); `record()` / `replay()`; pytest fixtures `mock_agent_run`, `event` | `CorrectnessEval(runtime).run([EvalCase(name, agent, prompt, expect_tools=[...], expect_tools_not_used=[...], expect_handoff_to=..., expect_output_contains=[...], tags=[...])]).all_passed`; semantic `assert_output_satisfies(result, criterion=..., model=..., threshold=0.8)`; start workers with `runtime.serve(agent, blocking=False)` |
| TypeScript (`@io-orkes/conductor-javascript/agents/testing`) | `mockRun(agent, prompt, { mockTools })` executes every tool locally (wiring check, not routing); `expectResult(r).toBeCompleted().toHaveUsedTool("get_weather")`; `record`/`replay` | `CorrectnessEval`, `validateStrategy` |
| Java / C# | none shipped — unit-test tool classes directly and assert `runtime.plan(agent)` compiles with the expected `requiredWorkers` | e2e against a server |

Ladder: unit → trace assertions (mock/replay) → live correctness evals (nightly) → semantic evals → production monitoring (`conductor agent execution`, token usage on `/agent/execution/{id}`).

## 12. Gotchas (all verified against source)

- `AGENT` conductor branch takes **`name`**, not `agentName` (`agentName` is an output field / REST alias only). `prompt` is required on start **and** on resume.
- `agentType` is an execution mode: `conductor`, `a2a` (default when omitted), `microsoft-foundry`, `openai-assistants`, `bedrock`. A framework name is never valid. Omitting it with `name` yields `AGENT requires 'agentUrl'`.
- Read results at `${ref.output.text}` and `${ref.output.output.result}` (two `.output`s) — `output` is the compiled workflow's `outputParameters` map.
- `model` must be `provider/model`. `CONDUCTOR_AGENT_LLM_MODEL` is read only by the Python OpenAI-compat `Runner` and SDK examples — not SDK configuration.
- Cancellation surfaces as task status `CANCELED` and `state: canceled` (not FAILED). Parent `TERMINATE` propagates to the child in the embedded runtime.
- `deploy()` registers only; `run()` is not a deployment; `requiredWorkers` non-empty or passthrough → `serve()` must run.
- `conductor deploy` (CLI) shells to a module that does not ship with `conductor-python` — use SDK `deploy()`. There is no `conductor agent cancel|stop|deploy`.
- Java artifact is `org.conductoross:conductor-client-ai` (not `conductor-ai`). C# `conductor-ai*` packages are a preview (project reference). TS SDK 4.x reads `CONDUCTOR_SERVER_URL` / `CONDUCTOR_AUTH_*`; C# per its README.
- Python LangChain: take `create_agent` from `conductor.ai.agents.langchain`, not `langchain.agents`.
- TS Vercel AI: the SDK auto-detects AI-SDK **≤ 4** tools (`parameters` + `execute`, named from the description); AI-SDK **5+** `inputSchema` tools are not detected — use the native `tool(execute, {name, description, inputSchema})` with the same Zod schema.
- `/api/skills/**` needs `agentspan.skills.enabled=true`; `/api/a2a/**` needs `conductor.a2a.server.enabled=true` (+ `agentspan.embedded=true`) — off unless set.
- `conductor workflow create` drops workflow `metadata`; register A2A-exposed workflows (`metadata.a2a.enabled`) via `POST /api/metadata/workflow?overwrite=true`. The workflow facade delivers the message as input `_a2a_text` (+ `_a2a_message_id`, `_a2a_context_id`, merged `data` parts) and returns the workflow output as a `data` artifact; deployed agents are called at `/api/a2a/agent/<name>` (they need `prompt`, which the workflow facade never sets).
- a2a `pushNotification: true` silently falls back to polling when `conductor.a2a.callback.url` is unset.
- `${workflow.secrets.X}` is not resolved for task input externalized to payload storage (large inputs).
- Python `serve()` / `run()` start worker processes with the `spawn` start method on macOS and Windows: call them under `if __name__ == "__main__":` (a bare module-level call re-imports the script in every child and fails with `An attempt has been made to start a new process before the current process has finished its bootstrapping phase`).
- Don't name your package directory `agents/` without an `__init__.py` — the OpenAI Agents SDK package is also called `agents`, and a namespace directory loses to it on import.
