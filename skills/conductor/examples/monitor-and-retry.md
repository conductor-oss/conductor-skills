# Example: Monitor and Retry Failed Workflows

> "Show me failed workflows from today and retry the timeout failures."

## Steps

```bash
# 1. Find failed workflows in the time range
conductor workflow search -s FAILED --start-time-after "2024-01-15" -c 20

# 2. Inspect each one to identify the failed task and reason
conductor workflow get-execution {workflowId} -c
```

Look at the failed task's `status` and `reasonForIncompletion`:

| Status | Action |
|--------|--------|
| `TIMED_OUT` | Retryable — `conductor workflow retry {id}` |
| `FAILED` (transient) | Retryable — `conductor workflow retry {id}` |
| `FAILED_WITH_TERMINAL_ERROR` | **Not** retryable. Surface root cause to the user before retrying. |

## Retry batch

```bash
conductor workflow retry {id1}
conductor workflow retry {id2}
conductor workflow retry {id3}
# verify
conductor workflow status {id1}   # → RUNNING
```

## Reporting back

Group results in your reply to the user:

```
Found 4 failed workflows.

Retried (3):
  - order_processing  ...111  → RUNNING
  - data_pipeline     ...222  → RUNNING
  - order_processing  ...444  → RUNNING

Skipped — terminal failure (1):
  - email_campaign    ...333  "Invalid email template" — needs template fix
```

## Patterns demonstrated

- Time-range search with `--start-time-after` / `--start-time-before`.
- Distinguishing retryable from terminal failures.
- Batch retry with post-retry verification.
- Recommending root-cause fixes when timeouts persist (raise `responseTimeoutSeconds` on the task definition).
