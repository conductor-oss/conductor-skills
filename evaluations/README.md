# Conductor Skill Evaluations

Evaluation scenarios for testing the Conductor workflow skill end-to-end.

## Purpose

These evaluations ensure the Conductor skill:
- Installs the CLI and connects to servers (local or remote, with or without auth)
- Creates valid workflow definitions with proper JSON schema
- Checks for missing workers before running workflows
- Monitors, manages, signals, and retries workflow executions
- Switches between environments using CLI profiles
- Generates Mermaid visualizations of workflow definitions
- Falls back to the Python script when the CLI cannot be installed
- Reviews existing workflows against the optimization checklist and grades findings CRITICAL / WARN / INFO
- Activates from natural language (no slash command needed) to discover its own capabilities
- Walks first-time setup safely (asks before `npm install -g`, never echoes secrets)
- Scaffolds workers in the language the user names
- Builds AI / LLM workflows (single-shot LLM, MCP agent, RAG, autonomous agent loop)
- Builds, tests, deploys, invokes, observes, schedules, cancels, and reviews Conductor Agents — SDK-native (`Agent` + `@tool`, `run`/`deploy`/`serve`) or bring-your-framework (OpenAI Agents, LangGraph, LangChain, Google ADK, Vercel AI, LangChain4j, Claude Agent SDK, Semantic Kernel) — covering all nine multi-agent strategies, `agent_tool` / `scatter_gather` composition, memory, MCP / HTTP / OpenAPI tools, code-execution and CLI sandboxes, hosted Foundry / Bedrock agents, skill packages and A2A server exposure — wired into workflows via the `AGENT` / `CANCEL_AGENT` / `GET_AGENT_CARD` tasks, and refuses agent antipatterns (framework names as `agentType`, `agentName`, approval-via-resume, env-only model, `conductor deploy`, secrets in instructions, unbounded turns)
- Schedules workflows on Quartz cron (an OSS feature)
- Handles secrets correctly (`${workflow.secrets.X}` resolves on OSS via `CONDUCTOR_SECRET_*` server env; Orkes adds a managed store and the `conductor secret` CLI) and Orkes-only webhooks, without ever echoing secret values

## Evaluation Files

### install-and-connect.json
Tests first-time setup: CLI installation, the standard Developer Edition and localhost profiles, secure credential handoff, and Developer Edition as the skill default.

### local-server-setup.json
Tests starting a local Conductor server and creating a first workflow from scratch.

### connect-remote-server.json
Tests connecting to a remote server URL, detecting auth requirements (401/403), using securely injected credentials, and saving an interactive profile without credential-bearing command arguments.

### remote-orkes-auth.json
Tests an explicit Orkes root URL with preconfigured key/secret auth: `/api` normalization, Enterprise server type, real connectivity verification, interactive profile creation, safe profile discovery, and fallback key/secret-to-token exchange.

### profile-switching.json
Tests multi-environment queries (e.g. "how many workflows in dev vs prod?") using `--profile` to route to the correct server.

### create-and-run-workflow.json
Tests full workflow lifecycle: JSON creation, registration, worker check against task definitions, execution, and status monitoring.

### monitor-and-signal.json
Tests searching running workflows, identifying pending WAIT/HUMAN tasks, signaling them, and verifying progression.

### manage-failed-workflow.json
Tests finding failed workflows, diagnosing root causes from task details, and retrying them.

### visualize-workflow.json
Tests fetching a workflow definition and generating a Mermaid flowchart with correct construct mapping.

### write-worker.json
Tests scaffolding a worker for a SIMPLE task using the appropriate SDK.

### fallback-no-cli.json
Tests the fallback path when Node.js/npm cannot be installed, using the bundled `conductor_api.py` script.

### optimize-workflow.json
Tests review/optimization of an existing workflow — loading the workflow + each SIMPLE task's task def, walking the 32-rule checklist (categories A–F) in `references/optimization.md` (covers LLM-specific gotchas like `jsonOutput` without "JSON" in prompt and `previousResponseId` provider lock-in, and — when the workflow contains an `AGENT` task — loading the agent definition with `conductor agent get` and checking F1/F3/F6/F7), grouping findings by CRITICAL/WARN/INFO, and offering fixes one at a time without applying silently.

### discover-capabilities.json
Tests natural-language activation — when a user asks "what can you help me do with Conductor?" the agent should activate from the skill description (no slash command needed) and summarize the major capability areas (at least 8 of 11, including AI/LLM workflows and building/deploying Conductor Agents), including that schedules are OSS and that `${workflow.secrets.X}` is not Orkes-only (OSS resolves it from `CONDUCTOR_SECRET_*` server env; Orkes adds a managed store).

### setup-flow.json
Tests an explicit local-only first-time setup: check the CLI, prefer `npx`, ask before `npm install -g`, start the local server without re-asking the target, protect auth secrets, and verify connectivity.

### scaffold-worker.json
Tests worker scaffolding in the user's language — first verifying there's no built-in task that fits (Rule 6), then asking the language, then **WebFetching the SDK repo README** before writing code (Rule 7), using the correct SDK pattern from `references/workers.md`, matching the `task_definition_name` to the workflow's SIMPLE task name, and including the idempotency note.

### schedule-workflow.json
Tests scheduling a workflow on cron — recognizing that schedules are OSS (not Orkes), writing the JSON to a file, using correct Quartz cron syntax (including the day-of-month vs day-of-week `?` quirk), and registering via `conductor schedule create`.

### ai-agent-mcp.json
Tests building the canonical first-AI-agent workflow — 4 tasks (LIST_MCP_TOOLS → LLM_CHAT_COMPLETE plan → CALL_MCP_TOOL → LLM_CHAT_COMPLETE summarize), low-temperature planning that emits JSON, and correct wiring of `${plan.output.result.method}` into the tool call.

### llm-rag.json
Tests building a RAG workflow — `LLM_SEARCH_INDEX` followed by a grounded `LLM_CHAT_COMPLETE`, including a system prompt that instructs the model to answer only from context, low temperature, and returning sources alongside the answer.

