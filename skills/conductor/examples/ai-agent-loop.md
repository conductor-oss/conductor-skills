# Example: Autonomous Agent Loop (ReAct Pattern)

An LLM-driven agent that **thinks**, **acts**, and **observes** in a loop until it decides it's done. Built with `DO_WHILE` wrapping an `LLM_CHAT_COMPLETE → SWITCH → tool task` inner sequence.

Use this when the answer requires multiple tool calls in sequence — e.g., "look up the customer, then their last order, then refund the matching line item." A single-shot agent ([ai-agent-mcp.md](ai-agent-mcp.md)) only plans once; an agent loop replans every iteration with the accumulated tool results in context.

> This page also serves as the worked example for everything in [../references/graaljs-gotchas.md](../references/graaljs-gotchas.md) and [../references/template-resolution.md](../references/template-resolution.md). If you are wiring up an agentic loop from scratch, read those two pages first.

## Pipeline

```
init_messages (SET_VARIABLE)                              ← seed system + user messages
agent_loop (DO_WHILE, graaljs, IIFE, iter cap):
    think (LLM_CHAT_COMPLETE, jsonOutput: true)           ← emits { action, ... }
    route (SWITCH on action):
        case "call_tool":
            call_tool (HTTP, optional: true)                          ← external call
            build_next_messages (JSON_JQ_TRANSFORM, .current + [...])  ← append to chat history
            update_messages (SET_VARIABLE)                            ← write merged array back
        case "answer":
            finalize (SET_VARIABLE final_response)
        defaultCase: []                                               ← empty — see below
until think says action == "answer", or iter cap
```

The whole loop is one workflow task. Each iteration is a durable checkpoint — a crash mid-tool-call resumes from the last completed iteration **without replaying earlier LLM calls**.

## Workflow

See [workflows/ai-agent-loop.json](workflows/ai-agent-loop.json) for the full file. The key shape:

```json
{
  "name": "autonomous_agent",
  "schemaVersion": 2,
  "inputParameters": ["question", "max_iterations"],
  "variables": { "messages": [], "final_response": "" },
  "tasks": [
    {
      "name": "init_messages",
      "taskReferenceName": "init_messages",
      "type": "SET_VARIABLE",
      "inputParameters": {
        "messages": [
          {"role": "system", "message": "You are an agent. Tools available: get_weather(city). Respond ONLY as JSON: {\"action\": \"call_tool\", \"tool\": \"get_weather\", \"args\": {...}} OR {\"action\": \"answer\", \"answer\": \"...\"}."},
          {"role": "user", "message": "${workflow.input.question}"}
        ]
      }
    },
    {
      "name": "agent_loop",
      "taskReferenceName": "agent_loop",
      "type": "DO_WHILE",
      "evaluatorType": "graaljs",
      "loopCondition": "(function(){ return $.agent_loop['iteration'] < $.max_iterations && $.final_response === ''; })();",
      "inputParameters": {
        "agent_loop": "${agent_loop.output}",
        "max_iterations": "${workflow.input.max_iterations}",
        "final_response": "${workflow.variables.final_response}"
      },
      "loopOver": [
        {
          "name": "think",
          "taskReferenceName": "think",
          "type": "LLM_CHAT_COMPLETE",
          "inputParameters": {
            "llmProvider": "openai",
            "model": "gpt-4o-mini",
            "messages": "${workflow.variables.messages}",
            "temperature": 0.1,
            "maxTokens": 500,
            "jsonOutput": true
          }
        },
        {
          "name": "route",
          "taskReferenceName": "route",
          "type": "SWITCH",
          "evaluatorType": "graaljs",
          "expression": "$.action",
          "inputParameters": { "action": "${think.output.result.action}" },
          "decisionCases": {
            "call_tool": [
              {
                "name": "call_weather",
                "taskReferenceName": "call_weather",
                "type": "HTTP",
                "optional": true,
                "inputParameters": {
                  "http_request": {
                    "uri": "https://wttr.in/${think.output.result.args.city}?format=j1",
                    "method": "GET"
                  }
                }
              },
              {
                "name": "build_next_messages",
                "taskReferenceName": "build_next_messages",
                "type": "JSON_JQ_TRANSFORM",
                "inputParameters": {
                  "current": "${workflow.variables.messages}",
                  "tool_result": "${call_weather.output.response.body}",
                  "queryExpression": ".current + [{\"role\": \"assistant\", \"message\": \"Called get_weather.\"}, {\"role\": \"user\", \"message\": (\"Tool result: \" + (.tool_result | tojson))}]"
                }
              },
              {
                "name": "update_messages",
                "taskReferenceName": "update_messages",
                "type": "SET_VARIABLE",
                "inputParameters": {
                  "messages": "${build_next_messages.output.result}"
                }
              }
            ],
            "answer": [
              {
                "name": "finalize",
                "taskReferenceName": "finalize",
                "type": "SET_VARIABLE",
                "inputParameters": {
                  "final_response": "${think.output.result.answer}"
                }
              }
            ]
          },
          "defaultCase": []
        }
      ]
    }
  ],
  "outputParameters": {
    "answer": "${workflow.variables.final_response}",
    "iterations": "${agent_loop.output.iteration}"
  },
  "timeoutSeconds": 600,
  "timeoutPolicy": "TIME_OUT_WF"
}
```

