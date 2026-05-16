# Example: AI Agent with MCP Tools

A 4-task agent that discovers tools from an MCP server, plans an action with an LLM, calls the chosen tool, then summarizes the result for the user. This is the canonical "first AI agent" pattern from the [Orkes docs](https://docs.conductor-oss.org/devguide/ai/first-ai-agent.html).

## Pipeline

```
LIST_MCP_TOOLS → LLM_CHAT_COMPLETE (plan) → CALL_MCP_TOOL → LLM_CHAT_COMPLETE (summarize)
```

The agent is **linear, deterministic, durable**: every task is a Conductor checkpoint. If the tool call or the summarizer crashes, the workflow resumes from the last completed task — no replay of the planning LLM call.

## Prerequisites

1. **An MCP server** reachable from Conductor. For local dev: `mcp-testkit --transport http` listens on `http://localhost:3001/mcp`.
2. **An LLM provider** with its API key set on the Conductor server:
   ```bash
   export OPENAI_API_KEY=sk-...
   # or
   export ANTHROPIC_API_KEY=sk-ant-...
   ```
   Conductor auto-enables providers when their API key is set — no separate registration in OSS.

## Workflow

See [workflows/ai-agent-mcp.json](workflows/ai-agent-mcp.json). Key tasks:

```json
{
  "name": "discover_tools",
  "taskReferenceName": "discover",
  "type": "LIST_MCP_TOOLS",
  "inputParameters": {
    "mcpServer": "http://localhost:3001/mcp"
  }
},
{
  "name": "plan_action",
  "taskReferenceName": "plan",
  "type": "LLM_CHAT_COMPLETE",
  "inputParameters": {
    "llmProvider": "openai",
    "model": "gpt-4o-mini",
    "messages": [
      {"role": "system", "message": "You are an AI agent. Available tools: ${discover.output.tools}. Pick exactly one tool and respond as JSON with fields `method` and `arguments`."},
      {"role": "user", "message": "${workflow.input.task}"}
    ],
    "temperature": 0.1,
    "maxTokens": 500
  }
},
{
  "name": "execute_tool",
  "taskReferenceName": "execute",
  "type": "CALL_MCP_TOOL",
  "inputParameters": {
    "mcpServer": "http://localhost:3001/mcp",
    "method": "${plan.output.result.method}",
    "arguments": "${plan.output.result.arguments}"
  }
},
{
  "name": "summarize_result",
  "taskReferenceName": "summarize",
  "type": "LLM_CHAT_COMPLETE",
  "inputParameters": {
    "llmProvider": "openai",
    "model": "gpt-4o-mini",
    "messages": [
      {"role": "user", "message": "The user asked: \"${workflow.input.task}\". Tool returned: ${execute.output.content}. Reply in one short paragraph."}
    ],
    "maxTokens": 500
  }
}
```

## Run

```bash
conductor workflow create examples/workflows/ai-agent-mcp.json
conductor workflow start -w my_first_agent -i '{"task": "What is the weather in San Francisco?"}' --sync
```

Or hit the REST API directly for synchronous execution:

```bash
curl -s -X POST 'http://localhost:8080/api/workflow/execute/my_first_agent/1' \
  -H 'Content-Type: application/json' \
  -d '{"task": "What is the weather in San Francisco?"}' | jq
```

## Output

```
${plan.output.result}       → the LLM's chosen action (parsed JSON: method + arguments)
${execute.output.content}   → raw output from the MCP tool
${summarize.output.result}  → final natural-language answer for the user
```

## Adding human-in-the-loop

Insert a `HUMAN` task between `plan` and `execute` to require approval before any tool call:

```json
{
  "name": "approve",
  "taskReferenceName": "approve",
  "type": "HUMAN",
  "inputParameters": {
    "plannedAction": "${plan.output.result}",
    "userTask": "${workflow.input.task}"
  }
}
```

The workflow pauses indefinitely until signaled. Approve via:

```bash
conductor task signal-sync --workflow-id {id} --task-ref approve --status COMPLETED --output '{"approved": true}'
```

See [signal-wait-task.md](signal-wait-task.md) for the signaling pattern.

## Patterns

- **Two LLM calls, two purposes.** First call plans (deterministic, low-temperature, JSON-shaped output). Second call summarizes (natural language for the user). Splitting them lets you swap models per role — small model for planning, larger for summary, or vice versa.
- **JSON-shaped LLM output.** `${plan.output.result.method}` works because Conductor parses the LLM response as JSON when the model emits one. Make the system prompt require JSON. Use `temperature: 0.1` to keep it deterministic.
- **Durable checkpoints.** Each task is a save point. A crashed MCP call resumes without re-running the planner.
- **Tool surface from `LIST_MCP_TOOLS`.** The agent learns its capabilities at runtime — change the MCP server's exposed tools and the workflow adapts without redeploy.
