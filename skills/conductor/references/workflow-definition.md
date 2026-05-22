# Conductor Workflow Definition Reference

## Workflow definition schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Workflow name (unique identifier) |
| `description` | string | no | Human-readable description |
| `version` | integer | no | Version number (default: 1) |
| `tasks` | array | yes | Ordered list of task definitions |
| `inputParameters` | array | no | Expected input parameter names |
| `outputParameters` | object | no | Mapping of output keys to expressions |
| `schemaVersion` | integer | no | Schema version (use 2) |
| `restartable` | boolean | no | Whether workflow can be restarted (default: true) |
| `ownerEmail` | string | no | Owner email for notifications |
| `timeoutPolicy` | string | no | `ALERT_ONLY` or `TIME_OUT_WF` |
| `timeoutSeconds` | long | no | Workflow timeout (0 = no timeout) |
| `failureWorkflow` | string | no | Workflow to run on failure |
| `variables` | object | no | Workflow-level variables |

## Task definition in workflow

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Task name (must match task definition for SIMPLE tasks) |
| `taskReferenceName` | string | yes | **Must be unique** across the entire workflow definition |
| `type` | string | yes | Task type (see below) |
| `inputParameters` | object | no | Input mapping using `${...}` expressions |
| `optional` | boolean | no | If true, failure won't fail the workflow |
| `startDelay` | integer | no | Delay in seconds before starting |
| `asyncComplete` | boolean | no | If true, task completes via external signal |

## Input expressions

Reference workflow input, task output, or variables:

- `${workflow.input.paramName}` — workflow input
- `${taskRefName.output.fieldName}` — output from a prior task
- `${workflow.variables.varName}` — workflow variable

---

## System task types

### SIMPLE
Worker task polled and executed by external workers.
```json
{"name": "my_task", "taskReferenceName": "my_task_ref", "type": "SIMPLE", "inputParameters": {"param1": "${workflow.input.data}"}}
```

### HTTP
Make HTTP requests. Supports GET, POST, PUT, DELETE, OPTIONS, HEAD with headers, body, and timeouts.
```json
{
  "name": "http_call", "taskReferenceName": "call_api", "type": "HTTP",
  "inputParameters": {
    "http_request": {
      "uri": "https://api.example.com/data",
      "method": "POST",
      "headers": {"Authorization": "Bearer ${workflow.input.token}"},
      "body": {"key": "${workflow.input.value}"},
      "accept": "application/json",
      "contentType": "application/json",
      "connectionTimeOut": 3000,
      "readTimeOut": 3000
    }
  }
}
```
**Input schema** (inside `http_request`):

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `uri` | string | yes | — | Full URL to call |
| `method` | string | yes | — | HTTP method: `GET`, `POST`, `PUT`, `DELETE`, `OPTIONS`, `HEAD` |
| `headers` | map\<string, object\> | no | `{}` | Request headers as key-value pairs |
| `body` | object/string | no | — | Request body (auto-serialized to JSON) |
| `accept` | string | no | `"application/json"` | Accept header MIME type |
| `contentType` | string | no | `"application/json"` | Content-Type header MIME type |
| `connectionTimeOut` | integer | no | `3000` | Connection timeout in milliseconds |
| `readTimeOut` | integer | no | `3000` | Read timeout in milliseconds |
| `vipAddress` | string | no | — | Discovery-based address (Eureka) |
| `appName` | string | no | — | Application name for discovery |

**Output schema** — the task outputs a `response` object:
```json
{
  "response": {
    "statusCode": 200,
    "reasonPhrase": "OK",
    "headers": {"Content-Type": ["application/json"]},
    "body": { }
  }
}
```
- `response.statusCode` (int) — HTTP status code
- `response.reasonPhrase` (string) — HTTP reason phrase (e.g. `"OK"`, `"Not Found"`)
- `response.headers` (map) — response headers (each value is an array of strings)
- `response.body` (object/array/string/number) — parsed response body (auto-parsed as JSON if possible, otherwise raw string)

To reference in subsequent tasks: `${call_api.output.response.body.fieldName}`, `${call_api.output.response.statusCode}`.

### JSON_JQ_TRANSFORM
Transform data using jq expressions. Powerful for reshaping, filtering, and aggregating JSON.
```json
{
  "name": "transform", "taskReferenceName": "jq_ref", "type": "JSON_JQ_TRANSFORM",
  "inputParameters": {
    "data": "${workflow.input.items}",
    "queryExpression": "[.[] | {name: .name, id: .id}]"
  }
}
```
Common jq patterns:
- Filter: `[.[] | select(.status == "active")]`
- Map: `[.[] | {id: .id, label: .name}]`
- Aggregate: `{total: ([.[].amount] | add), count: length}`
- Flatten: `[.[][] | .field]`

> **The `$.varName` rule — applies to every JavaScript-evaluated task (INLINE, DO_WHILE `loopCondition`, SWITCH with `javascript`/`graaljs` evaluator):**
> Every variable referenced as `$.varName` inside a script or condition **must** be declared as an `inputParameters` key on that task. The `$` object in the script is the task's resolved `inputParameters` map (excluding `evaluatorType` and `expression`).
>
> `$.workflow.input.*` and `$.workflow.variables.*` are **NOT** in scope inside a script — they throw `TypeError: Cannot read property "input"/"variables" from undefined`. To use a workflow input or variable in a script, plumb it through `inputParameters`.
>
> Prefer `evaluatorType: "graaljs"` — older `"javascript"` may not be wired up on recent clusters. See [graaljs-gotchas.md](graaljs-gotchas.md) for full rules.

