"""Nested Conductor agents that analyze, implement, test, and review software."""

from __future__ import annotations

import os

from conductor.ai.agents import (
    Agent,
    MaxMessageTermination,
    OnTextMention,
    Strategy,
    TextMentionTermination,
)

from software_society.tools import (
    apply_change_set,
    inspect_workspace,
    read_workspace_file,
    run_quality_checks,
    search_workspace,
    workspace_diff,
)


MODEL = os.environ.get("SOFTWARE_SOCIETY_MODEL", "openai/gpt-4o-mini")
if "/" not in MODEL:
    raise ValueError("SOFTWARE_SOCIETY_MODEL must use provider/model form")

READ_TOOLS = [inspect_workspace, read_workspace_file, search_workspace, workspace_diff]
BUILD_TOOLS = [*READ_TOOLS, apply_change_set, run_quality_checks]


# Phase 1: independent perspectives fan out, then the council synthesizes one build contract.
product_analyst = Agent(
    name="society_product_analyst",
    model=MODEL,
    instructions=(
        "Turn the short requirement into a crisp product contract. Identify users, core behavior, "
        "non-goals, acceptance criteria, and ambiguities. Inspect the workspace before assuming this "
        "is a greenfield project. Do not write files."
    ),
    tools=READ_TOOLS,
    max_turns=3,
    timeout_seconds=180,
)

system_architect = Agent(
    name="society_system_architect",
    model=MODEL,
    instructions=(
        "Inspect the existing repository and propose the smallest coherent architecture that satisfies "
        "the requirement. Name exact files and interfaces, preserve local conventions, and avoid "
        "unnecessary dependencies. Do not write files."
    ),
    tools=READ_TOOLS,
    max_turns=4,
    timeout_seconds=180,
)

test_strategist = Agent(
    name="society_test_strategist",
    model=MODEL,
    instructions=(
        "Derive executable acceptance tests, edge cases, and a practical test plan from the requirement "
        "and repository conventions. Call out how failures will be diagnosed. Do not write files."
    ),
    tools=READ_TOOLS,
    max_turns=3,
    timeout_seconds=180,
)

security_architect = Agent(
    name="society_security_architect",
    model=MODEL,
    instructions=(
        "Threat-model the proposed feature. Identify trust boundaries, input validation, secret handling, "
        "dependency and command-execution risks, and concrete mitigations. Stay proportional to the brief. "
        "Do not write files."
    ),
    tools=READ_TOOLS,
    max_turns=3,
    timeout_seconds=180,
)

planning_council = Agent(
    name="software_planning_council",
    model=MODEL,
    instructions=(
        "Synthesize the four independent analyses into one implementation contract. Preserve the original "
        "requirement, resolve conflicts explicitly, list exact deliverables, and finish with acceptance "
        "checks the development guild can execute."
    ),
    agents=[product_analyst, system_architect, test_strategist, security_architect],
    strategy=Strategy.PARALLEL,
    max_turns=3,
    timeout_seconds=300,
    synthesize=True,
)


# Phase 2: specialists share the council output and can hand work back until it passes.
implementation_engineer = Agent(
    name="society_implementation_engineer",
    model=MODEL,
    instructions=(
        "Implement the approved planning-council contract in the configured workspace. Inspect before "
        "editing. Use apply_change_set for cohesive, minimal batches; it requires human approval and may be "
        "retried, so always send complete file contents. Preserve unrelated work. Run the relevant checks. "
        "When the implementation is ready, transfer to society_test_engineer."
    ),
    tools=BUILD_TOOLS,
    max_turns=8,
    timeout_seconds=600,
    include_contents="default",
)

test_engineer = Agent(
    name="society_test_engineer",
    model=MODEL,
    instructions=(
        "Verify every acceptance criterion against the actual workspace. Add focused tests with "
        "apply_change_set when coverage is missing, then run an allow-listed quality-check profile. If a "
        "check fails, say TESTS_FAILED with precise evidence and transfer to society_implementation_engineer. "
        "If it passes, transfer to society_code_reviewer."
    ),
    tools=BUILD_TOOLS,
    max_turns=7,
    timeout_seconds=600,
    include_contents="default",
)

