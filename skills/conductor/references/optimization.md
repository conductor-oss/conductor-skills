# Reviewing & Optimizing Workflows

When the user asks to **review**, **optimize**, **simplify**, or **audit** a workflow, walk this checklist and produce a structured report. Findings are graded:

- **CRITICAL** — likely production incident waiting to happen. Recommend before next deploy.
- **WARN** — smell or maintenance burden. Recommend, but not blocking.
- **INFO** — observation; no fix required.

Treat the checklist as guidance — not every item applies to every workflow. A 3-task batch job doesn't need a `failureWorkflow`. Use judgment.

## Review flow

1. Load the workflow definition. Either:
   - User supplied a JSON file → read it.
   - User named a registered workflow → `conductor workflow get {name} --version {v}` (omit `--version` for the latest).
2. For each `SIMPLE` task, load its task definition: `conductor task get {name}`. Timeout/retry config lives there, not on the workflow task.
   - For each `AGENT` task with `agentType: "conductor"`, also load the agent definition: `conductor agent get {name} [--version v]`. `maxTurns`, tool approval flags, model and credentials live there — the analog of loading task defs. For an agent defined in code, `runtime.plan(agent)` / `conductor agent compile {config}` shows the compiled shape.
3. (Optional, if the user asks about runtime behavior) Look at recent executions: `conductor workflow search -w {name} -s FAILED -c 20` and inspect a few with `get-execution`.
4. Walk the checklist below, recording findings.
5. Report grouped by severity. Offer to apply each fix. Don't apply silently.

## Checklist

### A. Structure & maintainability

- **A1. Description present.** `description` should explain what the workflow does and why. Empty descriptions force readers to reverse-engineer intent.
  - Severity: WARN if missing.
- **A2. ownerEmail set.** Routes alerts and identifies the on-call.
  - Severity: WARN if missing.
- **A3. schemaVersion: 2.** Older schemas use legacy semantics. New workflows should always be 2.
  - Severity: WARN if missing or 1.
- **A4. Task count.** Soft limit ~100 tasks per workflow definition. Beyond that, readability and observability degrade — extract logical chunks into `SUB_WORKFLOW`s, just like refactoring oversized functions.
  - Severity: WARN if `len(tasks) > 100`.
- **A5. Descriptive `taskReferenceName`.** Each ref name is unique workflow-wide and shows up in the UI/logs. Prefer `validate_order` over `task1`.
  - Severity: INFO/WARN.
- **A6. Understand the three timeouts.** Reference (no severity — purely educational). Each task definition has three timeout knobs and they catch different failure modes:
  - `pollTimeoutSeconds` — task sits in the queue this long without a worker picking it up → abandoned. Catches "no worker is polling for this type."
  - `responseTimeoutSeconds` — once a worker checks out the task, how long without a heartbeat before redelivery. Catches "worker crashed mid-execution."
  - `timeoutSeconds` — total wall clock from pickup to terminal status. Catches "worker is alive but the task takes too long."

  The severity ladder for missing/zero timeouts is **B1** below.
- **A7. Workflow versioning hygiene.** Don't in-place update workflows that have running production executions — bump `version`, deploy callers pointing at the new version, deprecate the old when no executions remain. In-place updates can affect running executions in ways that vary by task type (especially around input expressions). New versions are free; the registry holds many.
  - Severity: WARN if a workflow with executions in the last 30 days has been edited in place.

### B. Reliability

- **B1. Task timeouts on every SIMPLE task.** Each task definition needs `responseTimeoutSeconds`, `pollTimeoutSeconds`, and `timeoutSeconds`. See A6 for what each catches. Single severity ladder:
  - **CRITICAL** if any of the three is `0` or unset on a task def for a SIMPLE task in production use.
  - **WARN** if all three are set but one or more are clearly too low (e.g. `responseTimeoutSeconds: 1`).
  - **INFO** if all three are set with reasonable values.
- **B2. Workflow-level timeout.** `timeoutSeconds` + `timeoutPolicy` (`TIME_OUT_WF` or `ALERT_ONLY`). Without one, a stuck workflow can run forever.
  - Severity: WARN by default; only INFO if the workflow legitimately has no upper bound (long-lived state machines, event-driven loops). Confirm with the user.
