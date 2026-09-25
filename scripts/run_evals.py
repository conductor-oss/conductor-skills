#!/usr/bin/env python3
"""Automated evaluation runner for Conductor skill.

Supports multiple LLM providers: Anthropic, OpenAI, and Google Gemini.

Usage:
    # Run all evals (default: Anthropic Claude)
    python3 scripts/run_evals.py

    # Run with OpenAI
    python3 scripts/run_evals.py --model gpt-4o

    # Run with Gemini
    python3 scripts/run_evals.py --model gemini-2.5-pro

    # Explicit provider (useful for custom/fine-tuned models)
    python3 scripts/run_evals.py --provider openai --model ft:gpt-4o:my-org

    # Use a different provider for the judge
    python3 scripts/run_evals.py --model gpt-4o --judge-model claude-sonnet-5

    # Run specific eval(s)
    python3 scripts/run_evals.py evaluations/install-and-connect.json

    # Run with verbose output
    python3 scripts/run_evals.py --verbose

    # Output JSON report
    python3 scripts/run_evals.py --json --output report.json

    # Print the size of the skill context sent to the agent (no API key needed)
    python3 scripts/run_evals.py --print-context-size
"""

import argparse
import json
import os
import socket
import http.client
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "claude-sonnet-5"
# Read timeout per API call. The agent-under-test receives the whole skill as a system prompt
# (~70K tokens) and may write up to 8192 tokens, which routinely exceeds 120 s.
API_TIMEOUT_SECONDS = int(os.environ.get("EVAL_API_TIMEOUT", "300"))  # override for very long plans
# Output cap for the agent-under-test (the judge keeps 8192). Claude 5 models emit thinking blocks that
# count against this budget, so complex plans need headroom.
AGENT_MAX_TOKENS = 32768
ANTHROPIC_MAX_OUTPUT_TOKENS = 64000
JUDGE_MODEL = "claude-sonnet-5"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = PROJECT_ROOT / "skills" / "conductor"
EVAL_DIR = PROJECT_ROOT / "evaluations"

PROVIDER_URLS = {
    "anthropic": "https://api.anthropic.com/v1/messages",
    "openai": "https://api.openai.com/v1/chat/completions",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
}

PROVIDER_ENV_KEYS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
}

# ---------------------------------------------------------------------------
# Provider detection
# ---------------------------------------------------------------------------

def detect_provider(model):
    """Detect provider from model name. Returns provider string."""
    m = model.lower()
    if any(m.startswith(p) for p in ("claude-", "claude3", "claude_")):
        return "anthropic"
    if any(m.startswith(p) for p in ("gpt-", "gpt4", "o1", "o3", "o4", "ft:gpt", "chatgpt")):
        return "openai"
    if any(m.startswith(p) for p in ("gemini-", "gemini/")):
        return "gemini"
    return None


def resolve_provider(model, explicit_provider=None):
    """Resolve provider, preferring explicit flag over auto-detection."""
    if explicit_provider:
        return explicit_provider
    detected = detect_provider(model)
    if not detected:
        print(
            f"Error: Cannot auto-detect provider for model '{model}'.\n"
            f"Use --provider {{anthropic,openai,gemini}} to specify explicitly.",
            file=sys.stderr,
        )
        sys.exit(1)
    return detected


def get_api_key(provider):
    """Get the API key for a provider from environment variables."""
    env_var = PROVIDER_ENV_KEYS[provider]
    key = os.environ.get(env_var, "")
    if not key:
        console_urls = {
            "anthropic": "https://console.anthropic.com/",
            "openai": "https://platform.openai.com/api-keys",
            "gemini": "https://aistudio.google.com/apikey",
        }
        print(f"Error: {env_var} is not set.", file=sys.stderr)
        print(f"Get your key at {console_urls[provider]}", file=sys.stderr)
        sys.exit(1)
    return key


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

class ApiError(RuntimeError):
    """Raised when an API call fails after retries; the runner records it and moves on."""