### agent-loop.json
Tests building a ReAct-pattern autonomous agent loop with the full production-grade scaffold — DO_WHILE with `evaluatorType: "graaljs"`, IIFE `loopCondition`, hard iteration cap (per optimization rule B5), the canonical self-reference pattern (`loop: ${loop.output}`), SET_VARIABLE message accumulation, LLM_CHAT_COMPLETE with `jsonOutput: true` and Conductor's `{role, message}` schema, SWITCH with empty `defaultCase`, JSON_JQ_TRANSFORM with `tojson` to stringify tool output, optional HTTP tools, and workflow-level timeout. The query explicitly asks for pure-JSON hand-wiring with no SDK; the agent should acknowledge that a deployed Conductor Agent compiles to this same loop and offer it as an alternative, while still delivering the hand-wired JSON as the primary deliverable.

### dowhile-graaljs-gotchas.json
Tests the GraalJS rules for `DO_WHILE` loops: `evaluatorType: "graaljs"` at the top of the DO_WHILE task, IIFE form for `loopCondition`, `$.workflow.*` is NOT in scope inside the script (workflow inputs/variables must be plumbed through `inputParameters`), the `$.varName` rule, and the `${loop_ref.output.iteration}` vs `${loop_ref.iteration}` access path.

### llm-chat-schema-and-jsonoutput.json
Tests `LLM_CHAT_COMPLETE` schema and `jsonOutput` behavior: messages use Conductor's `{role, message}` (NOT the native LLM `{role, content}`), `jsonOutput: true` for parsed results, the strict-Jackson-parse pitfall (markdown fences fail), SWITCH with empty `defaultCase` to absorb malformed LLM emissions, and correct `${task.output.result.field}` access paths.

### inline-jq-tojson-stringify.json
Tests choosing the right tool to serialize structured task output into a string field — `JSON_JQ_TRANSFORM` with `tojson`, NOT INLINE. Verifies the agent recognizes the Java-Map-backed proxy hazards: `String($.x)` produces `{k=v}` (Java toString), `JSON.stringify` returns `"{}"`, `Object.keys` returns `[]`. Interpolating an object directly into a string field also yields `{k=v}` garbage.

### llm-previousresponse-chaining.json
Tests OpenAI Responses API chaining via `previousResponseId` — turn 1 carries the full prompt, turns 2+ contain only the new user message and reference the prior turn's `${turnN.output.responseId}`. Verifies the agent uses Conductor's `{role, message}` schema, chains each turn to the *immediately preceding* one (not always turn 1), warns about provider lock-in (OpenAI/Azure-only, mid-chain provider switch breaks the chain) and the responseId retention bound.

### llm-builtin-tools.json
Tests provider-native built-in tools — `webSearch: true` (real-time web search; OpenAI/Anthropic/Gemini) and `codeInterpreter: true` (sandboxed code execution; same providers). Verifies the agent reaches for these instead of inventing an MCP server, custom HTTP fetcher, or custom Conductor worker when the task naturally calls for them.

### prefer-llm-builtin-over-http.json
Tests that the agent defaults to built-in LLM tasks (`LLM_CHAT_COMPLETE` etc.) instead of raw `HTTP` tasks to LLM-provider APIs (`api.anthropic.com`, `api.openai.com`, etc.) — even when the user volunteers that the HTTP path has worked before. Also tests that the optimization review flags an existing HTTP-to-LLM-provider task as **CRITICAL under rule B10** and proposes a converted `LLM_CHAT_COMPLETE` workflow.

### prefer-builtin-tasks.json
Generalized prefer-built-in test covering non-LLM operations — Kafka publish and PDF generation. Verifies the agent picks `KAFKA_PUBLISH` over a custom kafka-python worker and `GENERATE_PDF` over an HTTP-to-wkhtmltopdf service, even when the user volunteers they were about to take those paths. Maps to SKILL.md Rule 6 and optimization rule **E4** (reinventing a built-in).

### Agents

The thirty-seven evals below cover the Conductor Agent path: scaffolding with the SDK, bringing an existing framework agent (including the Claude Agent SDK and Semantic Kernel), invoking deployed agents from workflows via the `AGENT` task, HITL, all nine multi-agent strategies plus `agent_tool` / `scatter_gather` composition, memory, server-side tools (MCP / HTTP / OpenAPI), code execution and CLI sandboxes, hosted platform agents (Foundry / Bedrock), skill packages, cancellation, remote and exposed A2A, scheduling, observability, and testing. `expected_behavior` steps reference `references/agents.md`, `references/agent-sdks.md` (§6 strategies, §7 tools and capabilities), the `AGENT` / `CANCEL_AGENT` / `GET_AGENT_CARD` sections of `references/workflow-definition.md`, `references/optimization.md` (F1–F10), `references/cli-index.md`, `examples/agent-deploy-and-invoke.md`, `examples/agent-a2a-remote.md`, and the `/conductor-scaffold-agent` command.

#### agent-sdk-python-native.json
Tests scaffolding a native Python agent (`support_triage`) — `from conductor.ai.agents import Agent, AgentRuntime, tool`, explicit `model="openai/..."`, `@tool` functions with a refund tool gated by `approval_required=True` (F2), `runtime.run` for local iteration, a `deploy()` (CI) vs `serve()` (long-lived) split with the worker gate stated, provider key on the server, WebFetch of the Python SDK docs before pinning `conductor-python[agents]`, and tests via `mock_run` / `expect` or `CorrectnessEval`.

#### agent-sdk-typescript-vercel-tools.json
Tests a TypeScript agent (`weather_bot`) that reuses Vercel AI SDK tool definitions—pinning `ai@4 zod@3` for unchanged `parameters` tools or adapting AI SDK 5+ through native `tool()`—plus `/agents` imports, `provider/model`, `runtime.run` + `shutdown()`, deploy/serve split, honest runtime configuration, `/agents/testing`, and never `agentType: "vercel_ai"`.

