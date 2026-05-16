---
description: Conductor command menu — pick a structured action or describe what you want
---

The user invoked `/conductor` without a sub-action. Show the three structured subcommands and ask what they want to do.

**Structured commands** (each is a guided procedure):

- `/conductor-setup` — first-time setup: install the CLI, point at a server, configure auth.
- `/conductor-optimize` — review an existing workflow against the optimization checklist and report findings (CRITICAL / WARN / INFO).
- `/conductor-scaffold-worker` — generate a worker stub for a SIMPLE task.

For everything else (run, status, schedule, retry, signal, visualize, create, modify), the user can just describe it in plain English — the `conductor` skill ([SKILL.md](../skills/conductor/SKILL.md)) handles it.

After listing the three subcommands, ask: **"What would you like to do?"** and proceed based on their answer.
