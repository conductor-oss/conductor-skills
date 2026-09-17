# Example: Autonomous Agent Loop on a Diffusion LLM (ReAct Pattern)

An agent that **thinks**, **acts**, and **observes** in a loop until it decides it's done — driven by a **diffusion LLM** (Inception Labs [Mercury](https://docs.inceptionlabs.ai/)) instead of an autoregressive model. Built with `DO_WHILE` wrapping an `LLM_CHAT_COMPLETE → SWITCH → tool task` inner sequence.

This is the diffusion-model variant of [ai-agent-loop.md](ai-agent-loop.md). The Conductor wiring is identical — `DO_WHILE`, `graaljs`, JQ accumulation, empty `defaultCase` — because those are platform facts, not provider facts. Read [ai-agent-loop.md](ai-agent-loop.md) first; this page covers only **what changes when the brain is a diffusion model**.

The headline change is the loop's economics. The autoregressive version warns "if latency matters, use single-shot." Mercury reverses that calculus: it generates a whole block in parallel by iterative denoising rather than token-by-token, hitting **1,000+ tokens/sec** and **5–10× lower wall-clock latency in tool-heavy loops**. A 5–10 round-trip ReAct loop that was latency-prohibitive on an autoregressive model becomes routine on a diffusion model. The loop pattern is the *recommended* shape here, not the fallback.

## Why a diffusion model for the loop

| | Autoregressive (gpt-4o-mini) | Diffusion (mercury-2) |
|---|---|---|
| Generation | Left-to-right, one token at a time | Whole block, coarse→fine denoising |
| Per-iteration latency | Grows with output length | Near-flat; ~1,000+ tok/s |
| 5–10 round-trip loop | Latency adds up — often pick single-shot | Cheap enough to be the default |
| Per-iteration tuning knob | `temperature` / `maxTokens` | `reasoning_effort: instant\|low\|medium\|high` |
| Structured/JSON output | Native, but Claude wraps in fences | Native structured outputs; fewer fence problems |

The ReAct router needs short, well-formed JSON every iteration (`{action, ...}`) — exactly the latency-sensitive, structure-heavy workload diffusion is fastest at.

## Register Mercury as an LLM integration

Inception is **OpenAI-API-compatible**, so it plugs into Conductor as an OpenAI-type integration pointed at Inception's base URL. In Orkes: *Integrations → New → OpenAI*, then set

- **API base / endpoint:** `https://api.inceptionlabs.ai/v1`
- **API key:** your `INCEPTION_API_KEY` (store as a secret — see guardrails)
- **Integration name:** `inception` (this is what `llmProvider` references)
- **Model:** add `mercury-2` (general, 128K ctx, reasoning + tool use + structured output). For latency-critical coding subagents, `mercury-edit-2` (32K ctx) is the lighter option.

The `think` task then uses `"llmProvider": "inception"`, `"model": "mercury-2"`.

## Pipeline

```
init_messages (SET_VARIABLE)                              ← seed system + user messages
agent_loop (DO_WHILE, graaljs, IIFE, iter cap):
    think (LLM_CHAT_COMPLETE, inception/mercury-2,
           jsonOutput: true)                              ← emits { action, ... }, fast
    route (SWITCH on action):
        case "call_tool":
            call_weather (HTTP, optional: true)                       ← external call
            build_next_messages (JSON_JQ_TRANSFORM, .current + [...])  ← append to chat history
            update_messages (SET_VARIABLE)                            ← write merged array back
        case "answer":
            finalize (SET_VARIABLE final_response)
        defaultCase: []                                               ← empty
until think says action == "answer", or iter cap
```

## Workflow

See [workflows/diffusion-agent-loop.json](workflows/diffusion-agent-loop.json) for the full file. The only diff from the autoregressive scaffold is the `think` task's provider/model:

```json
{
  "name": "think",
  "taskReferenceName": "think",
  "type": "LLM_CHAT_COMPLETE",
  "inputParameters": {
    "llmProvider": "inception",
    "model": "mercury-2",
    "messages": "${workflow.variables.messages}",
    "temperature": 0.1,
    "maxTokens": 500,
    "jsonOutput": true
  }
}
```

Everything else — `DO_WHILE` with `evaluatorType: "graaljs"`, the IIFE `loopCondition` with an iteration cap, the `JSON_JQ_TRANSFORM` that stringifies tool output with `tojson` *and* concatenates onto chat history, the empty SWITCH `defaultCase`, the `optional: true` HTTP tool — is unchanged. Those exist for Conductor-platform reasons covered in [ai-agent-loop.md](ai-agent-loop.md); they are provider-agnostic.

## What changes for the diffusion model

### 1. `reasoning_effort` is the per-iteration latency lever

Mercury exposes `reasoning_effort` with four levels: `instant`, `low`, `medium`, `high`. For a ReAct router emitting one short JSON decision per turn, `instant` or `low` is usually right — you want a fast routing decision, not deep deliberation, and the *loop* supplies the reasoning by re-planning each iteration with accumulated results.

