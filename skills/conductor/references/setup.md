# Server Setup

Connect the agent to a Conductor server. Run through this once per environment.

## Server resolution order

`--profile` > `CONDUCTOR_SERVER_URL` > CLI auto-detection of a local server started via `conductor server start`.

Most commands need no flags — the CLI finds the server automatically. Only append `--profile {env}` when the user mentions a named environment (dev, qa, prod, staging, uat). If unsure which profile exists, read `~/.conductor-cli/config.yaml` and ask the user to confirm. Only create named profiles when the user explicitly wants to switch between multiple environments.

The Python fallback script (`scripts/conductor_api.py`) does **not** auto-detect — it requires `CONDUCTOR_SERVER_URL` to be set explicitly.

## Step 1 — Install the CLI

Check whether `conductor` is already installed:

```bash
conductor --version
```

If not installed, check for npm/Node.js:

```bash
npm --version
```

If npm is also missing, install Node.js first:

```bash
# macOS
brew install node
# Linux (Debian/Ubuntu)
curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash - && sudo apt-get install -y nodejs
```

For installing the CLI itself, two options:

- **Recommended (no global install):** invoke as `npx @conductor-oss/conductor-cli ...` for one-off use. No system modification.
- **Global install (ask the user first):** `npm install -g @conductor-oss/conductor-cli`. Modifies the global npm prefix — confirm before running. Once approved, verify with `conductor --version`.

**Fallback** — only after the CLI is genuinely unavailable (`conductor --version` fails) **and** Node/npm cannot be installed (restricted environment, no package manager), fall back to the bundled REST API script:

```bash
export CONDUCTOR_API="<path-to-this-skill>/scripts/conductor_api.py"
```

The fallback supports a subset of CLI commands — see [fallback-cli.md](fallback-cli.md). It does not support key/secret auth (token only), profiles, server auto-detection, taskDef CRUD, or time-range search.

## Step 2 — Choose a server

Ask the user:

- **Option A** — Start a local server (good for development/testing).
- **Option B** — Connect to an existing remote server.

Don't assume — present both.

**Option A — local server:**

```bash
conductor server start
# custom port:
conductor server start --port 3000
# verify:
conductor server status
```

**Option B — existing server:**

```bash
export CONDUCTOR_SERVER_URL="http://your-server:8080/api"
```

## Step 3 — Test connectivity and handle auth

```bash
conductor workflow list
```

If this succeeds, the server has no auth — go to Step 4.

If you get **401 or 403**, the server requires authentication. Only then ask the user for credentials. Set them via env vars (never echo the values):

```bash
# Key + Secret (recommended for Orkes / Enterprise)
export CONDUCTOR_AUTH_KEY="<ask user>"
export CONDUCTOR_AUTH_SECRET="<ask user>"

# Or a pre-existing token
export CONDUCTOR_AUTH_TOKEN="<ask user>"
```

Re-test: `conductor workflow list`

> **Auth header:** the REST API expects `X-Authorization: <token>`. The CLI handles this automatically. If using the Python fallback, only `CONDUCTOR_AUTH_TOKEN` is supported — key/secret exchange is not implemented.

## Step 4 — Verify

```bash
conductor workflow list
```

Report the result to the user. Setup complete.

## Optional — named profiles

For switching between multiple servers (dev / staging / prod):

```bash
conductor config save --server https://dev.example.com/api  --auth-key KEY --auth-secret SECRET --profile dev
conductor config save --server https://prod.example.com/api --auth-key KEY --auth-secret SECRET --profile prod
```

Then append `--profile {env}` on any command. Profiles live in `~/.conductor-cli/config.yaml`.

## Updating this skill

If the user asks to upgrade or you suspect this skill is outdated:

```bash
# macOS / Linux
curl -sSL https://conductor-oss.github.io/conductor-skills/install.sh | bash -s -- --all --upgrade

# Windows
irm https://conductor-oss.github.io/conductor-skills/install.ps1 -OutFile install.ps1; .\install.ps1 -All -Upgrade
```
