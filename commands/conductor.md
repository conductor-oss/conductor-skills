---
name: conductor
description: Conductor command menu — pick a structured action or describe what you want
---

The user invoked `/conductor` without a sub-action. Show the four structured subcommands and ask what they want to do.

**Structured commands** (each is a guided procedure):

- `/conductor-setup` — first-time setup: install the CLI, point at a server, configure auth.
- `/conductor-optimize` — review an existing workflow **or a deployed agent** against the optimization checklist and report findings (CRITICAL / WARN / INFO).
- `/conductor-scaffold-worker` — generate a worker stub for a SIMPLE task.
- `/conductor-scaffold-agent` — scaffold a Conductor Agent (native SDK, or bring LangChain / OpenAI Agents / Google ADK / LangGraph / Vercel AI / Claude Agent SDK / LangChain4j / Semantic Kernel), with tests, deploy/serve entry points, and a parent workflow that invokes it.

For everything else — run, status, schedule, retry, signal, visualize, create, modify, and agent operations (run an agent, stream it, approve a pending tool, cancel a run, schedule an agent) — the user can just describe it in plain English; the `conductor` skill ([SKILL.md](../skills/conductor/SKILL.md)) handles it. Agent requests that need no command: *"run the support_agent with 'where is order 123'"*, *"what is agent execution abc-123 waiting on?"*, *"approve it"*, *"cancel agent run abc-123"*, *"schedule nightly_digest at 2am"*.

After listing the four subcommands, ask: **"What would you like to do?"** and proceed based on their answer.
