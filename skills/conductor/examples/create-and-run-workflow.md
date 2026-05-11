# Example: Create and Run a Workflow

> "Create a workflow that calls a weather API and sends a notification, then run it."

## Steps

1. Verify CLI: `conductor --version`. Verify `CONDUCTOR_SERVER_URL` (or that a local server is running). See [setup.md](../references/setup.md).
2. Consult [workflow-definition.md](../references/workflow-definition.md) for task types.
3. Write the definition to a file and register it.
4. Start the workflow.
5. Check execution status.
6. Run the worker gate (Rule 1 in [SKILL.md](../SKILL.md)) — for this example, no SIMPLE tasks, so nothing to scaffold.

## Definition

See [workflows/weather-notification.json](workflows/weather-notification.json). Two HTTP tasks: fetch weather, then post a notification using the result.

```json
{
  "name": "send_notification", "taskReferenceName": "send_notification", "type": "HTTP",
  "inputParameters": {
    "http_request": {
      "uri": "https://api.notify.example.com/send",
      "method": "POST",
      "body": {
        "to": "${workflow.input.notifyEmail}",
        "message": "Weather in ${workflow.input.city}: ${fetch_weather.output.response.body.temperature}°F"
      }
    }
  }
}
```

## Run

```bash
conductor workflow create examples/workflows/weather-notification.json
conductor workflow start -w weather_notification -i '{"city": "San Francisco", "notifyEmail": "user@example.com"}'
# → returns workflowId
conductor workflow get-execution {workflowId} -c
```

Expected status: `COMPLETED`. Output: `${fetch_weather.output.response.body}` and `${send_notification.output.response.statusCode}`.

## Patterns demonstrated

- HTTP task for external APIs.
- Workflow input parameterization via `${workflow.input.x}`.
- Task-to-task data passing via `${taskRef.output.x}`.
- `outputParameters` for aggregating results.
