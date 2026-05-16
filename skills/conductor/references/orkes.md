# Orkes Enterprise Features

Secrets and webhooks require Orkes Conductor (orkes.io). They are unavailable on plain OSS Conductor and on the Python fallback script.

> Schedules used to live here — they're now part of OSS. See [schedules.md](schedules.md).

Auth is the same as the rest of the CLI — see [setup.md](setup.md) (key/secret recommended).

## Secrets

Securely store values referenced from workflows (e.g. API keys). Reference in tasks via `${workflow.secrets.MY_KEY}`.

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

## Notes

- Enterprise commands fail on OSS Conductor with a `404` or `Not Found`. If the user hits this, confirm they're pointed at an Orkes server.
- For dev against Orkes, [developer.orkescloud.com](https://developer.orkescloud.com) is the public developer sandbox.