def _api_call(url, headers, body_bytes, retries=5):
    """Make an HTTP POST with retries on transient errors (HTTP 429/5xx, timeouts,
    connection resets, half-closed responses). Raises ApiError after the last attempt
    instead of exiting, so one bad call cannot abort a whole eval run."""
    req = urllib.request.Request(url, data=body_bytes, headers=headers, method="POST")
    last = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=API_TIMEOUT_SECONDS) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                print(f"API error: HTTP {e.code} {e.reason} — check the API key", file=sys.stderr)
                sys.exit(1)
            if e.code in (408, 409, 425, 429, 500, 502, 503, 504, 529) and attempt < retries - 1:
                wait = min(2 ** (attempt + 1), 60)
                print(f"  [RETRY] HTTP {e.code}, waiting {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            error_body = ""
            try:
                error_body = e.read().decode()
            except Exception:
                pass
            raise ApiError(f"HTTP {e.code} {e.reason}: {error_body[:300]}")
        except (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionError,
                http.client.HTTPException, OSError) as e:
            # Connection resets / half-closed responses / read timeouts are transient: back off and retry.
            last = e
            if attempt < retries - 1:
                wait = min(2 ** (attempt + 1), 60)
                print(f"  [RETRY] {type(e).__name__}: {getattr(e, 'reason', e)}, waiting {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
    raise ApiError(f"connection failed after {retries} attempts: {type(last).__name__}: {getattr(last, 'reason', last)}")


def call_anthropic(api_key, model, system, user_message, max_tokens=4096):
    """Call Anthropic Messages API."""
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    body = json.dumps({
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user_message}],
    }).encode()
    data = _api_call(PROVIDER_URLS["anthropic"], headers, body)
    text_blocks = [
        block.get("text", "")
        for block in data.get("content", [])
        if block.get("type") == "text"
    ]
    # Claude 5 models may spend the whole budget on thinking blocks for large tasks and return no
    # text at all. Retry once with a doubled budget (capped) before giving up.
    if not any(t.strip() for t in text_blocks) and data.get("stop_reason") == "max_tokens" and max_tokens < ANTHROPIC_MAX_OUTPUT_TOKENS:
        bigger = min(max_tokens * 2, ANTHROPIC_MAX_OUTPUT_TOKENS)
        print(
            f"  [RETRY] Anthropic returned only thinking blocks at max_tokens={max_tokens}; retrying with {bigger}.",
            file=sys.stderr,
        )
        return call_anthropic(api_key, model, system, user_message, max_tokens=bigger)
    if data.get("stop_reason") == "max_tokens":
        print(
            f"  [WARN] Anthropic response hit max_tokens={max_tokens}; the answer is truncated.",
            file=sys.stderr,
        )
    if not text_blocks:
        print(
            f"  [WARN] Anthropic returned no text block. "
            f"stop_reason={data.get('stop_reason')!r}, content_types="
            f"{[b.get('type') for b in data.get('content', [])]!r}",
            file=sys.stderr,
        )
    return "".join(text_blocks)


def call_openai(api_key, model, system, user_message, max_tokens=4096):
    """Call OpenAI Chat Completions API."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    body = json.dumps({
        "model": model,
        "max_completion_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ],
    }).encode()
    data = _api_call(PROVIDER_URLS["openai"], headers, body)
    msg = data["choices"][0]["message"]
    content = msg.get("content") or ""
    if data["choices"][0].get("finish_reason") == "length":
        print(
            f"  [WARN] OpenAI response hit max_completion_tokens={max_tokens}; the answer is truncated.",
            file=sys.stderr,
        )
    if not content:
        refusal = msg.get("refusal", "")
        finish = data["choices"][0].get("finish_reason", "unknown")
        print(
            f"  [WARN] OpenAI returned empty content. "
            f"finish_reason={finish}, refusal={refusal!r}",
            file=sys.stderr,
        )
    return content


def call_gemini(api_key, model, system, user_message, max_tokens=4096):
    """Call Google Gemini via its OpenAI-compatible endpoint."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    body = json.dumps({
        "model": model,
        "max_completion_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ],
    }).encode()
    data = _api_call(PROVIDER_URLS["gemini"], headers, body)
    return data["choices"][0]["message"]["content"]


PROVIDER_CALLERS = {
    "anthropic": call_anthropic,
    "openai": call_openai,
    "gemini": call_gemini,
}


def call_llm(provider, api_key, model, system, user_message, max_tokens=4096):
    """Unified LLM call that dispatches to the correct provider."""
    return PROVIDER_CALLERS[provider](api_key, model, system, user_message, max_tokens)


