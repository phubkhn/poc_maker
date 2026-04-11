"""Business Analyst agent for task breakdown generation."""

import json
from pathlib import Path

from pydantic import ValidationError

from brd_agent.config import (
    load_ba_agent_mode,
    load_ba_llm_settings,
    load_ba_review_iterations,
    load_ba_review_prompt_path,
)
from brd_agent.llm.client import LiteLLMClient
from brd_agent.schemas.ba import BAEpic, BAPlan, BATask
from brd_agent.schemas.brd import NormalizedBRD


class BAAgentError(Exception):
    """Raised when BA task generation fails."""


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


def load_normalized_brd(input_path):
    """Load normalized BRD JSON from disk."""
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(
            "Normalized BRD artifact not found: {0}".format(path)
        )

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise BAAgentError(
            "Invalid normalized BRD JSON in {0}: {1}".format(path, error)
        )
    return NormalizedBRD.parse_obj(payload)


class BAAgent(object):
    """LLM-backed BA task generation agent."""

    def __init__(
        self,
        llm_client,
        prompt_path,
        review_prompt_path,
        review_iterations=1,
        temperature=0.2,
    ):
        self.llm_client = llm_client
        self.prompt_path = Path(prompt_path)
        self.review_prompt_path = Path(review_prompt_path)
        self.review_iterations = review_iterations
        self.temperature = temperature

    def generate_plan(self, normalized_brd):
        system_prompt = self._load_system_prompt()
        user_prompt = self._build_user_prompt(normalized_brd)
        first_response = self.llm_client.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=self.temperature,
        )

        try:
            draft_plan = self._parse_plan(first_response)
        except ValueError as parse_error:
            repair_response = self.llm_client.complete(
                system_prompt=system_prompt,
                user_prompt=self._build_repair_prompt(
                    normalized_brd,
                    first_response,
                    str(parse_error),
                ),
                temperature=0.0,
            )
            try:
                draft_plan = self._parse_plan(repair_response)
            except (ValueError, ValidationError) as second_error:
                raise BAAgentError(
                    "BA model returned invalid JSON after retry: {0}".format(
                        second_error
                    )
                )
        except ValidationError as validation_error:
            raise BAAgentError(
                "BA model returned JSON but schema validation failed: {0}".format(
                    validation_error
                )
            )
        return self._review(normalized_brd, draft_plan)

    def _load_system_prompt(self):
        if not self.prompt_path.exists():
            raise BAAgentError(
                "BA prompt file not found: {0}".format(self.prompt_path)
            )
        return self.prompt_path.read_text(encoding="utf-8")

    def _load_review_prompt(self):
        if not self.review_prompt_path.exists():
            raise BAAgentError(
                "BA review prompt file not found: {0}".format(self.review_prompt_path)
            )
        return self.review_prompt_path.read_text(encoding="utf-8")

    @staticmethod
    def _build_user_prompt(normalized_brd):
        return (
            "Use this normalized BRD JSON as your only source of truth:\n"
            "{0}\n\n"
            "Return ONLY valid JSON using this schema:\n"
            "{1}\n"
        ).format(normalized_brd.json(indent=2), BAPlan.schema_json(indent=2))

    @staticmethod
    def _build_repair_prompt(normalized_brd, invalid_output, parse_error):
        return (
            "Your previous BA output was invalid JSON.\n"
            "Error: {0}\n\n"
            "Return ONLY valid JSON for this schema:\n"
            "{1}\n\n"
            "Normalized BRD JSON:\n"
            "{2}\n\n"
            "Previous output to repair:\n"
            "{3}\n"
        ).format(
            parse_error,
            BAPlan.schema_json(indent=2),
            normalized_brd.json(indent=2),
            invalid_output,
        )

    @staticmethod
    def _parse_plan(raw_output):
        cleaned = _strip_json_code_fence(raw_output)
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as error:
            raise ValueError(str(error))
        return BAPlan.parse_obj(payload)

    def _review(self, normalized_brd, initial_plan):
        current_plan = initial_plan
        current_score = self._score_plan(current_plan)
        review_prompt = self._load_review_prompt()

        for _ in range(self.review_iterations):
            review_response = self.llm_client.complete(
                system_prompt=review_prompt,
                user_prompt=(
                    "Normalized BRD JSON:\n{0}\n\n"
                    "Draft BA JSON:\n{1}\n\n"
                    "Rubric scores to improve:\n{2}\n\n"
                    "Return improved BA JSON only."
                ).format(
                    normalized_brd.json(indent=2),
                    current_plan.json(indent=2),
                    json.dumps(current_score, indent=2),
                ),
                temperature=0.0,
            )
            try:
                candidate = self._parse_plan(review_response)
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
        if plan.project_summary:
            completeness += 20
        if plan.scope_summary:
            completeness += 20
        if plan.epics:
            completeness += 20
        task_count = 0
        acceptance_count = 0
        for epic in plan.epics:
            task_count += len(epic.tasks)
            for task in epic.tasks:
                acceptance_count += len(task.acceptance_criteria)
        if task_count > 0:
            completeness += 20
        if acceptance_count > 0:
            completeness += 20

        implementability = min(100, task_count * 15 + acceptance_count * 5)
        testability = min(100, acceptance_count * 20)
        ambiguity_penalty = 0
        if not plan.open_questions and not plan.assumptions:
            ambiguity_penalty = 20

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


