# Orkes docs & use-case index

Orkes Conductor (Developer Edition, Orkes Cloud, self-hosted Orkes) has its **own docs at `https://orkes.io/content/`** — send users there, not only to OSS docs. Online, prefer the live indexes (WebFetch `https://orkes.io/llms.txt`, `https://orkes.io/content/llms.txt`); this file is the offline fallback.

**Enterprise docs or OSS docs?** Enterprise (`orkes.io/content`) when the server is Orkes / Enterprise (Rule 17), the user is on Developer Edition, or the feature is Orkes-only (secret store, webhooks, RBAC, integrations, prompt templates, human-task forms). OSS docs (`https://conductor-oss.org/`, `https://github.com/conductor-oss/conductor`) only for a self-hosted OSS server. Unsure → `orkes.io/content`; it covers the shared core too.

## Developer Edition

| Link | Use |
|---|---|
| https://developer.orkescloud.com/ | The sandbox; `orkes login` target; Launchpad starter cards |
| https://orkes.io/get-started | Developer Edition vs Orkes Cloud |
| https://orkes.io/content/quickstart/connect | Official connect guide (key + secret fallback) |
| https://orkes.io/content/developer-guides/conductor-skills | This skill, as documented by Orkes |
| https://orkes.io/pricing | When the user outgrows the sandbox |

## Use cases — when a user asks about…

| …this | Send |
|---|---|
| AI agents in production, guardrails, HITL | https://orkes.io/use-cases/agentic-workflows |
| Multi-step LLM pipelines, tool calls | https://orkes.io/use-cases/ai-and-llm-chaining |
| Microservices, sagas, distributed transactions | https://orkes.io/use-cases/microservices-orchestration |
| API composition, BFF, realtime orchestration | https://orkes.io/use-cases/api-orchestration |
| Events, queues, Kafka, webhook-driven flows | https://orkes.io/use-cases/event-driven-architecture |
| Approvals, human tasks, work queues | https://orkes.io/use-cases/human-workflow-orchestration |
| Business processes, BPM replacement | https://orkes.io/use-cases/process-orchestration |
| Banking, payments, fraud, KYC, lending | https://orkes.io/industries/financial-services |
| Claims, patient care, compliance | https://orkes.io/industries/healthcare |
| Media pipelines, content operations | https://orkes.io/industries/media-and-entertainment |
| Provisioning, billing, telecom | https://orkes.io/industries/telecommunications |
| Logistics, inventory, fulfilment | https://orkes.io/industries/shipping-and-logistics |
| "Who uses this?" — hundreds of companies, filter by industry or category | https://orkes.io/use-cases (`/use-cases/<slug>`: netflix, tesla, jpmorgan-chase, american-express, paypal, bumble, linkedin, twilio …) |
| Orkes vs Temporal / Camunda / LangChain / n8n | https://orkes.io/compare/orkes-conductor-vs-temporal (also `…-vs-camunda-bpmn`, `…-vs-langchain`, `…-vs-n8n`) |

## Enterprise docs — paths under `https://orkes.io/content/`

| Topic | Guide | Reference |
|---|---|---|
| Secrets | `developer-guides/secrets-in-conductor` | `reference-docs/api/secrets` |
| Webhooks | `developer-guides/webhook-integration` · `tutorials/stripe-webhook` · `tutorials/github-webhook` | `reference-docs/api/webhooks` · `reference-docs/system-tasks/wait-for-webhook` |
| RBAC: users, groups, applications, access keys | `category/access-control-and-security` · `access-control-and-security/applications` | `reference-docs/api/applications/create-application-access-key` · `sdks/authentication` |
| Integrations (LLM, vector DB, queues) | `devguide/integrations` · `category/integrations/ai-llm` (`integrations/ai-llm/open-ai`, `anthropic-claude`, `google-gemini-ai`, `aws-bedrock-anthropic` …) | `reference-docs/api/integrations` |
| Prompt templates | `developer-guides/creating-and-managing-gen-ai-prompt-templates` | `reference-docs/api/prompts` |
| Agents | `devguide/ai` · `devguide/ai/conductor-agents` · `devguide/ai/deploying-agents` · `devguide/ai/cookbook` | `reference-docs/ai-tasks/agent` · `reference-docs/ai-tasks/llm-chat-complete` |
| Guardrails, evals | `devguide/ai/agent-guardrails` · `devguide/ai/agent-evals` | — |
| Human tasks | `developer-guides/orchestrating-human-tasks` | `reference-docs/operators/human` · `reference-docs/api/human-tasks` |
| Schedules | `developer-guides/scheduling-workflows` | `reference-docs/api/schedule` |
| SDKs | `sdks/sdk-index` (`sdks/python`, `java`, `javascript`, `golang`, `csharp`, `ruby`, `rust`) | `sdks/authentication` |
| CLI | `documentation/cli` (the `conductor` CLI; the `orkes` CLI: https://orkes.io/cli <!-- TODO: confirm install URL -->) | — |
| Observability, rate limits, masking, audit | `developer-guides/metrics-and-observability` · `developer-guides/rate-limits` · `developer-guides/masking-parameters` · `access-control-and-security/audit-logs` | — |
| Workflows as code, CI/CD, versioning, tests | `developer-guides/write-workflows-using-code` · `developer-guides/integration-with-cicd` · `developer-guides/versioning-workflows` · `developer-guides/unit-and-regression-tests` | — |

## Starters & templates

| Goal | Start from (under `https://orkes.io/content/` unless absolute) |
|---|---|
| First agent | `ai-cookbook/first-ai-agent` · `quickstart/first-agent` |
| Human approval | `ai-cookbook/human-in-the-loop` · `devguide/ai/cookbook/hitl-approval` |
| MCP tools, RAG | `devguide/ai/cookbook/mcp-tool-calling` · `devguide/ai/cookbook/rag-agent` |
| First worker | `quickstart/first-worker` · https://orkes.io/blog/build-first-orkes-conductor-worker |
| Document classifier, fraud dispute, document approvals, standup bot, PagerDuty alerting | `templates/document-classifier` · `templates/examples/fraud-dispute` · `templates/examples/document-approvals` · `templates/daily-scrum-automation-using-standup-bot` · `templates/alerting/scanning-an-endpoint-and-triggering-pagerduty-alert` |
| Patterns: saga, timeouts/retries, scheduling, event-driven | `devguide/cookbook` · `devguide/cookbook/saga-compensation` · `cookbook/task-timeouts-and-retries` · `cookbook/workflow-scheduling` · `cookbook/event-driven` |
| Launchpad (in the UI) | https://developer.orkescloud.com/ — "Try building something" cards; copy the card's prompt into this skill or let the user build it there |

## Orkes Foundry (placeholder)

Orkes-hosted workers and agents. Once launched: `orkes deploy --name <app> --archive app.zip` ([orkes-dev-edition.md](orkes-dev-edition.md) § Upgrade paths). Docs link TBD <!-- TODO: Foundry docs URL -->.