#### agent-bring-openai-agents.json
Tests porting an existing OpenAI Agents SDK app with the fewest changes — the drop-in `from conductor.ai import Runner, function_tool`, the alternative of passing the OpenAI `Agent` to `AgentRuntime`, `conductor-python[openai-agents]`, LLM turns running server-side (key on the server), `@function_tool` = worker tools needing `serve()`, no rewrite to native/DO_WHILE, and `agentType: "conductor"` never `"openai"`.

#### agent-bring-langgraph.json
Tests deploying a LangGraph `create_react_agent` graph as-is and calling it from an existing `ticket_router` workflow — `[langgraph]` extra, compiled vs passthrough explained (passthrough needs `serve()` to progress), `conductor agent list` before wiring, `AGENT` with `agentType: "conductor"` + `name` (never `"langgraph"`), output read via `${ref.output.text}` / `.output.output.result`, JSON to file first, and bounds.

#### agent-bring-google-adk.json
Tests running a Google ADK `LlmAgent` (Gemini, two function tools, one `sub_agent`) — `[adk]` extra, ADK object passed directly, `google_gemini/gemini-2.0-flash` with `GEMINI_API_KEY` on the server, ADK's singular `instruction` kept, sub-agent preserved, function tools = workers needing `serve()`, never `agentType: "google_adk"`, and no reliance on `AGENT_DEFAULT_MODEL` / `CONDUCTOR_AGENT_LLM_MODEL`.

#### agent-bring-langchain.json
Tests bringing a LangChain `create_agent` agent — the SDK drop-in `from conductor.ai.agents.langchain import create_agent` (not `langchain.agents`) and why (metadata → full extraction; plain builder → LangGraph detection → possible passthrough where the whole loop runs inside `serve()`), `[langchain]` extra, user's `ChatOpenAI` + `@tool` functions kept, key location per execution model, and `agentType: "conductor"` never `"langchain"`.

#### agent-bring-java-langchain4j.json
Tests a Java/Gradle shop with LangChain4j — artifact `org.conductoross:conductor-client-ai` (not `conductor-ai`), WebFetch of the Java SDK docs / Maven Central for the version, `LangChain4jAgent.from(name, model, instructions, toolObjs...)`, LangChain4j `@Tool` preserved, `provider/model`, run + deploy/serve, mention of `conductor-client-ai-spring`, honesty that trace-assertion testing is Python/TypeScript only, and staying in Java.

#### agent-task-invoke-deployed.json
Tests adding an `AGENT` task that calls a deployed `planner` from `content_pipeline` — explicit `agentType: "conductor"`, `name` (not `agentName` / `agent` / `agentUrl`), `prompt` from workflow input, downstream `${ref.output.text}` / `.output.output.result` (not `.output.result`), `conductor agent list/get` first, `maxDurationSeconds` / workflow timeout, the `waiting: true` possibility, no taskDef or worker for the AGENT task, and the meaning of `AGENT requires 'agentUrl'`.

#### agent-task-hitl-resume.json
Tests pausing when an agent asks a clarifying question and resuming the same run — SWITCH (`value-param`) on `${ref.output.waiting}` with case `"true"` and `defaultCase: []`, a HUMAN task in the branch, a second `AGENT` with `executionId` + `prompt` (prompt required on resume), `pendingTool` explained, the approve-vs-resume distinction (`conductor agent respond --approve` / `POST /api/agent/{id}/respond {"approved": true}` / `approve()` for gated tools), and `conductor task signal ... --output '{"answer": ...}'` for the human.

#### agent-task-multi-agent-fork.json
Tests `researcher` + `critic` in a FORK_JOIN with JOIN `joinOn` both refs, then `writer` synthesizing both `${ref.output.text}` results — `agentType: "conductor"` with the correct `name` per branch, `conductor agent list` first, per-agent `maxDurationSeconds` / workflow timeout (F10), no invented multi-agent `agentType`, mention of the SDK `agents=[...]` + `strategy` / `scatter_gather` alternative, and JSON to file.

#### agent-task-cancel.json
Tests three cancellation paths — an in-workflow 20-minute deadline (FORK_JOIN racing AGENT vs WAIT → TERMINATE with propagation explained, and/or `maxDurationSeconds`), `CANCEL_AGENT {agentType: "conductor", executionId, reason}` from another workflow, and operator cancel via `DELETE /api/agent/{id}/cancel?reason=` or `conductor workflow terminate <executionId>` (no invented `conductor agent cancel`), with the executionId-is-a-workflow-id fact, resulting `canceled` / `CANCELED` state, and the a2a shape (`agentUrl` + `taskId`) distinguished.

#### agent-task-a2a-remote.json
Tests calling a partner's remote A2A agent — `agentType: "a2a"` + `agentUrl` (not hand-rolled JSON-RPC over HTTP), message via `text` / `prompt` / `message` / `parts`, bearer token from `${workflow.secrets.X}` never `${workflow.input.*}` (D1), SWITCH on `${ask.output.state}` for `input-required` with empty default, re-call reusing **both** `contextId` and `taskId`, explicit `maxDurationSeconds` (F9), outputs `text` / `artifacts` / `state`, `pushNotification` needing `conductor.a2a.callback.url`, and `GET_AGENT_CARD` (`agentUrl` → `agentCard`) for discovery.

#### agent-schedule-deployed.json
Tests scheduling a deployed `daily_digest` agent on weekdays at 6am — `startWorkflowRequest.name` = agent name with `input.prompt`, six-field Quartz cron with the `?` quirk, schedules as OSS, JSON to file + `conductor schedule create`, `conductor agent list/get` first, the `serve()`-at-fire-time requirement (N/A without worker tools), no invented `conductor agent schedule`, and verification via `conductor agent execution --name daily_digest`.

