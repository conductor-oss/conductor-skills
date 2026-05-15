# Example: Autonomous Agent Loop (ReAct Pattern)

An LLM-driven agent that **thinks**, **acts**, and **observes** in a loop until it decides it's done. Built with `DO_WHILE` wrapping an LLM_CHAT_COMPLETE → SWITCH → CALL_MCP_TOOL inner sequence.

Use this when the answer requires multiple tool calls in sequence — e.g., "look up the customer, then their last order, then refund the matching line item." A single-shot agent ([ai-agent-mcp.md](ai-agent-mcp.md)) only plans once; an agent loop replans every iteration with the accumulated tool results in context.

## Pipeline

```
DO_WHILE {
  think  (LLM_CHAT_COMPLETE)  →  emits { done, method?, arguments?, answer? }
  act    (SWITCH on done)     →  CALL_MCP_TOOL if not done, NOOP if done
} until think says done == true
```

The whole loop is one workflow task. Each iteration is a durable checkpoint — a crash mid-tool-call resumes from the last completed iteration **without replaying earlier LLM calls**.

## Workflow

See [workflows/ai-agent-loop.json](workflows/ai-agent-loop.json). Key tasks:

```json
{
  "name": "agent_loop",
  "taskReferenceName": "loop",
  "type": "DO_WHILE",
  "loopCondition": "if ($.loop['iteration'] < 10 && $.loop[$.loop['iteration']].think.output.result.done != true) { true; } else { false; }",
  "loopOver": [
    {
      "name": "think",
      "taskReferenceName": "think",
      "type": "LLM_CHAT_COMPLETE",
      "inputParameters": {
        "llmProvider": "openai",
        "model": "gpt-4o-mini",
        "messages": [
          {"role": "system", "message": "You are an agent. Tools: ${workflow.input.tools}. Previous results: ${loop.output}. Decide next step. Respond as JSON: { done: bool, method?: string, arguments?: object, answer?: string }."},
          {"role": "user", "message": "${workflow.input.task}"}
        ],
        "temperature": 0.1,
        "maxTokens": 500
      }
    },
    {
      "name": "act",
      "taskReferenceName": "act",
      "type": "SWITCH",
      "evaluatorType": "javascript",
      "expression": "$.done ? 'finish' : 'call_tool'",
      "inputParameters": {
        "done": "${think.output.result.done}"
      },
      "decisionCases": {
        "call_tool": [{
          "name": "execute",
          "taskReferenceName": "execute",
          "type": "CALL_MCP_TOOL",
          "inputParameters": {
            "mcpServer": "${workflow.input.mcpServer}",
            "method": "${think.output.result.method}",
            "arguments": "${think.output.result.arguments}"
          }
        }],
        "finish": [{"name": "done", "taskReferenceName": "done", "type": "NOOP"}]
      }
    }
  ],
  "inputParameters": {
    "loop": "${loop.output}"
  }
}
```

Then a single task after the loop pulls out the final answer:

```json
{
  "name": "final_answer",
  "taskReferenceName": "final",
  "type": "INLINE",
  "inputParameters": {
    "evaluatorType": "graaljs",
    "expression": "function e() { var i = $.loop_output['iteration']; return $.loop_output[i].think.output.result.answer; } e();",
    "loop_output": "${loop.output}"
  }
}
```

## Run

```bash
conductor workflow create examples/workflows/ai-agent-loop.json
conductor workflow start -w autonomous_agent -i '{
  "task": "Find user 42 and refund their last order.",
  "mcpServer": "http://localhost:3001/mcp",
  "tools": "search_user, get_orders, refund_order"
}' --sync
```

## The `$.loop_ref` self-reference pattern

`"loop": "${loop.output}"` in `inputParameters` wires the loop task's own output back into its `loopCondition` scope. This looks like a typo — referencing a task before it has output — but it's the canonical pattern. Conductor resolves it lazily at each iteration, exposing `iteration` and all prior iterations' task outputs (`$.loop[1].think.output...`, `$.loop[2].think.output...`).

See [do-while-loop.md](do-while-loop.md) for more detail on this pattern.

## Critical guardrails

- **Cap iterations.** The condition above includes `$.loop['iteration'] < 10` as a hard cap. Without it, a buggy "I'm not done yet" reply spins forever and burns LLM budget. The optimization checklist ([../references/optimization.md](../references/optimization.md)) flags unbounded loops as **CRITICAL** (rule B5).
- **Set a workflow timeout** (`timeoutSeconds` + `timeoutPolicy: TIME_OUT_WF`). A 10-iteration cap with no per-iteration timeout can still hang on a slow tool call.
- **Token budget per iteration is enforced by `maxTokens`** — the loop itself has no token budget. For cost control, multiply: 10 iterations × 500 max tokens × $/token.

## When to use the loop vs the single-shot

| Use single-shot ([ai-agent-mcp.md](ai-agent-mcp.md)) | Use the loop |
|------------------------------------------------------|--------------|
| Answer always needs exactly one tool call | Answer needs an unknown number of tool calls |
| You can constrain the model to pick ONE action | Tasks chain — output of one tool informs the next |
| You want strict, audit-friendly determinism | Some exploration is acceptable |
| Latency matters (one LLM call + one tool call) | Total budget tolerates 5–10 LLM round trips |