## Why each piece is shaped the way it is

The agentic loop touches every Conductor gotcha at once. Each line of the example exists because the obvious alternative fails subtly.

### 1. `evaluatorType: "graaljs"` on the DO_WHILE task

For INLINE tasks, the platform aliases `"javascript"` and `"graaljs"`. For DO_WHILE's `loopCondition`, the alias has been reported to fail on some cluster versions — set `"graaljs"` explicitly here. Older docs omit it; that's where most "loop condition fails at runtime" reports trace back to.

### 2. IIFE `loopCondition` with iteration cap

```javascript
(function(){ return $.agent_loop['iteration'] < $.max_iterations && $.final_response === ''; })();
```

- **IIFE** returns a clean boolean. The `if (x) { true; } else { false; }` statement form is fragile across cluster versions.
- **Iteration cap** is mandatory. The optimization checklist flags unbounded loops as CRITICAL (rule B5).
- **`$.final_response === ''` early-exit** lets the loop terminate the moment the `finalize` branch fires, instead of running another empty iteration. `final_response` is read via `${workflow.variables.final_response}` — `$.workflow.*` is **not** in scope inside the condition, so we plumb it through `inputParameters`.

### 3. `inputParameters` wires for `loopCondition`

```json
"inputParameters": {
  "agent_loop": "${agent_loop.output}",
  "max_iterations": "${workflow.input.max_iterations}",
  "final_response": "${workflow.variables.final_response}"
}
```

`agent_loop: "${agent_loop.output}"` is the canonical self-reference pattern — it looks like a typo (referencing the task before it has output), but Conductor resolves it lazily each iteration, exposing `iteration` and per-iteration body outputs.

`max_iterations` and `final_response` are plumbed in because `$.workflow.input.*` and `$.workflow.variables.*` are **NOT in scope** inside `loopCondition`. Reading them with `$` would throw `TypeError: Cannot read property "input"/"variables" from undefined`.

### 4. `LLM_CHAT_COMPLETE` with `jsonOutput: true`

`output.result` is the **parsed object** when `jsonOutput: true`, the **raw string** when `false`. Downstream SWITCH branches on `action`, so a parsed object is what we want.

**Caveats:**

