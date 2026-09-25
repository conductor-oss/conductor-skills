---
name: conductor-setup
description: First-time Conductor setup — install the CLI, create profiles, configure auth
---

Walk the user through Conductor first-time setup using [skills/conductor/references/setup.md](../skills/conductor/references/setup.md).

Don't skip checks. Specifically:

- Run `conductor --version` first; if missing, prefer `npx @conductor-oss/conductor-cli` over global install.
- **Confirm with the user before** running `npm install -g @conductor-oss/conductor-cli` — it's a system-modifying action.
- For a generic first-time request, create both interactive profiles: `developer` and `localhost`. Default later commands to `--profile developer`. Honor explicit local-only, remote-only, URL, or named-profile requests instead.
- For `developer`, open `https://developer.orkescloud.com/` visibly when browser automation is available, let the user sign in, then navigate from the visible UI through **Access Control → Applications**. Do not guess an internal UI URL.
- Hand control to the user before **Create access key**. The user creates the application/key and enters the one-time key/secret directly into `conductor config save --profile developer`; never read the page after key generation, the clipboard, the secret, or profile YAML.
- Create `localhost` with interactive `conductor config save --profile localhost`, using `http://localhost:8080/api`, `OSS`, and no auth.
- Normalize a root remote URL by appending `/api`; preserve an existing `/api` or custom non-root path. Set `CONDUCTOR_SERVER_TYPE=Enterprise` for Orkes.
- Request auth setup only after `conductor workflow list` returns 401/403, or when the user explicitly says the target requires auth.
- Never ask for credentials in chat. Have the user inject `CONDUCTOR_AUTH_KEY` / `CONDUCTOR_AUTH_SECRET` (or `CONDUCTOR_AUTH_TOKEN`) through a secure environment, and never echo them or put them in command arguments.
- For reusable connections, use the interactive `conductor config save --profile NAME`; discover them with `conductor config list`, never by reading profile YAML.

End with `conductor config list` and `conductor --profile developer workflow list --json`. Verify `localhost` too when its server is running.
