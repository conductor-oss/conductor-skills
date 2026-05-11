---
description: First-time Conductor setup — install the CLI, choose a server, configure auth
---

Walk the user through Conductor first-time setup using [skills/conductor/references/setup.md](../skills/conductor/references/setup.md). Steps 1–4 in order.

Don't skip checks. Specifically:

- Run `conductor --version` first; if missing, prefer `npx @conductor-oss/conductor-cli` over global install.
- **Confirm with the user before** running `npm install -g @conductor-oss/conductor-cli` — it's a system-modifying action.
- Ask the user whether they want a local server (Option A) or to point at an existing one (Option B); don't assume.
- Only ask for credentials *after* `conductor workflow list` returns 401/403 — many servers don't need auth.
- Never echo auth tokens, keys, or secrets in output.

End with `conductor workflow list` to confirm connectivity, and report the result.
