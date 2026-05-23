# Example: Multi-Turn Chat Without Resending History (OpenAI / Azure)

OpenAI's Responses API stores the full conversation server-side, keyed by a `responseId`. By passing `previousResponseId` on the next `LLM_CHAT_COMPLETE` task, you reference the prior turn — and the new task's `messages` array only needs the **new** user message.

For long agent loops or multi-turn dialogues with a substantial system prompt or growing tool-call history, this saves a meaningful fraction of tokens (the system prompt + every prior turn no longer ride along on every call) and trims latency. For short two- or three-turn chats, the savings are marginal — choose the pattern that matches your portability needs first.

> **OpenAI and Azure OpenAI only.** Other providers ignore `previousResponseId`. For portable chains, keep accumulating `messages` (see [ai-agent-loop.md](ai-agent-loop.md)).

## Pattern

```
turn1 (LLM_CHAT_COMPLETE)           ← full system + first user message
  outputs: result, responseId
turn2 (LLM_CHAT_COMPLETE)           ← only the next user message
  previousResponseId: ${turn1.output.responseId}
turn3 (LLM_CHAT_COMPLETE)           ← only the next user message
  previousResponseId: ${turn2.output.responseId}
...
```

Each turn references the immediately preceding `responseId`. Conductor passes that ID to OpenAI's Responses API, which reconstructs the conversation state on the provider side.

## Workflow

See [workflows/llm-chaining.json](workflows/llm-chaining.json):

```json
{
  "name": "multi_turn_chain",
  "description": "Two-step conversation using previousResponseId",
  "version": 1,
  "schemaVersion": 2,
  "inputParameters": ["topic"],
  "tasks": [
    {
      "name": "first_turn",
      "taskReferenceName": "turn1",
      "type": "LLM_CHAT_COMPLETE",
      "inputParameters": {
        "llmProvider": "openai",
        "model": "gpt-4o",
        "messages": [
          {"role": "system", "message": "You are a technical architect. Be concise."},
          {"role": "user", "message": "Design a high-level architecture for: ${workflow.input.topic}"}
        ],
        "temperature": 0.3,
        "maxTokens": 2000
      }
    },
    {
      "name": "follow_up",
      "taskReferenceName": "turn2",
      "type": "LLM_CHAT_COMPLETE",
      "inputParameters": {
        "llmProvider": "openai",
        "model": "gpt-4o",
        "messages": [
          {"role": "user", "message": "Now list the key risks and mitigations for this architecture."}
        ],
        "previousResponseId": "${turn1.output.responseId}",
        "temperature": 0.3,
        "maxTokens": 2000
      }
    }
  ],
  "outputParameters": {
    "architecture": "${turn1.output.result}",
    "risks": "${turn2.output.result}"
  }
}
```

Run:

```bash
conductor workflow create examples/workflows/llm-chaining.json
conductor workflow start -w multi_turn_chain -i '{"topic": "real-time fraud detection pipeline"}' --sync
```

## When to use this vs accumulated `messages`

| Use `previousResponseId` (OpenAI/Azure) | Use accumulated `messages` |
|----------------------------------------|----------------------------|
| Chains exclusively against an OpenAI model | Mixed providers, or want to swap providers later |
| Want minimum token cost on each turn | Need the workflow execution to be portable |
| OK with provider-side state retention (~30 days) | Need durable chat history across long-lived workflows |
| Have access to the OpenAI Responses API | Using a base URL or proxy without Responses API support |

The two patterns combine: in an agent loop, you can accumulate **summarized** context in `messages` for portability AND set `previousResponseId` for fast iteration within a single execution. If portability matters most, stick with the accumulated-messages pattern from [ai-agent-loop.md](ai-agent-loop.md).

## Gotchas

- **Provider switch breaks the chain.** Every turn must point at the same provider (and account) that produced the `responseId`. Mid-chain swap to Anthropic or Gemini will fail or silently drop the chain.
- **`responseId` lifetime.** OpenAI's documented retention is ~30 days. Conductor doesn't replay or restore chains; once the upstream forgets the ID, subsequent turns lose context. For long-lived agent workflows, fall back to accumulated messages.
- **No mid-chain edits.** Once a turn is in the chain, you cannot rewrite earlier turns. If you need to revise the system message, start a new chain.
- **`tools` calling and chaining work together.** A turn can both reference `previousResponseId` and define new tools; the model will see the tools and may emit `finishReason: TOOL_CALLS`. Handle the tool call as you normally would, then continue the chain by referencing **that** task's `responseId` on the next turn.

## Combining with the agentic loop

Inside a `DO_WHILE` agent loop ([ai-agent-loop.md](ai-agent-loop.md)), keep `previousResponseId` on every chat task. The loop's chat task reads `${workflow.variables.previous_response_id}`; after each LLM call, a `SET_VARIABLE` updates it to the just-completed task's `${think.output.responseId}`. The `messages` array stays minimal (just the new tool result or next user prompt).

This combines durable workflow state (workflow variables persist across restarts) with cheap iteration (only the new turn is sent per call). It's strictly an OpenAI optimization — for portability, ship the accumulated-messages version.