### INLINE
Execute lightweight scripts (JavaScript via GraalVM).

**The `$.varName` rule applies — every `$.x` in the script must be declared as an `inputParameters` key.**

```json
{
  "name": "inline_task", "taskReferenceName": "compute", "type": "INLINE",
  "inputParameters": {
    "evaluatorType": "graaljs",
    "expression": "(function(){ return $.value * 2; })();",
    "value": "${workflow.input.number}"
  }
}
```

Example with multiple inputs — every `$.x` referenced in the script needs a matching key:
```json
{
  "name": "inline_task", "taskReferenceName": "compute", "type": "INLINE",
  "inputParameters": {
    "evaluatorType": "graaljs",
    "expression": "(function(){ return $.name + ' is ' + $.age; })();",
    "name": "${workflow.input.name}",
    "age": "${workflow.input.age}"
  }
}
```

**Important gotchas (see [graaljs-gotchas.md](graaljs-gotchas.md) for full rules):**
- Task outputs (HTTP, LLM, MCP) are already parsed objects. Don't `String()` then `JSON.parse` — `String()` on a Java-Map-backed proxy yields `{k=v}`, not JSON.
- `JSON.stringify` and `Object.keys` return `"{}"` / `[]` on those proxies. To serialize structured output into a string field, use `JSON_JQ_TRANSFORM` with `tojson`, not INLINE.
- Avoid `input` and `messages` as INLINE input-parameter names — observed obscure failures; rename to `inputMessages` etc.

### SWITCH
Conditional branching based on a value or JavaScript expression.
```json
{
  "name": "switch_task", "taskReferenceName": "route", "type": "SWITCH",
  "evaluatorType": "value-param",
  "expression": "switchCaseValue",
  "inputParameters": {"switchCaseValue": "${workflow.input.type}"},
  "decisionCases": {
    "typeA": [{"...task A...": ""}],
    "typeB": [{"...task B...": ""}]
  },
  "defaultCase": [{"...default task...": ""}]
}
```
**When using JavaScript evaluation, the `$.varName` rule applies** — every variable referenced in the expression must be declared in `inputParameters`. Prefer `evaluatorType: "graaljs"`:
```json
{
  "name": "switch_task", "taskReferenceName": "js_route", "type": "SWITCH",
  "evaluatorType": "graaljs",
  "expression": "$.priority > 5 ? 'high' : 'low'",
  "inputParameters": {"priority": "${workflow.input.priority}"},
  "decisionCases": {
    "high": [{"...urgent task...": ""}],
    "low": [{"...normal task...": ""}]
  },
  "defaultCase": [{"...default task...": ""}]
}
```

**Keep `defaultCase` empty (or a single `NOOP`) unless you have a meaningful no-op handler** — a `defaultCase` that performs a finalize/cleanup step will fire on every unrecognized value and overwrite downstream state with garbage. See [template-resolution.md](template-resolution.md) Pitfall 1.

### FORK_JOIN / JOIN
Execute tasks in parallel. Always pair FORK_JOIN with a JOIN task.
```json
{"name": "fork", "taskReferenceName": "parallel", "type": "FORK_JOIN", "forkTasks": [[{"...task A...": ""}], [{"...task B...": ""}]]}
```
```json
{"name": "join", "taskReferenceName": "join_ref", "type": "JOIN", "joinOn": ["taskA_ref", "taskB_ref"]}
```

### DO_WHILE
Loop until a JavaScript condition returns false.

**The `$.varName` rule applies — every variable in `loopCondition` must be declared in `inputParameters`. Always set `evaluatorType: "graaljs"` at the top level of the DO_WHILE task.**

```json
{
  "name": "loop",
  "taskReferenceName": "loop_ref",
  "type": "DO_WHILE",
  "evaluatorType": "graaljs",
  "loopCondition": "(function(){ return $.loop_ref['iteration'] < $.value; })();",
  "loopOver": [{"...task...": ""}],
  "inputParameters": {
    "value": "${workflow.input.count}",
    "loop_ref": "${loop_ref.output}"
  }
}
```