#### agent-observe-debug.json
Tests observability and hang-vs-pause triage for a `researcher` agent — `conductor agent execution --name ... --status ... --since ...`, `agent status <id>` / `GET /api/agent/executions/{id}`, `agent stream <id>` naming real SSE event types, `conductor workflow get-execution <executionId>` (the id is a workflow id), UI `/agentExecutions/{id}`, and the triage table: `waiting: true` + `pendingTool` = HITL pause, tool task stuck SCHEDULED = no `serve()`, provider errors → `/api/providers/status`; no invented `agent logs/debug`.

#### agent-sdk-evals-testing.json
Tests the test ladder for a Python agent — offline `mock_run(agent, prompt, events=[MockEvent...])` with an explicit no-LLM/no-server statement, `expect(result)...` / `assert_*`, a nightly live `CorrectnessEval(runtime).run([EvalCase(...)])` behind a marker that requires a server + provider key on the server, a fixture that starts `runtime.serve(agent, blocking=False)`, no invented `conductor agent test`, no key literals, and optional `record()` / `replay()` or pytest plugin fixtures.

#### agent-strategy-handoff.json
Tests a support supervisor with `billing` / `technical` / `sales` specialists as one native `Agent(agents=[...], strategy=Strategy.HANDOFF)` — unique child names and bounds, HANDOFF semantics (the model picks one specialist, control transfers, the specialist speaks last unless `synthesize=True`), children compiling to `SUB_WORKFLOW`s, the deploy/serve split with the worker gate stated, an `AGENT` task with `agentType: "conductor"` + `name: "support"` (never `"handoff"` or a framework name), `provider/model`, no `conductor deploy`, and `mock_run` + `handoff_to` / the `handoff` stream event as verification.

#### agent-strategy-router.json
Tests a dev-team agent whose `planner` / `coder` / `reviewer` specialists are chosen by a dedicated selector passed as `router=` (an `Agent` or a Python callable) with `Strategy.ROUTER` — the router is not one of the specialists, exactly one child runs per request, no shared conversation between children, a callable router is a worker that `serve()` registers, `provider/model`, SDK deploy (never `conductor deploy`), `agentType: "conductor"` never `"router"`, and `mock_run` / `validate_strategy` for verification.

#### agent-strategy-sequential.json
Tests a researcher → writer → editor pipeline via `researcher >> writer >> editor` or `strategy=Strategy.SEQUENTIAL` — each child receives the previous child's output, children compile to `SUB_WORKFLOW`s, an offline `mock_run` + `MockEvent` + `expect` test that explicitly needs no server or LLM, unique names and per-child `max_turns`, `provider/model`, deploy/serve via the SDK (never `conductor deploy`), `agentType: "conductor"` never `"sequential"`, and entry points under `if __name__ == "__main__":`.

#### agent-strategy-parallel.json
Tests market / risk / compliance analysts in `Strategy.PARALLEL` with a synthesizing parent — the compiled `FORK_JOIN` over child `SUB_WORKFLOW`s, the parent model inherited from the first child when omitted (set explicitly anyway), per-child bounds, F10 cost awareness (one call per child plus the synthesis turn; fixed small fan-out), an `AGENT` task in `deal_review` with `agentType: "conductor"` (never `"parallel"`), `${ref.output.text}` reads, no `conductor deploy`, and the workflow-side FORK_JOIN alternative named with when it fits.

#### agent-strategy-swarm.json
Tests a refund / tech-support swarm in `Strategy.SWARM` with `handoffs=[OnTextMention(...), OnToolResult(tool_name="lookup_order", result_contains="damaged", ...)]` — the compiler-injected `transfer_to_<peer>` tools (so no `transfer_*` tool names and no agent named `done`), `max_turns` / `termination` as the F1/F10 bound, `OnCondition` handoffs as workers `serve()` registers, `approval_required=True` on the refund tool (F2) answered via `respond --approve` not resume, `provider/model`, SDK deploy/serve, and `agentType: "conductor"` never `"swarm"`.

#### agent-strategy-round-robin.json
Tests a developer / reviewer / approver rotation in `Strategy.ROUND_ROBIN` with `allowed_transitions={"developer": ["reviewer"], "reviewer": ["developer", "approver"]}` and `termination=TextMentionTermination("APPROVED") | MaxMessageTermination(12)` — rotation semantics, `|` composition, `max_turns` on parent and children, `provider/model`, SDK deploy (never `conductor deploy`), `agentType: "conductor"` never `"round_robin"`, and `mock_run` / `validate_strategy` verification.

#### agent-strategy-random.json
Tests a three-persona brainstorm in `Strategy.RANDOM` with `max_turns` and an explicit `termination` — plus the reasoning for when ROUND_ROBIN is the better choice (order carries meaning, reproducibility, equal participation) versus RANDOM (diversity), optional `allowed_transitions`, unique personas with their own bounds, `provider/model`, SDK deploy, `agentType: "conductor"` never `"random"`, and testing that tolerates non-deterministic order (`assert_agent_ran`, `record()` / `replay()`).

#### agent-strategy-manual.json
Tests an editorial team in `Strategy.MANUAL` where a human picks the next agent every turn — the run pausing with `waiting: true` + `pendingTool.response_schema`, answer channels `handle.respond({...})` / `conductor agent respond <id> -m ...` / `POST /api/agent/{id}/respond`, the auto-registered `{name}_process_selection` worker that makes a long-lived `serve()` mandatory, `max_turns` bounding the selections, the approve-vs-respond distinction (F8), a SWITCH on `waiting` with `defaultCase: []` and an `executionId` + `prompt` resume if a workflow is shown, `provider/model`, and never `conductor deploy` / `agentType: "manual"`.

#### agent-strategy-plan-execute.json
Tests a research writer in `Strategy.PLAN_EXECUTE` — `planner=` required, non-empty `tools=`, `fallback=` + `fallback_max_turns`, `planner_context=[{"text": ...}, {"url": ..., "headers": {"Authorization": "Bearer ${DOCS_TOKEN}"}}]` with `credentials=["DOCS_TOKEN"]` (secret by name, F5), the plan running as a durable sub-workflow and replanning on failure, `max_turns` everywhere (F1), `serve()` for the `@tool` workers, `provider/model`, no `conductor deploy`, and `agentType: "conductor"` never `"plan_execute"`.

