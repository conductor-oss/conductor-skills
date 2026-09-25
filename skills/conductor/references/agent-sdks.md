# Agent SDKs — per-language scaffolds and framework bridges

Companion to [agents.md](agents.md) (contract, lifecycle, decision table). Everything below was verified against the SDK sources and the server's per-language quickstarts, but **the agent APIs drift faster than the worker APIs** — apply SKILL.md Rule 7.3 and Rule 13: WebFetch the SDK's `docs/agents/` before writing code and pin install commands, extras and versions from what the README says today.

| Language | WebFetch first | Package | Import |
|---|---|---|---|
| Python | `https://github.com/conductor-oss/python-sdk/tree/main/docs/agents` | `pip install 'conductor-python[agents]'` (extras: `langchain`, `langgraph`, `adk`, `openai`, `openai-agents`, `anthropic`, `claude`; `agents` = all; core `Agent` needs only `conductor-python`) | `from conductor.ai.agents import Agent, AgentRuntime, tool` |
| TypeScript / JavaScript | `https://github.com/conductor-oss/javascript-sdk/tree/main/docs/agents` | `npm install @io-orkes/conductor-javascript` (+ optional peers `@openai/agents`, `@google/adk`, `@langchain/core @langchain/openai @langchain/langgraph`, `ai zod`) | `import { Agent, AgentRuntime, tool } from "@io-orkes/conductor-javascript/agents"` (subpaths `/agents/testing`, `/agents/langchain`, `/agents/langgraph`, `/agents/vercel-ai`) |
| Java | `https://github.com/conductor-oss/java-sdk/tree/main/docs/agents` | Gradle `implementation 'org.conductoross:conductor-client-ai:<VERSION>'` (Maven Central; **not** `conductor-ai`); `conductor-client-ai-spring` for Spring Boot; framework libs are `compileOnly` | `org.conductoross.conductor.ai.{Agent, AgentRuntime}`, `ai.annotations.{Tool, AgentDef, GuardrailDef}`, `ai.tools.*`, `ai.frameworks.*` |
| C# (.NET 8) | `https://github.com/conductor-oss/csharp-sdk/tree/main/docs/agents` | NuGet ids `conductor-ai`, `conductor-ai-openai`, `conductor-ai-google-adk`, `conductor-ai-semantic-kernel` — **preview, not yet published**; use a project reference | `using Conductor.AI;` |

Env for every SDK: `CONDUCTOR_SERVER_URL` (API base ending in `/api`), `CONDUCTOR_AUTH_KEY` / `CONDUCTOR_AUTH_SECRET` when the server needs auth. Inject credential values through the runtime's secret store or environment; never put them in source, workflow input, chat, or CLI arguments. Provider API keys go on the **server**. Runtime tunables: Python/Java `CONDUCTOR_AGENT_*` (`WORKER_THREADS`, `WORKER_POLL_INTERVAL`, `STREAMING_ENABLED`, …); TS 4.x reads `CONDUCTOR_SERVER_URL` / `CONDUCTOR_AUTH_*` / `CONDUCTOR_TLS_*` (no `AGENTSPAN_*`; verified) and takes tunables as `new AgentRuntime(config?, {workerThreadCount, workerPollIntervalMs, streamingEnabled})`; C# per its README. `CONDUCTOR_AGENT_LLM_MODEL` is an examples convention only — always pass `model="provider/model"`.

## 1. Native scaffold (one tool) — copy, then edit

Python — see [../examples/agents/python/weather_agent.py](../examples/agents/python/weather_agent.py) for the full `run | plan | deploy | serve` version.

```python
from conductor.ai.agents import Agent, AgentRuntime, tool

@tool
def get_weather(city: str) -> dict:
    """Current weather for a city. Idempotent: Conductor may redeliver this task on retry."""
    return {"city": city, "condition": "Sunny", "temp_f": 68}

agent = Agent(
    name="weather_agent",
    model="openai/gpt-4o-mini",            # provider/model — required form
    instructions="Answer weather questions using the tool. Be brief.",
    tools=[get_weather],
    max_turns=10,
)

with AgentRuntime() as runtime:            # reads CONDUCTOR_SERVER_URL / CONDUCTOR_AUTH_*
    result = runtime.run(agent, "Weather in San Francisco?")
    result.print_result(); print(result.execution_id)
```

