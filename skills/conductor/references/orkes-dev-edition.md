# Orkes Conductor Developer Edition

Free hosted Orkes Conductor at `https://developer.orkescloud.com` — Enterprise features (secret store, webhooks, AI integrations, human tasks, RBAC), nothing to install, a private context per user. **Default target when the user has no server**; local OSS only when they ask. Sign-in is `orkes login` (OAuth 2.0 device flow). Signup is implicit on the browser page — **there is no signup command**. Install `orkes` from `https://orkes.io/cli` <!-- TODO: confirm install URL -->.

## Journey

| Step | Do | Notes |
|---|---|---|
| 0 Web → terminal | User says "I was on Launchpad" or pastes a Developer Edition prompt | Already signed in in the browser → `orkes login` is one click (SSO). The pasted prompt is the goal; don't re-explain Conductor. |
| 1 Login | `orkes login` — in the **user's** terminal | Prints a URL + user code, opens the browser, the user confirms; the CLI stores the session, activates profile `developer` and writes `~/.conductor-cli/config-developer.yaml` (so `conductor --profile developer …` works too). `--no-browser` on headless hosts. Verify: `orkes identity show`. |
| 2 Hello World (< 30 s) | register + run the workflow below | Always before the user's real goal, even when they pasted one. Link the run: `https://developer.orkescloud.com/execution/<workflowId>`. |
| 3 Starter | Pick the closest starter / template to the goal | [orkes-use-cases.md](orkes-use-cases.md) § Starters, or the Launchpad cards in the UI. Modify it; don't start blank. |
| 4 Their goal | Normal skill rules | Developer Edition is Enterprise: Rule 16 (LLM providers are integrations), Rule 18 (prompt templates), `conductor secret`, webhooks all apply. |
| 5 Workers / SDKs | `orkes conductor keys create --name <app> --save` | Mints an application + access key. Prints `CONDUCTOR_AUTH_KEY` / `CONDUCTOR_AUTH_SECRET` as shell exports **once**; `--save` also writes profile `<app>` for a standalone `conductor --profile <app>` and SDK workers. The worker reads the env vars — never paste or relay the values. Then run the worker gate (Rule 1). |
| 6 Upgrade | see below | Other clusters, CI, Foundry-hosted workers, local OSS. |

## Hello World

`hello_world.json` — built-in tasks only, so it completes with no worker:

```json
{
  "name": "hello_world",
  "version": 1,
  "tasks": [
    {
      "name": "greet",
      "taskReferenceName": "greet",
      "type": "INLINE",
      "inputParameters": {
        "who": "${workflow.input.who}",
        "evaluatorType": "graaljs",
        "expression": "(function(){ return 'Hello, ' + $.who + '!'; })();"
      }
    }
  ],
  "outputParameters": { "greeting": "${greet.output.result}" },
  "timeoutSeconds": 60,
  "timeoutPolicy": "ALERT_ONLY",
  "schemaVersion": 2
}
```

```bash
orkes conductor workflow create hello_world.json
orkes conductor workflow start -w hello_world -i '{"who":"World"}' --sync
```

Without `orkes` on PATH: `conductor --profile developer workflow …`.

## Upgrade paths

- **Another Orkes cluster:** `orkes login --server https://<cluster>` → a profile named after the hostname; `orkes profile list` / `orkes profile use <name>` to switch.
- **CI / no browser:** set `ORKES_KEY_ID` + `ORKES_KEY_SECRET` (from `keys create`); `orkes login` then does key login with no device flow. Or the plain `conductor` CLI with `CONDUCTOR_AUTH_KEY` / `_SECRET` — [setup.md](setup.md).
- **Orkes-hosted workers (Orkes Foundry, once launched):** `orkes deploy --name <app> --archive app.zip --json` deploys a worker app; verify with `orkes status --name <app> --json`. This is **not** `conductor deploy` (Rule 13). Details live in the `orkes` CLI's own `foundry-deploy` skill and `orkes --help`, not here.
- **Local OSS:** only when asked — `conductor server start`, profile `localhost` ([setup.md](setup.md)).

## `orkes` CLI cheat-sheet

| Command | Does |
|---|---|
| `orkes login [--profile N] [--server URL] [--no-browser] [--json]` | Device-flow sign-in (key login when `ORKES_KEY_ID` + `ORKES_KEY_SECRET` are set). Default server: Developer Edition; default profile: `developer`, else the server hostname. |
| `orkes logout [--profile N] [--all]` | Revoke + delete the session; the profile entry stays. |
| `orkes profile list` / `show [N]` / `use N` / `delete N` | Manage and switch profiles (`ORKES_PROFILE` env also works). |
| `orkes identity show` | Who am I: email, issuer, expiry — safe to show. |
| `orkes token` | Prints a bearer token — use only inline, `curl -H "X-Authorization: $(orkes token)"`; never into chat, a file, or a log. |
| `orkes conductor <conductor-cli command…>` | Any `conductor` verb with the active profile injected (`CONDUCTOR_SERVER_URL`, `CONDUCTOR_AUTH_TOKEN`, `CONDUCTOR_SERVER_TYPE=Enterprise`); explicit `--server` / `--auth-*` flags still override. |
| `orkes conductor keys create --name N [--save]` | Application + access key for workers / SDKs / CI. |

Precedence: `ORKES_TOKEN` > `ORKES_KEY_ID` + `ORKES_KEY_SECRET` > `--profile` / `ORKES_PROFILE` > active profile. Tokens live ~10 h; any `orkes` command renews them and the `config-developer.yaml` shim. Never read `~/.config/orkes/`, `~/.local/state/orkes/`, or `~/.conductor-cli/*.yaml`.
