---
name: conductor-setup
description: First-time Conductor setup — sign in to Developer Edition with `orkes login`, run a hello world, or fall back to key + secret / localhost
---

Walk the user through Conductor first-time setup using [skills/conductor/references/setup.md](../skills/conductor/references/setup.md) and [skills/conductor/references/orkes-dev-edition.md](../skills/conductor/references/orkes-dev-edition.md).

Don't skip checks. Specifically:

- Run `orkes --version` and `conductor --version` first. If only `conductor` is missing, prefer `npx @conductor-oss/conductor-cli` over a global install; **confirm with the user before** `npm install -g @conductor-oss/conductor-cli`. If `orkes` is missing, point to its install page and use the key + secret fallback below.
- For a generic first-time request — or when the user has no server — the default is **Developer Edition via `orkes login`**: run `orkes login --no-wait` (exit 7 = sign-in pending, not an error), relay the `Open <url>` / `Code XXXX-XXXX` lines verbatim and say the page also creates their account (signup is implicit; there is no signup command); never ask them to paste anything back or claim to have opened the browser; when they confirm (or `orkes login --timeout 30s` returns 0 — it resumes the same code) the CLI has written and activated the `developer` profile plus the `conductor --profile developer` shim. A user arriving from the Developer Edition web UI ("I was on Launchpad") is already signed in: one click. Honor explicit local-only, remote-only, URL, or named-profile requests instead.
- Verify with `orkes identity show` and `orkes conductor workflow list --json`, then run the Hello World in `orkes-dev-edition.md` (< 30 s) before the user's real goal.
- Workers / SDKs / CI: `orkes conductor keys create --name <app> --save`. Never ask for, paste, or echo a key or secret.
- **Fallback (no `orkes`, a cluster without device login, or CI):** open `https://developer.orkescloud.com/` visibly when browser automation is available, let the user sign in, navigate from the visible UI through **Access Control → Applications**, and hand control to the user before **Create access key**. The user enters the one-time key/secret directly into interactive `conductor config save --profile developer`; never read the page after key generation, the clipboard, the secret, or profile YAML.
- Create `localhost` only when the user wants a local server: interactive `conductor config save --profile localhost`, using `http://localhost:8080/api`, `OSS`, and no auth.
- Normalize a root remote URL by appending `/api`; preserve an existing `/api` or custom non-root path. Set `CONDUCTOR_SERVER_TYPE=Enterprise` for Orkes.
- Request auth setup only after `conductor workflow list` returns 401/403, or when the user explicitly says the target requires auth. Have the user inject `CONDUCTOR_AUTH_KEY` / `CONDUCTOR_AUTH_SECRET` (or `CONDUCTOR_AUTH_TOKEN`) through a secure environment; never echo them or put them in command arguments.
- For reusable connections, use `orkes login --server <url>` (device login) or the interactive `conductor config save --profile NAME`; discover them with `orkes profile list` / `conductor config list`, never by reading profile YAML.

End with `orkes profile list` (or `conductor config list`) and `orkes conductor workflow list --json` (or `conductor --profile developer workflow list --json`). Verify `localhost` too when its server is running.
