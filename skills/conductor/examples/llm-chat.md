# Example: Minimum LLM Workflow

The smallest useful AI workflow — one `LLM_CHAT_COMPLETE` task. Useful as a building block for prompts that don't need tools, retrieval, or loops.

> Conductor auto-enables LLM providers when their API key is set in the server's environment (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.). No separate provider registration needed in OSS.

## Workflow

See [workflows/llm-chat.json](workflows/llm-chat.json):

```json
{
  "name": "summarize_text",
  "tasks": [{
    "name": "summarize",
    "taskReferenceName": "summarize",
    "type": "LLM_CHAT_COMPLETE",
    "inputParameters": {
      "llmProvider": "openai",
      "model": "gpt-4o-mini",
      "messages": [
        {"role": "system", "message": "You summarize text in one sentence."},
        {"role": "user", "message": "${workflow.input.text}"}
      ],
      "temperature": 0.3,
      "maxTokens": 200
    }
  }],
  "outputParameters": {
    "summary": "${summarize.output.result}",
    "tokensUsed": "${summarize.output.tokenUsed}"
  }
}
```

## Run

```bash
conductor workflow create examples/workflows/llm-chat.json
conductor workflow start -w summarize_text -i '{"text": "Conductor is a workflow orchestration platform. It supports SIMPLE tasks, HTTP, SWITCH, FORK_JOIN, AI tasks, and more. Workflows are durable — they survive worker crashes by replaying from last completed task."}' --sync
```

The `--sync` flag waits for completion and returns the workflow result inline. For long-running prompts (large models, long outputs), drop `--sync` and poll via `conductor workflow get-execution`.

## Output shape

`LLM_CHAT_COMPLETE` returns:

- `result` — the response text (string)
- `finishReason` — `STOP`, `LENGTH`, or `TOOL_CALLS`
- `tokenUsed`, `promptTokens`, `completionTokens` — token accounting
- `toolCalls` — present if the model invoked a tool (see [ai-agent-mcp.md](ai-agent-mcp.md))

Downstream tasks read `${summarize.output.result}` for the text and `${summarize.output.tokenUsed}` for cost tracking.

## Patterns

- **Provider per-task.** Mix providers in one workflow — `gpt-4o-mini` for cheap classification, `claude-opus-4-7` for the hard reasoning step. Each task picks its own `llmProvider` + `model`.
- **Temperature near zero** for deterministic / classification work; **0.7+** for generative / creative.
- **`maxTokens`** is a hard cap. If `finishReason == "LENGTH"`, the response was truncated — raise the cap.
- **Don't put secrets in the prompt.** API keys, tokens, PII — keep them in `${workflow.secrets.X}` (Orkes) or worker env. Workflow inputs are visible in the execution view.
