# Example: Hand-wired agent loop (ReAct) — under the hood / manual control

> **The default way to build an agent is now a Conductor Agent** — see [../references/agents.md](../references/agents.md) and [agent-deploy-and-invoke.md](agent-deploy-and-invoke.md). The server's compiler emits exactly the shape below (`{name}_init_state` SET_VARIABLE → `{name}_loop` DO_WHILE { `{name}_llm` → guardrails → tool SWITCH → FORK_JOIN_DYNAMIC → merge } → `{name}_synth_output`), so this page is also how you read a compiled agent's execution view. Hand-wire only when the compiler cannot express what you need: (a) a custom termination predicate or non-LLM routing between iterations, (b) OpenAI `previousResponseId` chaining, (c) several models per iteration, (d) the server has agents disabled or you must ship a single JSON file. Say which reason applies (optimization rule F4). This page remains the worked example for [../references/graaljs-gotchas.md](../references/graaljs-gotchas.md) and [../references/template-resolution.md](../references/template-resolution.md).


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

Each line exists because the obvious alternative fails subtly (the agent compiler makes the same choices for you).

1. **`evaluatorType: "graaljs"` on the DO_WHILE.** The `"javascript"` alias works for INLINE but has failed for `loopCondition` on some cluster versions; set `"graaljs"` explicitly.
2. **IIFE `loopCondition` with an iteration cap:** `(function(){ return $.agent_loop['iteration'] < $.max_iterations && $.final_response === ''; })();` — an IIFE returns a clean boolean (the `if {true} else {false}` statement form is fragile); the cap is mandatory (rule B5); `$.final_response === ''` exits the moment `finalize` fires.
3. **`inputParameters` wires for the condition:** `"agent_loop": "${agent_loop.output}"` (the canonical lazy self-reference exposing `iteration`), plus `max_iterations` and `final_response` plumbed in explicitly — `$.workflow.input.*` / `$.workflow.variables.*` are **not in scope** inside `loopCondition` (`TypeError: Cannot read property "input" from undefined`).
4. **`LLM_CHAT_COMPLETE` with `jsonOutput: true`** makes `output.result` a parsed object so the SWITCH can branch on `action`. Caveats: the strict Jackson parse fails on markdown fences (Claude emits them — prefer provider-native structured output or `jsonOutput: false` + substring extraction); the `messages` schema is `{role, message}` not `{role, content}` (`Content must not be null for SYSTEM or USER messages`); `message` must be a **string** — an object is Java-`toString`ed into `{key=value}` garbage, so stringify tool results with JQ first (step 6).
5. **SWITCH with `defaultCase: []`.** A default that calls `finalize` would overwrite `final_response` with garbage whenever the model emits an unknown action; an empty default skips the junk and the loop tries again.
6. **`JSON_JQ_TRANSFORM` stringifies and accumulates in one step:** `.current + [{"role":"assistant","message":"Called get_weather."}, {"role":"user","message":("Tool result: " + (.tool_result | tojson))}]`. `tojson` avoids the Java-Map proxy trap (`JSON.stringify` on a proxy returns `"{}"`, `String(...)` returns `{k=v}`); `.current + [...]` appends to the history instead of replacing it (a fresh two-entry `SET_VARIABLE` would wipe prior turns). The JQ input is the whole `inputParameters` map minus `queryExpression` — see [../references/graaljs-gotchas.md](../references/graaljs-gotchas.md) Rule 3 and [../references/template-resolution.md](../references/template-resolution.md) Pitfall 2.
7. **HTTP tool task `optional: true`** (+ `retryCount` on its task def) keeps the loop alive when the service flakes; for finer control branch `route` on `call_weather.output.response.statusCode` and feed the model a "service unavailable" message.
8. **Chat history in `workflow.variables`** (JQ-concat then `SET_VARIABLE`): the model needs the full conversation every iteration, `${workflow.variables.messages}` is unambiguous from inside the loop, and it survives a restart. Variables are workflow-global — keep only cross-iteration state there.

## Run

```bash
conductor workflow create examples/workflows/ai-agent-loop.json
conductor workflow start -w autonomous_agent --sync -i '{"question":"What is the weather in San Francisco?","max_iterations":5}'
```

## OpenAI optimization — `previousResponseId` chaining

Committed to OpenAI / Azure OpenAI? Chain turns through the Responses API instead of re-sending the accumulated `messages` every iteration: keep `previous_response_id` in `workflow.variables` (empty at first), pass `"previousResponseId": "${workflow.variables.previous_response_id}"` into `think`, `SET_VARIABLE` it to `${think.output.responseId}` after each turn, and send only the new content in `messages`. Savings scale with how much context you would otherwise re-send. Keep the message-accumulation scaffold for portable workflows (mixed providers, proxies without the Responses API, runs that outlive OpenAI's ~30-day response retention). Full pattern and caveats: [llm-chaining.md](llm-chaining.md).

## A simpler MCP variant

Without history accumulation the loop collapses to `LLM_CHAT_COMPLETE` (prompt carries `Previous results: ${agent_loop.output}`) → `SWITCH` → one `CALL_MCP_TOOL` or `NOOP`, `defaultCase: []`. Enough when the model reliably emits `{action: "answer"}`; use the full scaffold for durable history, retries, or malformed-output handling.

## Critical guardrails

Cap iterations (`$.iteration < N` **and** the early-exit predicate) or a buggy "not done yet" reply spins forever; set `timeoutSeconds` + `timeoutPolicy: TIME_OUT_WF` (a slow tool call can still hang a capped loop); cost = iterations × `maxTokens` — the loop has no token budget of its own; no secrets in `workflow.input` (use `${workflow.secrets.X}` or worker env — inputs show in the execution view); keep `defaultCase` empty.

## Built-in tools as an alternative to MCP

`LLM_CHAT_COMPLETE` enables provider-native tools with a boolean — `webSearch`, `codeInterpreter`, `fileSearchVectorStoreIds` (OpenAI), `googleSearchRetrieval` (Gemini) — so a "search and run code" loop needs no MCP server; add `tools: [...]` for custom functions. Matrix: [llm-chat.md](llm-chat.md).

## When to use the loop vs the single-shot

| Use single-shot ([ai-agent-mcp.md](ai-agent-mcp.md)) | Use a Conductor Agent ([agents.md](../references/agents.md)) | Use this hand-wired loop |
|---|---|---|
| Answer always needs exactly one tool call | Unknown number of tool calls; tools are functions in your code; approval gates, guardrails, multi-agent, streaming, reuse by name | Same, but you need a custom loop condition, non-LLM steps between turns, `previousResponseId`, or JSON-only |
| Model constrained to ONE action; latency matters | Native function calling; budget tolerates N round trips (`max_turns`) | JSON `{action}` routing convention you own and maintain |
