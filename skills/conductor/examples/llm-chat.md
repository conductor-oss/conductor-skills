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

## Message schema gotcha

> Conductor uses `{role, message}`. Anthropic and OpenAI native APIs use `{role, content}`. **Conductor's field is `message`** — using `content` produces `Content must not be null for SYSTEM or USER messages`. This single difference catches almost everyone.

```json
{"role": "user", "message": "Summarize this article"}        // correct
{"role": "user", "content": "Summarize this article"}        // WRONG — fails at runtime
```

Always pass **strings** in `message`. Interpolating a structured object (e.g. `${some_task.output}` without stringifying) causes Conductor to Java-`toString` it into `{key=value}` garbage on the way to the provider. If you need to embed a tool result or structured data, stringify upstream with `JSON_JQ_TRANSFORM` and `tojson` — see [ai-agent-loop.md](ai-agent-loop.md).

## Output shape

`LLM_CHAT_COMPLETE` returns:

- `result` — **the response. Type depends on `jsonOutput`:**
  - `jsonOutput: false` (default) — `result` is a **string** (the raw model response).
  - `jsonOutput: true` — `result` is a **parsed object** (Conductor parses the raw text via Jackson).
- `finishReason` — `STOP`, `LENGTH`, or `TOOL_CALLS`
- `tokenUsed`, `promptTokens`, `completionTokens` — token accounting
- `toolCalls` — present if the model invoked a tool (see [ai-agent-mcp.md](ai-agent-mcp.md))

Downstream tasks read `${summarize.output.result}` for the text and `${summarize.output.tokenUsed}` for cost tracking.

## `jsonOutput: true` — strict parsing pitfall

Setting `jsonOutput: true` instructs Conductor to parse the raw model text via Jackson. This is the easiest path to clean structured output **only** if the model emits raw JSON. Three real-world failure modes:

1. **Markdown fences.** Claude (and sometimes other models) emit ```` ```json ... ``` ```` regardless of system-prompt instructions like "no markdown fences." Jackson fails hard on these — there is no tolerant mode that strips fences. Workarounds:
   - Use the provider's native structured-output mode (Anthropic tool-use, OpenAI JSON mode) via the `tools` parameter.
   - Keep `jsonOutput: false` and substring-extract `{...}` from `result` in a downstream INLINE.
   - Use a SIMPLE worker that calls the provider directly when you need bulletproof structured output.
2. **The word "JSON" must appear in the prompt for some providers.** Anthropic Claude in particular silently degrades to prose if no JSON cue is in the system or user message. Conductor's `@Documented` on `jsonOutput` says exactly this — "Depending on the model you MUST include JSON word as part of the prompt." Make this part of any structured-output system message.
3. **Result-type inconsistency.** With `jsonOutput: true`, when the parse succeeds, `output.result` is an object; when it fails or the model emits non-JSON, behavior depends on cluster version (task fail vs. result-as-string fallback). Any SWITCH that routes on `output.result.action` should have an **empty `defaultCase`** to avoid acting on garbage. See [ai-agent-loop.md](ai-agent-loop.md).

**`outputSchema` for retried validation.** Combine `jsonOutput: true` with an `outputSchema` to validate the parsed result. On validation failure, Conductor retries up to `retryCount` (task definition, default 3) times **with no backoff** — useful when the model occasionally emits malformed JSON but settles on a valid one after a retry.

## Built-in tools (no MCP / worker needed)

Recent Conductor releases ship provider-native tools that you enable with a single boolean. They run on the provider side; no MCP server or Conductor worker is required.

| Need | Field | Providers |
|------|-------|-----------|
| Real-time web search | `webSearch: true` | OpenAI, Anthropic, Gemini |
| Sandboxed code execution (Python by default) | `codeInterpreter: true` | OpenAI, Anthropic, Gemini |
| Search through pre-uploaded files (OpenAI Vector Stores) | `fileSearchVectorStoreIds: ["vs_..."]` | OpenAI only |
| Ground answers in Google Search results | `googleSearchRetrieval: true` | Gemini only |

```json
{
  "type": "LLM_CHAT_COMPLETE",
  "inputParameters": {
    "llmProvider": "openai",
    "model": "gpt-4o-mini",
    "messages": [
      {"role": "system", "message": "You are a research assistant. Use web search."},
      {"role": "user", "message": "${workflow.input.question}"}
    ],
    "webSearch": true
  }
}
```

These compose with `tools: [...]` — a single chat task can browse the web AND call your custom workflow tools in the same turn.

## Extended thinking / reasoning

| Field | What it does | Providers |
|-------|--------------|-----------|
| `thinkingTokenLimit` | budget (in tokens) for hidden reasoning BEFORE the answer is written | Anthropic (Claude 3.7+ / Sonnet 4), Gemini 2.5+ |
| `reasoningEffort` | `low` / `medium` / `high` | OpenAI o-series / gpt-5+ (Responses API) |
| `reasoningSummary` | surface the chain-of-thought in `output.reasoning` and `output.reasoningTokens` | OpenAI (`auto`/`concise`/`detailed`), Anthropic, Gemini (any non-blank value) |

Use `thinkingTokenLimit` or `reasoningEffort` when the problem benefits from deliberation — multi-step planning, math, complex code. The token cost is real (you pay for thinking tokens) but the answer quality jumps. Add `reasoningSummary` if you want to display or audit the reasoning text.

```json
{
  "type": "LLM_CHAT_COMPLETE",
  "inputParameters": {
    "llmProvider": "anthropic",
    "model": "claude-sonnet-4-20250514",
    "messages": [{"role": "user", "message": "${workflow.input.problem}"}],
    "thinkingTokenLimit": 10000,
    "maxTokens": 16000,
    "reasoningSummary": "detailed"
  }
}
```

## Chaining turns without resending history (OpenAI / Azure)

OpenAI's Responses API stores the full conversation server-side. Pass `previousResponseId` to reference the prior turn — your `messages` array only needs the **new** user turn. This dramatically reduces token cost and latency on long chains.

See [llm-chaining.md](llm-chaining.md) for the full pattern. Caveats: **OpenAI and Azure OpenAI only** (silently ignored on other providers), and server-side state expires per OpenAI's retention policy.

## Patterns

- **Provider per-task.** Mix providers in one workflow — `gpt-4o-mini` for cheap classification, `claude-opus-4-7` for the hard reasoning step. Each task picks its own `llmProvider` + `model`.
- **Temperature near zero** for deterministic / classification work; **0.7+** for generative / creative.
- **`maxTokens`** is a hard cap. If `finishReason == "LENGTH"`, the response was truncated — raise the cap.
- **Don't put secrets in the prompt.** API keys, tokens, PII — keep them in `${workflow.secrets.X}` (Orkes) or worker env. Workflow inputs are visible in the execution view.