# ---------------------------------------------------------------------------
# Skill context loader
# ---------------------------------------------------------------------------

def load_skill_context():
    """Load SKILL.md, references, and examples as context for the agent."""
    parts = []

    skill_md = SKILL_DIR / "SKILL.md"
    if skill_md.exists():
        parts.append(f"# SKILL.md\n\n{skill_md.read_text()}")

    refs_dir = SKILL_DIR / "references"
    if refs_dir.exists():
        for ref_file in sorted(refs_dir.glob("*.md")):
            parts.append(f"# {ref_file.name}\n\n{ref_file.read_text()}")

    examples_dir = SKILL_DIR / "examples"
    if examples_dir.exists():
        for ex_file in sorted(examples_dir.glob("*.md")):
            parts.append(f"# Example: {ex_file.stem}\n\n{ex_file.read_text()}")

    return "\n\n---\n\n".join(parts)


# ---------------------------------------------------------------------------
# Eval runner
# ---------------------------------------------------------------------------

def run_agent(provider, api_key, model, skill_context, query, verbose=False):
    """Send the eval query to an LLM acting as an agent with the skill."""
    system = f"""You are an AI coding agent with access to the Conductor workflow skill. Your tools include: Bash (shell commands), Read/Write/Edit (files), Grep/Glob (search).

You must follow the skill instructions precisely. Key rules:
- CLI resolution follows the skill's Rule 3: use `conductor` if on PATH; otherwise prefer `npx @conductor-oss/conductor-cli ...`; run `npm install -g @conductor-oss/conductor-cli` ONLY after the user has explicitly agreed — in a plan that means ending your message with that question, never "proceeding". Fall back to `scripts/conductor_api.py` only when Node.js/npm cannot be installed.
- For an unqualified first-time setup, create both standard interactive profiles: `developer` (`https://developer.orkescloud.com/api`, Enterprise, key + secret) and `localhost` (`http://localhost:8080/api`, OSS, no auth). Default later commands to `--profile developer`; honor an explicit target instead.
- For the developer profile, visibly open Developer Edition when browser automation is available, let the user sign in, navigate through Access Control > Applications, and hand control to the user before Create access key. The user enters the one-time secret directly into the interactive CLI prompt; never read the page afterward, clipboard, terminal input, or profile YAML.
- Request auth setup only when the server returns 401/403 or the user explicitly says auth is required. Never ask the user to paste credential values into chat; use securely injected CONDUCTOR_AUTH_* variables and never put values in command arguments.
- If the user supplies a root remote URL, append `/api`; preserve an existing `/api` or custom non-root path. Set CONDUCTOR_SERVER_TYPE=Enterprise for Orkes.
- Create profiles interactively with `conductor config save --profile developer` and `conductor config save --profile localhost`. Discover profiles with `conductor config list`; never read raw profile YAML.
- ALWAYS verify the setup works with a final connectivity check (e.g. `conductor workflow list`).
- NEVER use `python3 -c` for any purpose.
- NEVER echo auth tokens, keys, or secrets in output — use env vars or CLI flags, and redact any sensitive values.
- Write workflow JSON to a file first, then pass the file path to CLI commands.
- After registering a workflow, you MUST check `conductor task list --json` to verify all SIMPLE tasks have registered workers. For any SIMPLE task missing from the task definitions, flag it to the user and offer to create the task definition and scaffold a worker.
- When writing workers, always include a comment or docstring noting the worker must be idempotent (safe to retry on failure/timeout).
- Use `--profile` when the user names an existing environment (dev, prod, staging); first discover profiles with `conductor config list`.
- Use `--json` flags when available for structured output.

When responding, describe the exact steps you would take:
1. Show the exact bash commands you would run (real commands, not placeholders)
2. Show the exact file contents you would write (complete JSON, not truncated)
3. Explain your decision logic at the branching points that matter (not every hypothetical path). For example:
   - If the user gives no setup target: create both standard profiles and make developer the skill default
   - If a command returns 401/403: describe how you would handle auth
   - If a tool/CLI is missing: show the fallback approach
4. Show what you would communicate to the user at each step

Follow the patterns from the examples in the skill context. Be thorough — cover prerequisites, the main action, all conditional branches, verification, and cleanup/next-steps.

--- SKILL INSTRUCTIONS ---

{skill_context}"""

    user_msg = f"""User query: {query}

Describe in detail the complete sequence of steps you would take to handle this request. Show exact commands, exact file contents, and exact user communications. Follow the skill rules strictly."""

    if verbose:
        print(f"  [AGENT] Sending query to {provider}:{model}...")

    # The skill context is ~70K tokens and the agent is asked for a complete plan with full JSON
    # and code; 8192 output tokens truncated real answers mid-plan, which the judge then failed.
    response = call_llm(provider, api_key, model, system, user_msg, max_tokens=AGENT_MAX_TOKENS)
    if not response or not response.strip():
        print(
            f"  [WARN] Agent ({provider}:{model}) returned an empty response. "
            f"The model may not support the prompt size or refused to answer.",
            file=sys.stderr,
        )
    return response