- **B3. Retry policy on SIMPLE tasks.** `retryCount`, `retryLogic` (`FIXED` or `EXPONENTIAL_BACKOFF`), `retryDelaySeconds`. Transient errors are common — `retryCount: 0` exposes every blip.
  - Severity: WARN if `retryCount == 0` and the task isn't intrinsically non-retryable.
- **B4. `failureWorkflow` for cleanup/alerting.** Runs when the parent fails. Common pattern: send an alert, mark the entity failed in your DB, release reserved resources. Often missing.
  - Severity: WARN if absent on workflows that mutate external state.
- **B5. DO_WHILE iteration cap.** The `loopCondition` should always include a max-iteration guard (`$.loop_ref['iteration'] < N`) in addition to any result-driven exit. Without it, an unexpected output spins forever.
  - Severity: CRITICAL if unbounded.
- **B6. `optional: true` on non-critical branches.** A best-effort notification, audit log, or analytics push shouldn't fail the workflow. Mark them optional.
  - Severity: INFO — flag candidates, don't dictate.
- **B7. Rate limits and concurrent-exec limits on task defs.** Two related throttling levers, often both missing:
  - `rateLimitPerFrequency` + `rateLimitFrequencyInSeconds` — token-bucket rate limit. Use for tasks calling external APIs with quotas (Stripe, Slack, third-party LLMs). Without this, a spike in workflow starts blows your quota.
  - `concurrentExecLimit` — caps simultaneous executions of this task across all workflows. Use for resource-bound tasks: heavy DB writes, GPU-bound model calls, memory-hungry transforms.
  - Severity: WARN on tasks calling external rate-limited APIs without `rateLimitPerFrequency`. WARN on resource-bound tasks without `concurrentExecLimit`.
- **B8. `jsonOutput: true` without "JSON" in the prompt.** Conductor's `@Documented` on `jsonOutput` notes: "Depending on the model you MUST include JSON word as part of the prompt." Anthropic Claude in particular silently degrades to prose when this cue is missing.
  - Severity: WARN when an `LLM_CHAT_COMPLETE` sets `jsonOutput: true` and neither the system nor user messages contain the substring `JSON` (case-insensitive). Also recommend pairing with `outputSchema` for stricter contracts (Conductor retries on schema-validation failure).
- **B9. `previousResponseId` provider lock-in / chain breakage.** The OpenAI Responses-API chaining field is silently ignored on other providers, and a mid-chain provider switch breaks the chain.
  - Severity: WARN when any task uses `previousResponseId` and either (a) `llmProvider` is not `openai`/`azureopenai`, or (b) a chained task's provider differs from the task whose `responseId` it references.
  - For long-running workflows where chain lifetime exceeds OpenAI's ~30-day `responseId` retention, recommend the accumulated-messages fallback ([../examples/ai-agent-loop.md](../examples/ai-agent-loop.md)) and downgrade to INFO when an explicit fallback path is present.
- **B10. HTTP task hitting an LLM provider API — use the built-in LLM task instead.** Conductor ships first-class LLM tasks (`LLM_CHAT_COMPLETE`, `LLM_GENERATE_EMBEDDINGS`, `LLM_GENERATE_IMAGE`, `LLM_GENERATE_TTS`, `LLM_GENERATE_VIDEO`, `LLM_SEARCH_INDEX`). Hand-rolling the same call as an `HTTP` task to `api.openai.com` / `api.anthropic.com` / `generativelanguage.googleapis.com` / Vertex / Bedrock / Azure-OpenAI / Cohere / Mistral / Grok / Perplexity / HuggingFace / Ollama loses everything the built-in tasks give you: auth wiring, retries, token accounting, the `{role, message}` schema, `webSearch`/`codeInterpreter` built-in tools, `previousResponseId` chaining, `tools[]` function-calling, structured-output parsing (`jsonOutput` + `outputSchema`-driven retry), and a uniform `output.result` shape that downstream tasks can consume.
  - Severity: **CRITICAL** when an `HTTP` task's `http_request.uri` matches a known LLM-provider host (`*.openai.com`, `*.anthropic.com`, `generativelanguage.googleapis.com`, `*-aiplatform.googleapis.com`, `bedrock-runtime.*.amazonaws.com`, `*.openai.azure.com`, `api.cohere.ai`, `api.mistral.ai`, `api.x.ai`, `api.perplexity.ai`, `api-inference.huggingface.co`, `*.ollama.ai`, or any `/v1/chat/completions`, `/v1/messages`, `/v1/embeddings`, `/v1/responses` path on a non-Conductor host).
  - Fix: replace the HTTP task with the matching `LLM_*` task. If the user says "the server doesn't have an Anthropic integration configured," the answer is to set `ANTHROPIC_API_KEY` (or the provider-equivalent env var) on the Conductor server, not to keep the HTTP task. Conductor auto-enables providers when the key is present.
  - Legitimate exceptions (downgrade to INFO with a one-line note): (a) the URL is a non-AI endpoint the provider happens to host (e.g. an admin/billing API); (b) the user has demonstrated a specific feature gap not yet exposed by the built-in task — name the missing field. Provider lock-in concerns ("we want to swap providers later") are *not* a reason for HTTP; that's exactly what `llmProvider` on the built-in task solves.

