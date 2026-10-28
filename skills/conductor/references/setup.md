# Server Setup

Connect the agent to a Conductor server. Run through this once per environment.

## Server resolution order

With `orkes` on PATH, run Conductor verbs as `orkes conductor …`: the active
profile (`orkes profile list` / `orkes profile use NAME`, or `ORKES_PROFILE`) is
injected as `CONDUCTOR_SERVER_URL`, `CONDUCTOR_AUTH_TOKEN` and
`CONDUCTOR_SERVER_TYPE=Enterprise`; explicit `--server` / `--auth-*` flags still
override. Precedence: `ORKES_TOKEN` > `ORKES_KEY_ID` + `ORKES_KEY_SECRET` >
`--profile` / `ORKES_PROFILE` > active profile.

Without `orkes`, an explicit `conductor --profile NAME` selects
`~/.conductor-cli/config-NAME.yaml`. `orkes login` writes `developer` there as a
compatibility shim (token ~10 h, refreshed by any `orkes` command), so the skill
uses `conductor --profile developer …` unless the user selects another profile.
Do not duplicate its credentials or edit shell startup files to make it the
default. Discover saved environments with `orkes profile list` or
`conductor config list`; **never read profile YAML, `~/.config/orkes/` or
`~/.local/state/orkes/`**, which may contain credentials.

Without a profile, the CLI uses `CONDUCTOR_SERVER_URL`, `--server`, or local
server auto-detection. The Python fallback script (`scripts/conductor_api.py`)
does **not** auto-detect or support `orkes` profiles — it requires
`CONDUCTOR_SERVER_URL` to be set explicitly (or `--profile` for a
`conductor config save` profile).

## Default first run — `orkes login` (Developer Edition)

For an unqualified setup, or when the user wants to do something and has no
server, target Developer Edition — not a local server — unless they ask for
local. Honor an explicit target instead.

1. `orkes --version`. If missing, install it from `https://orkes.io/cli`
   <!-- TODO: confirm install URL --> (ask before any system-wide install). If
   it cannot be installed, use the key + secret fallback below.
2. In **their own terminal** the user runs:

   ```bash
   orkes login            # add --no-browser on a headless host
   ```

   It prints a verification URL + user code, opens the browser, the user signs
   in or signs up on that page (signup is implicit — there is no signup
   command; one click if the browser already has a Developer Edition session),
   then the CLI stores the session, writes and activates profile `developer`,
   and writes `~/.conductor-cli/config-developer.yaml`. Never read token or
   session files, the clipboard, or the page after sign-in.
3. Verify, then run the Hello World and continue in
   [orkes-dev-edition.md](orkes-dev-edition.md):

   ```bash
   orkes identity show
   orkes conductor workflow list --json       # or: conductor --profile developer workflow list --json
   ```

4. Workers, SDKs, CI: `orkes conductor keys create --name <app> --save` mints an
   application + access key, prints the pair once as shell exports and (with
   `--save`) writes profile `<app>` for `conductor --profile <app>`. Never paste
   or relay the values.

### Fallback — key + secret (no `orkes`, a cluster without device login, CI)

1. Open `https://developer.orkescloud.com/` (or the cluster UI) visibly and let
   the user sign in. Use the visible menu: **Access Control → Applications**;
   never guess an internal route. Without browser automation, give the root
   link and labels.
2. The user creates `conductor-skills-cli`, grants **Metadata API**, and adds
   **Worker** only if workers will run. Use least privilege.
3. Hand control to the user before **Access Keys → Create access key**. The
   secret appears once; never inspect it, read the clipboard, or request it in
   chat.
4. In their own terminal, the user runs:

   ```bash
   conductor config save --profile developer
   ```

   Enter `https://developer.orkescloud.com/api`, `Enterprise`, and API Key +
   Secret directly in the prompt. Never pass credentials through agent tools or
   command arguments. In CI, export `ORKES_KEY_ID` + `ORKES_KEY_SECRET` (then
   `orkes login` does key login, no browser) or `CONDUCTOR_AUTH_KEY` +
   `CONDUCTOR_AUTH_SECRET` for the plain `conductor` CLI.

### Localhost profile (only when the user wants local)

In the user's terminal, run:

```bash
conductor config save --profile localhost
```

Use `http://localhost:8080/api`, server type `OSS`, and no authentication. This
profile can exist even when the local server is not currently running; verify
with `conductor --profile localhost workflow list --json` when it is. Later
operations default to `orkes conductor …` / `conductor --profile developer …`;
use `--profile localhost` when requested. A user may set `ORKES_PROFILE` or
`CONDUCTOR_PROFILE` in their shell, but the agent must not edit startup files.

## Step 1 — Install the CLI

Check which CLIs are already installed:

```bash
orkes --version        # umbrella CLI: `orkes login`, `orkes conductor …`
conductor --version
```

`orkes` is closed-source; install it from `https://orkes.io/cli`
<!-- TODO: confirm install URL -->. For `conductor`:

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

The fallback supports a subset of CLI commands — see [fallback-cli.md](fallback-cli.md). It supports either a pre-existing token or Orkes key/secret exchange, but it does not support profiles, server auto-detection, task-definition CRUD, or time-range search.

## Step 2 — Choose and normalize a server

If the user already supplied a server URL or selected a profile, use it
immediately. If this is a generic first-time setup, or the user has no server,
use the `orkes login` flow above (Developer Edition). Otherwise:

- **Option A** — Start a local server (only when the user asks for local).
- **Option B** — Connect to an existing remote server.

**Option A — local server:**

```bash
conductor server start
# custom port:
conductor server start --port 3000
# verify:
conductor server status
```

