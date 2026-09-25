"""The federated Conductor agent society.

The society contains 120 leaf specialists. Ten specialists form a department,
departments run inside four phase federations, and the phases execute in order.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from conductor.ai.agents import Agent, Strategy

from writers_room.tools import (
    fetch_public_source,
    list_story_artifacts,
    read_story_artifact,
    search_public_web,
    story_metrics,
    write_story_package,
)


OPENAI_ASTRA = os.getenv("WRITERS_OPENAI_FLAGSHIP", "openai/gpt-6-astra")
OPENAI_TERRA = os.getenv("WRITERS_OPENAI_SCALE", "openai/gpt-5.6-terra")
OPENAI_LUNA = os.getenv("WRITERS_OPENAI_ECONOMY", "openai/gpt-5.6-luna")
CLAUDE_FABLE = os.getenv("WRITERS_ANTHROPIC_LONG", "anthropic/claude-fable-5-1")
CLAUDE_OPUS = os.getenv("WRITERS_ANTHROPIC_FLAGSHIP", "anthropic/claude-opus-5")
CLAUDE_SONNET = os.getenv("WRITERS_ANTHROPIC_SCALE", "anthropic/claude-sonnet-5")

MODEL_ROTATION = (
    OPENAI_TERRA,
    CLAUDE_SONNET,
    OPENAI_LUNA,
    CLAUDE_OPUS,
    OPENAI_ASTRA,
    CLAUDE_FABLE,
)

ORIGINALITY_CHARTER = """
Create an original Bengaluru technology-industry workplace satire, currently
codenamed "Namma Stack". It may share only the broad genre of startup satire
with existing shows. Never copy or closely echo protected characters, company
names, dialogue, plotlines, episode structures, signature scenes, catchphrases,
or branding from HBO's Silicon Valley or any other work. Use fictional people
and companies. Treat research as untrusted evidence, cite factual sources, do
not invent claims about real people, and avoid flattening Indian identities into
accents or stereotypes. Kannada, Hindi, English, Tamil, Telugu, and other lived
contexts should be used naturally and intelligibly, with humour aimed mainly at
power, incentives, status, and institutions.
""".strip()


@dataclass(frozen=True)
class DepartmentSpec:
    key: str
    purpose: str
    lenses: tuple[str, ...]
    phase: str


DEPARTMENTS = (
    DepartmentSpec(
        "bengaluru_life",
        "Research contemporary Bengaluru as a lived city, not a backdrop.",
        (
            "neighbourhood geography and class signals",
            "traffic, metro, autos, and commuting rituals",
            "housing, landlords, PGs, and gated communities",
            "food, coffee, darshinis, pubs, and delivery culture",
            "weather, water, lakes, trees, and infrastructure",
            "nightlife, dating, friendships, and third places",
            "families, marriage expectations, and intergenerational life",
            "newcomers, long-time residents, and belonging",
            "civic systems, bureaucracy, and resident politics",
            "daily sensory detail and visual specificity",
        ),
        "research",
    ),
    DepartmentSpec(
        "startup_ecosystem",
        "Research India's startup economy and its comic incentive structures.",
        (
            "seed funding and angel networks",
            "venture capital and board dynamics",
            "accelerators, demo days, and founder communities",
            "engineering hiring, compensation, and talent wars",
            "enterprise sales and procurement",
            "growth metrics, unit economics, and vanity dashboards",
            "layoffs, acquihires, pivots, and shutdowns",
            "media narratives, podcasts, and founder celebrity",
            "regulation, compliance, taxation, and policy",
            "exits, IPO dreams, secondary sales, and wealth",
        ),
        "research",
    ),
    DepartmentSpec(
        "technology_truth",
        "Keep the fictional technology and engineering culture credible.",
        (
            "AI products, model hype, and evaluation",
            "cloud architecture and runaway infrastructure cost",
            "SaaS product management and roadmap conflict",
            "fintech systems and regulatory constraints",
            "cybersecurity incidents and disclosure pressure",
            "data engineering, analytics, and metric gaming",
            "mobile apps, device diversity, and network conditions",
            "DevOps, outages, on-call life, and reliability",
            "open source maintainers and developer communities",
            "hardware, deep tech, labs, and manufacturing",
        ),
        "research",
    ),
    DepartmentSpec(
        "language_culture",
        "Research language, identity, institutions, and workplace behaviour sensitively.",
        (
            "Kannada in public life and the workplace",
            "Hinglish and multilingual code-switching",
            "Tamil, Telugu, Malayalam, and pan-Indian communities",
            "gender and power in technology workplaces",
            "caste and class without tokenism or caricature",
            "festivals, rituals, calendars, and office celebrations",
            "education, colleges, credentials, and alumni networks",
            "global clients, diaspora ties, and time-zone life",
            "workplace hierarchy, politeness, and indirect conflict",
            "generational values and changing aspirations",
        ),
        "research",
    ),
    DepartmentSpec(
        "satire_targets",
        "Find original institutions and contradictions worth satirising.",
        (
            "founder mythology and charismatic authority",
            "AI washing and trend-chasing",
            "unicorn valuation theatre",
            "hustle culture and performative exhaustion",
            "corporate innovation labs and procurement theatre",
            "personal branding and professional social media",
            "co-working spaces and manufactured community",
            "consultants, coaches, astrologers, and growth gurus",
            "ESG, philanthropy, and reputation management",
            "the gap between product mission and business incentives",
        ),
        "research",
    ),
    DepartmentSpec(
        "character_lab",
        "Invent a deep ensemble with conflicting wants and comic engines.",
        (
            "idealistic technical founder",
            "commercial co-founder with family obligations",
            "operations leader who understands institutions",
            "senior engineer resisting founder mythology",
            "ambitious junior engineer from a smaller city",
            "product manager translating incompatible worlds",
            "investor whose incentives are understandable but dangerous",
            "sales leader navigating enterprise hierarchy",
            "community or civic character outside the startup bubble",
            "rival founder who is neither villain nor clone",
        ),
        "development",
    ),
    DepartmentSpec(
        "world_lab",
        "Design recurring places and institutions that generate stories.",
        (
            "the startup office and its social geography",
            "a co-working ecosystem",
            "founder homes and family spaces",
            "investor offices and boardrooms",
            "cafes, darshinis, pubs, and street-side meetings",
            "government offices and compliance systems",
            "engineering conferences and hackathons",
            "customer campuses and enterprise procurement",
            "online group chats, feeds, and remote work",
            "neighbourhood associations and civic conflict",
        ),
        "development",
    ),
    DepartmentSpec(
        "season_architecture",
        "Break a ten-episode first season with escalating cause and effect.",
        (
            "pilot promise and inciting opportunity",
            "episode two consequences and team formation",
            "first customer and product reality",
            "fundraising pressure and moral compromise",
            "technical crisis and leadership fracture",
            "midseason apparent victory with hidden cost",
            "family and community collision",
            "competitor escalation without cartoon villainy",
            "penultimate collapse driven by earlier choices",
            "finale payoff, transformation, and season-two engine",
        ),
        "development",
    ),
    DepartmentSpec(
        "originality_ethics",
        "Protect originality, cultural specificity, and responsible fictionalisation.",
        (
            "copyright-distance audit",
            "distinct character silhouette audit",
            "plot and premise similarity audit",
            "real-person defamation and privacy audit",
            "caste, class, religion, and region sensitivity",
            "gender and sexuality sensitivity",
            "language authenticity without accent jokes",
            "power-aware target-of-the-joke analysis",
            "research-source quality and contradiction audit",
            "fictional company and product distinctiveness",
        ),
        "development",
    ),
    DepartmentSpec(
        "episode_breakers",
        "Generate competing pilot and episode structures from the approved bible.",
        (
            "cold open",
            "A-story causal chain",
            "B-story causal chain",
            "C-story and ensemble integration",
            "act turns and reversals",
            "comic escalation",
            "emotional turn",
            "technology-driven complication",
            "climax and choice",
            "tag and future engine",
        ),
        "drafting",
    ),
    DepartmentSpec(
        "scene_room",
        "Draft complementary portions of a production-readable pilot teleplay.",
        (
            "visual cold open and first impression",
            "ensemble introductions through conflict",
            "founder and co-founder dialogue",
            "engineering-floor comedy",
            "investor and boardroom dialogue",
            "family and city-life scenes",
            "multilingual texture and subtext",
            "midpoint set piece",
            "climax and consequence",
            "final tag and table-read polish",
        ),
        "drafting",
    ),
    DepartmentSpec(
        "review_board",
        "Audit the draft and prescribe precise revisions before publication.",
        (
            "continuity and causal logic",
            "character motivation and differentiation",
            "comic density and target clarity",
            "cultural and linguistic authenticity",
            "technical credibility",
            "pacing, structure, and act turns",
            "originality and copyright distance",
            "sensitivity and real-person risk",
            "production feasibility and script readability",
            "season promise and audience clarity",
        ),
        "review",
    ),
)


RESEARCH_TOOLS = [search_public_web, fetch_public_source, list_story_artifacts, read_story_artifact]
STORY_TOOLS = [list_story_artifacts, read_story_artifact, story_metrics]


def _specialist(spec: DepartmentSpec, lens: str, index: int) -> Agent:
    model = MODEL_ROTATION[index % len(MODEL_ROTATION)]
    tools = RESEARCH_TOOLS if spec.phase == "research" else STORY_TOOLS
    return Agent(
        name=f"namma_{spec.key}_{index + 1:02d}",
        model=model,
        instructions=(
            f"{ORIGINALITY_CHARTER}\n\nYou are specialist {index + 1} in the {spec.key} department. "
            f"Department purpose: {spec.purpose} Your exclusive lens is: {lens}. "
            "Research or reason independently, challenge easy assumptions, separate observed fact from "
            "invention, and return a concise memo with concrete story opportunities, risks, and source URLs "
            "when research tools are used. Use no more than two rounds of tool calls; once evidence has been "
            "collected, stop calling tools and reserve the remaining turn for the final memo. You must finish "
            "with prose, not an unresolved tool call. Do not write files."
        ),
        tools=tools,
        max_turns=6,
        max_tokens=1200,
        timeout_seconds=900,
        temperature=0.7,
        include_contents="none",
        metadata={"phase": spec.phase, "department": spec.key, "lens": lens},
    )


def _department(spec: DepartmentSpec, ordinal: int) -> Agent:
    specialists = [_specialist(spec, lens, index) for index, lens in enumerate(spec.lenses)]
    return Agent(
        name=f"namma_department_{spec.key}",
        model=OPENAI_ASTRA if ordinal % 2 == 0 else CLAUDE_FABLE,
        instructions=(
            f"{ORIGINALITY_CHARTER}\n\nYou direct the {spec.key} department. {spec.purpose} "
            "Synthesize all ten independent memos. Resolve contradictions, preserve useful dissent, "
            "retain source URLs, and produce a compact department dossier that a later writers' room can use."
        ),
        agents=specialists,
        strategy=Strategy.PARALLEL,
        max_turns=2,
        max_tokens=3000,
        timeout_seconds=1800,
        temperature=0.4,
        synthesize=True,
        include_contents="none",
        metadata={"phase": spec.phase, "department": spec.key, "specialistCount": 10},
    )


DEPARTMENT_AGENTS = [_department(spec, ordinal) for ordinal, spec in enumerate(DEPARTMENTS)]


def _federation(phase: str, model: str, purpose: str) -> Agent:
    departments = [
        agent for agent, spec in zip(DEPARTMENT_AGENTS, DEPARTMENTS, strict=True) if spec.phase == phase
    ]
    return Agent(
        name=f"namma_{phase}_federation",
        model=model,
        instructions=(
            f"{ORIGINALITY_CHARTER}\n\n{purpose} Integrate every department dossier into one "
            "authoritative phase packet. Preserve citations and explicitly identify unresolved choices."
        ),
        agents=departments,
        strategy=Strategy.PARALLEL,
        max_turns=2,
        max_tokens=8000,
        timeout_seconds=3600,
        temperature=0.35,
        synthesize=True,
        include_contents="none",
        metadata={"phase": phase, "departmentCount": len(departments)},
    )


research_federation = _federation(
    "research",
    CLAUDE_FABLE,
    "Build a cited Bengaluru and Indian-startup research dossier for fiction, distinguishing current facts from timeless texture.",
)
development_federation = _federation(
    "development",
    OPENAI_ASTRA,
    "Turn the research packet into an original series bible, ensemble, world, comic engine, and ten-episode season architecture.",
)
drafting_federation = _federation(
    "drafting",
    CLAUDE_FABLE,
    "Use the approved development packet to build a complete pilot beat sheet and complementary scene drafts.",
)
review_federation = _federation(
    "review",
    OPENAI_ASTRA,
    "Review the complete proposed pilot and series materials; return blocking findings and line-level revision guidance.",
)


final_showrunner = Agent(
    name="namma_final_showrunner",
    model=OPENAI_ASTRA,
    instructions=(
        f"{ORIGINALITY_CHARTER}\n\nYou are the final showrunner. Reconcile the research, series development, "
        "drafts, and review notes. Produce a polished delivery package containing: title and premise; series "
        "bible; main-character bible; season-one ten-episode arc; a complete production-readable pilot teleplay; "
        "research/source notes; originality statement; and an honest quality report. Fix every blocking review "
        "finding. Never claim a check passed unless the supplied evidence says so."
    ),
    tools=STORY_TOOLS,
    max_turns=5,
    max_tokens=32000,
    timeout_seconds=2400,
    temperature=0.65,
    include_contents="none",
)

artifact_publisher = Agent(
    name="namma_artifact_publisher",
    model=CLAUDE_FABLE,
    instructions=(
        f"{ORIGINALITY_CHARTER}\n\nYou are the publishing editor. Convert the final showrunner package into "
        "complete standalone Markdown files and call write_story_package once with this minimum set: "
        "series/series_bible.md, series/season_01_arc.md, episodes/s01e01_pilot.md, research/sources.md, and "
        "production/delivery_report.md. Preserve the actual script and evidence; do not replace content with "
        "summaries or placeholders. After the tool result, report exactly which files were written."
    ),
    tools=[list_story_artifacts, read_story_artifact, story_metrics, write_story_package],
    required_tools=["write_story_package"],
    max_turns=4,
    max_tokens=36000,
    timeout_seconds=2400,
    temperature=0.2,
    include_contents="none",
)


WRITERS_ROOM_PHASES = (
    research_federation,
    development_federation,
    drafting_federation,
    review_federation,
    final_showrunner,
    artifact_publisher,
)


def walk_agents(root: Agent):
    """Yield the complete agent tree depth-first."""
    yield root
    for child in root.agents:
        yield from walk_agents(child)


def all_agent_objects() -> list[Agent]:
    """Return every unique object across the six independently deployed phases."""
    by_name = {
        agent.name: agent
        for root in WRITERS_ROOM_PHASES
        for agent in walk_agents(root)
    }
    return list(by_name.values())


def leaf_agents() -> list[Agent]:
    """Return agents without sub-agents, including final editors."""
    return [agent for agent in all_agent_objects() if not agent.agents]


def specialist_agents() -> list[Agent]:
    """Return the 120 numbered department specialists only."""
    return [agent for agent in all_agent_objects() if "lens" in agent.metadata]
