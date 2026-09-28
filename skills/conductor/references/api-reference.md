# Conductor REST API Reference

## Authentication

Include one of these headers with every request:

```
X-Authorization: {token}
Content-Type: application/json
```

For Orkes, obtain the token with `POST /token` relative to the API base (for
example `POST https://developer.orkescloud.com/api/token`) and body
`{"keyId": "...", "keySecret": "..."}`. The CLI, SDKs, and bundled fallback
perform this exchange from `CONDUCTOR_AUTH_KEY` + `CONDUCTOR_AUTH_SECRET` and do
not print the returned JWT. An explicit `CONDUCTOR_AUTH_TOKEN` can be used
directly.

## Base URL

All paths below are relative to the server base URL (e.g. `http://localhost:8080/api`).

## Workflow metadata endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/metadata/workflow` | List all workflow definitions |
| GET | `/metadata/workflow/{name}?version={v}` | Get workflow definition |
| GET | `/metadata/workflow/names-and-versions` | List names and versions only |
| GET | `/metadata/workflow/latest-versions` | Get latest version of all workflows |
| POST | `/metadata/workflow` | Create a workflow definition |
| POST | `/metadata/workflow/validate` | Validate a workflow definition |
| PUT | `/metadata/workflow` | Update workflow definitions (array) |
| DELETE | `/metadata/workflow/{name}/{version}` | Delete a workflow definition |

## Workflow execution endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/workflow` | Start workflow (body: StartWorkflowRequest) |
| POST | `/workflow/{name}` | Start workflow by name (body: input map) |
| POST | `/workflow/execute/{name}/{version}` | Execute synchronously |
| GET | `/workflow/{workflowId}?includeTasks=true` | Get execution status |
| GET | `/workflow/{workflowId}/tasks` | Get execution tasks (paginated) |
| GET | `/workflow/running/{name}?version={v}` | List running workflow IDs |
| GET | `/workflow/search?query={q}&start={s}&size={n}` | Search executions |
| GET | `/workflow/{name}/correlated/{correlationId}` | Get by correlation ID |
| PUT | `/workflow/{workflowId}/pause` | Pause workflow |
| PUT | `/workflow/{workflowId}/resume` | Resume workflow |
| DELETE | `/workflow/{workflowId}?reason={r}` | Terminate workflow |
| POST | `/workflow/{workflowId}/restart` | Restart completed workflow |
| POST | `/workflow/{workflowId}/retry` | Retry last failed task |
| POST | `/workflow/{workflowId}/rerun` | Rerun from specific task |
| PUT | `/workflow/{workflowId}/skiptask/{taskRef}` | Skip a task |
| PUT | `/workflow/decide/{workflowId}` | Trigger decide |
| DELETE | `/workflow/{workflowId}/remove` | Remove from system |
| POST | `/workflow/test` | Test with mock data |

## Task endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/tasks/poll/{tasktype}` | Poll for a single task |
| GET | `/tasks/poll/batch/{tasktype}?count={n}` | Batch poll for tasks |
| POST | `/tasks` | Update a task (body: TaskResult) |
| POST | `/tasks/{workflowId}/{taskRefName}/{status}` | Update task by ref (async) |
| POST | `/tasks/{workflowId}/{taskRefName}/{status}/sync` | Update task by ref (returns workflow) |
| GET | `/tasks/{taskId}` | Get task by ID |
| POST | `/tasks/{taskId}/log` | Log task execution details |
| GET | `/tasks/{taskId}/log` | Get task execution logs |
| GET | `/tasks/queue/size?taskType={t}` | Get queue size |
| GET | `/tasks/queue/all` | Get all queue details |
| GET | `/tasks/search?query={q}` | Search tasks |

## Task definition endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/metadata/taskdefs` | List all task definitions |
| GET | `/metadata/taskdefs/{tasktype}` | Get task definition |
| POST | `/metadata/taskdefs` | Create task definitions (array) |
| PUT | `/metadata/taskdefs` | Update a task definition |
| DELETE | `/metadata/taskdefs/{tasktype}` | Delete task definition |

## Event endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/event` | List all event handlers |
| GET | `/event/{event}?activeOnly=true` | Get handlers for event |
| POST | `/event` | Create event handler |
| PUT | `/event` | Update event handler |
| DELETE | `/event/{name}` | Delete event handler |

