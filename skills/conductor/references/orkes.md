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

Never echo secret values in agent output. After `put`, confirm with name only.

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
