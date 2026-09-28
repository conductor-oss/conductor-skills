---
name: conductor-optimize
description: Review and optimize an existing Conductor workflow
---

Run the optimization checklist in [skills/conductor/references/optimization.md](../skills/conductor/references/optimization.md) against a workflow the user names.

## Procedure

1. **Identify the target.** Ask the user: a JSON file path, or a registered workflow name (+ optional version)? If they don't say, ask once.
2. **Load the definition.**
   - File: `Read` the JSON.
   - Registered: `conductor workflow get {name}` (omit `--version` for latest).
   - **Deployed agent** (user says "agent", or the definition has `metadata.classifier == "AGENT"`): also `conductor agent get {name}` for the agent config, and walk section **F (Agents)** of optimization.md in addition to A–E. Report on the compiled graph (`{name}_loop`, `{name}_llm`, tool tasks) but phrase fixes against the SDK definition — the user edits code, not the generated JSON.
3. **Load each SIMPLE task's definition.** Timeouts, retry policy, rate limits, and `concurrentExecLimit` live on the task definition, not on the workflow task. Run `conductor task get {name}` for every distinct SIMPLE task type referenced. For every `AGENT` task with `agentType: "conductor"`, run `conductor agent get {name}` — `maxTurns`, tool approval flags and the model live there.
4. **Walk every checklist item.** Categories A–F (A1–A7, B1–B10, C1–C5, D1–D4, E1–E4, F1–F10). Don't skip any — record findings as INFO if the item is fine, just to show coverage.
5. **Report findings grouped by severity** (CRITICAL / WARN / INFO). Use the report template in optimization.md. See [skills/conductor/examples/review-workflow.md](../skills/conductor/examples/review-workflow.md) for the expected shape.
6. **Offer fixes one at a time.** Don't apply changes silently. For each fix, describe what you'd change before doing it. Some findings (e.g. `failureWorkflow` design, retry semantics) need user input before you can implement.

If the user wants only a quick scan, prioritize CRITICAL items and skip the INFO-only output. Otherwise, full report.
