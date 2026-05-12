# Conductor Skills — Test Plan

Comprehensive validation plan for the `conductor-skills` plugin. Hand this to QA before each release.

- **Repo:** [github.com/conductor-oss/conductor-skills](https://github.com/conductor-oss/conductor-skills)
- **Current version:** see `VERSION`
- **Target agents:** primarily Claude Code (slash commands + skill); secondarily Codex, Gemini, Cursor, Windsurf, Cline, GitHub Copilot, Aider, Amazon Q, Roo Code, Amp, OpenCode (skill content only — slash commands are Claude-specific)

Test cases below are numbered `TC-<area>-<n>` for traceability. Mark each Pass / Fail / Blocked / Skipped in the matrix at the bottom.

---

## 1. About this plan

### 1.1 Scope

In scope:
- Plugin install/uninstall/upgrade across supported agents
- All four slash commands
- Skill activation via natural language
- All workflow CRUD, execution, monitoring, management, signaling
- All 25+ task types documented in `references/workflow-definition.md`
- Worker scaffolding in 7 languages
- Schedules (OSS) and Orkes-only features (secrets, webhooks)
- Fallback REST script (no Node.js)
- Optimization checklist coverage (all 19 items)
- Mermaid visualization
- Documentation integrity (links, JSON, version coherence)
- Security guarantees (no token/secret echoing, no `python3 -c` at runtime)

Out of scope:
- The Conductor CLI itself (separate project)
- Conductor server behavior (separate project)
- LLM provider correctness for AI tasks (provider-side concern)

### 1.2 Test environments

| Env | What it is | Purpose |
|-----|-----------|---------|
| **E1 — Clean** | Fresh machine, no `conductor` CLI, no Node.js, no Python beyond stdlib | Tests setup-from-zero and Python fallback path |
| **E2 — OSS local** | Local OSS Conductor server via `conductor server start` | Default dev path; covers most scenarios |
| **E3 — OSS remote** | Remote OSS Conductor with `CONDUCTOR_SERVER_URL` set, no auth | Tests remote server path |
| **E4 — OSS auth'd** | Remote OSS with `CONDUCTOR_AUTH_TOKEN` required | Tests token-based auth |
| **E5 — Orkes sandbox** | `https://developer.orkescloud.com` with key/secret credentials | Tests Orkes path: sandbox, schedules, secrets, webhooks |
| **E6 — Multi-profile** | Two profiles in `~/.conductor-cli/config.yaml` (e.g. `dev`, `prod`) | Tests profile switching |

QA must execute the test suite at minimum on E2 and E5. Each test case lists which environments it requires.

### 1.3 Prerequisites

- Claude Code (latest) for slash-command and skill testing
- A second AI coding agent (e.g. Cursor or Codex CLI) for cross-agent skill validation
- Node.js 20+ and npm (for CLI install path)
- Python 3.10+ (for validators, evals, fallback script)
- `git`, `curl`, `jq`
- API keys for eval framework: `ANTHROPIC_API_KEY` (default judge), optional `OPENAI_API_KEY` and `GEMINI_API_KEY`
- An Orkes account with key/secret for E5
- A spare repo for plugin install testing (to avoid polluting your main workspace)

---

## 2. Pre-flight (no agent required)

These run on the repo before involving any AI agent.

| ID | Description | Steps | Expected |
|----|-------------|-------|----------|
| TC-PRE-01 | Plugin manifest valid | `python3 scripts/validate_plugin.py` | `Plugin validation OK (version X.Y.Z)`; exit 0. Also covers workflow-JSON parsing (was a separate case). |
| TC-PRE-02 | All intra-repo markdown links resolve | Run the link checker (see Appendix A) | `0 broken links` |
| TC-PRE-03 | VERSION coherence | `grep -E '"version":' .claude-plugin/*.json package.json && cat VERSION` | Same version in all six places (covered by TC-PRE-01 too) |
| TC-PRE-04 | License + headers present | Inspect `LICENSE.txt`, `README.md` top | Apache 2.0 license intact, attribution present |

### 2.1 CI smoke (post-push)

The GitHub Actions `validate-plugin` workflow runs on push to `main` and on any PR touching plugin paths. This isn't pre-flight — by the time it runs, your work is already on origin.

| ID | Description | Steps | Expected |
|----|-------------|-------|----------|
| TC-CI-01 | CI runs and passes on PR | Push a branch and open a PR | GitHub Actions `validate-plugin` run is green |
| TC-CI-02 | CI catches a deliberate break | Push a commit with `version` mismatch | CI fails with a clear error from `validate_plugin.py` |

---

## 3. Plugin lifecycle (Claude Code)

| ID | Description | Env | Steps | Expected |
|----|-------------|-----|-------|----------|
| TC-PLG-01 | Install from local path | E2 | `/plugin marketplace add /path/to/conductor-skills` then `/plugin install conductor@conductor-skills` | Plugin shows in `/plugin` list at the new version |
| TC-PLG-02 | Install from GitHub marketplace | E2 | `/plugin marketplace add conductor-oss/conductor-skills` then `/plugin install conductor@conductor-skills` | Plugin installed; version matches `VERSION` |
| TC-PLG-03 | `/conductor` discoverable | E2 | After install, type `/` in chat input | `/conductor` appears in command picker with description |
| TC-PLG-04 | Three subcommands listed | E2 | Type `/conductor-` | Autocomplete shows `setup`, `optimize`, `scaffold-worker` (the bare `/conductor` is separately tested in TC-PLG-03) |
| TC-PLG-05 | Skill activates from natural language | E2 | Ask: *"What can the conductor skill do?"* | Skill activates, lists capabilities consistent with SKILL.md |
| TC-PLG-06 | Upgrade preserves config | E2 | Install vN-1, modify `~/.conductor-cli/config.yaml`, upgrade to vN | Config untouched; new version reported |
| TC-PLG-07 | Uninstall is clean | E2 | `/plugin uninstall conductor@conductor-skills` | Slash commands gone; skill no longer activates |
| TC-PLG-08 | install.sh works for non-Claude agents | E2 | `curl -sSL .../install.sh \| bash -s -- --agent codex` | Skill content installed at `~/.codex/AGENTS.md` (or path appropriate to the agent) |
| TC-PLG-09 | install.ps1 (Windows) works | E2 (Windows) | `.\install.ps1 -Agent cline` | Skill installed at `.clinerules` |
| TC-PLG-10 | `--upgrade` upgrades each agent | E2 | `bash install.sh --all --upgrade` | All previously-installed agents upgraded |
| TC-PLG-11 | `--uninstall` removes cleanly | E2 | `bash install.sh --agent cursor --uninstall` | Cursor agent's skill files removed; others untouched |

---

## 4. Slash commands

### 4.1 `/conductor` (menu)

| ID | Description | Env | Steps | Expected |
|----|-------------|-----|-------|----------|
| TC-CMD-01 | Menu lists all subcommands | E2 | `/conductor` | Output names `/conductor-setup`, `/conductor-optimize`, `/conductor-scaffold-worker` and gives natural-language examples |
| TC-CMD-02 | Menu prompts for next action | E2 | `/conductor` | Ends with a question like *"What would you like to do?"* — does not start an unprompted action |

### 4.2 `/conductor-setup`

| ID | Description | Env | Steps | Expected |
|----|-------------|-----|-------|----------|
| TC-CMD-10 | First-time on clean machine | E1 | `/conductor-setup` | Detects missing CLI; offers `npx` first; **asks before** `npm install -g` |
| TC-CMD-11 | CLI already installed | E2 | `/conductor-setup` | Skips install, moves to server choice |
| TC-CMD-12 | Local server option | E2 | `/conductor-setup`, choose Option A | Runs `conductor server start`; verifies with `conductor server status` |
| TC-CMD-13 | Remote no-auth option | E3 | `/conductor-setup`, choose Option B, no creds requested | Sets `CONDUCTOR_SERVER_URL`, `conductor workflow list` returns OK |
| TC-CMD-14 | Remote with token auth | E4 | `/conductor-setup`, server returns 401 first | Asks for token, sets `CONDUCTOR_AUTH_TOKEN`, never echoes the value |
| TC-CMD-15 | Orkes key/secret auth | E5 | `/conductor-setup` against `developer.orkescloud.com` | Asks for key + secret; sets both env vars; verifies; never echoes values |
| TC-CMD-16 | Saves named profile when asked | E5/E6 | After setup, ask "save this as profile prod" | `conductor config save --profile prod` runs; profile appears in `~/.conductor-cli/config.yaml` |
| TC-CMD-17 | `npm install -g` requires confirmation | E1 | When CLI is missing and user picks global install | Agent **explicitly confirms** before running install command |

### 4.3 `/conductor-optimize`

| ID | Description | Env | Steps | Expected |
|----|-------------|-----|-------|----------|
| TC-CMD-20 | Asks which workflow to review | E2 | `/conductor-optimize` (no arg) | Asks for file path or registered workflow name |
| TC-CMD-21 | Reviews from JSON file | E2 | `/conductor-optimize skills/conductor/examples/workflows/weather-notification.json` | Loads file; reports findings grouped CRITICAL/WARN/INFO |
| TC-CMD-22 | Reviews registered workflow | E2 | Register `weather_notification`; `/conductor-optimize weather_notification` | Calls `conductor workflow get`; reports findings |
| TC-CMD-23 | Loads each SIMPLE task definition | E2 | Use a workflow with SIMPLE tasks | Calls `conductor taskDef get` for each distinct SIMPLE task |
| TC-CMD-24 | Walks all 19 checklist items | E2 | Optimize a deliberately broken workflow (see Appendix B) | Report mentions every category A–E with at least one INFO entry per checked area |
| TC-CMD-25 | Flags missing timeouts as CRITICAL | E2 | Workflow with `responseTimeoutSeconds=0` | CRITICAL finding under B1 |
| TC-CMD-26 | Flags hardcoded secret as CRITICAL | E2 | Workflow input named `apiKey`, `token`, etc. | CRITICAL finding under D1 |
| TC-CMD-27 | Flags unbounded DO_WHILE as CRITICAL | E2 | DO_WHILE without iteration cap | CRITICAL under B5 |
| TC-CMD-28 | Flags missing description as WARN | E2 | Workflow with empty `description` | WARN under A1 |
| TC-CMD-29 | Flags 100+ task workflow | E2 | Workflow with 105 tasks | WARN under A4 |
| TC-CMD-30 | Flags single-task workflow | E2 | One-HTTP-task workflow | WARN under E2 |
| TC-CMD-31 | Offers fixes one at a time | E2 | After report, agent says "want me to apply X?" | One fix at a time, no silent application |
| TC-CMD-32 | Won't apply silently | E2 | Reply "fix everything" without specifics | Asks for confirmation per fix or proposes a plan |

### 4.4 `/conductor-scaffold-worker`

| ID | Description | Env | Steps | Expected |
|----|-------------|-----|-------|----------|
| TC-CMD-40 | Asks language and task name | E2 | `/conductor-scaffold-worker` | Asks for language; asks for task type name |
| TC-CMD-41 | Python worker | E2 | Choose Python, task `process_order` | Uses `@worker_task` decorator; `pip install conductor-python`; idempotency comment present |
| TC-CMD-42 | JavaScript/TypeScript worker | E2 | Choose JS, task `process_order` | Uses `TaskManager` from `@io-orkes/conductor-javascript`; idempotency note |
| TC-CMD-43 | Java worker (Worker iface) | E2 | Choose Java, task `process_order` | Implements `Worker` interface OR uses `@WorkerTask` |
| TC-CMD-44 | Go worker | E2 | Choose Go, task `process_order` | Uses `worker.NewTaskRunnerWithApiClient` |
| TC-CMD-45 | C# / Ruby / Rust worker — referral path | E2 | Choose C#, Ruby, or Rust; task `process_order` | `references/workers.md` does not ship inline scaffolds for these languages. Expected: agent points the user to the upstream SDK repo (e.g. github.com/conductor-oss/csharp-sdk) and asks them to follow that SDK's README. **Do NOT** verify against an inline pattern — none exists by design. |
| TC-CMD-46 | Worker name matches task type | E2 | Any language with an inline scaffold (Python/JS/Java/Go) | Worker registers for task type matching the user-supplied name exactly |
| TC-CMD-47 | Reminds about worker gate | E2 | Any | Output mentions registering the task definition / workflow |

---

## 5. Setup flows (natural-language activation)

| ID | Description | Env | Steps | Expected |
|----|-------------|-----|-------|----------|
| TC-SET-01 | "Help me set up Conductor" | E1 | Prompt agent in plain English | Agent walks `references/setup.md` Steps 1–4 |
| TC-SET-02 | Install via npx (no global) | E1 | When prompted, prefer no global install | Agent uses `npx @conductor-oss/conductor-cli ...` |
| TC-SET-03 | Connect to local server | E2 | "Connect to my local Conductor" | CLI auto-detects; no env var needed |
| TC-SET-04 | Connect to remote URL | E3 | "Connect to https://my.example.com/api" | Sets `CONDUCTOR_SERVER_URL`; verifies |
| TC-SET-05 | Connect to Orkes | E5 | "Connect to my Orkes server at developer.orkescloud.com with my key/secret" | Sets `CONDUCTOR_AUTH_KEY` + `_SECRET`; never echoes values |
| TC-SET-06 | Save profile | E6 | "Save this as profile dev" | `conductor config save --profile dev` succeeds |
| TC-SET-07 | Switch profile | E6 | "Switch to my prod profile" | All subsequent commands carry `--profile prod` |
| TC-SET-08 | Multi-env query | E6 | "How many workflows in dev vs prod?" | Two queries: one per profile; reports both counts |

---

## 6. Workflow definitions (CRUD)

| ID | Description | Env | Steps | Expected |
|----|-------------|-----|-------|----------|
| TC-DEF-01 | List all definitions | E2 | "List all workflows" | `conductor workflow list` runs; output rendered as a table |
| TC-DEF-02 | Get specific definition | E2 | "Show me the order_processing workflow" | `conductor workflow get order_processing`; JSON shown |
| TC-DEF-03 | Get specific version | E2 | "Show me v2 of order_processing" | Adds `--version 2` |
| TC-DEF-04 | Create from agent-generated JSON | E2 | "Create a workflow that fetches an API and posts a Slack message" | Writes JSON to file (not inline), runs `conductor workflow create file.json` |
| TC-DEF-05 | Worker gate runs after create | E2 | After TC-DEF-04 if any SIMPLE task | `conductor taskDef list` runs; missing workers flagged with offer to scaffold |
| TC-DEF-06 | Worker gate runs after update | E2 | Update an existing workflow that gains a SIMPLE task | Worker gate re-runs |
| TC-DEF-07 | Update existing definition | E2 | "Add a notification step to weather_notification" | Reads existing, modifies, calls `conductor workflow update` |
| TC-DEF-08 | Delete definition | E2 | "Delete weather_notification v1" | Confirms intent, runs `conductor workflow delete weather_notification 1` |
| TC-DEF-09 | Won't delete without confirmation | E2 | "Delete weather_notification" without specifying intent | Agent confirms before running delete |
| TC-DEF-10 | Validate before create | E2 | Submit a definition with a duplicate `taskReferenceName` | Agent catches the duplicate before sending |

---

## 7. Task definitions (CRUD)

| ID | Description | Env | Steps | Expected |
|----|-------------|-----|-------|----------|
| TC-TDF-01 | List task defs | E2 | "List task definitions" | `conductor taskDef list` |
| TC-TDF-02 | Get task def | E2 | "Show task def process_order" | `conductor taskDef get process_order` |
| TC-TDF-03 | Create task def from JSON | E2 | "Create a task definition for `process_order` with a 30-second response timeout" | Writes JSON to file, `conductor taskDef create file.json` |
| TC-TDF-04 | Update task def | E2 | "Increase retryCount on process_order to 5" | Reads existing, updates, sends |
| TC-TDF-05 | Delete task def | E2 | "Delete the process_order task def" | Confirms; deletes |
| TC-TDF-06 | Fallback path is missing | E1 (fallback) | When using fallback script, ask to list task defs | Agent reports the fallback doesn't support task-def CRUD; offers to install CLI |

---

## 8. Workflow execution

| ID | Description | Env | Steps | Expected |
|----|-------------|-----|-------|----------|
| TC-RUN-01 | Start async with inline input | E2 | "Run weather_notification with city=SF" | `conductor workflow start -w weather_notification -i '{...}'`; returns workflowId |
| TC-RUN-02 | Start with file input | E2 | "Run with this large input" + bigger payload | Writes JSON file, uses `-f input.json` |
| TC-RUN-03 | Start synchronous | E2 | "Run and wait for completion" | Uses `--sync`; returns terminal status |
| TC-RUN-04 | Wait until specific task | E2 | "Run and wait until the approval step" | Uses `--sync -u approval` |
| TC-RUN-05 | Specific version | E2 | "Run v3 of order_processing" | `--version 3` |
| TC-RUN-06 | With correlation ID | E2 | "Run order_processing for order #42" | `--correlation order-42` |
| TC-RUN-07 | Get execution by ID | E2 | "What's the status of `wf-123`?" | `conductor workflow get-execution wf-123 -c` |
| TC-RUN-08 | Quick status | E2 | "Just give me the status of `wf-123`" | `conductor workflow status wf-123` |
| TC-RUN-09 | Get by correlation ID | E2 | "Show me the workflow for order #42" | Resolves via correlation ID |

---

## 9. Workflow monitoring & search

| ID | Description | Env | Steps | Expected |
|----|-------------|-----|-------|----------|
| TC-MON-01 | Search by status | E2 | "Show all running workflows" | `conductor workflow search -s RUNNING` |
| TC-MON-02 | Search by name + status | E2 | "Show failed weather_notification runs" | `-w weather_notification -s FAILED` |
| TC-MON-03 | Search by time range | E2 | "Failed workflows from yesterday" | Uses `--start-time-after` / `--start-time-before` |
| TC-MON-04 | Render results as table | E2 | TC-MON-01 result | Markdown table with workflowId, name, status, startTime |
| TC-MON-05 | Pagination respected | E2 | "First 50 failed workflows" | `-c 50` |
| TC-MON-06 | Diagnose failure | E2 | "Why did `wf-456` fail?" | Loads execution, identifies failed task + reason |

---

## 10. Workflow management

| ID | Description | Env | Steps | Expected |
|----|-------------|-----|-------|----------|
| TC-MGT-01 | Pause running workflow | E2 | "Pause `wf-123`" | `conductor workflow pause wf-123` |
| TC-MGT-02 | Resume paused workflow | E2 | "Resume `wf-123`" | `conductor workflow resume wf-123` |
| TC-MGT-03 | Terminate with reason | E2 | "Terminate `wf-123`, customer cancelled" | Uses `--reason` |
| TC-MGT-04 | Restart completed | E2 | "Restart `wf-123`" | `conductor workflow restart wf-123` |
| TC-MGT-05 | Restart with latest definition | E2 | "Restart `wf-123` on the latest version" | Adds `--use-latest` |
| TC-MGT-06 | Retry last failed task | E2 | "Retry `wf-123`" | `conductor workflow retry wf-123` |
| TC-MGT-07 | Rerun from a specific task | E2 | "Rerun `wf-123` from validate_order" | `--task-id` |
| TC-MGT-08 | Skip a task | E2 | "Skip the email step in `wf-123`" | `conductor workflow skip-task` |
| TC-MGT-09 | Jump to a task | E2 | "Jump `wf-123` to fulfill_order" | `conductor workflow jump` |
| TC-MGT-10 | Distinguish retryable vs terminal | E2 | Workflow that failed with `FAILED_WITH_TERMINAL_ERROR` | Agent refuses retry, explains why |
| TC-MGT-11 | Batch retry | E2 | "Retry every failed weather_notification from today" | Searches first, then retries each in turn |

---

## 11. Task signaling (WAIT / HUMAN / async)

| ID | Description | Env | Steps | Expected |
|----|-------------|-----|-------|----------|
| TC-SIG-01 | Identify blocking task | E2 | "Why is `wf-123` stuck?" | Lists tasks, identifies task in IN_PROGRESS with type WAIT/HUMAN |
| TC-SIG-02 | Signal async | E2 | "Approve the wait task in `wf-123`" | `conductor task signal --status COMPLETED ...` |
| TC-SIG-03 | Signal sync | E2 | "Approve and tell me what runs next" | `conductor task signal-sync ...` |
| TC-SIG-04 | Pass output payload | E2 | "Approve with payment ID pay-456" | `--output '{"paymentId":"pay-456"}'` |
| TC-SIG-05 | Reject with FAILED | E2 | "Reject the wait task" | `--status FAILED` |
| TC-SIG-06 | Reject with terminal | E2 | "Permanently reject — don't retry" | `--status FAILED_WITH_TERMINAL_ERROR` |
| TC-SIG-07 | HUMAN task | E2 | Workflow with a HUMAN task | Same signaling pattern as WAIT |

---

## 12. Task type coverage

One workflow per task type, registered and run end-to-end. Drive each via natural-language prompts to the agent.

| ID | Task type | Env | Test idea | Expected |
|----|-----------|-----|-----------|----------|
| TC-TYP-01 | SIMPLE | E2 | Workflow → SIMPLE task → registered worker (Python) | Worker polls, executes, returns; workflow completes |
| TC-TYP-02 | HTTP | E2 | HTTP GET to a public JSON endpoint | `${ref.output.response.body}` accessible downstream |
| TC-TYP-03 | INLINE | E2 | INLINE with `$.value * 2` | All `$.x` declared in inputParameters |
| TC-TYP-04 | JSON_JQ_TRANSFORM | E2 | Filter array of items | `result` has expected shape |
| TC-TYP-05 | SWITCH (value-param) | E2 | Branch on `${workflow.input.type}` | Correct branch executes |
| TC-TYP-06 | SWITCH (javascript) | E2 | JS expression branching | All `$.x` declared |
| TC-TYP-07 | FORK_JOIN | E2 | Two parallel HTTP calls + JOIN | Both branches run; JOIN aggregates |
| TC-TYP-08 | DO_WHILE | E2 | Loop 5 iterations with self-reference | `iteration` increments; loop_ref output present |
| TC-TYP-09 | WAIT (signal) | E2 | Wait until external signal | Workflow stays IN_PROGRESS until signaled |
| TC-TYP-10 | WAIT (duration) | E2 | `"duration": "10s"` | Resumes ~10 s later |
| TC-TYP-11 | WAIT (until) | E2 | `"until": "<timestamp 1 min from now>"` | Resumes at that time |
| TC-TYP-12 | HUMAN | E2 | HUMAN task signaled via UI or API | Behaves like WAIT signal |
| TC-TYP-13 | SUB_WORKFLOW | E2 | Parent calling registered child | Parent waits; reads child output |
| TC-TYP-14 | START_WORKFLOW | E2 | Parent fires-and-forgets a child | Parent completes immediately; output has child's `workflowId` |
| TC-TYP-15 | DYNAMIC | E2 | `dynamicTaskNameParam` resolves to a real task | Resolved task runs |
| TC-TYP-16 | FORK_JOIN_DYNAMIC | E2 | Generate 3 branches at runtime | All branches run; JOIN aggregates |
| TC-TYP-17 | EXCLUSIVE_JOIN | E2 | Two branches racing | First to complete wins |
| TC-TYP-18 | EVENT | E2 | Publish to `conductor:my_event` | Event sink shows the message |
| TC-TYP-19 | KAFKA_PUBLISH | E2 + Kafka | Publish to test topic | Kafka receives message; key/headers preserved |
| TC-TYP-20 | SET_VARIABLE | E2 | Set then read in subsequent task | Variable visible via `${workflow.variables.x}` |
| TC-TYP-21 | TERMINATE | E2 | Early-exit with COMPLETED | Workflow ends in COMPLETED with provided output |
| TC-TYP-22 | NOOP | E2 | Use as default branch | Completes immediately, no side effect |
| TC-TYP-23 | LLM_CHAT_COMPLETE | E2/E5 + provider | Chat with OpenAI provider | `result` contains response text; token counts in output |
| TC-TYP-24 | LLM_TEXT_COMPLETE | Same | Single completion | `result`, `tokenUsed` in output |
| TC-TYP-25 | LLM_GENERATE_EMBEDDINGS | Same | Embed a string | `result` is a float array |
| TC-TYP-26 | GENERATE_IMAGE | Same | DALL-E or similar | `url` or `b64_json` returned |
| TC-TYP-27 | GENERATE_AUDIO | Same | TTS | `media` array with location + mimeType |
| TC-TYP-28 | GENERATE_VIDEO | Same | Sora or Veo | `media` with video URL; async polling handled |
| TC-TYP-29 | LLM_INDEX_TEXT | Same + vectorDB | Index a doc into Pinecone | Returns success; subsequent search finds it |
| TC-TYP-30 | LLM_STORE_EMBEDDINGS | Same | Store pre-computed | Stored under docId |
| TC-TYP-31 | LLM_SEARCH_INDEX | Same | Semantic search | Returns hits |
| TC-TYP-32 | LLM_SEARCH_EMBEDDINGS | Same | Vector search | Returns hits |
| TC-TYP-33 | LLM_GET_EMBEDDINGS | Same | Retrieve by docId | Returns float array |
| TC-TYP-34 | LIST_MCP_TOOLS | E2 + MCP server | List tools from MCP endpoint | Returns array of tool descriptors |
| TC-TYP-35 | CALL_MCP_TOOL | Same | Call a known tool | Returns `content` array |

---

## 13. Visualization

| ID | Description | Env | Steps | Expected |
|----|-------------|-----|-------|----------|
| TC-VIS-01 | Sequential flow | E2 | "Show me a diagram of weather_notification" | `flowchart TD` with `-->` between two HTTP nodes |
| TC-VIS-02 | SWITCH | E2 | Workflow with SWITCH | Diamond node, labeled edges per case + default |
| TC-VIS-03 | FORK_JOIN | E2 | Workflow with FORK_JOIN | Fork → branches → JOIN |
| TC-VIS-04 | DO_WHILE | E2 | Workflow with DO_WHILE | Loop edge from body back to loop node |
| TC-VIS-05 | SUB_WORKFLOW | E2 | Parent + child | Rounded sub-workflow node |
| TC-VIS-06 | WAIT / HUMAN | E2 | Workflow with WAIT | Parallelogram node |
| TC-VIS-07 | No forbidden chars in edge labels | E2 | Any | Edge labels do not contain `{}[]()` |
| TC-VIS-08 | UI link offered | E2 | After diagram, agent gives UI URL | URL is `BASE_URL/workflowDef/<name>` with `/api` stripped |

---

## 14. Schedules (OSS)

Per the latest skill version, schedules are OSS, not Orkes-only.

| ID | Description | Env | Steps | Expected |
|----|-------------|-----|-------|----------|
| TC-SCH-01 | List schedules | E2 | "List my schedules" | `conductor schedule list` |
| TC-SCH-02 | Create daily schedule | E2 | "Schedule cleanup_workflow daily at 2am" | Writes JSON, `conductor schedule create file.json` with cron `0 0 2 * * ?` |
| TC-SCH-03 | Create with correlation pattern | E2 | "Use a daily correlation ID" | `correlationId` in `startWorkflowRequest` includes a date-derived value |
| TC-SCH-04 | Update schedule | E2 | "Change cleanup to 3am" | Reads existing, updates cron, sends |
| TC-SCH-05 | Pause schedule | E2 | "Pause the cleanup schedule" | `conductor schedule pause cleanup` |
| TC-SCH-06 | Resume schedule | E2 | "Resume cleanup" | `conductor schedule resume cleanup` |
| TC-SCH-07 | Delete schedule | E2 | "Delete cleanup" | Confirms, deletes |
| TC-SCH-08 | Cron parses correctly | E2 | "Every 15 minutes" | Generates `0 */15 * * * ?` |
| TC-SCH-09 | Quartz quirk respected | E2 | "Every Monday at noon" | Day-of-month is `?` (since dow is set) |
| TC-SCH-10 | Search executions by correlation | E2 | "Show me last 50 scheduled cleanup runs" | Searches by `correlationId:scheduled-*` (or whatever pattern was used) |

---

## 15. Orkes-only features (E5)

| ID | Description | Env | Steps | Expected |
|----|-------------|-----|-------|----------|
| TC-ORK-01 | Connect to developer.orkescloud.com | E5 | Setup with key/secret for sandbox | `conductor workflow list` succeeds |
| TC-ORK-02 | Secret put | E5 | "Save STRIPE_KEY = sk_test_..." | `conductor secret put STRIPE_KEY <value>`; value never echoed |
| TC-ORK-03 | Secret get (name only) | E5 | "Do I have a Stripe secret?" | Lists name; does NOT echo the value |
| TC-ORK-04 | Secret list | E5 | "List my secrets" | Names only, no values |
| TC-ORK-05 | Secret delete | E5 | "Delete STRIPE_KEY" | Confirms, deletes |
| TC-ORK-06 | Reference secret in workflow | E5 | Use `${workflow.secrets.STRIPE_KEY}` in HTTP header | Workflow runs; secret value resolved server-side |
| TC-ORK-07 | Webhook list | E5 | "List webhooks" | `conductor webhook list` |
| TC-ORK-08 | Webhook create | E5 | "Create a GitHub webhook for github_pr_handler workflow" | Writes JSON, creates, surfaces returned URL |
| TC-ORK-09 | Webhook returns URL | E5 | After TC-ORK-08 | Agent shows the actual returned URL — not a placeholder |
| TC-ORK-10 | Webhook delete | E5 | "Delete the GitHub webhook" | Confirms, deletes |
| TC-ORK-11 | Enterprise command on OSS fails clearly | E2 | Try `conductor secret list` against OSS | Agent reports it's an Orkes-only feature; suggests checking server endpoint |

---

## 16. Optimization checklist coverage

For each item in `references/optimization.md`, prepare a workflow that violates it and confirm `/conductor-optimize` reports it.

### A. Structure & maintainability

| ID | Item | Test workflow | Expected severity |
|----|------|---------------|-------------------|
| TC-OPT-A1 | A1 Description present | `description: ""` | WARN |
| TC-OPT-A2 | A2 ownerEmail set | No ownerEmail | WARN |
| TC-OPT-A3 | A3 schemaVersion: 2 | `schemaVersion: 1` | WARN |
| TC-OPT-A4 | A4 Task count | 105 tasks | WARN |
| TC-OPT-A5 | A5 Descriptive task ref | `taskReferenceName: "task1"` | INFO/WARN |
| TC-OPT-A6 | A6 Three timeouts (educational) | Task def missing pollTimeoutSeconds | Agent explains the three timeouts and points to B1 for severity |
| TC-OPT-A7 | A7 Versioning hygiene | Workflow edited in place with executions in last 30d | WARN (manually verify against execution history) |

### B. Reliability

| ID | Item | Test workflow | Expected severity |
|----|------|---------------|-------------------|
| TC-OPT-B1 | B1 Task timeouts | `responseTimeoutSeconds: 0` | CRITICAL |
| TC-OPT-B2 | B2 Workflow timeout | No `timeoutSeconds` | WARN |
| TC-OPT-B3 | B3 Retry policy | `retryCount: 0` on email task | WARN |
| TC-OPT-B4 | B4 failureWorkflow | None set; workflow mutates external state | WARN |
| TC-OPT-B5 | B5 DO_WHILE cap | No `iteration < N` clause | CRITICAL |
| TC-OPT-B6 | B6 Optional branches | Best-effort notification, not optional | INFO |
| TC-OPT-B7 | B7 Rate / concurrent limits | External API task with no rate limit | WARN |

### C. Performance & complexity

| ID | Item | Test workflow | Expected severity |
|----|------|---------------|-------------------|
| TC-OPT-C1 | C1 INLINE scope | 60-line INLINE script | WARN |
| TC-OPT-C2 | C2 Prefer JQ | INLINE doing pure data shaping | INFO |
| TC-OPT-C3 | C3 Bounded fan-out | Static FORK_JOIN with 50 branches | WARN |
| TC-OPT-C4 | C4 asyncComplete | Long-running task without it | INFO |
| TC-OPT-C5 | C5 SUB_WORKFLOW reuse | Sub-workflow used by exactly one parent | WARN |

### D. Security & inputs

| ID | Item | Test workflow | Expected severity |
|----|------|---------------|-------------------|
| TC-OPT-D1 | D1 Secrets in input | Input named `apiKey` | CRITICAL |
| TC-OPT-D2 | D2 Hardcoded URLs | `uri: "https://prod.example.com"` | WARN |
| TC-OPT-D3 | D3 Output API stability | Workflow renamed an output param in place | WARN |

### E. Wrong tool

| ID | Item | Test workflow | Expected severity |
|----|------|---------------|-------------------|
| TC-OPT-E1 | E1 Latency-critical | "Use case: synchronous web request, P95 50ms" | WARN |
| TC-OPT-E2 | E2 Single-task workflow | One HTTP task only | WARN |
| TC-OPT-E3 | E3 Large payload | Input contains 10 MB string | WARN/CRITICAL |

---

## 17. Fallback path (Python REST script)

| ID | Description | Env | Steps | Expected |
|----|-------------|-----|-------|----------|
| TC-FBK-01 | No CLI, no npm | E1 (no Node) | Ask agent to do anything | Falls back to `scripts/conductor_api.py`; exports `CONDUCTOR_API` |
| TC-FBK-02 | List workflows via fallback | E1 | "List workflows" | `python3 "$CONDUCTOR_API" list-workflows` |
| TC-FBK-03 | Create + start via fallback | E1 | "Create + run a simple workflow" | Both run via fallback script |
| TC-FBK-04 | Search via fallback | E1 | "Show running workflows" | Uses `--query` / `--status`; agent notes time-range filter unsupported |
| TC-FBK-05 | Signal task via fallback | E1 | "Signal the wait task" | `signal-task` or `signal-task-sync` |
| TC-FBK-06 | Auth: token only | E1 + auth | Set `CONDUCTOR_AUTH_TOKEN` | Works |
| TC-FBK-07 | Auth: key/secret rejected | E1 + Orkes | Set `CONDUCTOR_AUTH_KEY` only | Agent reports fallback doesn't support key/secret; recommends installing CLI |
| TC-FBK-08 | TaskDef CRUD unsupported | E1 | "Create a task def" | Agent reports fallback doesn't cover taskDef commands |
| TC-FBK-09 | Schedules unsupported | E1 | "Schedule cleanup daily" | Agent reports fallback doesn't cover schedules |
| TC-FBK-10 | Retries with backoff | E1 (server returns 500) | Run any command | Fallback retries 3× with exponential backoff |

---

## 18. Error handling

| ID | Description | Env | Steps | Expected |
|----|-------------|-----|-------|----------|
| TC-ERR-01 | 401 Unauthorized | E4 (bad token) | Run any command | Agent suggests checking `CONDUCTOR_AUTH_TOKEN`; doesn't echo it |
| TC-ERR-02 | 403 Forbidden | E5 (limited token) | Try a privileged op | Agent confirms creds have access; suggests escalation |
| TC-ERR-03 | 404 workflow not found | E2 | "Show me wf-doesnotexist" | Agent suggests `workflow list` or `search` |
| TC-ERR-04 | 409 already exists | E2 | Create a definition that already exists at v1 | Agent suggests bumping version or update |
| TC-ERR-05 | Connection refused | E2 (server down) | Any command | Agent verifies `CONDUCTOR_SERVER_URL`, suggests `server start` |
| TC-ERR-06 | 5xx server error | E2 (forced) | Any command | CLI/fallback retries; agent surfaces final error |
| TC-ERR-07 | Stuck on missing worker | E2 | Start a workflow whose SIMPLE task has no worker | `queue-size > 0`; agent recommends scaffolding |
| TC-ERR-08 | Terminal task failure | E2 | Workflow with `FAILED_WITH_TERMINAL_ERROR` | Agent refuses retry, explains why |
| TC-ERR-09 | Persistent timeouts | E2 | Repeatedly TIMED_OUT task | Agent recommends raising `responseTimeoutSeconds` |
| TC-ERR-10 | Invalid workflow JSON | E2 | Submit malformed JSON | Agent catches before sending or surfaces server error clearly |

---

## 19. Security

| ID | Description | Env | Steps | Expected |
|----|-------------|-----|-------|----------|
| TC-SEC-01 | Token never echoed in chat | E4 | "What's my Conductor token?" | Agent declines or refers to env var by name only |
| TC-SEC-02 | Token never echoed in commands | E4 | Inspect agent-issued shell commands | No `echo $CONDUCTOR_AUTH_TOKEN` or token literal |
| TC-SEC-03 | Key/secret never echoed | E5 | Same as TC-SEC-01/02 for `CONDUCTOR_AUTH_KEY`/`_SECRET` | Same |
| TC-SEC-04 | Orkes secret values never echoed | E5 | After `secret put`, ask "what was the value?" | Agent confirms by name only; doesn't print value |
| TC-SEC-05 | No `python3 -c` at runtime | E2 | Watch agent's tool calls during any session | Never invokes `python3 -c`; uses script files only |
| TC-SEC-06 | Sensitive workflow input flagged | E2 | Workflow with input named `apiKey` | Optimization review flags D1 CRITICAL |
| TC-SEC-07 | Hardcoded URL flagged | E2 | Workflow with `uri: "https://prod.example.com/..."` | Optimization review flags D2 WARN |
| TC-SEC-08 | npm install -g requires consent | E1 | Setup flow | Asks before running global install |

---

## 20. Multi-environment / profile switching

| ID | Description | Env | Steps | Expected |
|----|-------------|-----|-------|----------|
| TC-PRF-01 | Save profile | E6 | "Save current connection as dev" | `conductor config save --profile dev` |
| TC-PRF-02 | Save second profile | E6 | "Save another connection as prod" | Both appear in `~/.conductor-cli/config.yaml` |
| TC-PRF-03 | Use profile flag | E6 | "List workflows in dev" | Adds `--profile dev` |
| TC-PRF-04 | Profile inferred from context | E6 | "How many failed today in prod?" | Uses `--profile prod` automatically |
| TC-PRF-05 | Confirm ambiguous profile | E6 | "Run on production" when only `prod` exists | Agent confirms or just uses `prod` (if unambiguous) |
| TC-PRF-06 | Cross-env query | E6 | "Compare workflow counts in dev vs prod" | Two separate `--profile` queries; reports both |

---

## 21. Cross-agent sanity (skill content only)

The slash commands are Claude Code-specific. Confirm the **skill content** still works for other agents on a basic create/run/monitor flow.

| ID | Agent | Test |
|----|-------|------|
| TC-AGT-01 | Cursor | Install via `bash install.sh --agent cursor`. Ask: "create a Conductor workflow that ..." Expect: skill content activates |
| TC-AGT-02 | Codex CLI | Same |
| TC-AGT-03 | Gemini CLI | Same |
| TC-AGT-04 | Windsurf | Same |
| TC-AGT-05 | Cline | Same (project-level install) |
| TC-AGT-06 | GitHub Copilot | Same |
| TC-AGT-07 | Aider | Same |
| TC-AGT-08 | Amazon Q | Same |
| TC-AGT-09 | Roo Code | Same |
| TC-AGT-10 | Amp | Same |
| TC-AGT-11 | OpenCode | Same |

---

## 22. Eval framework

| ID | Description | Env | Steps | Expected |
|----|-------------|-----|-------|----------|
| TC-EVL-01 | Run all evals (Anthropic) | Any | `python3 scripts/run_evals.py` | Exits 0, all scenarios pass |
| TC-EVL-02 | Run all evals (OpenAI) | Any | `python3 scripts/run_evals.py --model gpt-4o` | Exits 0 |
| TC-EVL-03 | Run all evals (Gemini) | Any | `python3 scripts/run_evals.py --model gemini-2.5-pro` | Exits 0 |
| TC-EVL-04 | Run a single eval | Any | `python3 scripts/run_evals.py evaluations/create-and-run-workflow.json` | Single result printed |
| TC-EVL-05 | JSON report | Any | `python3 scripts/run_evals.py --json -o report.json` | Valid JSON file written |
| TC-EVL-06 | Verbose mode | Any | `... --verbose` | Full agent response printed |
| TC-EVL-07 | Cross-provider compare | Any | Run twice with different `--model` | Reports differ; both still pass |
| TC-EVL-08 | New optimization eval | Any | (Once added) `optimize-workflow.json` | Passes |
| TC-EVL-09 | Failing eval correctly fails | Any | Edit a scenario to add an impossible criterion | Exit code 1, scenario reported as failed |

---

## 23. Documentation integrity

| ID | Description | Steps | Expected |
|----|-------------|-------|----------|
| TC-DOC-01 | Intra-repo links resolve | See Appendix A | 0 broken |
| TC-DOC-02 | All workflow JSONs parse | See Appendix B | All OK |
| TC-DOC-03 | SKILL.md frontmatter complete | Inspect | `name`, `description`, `allowed-tools` present |
| TC-DOC-04 | Every command file has description | `validate_plugin.py` | OK |
| TC-DOC-05 | No play.orkes.io references | `grep -r "play.orkes" .` | 0 matches |
| TC-DOC-06 | All references files cross-link | Inspect | Each ref file points back to `SKILL.md` or sibling refs where relevant |
| TC-DOC-07 | All examples reference correct paths | Inspect each `examples/*.md` | Paths to `references/` and `workflows/` are correct |

---

## 24. Regression / smoke (run before every release)

This is the quick subset to run before tagging a release. ~30 minutes.

| ID | Description |
|----|-------------|
| TC-SMK-01 | TC-PRE-01 through TC-PRE-05 (pre-flight) |
| TC-SMK-02 | TC-PLG-01 (local install) |
| TC-SMK-03 | TC-PLG-03, TC-PLG-04 (commands discoverable) |
| TC-SMK-04 | TC-CMD-10, TC-CMD-12 (setup local OSS) |
| TC-SMK-05 | TC-CMD-21 (optimize from file) |
| TC-SMK-06 | TC-CMD-41 (Python worker scaffold) |
| TC-SMK-07 | TC-DEF-04, TC-DEF-05 (create + worker gate) |
| TC-SMK-08 | TC-RUN-01, TC-RUN-07 (start + status) |
| TC-SMK-09 | TC-VIS-01 (Mermaid) |
| TC-SMK-10 | TC-SEC-01, TC-SEC-05 (token redaction, no python3 -c) |
| TC-SMK-11 | TC-EVL-01 (eval suite passes) |
| TC-SMK-12 | TC-DOC-01, TC-DOC-05 (links + no play.orkes) |
| TC-SMK-13 | TC-ORK-01 (Orkes connect, sandbox) |

---

## 25. Sign-off matrix

| Area | Owner | Pass / Fail / Blocked / Skipped | Notes |
|------|-------|-------------------------------|-------|
| Pre-flight (§2) | | | |
| Plugin lifecycle (§3) | | | |
| Slash commands (§4) | | | |
| Setup flows (§5) | | | |
| Workflow CRUD (§6) | | | |
| Task CRUD (§7) | | | |
| Execution (§8) | | | |
| Monitoring (§9) | | | |
| Management (§10) | | | |
| Signaling (§11) | | | |
| Task type coverage (§12) | | | |
| Visualization (§13) | | | |
| Schedules (§14) | | | |
| Orkes (§15) | | | |
| Optimization (§16) | | | |
| Fallback (§17) | | | |
| Error handling (§18) | | | |
| Security (§19) | | | |
| Multi-env (§20) | | | |
| Cross-agent (§21) | | | |
| Evals (§22) | | | |
| Docs (§23) | | | |

---

## Appendix A — Markdown link checker

Run from repo root:

```bash
python3 - <<'PY'
import re, os, sys
broken = []
for dp, _, fs in os.walk("."):
    if any(part in dp for part in [".git", "node_modules"]):
        continue
    for f in fs:
        if not f.endswith(".md"): continue
        p = os.path.join(dp, f)
        text = open(p).read()
        for m in re.findall(r'\]\(([^)]+)\)', text):
            if m.startswith(("http", "#", "mailto:")): continue
            target = m.split("#")[0]
            if not target: continue
            resolved = os.path.normpath(os.path.join(dp, target))
            if not os.path.exists(resolved):
                broken.append(f"{p} -> {m}")
for b in broken: print("BROKEN:", b)
print(f"{len(broken)} broken")
sys.exit(1 if broken else 0)
PY
```

## Appendix B — Workflow JSON validator

```bash
python3 - <<'PY'
import json, glob, sys
bad = 0
for p in sorted(glob.glob("skills/*/examples/workflows/*.json")):
    try:
        json.load(open(p))
        print("OK ", p)
    except Exception as e:
        print("BAD", p, e); bad += 1
sys.exit(bad)
PY
```

## Appendix C — Sample broken workflow for optimization tests

For TC-CMD-24 and the TC-OPT-* series, use this deliberately-bad workflow (save as `tests/fixtures/bad-workflow.json`):

```json
{
  "name": "broken_pipeline",
  "description": "",
  "schemaVersion": 1,
  "tasks": [
    {
      "name": "charge_card",
      "taskReferenceName": "task1",
      "type": "SIMPLE",
      "inputParameters": {
        "apiKey": "${workflow.input.apiKey}"
      }
    },
    {
      "name": "loop",
      "taskReferenceName": "loop_ref",
      "type": "DO_WHILE",
      "loopCondition": "if ($.done) { false } else { true }",
      "loopOver": [
        {"name": "noop", "taskReferenceName": "noop_ref", "type": "NOOP"}
      ],
      "inputParameters": {
        "done": false
      }
    },
    {
      "name": "compute",
      "taskReferenceName": "compute",
      "type": "INLINE",
      "inputParameters": {
        "evaluatorType": "graaljs",
        "expression": "<paste 60 lines of business logic here for C1>",
        "x": 1
      }
    },
    {
      "name": "send_email",
      "taskReferenceName": "send_email",
      "type": "SIMPLE"
    }
  ]
}
```

A matching `task_def_charge_card.json` with `responseTimeoutSeconds: 0` and `retryCount: 0` registered alongside it triggers TC-OPT-B1 / TC-OPT-B3.

---

*End of plan. Last updated: this version of `VERSION`.*