**The self-reference pattern.** `"loop_ref": "${loop_ref.output}"` looks like a typo — referencing a task before it has output — but it is the canonical pattern. Conductor resolves the reference lazily on each iteration, exposing the running `iteration` counter (and prior iterations' task outputs) inside the script. See [examples/do-while-loop.md](../examples/do-while-loop.md) for a runnable workflow.

**Use an IIFE for `loopCondition`.** Conductor reads the final value of the script. The IIFE form returns a clean boolean across cluster versions; the older `if (...) { true; } else { false; }` statement form is fragile, and named functions or `return true; return false;` patterns produce confusing failures. See [graaljs-gotchas.md](graaljs-gotchas.md) Rule 6.

**Scope inside `loopCondition`:**

- `$.<key>` for every key in `inputParameters` (after `${...}` resolution).
- **Not** in scope: `$.workflow.input.*`, `$.workflow.variables.*`. Plumb workflow inputs/variables through `inputParameters` if you need them.

**Reading the iteration counter from outside the loop:**

| Where | Expression |
|-------|------------|
| `workflow.outputParameters` | `${loop_ref.output.iteration}` |
| Another task's `inputParameters` | `${loop_ref.output.iteration}` |
| Inside `loopCondition` (after wiring `loop_ref: ${loop_ref.output}`) | `$.loop_ref['iteration']` |

`${loop_ref.iteration}` (no `.output`) is wrong — `iteration` lives inside `outputData`, not on the task. See [template-resolution.md](template-resolution.md) Pitfall 3.

**Always cap the loop.** Even when the body has a result-driven exit, include an iteration cap in the condition (`$.loop_ref['iteration'] < N`). An unbounded loop is flagged CRITICAL by the optimization checklist.

### WAIT
Pause execution until a signal, a duration elapses, or a specific date/time is reached. Use `conductor task signal` to resume a signal-based wait.

**Wait forever (signal mode)** — pauses until explicitly signaled via API or CLI:
```json
{"name": "wait_task", "taskReferenceName": "wait_for_signal", "type": "WAIT", "inputParameters": {}}
```

**Wait for a duration** — resumes automatically after the specified time:
```json
{"name": "wait_task", "taskReferenceName": "wait_10m", "type": "WAIT", "inputParameters": {"duration": "10m"}}
```
Duration format: `[Xd] [Xh] [Xm] [Xs]` — combine any units, case-insensitive, integers only (no decimals).
- Days: `days`, `day`, `d`
- Hours: `hours`, `hour`, `hrs`, `hr`, `h`
- Minutes: `minutes`, `minute`, `mins`, `min`, `m`
- Seconds: `seconds`, `second`, `secs`, `sec`, `s`
- Examples: `"5s"`, `"5m"`, `"2h"`, `"5d"`, `"5d 5h 5m 5s"`, `"30m 10s"`
- Invalid: `"5"` (no unit), `"5.0s"` (no decimals)

**Wait until a specific date/time** — resumes at the given timestamp:
```json
{"name": "wait_task", "taskReferenceName": "wait_until", "type": "WAIT", "inputParameters": {"until": "2026-01-15 17:00"}}
```
Until format (parsed in order): `yyyy-MM-dd HH:mm`, `yyyy-MM-dd HH:mm z`, or `yyyy-MM-dd`.
- With timezone: `"2026-01-15 17:00 GMT+04:00"`, `"2026-01-15 17:00 PST"`
- Without timezone: `"2026-01-15 17:00"` (uses server timezone)
- Date only: `"2026-01-15"` (midnight)
- Dynamic: `"until": "${workflow.input.scheduledTime}"`

Note: you cannot specify both `duration` and `until` — the task will fail with `FAILED_WITH_TERMINAL_ERROR`.

### HUMAN
Wait for human input (similar to WAIT but designed for human-in-the-loop).
```json
{"name": "human_task", "taskReferenceName": "approval", "type": "HUMAN"}
```

### SUB_WORKFLOW
Execute another workflow as a task. The parent workflow waits for the sub-workflow to complete.
```json
{"name": "sub", "taskReferenceName": "sub_ref", "type": "SUB_WORKFLOW", "subWorkflowParam": {"name": "child_workflow", "version": 1}, "inputParameters": {"data": "${workflow.input.payload}"}}
```

### START_WORKFLOW
Start another workflow asynchronously (fire-and-forget). Unlike SUB_WORKFLOW, the parent does NOT wait — it immediately completes and outputs the child's workflowId.
```json
{
  "name": "start_wf", "taskReferenceName": "start_ref", "type": "START_WORKFLOW",
  "inputParameters": {
    "startWorkflow": {
      "name": "child_workflow",
      "version": 1,
      "input": {"key": "${workflow.input.value}"},
      "correlationId": "${workflow.correlationId}"
    }
  }
}
```
**Outputs**: `workflowId` (the started workflow's ID).

### DYNAMIC
Dynamically resolve the task type at runtime. The `dynamicTaskNameParam` input specifies which input parameter holds the actual task name to execute.
```json
{
  "name": "dynamic_task", "taskReferenceName": "dynamic_ref", "type": "DYNAMIC",
  "dynamicTaskNameParam": "taskToExecute",
  "inputParameters": {
    "taskToExecute": "${workflow.input.taskName}",
    "param1": "${workflow.input.data}"
  }
}
```

### FORK_JOIN_DYNAMIC
Dynamically create parallel branches at runtime. A `dynamicForkTasksParam` input provides the list of tasks, and `dynamicForkTasksInputParamName` provides their inputs.
```json
{
  "name": "dynamic_fork", "taskReferenceName": "dfork_ref", "type": "FORK_JOIN_DYNAMIC",
  "dynamicForkTasksParam": "dynamicTasks",
  "dynamicForkTasksInputParamName": "dynamicTasksInput",
  "inputParameters": {
    "dynamicTasks": "${generate_tasks.output.tasks}",
    "dynamicTasksInput": "${generate_tasks.output.inputs}"
  }
}
```
Always follow with a JOIN task. The `dynamicTasks` value is an array of task definitions, and `dynamicTasksInput` is a map of taskReferenceName to input objects.

### EXCLUSIVE_JOIN
Like JOIN but completes as soon as any ONE of the specified tasks completes (instead of waiting for all). Used after FORK_JOIN for exclusive/race patterns.
```json
{
  "name": "exclusive_join", "taskReferenceName": "ejoin_ref", "type": "EXCLUSIVE_JOIN",
  "inputParameters": {},
  "joinOn": ["taskA_ref", "taskB_ref"],
  "defaultExclusiveJoinTask": ["taskA_ref"]
}
```

### EVENT
Publish an event to a sink (e.g. SQS, Conductor internal).
```json
{"name": "event", "taskReferenceName": "publish", "type": "EVENT", "sink": "conductor:event_name", "inputParameters": {"payload": "${workflow.input.data}"}}
```

### KAFKA_PUBLISH
Publish a message to a Kafka topic. Requires the Kafka module to be enabled.
```json
{
  "name": "kafka_task", "taskReferenceName": "kafka_ref", "type": "KAFKA_PUBLISH",
  "inputParameters": {
    "kafka_request": {
      "topic": "my-topic",
      "bootStrapServers": "kafka-broker:9092",
      "value": {"data": "${workflow.input.payload}"},
      "key": "${workflow.input.messageKey}",
      "headers": {"source": "conductor"}
    }
  }
}
```
**Inputs** (inside `kafka_request`): `topic` (required), `bootStrapServers` (required), `value` (required), `key`, `headers`.

### SET_VARIABLE
Set workflow-level variables accessible by subsequent tasks.
```json
{"name": "set_var", "taskReferenceName": "set_ref", "type": "SET_VARIABLE", "inputParameters": {"myVar": "${some_task.output.result}"}}
```

### TERMINATE
End the workflow immediately with a status and output.
```json
{"name": "end", "taskReferenceName": "terminate_ref", "type": "TERMINATE", "inputParameters": {"terminationStatus": "COMPLETED", "workflowOutput": {"result": "${task_ref.output.data}"}}}
```
`terminationStatus` can be `COMPLETED` or `FAILED`.

### NOOP
No-operation task. Immediately completes with no side effects. Useful as a placeholder or default branch in SWITCH.
```json
{"name": "noop", "taskReferenceName": "noop_ref", "type": "NOOP"}
```


---

## AI task types

Conductor has built-in AI tasks supporting 12 LLM providers (OpenAI, Anthropic, Google Vertex AI, Azure OpenAI, AWS Bedrock, Mistral, Cohere, Grok, Perplexity, HuggingFace, Ollama, Stability AI) and vector databases (Pinecone, Postgres pgvector, MongoDB Atlas).

### LLM_CHAT_COMPLETE
Multi-turn conversational AI with optional tool calling. Supports all LLM providers.

> **Message schema is `{role, message}`, NOT `{role, content}`.** This contradicts the native Anthropic, OpenAI, and most other LLM-provider schemas (which use `content`). Conductor's field is `message`. Using `content` produces `Content must not be null for SYSTEM or USER messages`.

```json
{
  "name": "chat_task", "taskReferenceName": "chat", "type": "LLM_CHAT_COMPLETE",
  "inputParameters": {
    "llmProvider": "openai",
    "model": "gpt-4o",
    "messages": [
      {"role": "system", "message": "You are a helpful assistant."},
      {"role": "user", "message": "${workflow.input.question}"}
    ],
    "temperature": 0.7,
    "maxTokens": 500,
    "jsonOutput": false
  }
}
```
**Inputs** (full list — see [examples/llm-chat.md](../examples/llm-chat.md) for usage patterns):

| Field | Type | Description |
|-------|------|-------------|
| `llmProvider` | string (required) | e.g. `openai`, `anthropic`, `google_gemini`, `vertex_ai`, `azureopenai`, `bedrock`, `mistral`, `cohere`, `grok`, `perplexity`, `huggingface`, `ollama` |
| `model` | string (required) | provider-specific model ID |
| `messages` | array (required) | `[{role, message}]` — note `message`, not `content` |
| `instructions` | string | optional system instructions (alias for the legacy `prompt` field) |
| `temperature` | number | sampling temperature (0.0–2.0) |
| `maxTokens` | integer | hard cap on completion length (default `8192`) |
| `topP` | number | nucleus sampling |
| `topK` | integer | top-k sampling (where supported) |
| `frequencyPenalty` | number | OpenAI-style frequency penalty |
| `presencePenalty` | number | OpenAI-style presence penalty |
| `stopSequences` | array | stop tokens (also accepted: `stopWords`) |
| `tools` | array | function-calling tool definitions. **Each tool is a registered Conductor worker** (default `type: SIMPLE`) or a supported integration — when the LLM emits a tool call, Conductor dispatches it to the matching worker. See below. |
| `participants` | object | role assignments for MCP tool integrations |
| `jsonOutput` | boolean | parse the raw text as JSON into `output.result`. **For some models (notably Anthropic Claude), you MUST include the word `JSON` somewhere in the prompt** — otherwise the model emits prose. Conductor parses via Jackson and fails hard on markdown fences. |
| `inputSchema` | object | `SchemaDef` — validates the inputs before calling the model |
| `outputSchema` | object | `SchemaDef` — validates the parsed output. On schema failure the task is **retried `retryCount` times** (default 3) with no backoff. Useful with `jsonOutput: true`. |
| `webSearch` | boolean | enable provider-native web search. Supported by **OpenAI, Anthropic, Google Gemini**. |
| `codeInterpreter` | boolean | enable sandboxed code execution. Supported by **OpenAI (`code_interpreter`), Anthropic (`code_execution`), Google Gemini (`codeExecution`)**. |
| `fileSearchVectorStoreIds` | array\<string\> | vector store IDs for file search. **OpenAI only.** |
| `googleSearchRetrieval` | boolean | enable Google Search grounding. **Gemini only.** |
| `thinkingTokenLimit` | integer | token budget for extended reasoning **before** the model writes its answer. Supported by **Anthropic** (Claude 3.7+/Sonnet 4 extended thinking) and **Google Gemini** (2.5+). |
| `reasoningEffort` | string | `low`, `medium`, or `high`. **OpenAI only** (o-series / gpt-5+ via the Responses API). |
| `reasoningSummary` | string | surface chain-of-thought reasoning on the task output. Values: OpenAI accepts `auto` / `concise` / `detailed`; Anthropic and Gemini accept any non-blank value to opt in. When set, `output.reasoning` and `output.reasoningTokens` are populated. |
| `previousResponseId` | string | **chain multi-turn conversations without resending message history**. The output `responseId` of a prior `LLM_CHAT_COMPLETE` task is referenced here, e.g. `${turn1.output.responseId}`. **OpenAI and Azure OpenAI only** (uses the Responses API). The new task's `messages` array is treated as the next turn appended to the chain. |
| `outputMimeType` | string | HTTP-style content type for the output (media generation flows) |
| `outputLocation` | string | URI where results should be stored (e.g., audio/video output paths) |
| `voice` | string | audio output voice (when the model supports speech) |
| `promptVersion` / `promptVariables` / `allowRawPrompts` | — | Orkes prompt-template integration (named prompts stored on the server, with versioning and variable interpolation). Pair with the legacy `prompt` field on the task. |
| `integrationName` | string | named Orkes integration override (per-environment auth) |
| `maxResults` | integer | when the provider returns N choices, how many to keep (default `1`) |

**Outputs** — `output.result` is an `Object` whose runtime type depends on `jsonOutput` and the provider's reply:

| Field | Type | Description |
|-------|------|-------------|
| `result` | string or object | response text (default) or parsed object (when `jsonOutput: true` AND the model emitted parseable JSON) |
| `finishReason` | string | `STOP`, `TOOL_CALLS`, `LENGTH` |
| `tokenUsed`, `promptTokens`, `completionTokens` | integer | token accounting |
| `toolCalls` | array | present when `finishReason == "TOOL_CALLS"` |
| `responseId` | string | provider-side response ID. **Pass into the next task's `previousResponseId` to chain (OpenAI/Azure).** |
| `reasoning` | string | chain-of-thought text when `reasoningSummary` was set (OpenAI/Anthropic/Gemini) |
| `reasoningTokens` | integer | tokens spent on reasoning (where supported) |
| `media` | array | generated media items (`location`, `mimeType`) for audio/video output |
| `jobId` | string | provider's async job ID for long-running operations |

**Built-in tools — when to use which.**

| Need | Use |
|------|-----|
| Real-time / fresh-from-the-web answers | `webSearch: true` (no MCP needed) |
| Run Python/JS to compute, analyze, generate charts | `codeInterpreter: true` |
| Search through pre-uploaded files (OpenAI Vector Stores) | `fileSearchVectorStoreIds: ["vs_..."]` |
| Ground a Gemini answer in Google Search results | `googleSearchRetrieval: true` (Gemini only) |
| Deeper reasoning before the final answer | `thinkingTokenLimit: 10000` (Anthropic/Gemini) or `reasoningEffort: "high"` (OpenAI) |
| Surface the reasoning text in the task output | `reasoningSummary: "detailed"` |
| Custom tools / your own workflows / external APIs | `tools: [...]` (function calling) or `CALL_MCP_TOOL` |

These are mutually compatible — a single task can combine `webSearch: true` with `tools: [...]` for a custom-tool agent that can also browse the web.

**Custom tools dispatched to Conductor workers.**

The `tools` array is Conductor-distinctive. Each entry is a `ToolSpec`:

```json
"tools": [
  {
    "name": "lookup_customer",
    "type": "SIMPLE",
    "description": "Look up a customer by ID. Returns name, email, and account status.",
    "inputSchema": {
      "type": "object",
      "properties": { "customer_id": { "type": "string" } },
      "required": ["customer_id"]
    }
  }
]
```

| Field | Description |
|-------|-------------|
| `name` | Tool name the LLM sees. Must match a registered Conductor worker `taskDefName` (when `type` is `SIMPLE`). |
| `type` | Task type. Defaults to `SIMPLE`. Other values dispatch through the corresponding Conductor task. |
| `description` | What the LLM reads to decide whether to call this tool. Be specific — this is the only signal the model has. |
| `inputSchema` | JSON Schema for the tool's inputs. The LLM-emitted arguments are validated against this. |
| `outputSchema` | JSON Schema for the tool's outputs (informational). |
| `configParams` / `integrationNames` | Per-tool config and integration overrides. |

When the LLM emits a tool call, `output.finishReason` is `TOOL_CALLS` and `output.toolCalls` contains the resolved invocations — each `ToolCall` includes the matched `type` (the Conductor task type to dispatch). You typically follow with a SWITCH or DYNAMIC task that runs the worker, then a follow-up `LLM_CHAT_COMPLETE` that consumes the tool result.

This is the "registered Conductor worker is a tool" pattern. The LLM picks from your registered task definitions; no separate function-calling layer to write. Combine with `previousResponseId` (OpenAI) to chain tool-call turns without resending history.

**Multi-turn chaining without resending history (OpenAI/Azure).**

The Responses API stores the entire conversation server-side. `previousResponseId` references the prior turn; you only need to send the new user turn in `messages`. This cuts cost and latency dramatically across long agent loops or multi-turn dialogues.

```json
{
  "tasks": [
    {
      "taskReferenceName": "turn1",
      "type": "LLM_CHAT_COMPLETE",
      "inputParameters": {
        "llmProvider": "openai",
        "model": "gpt-4o",
        "messages": [
          {"role": "system", "message": "You are a technical architect."},
          {"role": "user", "message": "Design X."}
        ]
      }
    },
    {
      "taskReferenceName": "turn2",
      "type": "LLM_CHAT_COMPLETE",
      "inputParameters": {
        "llmProvider": "openai",
        "model": "gpt-4o",
        "messages": [{"role": "user", "message": "Now list the key risks."}],
        "previousResponseId": "${turn1.output.responseId}"
      }
    }
  ]
}
```

**Caveats:**
- `previousResponseId` is **OpenAI- and Azure-OpenAI-only**. Other providers ignore it. For portable chains, accumulate the full `messages` array (see [../examples/ai-agent-loop.md](../examples/ai-agent-loop.md)).
- Server-side state expires per OpenAI's Responses retention policy (currently ~30 days). For long-lived agent state, persist messages yourself.
- You cannot mix providers mid-chain — every turn must point to the same provider that produced the original `responseId`.

See [../examples/llm-chaining.md](../examples/llm-chaining.md) for the full pattern.

**The `result` type is `jsonOutput`-dependent.** With `jsonOutput: true`, `result` is a **parsed object** and you access fields as `${chat.output.result.action}`. With `jsonOutput: false`, `result` is a **string** and you have to parse it yourself (or branch on it as text). Downstream SWITCH cases that route on `output.result.action` should always have an empty `defaultCase` or a sentinel branch, since a malformed LLM emission falls through as a string.

**`jsonOutput: true` is strict.** Conductor parses the raw model text via Jackson. If the model emits markdown fences (```` ```json ... ``` ````) — which Claude frequently does regardless of system-prompt instructions — the parse fails hard and the task errors. There is no "tolerant" mode that strips fences. Workarounds:
- Use the provider's native structured-output mode (Anthropic tool-use, OpenAI JSON mode) via `tools`.
- Keep `jsonOutput: false` and parse defensively downstream (substring-extract the JSON between `{` and the matching `}`).
- Use a SIMPLE worker that calls the provider directly when you need strict structured output.

**Object-typed `message` fields are dangerous.** If a `messages[].message` value is a structured object rather than a string (e.g. you accidentally interpolate `${some_task.output}` without stringifying), Conductor Java-`toString`s it to `{key=value}` on the way to the provider — producing garbage in the chat history and nonsense responses. Always serialize structured data into a string first using `JSON_JQ_TRANSFORM` with `tojson` (not INLINE — see [graaljs-gotchas.md](graaljs-gotchas.md) Rule 3).

### LLM_TEXT_COMPLETE
Single prompt text completion.
```json
{
  "name": "text_task", "taskReferenceName": "complete", "type": "LLM_TEXT_COMPLETE",
  "inputParameters": {
    "llmProvider": "anthropic",
    "model": "claude-3-5-sonnet-20241022",
    "prompt": "Summarize: ${workflow.input.text}",
    "temperature": 0.3,
    "maxTokens": 1000
  }
}
```
**Inputs**: `llmProvider`, `model`, `prompt` (all required), `temperature`, `maxTokens`.
**Outputs**: `result`, `tokenUsed`.

### LLM_GENERATE_EMBEDDINGS
Convert text to vector embeddings.
```json
{
  "name": "embed_task", "taskReferenceName": "embed", "type": "LLM_GENERATE_EMBEDDINGS",
  "inputParameters": {
    "llmProvider": "openai",
    "model": "text-embedding-3-small",
    "text": "${workflow.input.document}"
  }
}
```
**Inputs**: `llmProvider`, `model`, `text` (all required).
**Outputs**: `result` (array of floats, e.g. 1536 dimensions for OpenAI).

### GENERATE_IMAGE
Generate images from text prompts. Supports OpenAI (DALL-E-3), Vertex AI (Imagen), Azure OpenAI, Stability AI.
```json
{
  "name": "img_task", "taskReferenceName": "img", "type": "GENERATE_IMAGE",
  "inputParameters": {
    "llmProvider": "openai",
    "model": "dall-e-3",
    "prompt": "A futuristic cityscape at sunset",
    "width": 1024,
    "height": 1024,
    "style": "vivid"
  }
}
```
**Inputs**: `llmProvider`, `model`, `prompt` (all required), `width`, `height`, `n`, `style`.
**Outputs**: `url` or `b64_json`.

### GENERATE_AUDIO
Text-to-speech synthesis. Supports OpenAI TTS.
```json
{
  "name": "audio_task", "taskReferenceName": "audio", "type": "GENERATE_AUDIO",
  "inputParameters": {
    "llmProvider": "openai",
    "model": "tts-1-hd",
    "text": "${workflow.input.narration}",
    "voice": "nova"
  }
}
```
**Inputs**: `llmProvider`, `model`, `text` (all required), `voice` (e.g. `alloy`, `echo`, `nova`).
**Outputs**: `media` (array with `location` URL and `mimeType`).

### GENERATE_VIDEO
Generate videos from text/image prompts (async). Supports OpenAI Sora and Google Vertex AI Veo.
```json
{
  "name": "video_task", "taskReferenceName": "video", "type": "GENERATE_VIDEO",
  "inputParameters": {
    "llmProvider": "openai",
    "model": "sora-2",
    "prompt": "A drone flying over a mountain landscape",
    "duration": 8,
    "size": "1280x720"
  }
}
```
**Inputs**: `llmProvider`, `model`, `prompt` (all required), `duration`, `size`, `aspectRatio`, `resolution`, `style`, `n`, `inputImage` (for image-to-video), `negativePrompt`, `generateAudio` (Veo 3+).
**Outputs**: `media` (array with video URL and optional thumbnail), `jobId`, `status`, `pollCount`.

### LLM_INDEX_TEXT
Store text with auto-generated embeddings in a vector database.
```json
{
  "name": "index_task", "taskReferenceName": "index", "type": "LLM_INDEX_TEXT",
  "inputParameters": {
    "vectorDB": "pinecone-prod",
    "namespace": "docs",
    "index": "knowledge-base",
    "embeddingModelProvider": "openai",
    "embeddingModel": "text-embedding-3-small",
    "text": "${workflow.input.document}",
    "docId": "${workflow.input.docId}",
    "metadata": {"source": "upload", "category": "${workflow.input.category}"}
  }
}
```
**Inputs**: `vectorDB`, `namespace`, `index`, `embeddingModelProvider`, `embeddingModel`, `text` (all required), `docId`, `metadata`.

### LLM_STORE_EMBEDDINGS
Store pre-computed embeddings in a vector database.
```json
{
  "name": "store_task", "taskReferenceName": "store", "type": "LLM_STORE_EMBEDDINGS",
  "inputParameters": {
    "vectorDB": "postgres-prod",
    "namespace": "docs",
    "index": "articles",
    "embeddings": "${embed.output.result}",
    "docId": "${workflow.input.docId}"
  }
}
```
**Inputs**: `vectorDB`, `namespace`, `index`, `embeddings` (all required), `docId`, `metadata`.

### LLM_SEARCH_INDEX
Semantic search using a text query (auto-generates embeddings from the query).
```json
{
  "name": "search_task", "taskReferenceName": "search", "type": "LLM_SEARCH_INDEX",
  "inputParameters": {
    "vectorDB": "postgres-prod",
    "namespace": "kb",
    "index": "articles",
    "embeddingModelProvider": "openai",
    "embeddingModel": "text-embedding-3-small",
    "query": "${workflow.input.question}",
    "llmMaxResults": 5
  }
}
```
**Inputs**: `vectorDB`, `namespace`, `index`, `embeddingModelProvider`, `embeddingModel`, `query` (all required), `llmMaxResults`.

### LLM_SEARCH_EMBEDDINGS
Search using a pre-computed embedding vector.
**Inputs**: `vectorDB`, `namespace`, `index`, `embeddings` (all required), `llmMaxResults`.

### LLM_GET_EMBEDDINGS
Retrieve stored embeddings by document ID.
**Inputs**: `vectorDB`, `namespace`, `index`, `docId` (all required).
**Outputs**: `result` (array of floats).

### GENERATE_PDF
Convert markdown text to a PDF document. Built-in (Apache PDFBox); no external API key required. Supports full GitHub-Flavored Markdown — headings, tables, code blocks, lists, task lists, blockquotes, images (HTTP/HTTPS, `file://`, `data:`, relative paths), links, footnotes, strikethrough, inline formatting.

```json
{
  "name": "gen_pdf", "taskReferenceName": "pdf", "type": "GENERATE_PDF",
  "inputParameters": {
    "markdown": "${report.output.result}",
    "pageSize": "A4",
    "theme": "default",
    "baseFontSize": 11,
    "pdfMetadata": {
      "title": "${workflow.input.topic}",
      "author": "Conductor",
      "subject": "Auto-generated report"
    }
  }
}
```

| Parameter | Type | Required | Default | Description |
|-----------|------|:--------:|---------|-------------|
| `markdown` | string | ✅ | — | Markdown text to render |
| `pageSize` | string | ❌ | `A4` | `A4`, `LETTER`, `LEGAL`, `A3`, `A5` |
| `marginTop` / `marginRight` / `marginBottom` / `marginLeft` | number | ❌ | `72` | Margins in points (72 = 1 inch) |
| `theme` | string | ❌ | `default` | `default` or `compact` |
| `baseFontSize` | number | ❌ | `11` | Base font size in points |
| `outputLocation` | string | ❌ | auto | Output URI (e.g., `file:///tmp/report.pdf`). Defaults to payload store. |
| `pdfMetadata` | object | ❌ | — | `{title, author, subject, keywords}` |
| `imageBaseUrl` | string | ❌ | — | Base URL for resolving relative image paths in markdown |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `result.location` | string | URI of the generated PDF |
| `result.sizeBytes` | integer | Size of the generated PDF in bytes |
| `media` | array | `[{location, mimeType: "application/pdf"}]` |
| `finishReason` | string | `COMPLETED` on success |

Common pattern is LLM → PDF: an `LLM_CHAT_COMPLETE` task emits markdown into `output.result`, then `GENERATE_PDF` consumes `${report.output.result}` and writes the binary out.

### LIST_MCP_TOOLS
List available tools from an MCP (Model Context Protocol) server.
```json
{
  "name": "list_tools", "taskReferenceName": "mcp_tools", "type": "LIST_MCP_TOOLS",
  "inputParameters": {
    "mcpServer": "http://localhost:3001/mcp",
    "headers": {"Authorization": "Bearer ${workflow.input.mcpToken}"}
  }
}
```
**Inputs**: `mcpServer` (required), `headers`.
**Outputs**: `tools` (array of `{name, description, inputSchema}`).

### CALL_MCP_TOOL
Call a specific tool on an MCP server. All extra inputParameters are passed as tool arguments.
```json
{
  "name": "call_tool", "taskReferenceName": "mcp_call", "type": "CALL_MCP_TOOL",
  "inputParameters": {
    "mcpServer": "http://localhost:3001/mcp",
    "method": "get_weather",
    "location": "New York",
    "units": "fahrenheit"
  }
}
```
**Inputs**: `mcpServer`, `method` (both required), `headers`, plus any tool-specific parameters.
**Outputs**: `content` (array of result items), `isError`.

---

## Complete examples

### Example 1: Data pipeline with HTTP, transform, and approval

```json
{
  "name": "data_pipeline",
  "description": "Fetch, transform, and approve data",
  "version": 1,
  "schemaVersion": 2,
  "inputParameters": ["apiUrl", "authToken"],
  "tasks": [
    {
      "name": "fetch_data",
      "taskReferenceName": "fetch",
      "type": "HTTP",
      "inputParameters": {
        "http_request": {
          "uri": "${workflow.input.apiUrl}",
          "method": "GET",
          "headers": {"Authorization": "Bearer ${workflow.input.authToken}"}
        }
      }
    },
    {
      "name": "transform_data",
      "taskReferenceName": "transform",
      "type": "JSON_JQ_TRANSFORM",
      "inputParameters": {
        "data": "${fetch.output.response.body.items}",
        "queryExpression": "[.[] | {id: .id, name: .name, status: .status}]"
      }
    },
    {
      "name": "wait_for_approval",
      "taskReferenceName": "approval",
      "type": "WAIT"
    }
  ],
  "outputParameters": {
    "transformedData": "${transform.output.result}",
    "approvalStatus": "${approval.output.approved}"
  }
}
```

### Example 2: RAG workflow (search + AI chat)

```json
{
  "name": "rag_workflow",
  "description": "Retrieval-augmented generation: search knowledge base then answer",
  "version": 1,
  "schemaVersion": 2,
  "inputParameters": ["question"],
  "tasks": [
    {
      "name": "search_knowledge_base",
      "taskReferenceName": "search",
      "type": "LLM_SEARCH_INDEX",
      "inputParameters": {
        "vectorDB": "postgres-prod",
        "namespace": "kb",
        "index": "articles",
        "embeddingModelProvider": "openai",
        "embeddingModel": "text-embedding-3-small",
        "query": "${workflow.input.question}",
        "llmMaxResults": 3
      }
    },
    {
      "name": "generate_answer",
      "taskReferenceName": "answer",
      "type": "LLM_CHAT_COMPLETE",
      "inputParameters": {
        "llmProvider": "anthropic",
        "model": "claude-3-5-sonnet-20241022",
        "messages": [
          {"role": "system", "message": "Answer based on the following context: ${search.output.result}"},
          {"role": "user", "message": "${workflow.input.question}"}
        ],
        "temperature": 0.3
      }
    }
  ],
  "outputParameters": {
    "answer": "${answer.output.result}",
    "sources": "${search.output.result}"
  }
}
```

### Example 3: MCP tool call

```json
{
  "name": "mcp_weather_workflow",
  "description": "Call an MCP tool to get weather data",
  "version": 1,
  "schemaVersion": 2,
  "tasks": [
    {
      "name": "get_weather",
      "taskReferenceName": "weather",
      "type": "CALL_MCP_TOOL",
      "inputParameters": {
        "mcpServer": "http://localhost:3001/mcp",
        "method": "get_weather",
        "location": "${workflow.input.city}",
        "units": "fahrenheit"
      }
    }
  ]
}
```

---

## Visualization

To generate a Mermaid diagram of any workflow definition, see [visualization.md](visualization.md). It maps Conductor constructs (SWITCH, FORK_JOIN, DO_WHILE, WAIT, etc.) to flowchart syntax and covers the Conductor UI link format.
