# Orkes Integrations — AI Providers, Models and Access

On **OSS** Conductor an LLM provider is enabled by putting its key in the server's environment (`OPENAI_API_KEY`, …) and `llmProvider` is the provider name (`openai`). On **Orkes Conductor** (Enterprise — the server **requires auth**; check with `python3 "$CONDUCTOR_API" server-info`, SKILL.md Rule 17) that is not how it works: every provider is a named **integration** on the cluster, every model must be **registered under that integration**, and the calling application needs **access** to it. Skip any of the three and `LLM_*` tasks fail even though the workflow JSON is valid.

| Concept | What it is | Where it shows up in a task |
|---|---|---|
| Integration (provider) | A named, credential-backed connection, e.g. `openai-prod` of type `openai` | `llmProvider: "openai-prod"` — the **integration name**, not the type |
| Model (integration resource) | An exact provider model id registered under the integration, e.g. `gpt-4o-mini` | `model: "gpt-4o-mini"` |
| Access | Permission for an application / group / role on the integration | none — missing access surfaces as a 403 / access error at run time |

The `conductor` CLI has **no integration commands** (and `conductor doctor` only checks *local* env vars — it says nothing about the cluster's integrations). Use the bundled script even when the CLI is installed: `export CONDUCTOR_API="<path-to-this-skill>/scripts/conductor_api.py"`. It authenticates from `CONDUCTOR_SERVER_URL` + `CONDUCTOR_AUTH_KEY` / `CONDUCTOR_AUTH_SECRET`, or from a saved CLI profile with `--profile <name>` (the script reads the profile itself and never prints it — you still never open the YAML). Every `*-env` flag takes an environment variable **name** (`OPENAI_API_KEY`), never `$OPENAI_API_KEY` or the value.

## 1. Check what exists — before writing any LLM task for Orkes

```bash
python3 "$CONDUCTOR_API" integration-list --category AI_MODEL     # names, types; secret config masked
python3 "$CONDUCTOR_API" model-list --provider openai-prod          # models registered under one integration
```

- Suitable integration **and** model exist → use their names; tell the user which names the workflow will use.
- Integration exists but lacks the model → add it to that integration (§3: `model-save` or `model-sync`); don't create a parallel integration.
- Listing returns **403** → this application may not manage integrations; ask the user for the integration name to use (or for an admin to create it / grant rights) instead of guessing or creating one.

## 2. Create the integration (persistent change — confirm with the user first)

The key comes from an environment variable the user set securely (shell, CI secret store) — never chat, never a command-line value, never workflow JSON. `--config-env KEY=ENV_VAR` reads it; `--config KEY=VALUE` is for non-secret fields and refuses secret-looking keys.

```bash
python3 "$CONDUCTOR_API" integration-save --name openai-prod --type openai \
  --config-env api_key=OPENAI_API_KEY --description "OpenAI for prod workflows"
```

| `--type` | Configuration keys (secret ones via `--config-env`) |
|---|---|
| `openai` | `api_key`; optional `endpoint`, `organizationId` |
| `anthropic` | `api_key`, `endpoint` (e.g. `https://api.anthropic.com`); optional `version`, `betaVersion`, `completionsPath` |
| `azure_openai` | `api_key`, `endpoint` |
| `vertex_ai` / `vertex_ai_gemini` | `projectName`, `environment` (region), `publisher`, `file` (service-account JSON) |
| `aws_bedrock_anthropic` / `aws_bedrock_cohere` / `aws_bedrock_titan` | `connectionType`, `region`; `ACCESS_KEY` → `user`, `api_key`; `EXTERNAL_ROLE` → `roleArn`, `externalId` |
| `mistral`, `cohere`, `grok`, `perplexity`, `huggingface` | `api_key` (+ `endpoint` where the provider needs one) |
| `ollama` | `endpoint` |
| Vector DBs (`--category VECTOR_DB`): `pineconedb`, `weaviatedb`, `pgvectordb`, `mongovectordb` | provider-specific; run `integration-defs --category VECTOR_DB` |

Secret-looking fields (`*key*`, `*secret*`, `*token*`, `*password*`, `*credential*`, `file`) are only accepted via `--config-env`, e.g. Vertex `--config-env file=VERTEX_SA_JSON` where the variable holds the service-account JSON. For any type not listed, or to confirm field names on this cluster, run `python3 "$CONDUCTOR_API" integration-defs --category AI_MODEL`. The `type` cannot be changed after creation. `integration-save` refuses an existing `--name`: `--overwrite` replaces the **whole** configuration, so pass every secret field again with `--config-env` or it is cleared.

## 3. Register the models — all of them, discovered live

When creating an AI integration, register **every model the key can use**, not just the one the current workflow needs, so later workflows and agents don't hit "model not found". Discover models live — never from memory, they change monthly.

**Providers with a model-list API** (`openai`, `anthropic`, `mistral`, `cohere`, `grok`, `ollama`, and Gemini-API keys via `--source gemini`): ask the provider with the same key, then register the lot.

```bash
python3 "$CONDUCTOR_API" model-sync --provider openai-prod --type openai --key-env OPENAI_API_KEY --dry-run   # preview
python3 "$CONDUCTOR_API" model-sync --provider openai-prod --type openai --key-env OPENAI_API_KEY             # register all
```

`model-sync` calls the provider's own list endpoint (the key is sent only there), skips models already registered and fine-tunes (`--include-fine-tunes` to keep them), registers the rest, and reports `added` / `failed`. The integration must exist first. `--include` / `--exclude` take regexes when the user wants a subset (e.g. `--exclude '-[0-9]{4}-[0-9]{2}-[0-9]{2}$'` drops dated snapshots). `provider-models` prints the same list without touching Orkes. Custom gateways and Ollama hosts: `--endpoint <url>`.

**Providers without one** (`azure_openai` — models are the user's *deployment names*, ask for them; `aws_bedrock_*`, `vertex_ai*`, `perplexity`, `huggingface`): use **WebSearch / WebFetch** on the provider's official models page (e.g. "Amazon Bedrock supported models", "Vertex AI model garden Gemini models", "Perplexity API models") for the current model ids, show the list, then `model-save` each one. Bedrock ids must also be enabled in the user's AWS account/region.

**Either way, also look up what's current**: WebSearch / WebFetch the provider's models or deprecations page and tell the user which registered models are the latest (and which are deprecated), and use the latest suitable one as the workflow's default `model` — not a model remembered from training.

Single model: `python3 "$CONDUCTOR_API" model-save --provider openai-prod --model gpt-4o-mini`. The id must exactly match the provider's. For a vector DB the "model" is the index name. `--max-tokens` caps a model; `--disabled` keeps it registered but unusable.

## 4. Grant access

- The identity that **created** the integration gets full access automatically — when the same application key creates the integration and runs the workflows, nothing else is needed.
- Other groups / roles / users: `python3 "$CONDUCTOR_API" grant-access --subject-type group --subject-id <group> --target-id openai-prod --access READ,EXECUTE` (`--target-type` defaults to `INTEGRATION_PROVIDER`).
- Another **application** (the identity behind a different access key): grant it in the UI — **Access Control → Applications → \<app\> → Integration** tab, toggle the models — and confirm with `access-list`. Don't guess an API subject id for an application.
- Check: `python3 "$CONDUCTOR_API" access-list --target-id openai-prod`.

## 5. Use it in a workflow

```json
{
  "name": "summarize", "taskReferenceName": "summarize_ref", "type": "LLM_CHAT_COMPLETE",
  "inputParameters": {
    "llmProvider": "openai-prod",
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "message": "Summarize: ${workflow.input.text}"}]
  }
}
```

Same rule for every `LLM_*` task; for `LLM_INDEX_TEXT` / `LLM_SEARCH_INDEX`, `vectorDB` is the vector integration name, `index` a registered index, and `embeddingModelProvider` / `embeddingModel` an AI integration name + registered embedding model. Prompt text in `instructions` / `promptName` / image `prompt` follows §6 — a saved template by name, or `allowRawPrompts: true`.

Verify end to end with a one-task test workflow before wiring the real one.

## 6. Prompts — saved templates by name (raw text needs `allowRawPrompts`)

On Enterprise the server treats a task's prompt field as the **name of a saved prompt template** and checks that the template is associated with the task's exact `integration:model`. Literal text there fails at run time with *"Prompt \<text\> is not associated with integration \<name\> and model \<model\>"* — unless the task sets `allowRawPrompts: true`.

| Field | Enterprise behaviour |
|---|---|
| `LLM_CHAT_COMPLETE.instructions` | template name; raw text needs `allowRawPrompts: true` |
| `LLM_TEXT_COMPLETE.promptName` (also `prompt`) | template name; raw text in `promptName` needs `allowRawPrompts: true` |
| `GENERATE_IMAGE.prompt` | raw text needs `allowRawPrompts: true` (or a template name) |
| `messages[]`, `GENERATE_AUDIO.text`, `GENERATE_VIDEO.prompt` | not gated |

**Default: put the prompt in a template and reference it by name.** Templates are versioned, reviewable, reusable across workflows, and the association doubles as an allow-list of the models a prompt may run on.

1. Write the template text to a file. Placeholders are `${name}`.
2. Save it and associate it with **every** `integration:model` the tasks use:
   `python3 "$CONDUCTOR_API" prompt-save --name ticket_summary --template-file ticket_summary.txt --model openai-prod:gpt-4o-mini --model openai-prod:gpt-4o`
   (re-run with the full `--model` list to add a model; `prompt-list` / `prompt-get` show what exists and its `variables`).
3. Reference it by name and pass runtime values through `promptVariables` (real Conductor expressions go **here**):

```json
{
  "name": "summarize", "taskReferenceName": "summarize_ref", "type": "LLM_CHAT_COMPLETE",
  "inputParameters": {
    "llmProvider": "openai-prod", "model": "gpt-4o-mini",
    "instructions": "ticket_summary",
    "promptVariables": {"ticket": "${workflow.input.ticket_text}", "tone": "brief"},
    "messages": [{"role": "user", "message": "${workflow.input.ticket_text}"}]
  }
}
```

`LLM_TEXT_COMPLETE` uses `"promptName": "ticket_summary"` the same way.

**`${var}` placeholders only work inside a saved template.** In workflow JSON, `${...}` is a Conductor expression: `"instructions": "Summarize ${ticket}"` fails registration (*"taskReferenceName: ticket … is not defined in workflow definition"*). Inline text must use real expressions (`${workflow.input.ticket}`), not template placeholders.

**Raw text instead — only when the user explicitly asks for inline prompts** (never as your own default): keep the literal text and add `"allowRawPrompts": true` to the task. When you build a template, mention this alternative in one line. It is ignored on OSS, so it is safe in workflows that run on both.

OSS has no prompt registry: prompts are always literal text and `prompt-*` commands are refused.

## 7. Errors

| Symptom on Orkes | Cause | Fix |
|---|---|---|
| LLM task fails with integration / provider not found | `llmProvider` is the provider *type* (`openai`) or a typo, not an existing integration name | `integration-list`, use the exact name |
| Model not found / not enabled | Model not registered under that integration, or `--disabled` | `model-save` |
| 403 / access denied on the LLM task | The running application has no access to the integration | §4 |
| "this server does not require auth, so it is OSS" / integration endpoints 404 | Server is OSS — integration APIs don't exist there (a 404 for one name on Enterprise = that integration doesn't exist) | OSS uses server env keys — see [setup.md](setup.md) Step 5 |
| *"Prompt … is not associated with integration … and model …"* | Literal text in `instructions` / `promptName` / image `prompt` without `allowRawPrompts`, or the template isn't associated with that `integration:model` | Use a template name and `prompt-save … --model <integration>:<model>`, or set `allowRawPrompts: true` (§6) |
| Registration fails: *"taskReferenceName: x … is not defined"* for prompt text | `${x}` template placeholder written inline in the workflow | Move the text into a saved template, or use a real expression (§6) |
| `integration-list` returns 403 | This application can't manage integrations | Ask for the integration name to use, or an admin to create it / grant rights (§1) |
| `integration-save`: "already exists" | Name taken | Use it (add models with `model-sync`), or `--overwrite` with all secrets re-supplied |
| A `*-env` flag says the variable isn't set | Shell expanded `$VAR` into a value, or the variable isn't exported | Pass the bare name; ask the user to export it |

Never work around a missing integration with an `HTTP` task to the provider API (rule B10) — create or fix the integration.
