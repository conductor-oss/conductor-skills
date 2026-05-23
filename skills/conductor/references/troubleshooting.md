# Troubleshooting & Output

## Output formatting

- Present workflow data as structured summaries: `workflowId`, `status`, `startTime`, `endTime`, failed-task details.
- For searches, render a table with `workflowId`, `name`, `status`, `startTime`.
- On failures, include the failed task name, error message, and retry count.
- Never echo auth tokens, keys, or secrets in output or logs.

## Common errors

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `conductor: command not found` | CLI not installed | Run `npx @conductor-oss/conductor-cli ...`, or ask the user before global install (see [setup.md](setup.md)). If npm itself is missing, fall back to `scripts/conductor_api.py`. |
| `Connection refused` / `URLError` | Server not running, or wrong URL | Verify `CONDUCTOR_SERVER_URL`. For local servers run `conductor server status`. |
| `401 Unauthorized` | Missing or invalid auth | Check `CONDUCTOR_AUTH_TOKEN` (or `CONDUCTOR_AUTH_KEY` + `_SECRET` with the CLI). Re-run `conductor workflow list` to confirm. |
| `403 Forbidden` | Token valid but lacks permissions | Confirm with the user that the credentials have access to the target workflow/namespace. |
| `404 Not Found` | Wrong workflow name, version, or execution ID | Run `conductor workflow list` or `conductor workflow search` to find the correct identifier. |
| Workflow stuck on a SIMPLE task | No worker polling for that task type | Run `conductor task queue-size --task-type {name}` — if size > 0 and growing, no worker is consuming. Scaffold a worker (see [workers.md](workers.md)). |
| `409 Conflict` on workflow create | Definition with that name+version already exists | Bump version, or use update instead of create. |
| 5xx errors | Server-side issue | The fallback script auto-retries 3× with backoff. CLI may need a manual retry. Surface server error to the user. |

## JavaScript / GraalJS errors

These show up in INLINE, DO_WHILE `loopCondition`, or SWITCH with a JS evaluator.

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `TypeError: Cannot read property "variables" from undefined` (or `"input"`) | `$.workflow.variables.X` / `$.workflow.input.X` used inside a script. Workflow inputs/variables are not in scope inside JS. | Plumb the value through `inputParameters` and read as `$.varName`. See [graaljs-gotchas.md](graaljs-gotchas.md) Rule 4. |
| `$.someVar` is `undefined` at runtime | Variable referenced as `$.x` but missing from `inputParameters`. | Add a matching key. The `$` object is the task's resolved `inputParameters` map. |
| `loopCondition` always evaluates the same way / loop never exits | `evaluatorType` omitted on DO_WHILE (the implicit-`javascript` alias has been reported to fail in some cluster versions), or `loopCondition` returns a non-boolean value. | Set `evaluatorType: "graaljs"` explicitly at the top of the DO_WHILE task; use an IIFE form like `(function(){ return ... ; })();`. |
| `${loop.iteration}` resolves to garbage in `outputParameters` | Wrong path — `iteration` lives inside the task's `outputData`. | Use `${loop.output.iteration}`. See [template-resolution.md](template-resolution.md) Pitfall 3. |
| Downstream string field contains `{key1=value1, key2=value2}` (note `=` separators, no quotes) | A structured object was interpolated into a string-typed field, or `String($.someTaskOutput)` was used in INLINE — both invoke Java's `Map.toString()`. | Stringify with `JSON_JQ_TRANSFORM` and `tojson` upstream. Do **not** try to do this in INLINE — `JSON.stringify` returns `"{}"` and `Object.keys` returns `[]` on Java-Map-backed proxies. See [graaljs-gotchas.md](graaljs-gotchas.md) Rule 3. |
| `JSON.parse` fails / `catch` returns garbage in an INLINE | Caller wrote `JSON.parse(String($.taskOutput))` defensively, but `$.taskOutput` is already a parsed object. | Drop the `String() + JSON.parse` wrapper. Access fields directly on the parsed object. |
| Downstream field gets the **wrong** task-output object | `${task.output.path.to.missing}` traversed a non-existent intermediate field. The resolver silently returns the parent object rather than null. | Route on the relevant signal **first** with SWITCH; only access deeper paths in the branch where they exist. See [template-resolution.md](template-resolution.md) Pitfall 1. |
| INLINE task fails mysteriously after renaming inputs | The input parameter was named `input` or `messages` — empirically these cause obscure failures (collision or reserved-ish). | Rename to e.g. `inputMessages`. See [graaljs-gotchas.md](graaljs-gotchas.md) Rule 5. |

