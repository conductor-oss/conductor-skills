# Troubleshooting & Output

## Output formatting

- Present workflow data as structured summaries: `workflowId`, `status`, `startTime`, `endTime`, failed-task details.
- For searches, render a table with `workflowId`, `name`, `status`, `startTime`.
- On failures, include the failed task name, error message, and retry count.
- Never echo auth tokens, keys, or secrets in output or logs.

## Common errors

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `conductor: command not found` | CLI not installed | Run `npx @conductor-oss/conductor-cli ...`, or ask the user before global install (see [setup.md](setup.md)). If npm itself is missing, fall back to `scripts/conductor_api.py`. |
| `Connection refused` / `URLError` | Server not running, or wrong URL | Verify `CONDUCTOR_SERVER_URL`. For local servers run `conductor server status`. |
| `401 Unauthorized` | Missing or invalid auth | Check `CONDUCTOR_AUTH_TOKEN` (or `CONDUCTOR_AUTH_KEY` + `_SECRET` with the CLI). Re-run `conductor workflow list` to confirm. |
| `403 Forbidden` | Token valid but lacks permissions | Confirm with the user that the credentials have access to the target workflow/namespace. |
| `404 Not Found` | Wrong workflow name, version, or execution ID | Run `conductor workflow list` or `conductor workflow search` to find the correct identifier. |
| Workflow stuck on a SIMPLE task | No worker polling for that task type | Run `conductor task queue-size --task-type {name}` — if size > 0 and growing, no worker is consuming. Scaffold a worker (see [workers.md](workers.md)). |
| `409 Conflict` on workflow create | Definition with that name+version already exists | Bump version, or use update instead of create. |
| 5xx errors | Server-side issue | The fallback script auto-retries 3× with backoff. CLI may need a manual retry. Surface server error to the user. |

## Diagnosis flow for failed workflows

1. `conductor workflow get-execution {id} -c` — full task list with statuses.
2. Identify the failed task (`status: FAILED` or `TIMED_OUT`) and its `reasonForIncompletion`.
3. Decide:
   - `TIMED_OUT` with retries remaining → `conductor workflow retry {id}`.
   - `FAILED_WITH_TERMINAL_ERROR` → not retryable; fix root cause first.
   - Persistent timeouts → recommend raising `responseTimeoutSeconds` on the task definition.

## Docs

- General Conductor docs: https://orkes.io/content/
- REST endpoints: see [api-reference.md](api-reference.md)
