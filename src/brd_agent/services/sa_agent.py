"""Solution Architect agent for architecture and dev plan generation."""

import json
from pathlib import Path

from pydantic import ValidationError

from brd_agent.config import (
    load_sa_agent_mode,
    load_sa_llm_settings,
    load_sa_review_iterations,
    load_sa_review_prompt_paths,
)
from brd_agent.llm.client import LiteLLMClient
from brd_agent.schemas.brd import NormalizedBRD
from brd_agent.schemas.sa import SAArchitecturePlan, SAComponent, SADevelopmentPlan
from brd_agent.services.ba_agent import load_normalized_brd


class SAAgentError(Exception):
    """Raised when SA generation fails."""


def _strip_json_code_fence(text):
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    return stripped


def load_sa_inputs(brd_input_path, task_input_path):
    """Load normalized BRD JSON and BA task markdown from disk."""
    normalized_brd = load_normalized_brd(brd_input_path)
    task_path = Path(task_input_path)
    if not task_path.exists():
        raise FileNotFoundError("BA task artifact not found: {0}".format(task_path))

    task_markdown = task_path.read_text(encoding="utf-8").strip()
    if not task_markdown:
        raise SAAgentError("BA task artifact is empty: {0}".format(task_path))

    return normalized_brd, task_markdown