### C. Performance & complexity

- **C1. INLINE/graaljs scope.** JavaScript inline is for trivial validation, format conversion, simple computation. Anything with business logic — multi-step transforms, external dependencies, side effects — belongs in a worker.
  - Heuristic: INLINE script over ~15 lines, or one that's hard to follow at a glance, is a smell.
  - Severity: WARN.
- **C2. Prefer `JSON_JQ_TRANSFORM` for data shaping.** JQ is purpose-built and faster than INLINE for filter/map/aggregate. INLINE makes sense for control flow or arithmetic; JQ for shape transforms.
  - Severity: INFO.
- **C3. Bounded fan-out.** Static `FORK_JOIN` with > ~20 branches is a smell — switch to `FORK_JOIN_DYNAMIC`. Dynamic fork with thousands of branches needs batching (chunk inputs, run sub-workflows of size ~50).
  - Severity: WARN at high static counts; CRITICAL at unbounded dynamic counts without batching.
- **C4. `asyncComplete: true` for long-running operations.** Worker initiates external work, returns immediately, then signals completion later. Avoids holding worker threads for hours.
  - Severity: INFO.
- **C5. SUB_WORKFLOW for reuse, not organization.** Each sub-workflow has its own execution context, separate UI view, and orchestration overhead. Worth it when:
  - the same logic is reused across multiple parents, OR
  - the chunk is independently scheduled or testable.

  Don't extract a sub-workflow just to "organize" a long workflow into chapters — that's what naming and the description field are for. The cost is real: debugging a single failure now spans two execution views.
  - Severity: WARN if a SUB_WORKFLOW is used by exactly one parent and isn't independently scheduled.

### D. Security & inputs

- **D1. No secrets in workflow input.** Tokens, API keys, signing secrets must come from the secrets system — `${workflow.secrets.X}` resolves on OSS from `CONDUCTOR_SECRET_X` env vars on the server and on Orkes from the managed secret store — or from worker environment variables; never `${workflow.input.token}`. Workflow inputs are visible in the execution view. For agents see F5.
  - Severity: CRITICAL if a real secret is being passed via input.
- **D2. No hardcoded URLs / config in task definitions.** Parameterize via `${workflow.input.x}` or `${workflow.variables.x}` — environment-specific URLs hardcoded into a definition mean a separate definition per environment.
  - Severity: WARN.
- **D3. `outputParameters` is a public API.** Other workflows, services, and dashboards depend on the workflow's output shape. Treat changes the way you'd treat function-signature changes: additions are usually safe, removals and renames are breaking. Bump `version` on breaking output changes; never reshape outputs in place.
  - Severity: WARN if a workflow with active consumers had outputs renamed or removed in place.
- **D4. LLM outputs that route control flow need defensive handling.** When a SWITCH branches on `${chat.output.result.action}` (or any LLM-emitted field), an unparseable or unexpected emission can silently flow into the wrong branch.
  - Severity: WARN when a SWITCH whose `expression` reads `output.result.<x>` from an `LLM_CHAT_COMPLETE` task has a non-empty `defaultCase` that performs business logic (writes, finalize, etc.). Recommend either an empty `defaultCase: []` or a sentinel/no-op handler. See [template-resolution.md](template-resolution.md) Pitfall 1.