**Option B — existing server:**

`CONDUCTOR_SERVER_URL` is the API base and must end in `/api`. A UI/root URL with
no path is normalized by appending `/api`; do not append it twice and do not
rewrite a URL that already has a non-root deployment path.

```bash
# https://developer.orkescloud.com/ -> https://developer.orkescloud.com/api
export CONDUCTOR_SERVER_URL="https://developer.orkescloud.com/api"

# For Orkes / Enterprise servers:
export CONDUCTOR_SERVER_TYPE="Enterprise"
```

Examples:

| User supplied | Use |
|---|---|
| `https://developer.orkescloud.com/` | `https://developer.orkescloud.com/api` |
| `https://pg-qa.orkesconductor.com` | `https://pg-qa.orkesconductor.com/api` |
| `https://host.example/api` | unchanged |

## Step 3 — Test connectivity and handle auth

```bash
conductor workflow list
```

If this succeeds without credentials, the server has no auth — it is **OSS** — go to Step 4.

If you get **401 or 403**, the server requires authentication — it is **Enterprise (Orkes)**: set `CONDUCTOR_SERVER_TYPE=Enterprise`. (`python3 "$CONDUCTOR_API" server-info` makes the same check without sending credentials.) The same applies
when the user explicitly says the target requires auth; an unauthenticated probe
is then unnecessary.

Never ask the user to paste a key, secret, or token into chat. Ask them to inject
the variables through their shell, CI secret store, or the application's secure
environment settings. Check only whether the variable names are present; never
print their values and never use `set -x`, `env`, or credential-bearing CLI
arguments.

```bash
# Key + Secret (recommended for Orkes / Enterprise)
# Set securely outside the agent transcript:
#   CONDUCTOR_AUTH_KEY
#   CONDUCTOR_AUTH_SECRET

# Or a pre-existing token
#   CONDUCTOR_AUTH_TOKEN
```

Re-test: `conductor workflow list`

> **Auth behavior:** Orkes exchanges `CONDUCTOR_AUTH_KEY` +
> `CONDUCTOR_AUTH_SECRET` at `POST /api/token`, then sends the returned JWT in
> `X-Authorization`. The CLI, SDKs, and bundled Python fallback perform this
> exchange automatically. An explicit `CONDUCTOR_AUTH_TOKEN` takes precedence.
> The fallback keeps the exchanged token in memory only and never prints it.
> These are **Conductor access** credentials only. LLM-provider keys
> (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, …) live on the Conductor server (on
> Orkes: in cluster integrations — [orkes-integrations.md](orkes-integrations.md)), never
> in the client environment — say so when reporting the connection.

If the user pasted a credential into chat, follow SKILL.md Rule 5: treat it as
compromised, do not use or repeat it, and recommend rotation.

## Step 4 — Verify

```bash
conductor whoami                 # useful on authenticated Enterprise servers
conductor workflow list
```

Report the result to the user. Setup complete.

## Step 5 — Enable agents (only if the user will build or call agents)

```bash
export CONDUCTOR_API="<path-to-this-skill>/scripts/conductor_api.py"   # used with the CLI for agent verbs it lacks
conductor agent list                              # table or "No agents found." = agent runtime on
python3 "$CONDUCTOR_API" providers-status          # which LLM providers have keys on the SERVER
```

- `conductor server start` already passes `--conductor.integrations.ai.enabled=true --agentspan.embedded=true`, so a local server is ready.
- A remote server needs `conductor.integrations.ai.enabled=true` (+ `agentspan.embedded=true`, `spring.main.allow-bean-definition-overriding=true`) and provider keys in **its** environment (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, …). Keys never go in agent code.
- **Orkes (Enterprise):** LLM providers are cluster **integrations**, not server env vars — list them with `python3 "$CONDUCTOR_API" integration-list --category AI_MODEL` and create/extend them per [orkes-integrations.md](orkes-integrations.md). `conductor doctor` only inspects local env vars, not the cluster's integrations.
- MCP / OpenAPI tool discovery is outbound deny-all: `conductor.ai.outbound.allowed-origins=https://tools.example.com` (`conductor.ai.outbound.allow-private-networks=true` for localhost in dev).
- OSS secrets: `${workflow.secrets.NAME}` resolves from `CONDUCTOR_SECRET_NAME` env vars on the server (default `conductor.secrets.type=env`).
- Symptom of a disabled runtime: an `AGENT` task with `agentType: "conductor"` fails with `AGENT requires 'agentUrl'`.

Then continue with [agents.md](agents.md) and [agent-sdks.md](agent-sdks.md).

## Additional named profiles

The current CLI saves profiles interactively. This is deliberate: putting
`--auth-key` or `--auth-secret` values in a command would expose them in shell
history, process listings, and agent/tool transcripts.

```bash
conductor config save --profile dev
conductor config save --profile prod
```

Run those commands in the user's terminal and answer the interactive prompts for
server URL, server type, and credentials. Do not send the secret through chat or
an agent-executed command. Profiles live in
`~/.conductor-cli/config-<profile>.yaml`; treat the files as sensitive.

List profiles and use one without reading its file:

```bash
conductor config list
conductor --profile dev whoami
conductor --profile dev workflow list --json
```

## Updating this skill

If the user asks to upgrade or you suspect this skill is outdated:

```bash
# macOS / Linux
curl -sSL https://conductor-oss.github.io/conductor-skills/install.sh | bash -s -- --all --upgrade

# Windows
irm https://conductor-oss.github.io/conductor-skills/install.ps1 -OutFile install.ps1; .\install.ps1 -All -Upgrade
```
