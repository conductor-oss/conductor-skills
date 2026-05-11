# Schedules

Run a workflow on a cron schedule. Schedules are part of OSS Conductor.

## CLI

```bash
conductor schedule list
conductor schedule get {name}
conductor schedule create schedule.json
conductor schedule update schedule.json
conductor schedule delete {name}
conductor schedule pause {name}
conductor schedule resume {name}
```

The Python fallback script does **not** include schedule commands — the CLI is required.

## Schedule definition

Write the schedule to a JSON file, then `conductor schedule create file.json`.

```json
{
  "name": "nightly-cleanup",
  "cronExpression": "0 0 2 * * ?",
  "startWorkflowRequest": {
    "name": "cleanup_workflow",
    "version": 1,
    "input": { "olderThanDays": 30 },
    "correlationId": "scheduled-${date}"
  },
  "scheduleStartTime": 0,
  "scheduleEndTime": 0,
  "paused": false
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Unique schedule name |
| `cronExpression` | string | yes | Quartz cron (6 or 7 fields, see below) |
| `startWorkflowRequest` | object | yes | The workflow to start each tick |
| `scheduleStartTime` | long | no | Epoch ms; `0` = no start bound |
| `scheduleEndTime` | long | no | Epoch ms; `0` = no end bound |
| `paused` | boolean | no | If true, schedule exists but does not fire |
| `description` | string | no | Human description |

`startWorkflowRequest` mirrors `POST /workflow`: `name`, `version`, `input`, `correlationId`, `taskToDomain`.

## Cron expression format

Quartz cron — 6 fields (no year) or 7 fields (with year):

```
seconds  minutes  hours  day-of-month  month  day-of-week  [year]
```

| Pattern | Meaning |
|---------|---------|
| `0 0 * * * ?` | Every hour, on the hour |
| `0 0 2 * * ?` | Every day at 02:00 |
| `0 30 9 ? * MON-FRI` | Weekdays at 09:30 |
| `0 0 0 1 * ?` | First of every month, midnight |
| `0 */15 * * * ?` | Every 15 minutes |

Either day-of-month or day-of-week must be `?` (Quartz quirk — they can't both be specified). Cron is evaluated in the server's timezone unless you configure otherwise.

## Patterns

**Idempotency.** Use a derived `correlationId` (e.g. `nightly-cleanup-${date}`) so a schedule that double-fires won't create duplicate work — your workflow can detect the existing run and short-circuit.

**Pausing without deleting.** Set `paused: true` and update — preserves history vs delete.

**Ad-hoc backfill.** To run the scheduled workflow immediately for a missed window, just `conductor workflow start -w {name} -i '{...}'` — the schedule is just a trigger, not the workflow.

**Monitoring.** Schedules don't have their own execution history. Search executions by `correlationId` prefix to find scheduled runs:

```bash
conductor workflow search -q "correlationId:scheduled-*" -c 50
```