### E. Wrong tool

Sometimes the right answer is *not a workflow*. Smell tests:

- **E1. Sub-100ms latency-critical paths.** Workflow start has measurable overhead (queue write, definition load, dispatch). If a user is waiting synchronously, prefer a direct call.
- **E2. Single-task "workflows."** A workflow with one HTTP task is a queue with extra steps. Use a queue, scheduled worker, or just a function call.
- **E3. Large payloads in inputs/outputs.** Conductor has practical limits — typically a few MB before perf degrades and the UI struggles. Push blobs (uploaded files, large model outputs, dataset rows) to object storage and let the workflow carry only references (`{ "bucket": "...", "key": "..." }`).
  - Severity: WARN/CRITICAL depending on actual payload size and frequency.
- **E4. Reinventing a built-in task with HTTP / INLINE / a custom worker.** Conductor ships dedicated system tasks for most common operations — using HTTP, INLINE, or a hand-rolled worker for any of them loses retries, schema validation, observability, and clean parameter swaps. B10 is the LLM-specific instance of this rule (CRITICAL); E4 covers everything else (WARN by default).
  - Common patterns to flag:

    | Smell | Use built-in |
    |---|---|
    | `HTTP` POST to a Kafka REST proxy, or worker that calls a Kafka producer | `KAFKA_PUBLISH` |
    | Worker that renders HTML/markdown to PDF | `GENERATE_PDF` |
    | `HTTP` POST to `pinecone.io`, `*.pinecone.io`, `api.pinecone.io`, `*.weaviate.network`, MongoDB Atlas Search, or worker that wraps a vector-DB client | `LLM_INDEX_TEXT` / `LLM_STORE_EMBEDDINGS` / `LLM_SEARCH_INDEX` / `LLM_SEARCH_EMBEDDINGS` / `LLM_GET_EMBEDDINGS` |
    | Worker that just sleeps / polls a deadline | `WAIT` (duration or `until`) |
    | Worker that waits on a human approval queue | `HUMAN` |
    | Worker that triggers another workflow via the REST API | `SUB_WORKFLOW` (synchronous) or `START_WORKFLOW` (fire-and-forget) |
    | `INLINE` script that just reshapes / filters / aggregates / stringifies JSON | `JSON_JQ_TRANSFORM` (also covered by C2 — INFO) |
    | Worker that publishes to SQS / internal Conductor event sink | `EVENT` |
    | Worker that resolves "which task to run" at runtime from input | `DYNAMIC` / `FORK_JOIN_DYNAMIC` |
    | `HTTP` POST to OpenAI Images / Vertex Imagen, OpenAI TTS, OpenAI Sora / Vertex Veo | `GENERATE_IMAGE` / `GENERATE_AUDIO` / `GENERATE_VIDEO` (B10 CRITICAL — these are LLM-provider hosts) |
    | `HTTP` GET/POST to an MCP server | `LIST_MCP_TOOLS` / `CALL_MCP_TOOL` |

  - Severity: **WARN** by default; **CRITICAL** when the reinvented task is on the B10 list (LLM/media providers — auth/secret-leak risk is concentrated there).
  - Fix: replace the HTTP/INLINE/worker task with the matching built-in. If the user objects ("we want flexibility / we want to swap providers"), point out that flexibility is exactly what `llmProvider` on `LLM_*`, `vectorDB` on `LLM_INDEX_TEXT`/`LLM_SEARCH_INDEX`, and `subWorkflowParam` on `SUB_WORKFLOW` already give you.
  - Legitimate exceptions (downgrade to INFO with one-line reason): (a) the operation truly has no built-in (custom internal API, proprietary system); (b) the user has demonstrated a specific missing feature in the built-in — name it. In case (a), follow SKILL.md Rule 7 to scaffold a worker (ask language, WebFetch the SDK).

### F. Agents (`AGENT` / `CANCEL_AGENT` / `GET_AGENT_CARD` tasks and deployed agents)