def judge_response(judge_provider, api_key, judge_model, query, agent_response, expected_behavior, success_criteria, verbose=False):
    """Use Claude as judge to evaluate the agent response."""
    system = """You are an evaluation judge for an AI coding agent. The agent was given a task and described the steps it WOULD take (a plan), without actually executing anything.

You must evaluate EACH success criterion individually based on the agent's described plan.

Evaluation guidelines:
- The agent is describing a PLAN, not showing actual execution output. Judge whether the plan WOULD satisfy each criterion if executed.
- "CLI is installed" / "install step included" means the plan runs `npx @conductor-oss/conductor-cli` or runs `npm install -g` after the user's explicit OK (not merely telling the user to install it); running a global install without consent is a failure of the consent criteria, not a pass of this one.
- "Auth tokens are never echoed" means the plan does not include printing/logging actual token values, and uses env vars or redacted placeholders appropriately.
- "Workflow definition is fetched from the server" means the plan includes a command to fetch it (e.g., `conductor workflow get ...`), even though no actual server response is shown.
- "Commands are shown" means the agent wrote out the actual CLI commands it would run, not vague descriptions.
- If the agent describes a conditional path (e.g., "if 401 then request auth"), credit the criterion if the relevant branch is covered.
- "Deployed via the SDK" means the plan calls `runtime.deploy(...)` (or the language equivalent) in code. A `conductor deploy` shell command does NOT satisfy it.
- "serve() is running" means the plan starts `runtime.serve(...)` as a separate, long-lived process (second terminal, container, service) — not merely calling `run()`.
- A criterion phrased "N/A and passing when <condition>" passes when that condition holds in the agent's plan, even though the agent did nothing for it.
- Be lenient on exact formatting but strict on whether the correct commands and approach are used.

Return a JSON object with this exact structure:
{
  "criteria_results": [
    {
      "criterion": "the criterion text",
      "pass": true or false,
      "reason": "brief explanation"
    }
  ],
  "overall_pass": true or false,
  "overall_score": 0.0 to 1.0,
  "summary": "1-2 sentence overall assessment"
}

Set overall_score to the fraction of criteria that passed (passed / total). Set overall_pass to true if at least 80% of criteria pass.
Return ONLY valid JSON, no other text."""

    user_msg = f"""## User Query
{query}

## Agent Response
{agent_response}

## Expected Behavior (for reference, not scored)
{json.dumps(expected_behavior, indent=2)}

## Success Criteria (score each one)
{json.dumps(success_criteria, indent=2)}

Evaluate each success criterion. Return JSON only."""

    if verbose:
        print(f"  [JUDGE] Evaluating with {judge_provider}:{judge_model}...")

    def _extract(raw):
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")[1:]  # remove opening ```json
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        # tolerate prose around the object
        if not text.startswith("{") and "{" in text:
            text = text[text.index("{"):text.rindex("}") + 1]
        return json.loads(text)

    raw = call_llm(judge_provider, api_key, judge_model, system, user_msg, max_tokens=16384)
    try:
        return _extract(raw)
    except (json.JSONDecodeError, ValueError):
        # One retry with a bigger budget and an explicit reminder; a judge that still fails is
        # reported as a runner error (visible in the report), never as a silent zero.
        print("  [RETRY] judge output was not valid JSON; retrying once with a larger budget", file=sys.stderr)
        raw = call_llm(judge_provider, api_key, judge_model, system,
                       user_msg + "\n\nReturn ONLY the JSON object — no prose, no markdown fences.", max_tokens=32768)
    try:
        return _extract(raw)
    except (json.JSONDecodeError, ValueError):
        return {
            "criteria_results": [],
            "overall_pass": False,
            "overall_score": 0.0,
            "summary": f"Judge returned invalid JSON: {raw[:200]}",
            "runner_error": True,
        }