TypeScript

```typescript
import { Agent, AgentRuntime, tool } from "@io-orkes/conductor-javascript/agents";

const getWeather = tool(async ({ city }: { city: string }) => ({ city, condition: "Sunny" }), {
  name: "get_weather", description: "Current weather for a city.",
  inputSchema: { type: "object", properties: { city: { type: "string" } }, required: ["city"] },
});
const agent = new Agent({ name: "weather_agent", model: "openai/gpt-4o-mini",
  instructions: "Answer weather questions using the tool.", tools: [getWeather], maxTurns: 10 });

const runtime = new AgentRuntime();
try { (await runtime.run(agent, "Weather in San Francisco?")).printResult(); }
finally { await runtime.shutdown(); }
```

Java

```java
import org.conductoross.conductor.ai.Agent;
import org.conductoross.conductor.ai.AgentRuntime;
import org.conductoross.conductor.ai.annotations.Tool;

class WeatherTools {
    @Tool(name = "get_weather", description = "Current weather for a city")
    public Map<String, Object> getWeather(String city) { return Map.of("city", city, "condition", "Sunny"); }
}
Agent agent = Agent.builder().name("weather_agent").model("openai/gpt-4o-mini")
    .instructions("Answer weather questions using the tool.")
    .tools(ToolRegistry.fromInstance(new WeatherTools())).build();   // ToolRegistry: confirm package in docs/agents
try (AgentRuntime runtime = new AgentRuntime()) {
    runtime.run(agent, "Weather in San Francisco?").printResult();
}
```

C# (preview)

```csharp
using Conductor.AI;
var agent = new Agent("weather_agent") { Model = "openai/gpt-4o-mini",
    Instructions = "Answer weather questions using the tool.", Tools = ToolRegistry.FromInstance(new WeatherTools()) };
await using var runtime = new AgentRuntime();
(await runtime.RunAsync(agent, "Weather in San Francisco?")).PrintResult();
sealed class WeatherTools { [Tool("Current weather for a city.")] public Dictionary<string, object> GetWeather(string city) => new() { ["city"] = city, ["condition"] = "Sunny" }; }
```

Structured output: Python `output_type=MyModel` where `MyModel(BaseModel)` is Pydantic; TS `outputType: z.object({...})` (or JSON Schema); Java `.outputType(MyRecord.class)`; C# `.WithOutputType<MyRecord>()`. Execution entry points (`run` / `serve`) go under `if __name__ == "__main__":` in Python — the runtime spawns worker processes.

Decorator forms exist too: Python `@agent` (docstring = instructions) + `Agent.from_instance`, TS `AgentDec`/`agentsFrom`, Java `@AgentDef` + `Agent.fromInstance`, C# `[AgentDef]` + `Agent.FromInstance`.

TypeScript specifics (verified with `tsc --strict` against the published package): guardrail options are **lowercase string unions** and `name` + `mode` are required — `new RegexGuardrail({ name: "no_aws_keys", patterns: [...], mode: "block", position: "output", onFail: "raise", maxRetries: 1, message: "..." })` and `new LLMGuardrail({ model, policy, position: "input", onFail: "retry" })` (not `"OUTPUT"` / `"RAISE"`); structured output is `outputType: z.object({...})` on `new Agent({...})` (there is no `outputSchema` option); `runtime.plan(agent)` is typed `Promise<object>`, so cast it: `const plan = (await runtime.plan(agent)) as { workflowDef: Record<string, unknown>; requiredWorkers: string[] };`; `agent.tools` holds tool wrappers — read tool metadata through `getToolDef(tool)` rather than `agent.tools.find(t => t.name ...)`.

