# Orkes Enterprise Features

Webhooks, the managed secret store (with the `conductor secret` CLI), and AI model integrations (below) require Orkes Conductor (orkes.io). **`${workflow.secrets.X}` itself is not Orkes-only any more**: OSS Conductor resolves it from `CONDUCTOR_SECRET_X` environment variables on the server (`conductor.secrets.type=env`, the default), and servers with the agent runtime expose the store at `/api/secrets` (UI `/agentSecrets`) for agent `credentials=[...]` — see [agents.md](agents.md) §8. The Python fallback script has no secret commands, but does cover AI model integrations (below).

> Schedules used to live here — they're now part of OSS. See [schedules.md](schedules.md).

Auth is the same as the rest of the CLI — see [setup.md](setup.md) (key/secret recommended).

## Secrets

Securely store values referenced from workflows (e.g. API keys). Reference in tasks via `${workflow.secrets.MY_KEY}` (and `${workflow.secrets.MY_KEY.sub_key}` when the secret holds a JSON object). On OSS the equivalent is `export CONDUCTOR_SECRET_MY_KEY=...` in the server's environment.

```bash
conductor secret list
conductor secret get {key}
conductor secret put {key} {value}
conductor secret delete {key}
```

**Important: secret values are resolved server-side at task execution time**, not by the agent, the CLI, or the workflow definition. The reference `${workflow.secrets.MY_KEY}` lives in the workflow JSON; the actual value is substituted by the Conductor server when the task runs. This means:

- The plaintext secret never appears in the workflow definition, the execution view, or any agent transcript.
- Rotating a secret on the server affects every running and future workflow without redeploying any definition.
- Workers and HTTP tasks receive the substituted value at runtime via task inputs.

Never echo secret values in agent output. After `put`, confirm with name only (e.g. via `conductor secret list`).

## Webhooks

Trigger workflows from external HTTP callbacks (Stripe, GitHub, custom services).

```bash
conductor webhook list
conductor webhook get {name}
conductor webhook create webhook.json
conductor webhook update webhook.json
conductor webhook delete {name}
```

Example `webhook.json`:

```json
{
  "name": "github-pr-events",
  "verifier": "HEADER_BASED",
  "headers": { "X-Hub-Signature-256": "${secrets.GITHUB_WEBHOOK_SIG}" },
  "receiverWorkflowNamesToVersions": { "github_pr_handler": 1 },
  "sourcePlatform": "Custom"
}
```

After creation the CLI returns a webhook URL — give that to the user (don't fabricate one).

## AI model integrations (`LLM_CHAT_COMPLETE` and friends)

OSS auto-enables a provider when its key is a **server** env var (`OPENAI_API_KEY`, etc.). **No equivalent exists on Developer Edition or any Orkes server you don't administer** — register the provider/model per-account instead, via the Integrations API (separate from the agent-runtime's `providers-status`, §8 in [agents.md](agents.md)).

No `conductor` CLI verb exists for this — always use the fallback script, even with the CLI installed:

```bash
export CONDUCTOR_API="<path-to-this-skill>/scripts/conductor_api.py"
python3 "$CONDUCTOR_API" integration-status --provider openai --model gpt-4o   # check first

export OPENAI_API_KEY="..."   # set outside the agent transcript, like any other credential
python3 "$CONDUCTOR_API" integration-create --provider openai --model gpt-4o   # idempotent
```

Provider → env var: `openai` → `OPENAI_API_KEY`, `anthropic` → `ANTHROPIC_API_KEY`, `google_gemini` → `GEMINI_API_KEY`. One call per distinct `(provider, model)` pair in the workflow. A new provider means adding it to `PROVIDER_CONFIG` in `conductor_api.py` — ask the user for its endpoint and key convention, don't guess.

Signature symptom: `LLM_CHAT_COMPLETE` fails saying the provider/model isn't found on a Developer Edition / Orkes target. Run `integration-status` before assuming the workflow is broken.

## Notes

- Enterprise commands fail on OSS Conductor with a `404` or `Not Found`. If the user hits this, confirm they're pointed at an Orkes server. (`conductor secret` may also answer on an OSS server with the agent runtime, but `put` returns 501 when the backend is env-backed and read-only.)
- For dev against Orkes, [developer.orkescloud.com](https://developer.orkescloud.com) is the public developer sandbox.