## Agent runtime endpoints (`conductor.integrations.ai.enabled=true`)

Base `/agent`. Contract and usage in [agents.md](agents.md). `AgentStartRequest` body = `{name[, version]} | {agentConfig} | {framework, rawConfig} | {skillRef}` plus `prompt`, `sessionId`, `media`, `context`, `idempotencyKey`, `timeoutSeconds`.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/agent/compile` | Compile to `{workflowDef, requiredWorkers}` (no register, no run) |
| POST | `/agent/deploy` | Register a named, versioned agent → `{agentName, requiredWorkers[]}` |
| POST | `/agent/start` | Start a deployed or inline agent → `{executionId, agentName, requiredWorkers[]}` |
| GET | `/agent/list` | List deployed agents |
| GET / DELETE | `/agent/{name}?version={v}` | Get / delete a definition |
| GET | `/agent/executions?agentName&status&sessionId&classifier&freeText&start&size&sort` | Search executions |
| GET | `/agent/executions/{executionId}` | Execution detail (`currentTask`, `input`, `output`) |
| GET | `/agent/executions/{executionId}/full` | Full workflow + aggregate token usage |
| GET | `/agent/execution/{executionId}` | `AgentRun` with `tokenUsage` and tasks |
| GET | `/agent/{executionId}/status` | `{status, isComplete, isRunning, isWaiting, output, pendingTool, ...}` |
| GET | `/agent/stream/{executionId}` | SSE events (`Last-Event-ID` header to resume) |
| POST | `/agent/{executionId}/respond` | Answer a human gate: `{"approved": true}` / `{"approved": false, "reason": "..."}` / `{"message": "..."}` |
| POST | `/agent/{executionId}/signal` | `{"message": "..."}` injected into the agent's context |
| PUT | `/agent/{executionId}/pause` · `/resume` | Pause / resume |
| POST | `/agent/{executionId}/stop` | Graceful stop after the current iteration |
| DELETE | `/agent/{executionId}/cancel?reason={r}` | Cancel (propagates through the graph) |
| POST | `/agent/executions/{executionId}/restart` · `/retry` · `/rerun` | Same semantics as the workflow verbs |
| POST | `/agent/executions/prune?olderThanDays=30&archiveTasks=false` | Delete old executions |

| Method | Path | Description |
|--------|------|-------------|
| GET | `/providers/status` | `{providers: [{name, configured, baseUrl?, reachable?}]}` — which LLM providers the server has keys for |
| GET / PUT / DELETE | `/secrets` · `/secrets/{key}` · `/secrets/{key}/exists` | Agent credential store (key pattern `[a-zA-Z0-9_-]+`); `PUT` returns 501 when the backend is read-only (env-backed OSS default) |
| POST | `/skills/register` (multipart `manifest` + `package` zip) · GET `/skills[?allVersions]` · GET `/skills/{name}[/versions/{v}]` · POST `/skills/{name}/versions/{v}/deploy` · DELETE `/skills/{name}/versions/{v}` | Skill packages — only when `agentspan.skills.enabled=true` |
| GET / POST | `/a2a/workflow/{name}` · `/a2a/workflow/{name}/.well-known/agent-card.json` (and `/a2a/agent/{name}` for deployed agents) | Conductor as an A2A server — only when `conductor.a2a.server.enabled=true` |

## Scheduler endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET / POST | `/scheduler/schedules[?workflowName={n}]` | List / create (`{name, cronExpression, zoneId, paused, startWorkflowRequest{name, version, input}}`) |
| GET / DELETE | `/scheduler/schedules/{name}` | Get / delete |
| PUT | `/scheduler/schedules/{name}/pause` · `/resume` | Pause / resume |
| GET | `/scheduler/search/executions` · `/scheduler/nextFewSchedules?cronExpression={c}&limit=3` | Executions / preview |

## Search query syntax

The `query` parameter supports field-based filtering:

- `status=RUNNING`
- `workflowType=my_workflow`
- `startTime>[epoch_ms]`
- `startTime<[epoch_ms]`

Combine with AND: `status=RUNNING AND workflowType=my_workflow`

The `sort` parameter: `sort=startTime:DESC`

## Response codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 204 | Success, no content |
| 400 | Bad request (invalid input) |
| 401 | Unauthorized (missing/invalid token) |
| 404 | Resource not found |
| 409 | Conflict (already exists) |
| 500 | Server error |
