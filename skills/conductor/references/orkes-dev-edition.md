# Orkes Conductor Developer Edition

Free hosted Orkes Conductor at `https://developer.orkescloud.com` — Enterprise features (secret store, webhooks, AI integrations, human tasks, RBAC), nothing to install, a private context per user. **Default target when the user has no server**; local OSS only when they ask. An unattended agent starts an **anonymous session** (`orkes login --anonymous`; no browser, no human) and relays the claim link once; a person who prefers to sign in first uses `orkes login` (OAuth 2.0 device flow, two steps) — both in § Agent login. Signup is implicit on the claim / sign-in page — **there is no signup command**. Install `orkes` from `https://orkes.io/cli` <!-- TODO: confirm install URL -->.

## Journey

| Step | Do | Notes |
|---|---|---|
| 0 Web → terminal | User says "I was on Launchpad" or pastes a Developer Edition prompt | Already signed in in the browser → `orkes login` is one click (SSO). The pasted prompt is the goal; don't re-explain Conductor. |
| 1 Login | **Unattended (default for an agent):** `orkes login --anonymous` → start working at once. **Person present who wants to sign in first:** `orkes login --no-wait` → relay link + code → wait (§ Agent login) | Anonymous: exit 0, prints `Profile <name> (active)`, `Identity guest-…@guest.orkes.io (level 0, not yet claimed)`, `Claim it <url>` + `Code XXXX-XXXX`; relay the claim link to the person **once**, then continue — never block on it. Device flow: exit 7 = sign-in pending, not an error; once approved the CLI activates profile `developer` and writes `~/.conductor-cli/config-developer.yaml` (so `conductor --profile developer …` works too). Verify either way: `orkes identity show` (no server call; `level 0` + `guest` = unclaimed). |
| 1b Claim | Only on **exit 9** (`this action needs a claimed account … Run orkes claim`) or when the person wants the work under their account | Stop that action, name it, give the claim link again; then `orkes claim --timeout 60s` a few times (exit 7 = still pending) or continue with other work. After the claim: same session, same profile, level 1, the person's email — nothing restarts and everything done so far is theirs. |
| 2 Hello World (< 30 s) | register + run the workflow below | Always before the user's real goal, even when they pasted one. Link the run: `https://developer.orkescloud.com/execution/<workflowId>`. |
| 3 Starter | Pick the closest starter / template to the goal | [orkes-use-cases.md](orkes-use-cases.md) § Starters, or the Launchpad cards in the UI. Modify it; don't start blank. |
| 4 Their goal | Normal skill rules | Developer Edition is Enterprise: Rule 16 (LLM providers are integrations), Rule 18 (prompt templates), `conductor secret`, webhooks all apply. |
| 5 Workers / SDKs | `orkes conductor keys create --name <app> --save` | **Needs a claimed account** — on an unclaimed anonymous session it exits 9 → step 1b (meanwhile a local worker can poll with the guest's own token: `CONDUCTOR_AUTH_TOKEN="$(orkes token)" …` inline, never into chat or a file). Mints an application + access key (default roles `WORKER` + `METADATA_API`; `--role` to change). Prints `export CONDUCTOR_SERVER_URL` / `CONDUCTOR_AUTH_KEY` / `CONDUCTOR_AUTH_SECRET` lines **once**; `--save` writes the key into the active Orkes profile's Conductor CLI file (`~/.conductor-cli/config-developer.yaml`), replacing the sign-in token there — so standalone `conductor --profile developer …` and SDK workers on that profile use the long-lived key, while `orkes conductor …` keeps the personal sign-in. It does not create a profile named after the app. The worker reads the env vars — never paste or relay the values. Then run the worker gate (Rule 1). |
| 6 Upgrade | see below | Other clusters, CI, Foundry-hosted workers, local OSS. |

## Agent login

### Unattended run (default): anonymous session

No browser, no human. The session is bound to a key on this machine:

```bash
orkes login --anonymous          # or: orkes login --anonymous --json
# Started an anonymous session on https://developer.orkescloud.com
# Profile <name> (active)
# Identity guest-xxxx@guest.orkes.io (level 0, not yet claimed)
# Claim it <url>      Code XXXX-XXXX
# exit 0 — start working; re-running while unclaimed prints "Anonymous session already active"
```

`ORKES_ANONYMOUS=1` in the environment does the same lazily: `orkes conductor …` starts the session itself when nothing is signed in and prints the block on stderr once. A shell `export` only lives inside one Bash call, so prefer the explicit `orkes login --anonymous` or prefix each command.

1. **Relay once.** The first time the `Claim it <url>` / `Code` block appears, tell the person in one short sentence with the URL verbatim — "Your work is in an anonymous session; open <url> whenever you want to keep it under your account, no rush" — then continue. Never block on the claim, never repeat it unprompted, never claim to have opened the browser.
2. **Exit 9 = step-up, not an error.** Actions the cluster reserves for claimed accounts (today `orkes conductor keys create`; later schedules, secrets, credits, purchases) fail with `this action needs a claimed account … Run orkes claim`. Stop that action, say which action needs a claimed account, give the claim link again, then either wait — `orkes claim --timeout 60s`, a few times — or continue with other work. Never retry the action blindly.
3. **`orkes claim`** prints the link + code again and waits until the person has opened the link and signed in (a new email creates the account; Google works too). Without a terminal it waits ≤ 90 s then exits 7 (pending); `--no-wait` exits 7 right after printing; `--json` available. After the claim: same session, same profile, level 1, the person's email — nothing restarts, the work already done belongs to them. `orkes identity show` reports `level` and `guest`.
4. **Never `orkes logout` an unclaimed session** — its key on this machine is the only way back to that work.
5. `orkes identity show` already reports a signed-in account → nothing about anonymous mode applies.
6. Exit 5, "anonymous sessions are not enabled on this server's identity provider" → that provider has no token-exchange grant; use the device flow below.

### Person present, prefers to sign in first: device flow

A coding agent has no interactive terminal, so `orkes login` runs in two steps:

```bash
orkes login --no-wait            # or: orkes login --json --no-wait
# stderr:  Open   https://…      Code   XXXX-XXXX      "New to Orkes? That page also creates your account."
# stdout (--json): {"pending": true, "userCode": "…", "verificationUri": "…", "profile": "…", "server": "…"}
# exit 7 = not signed in yet — nothing failed
```

1. Relay the `Open <url>` and `Code XXXX-XXXX` lines to the user **verbatim**, and say that the page also creates their account. Never ask them to paste anything back; never claim to have opened the browser for them.
2. Wait until they say they are done — or poll `orkes login --timeout 30s` a few times; re-running `orkes login` (same `--server` / profile) resumes the same code ("Resuming the sign-in you started earlier"), which stays valid about 15 minutes. Exit 0 = signed in.
3. Without `--no-wait` and without a terminal, `orkes login` polls for at most 90 s, then exits 7 with the sign-in still pending — the same resume applies.

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
| `orkes login [--profile N] [--server URL] [--no-wait] [--timeout 60s] [--no-browser] [--json]` | Device-flow sign-in (key login when `ORKES_KEY_ID` + `ORKES_KEY_SECRET` are set). Exit 7 = pending; re-run resumes the same code. Default server: Developer Edition; default profile: `developer`, else the server hostname. |
| `orkes login --anonymous [--json]` | Anonymous session bound to a key on this machine — no browser, no human. Prints `Started an anonymous session on <server>`, `Profile <name> (active)`, `Identity guest-…@guest.orkes.io (level 0, not yet claimed)`, `Claim it <url>`, `Code XXXX-XXXX`; exit 0. Re-run while unclaimed = "Anonymous session already active". Exit 5 = the server's identity provider has no token-exchange grant → `orkes login`. |
| `ORKES_ANONYMOUS=1` (env) | `orkes conductor …` starts the anonymous session itself when nothing is signed in (same block on stderr, once). Only applies when nothing else resolves. |
| `orkes claim [--no-wait] [--timeout 60s] [--json]` | Prints the claim link + code again and waits for the person to open it and sign in (new email creates the account; Google works). No terminal: ≤ 90 s then exit 7; `--no-wait` exits 7 at once. After: same session + profile, level 1, the person's email. |
| `orkes logout [--profile N] [--all]` | Revoke + delete the session; the profile entry stays. **Never on an unclaimed anonymous session.** |
| `orkes profile list` / `show [N]` / `use N` / `delete N` | Manage and switch profiles (`ORKES_PROFILE` env also works). |
| `orkes identity show` | Who am I: email, issuer, expiry, `level` (0 = unclaimed guest, 1 = claimed / signed in) and `guest` — local, no server call; safe to show. |
| `orkes token` | Prints a bearer token for curl against the profile's `conductorUrl` — use only inline, `curl -H "X-Authorization: $(orkes token)"`; never into chat, a file, or a log. |
| `orkes conductor <conductor-cli command…>` | Any `conductor` verb with the active profile injected (`CONDUCTOR_SERVER_URL`, `CONDUCTOR_AUTH_TOKEN`, `CONDUCTOR_SERVER_TYPE=Enterprise`); explicit `--server` / `--auth-*` flags still override. No `update` subcommand. |
| `orkes conductor keys create --name N [--role WORKER --role METADATA_API] [--save] [--json]` | Application + access key for workers / SDKs / CI; prints the three `export` lines once. |

Exit status: 0 ok · 5 anonymous not enabled on that provider · 7 sign-in / claim pending (nothing failed) · 9 needs a claimed account (step-up, never retry blindly). Precedence: `ORKES_TOKEN` > `ORKES_KEY_ID` + `ORKES_KEY_SECRET` > `--profile` / `ORKES_PROFILE` > active profile. Tokens live ~10 h; any `orkes` command renews them and the `config-developer.yaml` shim. Never read the profiles file (`~/.config/orkes/profiles.toml`; macOS `~/Library/Application Support/orkes/profiles.toml`), the token state dir (`~/.local/state/orkes/`), or `~/.conductor-cli/*.yaml`.