TypeScript symbol index (`@io-orkes/conductor-javascript/agents`): `Agent`, `AgentRuntime`, `tool`, `httpTool`, `apiTool`, `mcpTool`, `agentTool`, `humanTool`, `waitForMessageTool`, `imageTool`, `audioTool`, `videoTool`, `pdfTool`, `indexTool`, `searchTool`, `toolsFrom`, `guardrail`, `RegexGuardrail`, `LLMGuardrail`, `ConversationMemory`, `SemanticMemory`, `scatterGather`, `PromptTemplate`, `ClaudeCode`, `skill`, `loadSkills`, `schedules`, `OrkesAgentClient`, `SchedulerClient`, `discoverAgents`, `detectFramework`; testing subpath: `mockRun(agent, prompt, { mockTools })`, `expectResult(r).toBeCompleted().toHaveUsedTool(...).toContainOutput(...).toHavePassedGuardrail(...).toHaveFinishReason(...).toHaveTokenUsageBelow(n)` (no `.not` — assert the negative with your test runner's `expect` on `r.output` / `getToolDef`), `CorrectnessEval`, `validateStrategy`, `record`, `replay`. SIMPLE-task workers (not agent tools) use `new TaskManager(client, [{ taskDefName, execute }])`.

## 2. Production split (deploy in CI, serve as a service)

```python
# release.py — CI/CD, runs once                 # worker.py — long-lived service
with AgentRuntime() as runtime:                 with AgentRuntime() as runtime:
    plan = runtime.plan(agent)                       runtime.serve(agent)          # blocks; serve(agent, blocking=False) in tests
    print(plan["requiredWorkers"])
    runtime.deploy(agent)                       # registers; no execution
```

TS: `await runtime.plan(agent); await runtime.deploy(agent);` / `await runtime.serve(agent)`. Java: `runtime.plan(agent).getRequiredWorkers(); runtime.deploy(agentA, agentB); runtime.serve(agentA, agentB)`. C#: `await runtime.PlanAsync(agent); await runtime.DeployAsync(agent); await runtime.ServeAsync(token, agent)`. Python `deploy(*agents, packages=[...], schedules=[Schedule(...)])` also attaches cron schedules.

Then call the deployed agent from any workflow with the `AGENT` task ([workflow-definition.md](workflow-definition.md#agent)) and run the agent worker gate (SKILL.md Rule 9).

## 3. Code-free path (CLI config agent)

```bash
conductor agent init my_agent --model openai/gpt-4o-mini -f json     # writes my_agent.json {name, description, model, instructions, maxTurns: 25, tools: []}
conductor agent compile my_agent.json                                 # dry run → compiled workflow + requiredWorkers
conductor agent run --config my_agent.json "Say hello"                # start + stream
python3 "$CONDUCTOR_API" agent-deploy-config --file my_agent.json     # POST /api/agent/deploy {"agentConfig": ...}; there is no CLI deploy for configs
```

Tools in a config file must be server-side types (`http`, `api`, `mcp`, `agent_tool`, `human`, media, RAG) — nothing serves `worker` tools for a config-only agent.

## 4. Bring your framework — support matrix (SKILL.md Rule 10: `agentType` stays `conductor`)

| Framework | Python | TypeScript | Java | C# |
|---|---|---|---|---|
| **OpenAI Agents SDK** | `[openai-agents]`; drop-in `from conductor.ai import Runner, function_tool` + `from agents import Agent` → `Runner.run_sync(agent, prompt)` (`result.final_output`, `result.execution_id`); or pass the `agents.Agent` to `runtime.run` — [example](../examples/agents/python/openai_agents_bridge.py). The normalizer carries over `handoffs` (→ HANDOFF sub-agents), guardrails (custom), `output_type` and `model_settings` — say so, or ask whether the app uses them; nothing has to be dropped | `npm i @openai/agents`; `setTracingDisabled(true)`; pass the `Agent` to `runtime.run` — [example](../examples/agents/typescript/openai-agents-bridge.ts) | OpenAI-*style* builder `frameworks.OpenAIAgent.builder().name().model("openai/…").instructions().tools().handoffs().build()` (does not consume `com.openai` objects) | `conductor-ai-openai`: `Conductor.AI.OpenAI.OpenAIAgent.Builder().Name().Model().Instructions().Tools(new T()).Build()` |
| **Google ADK** | `[adk]`; pass `google.adk.agents.Agent` / `LlmAgent(name, model="gemini-2.0-flash", instruction=..., tools=[...], sub_agents=[...], output_key=...)` or a `SequentialAgent` / `ParallelAgent` / `LoopAgent(max_iterations=...)` to `runtime.run` (model → `google_gemini/`; server needs `GEMINI_API_KEY`; sub-agents map to strategies, callbacks and `output_key` are preserved) — [example](../examples/agents/python/adk_bridge.py) | `npm i @google/adk`; pass `new LlmAgent({...})` (duck-typed) | `compileOnly 'com.google.adk:google-adk:<v>'`; `Agent agent = frameworks.AdkBridge.toAgentspan(llmAgent)` | `conductor-ai-google-adk`: `GoogleADKAgent.Builder().Name().Model().Instruction().Build()` |
| **LangChain** | `[langchain]`; **`from conductor.ai.agents.langchain import create_agent`** — signature `create_agent(model, *, tools=[...], name=..., system_prompt=...)`; any other kwarg is forwarded to LangChain and an unknown one (e.g. `max_turns`) raises `TypeError`. Stamps metadata → compiled. Plain `langchain.agents.create_agent` is detected as LangGraph and may run passthrough — then `OPENAI_API_KEY` must live in the `serve()` process env, not (only) on the server — [example](../examples/agents/python/langchain_bridge.py) | `npm i @langchain/core @langchain/openai`; `createAgentExecutor({agent, tools, llm})` from `/agents/langchain`, or pass an `AgentExecutor` | **LangChain4j**: `compileOnly 'dev.langchain4j:langchain4j:<v>'`; `LangChain4jAgent.from("calculator", "openai/gpt-4o-mini", "Use the tool.", new CalculatorTools())` with `@Tool`/`@P`; or `LangChainBridge.agentBuilder(name, chatModel, systemPrompt, tools...)` | — |
| **LangGraph** | `[langgraph]`; pass `create_react_agent(ChatOpenAI(...), tools=[...], name=...)` to `runtime.run` — compiled when the model is extractable, passthrough for custom `StateGraph`s — [example](../examples/agents/python/langgraph_bridge.py) | `npm i @langchain/langgraph @langchain/openai @langchain/core`; pass the `createReactAgent` graph; wrapper `createReactAgent` from `/agents/langgraph` stamps metadata; `runtime.run(graph, prompt, { model: "anthropic/claude-sonnet-4-6" })` as a hint — [example](../examples/agents/typescript/langgraph-bridge.ts) | **LangGraph4j**: `compileOnly 'org.bsc.langgraph4j:langgraph4j-agent-executor:<v>'` + `langchain4j-open-ai`; pass `AgentExecutor.builder().chatModel(model)` directly to `runtime.run` | — |
| **Vercel AI SDK** | — | Pin `npm i ai@4 zod@3` when unchanged `tool({description, parameters: z.object(...), execute})` objects must go straight into `Agent.tools`; the SDK detects `parameters` + `execute` and derives the tool name from the description. **AI SDK 5+ uses `inputSchema`, which is not auto-detected**: declare the tool with native `tool(execute, {name, description, inputSchema})` from `/agents` instead (same Zod schema, explicit name — recommended when names must be stable) — [example](../examples/agents/typescript/vercel-ai-tools.ts); drop-in `generateText`/`streamText` from `/agents/vercel-ai` for prompt-only use | — | — |
| **Claude Agent SDK** | `[claude]`; `Agent(name, model=ClaudeCode("sonnet"), instructions, tools=["Read", "Glob", "Grep"])` — built-in Claude tool names only; **passthrough → `serve()` mandatory** — [example](../examples/agents/python/claude_agent_sdk_bridge.py) | `ClaudeCode` model class only (no passthrough bridge) | — | — |
| **Semantic Kernel** | — | — | — | `conductor-ai-semantic-kernel`: `SemanticKernelAgent.From(name, model, instructions, new CalculatorPlugin())` with `[KernelFunction]` methods |

All cells use the same `runtime.run(agentOrGraph, prompt)` / `deploy` / `serve` entry point; the compiled-vs-passthrough consequence per row is in [agents.md §6](agents.md#6-framework-execution-model).

**Bounding a framework-bridged agent.** Framework builders have no `max_turns` — do not add one. The compiled loop uses the server default `maxTurns=100` unless the framework carries a cap the normalizer maps (ADK `LoopAgent(max_iterations=...)`, Vercel `maxSteps`, LangGraph custom graphs' `recursion_limit`). Bound framework agents with `AGENT.maxDurationSeconds` on the caller, `runtime.run(..., timeout=...)`, and workflow `timeoutSeconds`; when you need a hard turn cap, `approval_required` tools or guardrails, wrap the loop in a native `Agent` instead (rule F1).

### Unsupported cells — say this, then offer the nearest path

- **Vercel AI outside TypeScript:** "The Vercel AI SDK bridge is TypeScript-only (the `ai` package is JS). In Python use native `@tool` functions on a Conductor `Agent` — same durable execution — or write this agent in TypeScript."
- **LangChain / LangGraph in C#:** "There is no LangChain or LangGraph bridge for .NET. The .NET SDK supports native agents, OpenAI-style, Google ADK and Semantic Kernel; Semantic Kernel is the closest plugin-style fit."
- **Claude Agent SDK outside Python:** "The Claude Agent SDK passthrough bridge is Python-only. If you want Claude as the *model*, use a native agent with `model: "anthropic/claude-sonnet-4-6"` in any language — compiled, server-side, no local Claude Code process."
- **Semantic Kernel outside C#:** "Semantic Kernel is .NET-only. In Java the plugin-style equivalent is LangChain4j (`@Tool` classes); in Python/TS use native `@tool` / `tool()`."
- **CrewAI / AutoGen / Pydantic AI / smolagents / anything else:** "Conductor has no bridge for X. Either (1) rewrite as a native Conductor `Agent` — the `Agent(name, model, instructions, tools)` shape is close — or (2) keep X, expose it as an A2A server, and call it with an `AGENT` task (`agentType: "a2a"`, `agentUrl`). Recommend (1) unless X is deployed independently."
- **Java "OpenAI Agents SDK":** clarify that `OpenAIAgent.builder()` is an OpenAI-*style* builder that compiles to a Conductor agent; it does not port `com.openai` agent objects.

## 6. Multi-agent strategies (all nine, Python; TS/Java/C# use the same names)

`Agent(agents=[...], strategy=...)` — every child needs a unique `name` and its own bounds. `Strategy` values: `handoff` (default), `router`, `sequential`, `parallel`, `swarm`, `round_robin`, `random`, `manual`, `plan_execute`. Children compile to `SUB_WORKFLOW`s; the parent owns the loop.

```python
from conductor.ai.agents import Agent, Strategy, agent_tool, scatter_gather, OnTextMention, OnToolResult, OnCondition
from conductor.ai.agents import TextMentionTermination, MaxMessageTermination, StopMessageTermination, TokenUsageTermination
M = "openai/gpt-4o-mini"

# handoff — the model picks a specialist and the conversation continues there (specialist speaks last unless synthesize=True)
support = Agent(name="support", model=M, instructions="Route to the right specialist.", agents=[billing, technical, sales], strategy=Strategy.HANDOFF)

# router — a dedicated classifier (an Agent or a Python callable) picks exactly one child; no shared conversation
team = Agent(name="dev_team", model=M, agents=[planner, coder, reviewer], strategy=Strategy.ROUTER, router=selector)

# sequential — each child receives the previous child's output; `>>` is sugar for strategy=SEQUENTIAL
pipeline = researcher >> writer >> editor      # or Agent(name="pipeline", agents=[...], strategy=Strategy.SEQUENTIAL)

# parallel — all children at once (FORK_JOIN), parent synthesizes; model is inherited from the first child if omitted
analysis = Agent(name="analysis", model=M, agents=[market_analyst, risk_analyst, compliance], strategy=Strategy.PARALLEL)

# swarm — children pass control to each other through compiler-injected transfer_to_<peer> tools; declarative fallbacks
support = Agent(name="support_swarm", model=M, agents=[refund_specialist, tech_support], strategy=Strategy.SWARM, max_turns=6,
                handoffs=[OnTextMention(text="refund", target="refund_specialist"), OnToolResult(tool_name="lookup_order", result_contains="damaged", target="tech_support")])

# round_robin / random — fixed rotation or a random child per turn; allowed_transitions constrains who may follow whom.
# Open-ended rotations (round_robin/random/swarm) have no natural end: always pair max_turns with termination= (F1/F10).
review = Agent(name="code_review", model=M, agents=[developer, reviewer, approver], strategy=Strategy.ROUND_ROBIN, max_turns=6,
               allowed_transitions={"developer": ["reviewer"], "reviewer": ["developer", "approver"]},
               termination=TextMentionTermination("APPROVED") | MaxMessageTermination(9))
brainstorm = Agent(name="brainstorm", model=M, agents=[creative, practical, critical], strategy=Strategy.RANDOM, max_turns=6,
                   termination=TextMentionTermination("FINAL IDEAS") | MaxMessageTermination(9))

# manual — the run pauses every turn (waiting + pendingTool.response_schema) and a human picks the next agent via handle.respond({...});
# serve()/run() register the `{name}_process_selection` worker for you
team = Agent(name="editorial_team", model=M, agents=[writer, editor, fact_checker], strategy=Strategy.MANUAL, max_turns=3)

# plan_execute — a planner agent emits a typed plan over `tools`, executed as a durable sub-workflow and replanned on failure.
# Requires planner= and a non-empty tools=; fallback= runs when planning fails; planner_context feeds text or fetched URLs to the planner.
writer = Agent(name="research_writer", model=M, tools=[search_web, write_section], strategy=Strategy.PLAN_EXECUTE,
               planner=planner, fallback=fallback, fallback_max_turns=3,
               planner_context=[{"text": "House style: short paragraphs."}, {"url": "https://intranet.example/guide", "headers": {"Authorization": "Bearer ${DOCS_TOKEN}"}}])
```

Composition beyond strategies: `agent_tool(child, name=..., description=..., retry_count=, retry_delay_seconds=, optional=)` calls a child as a tool and returns its result without transferring control (compiles to `SUB_WORKFLOW`; no `max_calls`/`timeout_seconds` kwargs — set `tool_def.max_calls = N` on the result if you need a call bound); `scatter_gather(name, worker=researcher, model=..., instructions=..., retry_count=3, fail_fast=False)` builds a coordinator that decomposes a task, fans the worker out N times (`FORK_JOIN_DYNAMIC`) and synthesizes; strategies nest (`parallel_research >> summarizer`). Stop rules: `termination=TextMentionTermination("DONE") | MaxMessageTermination(20)`, `&`, `StopMessageTermination("TERMINATE")`, `TokenUsageTermination(max_total_tokens=50000)`; `stop_when=callable`. Gotchas: don't name a tool `transfer_*` or an agent `done` in a SWARM; a callable `router`, SWARM `OnCondition` handoffs and MANUAL selection are workers that `serve()` registers — the agent worker gate (Rule 9) applies; every open-ended strategy needs `max_turns` or `termination` (rule F1). Framework agents (LangGraph/OpenAI/ADK) bring their own orchestration — the normalizer maps ADK `SequentialAgent`/`ParallelAgent`/`LoopAgent` and OpenAI `handoffs` to these strategies; you do not add `strategy=` to them.

TS: `strategy: "router"`, `router`, `handoffs: [new OnTextMention(...)]`, `agentTool(child)`, `scatterGather({...})`, `termination` classes from `/agents`. Java: `Strategy.ROUTER`, `.router(agent)`, `.handoffs(...)`, `AgentTool`, `Agent.then(...)` for sequential. C#: `Strategy.Router`, `Agent.ScatterGather(...)`, `a >> b` for sequential.

## 7. Tools beyond functions, memory, code execution, skills, Claude Code

```python
from conductor.ai.agents import http_tool, api_tool, mcp_tool, human_tool, SemanticMemory, CodeExecutionConfig, CliConfig, ClaudeCode, skill

reverse = http_tool(name="reverse_string", description="Reverse a string", url="https://api.example.com/reverse", method="POST",
                    headers={"Authorization": "Bearer ${API_TOKEN}"}, input_schema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}, credentials=["API_TOKEN"])
petstore = api_tool(url="https://petstore.example.com/openapi.json", tool_names=["getPetById", "findPetsByStatus"], max_tools=64)   # OpenAPI/Swagger/Postman discovery → HTTP tools
testkit = mcp_tool(server_url="http://localhost:3001/mcp", name="mcp_testkit", tool_names=["get_weather"])                         # LIST_MCP_TOOLS at compile time; origin must be allowed on the server
ask = human_tool(name="ask_customer", description="Ask the customer one clarifying question.")

# Cross-run memory (sessionId alone never remembers): SemanticMemory is SDK-side (default InMemoryStore is per-process — subclass
# MemoryStore over your DB for durability; `recall` is a worker tool → serve()); index_tool/search_tool are server-side
# LLM_INDEX_TEXT/LLM_SEARCH_INDEX (need a vector DB + embedding integration, no worker).
memory = SemanticMemory(max_results=3); memory.add("Customer Alice prefers email.")
@tool
def recall(query: str) -> str:
    """Recall relevant customer context."""
    return memory.get_context(query)

coder = Agent(name="coder", model=M, instructions="Write and run Python to answer.", local_code_execution=True, allowed_languages=["python"], allowed_commands=["python3"])
sandboxed = Agent(name="sandboxed_coder", model=M, code_execution=CodeExecutionConfig(executor=DockerCodeExecutor(image="python:3.12-slim")))   # also Jupyter/Serverless executors
ops = Agent(name="ops_agent", model=M, cli_commands=True, cli_allowed_commands=["gh", "aws"], credentials=["GH_TOKEN"])            # or cli_config=CliConfig(allowed_commands=[...], timeout=60, working_dir="/work", allow_shell=False)

dg = skill("~/.claude/skills/dg", model=M)                                   # agentskills.io SKILL.md folder → Agent (framework "skill"); also load_skills(dir)
# Compiles to: scripts/* → worker tools `<skill>__<script>` (serve with `conductor skill serve <path>`), agent *.md → `<skill>__<agent>`
# agent_tools, files via `<skill>__read_skill_file`; SKILL.md bodies > 50,000 chars auto-split into `## ` sections. Invoke: AGENT name=<skill> or skillRef.
lead = Agent(name="tech_lead", model=M, tools=[agent_tool(dg, description="Run the DG review")])

fixer = Agent(name="claude_code_fixer", model=ClaudeCode("sonnet", permission_mode=ClaudeCode.PermissionMode.ACCEPT_EDITS),
              tools=["Bash", "Read", "Write", "Edit", "Glob", "Grep"], credentials=["GITHUB_TOKEN"], max_turns=50)              # passthrough: runs inside serve(); tools are Claude's built-ins
```

Hosted platform agents (Foundry / OpenAI Assistants / Bedrock) are not SDK objects — they are `AGENT` tasks with `credentials{}` + `rawConfig` (agents.md §9); with `autoRunTools` (default) their function-tool calls run as SIMPLE tasks named after the tool, so a worker registered for that name serves them. Exposing a Conductor workflow or deployed agent as an A2A server is a server setting (`conductor.a2a.server.enabled=true`, `metadata.a2a.enabled` on the workflow via REST) — see [../examples/agent-a2a-remote.md](../examples/agent-a2a-remote.md).

## 5. Scaffold checklist (what `/conductor-scaffold-agent` generates)

`agent.<ext>` (definition: `provider/model`, instructions, tools, `max_turns`, optional `credentials=[...]`) · `tools.<ext>` (descriptions are the routing contract; idempotency comment; `approval_required` on write tools) · `test_<name>.<ext>` (Python `mock_run` + `expect`, optional live `CorrectnessEval`; TS `mockRun` + `expectResult`; Java/C#: assert `plan()` compiles) · `run_<name>.<ext>` · `deploy.<ext>` (`plan` then `deploy`, prints `requiredWorkers`) · `serve.<ext>` · `workflows/<name>-invoke.json` (`AGENT` task; `waiting` → HUMAN → resume branch when the agent has a human tool) · `.env.example` (server URL + auth only, no provider keys).