Contract in [agents.md](agents.md). Load the agent definition first (review flow step 2).

- **F1. Bounded agent loop.** Three independent bounds: turns (`max_turns` / `maxTurns`), agent wall clock (agent `timeoutSeconds` / run `timeout`), caller wall clock (`AGENT.maxDurationSeconds` — the 86400 s default is effectively unbounded) plus workflow `timeoutSeconds` + `timeoutPolicy` (B2). B5 is the DO_WHILE instance of this rule.
  - Detect: `maxTurns` absent / `<= 0` / `> 200`; agent `timeoutSeconds` 0; `AGENT` task without `maxDurationSeconds`; open-ended stop criteria in the instructions ("until you have everything"); a framework-bridged agent (LangChain / LangGraph / OpenAI Agents) with no caller-side bound — those builders take no `max_turns` and compile with the server default of 100.
  - Severity: **CRITICAL** if `maxTurns` is missing/absurd or an `AGENT` inside `DO_WHILE`/`FORK_JOIN_DYNAMIC` has no `maxDurationSeconds`; **WARN** when relying on defaults; **INFO** when all three are explicit.
  - Fix: `max_turns` 10–50, agent `timeoutSeconds`, `maxDurationSeconds`, workflow timeout; an explicit stop condition or `termination` / `stop_when`.
- **F2. Side-effect tools without an approval gate or guardrail.** Tools that transfer / refund / charge / delete / send / deploy / run shell or code need `approval_required=True`, an input guardrail, allow-lists (`cli_allowed_commands`, `allowed_languages`) or `max_calls`.
  - Detect: tool name/description matching `transfer|refund|charge|pay|delete|remove|drop|send|email|post|deploy|write|update|rm|exec`; `http` POST/PUT/DELETE; `cliConfig` / `codeExecution` enabled with empty allow-lists — and no gate.
  - Severity: **CRITICAL** for financial/destructive verbs or unrestricted shell/code; **WARN** other mutating tools; **INFO** gated.
  - Fix: `approval_required` (the run pauses with `waiting: true` + `pendingTool`; approve via `conductor agent respond {id} --approve`), a guardrail, allow-lists, `max_calls`.
- **F3. Worker tools or a passthrough agent with no `serve()` process.** `deploy()` registers only. Every `worker` tool (any `@tool` function, framework function tools) and every passthrough framework (plain LangChain, Claude Agent SDK, complex LangGraph) needs a process running `runtime.serve(agent)`; otherwise the run sits IN_PROGRESS forever. Agent analog of SKILL.md Rule 1.
  - Detect: agent def has `worker` tools or a single `<name>_worker` passthrough tool; tool task stuck SCHEDULED in a recent execution; a deployment plan with `deploy()` but no `serve()`.
  - Severity: **CRITICAL** when worker tools exist and no serving process is planned/evidenced; **WARN** when unverifiable (ask); **INFO** when confirmed.
  - Fix: long-lived `runtime.serve(agent)`; `serve(agent, blocking=False)` in tests.
- **F4. Hand-wired ReAct loop where a Conductor Agent would do.** `DO_WHILE { LLM_CHAT_COMPLETE(jsonOutput) → SWITCH → tool → SET_VARIABLE history }` is what the agent compiler emits (`{name}_loop`, `{name}_llm`) minus approval gates, guardrails, streaming, token accounting and handoffs. Legitimate when the compiler cannot express it: custom loop condition, non-LLM steps between turns, several models per iteration, `previousResponseId` chaining, no agent runtime on the server, JSON-only deliverable.
  - Detect: that shape in a workflow whose `metadata.classifier` is not `AGENT`.
  - Severity: **INFO** by default (offer the SDK path); **WARN** when the loop re-implements approval/guardrail/streaming by hand or is duplicated across workflows.
  - Fix: `Agent(...)` + `runtime.deploy` (+ `serve`) and an `AGENT` task with `agentType: "conductor"`; keep the hand-wired loop only with a stated reason.