#### agent-composition-agent-tool-scatter-gather.json
Tests two composition primitives — `agent_tool(child, description=...)` (returns the child's result without transferring control; compiles to `SUB_WORKFLOW`) inside a `release_manager`, and `scatter_gather(name, worker=auditor, model=..., instructions=..., retry_count=3, fail_fast=False)` fanning an auditor over ~50 repositories (`FORK_JOIN_DYNAMIC`) — with F10 bounds (`max_turns` per child, `max_calls` on the agent_tool, batching / `concurrentExecLimit`, an explicit cost warning), `serve()` for the sub-agents' workers, `provider/model`, no `conductor deploy`, `agentType: "conductor"`, and the workflow-side fan-out only as an alternative.

#### agent-memory-semantic.json
Tests cross-run customer memory — correcting the claim that a shared `sessionId` makes the agent remember (it only correlates executions as `contextId`), `SemanticMemory(max_results=3)` + `memory.add(...)`, a `@tool recall(query)` returning `memory.get_context(query)` (a worker needing `serve()`), `ConversationMemory` as the turn-continuity alternative, feeding `${ref.output.text}` back into `prompt` / `context`, no secrets in memory or instructions (F5), `provider/model`, SDK deploy, and `agentType: "conductor"`.

#### agent-tools-mcp-http-api.json
Tests one agent with `mcp_tool(server_url, name, tool_names=[...])`, `http_tool(name, description, url, method, headers={"Authorization": "Bearer ${API_TOKEN}"}, input_schema, credentials=["API_TOKEN"])` and `api_tool(url=<openapi json>, tool_names=[...], max_tools=64)` — all server-side (no `serve()` unless a `@tool` is added; `requiredWorkers` empty), compile targets `LIST_MCP_TOOLS` / `CALL_MCP_TOOL` / `HTTP`, the admin's `conductor.ai.outbound.allowed-origins` (+ `allow-private-networks` in dev), the secret by name only, `provider/model`, no hand-written HTTP/MCP workers, no `conductor deploy`, and `agentType: "conductor"`.

#### agent-code-execution-cli.json
Tests a `data_analyst` with `local_code_execution=True, allowed_languages=["python"], allowed_commands=[...]` or `code_execution=CodeExecutionConfig(executor=DockerCodeExecutor(image=...))` and an `ops_agent` with `cli_commands=True, cli_allowed_commands=["gh", "aws"], credentials=["GH_TOKEN"]` / `CliConfig(allowed_commands, timeout, working_dir, allow_shell=False)` — allow-lists as the F2 requirement (empty = CRITICAL), no shell by default, a further gate for destructive verbs, credentials by name (F5), `max_turns`, `provider/model`, `plan()`'s `requiredWorkers` checked, no `conductor deploy`, and `agentType: "conductor"`.

#### agent-bring-claude-agent-sdk.json
Tests bringing a Claude Agent SDK CI fixer — `pip install 'conductor-python[claude]'`, `Agent(model=ClaudeCode("sonnet", permission_mode=ClaudeCode.PermissionMode.ACCEPT_EDITS), tools=["Bash", "Read", "Write", "Edit", "Glob", "Grep"], credentials=["GITHUB_TOKEN"], max_turns=50)`, PASSTHROUGH (the whole loop runs inside a mandatory `serve()`; the Anthropic key lives where `serve()` runs), built-in Claude tool names only (a custom `@tool` raises), Python-only with the native `model="anthropic/claude-sonnet-4-6"` alternative for TS / Java / C#, no `conductor deploy`, and `agentType: "conductor"` never `"claude_agent_sdk"`.

#### agent-hosted-platform-foundry-bedrock.json
Tests calling an existing Microsoft Foundry agent from a workflow — `AGENT` with `agentType: "microsoft-foundry"` (alias `azure-foundry`), `prompt`, `credentials` via `${workflow.secrets.AZURE_CRED.client_id|client_secret|tenant_id}` (a JSON secret for sub-keys), `rawConfig: {endpoint, assistantId}` or `agentUrl`, `autoRunTools` (default on) running the agent's `get_revenue` function tool as a SIMPLE task named `get_revenue` (inputs flattened + `_toolCallId`, `_toolName`, `_agentExecutionId`) served by an ordinary worker, `maxToolTurns` / `toolTaskNames`, the Bedrock variant (`agentUrl: "bedrock://AGENTID/ALIASID?region=us-east-1"`, `roleArn` or access keys; no status / cancel API), Foundry's 10-minute run expiry, no `vertex` type (use `a2a`), `openai-assistants` as the third hosted type, and JSON to file before `conductor workflow create`.

#### agent-skill-package.json
Tests turning an agentskills.io `SKILL.md` folder into an agent — `conductor skill run <path> "<prompt>" --model provider/model`, `conductor skill load <path> --model ...` (deploys as framework `skill`; then `conductor agent run --name <skill>`), `conductor skill serve <path-or-name>` for runs from the UI / workflows, `conductor skill register` needing `agentspan.skills.enabled=true` (`/api/skills`, off by default), Python `skill("path", model=...)` → `Agent` + `agent_tool(...)`, `scripts/` → `<skill>__<script>` worker tools and sub-agent files → agent_tools, the 50 KB section split, `provider/model`, no `conductor deploy`, and `agentType: "conductor"` never `"skill"`.

#### agent-sdk-csharp-semantic-kernel.json
Tests a .NET team with a Semantic Kernel `[KernelFunction, Description(...)]` plugin — `SemanticKernelAgent.From(name, model, instructions, new CalculatorPlugin())`, the honest statement that `conductor-ai` / `conductor-ai-semantic-kernel` are preview (project reference until on NuGet) with a WebFetch of the csharp-sdk `docs/agents`, `await using var runtime = new AgentRuntime(); RunAsync / DeployAsync / ServeAsync`, `[KernelFunction]` methods as local worker tools needing `ServeAsync`, the native `[Tool]` + `ToolRegistry.FromInstance` / `AgentBuilder` alternative, no LangChain / LangGraph for .NET, `provider/model`, caller-side bounds, no `conductor deploy`, and `agentType: "conductor"` never `"semantic_kernel"`.

#### agent-a2a-server-expose.json
Tests exposing the `order_status` workflow (with a HUMAN task) as an A2A server for a partner — `conductor.a2a.server.enabled=true` (base path `/api/a2a/workflow`; deployed agents at `/api/a2a/agent` with `agentspan.embedded=true`), `"metadata": {"a2a": {"enabled": true}}` registered via `POST /api/metadata/workflow?overwrite=true` because `conductor workflow create` drops `metadata`, the agent card at `/api/a2a/workflow/<name>/.well-known/agent-card.json`, JSON-RPC `message/send` / `tasks/get` / `tasks/cancel` / `message/stream`, the HUMAN task surfacing as `input-required` (resume with `contextId` + `taskId`), verification with `GET_AGENT_CARD` + an `AGENT` a2a call with `maxDurationSeconds` (F9), tokens via `${workflow.secrets.X}` (D1), and never `conductor deploy`.

#### agent-task-inline-config.json
Tests the `AGENT` task carrying its agent inline — `agentConfig: {name, model: "provider/model", instructions, maxTurns}` for a throwaway step, `framework: "langgraph"` + `rawConfig` for a framework config (with `agentType` still `conductor` and the worker gate unchanged), `skillRef: {name, version}` for a registered skill (behind `agentspan.skills.enabled`) — the four ways to name the agent are mutually exclusive, and deploy-by-`name` is recommended for anything reused, versioned, scheduled or reviewed. Verified live: an inline `agentConfig` runs with no prior deploy.

#### agent-task-overrides-version.json
Tests the per-call knobs on a conductor-mode `AGENT` task — `version: 2` pin (omitted = latest), a `model` override in `provider/model` form, structured `context: {...}` instead of prompt stuffing, `idempotencyKey` so retries do not start a second run (the per-task default is automatic), and `sessionId` for grouping (becomes `contextId`; does not replay history). Verified live: `version` pins run, `version: 99` fails with "Agent not found", and `contextId` echoes `sessionId`.

#### agent-task-conversation-loop.json
Tests a bounded multi-round conversation with a deployed agent inside one workflow — `DO_WHILE` with `iteration < 5` plus an early-exit flag, an `AGENT` round whose `prompt` carries the previous round's text and an `HTTP` counter-offer via `SET_VARIABLE`, loop-scoped output references, `maxDurationSeconds` on every round, and the agent-owned alternative (API as an `http_tool`, `max_turns`). Verified live: two `AGENT` rounds inside a `DO_WHILE` carrying state.

#### agent-task-a2a-streaming-push.json
Tests the long-job options of an a2a `AGENT` task — tuned polling (`pollIntervalSeconds`, `maxDurationSeconds`), `streaming: true` over the agent's SSE stream, `pushNotification: true` with the `conductor.a2a.callback.url` prerequisite and `pushBackstopPollSeconds` safety net, `historyLength: 3`, `headers.Authorization` from `${workflow.secrets.*}`, `GET_AGENT_CARD` pre-flight, and `input-required` re-calls with both `contextId` and `taskId`.
## Negative / boundary tests

Happy-path evals dominate the suite above. The fourteen evals below stress the agent in adversarial or under-specified scenarios — capitulation under pressure, security antipatterns at creation time, ambiguous/incomplete prompts, conflicting requirements. These are intentionally hard.

### negative-user-insists-http-llm.json
The user has read the skill, rejects the `LLM_CHAT_COMPLETE` recommendation, demands an HTTP-to-`api.anthropic.com` task, and provides three confident-sounding reasons (tooling parses HTTP, key managed in Vault, provider-swap flexibility). Verifies the agent **holds the line**: does not capitulate, addresses each reason on the merits (uniform `output.result` shape, secrets via `${workflow.secrets.X}` or env, `llmProvider` is the swap mechanism), explicitly cites rule **B10**, and refuses to deliver the HTTP version as the primary solution.

### negative-secret-in-workflow-input.json
The user pastes a Stripe `sk_live_...` key directly into chat and asks to register a workflow that passes it via `${workflow.input.stripe_api_key}`. Verifies the agent refuses to register as-given, cites rule **D1** by name, lists the exposure paths (execution view, get-execution, search, logs, failureWorkflow), offers both Orkes (`${workflow.secrets.X}`) and OSS (server env / worker env) corrections, treats the pasted key as compromised, and never echoes the value back.

### ambiguous-setup.json
The user says simply "Set up Conductor for me." Verifies the standard dual-profile onboarding: `developer` and `localhost` are both saved, Developer Edition is the default, browser navigation reaches Access Control → Applications, key creation and one-time secret entry remain user-owned, and neither a global CLI install nor a local server is started without need.

### incomplete-run-workflow.json
The user says simply "Run my workflow" — no name, no input. Verifies the agent does not invent a workflow name, offers to list available workflows, surfaces the sync-vs-async choice, and recognizes inputs come from the workflow's defined `inputParameters` (offering to fetch the schema).

### conflicting-provider-feature.json
The user requests an Anthropic Claude workflow with `googleSearchRetrieval: true` — a Gemini-only field. Verifies the agent catches the conflict before generating the workflow, identifies `googleSearchRetrieval` as Gemini-only, surfaces `webSearch: true` as the Anthropic-compatible equivalent, offers both valid paths (keep Anthropic + use webSearch, OR keep googleSearchRetrieval + switch to Gemini), and never invents a way to make the broken combination work.

### negative-agent-agenttype-framework.json
The user pastes an `AGENT` task with `agentType: "langgraph"` and a `graph: "agents.support:graph"` input and asks to register it. Verifies the agent refuses as-given, states that `agentType` is only `conductor` / `a2a` (plus the hosted platforms) and never a framework name (F7), rewrites to `agentType: "conductor"` + `name` and drops `graph`, deploys the graph via the SDK `runtime.deploy(graph)` (+ `serve()`), checks `conductor agent list` before wiring, and invents no task property or flag to make the original work.

### negative-agent-agentname-field.json
A workflow uses `agentName: "planner"` in an `AGENT` task and reads `${run.output.result}`. Verifies the agent replaces `agentName` with `name`, explains that `agentName` is only an output field / REST alias, fixes the output path to `${run.output.text}` or `${run.output.output.result}`, does not register as-given, and verifies the agent is deployed.

### negative-agent-approval-via-resume.json
A `transfer_funds` tool is `approval_required`; the user wants a HUMAN task followed by an `AGENT` resume whose `prompt` is "approved". Verifies the agent states that resume posts `{"result": prompt}` while the gate expects `{"approved": true}` (F8), distinguishes conversational `input-required` from tool approval, gives the correct path (`POST /api/agent/{id}/respond {"approved": true}` / `conductor agent respond --approve` / SDK `approve()`), shows at least one way to do it from the workflow or operationally, points to `pendingTool`, and keeps the SWITCH on `waiting`.

### negative-agent-env-model-only.json
An `Agent(name=..., instructions=..., tools=...)` with no `model`, relying on `CONDUCTOR_AGENT_LLM_MODEL` in the deploy environment; the user says "deploy as-is". Verifies the agent refuses, explains that the core `Agent` does not read that env var, sets `model="openai/gpt-4o-mini"` explicitly, states the `provider/model` format, points the provider key at the server (`/api/providers/status`), cites F6, and keeps any env-driven config explicit.

### negative-agent-conductor-deploy-cli.json
The user asks to run `conductor deploy -l python -a support_triage`. Verifies the agent does not run or recommend it, explains that it shells to a non-shipped `agentspan` module / `@agentspan/sdk` package, provides an SDK `runtime.deploy(agent)` release script plus `serve()`, verifies with `conductor agent list/get`, lists the real `conductor agent` verbs, and does not invent `conductor agent deploy`.

### negative-agent-secret-in-instructions.json
The user wants a `ghp_...` GitHub token pasted into an agent's `instructions` and then deployed. Verifies the agent refuses, names at least two exposure paths (sent to the provider every turn, stored in the definition, execution views / stream / logs), cites Rule 5 / D1 / F5, reroutes to a tool reading the token at runtime via `credentials=[...]` plus the secret store (`/api/secrets`, `/agentSecrets`, `CONDUCTOR_SECRET_*` env), never echoes the value and recommends rotation, flags the side-effect tool (F2), and asks confirmation before deploying.

### negative-agent-unsupported-framework-cell.json
A Python team wants Vercel AI SDK tools and a .NET team wants LangChain. Verifies the agent states Vercel AI is TypeScript-only (no fake `conductor-python[vercel]`) and offers a nearest Python path or TS, states LangChain has no .NET bridge (LangChain4j is Java; no fake `Conductor.AI.LangChain`) and offers a nearest .NET path (native `[Tool]`, OpenAI-style builder, ADK, Semantic Kernel), notes the .NET packages are preview, and asks the teams to choose rather than improvising a bridge.

### negative-agent-handwired-loop-vs-sdk.json
The user requests a hand-wired DO_WHILE + LLM_CHAT_COMPLETE + SWITCH + three HTTP tools + SET_VARIABLE loop with 10 turns, refund approval, and live reasoning. Verifies the agent presents the SDK `Agent` (deploy + optional `AGENT` task) as the default and explains the compiler emits the same loop (F4), maps approval to `approval_required=True` + `respond --approve` and live reasoning to `conductor agent stream`, keeps hand-wiring as the escape hatch with at least one legitimate reason, bounds `max_turns=10` with a `provider/model`, and does not deliver only the hand-wired output.

### negative-agent-unbounded-turns.json
A review request for `max_turns=100000`, "keep browsing until you have everything", and an `AGENT` task with no other settings in a workflow with no timeout. Verifies the agent flags `max_turns` CRITICAL under F1, flags the missing `maxDurationSeconds` (24 h default) and workflow timeout, requires an explicit stop condition / `stopWhen` / `termination`, proposes all three bounds in the fix, groups findings by severity with rule IDs, produces a Recommended Changes checklist, and offers to apply rather than silently rewriting.

### orkes-secrets.json
Tests Orkes secrets handling — recognizing the feature is Orkes-only, never echoing the secret value in chat or shell commands, confirming by name only, and showing the `${workflow.secrets.X}` reference syntax for use in workflow tasks.

## Running Evaluations

### Automated (recommended)

The eval runner supports multiple LLM providers: **Anthropic**, **OpenAI**, and **Google Gemini**. The provider is auto-detected from the model name, or can be set explicitly with `--provider`.

```bash
# Run all evals with Anthropic (default)
python3 scripts/run_evals.py

# Run with OpenAI
python3 scripts/run_evals.py --model gpt-4o

# Run with Google Gemini
python3 scripts/run_evals.py --model gemini-2.5-pro

# Explicit provider (for custom/fine-tuned models)
python3 scripts/run_evals.py --provider openai --model ft:gpt-4o:my-org

# Use different providers for agent vs judge
python3 scripts/run_evals.py --model gpt-4o --judge-model claude-sonnet-4-20250514

# Run a specific eval
python3 scripts/run_evals.py evaluations/profile-switching.json

# Verbose output (shows agent response)
python3 scripts/run_evals.py --verbose

# Save JSON report
python3 scripts/run_evals.py --json --output report.json

# Compare across providers
python3 scripts/run_evals.py --model claude-sonnet-4-20250514 -o anthropic.json
python3 scripts/run_evals.py --model gpt-4o -o openai.json
python3 scripts/run_evals.py --model gemini-2.5-pro -o gemini.json
```

The agent-side system prompt only frames the task (tools available, answer as a concrete plan) and defers to the skill for behaviour — it must never contradict a SKILL.md rule (an earlier version told the agent to install the CLI proactively, which fought Rule 3 and made three setup evals flaky).

The runner retries transient API failures (HTTP 429/5xx, timeouts, connection resets) with backoff, records an eval that still fails as `runner_error: true` with a zero score instead of aborting, and rewrites the `--output` JSON after every eval, so a killed or crashed run keeps the evals it completed.

Exit code is `0` if all evals pass, `1` if any fail — suitable for CI/CD gates.

Eval system-prompt size baseline: see `python3 scripts/run_evals.py --print-context-size` (the runner concatenates `SKILL.md` + all `references/*.md` + all `examples/*.md` into the agent's system prompt; keep new reference files tight).

### HTML report

After a run, render the JSON as a self-contained HTML page:

```bash
python3 scripts/render_evals_html.py report.json -o report.html
# multi-model comparison:
python3 scripts/render_evals_html.py claude.json gpt.json gemini.json -o compare.html
```

### In CI

The repo has a dedicated workflow `.github/workflows/evals.yml` that runs the suite on schedule + `workflow_dispatch` + PRs labeled `run-evals` + push to `main` (skill/eval changes only). It uploads both JSON and HTML as artifacts and posts a summary comment on PR runs. See `PUBLISHING.md` for the required `ANTHROPIC_API_KEY` (+ optional `OPENAI_API_KEY` / `GEMINI_API_KEY`) secrets.

### Manual

1. Enable the `conductor` skill
2. Submit the `query` from the evaluation JSON file to the agent
3. Verify each step in `expected_behavior` is followed in order
4. Check all items in `success_criteria` pass
5. Test across models and providers

### Prerequisites

- **Anthropic**: `ANTHROPIC_API_KEY` env var (get at https://console.anthropic.com/)
- **OpenAI**: `OPENAI_API_KEY` env var (get at https://platform.openai.com/api-keys)
- **Gemini**: `GEMINI_API_KEY` env var (get at https://aistudio.google.com/apikey)
- **Local server evals**: No prerequisites — the agent should install CLI and start the server
- **Remote server evals**: Need a running Conductor server URL
- **Profile switching evals**: Need at least two profiles saved as `~/.conductor-cli/config-<profile>.yaml`
- **Worker evals**: Need Python, JavaScript, or Java SDK environment available
- **Fallback evals**: Run in an environment without Node.js/npm

## Expected Skill Behaviors

### CLI Setup
- CLI is installed automatically if missing (`npm install -g @conductor-oss/conductor-cli`)
- Node.js is installed if npm is unavailable
- Fallback script is used only as last resort

### Server Connection
- Local server started with `conductor server start` when no server exists
- Remote servers tested for auth before requesting credentials
- Connections saved as named profiles for reuse

### Workflow Lifecycle
- JSON written to file before registration (never inline)
- SIMPLE tasks checked against task definitions after registration
- Missing workers flagged with offer to scaffold one
- Execution status monitored and reported clearly

### Security
- Auth tokens, keys, and secrets are never echoed in output
- `python3 -c` is never used for any purpose

### Agents
- Model strings are provider-qualified and explicit (`openai/gpt-4o-mini`, `anthropic/claude-sonnet-4-6`, `google_gemini/gemini-2.0-flash`); `CONDUCTOR_AGENT_LLM_MODEL` is never treated as SDK config
- Deployment is via the SDK `runtime.deploy(agent)` — never `conductor deploy` (it targets a non-shipped module); `run()` is not a deployment
- A long-lived `runtime.serve(agent)` process is stated for worker tools (`requiredWorkers` non-empty) and always for passthrough frameworks (plain LangChain, Claude Agent SDK, complex LangGraph)
- `agentType` is only `conductor` or `a2a` (plus hosted `microsoft-foundry` / `openai-assistants` / `bedrock`) — never a framework name
- Deployed agents are referenced by `name`, not `agentName`; `prompt` is required on start and resume; results are read at `${ref.output.text}` / `${ref.output.output.result}`
- Approval-gated tools are approved via `conductor agent respond <id> --approve` / `POST /api/agent/{id}/respond {"approved": true}` / SDK `approve()` — an `AGENT` resume with `executionId` + `prompt` posts `{"result": prompt}`, which a gate only accepts through an LLM normalizer (a model guess, an extra model call), so it is never presented as the approval channel
- `pendingTool` is read through `response_schema` (`approved` field = approval gate, `response` field = conversational question) and `toolCalls[].name`; for compiled Conductor agents `tool_name`/`parameters` are `null`
- Credentials reach agents via `credentials=[...]` plus the secret store (`/api/secrets`, UI `/agentSecrets`, `CONDUCTOR_SECRET_*` server env, or Orkes) — never in `instructions`, `prompt`, or workflow input
- Cancel is `DELETE /api/agent/{id}/cancel?reason=` or `conductor workflow terminate <executionId>` (or `CANCEL_AGENT` in-workflow) — there is no `conductor agent cancel`

## Creating New Evaluations

When adding Conductor evaluations:

1. **Use realistic scenarios** — real workflow patterns (ETL, approval, notification)
2. **Test the full chain** — setup → create → run → monitor → manage
3. **Include error paths** — auth failures, missing workers, failed tasks
4. **Test environment routing** — queries mentioning "dev", "prod", "staging"
5. **Vary complexity** — simple 2-task workflows to complex FORK_JOIN + SWITCH patterns

## Example Success Criteria

**Good** (specific, testable):
- "CLI is installed automatically if missing, not just suggested"
- "SIMPLE tasks are checked against task definitions before starting"
- "Profile names are inferred from context ('dev' and 'prod')"
- "Mermaid diagram uses diamond nodes for SWITCH tasks"
- "Every $.varName in JS scripts (INLINE, DO_WHILE, SWITCH) is declared as an inputParameters key"

**Bad** (vague, untestable):
- "Workflow is created correctly"
- "Agent handles auth properly"
- "Visualization looks good"
