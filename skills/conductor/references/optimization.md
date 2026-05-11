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
2. For each `SIMPLE` task, load its task definition: `conductor taskDef get {name}`. Timeout/retry config lives there, not on the workflow task.
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
- **A6. Understand the three timeouts.** On task definitions, all three matter and they catch different failure modes:
  - `pollTimeoutSeconds` — task sits in the queue this long without a worker picking it up → abandoned. Catches "no worker is polling for this type."
  - `responseTimeoutSeconds` — once a worker checks out the task, how long without a heartbeat before redelivery. Catches "worker crashed mid-execution."
  - `timeoutSeconds` — total wall clock from pickup to terminal status. Catches "worker is alive but the task takes too long."
  - Severity: WARN if a task definition has only one of the three set.
- **A7. Workflow versioning hygiene.** Don't in-place update workflows that have running production executions — bump `version`, deploy callers pointing at the new version, deprecate the old when no executions remain. In-place updates can affect running executions in ways that vary by task type (especially around input expressions). New versions are free; the registry holds many.
  - Severity: WARN if a workflow with executions in the last 30 days has been edited in place.

### B. Reliability

- **B1. Task timeouts on every SIMPLE task.** Each task definition needs `responseTimeoutSeconds` (worker must respond), `pollTimeoutSeconds` (worker must poll), and `timeoutSeconds` (overall). Without these, a hung worker hangs the workflow indefinitely.
  - Severity: CRITICAL if any are zero/missing.
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

- **D1. No secrets in workflow input.** Tokens, API keys, signing secrets must come from the secrets system (`${workflow.secrets.X}` on Orkes) or worker environment variables — never `${workflow.input.token}`. Workflow inputs are visible in the execution view.
  - Severity: CRITICAL if a real secret is being passed via input.
- **D2. No hardcoded URLs / config in task definitions.** Parameterize via `${workflow.input.x}` or `${workflow.variables.x}` — environment-specific URLs hardcoded into a definition mean a separate definition per environment.
  - Severity: WARN.
- **D3. `outputParameters` is a public API.** Other workflows, services, and dashboards depend on the workflow's output shape. Treat changes the way you'd treat function-signature changes: additions are usually safe, removals and renames are breaking. Bump `version` on breaking output changes; never reshape outputs in place.
  - Severity: WARN if a workflow with active consumers had outputs renamed or removed in place.

### E. Wrong tool

Sometimes the right answer is *not a workflow*. Smell tests:

- **E1. Sub-100ms latency-critical paths.** Workflow start has measurable overhead (queue write, definition load, dispatch). If a user is waiting synchronously, prefer a direct call.
- **E2. Single-task "workflows."** A workflow with one HTTP task is a queue with extra steps. Use a queue, scheduled worker, or just a function call.
- **E3. Large payloads in inputs/outputs.** Conductor has practical limits — typically a few MB before perf degrades and the UI struggles. Push blobs (uploaded files, large model outputs, dataset rows) to object storage and let the workflow carry only references (`{ "bucket": "...", "key": "..." }`).
  - Severity: WARN/CRITICAL depending on actual payload size and frequency.

## Report template

Render findings like this:

```
Workflow: order_processing v3 (47 tasks)

CRITICAL (3)
  ✗ B1  SIMPLE task `charge_card`: responseTimeoutSeconds=0
        → Set responseTimeoutSeconds >= 30, pollTimeoutSeconds >= 60, timeoutSeconds = 300
  ✗ B5  DO_WHILE `retry_loop`: condition has no iteration cap
        → Add `$.retry_loop['iteration'] < 10 &&` to loopCondition
  ✗ D1  Workflow input `stripeKey` looks like a secret
        → Move to ${workflow.secrets.STRIPE_KEY} or worker env

WARN (4)
  ⚠ A1  Description is empty
  ⚠ B2  No workflow timeout. Add timeoutSeconds + timeoutPolicy.
  ⚠ B3  SIMPLE task `send_email` has retryCount=0 (transient SMTP errors will fail the workflow)
  ⚠ C1  INLINE task `compute_pricing` has 60 lines of JS — extract to a worker

INFO (2)
  • A4  47 tasks — well within the 100-task soft limit
  • A5  Task names are descriptive
```

Then offer: *"Want me to apply any of these? I can update the task definitions and re-register the workflow."*

## When the user just says "make it simpler"

A simpler workflow is one a new engineer can read in five minutes. The biggest levers:

1. **Extract sub-workflows.** Group related tasks (validate-and-prep, fulfill, notify) into separate registered workflows.
2. **Replace INLINE business logic with workers.** A worker has a name, version, tests, and a stack trace; INLINE has none of those.
3. **Flatten nested SWITCHes.** Two-level decision trees are usually a sign that one level should be a sub-workflow.
4. **Name things.** Every task ref name and variable should read as English.

Don't over-refactor. If the workflow is already small and readable, "simpler" might be a no-op — say so.
