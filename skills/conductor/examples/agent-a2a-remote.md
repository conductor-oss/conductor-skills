# Example: Call a remote A2A agent (and expose a workflow as one)

Use `AGENT` with `agentType: "a2a"` when the agent is operated elsewhere — another team, a vendor, a Vertex AI agent, any Agent2Agent endpoint. Contract: [../references/workflow-definition.md#agent](../references/workflow-definition.md#agent). Full JSON: [workflows/a2a-remote-agent.json](workflows/a2a-remote-agent.json).

## Discover, call, handle a follow-up question

```json
{"name":"card","taskReferenceName":"card","type":"GET_AGENT_CARD",
 "inputParameters":{"agentUrl":"${workflow.input.agentUrl}"}},
{"name":"ask_agent","taskReferenceName":"ask","type":"AGENT",
 "inputParameters":{"agentType":"a2a","agentUrl":"${workflow.input.agentUrl}","text":"${workflow.input.prompt}",
   "headers":{"Authorization":"Bearer ${workflow.secrets.AGENT_TOKEN}"},"pollIntervalSeconds":5,"maxDurationSeconds":900}},
{"name":"branch_on_state","taskReferenceName":"branch","type":"SWITCH","evaluatorType":"value-param","expression":"state",
 "inputParameters":{"state":"${ask.output.state}"},
 "decisionCases":{"input-required":[
   {"name":"answer_agent","taskReferenceName":"answer","type":"AGENT",
    "inputParameters":{"agentType":"a2a","agentUrl":"${workflow.input.agentUrl}","text":"${workflow.input.answer}",
      "contextId":"${ask.output.contextId}","taskId":"${ask.output.taskId}"}}]},
 "defaultCase":[]}
```

- `GET_AGENT_CARD` → `${card.output.agentCard}` (skills, capabilities, streaming flag). Optional; mark it `optional: true` in production.
- `agentUrl` is the JSON-RPC endpoint or a `*.json` agent-card URL. Message precedence: `message` > `parts[]` > `text` / `prompt`.
- `input-required` / `auth-required` complete the task; re-call with **both** `contextId` and `taskId` to resume the same remote task. States: `submitted`, `working`, `input-required`, `auth-required`, `completed`, `canceled`, `failed`, `rejected`, `unknown`, or `"message"` for a direct reply.
- Outputs: `${ask.output.text}`, `.artifacts`, `.state`, `.taskId`, `.contextId`, `.agentMessage`. `text` is set only for text parts; Conductor's own facades answer with a `data` artifact — read `${ask.output.artifacts[0].parts[0].data.result}` (agent facade) or `...data.<outputKey>` (workflow facade). Verified live.
- Token via `${workflow.secrets.AGENT_TOKEN}` (OSS: `CONDUCTOR_SECRET_AGENT_TOKEN` env on the server; Orkes: secret manager) — never `${workflow.input.token}` (rule D1). Always set `maxDurationSeconds` (rule F9). `streaming: true` uses SSE; `pushNotification: true` needs `conductor.a2a.callback.url` on the server or it silently polls. Localhost agents need `conductor.a2a.client.allow-private-network=true`.
- Cancel: `CANCEL_AGENT {agentType: "a2a", agentUrl, taskId: "${ask.output.taskId}"}` → `{task}`.

```bash
conductor workflow create examples/workflows/a2a-remote-agent.json
conductor workflow start -w a2a_client_multi_turn --sync -i '{"agentUrl":"http://localhost:9999","prompt":"convert 100 USD to EUR","answer":"today"}'
```

## Expose a Conductor workflow (or deployed agent) as an A2A server

Server props: `conductor.a2a.server.enabled=true` (base path `/api/a2a/workflow`; deployed agents additionally at `/api/a2a/agent` when `agentspan.embedded=true`). Register the workflow with `"metadata": {"a2a": {"enabled": true}}` via `POST /api/metadata/workflow?overwrite=true` (no curl needed: `python3 "$CONDUCTOR_API" create-workflow --file order_status.json --overwrite`) — `conductor workflow create` drops `metadata`. Card: `GET /api/a2a/workflow/<name>/.well-known/agent-card.json`; JSON-RPC at `POST /api/a2a/workflow/<name>` (`message/send`, `tasks/get`, `tasks/cancel`, `message/stream`). A `HUMAN` task inside the workflow surfaces as `input-required` to the caller. `conductor.a2a.server.expose-all=true` exposes every workflow without metadata (dev only).

**Input mapping (verified live):** the facade starts the workflow with `_a2a_text` (text parts joined), `_a2a_message_id`, `_a2a_context_id`, plus every `data` part merged into the input — read the message as `${workflow.input._a2a_text}`; callers needing named inputs send a `data` part. The workflow output becomes the `workflow-output` artifact. To expose a deployed agent through the workflow facade, register a thin wrapper — [workflows/a2a-expose-agent.json](workflows/a2a-expose-agent.json): `metadata.a2a.enabled`, an `AGENT` task with `prompt: "${workflow.input._a2a_text}"` and `sessionId: "${workflow.input._a2a_context_id}"`, output `result` (verified live end to end). Deployed agents are also served directly at `/api/a2a/agent/<name>` (answer in the `agent-output` artifact, `parts[0].data.result`).