- Conductor's strict Jackson parse fails hard on markdown fences (`` ```json ... ``` ``). Claude emits these regardless of system-prompt instructions. If you target Claude, prefer provider-native structured output (Anthropic tool-use) or keep `jsonOutput: false` and substring-extract the JSON downstream.
- The `messages` schema is `{role, message}` — **NOT** `{role, content}` (which is what Anthropic and OpenAI's native APIs use). Mixing this up gives `Content must not be null for SYSTEM or USER messages`.
- `messages` must contain **strings** in the `message` field, never structured objects. Conductor will Java-`toString` an object into `{key=value}` on the way to the provider, producing garbage in the chat history. To embed tool results, route through `JSON_JQ_TRANSFORM` with `tojson` first (step 6 below).

### 5. SWITCH with empty `defaultCase`

```json
"defaultCase": []
```

Leave `defaultCase` empty unless you have a meaningful no-op handler. A `defaultCase` that calls `finalize` will fire whenever the LLM emits an unrecognized action, **overwriting `final_response` with garbage**. With an empty defaultCase, junk replies are silently skipped and the loop tries again next iteration.

### 6. `JSON_JQ_TRANSFORM` to stringify AND accumulate in one step

```json
{
  "type": "JSON_JQ_TRANSFORM",
  "inputParameters": {
    "current": "${workflow.variables.messages}",
    "tool_result": "${call_weather.output.response.body}",
    "queryExpression": ".current + [{\"role\": \"assistant\", \"message\": \"Called get_weather.\"}, {\"role\": \"user\", \"message\": (\"Tool result: \" + (.tool_result | tojson))}]"
  }
}
```

Two things happen in this single JQ task:

1. **The structured HTTP body is stringified** via `(.tool_result | tojson)`. This is essential — embedding the raw Java-Map-backed object in a `message` field would Java-`toString` it into `{key=value}` garbage. The obvious INLINE alternative also fails: `JSON.stringify` on a Java-Map-backed proxy returns `"{}"`, `String(...)` returns `{k=v}` (Java's `Map.toString`). JQ operates on JSON natively and bypasses the entire JS/Java-proxy stack.
2. **The new messages are concatenated onto the existing chat history** via `.current + [...]`. This preserves the system prompt and prior turns. The naive `SET_VARIABLE` that writes a fresh two-entry array **replaces** the variable instead of appending — every iteration the LLM would lose its history and produce nonsense.

The output (`${build_next_messages.output.result}`) is the full new messages array; `update_messages` (SET_VARIABLE) writes it back to `workflow.variables.messages`. Next iteration's `think` sees the complete grown history.

JQ input semantics: the entire `inputParameters` map (minus `queryExpression`) is the JQ input — reference fields as `.current`, `.tool_result`. See [../references/graaljs-gotchas.md](../references/graaljs-gotchas.md) Rule 3 and [../references/template-resolution.md](../references/template-resolution.md) Pitfall 2.

### 7. HTTP tool task: `optional: true` + retry on the task def

```json
{ "type": "HTTP", "optional": true, ... }
```

`optional: true` keeps the loop alive if the external service flakes. Combined with `retryCount` on the HTTP task definition (or accepting that a 5xx is recoverable next iteration), the agent treats tool failure as a signal to retry or pick a different action, not a workflow-killing error.

For more sophisticated failure handling, branch `route` on `call_weather.output.response.statusCode` and prepare a "service unavailable" message for the LLM instead of appending the raw error.

### 8. Workflow `variables` for chat history accumulation

Each iteration grows `workflow.variables.messages` via the JQ-concat-then-SET_VARIABLE pair from step 6. We persist chat history in a workflow variable, outside the loop's per-iteration outputs, because:

- The LLM needs the full conversation each iteration.
- Reading `${workflow.variables.messages}` from inside the loop is clean and unambiguous; pulling from the loop's nested per-iteration outputs is fragile.
- It survives a workflow restart.

The trade-off: variables are global to the workflow. Don't put one-shot data there — only state that needs to span iterations.

## Run

```bash
conductor workflow create examples/workflows/ai-agent-loop.json
conductor workflow start -w autonomous_agent -i '{
  "question": "What is the weather in San Francisco?",
  "max_iterations": 5
}' --sync
```

## OpenAI optimization — `previousResponseId` chaining

If your loop is committed to OpenAI (or Azure OpenAI), you can reduce per-iteration token cost by chaining via the Responses API instead of sending the accumulated `messages` array every iteration. Each chat task sends only the new content and references the prior turn's `responseId`. The savings scale with how much prior context you'd otherwise be re-sending — meaningful for long loops with a substantial system prompt; marginal for short ones.

**Changes from the canonical scaffold above:**

1. Add `previous_response_id` to `workflow.variables` (initialized empty).
2. In the `think` task, add `"previousResponseId": "${workflow.variables.previous_response_id}"`. On iteration 1 this is empty and the provider treats it as a fresh chain; on subsequent iterations it points at the prior task's `responseId`.
3. After `think`, add a `SET_VARIABLE` that updates `workflow.variables.previous_response_id = ${think.output.responseId}`.
4. Shrink `messages` — on each iteration you only need the latest user content (the tool result, the next instruction), not the system prompt or prior turns.

The full message-accumulation scaffold above remains the right default for **portable** workflows (mixed providers, base URLs / proxies without Responses API, long-running workflows that outlive OpenAI's response retention window — currently ~30 days). Use chaining only when you're committed to OpenAI and the savings matter.

See [llm-chaining.md](llm-chaining.md) for the full pattern, caveats around provider lock-in, and the `responseId` lifetime.

## A simpler MCP variant

If you have an MCP server and don't need the chat-history-accumulation pattern, the loop collapses considerably — system message includes `Previous results: ${agent_loop.output}` and the tool branch is just a single `CALL_MCP_TOOL`. That was the previous shape of this example; it works for simple flows but breaks down for longer chains and harder failure modes.

```json
"loopOver": [
  { "type": "LLM_CHAT_COMPLETE", "...": "...passes ${agent_loop.output} into the prompt..." },
  { "type": "SWITCH", "decisionCases": {
      "call_tool": [{ "type": "CALL_MCP_TOOL", "...": "..." }],
      "answer":    [{ "type": "NOOP", "...": "..." }]
  }, "defaultCase": [] }
]
```

Choose the variant by how the loop terminates: if the LLM reliably emits `{ action: "answer", ... }` and you only ever route on the latest LLM call, the MCP variant is enough. If you need durable chat history, retries, or paranoid handling of malformed LLM output, use the full scaffold above.

## Critical guardrails

- **Cap iterations.** Both as an explicit `$.iteration < N` clause in the condition AND an `early-exit on final_response` predicate. Without a cap, a buggy "I'm not done yet" reply spins forever and burns LLM budget.
- **Set a workflow timeout** (`timeoutSeconds` + `timeoutPolicy: TIME_OUT_WF`). A 10-iteration cap with no per-iteration timeout can still hang on a slow tool call.
- **Token budget per iteration is enforced by `maxTokens`** — the loop itself has no token budget. For cost control, multiply: 10 iterations × 500 max tokens × $/token.
- **No secrets in `workflow.input`.** API keys, signing secrets, etc. go in `${workflow.secrets.X}` (Orkes) or worker env. Workflow inputs are visible in the execution view.
- **Empty SWITCH `defaultCase`** unless you have a real no-op handler.

## Built-in tools as an alternative to MCP

Recent Conductor releases let `LLM_CHAT_COMPLETE` enable provider-native tools with a boolean — no MCP server or worker needed:

- `webSearch: true` (OpenAI / Anthropic / Gemini) — real-time information
- `codeInterpreter: true` (OpenAI / Anthropic / Gemini) — sandboxed Python/JS execution
- `fileSearchVectorStoreIds: ["vs_..."]` (OpenAI) — search through pre-uploaded documents
- `googleSearchRetrieval: true` (Gemini) — Google Search grounding

For agent loops where the "tools" are just "web search and run some code," skip the MCP server entirely and set these on every `think` task. Combine with `tools: [...]` (function calling) for custom tools alongside the built-ins.

See [llm-chat.md](llm-chat.md) for the full list and provider matrix.

## When to use the loop vs the single-shot

| Use single-shot ([ai-agent-mcp.md](ai-agent-mcp.md)) | Use the loop |
|------------------------------------------------------|--------------|
| Answer always needs exactly one tool call | Answer needs an unknown number of tool calls |
| You can constrain the model to pick ONE action | Tasks chain — output of one tool informs the next |
| You want strict, audit-friendly determinism | Some exploration is acceptable |
| Latency matters (one LLM call + one tool call) | Total budget tolerates 5–10 LLM round trips |
