---
description: Generate a Conductor worker stub for a SIMPLE task in your language of choice
---

Scaffold a worker using the SDK pattern in [skills/conductor/references/workers.md](../skills/conductor/references/workers.md).

## Procedure

1. **Ask for language.** Supported: Python, JavaScript / TypeScript, Java, Go, C#, Ruby, Rust. If the user has a workspace open, default to whatever language is dominant in the repo.
2. **Ask for the task type.** This must match the `name` field of the SIMPLE task in the workflow definition. If the user has a specific workflow in mind, offer to read it (`conductor workflow get` or a JSON file) and pull the task name(s) directly.
3. **Generate the worker stub** from the matching SDK template in workers.md. Include:
   - Install command for the SDK (e.g. `pip install conductor-python`).
   - The worker function with input parameter mapping and output shape.
   - The runner / poller setup.
   - **A comment noting the worker must be idempotent** — Conductor may redeliver on failure or timeout.
4. **Show how to start it** — the actual command/entry point in that language.
5. **Mention the worker gate.** If the workflow that uses this task type isn't registered yet, remind the user to register both the workflow and the task definition (`conductor taskDef create taskdef.json`) so the runtime knows about it.

If the user has a workflow JSON file or registered workflow handy, also offer to verify the task type appears as a SIMPLE task there.