def run_single_eval(provider, api_key, model, judge_provider, judge_api_key,
                     judge_model, skill_context, eval_file, verbose=False):
    """Run a single evaluation and return results."""
    with open(eval_file) as f:
        eval_data = json.load(f)

    name = eval_data["name"]
    query = eval_data["query"]
    expected_behavior = eval_data.get("expected_behavior", [])
    success_criteria = eval_data.get("success_criteria", [])

    print(f"\n{'='*60}")
    print(f"  EVAL: {name}")
    print(f"  FILE: {Path(eval_file).name}")
    print(f"  MODEL: {provider}:{model}")
    print(f"  JUDGE: {judge_provider}:{judge_model}")
    print(f"{'='*60}")

    # Step 1: Run agent
    agent_response = run_agent(provider, api_key, model, skill_context, query, verbose)

    if verbose:
        print(f"\n  --- Agent Response ---")
        print(f"  {agent_response[:500]}...")
        print(f"  --- End Response ---\n")

    # Step 2: Judge response
    judgment = judge_response(
        judge_provider, judge_api_key, judge_model, query, agent_response,
        expected_behavior, success_criteria, verbose
    )

    # Step 3: Display results
    criteria_results = judgment.get("criteria_results", [])
    passed = sum(1 for c in criteria_results if c.get("pass"))
    total = len(criteria_results) or len(success_criteria)
    score = judgment.get("overall_score", 0.0)
    overall = judgment.get("overall_pass", False)

    for cr in criteria_results:
        status = "PASS" if cr.get("pass") else "FAIL"
        icon = "+" if cr.get("pass") else "-"
        print(f"  [{icon}] {status}: {cr.get('criterion', '?')}")
        if not cr.get("pass") and verbose:
            print(f"         Reason: {cr.get('reason', '')}")

    print(f"\n  Score: {passed}/{total} criteria passed ({score:.0%})")
    print(f"  Overall: {'PASS' if overall else 'FAIL'}")
    print(f"  Summary: {judgment.get('summary', '')}")

    return {
        "name": name,
        "file": str(Path(eval_file).name),
        "provider": provider,
        "model": model,
        "overall_pass": overall,
        "overall_score": score,
        "passed": passed,
        "total": total,
        "summary": judgment.get("summary", ""),
        "runner_error": bool(judgment.get("runner_error")),
        "criteria_results": criteria_results,
        "agent_response": agent_response,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Run automated evaluations for the Conductor skill",
        epilog="""
Examples:
  python3 scripts/run_evals.py                                   # Anthropic (default)
  python3 scripts/run_evals.py --model gpt-4o                    # OpenAI
  python3 scripts/run_evals.py --model gemini-2.5-pro            # Google Gemini
  python3 scripts/run_evals.py --provider openai --model ft:gpt-4o:my-org
  python3 scripts/run_evals.py --model gpt-4o --judge-model claude-sonnet-4-20250514
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "files", nargs="*",
        help="Specific eval JSON files to run (default: all in evaluations/)"
    )
    parser.add_argument(
        "--model", default=DEFAULT_MODEL,
        help=f"Model for agent-under-test (default: {DEFAULT_MODEL})"
    )
    parser.add_argument(
        "--provider", choices=["anthropic", "openai", "gemini"], default=None,
        help="Provider for agent model (auto-detected from model name if omitted)"
    )
    parser.add_argument(
        "--judge-model", default=JUDGE_MODEL,
        help=f"Model for judge (default: {JUDGE_MODEL})"
    )
    parser.add_argument(
        "--judge-provider", choices=["anthropic", "openai", "gemini"], default=None,
        help="Provider for judge model (auto-detected from model name if omitted)"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Output JSON report")
    parser.add_argument("--output", "-o", default=None, help="Write JSON report to file")
    parser.add_argument(
        "--print-context-size", action="store_true",
        help="Print the size of the skill context sent to the agent and exit (no API key needed)"
    )

    args = parser.parse_args()

    # Context-size probe — runs before any provider/API-key resolution.
    if args.print_context_size:
        size = len(load_skill_context())
        print(f"Eval context size: {size} chars (~{size // 4} tokens)")
        sys.exit(0)

    # Resolve providers
    provider = resolve_provider(args.model, args.provider)
    judge_provider = resolve_provider(args.judge_model, args.judge_provider)

    # Get API keys
    api_key = get_api_key(provider)
    judge_api_key = get_api_key(judge_provider) if judge_provider != provider else api_key

    judge_model = args.judge_model

    # Collect eval files
    if args.files:
        eval_files = [Path(f) for f in args.files]
    else:
        eval_files = sorted(EVAL_DIR.glob("*.json"))

    if not eval_files:
        print("No evaluation files found.", file=sys.stderr)
        sys.exit(1)

    # Load skill context once
    print("Loading skill context...")
    skill_context = load_skill_context()
    print(f"Loaded {len(skill_context)} chars of skill context")
    print(f"Running {len(eval_files)} evaluation(s)")
    print(f"  Agent: {provider}:{args.model}")
    print(f"  Judge: {judge_provider}:{judge_model}")

    # Run evals
    results = []
    for eval_file in eval_files:
        if not eval_file.exists():
            print(f"Warning: {eval_file} not found, skipping.", file=sys.stderr)
            continue
        if eval_file.name == "README.md":
            continue

        try:
            result = run_single_eval(
                provider, api_key, args.model,
                judge_provider, judge_api_key, judge_model,
                skill_context, eval_file, args.verbose,
            )
        except SystemExit:
            raise
        except Exception as e:  # ApiError, JSON decode, anything else: record and continue
            try:
                spec = json.loads(eval_file.read_text())
                n_crit = len(spec.get("success_criteria", []))
                name = spec.get("name", eval_file.stem)
            except Exception:
                n_crit, name = 0, eval_file.stem
            print(f"  [ERROR] {eval_file.name}: {type(e).__name__}: {e}", file=sys.stderr)
            result = {
                "name": name, "file": eval_file.name, "provider": provider, "model": args.model,
                "overall_pass": False, "overall_score": 0.0, "passed": 0, "total": n_crit,
                "summary": f"runner error: {type(e).__name__}: {e}", "criteria_results": [],
                "agent_response": "", "runner_error": True,
            }
        results.append(result)
        if args.output:  # checkpoint so a crash or kill never loses completed evals
            with open(args.output, "w") as f:
                json.dump({"partial": True, "results": results}, f, indent=2)

    # Summary
    total_evals = len(results)
    passed_evals = sum(1 for r in results if r["overall_pass"])
    total_criteria = sum(r["total"] for r in results)
    passed_criteria = sum(r["passed"] for r in results)
    avg_score = sum(r["overall_score"] for r in results) / total_evals if total_evals else 0

    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    print(f"  Agent:    {provider}:{args.model}")
    print(f"  Judge:    {judge_provider}:{judge_model}")
    print(f"  Evals:    {passed_evals}/{total_evals} passed")
    print(f"  Criteria: {passed_criteria}/{total_criteria} passed")
    print(f"  Avg score: {avg_score:.0%}")
    print()

    for r in results:
        icon = "+" if r["overall_pass"] else "-"
        print(f"  [{icon}] {r['name']}: {r['passed']}/{r['total']} ({r['overall_score']:.0%})")

    print()

    # JSON report
    report = {
        "provider": provider,
        "model": args.model,
        "judge_provider": judge_provider,
        "judge_model": judge_model,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "summary": {
            "total_evals": total_evals,
            "passed_evals": passed_evals,
            "total_criteria": total_criteria,
            "passed_criteria": passed_criteria,
            "avg_score": round(avg_score, 3),
        },
        "results": results,
    }

    if args.json_output:
        # Strip agent_response from console JSON to keep it readable
        slim = json.loads(json.dumps(report))
        for r in slim["results"]:
            r.pop("agent_response", None)
        print(json.dumps(slim, indent=2))

    if args.output:
        with open(args.output, "w") as f:
            json.dump(report, f, indent=2)
        print(f"  Report written to {args.output}")

    # Exit code: fail if any eval failed
    sys.exit(0 if passed_evals == total_evals else 1)


if __name__ == "__main__":
    main()