- **F5. Secrets or PII in agent `instructions`, `prompt` or tool config.** Instructions are sent to the LLM provider every turn, persisted in the agent definition (`conductor agent get`) and shown in execution views. Extends D1.
  - Detect: `sk-`, `sk_live_`, `ghp_`, `AKIA`, `Bearer `, `api_key=`, `eyJ` (JWT), `-----BEGIN` in `instructions`, `AGENT.prompt`, `tools[].config.headers`, `plannerContext`; customer PII pasted into instructions.
  - Severity: **CRITICAL** credentials; **WARN** PII that belongs in the run-time `prompt`/`context`.
  - Fix: `credentials=["NAME"]` on the agent or tool with the value in the server store (`CONDUCTOR_SECRET_NAME` env on the server, `PUT /api/secrets/{key}` when writable, UI `/agentSecrets`, or the Orkes secret manager); `${workflow.secrets.X}` in task input; `${CRED}` in `plannerContext` headers. Treat any pasted value as compromised (Rule 5).
- **F6. Model not provider-qualified / provider not configured.** `AgentConfig.model` must be `provider/model` (`openai/gpt-4o-mini`, `anthropic/claude-sonnet-4-6`, `google_gemini/gemini-2.0-flash`); a bare model name is rejected at compile/deploy. The provider must report `configured: true` on `GET /api/providers/status`. `CONDUCTOR_AGENT_LLM_MODEL` is read only by the Python OpenAI-compat `Runner` and by examples — never a substitute for `model=`.
  - Detect: `model` without `/`; empty `model`; provider prefix not configured; an `AGENT.model` override with the same faults.
  - Severity: **CRITICAL**.
  - Fix: explicit `model="provider/model"`; the provider key env var on the Conductor server.
- **F7. `AGENT` task with an invalid `agentType` or wrong agent reference.** `agentType` ∈ {`conductor`, `a2a` (default), `microsoft-foundry` (alias `azure-foundry`), `openai-assistants`, `bedrock`}; there is no `vertex` runtime (use a2a); framework names are never valid. The conductor branch takes `name` (+ `version`), **not `agentName`**; `prompt` is required on start and resume; omitting `agentType` with `name` defaults to a2a → misleading `AGENT requires 'agentUrl'`.
  - Detect: `agentType` outside the set; `agentName` / `agent` / `agent_name` keys; `name` not in `conductor agent list`; both `name` and `agentConfig`; missing `prompt`; `agentType` omitted with `name`.
  - Severity: **CRITICAL**.
  - Fix: `{"agentType": "conductor", "name": "<deployed>", "prompt": "..."}`; deploy framework agents via the SDK first.
- **F8. HITL resume misuse.** Resuming with `AGENT` + `executionId` posts `{"result": prompt}` — right for a conversational `input-required` pause (`pendingTool.response_schema` has `response`), wrong for a tool-approval gate that expects `{"approved": true}` (`response_schema.required` has `approved`; the compiled gate only bridges free text through an LLM normalizer — a model guess plus an extra model call). Also: an agent with approval/human tools whose caller never branches on `waiting` proceeds with a partial answer.
  - Detect: resume `AGENT` fed from a HUMAN task whose output is `approved`/boolean; `approvalRequired` tools and no `SWITCH` on `${ref.output.waiting}`.
  - Severity: **CRITICAL** approval-via-resume (the verdict depends on an LLM reading free text); **WARN** missing `waiting` branch.
  - Fix: `POST /api/agent/{id}/respond {"approved": true}` / `conductor agent respond {id} --approve` / SDK `approve()`; SWITCH on `waiting` with `defaultCase: []`; AGENT-resume only for answer text.
- **F9. A2A call bounds and callback config.** Remote agents are outside your control.
  - Detect: `agentType: a2a` without `maxDurationSeconds`; `pushNotification: true` while `conductor.a2a.callback.url` is unset (silent fallback to polling every 300 s); `headers.Authorization` from `${workflow.input.*}` (D1); no `SWITCH` on `state` for `input-required` / `auth-required`; per-environment `agentUrl` hardcoded (D2).
  - Severity: **WARN**; **CRITICAL** for credentials via workflow input.
  - Fix: `maxDurationSeconds` + `pollIntervalSeconds`; re-call with `contextId` + `taskId`; configure the callback URL or drop `pushNotification`; secrets system for tokens.
