#!/usr/bin/env python3
"""Conductor REST API fallback — stdlib only, no third-party packages.

Use when the `conductor` CLI is not installed.
Requires CONDUCTOR_SERVER_URL. Authentication accepts CONDUCTOR_AUTH_TOKEN or
CONDUCTOR_AUTH_KEY + CONDUCTOR_AUTH_SECRET (exchanged at POST /api/token).
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_server_url(value):
    """Return an API base URL without guessing over a custom deployment path."""
    raw = (value or "").strip()
    if not raw:
        print("Error: CONDUCTOR_SERVER_URL is not set.", file=sys.stderr)
        sys.exit(1)

    parsed = urllib.parse.urlsplit(raw)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        print(
            "Error: CONDUCTOR_SERVER_URL must be an absolute http(s) URL.",
            file=sys.stderr,
        )
        sys.exit(1)
    if parsed.query or parsed.fragment:
        print(
            "Error: CONDUCTOR_SERVER_URL must not include a query or fragment.",
            file=sys.stderr,
        )
        sys.exit(1)

    path = parsed.path.rstrip("/")
    if not path:
        path = "/api"
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def exchange_auth_token(base, key, secret):
    """Exchange an Orkes application key/secret for a JWT, kept in memory only."""
    result = request_json(
        build_url(base, "/token"),
        "",
        method="POST",
        body={"keyId": key, "keySecret": secret},
    )
    token = result.get("token", "") if isinstance(result, dict) else ""
    if not token:
        print("Error: /token response did not include a token.", file=sys.stderr)
        sys.exit(1)
    return token


def load_cli_profile(name):
    """Read a `conductor config save --profile <name>` file (flat `key: value` YAML).
    Values stay in memory and are never printed."""
    path = os.path.expanduser(f"~/.conductor-cli/config-{name}.yaml")
    if not os.path.exists(path):
        print(f"Error: CLI profile {name!r} not found (see `conductor config list`).", file=sys.stderr)
        sys.exit(1)
    values = {}
    with open(path) as f:
        for line in f:
            if ":" in line and not line.lstrip().startswith("#"):
                k, v = line.split(":", 1)
                values[k.strip()] = v.strip().strip("'\"")
    return values


def get_config():
    # Environment variables win; a CLI profile (--profile / CONDUCTOR_PROFILE) fills the gaps.
    profile_name = os.environ.get("CONDUCTOR_PROFILE", "").strip()
    profile = load_cli_profile(profile_name) if profile_name else {}
    base = normalize_server_url(os.environ.get("CONDUCTOR_SERVER_URL") or profile.get("server", ""))
    token = os.environ.get("CONDUCTOR_AUTH_TOKEN", "").strip()
    key = os.environ.get("CONDUCTOR_AUTH_KEY") or profile.get("auth-key", "")
    secret = os.environ.get("CONDUCTOR_AUTH_SECRET") or profile.get("auth-secret", "")
    if bool(key) != bool(secret):
        print(
            "Error: set both CONDUCTOR_AUTH_KEY and CONDUCTOR_AUTH_SECRET.",
            file=sys.stderr,
        )
        sys.exit(1)
    if not token and key and secret:
        token = exchange_auth_token(base, key, secret)
    return base, token


def build_url(base, path, params=None):
    url = f"{base}{path}"
    if params:
        qs = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        if qs:
            url = f"{url}?{qs}"
    return url


def request_json(url, token, method="GET", body=None, expect_json=True):
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["X-Authorization"] = token

    data = None
    if body is not None:
        data = json.dumps(body).encode() if not isinstance(body, bytes) else body

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    retries = 3
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode()
                if not raw:
                    return None
                if expect_json:
                    return json.loads(raw)
                return raw
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            body_text = ""
            try:
                body_text = e.read().decode()
            except Exception:
                pass
            print(f"HTTP {e.code}: {e.reason}\n{body_text}", file=sys.stderr)
            sys.exit(1)
        except urllib.error.URLError as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            print(f"Connection error: {e.reason}", file=sys.stderr)
            sys.exit(1)


def output(data):
    print(json.dumps(data, indent=2))


# ---------------------------------------------------------------------------
# Workflow metadata handlers
# ---------------------------------------------------------------------------

def handle_list_workflows(args):
    base, token = get_config()
    url = build_url(base, "/metadata/workflow")
    result = request_json(url, token)
    output(result)


def handle_get_workflow(args):
    base, token = get_config()
    params = {}
    if args.version:
        params["version"] = args.version
    url = build_url(base, f"/metadata/workflow/{urllib.parse.quote(args.name)}", params)
    result = request_json(url, token)
    output(result)


def handle_create_workflow(args):
    base, token = get_config()
    with open(args.file) as f:
        body = json.load(f)
    # --overwrite maps to POST /metadata/workflow?overwrite=true (needed to re-register an existing
    # version, e.g. a workflow whose `metadata.a2a.enabled` the CLI would drop).
    url = build_url(base, "/metadata/workflow", {"overwrite": "true"} if getattr(args, "overwrite", False) else None)
    result = request_json(url, token, method="POST", body=body)
    if result:
        output(result)
    else:
        print("Workflow created successfully.")


def handle_update_workflow(args):
    base, token = get_config()
    with open(args.file) as f:
        body = json.load(f)
    # Update expects an array
    if isinstance(body, dict):
        body = [body]
    url = build_url(base, "/metadata/workflow")
    result = request_json(url, token, method="PUT", body=body)
    if result:
        output(result)
    else:
        print("Workflow updated successfully.")


def handle_delete_workflow(args):
    base, token = get_config()
    url = build_url(base, f"/metadata/workflow/{urllib.parse.quote(args.name)}/{args.version}")
    request_json(url, token, method="DELETE", expect_json=False)
    print(f"Workflow {args.name} v{args.version} deleted.")


# ---------------------------------------------------------------------------
# Workflow execution handlers
# ---------------------------------------------------------------------------

def handle_start_workflow(args):
    base, token = get_config()
    body = {"name": args.name}
    if args.version:
        body["version"] = int(args.version)
    if args.correlation_id:
        body["correlationId"] = args.correlation_id
    if args.input:
        body["input"] = json.loads(args.input)
    elif args.input_file:
        with open(args.input_file) as f:
            body["input"] = json.load(f)

    url = build_url(base, "/workflow")
    result = request_json(url, token, method="POST", body=body, expect_json=False)
    # Start returns the workflow ID as plain text
    wf_id = result.strip().strip('"') if result else ""
    print(json.dumps({"workflowId": wf_id}, indent=2))


def handle_get_execution(args):
    base, token = get_config()
    params = {}
    if args.include_tasks:
        params["includeTasks"] = "true"
    url = build_url(base, f"/workflow/{urllib.parse.quote(args.id)}", params)
    result = request_json(url, token)
    output(result)


def handle_search_workflows(args):
    base, token = get_config()
    params = {"size": str(args.size or 10)}
    if args.status:
        params["query"] = f"status={args.status}"
    if args.query:
        params["query"] = args.query
    if args.sort:
        params["sort"] = args.sort
    url = build_url(base, "/workflow/search", params)
    result = request_json(url, token)
    output(result)


# ---------------------------------------------------------------------------
# Workflow management handlers
# ---------------------------------------------------------------------------

def handle_pause_workflow(args):
    base, token = get_config()
    url = build_url(base, f"/workflow/{urllib.parse.quote(args.id)}/pause")
    request_json(url, token, method="PUT", expect_json=False)
    print(f"Workflow {args.id} paused.")


def handle_resume_workflow(args):
    base, token = get_config()
    url = build_url(base, f"/workflow/{urllib.parse.quote(args.id)}/resume")
    request_json(url, token, method="PUT", expect_json=False)
    print(f"Workflow {args.id} resumed.")


def handle_terminate_workflow(args):
    base, token = get_config()
    params = {}
    if args.reason:
        params["reason"] = args.reason
    url = build_url(base, f"/workflow/{urllib.parse.quote(args.id)}", params)
    request_json(url, token, method="DELETE", expect_json=False)
    print(f"Workflow {args.id} terminated.")


def handle_restart_workflow(args):
    base, token = get_config()
    url = build_url(base, f"/workflow/{urllib.parse.quote(args.id)}/restart")
    request_json(url, token, method="POST", expect_json=False)
    print(f"Workflow {args.id} restarted.")


def handle_retry_workflow(args):
    base, token = get_config()
    url = build_url(base, f"/workflow/{urllib.parse.quote(args.id)}/retry")
    request_json(url, token, method="POST", expect_json=False)
    print(f"Workflow {args.id} retried.")


# ---------------------------------------------------------------------------
# Task handlers
# ---------------------------------------------------------------------------

def handle_signal_task(args):
    base, token = get_config()
    status = urllib.parse.quote(args.status)
    url = build_url(
        base,
        f"/tasks/{urllib.parse.quote(args.workflow_id)}/{urllib.parse.quote(args.task_ref)}/{status}",
    )
    body = {}
    if args.output:
        body = json.loads(args.output)
    result = request_json(url, token, method="POST", body=body, expect_json=False)
    print(f"Task {args.task_ref} signaled with status {args.status}.")
    if result:
        print(result)


def handle_signal_task_sync(args):
    base, token = get_config()
    status = urllib.parse.quote(args.status)
    url = build_url(
        base,
        f"/tasks/{urllib.parse.quote(args.workflow_id)}/{urllib.parse.quote(args.task_ref)}/{status}/sync",
    )
    body = {}
    if args.output:
        body = json.loads(args.output)
    result = request_json(url, token, method="POST", body=body)
    if result:
        output(result)
    else:
        print(f"Task {args.task_ref} signaled synchronously with status {args.status}.")


def handle_poll_task(args):
    base, token = get_config()
    params = {"count": str(args.count or 1)}
    url = build_url(base, f"/tasks/poll/batch/{urllib.parse.quote(args.task_type)}", params)
    result = request_json(url, token)
    output(result)


def handle_queue_size(args):
    base, token = get_config()
    params = {}
    if args.task_type:
        params["taskType"] = args.task_type
    url = build_url(base, "/tasks/queue/size", params)
    result = request_json(url, token)
    output(result)



# ---------------------------------------------------------------------------
# Agent runtime handlers (no CLI equivalent for several of these; see
# references/agents.md and references/fallback-cli.md)
# ---------------------------------------------------------------------------

def handle_providers_status(args):
    base, token = get_config()
    url = build_url(base, "/providers/status")
    output(request_json(url, token))


def handle_agent_list(args):
    base, token = get_config()
    url = build_url(base, "/agent/list")
    output(request_json(url, token))


def handle_agent_get(args):
    base, token = get_config()
    params = {"version": args.version} if args.version else None
    url = build_url(base, f"/agent/{urllib.parse.quote(args.name)}", params)
    output(request_json(url, token))


def handle_agent_deploy_config(args):
    """POST /agent/deploy with {"agentConfig": <file contents>} — registers only, never runs."""
    base, token = get_config()
    with open(args.file) as f:
        config = json.load(f)
    body = config if "agentConfig" in config or "framework" in config else {"agentConfig": config}
    url = build_url(base, "/agent/deploy")
    output(request_json(url, token, method="POST", body=body))


def handle_agent_start(args):
    base, token = get_config()
    body = {"name": args.name, "prompt": args.prompt}
    if args.version:
        body["version"] = int(args.version)
    if args.session_id:
        body["sessionId"] = args.session_id
    url = build_url(base, "/agent/start")
    output(request_json(url, token, method="POST", body=body))


def handle_agent_status(args):
    base, token = get_config()
    url = build_url(base, f"/agent/{urllib.parse.quote(args.id)}/status")
    output(request_json(url, token))


def handle_agent_executions(args):
    base, token = get_config()
    params = {
        "agentName": args.name,
        "status": args.status,
        "start": 0,
        "size": args.size,
        "sort": "startTime:DESC",
    }
    url = build_url(base, "/agent/executions", params)
    output(request_json(url, token))


def handle_agent_execution(args):
    base, token = get_config()
    url = build_url(base, f"/agent/execution/{urllib.parse.quote(args.id)}")
    output(request_json(url, token))


def handle_agent_respond(args):
    """Answer a human gate. --approve / --deny for approval_required tools; --message for a question."""
    base, token = get_config()
    if args.approve and args.deny:
        print("Error: --approve and --deny are mutually exclusive.", file=sys.stderr)
        sys.exit(1)
    body = {}
    if args.approve:
        body["approved"] = True
    if args.deny:
        body["approved"] = False
    if args.reason:
        body["reason"] = args.reason
    if args.message:
        body["message"] = args.message
    if not body:
        print("Error: pass --approve, --deny, or --message.", file=sys.stderr)
        sys.exit(1)
    url = build_url(base, f"/agent/{urllib.parse.quote(args.id)}/respond")
    result = request_json(url, token, method="POST", body=body)
    output(result if result is not None else {"status": "ok", "executionId": args.id})


def handle_agent_cancel(args):
    base, token = get_config()
    params = {"reason": args.reason} if args.reason else None
    url = build_url(base, f"/agent/{urllib.parse.quote(args.id)}/cancel", params)
    result = request_json(url, token, method="DELETE")
    output(result if result is not None else {"status": "canceled", "executionId": args.id})


def handle_agent_stop(args):
    base, token = get_config()
    url = build_url(base, f"/agent/{urllib.parse.quote(args.id)}/stop")
    result = request_json(url, token, method="POST")
    output(result if result is not None else {"status": "stop-requested", "executionId": args.id})

# ---------------------------------------------------------------------------
# Orkes integrations: AI providers, models, access (references/orkes-integrations.md).
# The `conductor` CLI has no integration commands. Orkes-only: OSS returns 404.
# ---------------------------------------------------------------------------

_SECRET_HINTS = ("key", "secret", "token", "password", "credential", "file")


def redact(data):
    """Mask secret-looking configuration values so they never reach the transcript."""
    if isinstance(data, list):
        return [redact(d) for d in data]
    if not isinstance(data, dict):
        return data
    out = {}
    for k, v in data.items():
        if k == "configuration" and isinstance(v, dict):
            out[k] = {ck: ("***" if any(h in ck.lower() for h in _SECRET_HINTS) and v[ck] not in (None, "") else v[ck])
                      for ck in v}
        else:
            out[k] = redact(v)
    return out


_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def env_value(name, purpose):
    """Read a secret from the env var NAME. A malformed name is probably an expanded value
    (`$OPENAI_API_KEY` instead of `OPENAI_API_KEY`), so it is never echoed."""
    if not name or not _ENV_NAME.match(name):
        print(f"Error: {purpose} needs an environment variable NAME such as OPENAI_API_KEY — not its value "
              "and not $NAME (the shell expands that). The value you passed was not printed.", file=sys.stderr)
        sys.exit(1)
    value = os.environ.get(name, "")
    if not value:
        # Don't echo the name either: an alphanumeric key pasted in its place would look like one.
        print(f"Error: the environment variable named for {purpose} is not set (or is empty).", file=sys.stderr)
        sys.exit(1)
    return value


def parse_pairs(pairs, flag):
    result = {}
    for pair in pairs or []:
        if "=" not in pair:
            print(f"Error: {flag} expects KEY=VALUE, got {pair!r}.", file=sys.stderr)
            sys.exit(1)
        k, v = pair.split("=", 1)
        result[k] = v
    return result


def integration_path(name, model=None):
    path = f"/integrations/provider/{urllib.parse.quote(name, safe='')}"
    if model is not None:
        path += f"/integration/{urllib.parse.quote(model, safe='')}"
    return path


def handle_integration_defs(args):
    base, token = get_config()
    result = request_json(build_url(base, "/integrations/def"), token)
    if args.category and isinstance(result, list):
        result = [d for d in result if d.get("category") == args.category]
    output(result)


def handle_integration_list(args):
    base, token = get_config()
    params = {"activeOnly": "true"} if args.active_only else None
    result = request_json(build_url(base, "/integrations/provider", params), token) or []
    if isinstance(result, dict):
        result = [result]
    if args.category:
        result = [r for r in result if r.get("category") == args.category]
    output(redact(result))


def handle_integration_get(args):
    base, token = get_config()
    output(redact(request_json(build_url(base, integration_path(args.name)), token)))


def handle_integration_save(args):
    base, token = get_config()
    configuration = {}
    if args.config_file:
        with open(args.config_file) as f:
            configuration.update(json.load(f))
    configuration.update(parse_pairs(args.config, "--config"))
    for key in configuration:
        if any(h in key.lower() for h in _SECRET_HINTS):
            print(f"Error: {key} looks secret; pass it with --config-env {key}=ENV_VAR_NAME, "
                  "not in --config or --config-file.", file=sys.stderr)
            sys.exit(1)
    # Secret values come from environment variables named on the command line, never from argv.
    for key, env_name in parse_pairs(args.config_env, "--config-env").items():
        configuration[key] = env_value(env_name, f"--config-env {key}")
    # POST is create-or-update and replaces the whole configuration, so an update without the
    # secrets would wipe them. Require an explicit --overwrite for an existing integration.
    existing = request_json(build_url(base, "/integrations/provider"), token) or []
    if isinstance(existing, dict):
        existing = [existing]
    if any(isinstance(e, dict) and e.get("name") == args.name for e in existing) and not args.overwrite:
        print(f"Error: integration {args.name!r} already exists. Re-run with --overwrite to replace its "
              "configuration — and pass every secret field again with --config-env, or it is cleared. "
              "To add models to it, use model-save / model-sync instead.", file=sys.stderr)
        sys.exit(1)
    body = {
        "type": args.type,
        "category": args.category,
        "enabled": not args.disabled,
        "description": args.description or args.name,
        "configuration": configuration,
    }
    request_json(build_url(base, integration_path(args.name)), token, method="POST", body=body, expect_json=False)
    print(json.dumps({"saved": args.name, "type": args.type, "category": args.category,
                      "configurationKeys": sorted(configuration)}, indent=2))


def handle_integration_delete(args):
    base, token = get_config()
    request_json(build_url(base, integration_path(args.name)), token, method="DELETE", expect_json=False)
    print(f"Integration {args.name} deleted.")


def handle_model_list(args):
    base, token = get_config()
    params = {"activeOnly": "true"} if args.active_only else None
    url = build_url(base, integration_path(args.provider) + "/integration", params)
    output(redact(request_json(url, token)))


def handle_model_save(args):
    base, token = get_config()
    body = {"enabled": not args.disabled, "description": args.description or args.model}
    if args.max_tokens:
        body["maxTokens"] = args.max_tokens
    request_json(build_url(base, integration_path(args.provider, args.model)), token,
                 method="POST", body=body, expect_json=False)
    print(json.dumps({"saved": f"{args.provider}/{args.model}", "enabled": body["enabled"]}, indent=2))



# Provider model catalogs: ask the provider which models this key can use, so a new
# integration can register all of them. The key comes from an env var and is only sent
# to the provider's own API.
PROVIDER_SOURCES = {
    # source: (default base URL, list path, auth style, response list key, id field)
    "openai": ("https://api.openai.com", "/v1/models", "bearer", "data", "id"),
    "anthropic": ("https://api.anthropic.com", "/v1/models?limit=1000", "anthropic", "data", "id"),
    "gemini": ("https://generativelanguage.googleapis.com", "/v1beta/models?pageSize=1000", "google", "models", "name"),
    "mistral": ("https://api.mistral.ai", "/v1/models", "bearer", "data", "id"),
    "cohere": ("https://api.cohere.com", "/v1/models?page_size=1000", "bearer", "models", "name"),
    "xai": ("https://api.x.ai", "/v1/models", "bearer", "data", "id"),
    "ollama": ("http://localhost:11434", "/api/tags", "none", "models", "name"),
}
# Orkes integration type -> provider catalog source.
TYPE_TO_SOURCE = {"openai": "openai", "anthropic": "anthropic", "mistral": "mistral", "cohere": "cohere",
                  "grok": "xai", "ollama": "ollama", "google_gemini": "gemini", "gemini": "gemini"}
# Types whose models can't be listed with a plain key: look them up online and model-save each.
NO_CATALOG_TYPES = {
    "azure_openai": "models are your Azure deployment names — ask the user for them",
    "vertex_ai": "look up current model ids on Google's Vertex AI models page",
    "vertex_ai_gemini": "look up current model ids on Google's Vertex AI models page",
    "perplexity": "look up current model ids on Perplexity's API models page",
    "huggingface": "use the model ids the user deploys/uses on Hugging Face",
}
FINE_TUNES = r"^ft:|:ft-|^ft-"  # fine-tunes belong to one org; register them explicitly with model-save


def fetch_provider_models(source, key_env, endpoint=None):
    if source not in PROVIDER_SOURCES:
        print(f"Error: no model catalog for {source!r}; supported: {', '.join(sorted(PROVIDER_SOURCES))}. "
              "For other providers look the models up on the provider's docs and use model-save.", file=sys.stderr)
        sys.exit(1)
    default_base, path, auth, list_key, id_field = PROVIDER_SOURCES[source]
    key = env_value(key_env, "--key-env") if auth != "none" else ""
    base = (endpoint or default_base).rstrip("/")
    for suffix in ("/v1beta", "/v1"):  # list paths already carry the version
        if base.endswith(suffix):
            base = base[: -len(suffix)]
    headers = {"Accept": "application/json"}
    if auth == "bearer":
        headers["Authorization"] = f"Bearer {key}"
    elif auth == "anthropic":
        headers["x-api-key"] = key
        headers["anthropic-version"] = "2023-06-01"
    elif auth == "google":
        headers["x-goog-api-key"] = key
    req = urllib.request.Request(base + path, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"Error: {source} model list returned HTTP {e.code} {e.reason} (check the key in {key_env}).",
              file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Error: could not reach {base}: {e.reason}", file=sys.stderr)
        sys.exit(1)
    models = []
    for item in data.get(list_key, []) if isinstance(data, dict) else []:
        model_id = item.get(id_field, "")
        if source == "gemini":
            model_id = model_id.removeprefix("models/")
        if model_id:
            models.append({"id": model_id,
                           "created": item.get("created") or item.get("created_at"),
                           "displayName": item.get("display_name") or item.get("displayName")})
    return sorted(models, key=lambda m: m["id"])


def resolve_source(args):
    kind = (args.type or "").lower()
    if not args.source and (kind in NO_CATALOG_TYPES or kind.startswith("aws_bedrock")):
        hint = NO_CATALOG_TYPES.get(kind, "look up current Bedrock model ids on AWS's supported-models page; "
                                          "they must also be enabled in the account/region")
        print(f"Error: {args.type} has no model-list API usable with a key: {hint}, then run model-save "
              "for each id. Don't point --source at another provider.", file=sys.stderr)
        sys.exit(1)
    source = args.source or TYPE_TO_SOURCE.get(kind)
    if not source:
        print(f"Error: unknown --type {args.type!r}; pass --source (" + ", ".join(sorted(PROVIDER_SOURCES)) + ")"
              " only if this integration really is that provider's API (e.g. gemini for a Gemini API key).",
              file=sys.stderr)
        sys.exit(1)
    return source


def filter_models(models, include, exclude, fine_tunes=False):
    if not fine_tunes:
        models = [m for m in models if not re.search(FINE_TUNES, m["id"])]
    if include:
        models = [m for m in models if re.search(include, m["id"])]
    if exclude:
        models = [m for m in models if not re.search(exclude, m["id"])]
    return models


def handle_provider_models(args):
    models = fetch_provider_models(resolve_source(args), args.key_env, args.endpoint)
    output(filter_models(models, args.include, args.exclude, args.include_fine_tunes))


def handle_model_sync(args):
    models = filter_models(fetch_provider_models(resolve_source(args), args.key_env, args.endpoint),
                           args.include, args.exclude, args.include_fine_tunes)
    base, token = get_config()
    # Fails fast (HTTP 404) when the integration doesn't exist yet — create it with integration-save first.
    request_json(build_url(base, integration_path(args.provider)), token)
    existing = request_json(build_url(base, integration_path(args.provider) + "/integration"), token) or []
    have = {e.get("api") or e.get("name") for e in existing if isinstance(e, dict)}
    to_add = [m["id"] for m in models if m["id"] not in have]
    added, failed = [], []
    if not args.dry_run:
        for model_id in to_add:
            try:  # request_json exits on an HTTP error; keep going so one bad id doesn't stop the sync
                request_json(build_url(base, integration_path(args.provider, model_id)), token, method="POST",
                             body={"enabled": True, "description": model_id}, expect_json=False)
                added.append(model_id)
            except SystemExit:
                failed.append(model_id)
    result = {"provider": args.provider, "dryRun": args.dry_run,
              "alreadyRegistered": sorted(m["id"] for m in models if m["id"] in have)}
    if args.dry_run:
        result["wouldAdd"] = to_add
    else:
        result["added"], result["failed"] = added, failed
    output(result)
    if failed:
        sys.exit(1)


def handle_model_delete(args):
    base, token = get_config()
    request_json(build_url(base, integration_path(args.provider, args.model)), token,
                 method="DELETE", expect_json=False)
    print(f"Model {args.model} removed from integration {args.provider}.")


def handle_prompt_associate(args):
    base, token = get_config()
    path = integration_path(args.provider, args.model) + f"/prompt/{urllib.parse.quote(args.prompt, safe='')}"
    request_json(build_url(base, path), token, method="POST", expect_json=False)
    print(f"Prompt {args.prompt} associated with {args.provider}/{args.model}.")


def handle_grant_access(args):
    base, token = get_config()
    body = {
        "subject": {"type": args.subject_type, "id": args.subject_id},
        "target": {"type": args.target_type, "id": args.target_id},
        "access": [a.strip().upper() for a in args.access.split(",") if a.strip()],
    }
    request_json(build_url(base, "/auth/authorization"), token, method="POST", body=body, expect_json=False)
    output({"granted": body})


def handle_access_list(args):
    base, token = get_config()
    path = f"/auth/authorization/{urllib.parse.quote(args.target_type)}/{urllib.parse.quote(args.target_id, safe='')}"
    output(request_json(build_url(base, path), token))

# ---------------------------------------------------------------------------
# CLI definition
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Conductor REST API fallback (stdlib only)"
    )
    parser.add_argument("--profile", default=None,
                        help="use a `conductor config save` profile for server + auth (values never printed); env vars override it")
    sub = parser.add_subparsers(dest="command", required=True)

    # -- Workflow metadata --
    sub.add_parser("list-workflows", help="List all workflow definitions")

    p = sub.add_parser("get-workflow", help="Get a workflow definition")
    p.add_argument("--name", required=True)
    p.add_argument("--version", default=None)

    p = sub.add_parser("create-workflow", help="Create a workflow definition from JSON file (keeps `metadata`, unlike the CLI)")
    p.add_argument("--file", required=True)
    p.add_argument("--overwrite", action="store_true", help="POST ...?overwrite=true to replace an existing version")

    p = sub.add_parser("update-workflow", help="Update a workflow definition from JSON file")
    p.add_argument("--file", required=True)

    p = sub.add_parser("delete-workflow", help="Delete a workflow definition")
    p.add_argument("--name", required=True)
    p.add_argument("--version", required=True)

    # -- Workflow execution --
    p = sub.add_parser("start-workflow", help="Start a workflow execution")
    p.add_argument("--name", required=True)
    p.add_argument("--version", default=None)
    p.add_argument("--correlation-id", default=None)
    p.add_argument("--input", default=None, help="Inline JSON input")
    p.add_argument("--input-file", default=None, help="Path to JSON input file")

    p = sub.add_parser("get-execution", help="Get workflow execution status")
    p.add_argument("--id", required=True)
    p.add_argument("--include-tasks", action="store_true")

    p = sub.add_parser("search-workflows", help="Search workflow executions")
    p.add_argument("--status", default=None)
    p.add_argument("--query", default=None)
    p.add_argument("--size", type=int, default=10)
    p.add_argument("--sort", default=None)

    # -- Workflow management --
    p = sub.add_parser("pause-workflow", help="Pause a running workflow")
    p.add_argument("--id", required=True)

    p = sub.add_parser("resume-workflow", help="Resume a paused workflow")
    p.add_argument("--id", required=True)

    p = sub.add_parser("terminate-workflow", help="Terminate a workflow")
    p.add_argument("--id", required=True)
    p.add_argument("--reason", default=None)

    p = sub.add_parser("restart-workflow", help="Restart a completed workflow")
    p.add_argument("--id", required=True)

    p = sub.add_parser("retry-workflow", help="Retry the last failed task")
    p.add_argument("--id", required=True)

    # -- Task operations --
    p = sub.add_parser("signal-task", help="Signal a task (async)")
    p.add_argument("--workflow-id", required=True)
    p.add_argument("--task-ref", required=True)
    p.add_argument("--status", required=True)
    p.add_argument("--output", default=None, help="JSON output to pass to the task")

    p = sub.add_parser("signal-task-sync", help="Signal a task (sync, returns workflow)")
    p.add_argument("--workflow-id", required=True)
    p.add_argument("--task-ref", required=True)
    p.add_argument("--status", required=True)
    p.add_argument("--output", default=None, help="JSON output to pass to the task")

    p = sub.add_parser("poll-task", help="Poll for tasks of a given type")
    p.add_argument("--task-type", required=True)
    p.add_argument("--count", type=int, default=1)

    p = sub.add_parser("queue-size", help="Get task queue size")
    p.add_argument("--task-type", default=None)

    # -- Agents (references/agents.md) --
    sub.add_parser("providers-status", help="Which LLM providers are configured on the server (GET /providers/status)")

    sub.add_parser("agent-list", help="List deployed Conductor Agents")

    p = sub.add_parser("agent-get", help="Get a deployed agent definition")
    p.add_argument("--name", required=True)
    p.add_argument("--version", default=None)

    p = sub.add_parser("agent-deploy-config", help="Deploy an agent config file (POST /agent/deploy); registers only")
    p.add_argument("--file", required=True)

    p = sub.add_parser("agent-start", help="Start a deployed agent (POST /agent/start)")
    p.add_argument("--name", required=True)
    p.add_argument("--prompt", required=True)
    p.add_argument("--version", default=None)
    p.add_argument("--session-id", default=None)

    p = sub.add_parser("agent-status", help="Agent execution status")
    p.add_argument("--id", required=True)

    p = sub.add_parser("agent-executions", help="Search agent executions")
    p.add_argument("--name", default=None, help="agentName filter")
    p.add_argument("--status", default=None, help="RUNNING, COMPLETED, FAILED, ...")
    p.add_argument("--size", type=int, default=20)

    p = sub.add_parser("agent-execution", help="Agent execution detail with token usage")
    p.add_argument("--id", required=True)

    p = sub.add_parser("agent-respond", help="Answer a waiting agent: --approve/--deny a tool, or --message an answer")
    p.add_argument("--id", required=True)
    p.add_argument("--approve", action="store_true")
    p.add_argument("--deny", action="store_true")
    p.add_argument("--reason", default=None)
    p.add_argument("--message", default=None)

    p = sub.add_parser("agent-cancel", help="Cancel an agent execution (DELETE /agent/{id}/cancel)")
    p.add_argument("--id", required=True)
    p.add_argument("--reason", default=None)

    p = sub.add_parser("agent-stop", help="Request a graceful stop after the current iteration")
    p.add_argument("--id", required=True)

    # -- Orkes integrations (references/orkes-integrations.md) --
    p = sub.add_parser("integration-defs", help="Orkes: integration types and their configuration fields (GET /integrations/def)")
    p.add_argument("--category", default=None, help="AI_MODEL, VECTOR_DB, ...")

    p = sub.add_parser("integration-list", help="Orkes: list integration providers (secret config masked)")
    p.add_argument("--category", default=None, help="AI_MODEL, VECTOR_DB, ...")
    p.add_argument("--active-only", action="store_true")

    p = sub.add_parser("integration-get", help="Orkes: get one integration provider (secret config masked)")
    p.add_argument("--name", required=True)

    p = sub.add_parser("integration-save", help="Orkes: create/update an integration provider (POST /integrations/provider/{name})")
    p.add_argument("--name", required=True, help="integration name -- this is what LLM tasks put in llmProvider")
    p.add_argument("--type", required=True, help="openai, anthropic, azure_openai, vertex_ai, aws_bedrock_anthropic, ...")
    p.add_argument("--category", default="AI_MODEL")
    p.add_argument("--description", default=None)
    p.add_argument("--config", action="append", default=[], metavar="KEY=VALUE", help="non-secret configuration (endpoint, region, ...)")
    p.add_argument("--config-env", action="append", default=[], metavar="KEY=ENV_VAR", help="secret configuration read from an env var, e.g. api_key=OPENAI_API_KEY")
    p.add_argument("--config-file", default=None, help="JSON file of non-secret configuration")
    p.add_argument("--disabled", action="store_true")
    p.add_argument("--overwrite", action="store_true",
                   help="replace an existing integration's whole configuration (re-supply secrets with --config-env)")

    p = sub.add_parser("integration-delete", help="Orkes: delete an integration provider")
    p.add_argument("--name", required=True)

    p = sub.add_parser("model-list", help="Orkes: list models registered under an integration")
    p.add_argument("--provider", required=True, help="integration name")
    p.add_argument("--active-only", action="store_true")

    p = sub.add_parser("model-save", help="Orkes: add/update a model under an integration")
    p.add_argument("--provider", required=True, help="integration name")
    p.add_argument("--model", required=True, help="exact provider model id, e.g. gpt-4o-mini")
    p.add_argument("--description", default=None)
    p.add_argument("--max-tokens", type=int, default=None)
    p.add_argument("--disabled", action="store_true")

    p = sub.add_parser("provider-models", help="List the models a provider key can use, from the provider's own API (key from an env var)")
    p.add_argument("--type", default=None, help="Orkes integration type (openai, anthropic, mistral, cohere, grok, ollama)")
    p.add_argument("--source", default=None, choices=sorted(PROVIDER_SOURCES), help="catalog to query when --type doesn't map")
    p.add_argument("--key-env", default=None, help="env var holding the provider key, e.g. OPENAI_API_KEY")
    p.add_argument("--endpoint", default=None, help="custom base URL (OpenAI-compatible gateway, Ollama host)")
    p.add_argument("--include", default=None, help="regex models must match")
    p.add_argument("--exclude", default=None, help="regex of models to skip (fine-tunes are always skipped)")
    p.add_argument("--include-fine-tunes", action="store_true", help="also register ft:... fine-tuned models")

    p = sub.add_parser("model-sync", help="Orkes: register every model the provider key can use under an integration")
    p.add_argument("--provider", required=True, help="integration name")
    p.add_argument("--type", default=None, help="Orkes integration type (openai, anthropic, mistral, cohere, grok, ollama)")
    p.add_argument("--source", default=None, choices=sorted(PROVIDER_SOURCES))
    p.add_argument("--key-env", default=None, help="env var holding the provider key, e.g. OPENAI_API_KEY")
    p.add_argument("--endpoint", default=None)
    p.add_argument("--include", default=None, help="regex models must match")
    p.add_argument("--exclude", default=None, help="regex of models to skip (fine-tunes are always skipped)")
    p.add_argument("--include-fine-tunes", action="store_true", help="also register ft:... fine-tuned models")
    p.add_argument("--dry-run", action="store_true", help="show what would be added")

    p = sub.add_parser("model-delete", help="Orkes: remove a model from an integration")
    p.add_argument("--provider", required=True)
    p.add_argument("--model", required=True)

    p = sub.add_parser("prompt-associate", help="Orkes: allow a prompt template to run on an integration model")
    p.add_argument("--provider", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--prompt", required=True)

    p = sub.add_parser("grant-access", help="Orkes: grant a user/group/role access to a resource (POST /auth/authorization)")
    p.add_argument("--subject-type", required=True, type=str.upper, choices=["USER", "GROUP", "ROLE"])
    p.add_argument("--subject-id", required=True)
    p.add_argument("--target-type", default="INTEGRATION_PROVIDER")
    p.add_argument("--target-id", required=True, help="integration name for INTEGRATION_PROVIDER")
    p.add_argument("--access", default="READ,EXECUTE", help="comma list of READ,CREATE,UPDATE,DELETE,EXECUTE")

    p = sub.add_parser("access-list", help="Orkes: who has access to a resource (GET /auth/authorization/{type}/{id})")
    p.add_argument("--target-type", default="INTEGRATION_PROVIDER")
    p.add_argument("--target-id", required=True)

    # Accept --profile before or after the subcommand (agents write it both ways).
    argv, profile, i = [], None, 0
    raw = sys.argv[1:]
    while i < len(raw):
        if raw[i] == "--profile" and i + 1 < len(raw):
            profile, i = raw[i + 1], i + 2
            continue
        if raw[i].startswith("--profile="):
            profile = raw[i].split("=", 1)[1]
        else:
            argv.append(raw[i])
        i += 1
    args = parser.parse_args(argv)
    if profile:
        os.environ["CONDUCTOR_PROFILE"] = profile

    handlers = {
        "list-workflows": handle_list_workflows,
        "get-workflow": handle_get_workflow,
        "create-workflow": handle_create_workflow,
        "update-workflow": handle_update_workflow,
        "delete-workflow": handle_delete_workflow,
        "start-workflow": handle_start_workflow,
        "get-execution": handle_get_execution,
        "search-workflows": handle_search_workflows,
        "pause-workflow": handle_pause_workflow,
        "resume-workflow": handle_resume_workflow,
        "terminate-workflow": handle_terminate_workflow,
        "restart-workflow": handle_restart_workflow,
        "retry-workflow": handle_retry_workflow,
        "signal-task": handle_signal_task,
        "signal-task-sync": handle_signal_task_sync,
        "poll-task": handle_poll_task,
        "queue-size": handle_queue_size,
        "providers-status": handle_providers_status,
        "agent-list": handle_agent_list,
        "agent-get": handle_agent_get,
        "agent-deploy-config": handle_agent_deploy_config,
        "agent-start": handle_agent_start,
        "agent-status": handle_agent_status,
        "agent-executions": handle_agent_executions,
        "agent-execution": handle_agent_execution,
        "agent-respond": handle_agent_respond,
        "agent-cancel": handle_agent_cancel,
        "agent-stop": handle_agent_stop,
        "integration-defs": handle_integration_defs,
        "integration-list": handle_integration_list,
        "integration-get": handle_integration_get,
        "integration-save": handle_integration_save,
        "integration-delete": handle_integration_delete,
        "model-list": handle_model_list,
        "model-save": handle_model_save,
        "model-delete": handle_model_delete,
        "provider-models": handle_provider_models,
        "model-sync": handle_model_sync,
        "prompt-associate": handle_prompt_associate,
        "grant-access": handle_grant_access,
        "access-list": handle_access_list,
    }

    handler = handlers.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