`reasoning_effort` is an OpenAI `extra_body` parameter, not a first-class `LLM_CHAT_COMPLETE` field. Set it where your Conductor version allows:

- **Integration/model config** (most portable): pin `reasoning_effort` on the `mercury-2` model entry in the integration so every `think` call inherits it. No workflow change needed.
- **Per-task passthrough**: if your cluster's `LLM_CHAT_COMPLETE` forwards unknown keys to the provider, add `"reasoning_effort": "low"` to `inputParameters`. Verify on your version before relying on it — older builds silently drop unrecognized fields.

Keep `temperature: 0.1` regardless; low effort governs *how hard* it thinks, temperature governs *how varied* the output is, and a router wants both low.

### 2. Prefer native structured outputs over JSON-mode-and-pray

`jsonOutput: true` gives you `output.result` as a parsed object (raw string when `false`) — the SWITCH branches on `result.action`, so the parsed object is what we want. Mercury 2 supports **native structured outputs**, so it does not wrap JSON in markdown fences the way Claude does, which removes the main failure mode the autoregressive example warns about. Still:

- Keep the `"Emit raw JSON with no markdown fences."` line in the system prompt as a cheap belt-and-suspenders.
- If your integration supports it, attach a `response_format` JSON schema for the `{action, tool, args, answer}` shape to make malformed routing decisions structurally impossible. That is strictly better than relying on `jsonOutput` parsing of free text.
- The `messages` schema is still Conductor's `{role, message}` — **not** `{role, content}`. The Inception *native* API uses `content`; Conductor's `LLM_CHAT_COMPLETE` uses `message` and translates. Mixing them up gives `Content must not be null for SYSTEM or USER messages`.

### 3. `stream` / `diffusing` do **not** apply inside the workflow

Inception's `stream: true` and `diffusing: true` exist to *visualize* denoising for a human watching a chat UI — each chunk is the full text re-refined. Inside a Conductor task you consume one final result, so leave both off. They belong in a front-end (see the diffusing-overwrite snippet in the [Streaming & Diffusion docs](https://docs.inceptionlabs.ai/)), not in `think`.

### 4. No `previousResponseId` chaining

The autoregressive example offers an OpenAI Responses-API optimization (`previousResponseId`) to avoid re-sending the message array each turn. Inception is compatible with OpenAI's **Chat Completions** API, not the Responses API, so that optimization is unavailable. Use the full message-accumulation scaffold (the JQ-concat-then-`SET_VARIABLE` pair) as the default and only mechanism — which is exactly what [workflows/diffusion-agent-loop.json](workflows/diffusion-agent-loop.json) does. The cost you'd otherwise save by chaining is largely offset by Mercury's throughput anyway.

## Run

```bash
conductor workflow create skills/conductor/examples/workflows/diffusion-agent-loop.json
conductor workflow start -w diffusion_agent -i '{
  "question": "What is the weather in San Francisco?",
  "max_iterations": 5
}' --sync
```

Quick API sanity check before wiring it into Conductor — confirm the key and model resolve:

```bash
curl https://api.inceptionlabs.ai/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $INCEPTION_API_KEY" \
  -d '{
    "model": "mercury-2",
    "messages": [{"role": "user", "content": "Reply with the single word: ok"}],
    "max_tokens": 10
  }'
```

## Critical guardrails

Same as the autoregressive loop, plus two diffusion notes:

- **Cap iterations** — explicit `$.iteration < N` clause **and** an early-exit on `final_response`. Diffusion being fast makes a runaway loop burn budget *faster*, not slower.
- **Set a workflow timeout** (`timeoutSeconds` + `timeoutPolicy: TIME_OUT_WF`). A slow *tool* call still hangs the loop regardless of how fast the model is.
- **`maxTokens` enforces per-iteration token budget**; the loop itself has none. Cost ≈ iterations × maxTokens × $/token at Mercury's rate.
- **No secrets in `workflow.input`.** Put the Inception API key in `${workflow.secrets.X}` (Orkes) or the integration's secret store / worker env — never in workflow inputs, which are visible in the execution view.
- **Empty SWITCH `defaultCase`** unless you have a real no-op handler. A `defaultCase` that calls `finalize` overwrites `final_response` with garbage on any unrecognized action.
- **Pin `reasoning_effort` low for the router.** Letting it default to a high effort throws away the latency advantage that motivated using a diffusion model here.

## When to use the loop vs the single-shot

The autoregressive table still holds, but the latency row flips:

| Use single-shot ([ai-agent-mcp.md](ai-agent-mcp.md)) | Use the diffusion loop |
|------------------------------------------------------|------------------------|
| Answer always needs exactly one tool call | Answer needs an unknown number of tool calls |
| You can constrain the model to pick ONE action | Tasks chain — one tool's output informs the next |
| You want strict, audit-friendly determinism | Some exploration is acceptable |
| ~~Latency matters~~ — *no longer a reason to avoid the loop with Mercury* | 5–10 round trips are cheap at 1,000+ tok/s |