- **F10. Unbounded sub-agent / `agent_tool` fan-out.** `agents[]` with `parallel` / `swarm`, `agent_tool` tools, `FORK_JOIN(_DYNAMIC)` over `AGENT` tasks multiply LLM spend and worker load. C3 is the workflow instance.
  - Detect: `agent_tool` with no call bound (`max_calls` set on the returned `ToolDef` — the constructor has no such kwarg); children without their own `max_turns`; `FORK_JOIN` with > ~10 `AGENT` branches; `FORK_JOIN_DYNAMIC` over `AGENT` tasks with no batching; `swarm` without `termination`.
  - Severity: **WARN**; **CRITICAL** when dynamic and unbounded.
  - Fix: `t = agent_tool(child); t.max_calls = N`, `max_turns` on children, `scatter_gather` with a batch size, `concurrentExecLimit` on the generated tool task defs, explicit `termination`.

## Report template

Render findings like this:

```
Workflow: order_processing v3 (47 tasks)

CRITICAL (6)
  ✗ B1  SIMPLE task `charge_card`: responseTimeoutSeconds=0
        → Set responseTimeoutSeconds >= 30, pollTimeoutSeconds >= 60, timeoutSeconds = 300
  ✗ B5  DO_WHILE `retry_loop`: condition has no iteration cap
        → Add `$.retry_loop['iteration'] < 10 &&` to loopCondition
  ✗ B10 HTTP task `call_claude` posts to https://api.anthropic.com/v1/messages
        → Replace with an LLM_CHAT_COMPLETE task (llmProvider: anthropic). Set
          ANTHROPIC_API_KEY on the server if the integration isn't configured yet.
  ✗ D1  Workflow input `stripeKey` looks like a secret
        → Move to ${workflow.secrets.STRIPE_KEY} or worker env
  ✗ F1  AGENT `run_crawler`: agent maxTurns=100000, task has no maxDurationSeconds
        → Set max_turns=30 on the agent, maxDurationSeconds=1800 on the task, workflow timeoutSeconds=3600
  ✗ F3  Agent `support_triage` has 2 worker tools; no poller for `lookup_order`
        → Run `runtime.serve(agent)` as a long-lived process next to the deployment

WARN (4)
  ⚠ A1  Description is empty
  ⚠ B2  No workflow timeout. Add timeoutSeconds + timeoutPolicy.
  ⚠ B3  SIMPLE task `send_email` has retryCount=0 (transient SMTP errors will fail the workflow)
  ⚠ C1  INLINE task `compute_pricing` has 60 lines of JS — extract to a worker

INFO (2)
  • A4  47 tasks — well within the 100-task soft limit
  • A5  Task names are descriptive

Recommended Changes (priority order)
  [ ] task_def_charge_card.json  set responseTimeoutSeconds=30, pollTimeoutSeconds=60, timeoutSeconds=300
  [ ] order_processing.json:7    add `$.retry_loop['iteration'] < 10` clause to loopCondition
  [ ] order_processing.json:2    move stripeKey to ${workflow.secrets.STRIPE_KEY}
  [ ] order_processing.json:1    add description, timeoutSeconds, timeoutPolicy
  [ ] task_def_send_email.json   set retryCount=3, retryLogic=EXPONENTIAL_BACKOFF
  [ ] compute_pricing INLINE     extract to a Python worker
```

Then offer: *"Want me to apply any of these? I can update the task definitions and re-register the workflow."*

**Always end with a `Recommended Changes` checklist** even if the findings are split by severity above. The checklist is the actionable artifact the user takes away — one bullet per fix, file/path pointer first, then the change to make. Skip findings that are INFO-only.

## When the user just says "make it simpler"

A simpler workflow is one a new engineer can read in five minutes. The biggest levers:

1. **Extract sub-workflows.** Group related tasks (validate-and-prep, fulfill, notify) into separate registered workflows.
2. **Replace INLINE business logic with workers.** A worker has a name, version, tests, and a stack trace; INLINE has none of those.
3. **Flatten nested SWITCHes.** Two-level decision trees are usually a sign that one level should be a sub-workflow.
4. **Name things.** Every task ref name and variable should read as English.

Don't over-refactor. If the workflow is already small and readable, "simpler" might be a no-op — say so.