class SAAgent(object):
    """LLM-backed SA agent that generates architecture and dev plan markdown."""

    def __init__(
        self,
        llm_client,
        architecture_prompt_path,
        dev_plan_prompt_path,
        architecture_review_prompt_path,
        dev_plan_review_prompt_path,
        review_iterations=1,
        temperature=0.2,
    ):
        self.llm_client = llm_client
        self.architecture_prompt_path = Path(architecture_prompt_path)
        self.dev_plan_prompt_path = Path(dev_plan_prompt_path)
        self.architecture_review_prompt_path = Path(architecture_review_prompt_path)
        self.dev_plan_review_prompt_path = Path(dev_plan_review_prompt_path)
        self.review_iterations = review_iterations
        self.temperature = temperature

    def generate(self, normalized_brd, task_markdown):
        architecture_prompt = self._load_prompt(self.architecture_prompt_path)
        dev_plan_prompt = self._load_prompt(self.dev_plan_prompt_path)

        user_context = self._build_user_context(normalized_brd, task_markdown)

        architecture_response = self.llm_client.complete(
            system_prompt=architecture_prompt,
            user_prompt=user_context,
            temperature=self.temperature,
        )
        dev_plan_response = self.llm_client.complete(
            system_prompt=dev_plan_prompt,
            user_prompt=user_context,
            temperature=self.temperature,
        )

        architecture_plan = self._parse_with_retry(
            architecture_response,
            architecture_prompt,
            user_context,
            SAArchitecturePlan,
            "architecture",
        )
        dev_plan = self._parse_with_retry(
            dev_plan_response,
            dev_plan_prompt,
            user_context,
            SADevelopmentPlan,
            "dev_plan",
        )
        architecture_plan = self._review(
            architecture_plan,
            user_context,
            self.architecture_review_prompt_path,
            SAArchitecturePlan,
        )
        dev_plan = self._review(
            dev_plan,
            user_context,
            self.dev_plan_review_prompt_path,
            SADevelopmentPlan,
        )
        return architecture_plan, dev_plan

    def _parse_with_retry(self, raw_output, system_prompt, user_context, schema_cls, kind):
        try:
            return self._parse_payload(raw_output, schema_cls)
        except (ValueError, ValidationError) as first_error:
            repair_response = self.llm_client.complete(
                system_prompt=system_prompt,
                user_prompt=self._build_repair_prompt(
                    user_context,
                    raw_output,
                    str(first_error),
                    schema_cls,
                ),
                temperature=0.0,
            )
            try:
                return self._parse_payload(repair_response, schema_cls)
            except (ValueError, ValidationError) as second_error:
                raise SAAgentError(
                    "SA model returned invalid {0} JSON after retry: {1}".format(
                        kind,
                        second_error,
                    )
                )

    @staticmethod
    def _build_user_context(normalized_brd, task_markdown):
        return (
            "Normalized BRD JSON:\n"
            "{0}\n\n"
            "BA task markdown:\n"
            "{1}\n"
        ).format(normalized_brd.json(indent=2), task_markdown)

    @staticmethod
    def _build_repair_prompt(user_context, invalid_output, parse_error, schema_cls):
        return (
            "Your previous output was invalid JSON.\n"
            "Error: {0}\n\n"
            "Return ONLY valid JSON for this schema:\n"
            "{1}\n\n"
            "Context:\n"
            "{2}\n\n"
            "Previous output to repair:\n"
            "{3}\n"
        ).format(parse_error, schema_cls.schema_json(indent=2), user_context, invalid_output)

    @staticmethod
    def _parse_payload(raw_output, schema_cls):
        cleaned = _strip_json_code_fence(raw_output)
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as error:
            raise ValueError(str(error))
        return schema_cls.parse_obj(payload)

    @staticmethod
    def _load_prompt(prompt_path):
        if not prompt_path.exists():
            raise SAAgentError("SA prompt file not found: {0}".format(prompt_path))
        return prompt_path.read_text(encoding="utf-8")

    def _review(self, initial_plan, user_context, review_prompt_path, schema_cls):
        current_plan = initial_plan
        current_score = self._score_plan(initial_plan)
        review_prompt = self._load_prompt(review_prompt_path)
        for _ in range(self.review_iterations):
            review_response = self.llm_client.complete(
                system_prompt=review_prompt,
                user_prompt=(
                    "Context:\n{0}\n\n"
                    "Draft JSON:\n{1}\n\n"
                    "Rubric scores to improve:\n{2}\n\n"
                    "Return improved JSON only."
                ).format(
                    user_context,
                    current_plan.json(indent=2),
                    json.dumps(current_score, indent=2),
                ),
                temperature=0.0,
            )
            try:
                candidate = self._parse_payload(review_response, schema_cls)
            except (ValueError, ValidationError):
                continue
            candidate_score = self._score_plan(candidate)
            if candidate_score["overall"] >= current_score["overall"]:
                current_plan = candidate
                current_score = candidate_score
        return current_plan

    @staticmethod
    def _score_plan(plan):
        completeness = 0
        if isinstance(plan, SAArchitecturePlan):
            if plan.system_overview:
                completeness += 20
            if plan.high_level_architecture:
                completeness += 20
            if plan.components:
                completeness += 20
            if plan.data_flow:
                completeness += 20
            if plan.risks_and_tradeoffs:
                completeness += 20
            implementability = min(100, len(plan.components) * 20 + len(plan.integration_points) * 10)
            testability = min(100, len(plan.observability_considerations) * 20 + len(plan.non_functional_considerations) * 10)
        else:
            if plan.implementation_strategy:
                completeness += 20
            if plan.development_phases:
                completeness += 20
            if plan.module_breakdown:
                completeness += 20
            if plan.implementation_order:
                completeness += 20
            if plan.testing_considerations:
                completeness += 20
            implementability = min(100, len(plan.module_breakdown) * 15 + len(plan.implementation_order) * 10)
            testability = min(100, len(plan.testing_considerations) * 20)

        ambiguity_penalty = 0
        if hasattr(plan, "open_questions") and not plan.open_questions:
            ambiguity_penalty = 10
        if hasattr(plan, "clarification_items") and not plan.clarification_items:
            ambiguity_penalty = 10

        overall = max(
            0,
            int((completeness * 0.35) + (implementability * 0.35) + (testability * 0.3) - ambiguity_penalty),
        )
        return {
            "completeness": int(completeness),
            "implementability": int(implementability),
            "testability": int(testability),
            "ambiguity_penalty": int(ambiguity_penalty),
            "overall": int(overall),
        }