code_reviewer = Agent(
    name="society_code_reviewer",
    model=MODEL,
    instructions=(
        "Review the complete diff for correctness, maintainability, compatibility, and needless complexity. "
        "Read the relevant files; do not edit them. If material changes are needed, say CHANGES_REQUIRED "
        "with file-specific findings and transfer to society_implementation_engineer. Otherwise transfer "
        "to society_security_reviewer."
    ),
    tools=READ_TOOLS,
    max_turns=5,
    timeout_seconds=300,
    include_contents="default",
)

security_reviewer = Agent(
    name="society_security_reviewer",
    model=MODEL,
    instructions=(
        "Review the implemented diff against the threat model: validation, path traversal, injection, "
        "secrets, unsafe execution, authorization, and dependency risk. Do not edit files. If remediation "
        "is needed, say CHANGES_REQUIRED and transfer to society_implementation_engineer. Otherwise transfer "
        "to society_release_steward."
    ),
    tools=READ_TOOLS,
    max_turns=5,
    timeout_seconds=300,
    include_contents="default",
)

release_steward = Agent(
    name="society_release_steward",
    model=MODEL,
    instructions=(
        "Perform the final release check. Inspect the diff, verify the planning contract, and run the "
        "allow-listed project checks. If anything fails, say TESTS_FAILED or CHANGES_REQUIRED and transfer "
        "to society_implementation_engineer. When the implementation is genuinely ready, end with the exact "
        "marker SOCIETY_BUILD_COMPLETE and summarize files changed, checks run, known limitations, and how "
        "to use the new software."
    ),
    tools=[*READ_TOOLS, run_quality_checks],
    max_turns=5,
    timeout_seconds=600,
    include_contents="default",
)

development_swarm = Agent(
    name="software_development_swarm",
    model=MODEL,
    instructions=(
        "Coordinate implementation of the planning-council contract. Start by transferring to "
        "society_implementation_engineer. Require tests, code review, security review, and release review. "
        "Never claim completion before the release steward emits SOCIETY_BUILD_COMPLETE."
    ),
    agents=[
        implementation_engineer,
        test_engineer,
        code_reviewer,
        security_reviewer,
        release_steward,
    ],
    strategy=Strategy.SWARM,
    handoffs=[
        OnTextMention(text="TESTS_FAILED", target="society_implementation_engineer"),
        OnTextMention(text="CHANGES_REQUIRED", target="society_implementation_engineer"),
    ],
    allowed_transitions={
        "software_development_swarm": ["society_implementation_engineer"],
        "society_implementation_engineer": ["society_test_engineer"],
        "society_test_engineer": [
            "society_implementation_engineer",
            "society_code_reviewer",
        ],
        "society_code_reviewer": [
            "society_implementation_engineer",
            "society_security_reviewer",
        ],
        "society_security_reviewer": [
            "society_implementation_engineer",
            "society_release_steward",
        ],
        "society_release_steward": ["society_implementation_engineer"],
    },
    termination=(
        TextMentionTermination("SOCIETY_BUILD_COMPLETE") | MaxMessageTermination(28)
    ),
    max_turns=16,
    timeout_seconds=1800,
    include_contents="default",
    synthesize=True,
)


# Phase 3: a fresh reader produces the user-facing delivery report from the actual workspace.
delivery_reporter = Agent(
    name="society_delivery_reporter",
    model=MODEL,
    instructions=(
        "Independently inspect the resulting workspace and the development report. Produce the final delivery "
        "note: requirement coverage, architecture, files changed, test evidence, security considerations, "
        "known limitations, and exact run instructions. Do not modify files and do not hide failed checks."
    ),
    tools=READ_TOOLS,
    max_turns=5,
    timeout_seconds=300,
    include_contents="default",
)


SOFTWARE_SOCIETY = Agent(
    name="software_society",
    model=MODEL,
    instructions=(
        "Convert a short software requirement into a reviewed implementation. The planning council analyzes "
        "in parallel, the development swarm implements and iterates, and the delivery reporter verifies the "
        "actual workspace. Pass each phase's complete output to the next phase."
    ),
    agents=[planning_council, development_swarm, delivery_reporter],
    strategy=Strategy.SEQUENTIAL,
    max_turns=3,
    timeout_seconds=2400,
    include_contents="default",
)