## LLM_CHAT_COMPLETE errors

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `Content must not be null for SYSTEM or USER messages` | Used `{role, content}` (Anthropic/OpenAI shape) instead of `{role, message}` (Conductor shape). | Rename `content` → `message` in every message. |
| Chat history contains `{role=user, message=Hello}` and the LLM replies with nonsense | A structured object was placed in the `message` field; Conductor Java-`toString`'d it on the way to the provider. | Ensure `message` is always a **string**. Stringify structured data upstream with `JSON_JQ_TRANSFORM` + `tojson`. |
| Task fails with JSON parse error from Jackson when `jsonOutput: true` | The model emitted markdown fences (` ```json ... ``` `) and Conductor's strict parser rejected them. Common with Claude. | Use provider-native structured output (Anthropic tool-use, OpenAI JSON mode), or keep `jsonOutput: false` and substring-extract `{...}` downstream. |
| SWITCH branches behave weirdly on `output.result.action` | `output.result` is a parsed object when `jsonOutput: true` and a string when `false` — and the LLM occasionally emits a non-JSON reply even with `jsonOutput: true`. | Keep `defaultCase: []` on SWITCH so unrecognized replies don't poison state. Verify which mode is configured. |
| `jsonOutput: true` quietly returns prose (Anthropic/Claude) | The model wasn't told it needs to emit JSON. Conductor's `@Documented` on `jsonOutput` notes: "Depending on the model you MUST include JSON word as part of the prompt." | Add the word **JSON** to the system or user message. For stricter contracts, also set `outputSchema` — Conductor will retry up to `retryCount` times on schema failure. |
| `previousResponseId` silently ignored / chain breaks | `previousResponseId` is OpenAI/Azure-only (Responses API). Other providers ignore the field. Mid-chain provider switches also break the chain. | Keep every turn on the same OpenAI/Azure account. For portable chains, accumulate the full `messages` array instead — see [../examples/ai-agent-loop.md](../examples/ai-agent-loop.md). |
| OpenAI chain works for a while then breaks | `responseId` retention is bounded (currently ~30 days). After that, the upstream forgets the chain and subsequent turns lose context. | For long-lived workflows, fall back to accumulated `messages`. Persist them yourself in `workflow.variables`. |
| Extended thinking / `thinkingTokenLimit` has no effect | Wrong provider, or model isn't a thinking/reasoning-capable variant. `thinkingTokenLimit` is Anthropic and Gemini; OpenAI uses `reasoningEffort: low\|medium\|high` via the Responses API. | Pick the right knob for the provider, and confirm the chosen model is one of the provider's thinking-capable models. To surface the chain-of-thought, set `reasoningSummary` and read `output.reasoning`. |
| `webSearch` / `codeInterpreter` returns "feature not supported" | Provider doesn't expose that built-in tool. `webSearch` and `codeInterpreter` work on OpenAI/Anthropic/Gemini; `fileSearchVectorStoreIds` is OpenAI-only; `googleSearchRetrieval` is Gemini-only. | Check the provider matrix in [workflow-definition.md](workflow-definition.md) LLM_CHAT_COMPLETE section. |

## Diagnosis flow for failed workflows

1. `conductor workflow get-execution {id} -c` — full task list with statuses.
2. Identify the failed task (`status: FAILED` or `TIMED_OUT`) and its `reasonForIncompletion`.
3. Decide:
   - `TIMED_OUT` with retries remaining → `conductor workflow retry {id}`.
   - `FAILED_WITH_TERMINAL_ERROR` → not retryable; fix root cause first.
   - Persistent timeouts → recommend raising `responseTimeoutSeconds` on the task definition.

## Docs

- General Conductor docs: https://orkes.io/content/
- REST endpoints: see [api-reference.md](api-reference.md)