def deterministic_generate_ba_plan(normalized_brd):
    """Deterministic BA plan generator for fallback and non-LLM mode."""
    epic_tasks = []
    for item in normalized_brd.functional_requirements or normalized_brd.in_scope:
        epic_tasks.append(
            BATask(
                title=item,
                description="Implement and validate: {0}".format(item),
                module_hint="Core business logic",
                dependency_notes=list(normalized_brd.dependencies),
                risk_notes=list(normalized_brd.risks),
                open_questions=list(normalized_brd.open_questions[:2]),
                acceptance_criteria=list(normalized_brd.acceptance_criteria[:2]),
            )
        )

    if not epic_tasks:
        epic_tasks = [
            BATask(
                title="Clarify requirements",
                description="Gather missing BRD details before implementation.",
                module_hint="Discovery",
                dependency_notes=[],
                risk_notes=["Scope ambiguity may delay implementation."],
                open_questions=list(normalized_brd.open_questions),
                acceptance_criteria=["Open questions are resolved."],
            )
        ]

    return BAPlan(
        project_summary=normalized_brd.business_goal or normalized_brd.project_name,
        scope_summary=", ".join(normalized_brd.in_scope) if normalized_brd.in_scope else "Not specified in BRD.",
        epics=[
            BAEpic(
                name="Core Delivery",
                objective="Deliver scoped business capabilities with clear acceptance criteria.",
                summary="Deliver in-scope capabilities from normalized BRD.",
                out_of_scope_notes=list(normalized_brd.out_of_scope),
                tasks=epic_tasks,
            )
        ],
        implementation_notes=[
            "Prioritize tasks with high business impact first.",
            "Resolve open questions before locking implementation sequence.",
        ],
        cross_epic_dependencies=list(normalized_brd.dependencies),
        dependencies=list(normalized_brd.dependencies),
        risks=list(normalized_brd.risks),
        assumptions=list(normalized_brd.assumptions),
        open_questions=list(normalized_brd.open_questions),
    )


def generate_ba_plan(normalized_brd, llm_client=None):
    """Generate BA plan from a NormalizedBRD object using configured mode."""
    mode = load_ba_agent_mode()
    if mode == "deterministic":
        return deterministic_generate_ba_plan(normalized_brd)

    settings = load_ba_llm_settings()
    client = llm_client or LiteLLMClient(
        model_name=settings.model_name,
        api_key=settings.api_key,
        base_url=settings.base_url,
    )
    agent = BAAgent(
        llm_client=client,
        prompt_path=settings.prompt_path,
        review_prompt_path=load_ba_review_prompt_path(),
        review_iterations=load_ba_review_iterations(),
        temperature=settings.temperature,
    )
    if mode == "llm":
        return agent.generate_plan(normalized_brd)

    # hybrid
    try:
        return agent.generate_plan(normalized_brd)
    except BAAgentError:
        return deterministic_generate_ba_plan(normalized_brd)