def generate_sa_artifacts(normalized_brd, task_markdown, llm_client=None):
    """Generate SA plans from BRD and BA artifacts with selected mode."""
    if not isinstance(normalized_brd, NormalizedBRD):
        raise SAAgentError("normalized_brd must be a NormalizedBRD instance.")

    mode = load_sa_agent_mode()
    if mode == "deterministic":
        return deterministic_generate_sa_artifacts(normalized_brd, task_markdown)

    settings = load_sa_llm_settings()
    client = llm_client or LiteLLMClient(
        model_name=settings.model_name,
        api_key=settings.api_key,
        base_url=settings.base_url,
    )
    review_paths = load_sa_review_prompt_paths()
    agent = SAAgent(
        llm_client=client,
        architecture_prompt_path=settings.architecture_prompt_path,
        dev_plan_prompt_path=settings.dev_plan_prompt_path,
        architecture_review_prompt_path=review_paths["architecture"],
        dev_plan_review_prompt_path=review_paths["dev_plan"],
        review_iterations=load_sa_review_iterations(),
        temperature=settings.temperature,
    )
    if mode == "llm":
        return agent.generate(normalized_brd, task_markdown)

    # hybrid
    try:
        return agent.generate(normalized_brd, task_markdown)
    except Exception:
        return deterministic_generate_sa_artifacts(normalized_brd, task_markdown)


def deterministic_generate_sa_artifacts(normalized_brd, task_markdown):
    """Deterministic SA plans for fallback and non-LLM mode."""
    architecture = SAArchitecturePlan(
        system_overview="Architecture aligned to BRD scope for {0}.".format(
            normalized_brd.project_name
        ),
        goals_and_constraints=list(normalized_brd.constraints),
        high_level_architecture="Layered service architecture with intake, prioritization logic, and routing.",
        architecture_decisions=[
            "Separate prioritization rules from routing to simplify future rule changes.",
            "Record audit trail for every prioritization decision.",
        ],
        components=[
            SAComponent(
                name="Ticket Intake",
                responsibility="Accept and validate ticket inputs.",
                interfaces=["POST /tickets", "Input queue consumer"],
            ),
            SAComponent(
                name="Prioritization Engine",
                responsibility="Apply business rules to determine priority.",
                interfaces=["Priority scoring service API"],
            ),
            SAComponent(
                name="Routing Module",
                responsibility="Assign tickets to resolver groups.",
                interfaces=["Routing rules API", "Assignment event publisher"],
            ),
        ],
        data_flow=[
            "Ticket received from support channels.",
            "Prioritization engine assigns urgency level.",
            "Routing module dispatches ticket and records audit trail.",
        ],
        integration_points=[
            "Support platform webhook/event ingestion",
            "Resolver group directory lookup",
        ],
        external_integrations=list(normalized_brd.dependencies),
        data_storage_considerations=[
            "Persist ticket metadata and prioritization decision history.",
        ],
        security_considerations=[
            "Restrict access to prioritization overrides.",
            "Audit all manual priority changes.",
        ],
        observability_considerations=[
            "Track priority distribution and SLA breach metrics.",
            "Alert on routing failures and queue latency.",
        ],
        non_functional_considerations=list(normalized_brd.non_functional_requirements),
        risks_and_tradeoffs=list(normalized_brd.risks),
        open_questions=list(normalized_brd.open_questions),
    )
    dev_plan = SADevelopmentPlan(
        implementation_strategy="Deliver foundational modules first, then integrate and harden.",
        development_phases=[
            "Phase 1: Core domain models and intake interfaces.",
            "Phase 2: Prioritization logic and routing implementation.",
            "Phase 3: Integration, observability, and SLA validation.",
        ],
        deliverables_by_phase=[
            "Phase 1: ticket schemas, intake adapter, and validation tests",
            "Phase 2: prioritization/routing modules with unit tests",
            "Phase 3: integration suite, dashboards, and deployment checklist",
        ],
        module_breakdown=[
            "Input adapters",
            "Prioritization rules",
            "Routing and assignment",
            "Audit logging",
        ],
        implementation_order=[
            "Define schemas and interfaces",
            "Implement prioritization engine",
            "Implement routing module",
            "Add end-to-end integration tests",
        ],
        risks_and_dependencies=list(normalized_brd.risks) + list(normalized_brd.dependencies),
        testing_considerations=[
            "Unit tests for prioritization rules.",
            "Integration tests for routing and audit trail.",
            "SLA-focused performance checks.",
        ],
        rollout_and_release_notes=[
            "Run shadow mode against historical tickets before full enablement.",
            "Enable manual rollback to previous prioritization policy.",
        ],
        clarification_items=list(normalized_brd.open_questions),
    )
    if task_markdown and "## Open Questions" in task_markdown:
        dev_plan.clarification_items.append(
            "Reconcile BA open questions with architecture assumptions before coding."
        )
    return architecture, dev_plan
