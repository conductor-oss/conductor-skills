# Orkes Integrations — AI Providers, Models and Access

On **OSS** Conductor an LLM provider is enabled by putting its key in the server's environment (`OPENAI_API_KEY`, …) and `llmProvider` is the provider name (`openai`). On **Orkes Conductor** (Enterprise — `*.orkesconductor.*`, `developer.orkescloud.com`, `CONDUCTOR_SERVER_TYPE=Enterprise`) that is not how it works: every provider is a named **integration** on the cluster, every model must be **registered under that integration**, and the calling application needs **access** to it. Skip any of the three and `LLM_*` tasks fail even though the workflow JSON is valid.

| Concept | What it is | Where it shows up in a task |
|---|---|---|
| Integration (provider) | A named, credential-backed connection, e.g. `openai-prod` of type `openai` | `llmProvider: "openai-prod"` — the **integration name**, not the type |
| Model (integration resource) | An exact provider model id registered under the integration, e.g. `gpt-4o-mini` | `model: "gpt-4o-mini"` |
| Access | Permission for an application / group / role on the integration | none — missing access surfaces as a 403 / access error at run time |

The `conductor` CLI has **no integration commands** (and `conductor doctor` only checks *local* env vars — it says nothing about the cluster's integrations). Use the bundled fallback script (`$CONDUCTOR_API`, see [fallback-cli.md](fallback-cli.md)) or the REST endpoints below. Same auth as everything else (`CONDUCTOR_AUTH_KEY` / `CONDUCTOR_AUTH_SECRET`).

## 1. Check what exists — before writing any LLM task for Orkes

```bash
python3 "$CONDUCTOR_API" integration-list --category AI_MODEL     # names, types; secret config masked
python3 "$CONDUCTOR_API" model-list --provider openai-prod          # models registered under one integration
```

If a suitable integration and model already exist, **use their names** — don't create a parallel integration. Tell the user which names the workflow will use.

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

For any type not listed, or to confirm field names on this cluster, run `python3 "$CONDUCTOR_API" integration-defs --category AI_MODEL` — it returns each type's configuration form fields. The `type` cannot be changed after creation; re-running `integration-save` with the same `--name` updates the integration.

## 3. Register the models

```bash
python3 "$CONDUCTOR_API" model-save --provider openai-prod --model gpt-4o-mini --description "default chat model"
python3 "$CONDUCTOR_API" model-save --provider openai-prod --model text-embedding-3-small
```

The model id must **exactly** match the provider's id. For a vector DB the "model" is the index name. Optional `--max-tokens` caps a model; `--disabled` keeps it registered but unusable.

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

Same rule for every `LLM_*` task; for `LLM_INDEX_TEXT` / `LLM_SEARCH_INDEX`, `vectorDB` is the vector integration name, `index` a registered index, and `embeddingModelProvider` / `embeddingModel` an AI integration name + registered embedding model. For `promptName` templates — a stored prompt also has to be associated with each model it runs on: `python3 "$CONDUCTOR_API" prompt-associate --provider openai-prod --model gpt-4o-mini --prompt <template>`.

Verify end to end with a one-task test workflow before wiring the real one.

## 6. Errors

| Symptom on Orkes | Cause | Fix |
|---|---|---|
| LLM task fails with integration / provider not found | `llmProvider` is the provider *type* (`openai`) or a typo, not an existing integration name | `integration-list`, use the exact name |
| Model not found / not enabled | Model not registered under that integration, or `--disabled` | `model-save` |
| 403 / access denied on the LLM task | The running application has no access to the integration | §4 |
| Integration endpoints return 404 | Server is OSS | OSS uses server env keys — see [setup.md](setup.md) Step 5 |

Never work around a missing integration with an `HTTP` task to the provider API (rule B10) — create or fix the integration.
