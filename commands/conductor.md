---
description: Conductor command menu — pick a structured action or describe what you want
---

The user invoked `/conductor` without a sub-action. Show this menu and ask what they want to do.

**Structured commands** (each is a guided procedure):

- `/conductor-setup` — first-time setup: install the CLI, point at a server, configure auth.
- `/conductor-optimize` — review an existing workflow against the optimization checklist and report findings (CRITICAL / WARN / INFO).
- `/conductor-scaffold-worker` — generate a worker stub in any supported language (Python, JS/TS, Java, Go, C#, Ruby, Rust).

**Or just describe what you want.** Anything else is fluid through natural language — the `conductor` skill handles it. Examples:

- *"Create a workflow that calls the GitHub API and posts a Slack message"*
- *"Run order-processing with input {orderId: 42}"*
- *"Show me failed executions today"*
- *"Pause workflow abc-123"*
- *"Schedule cleanup-workflow to run daily at 2am"*
- *"Show me a diagram of the order-processing workflow"*

After listing the menu, ask the user: **"What would you like to do?"** and proceed based on their answer. Use the `conductor` skill ([SKILL.md](../skills/conductor/SKILL.md)) for any of the above.
