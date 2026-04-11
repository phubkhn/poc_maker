"""Developer agent for implementation-oriented code artifact generation."""

import json
from pathlib import Path

from pydantic import ValidationError

from brd_agent.config import (
    DEFAULT_CODE_STANDARDS_NAME,
    DEFAULT_REVIEW_STANDARDS_NAME,
    load_dev_agent_mode,
    load_dev_llm_settings,
    load_dev_review_iterations,
    load_dev_review_prompt_path,
)
from brd_agent.llm.client import LiteLLMClient
from brd_agent.schemas.brd import NormalizedBRD
from brd_agent.schemas.dev import DevCodeArtifact, DevPlan
from brd_agent.services.ba_agent import load_normalized_brd
from brd_agent.services.standards import (
    default_code_standards_context,
    default_review_standards_context,
)


class DevAgentError(Exception):
    """Raised when Dev generation fails."""


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


def _default_code_standards_markdown():
    lines = ["# Code Standards"]
    for section in default_code_standards_context()["sections"]:
        lines.append("")
        lines.append("## {0}".format(section["title"]))
        for item in section["items"]:
            lines.append("- {0}".format(item))
    return "\n".join(lines).strip()


def _default_review_standards_markdown():
    context = default_review_standards_context()
    lines = ["# Review Standards", "", "## Severity Levels"]
    for item in context["severity_levels"]:
        lines.append("- {0}".format(item))
    lines.append("")
    lines.append("## Stage Checklists")
    for checklist in context["stage_checklists"]:
        lines.append("### {0}".format(checklist["stage"]))
        for item in checklist["checks"]:
            lines.append("- {0}".format(item))
    lines.append("")
    lines.append("## Definition Of Done")
    for item in context["definition_of_done"]:
        lines.append("- {0}".format(item))
    return "\n".join(lines).strip()


def load_dev_inputs(
    brd_input_path,
    task_input_path,
    architecture_input_path,
    dev_plan_input_path,
    code_standards_input_path=None,
    review_standards_input_path=None,
):
    """Load artifacts required by Dev agent."""
    normalized_brd = load_normalized_brd(brd_input_path)

    task_path = Path(task_input_path)
    architecture_path = Path(architecture_input_path)
    dev_plan_path = Path(dev_plan_input_path)
    standards_path = (
        Path(code_standards_input_path) if code_standards_input_path else None
    )
    review_path = (
        Path(review_standards_input_path) if review_standards_input_path else None
    )

    if not task_path.exists():
        raise FileNotFoundError("BA task artifact not found: {0}".format(task_path))
    if not architecture_path.exists():
        raise FileNotFoundError(
            "SA architecture artifact not found: {0}".format(architecture_path)
        )
    if not dev_plan_path.exists():
        raise FileNotFoundError(
            "SA development plan artifact not found: {0}".format(dev_plan_path)
        )
    if standards_path and not standards_path.exists():
        raise FileNotFoundError(
            "Code standards artifact not found: {0}".format(standards_path)
        )
    if review_path and not review_path.exists():
        raise FileNotFoundError(
            "Review standards artifact not found: {0}".format(review_path)
        )

    task_markdown = task_path.read_text(encoding="utf-8").strip()
    architecture_markdown = architecture_path.read_text(encoding="utf-8").strip()
    dev_plan_markdown = dev_plan_path.read_text(encoding="utf-8").strip()
    code_standards_markdown = _default_code_standards_markdown()
    review_standards_markdown = _default_review_standards_markdown()
    if standards_path:
        code_standards_markdown = standards_path.read_text(encoding="utf-8").strip()
    if review_path:
        review_standards_markdown = review_path.read_text(encoding="utf-8").strip()

    if not task_markdown:
        raise DevAgentError("BA task artifact is empty: {0}".format(task_path))
    if not architecture_markdown:
        raise DevAgentError("SA architecture artifact is empty: {0}".format(architecture_path))
    if not dev_plan_markdown:
        raise DevAgentError("SA development plan artifact is empty: {0}".format(dev_plan_path))
    if not code_standards_markdown:
        raise DevAgentError(
            "Code standards artifact is empty: {0}".format(
                standards_path if standards_path else DEFAULT_CODE_STANDARDS_NAME
            )
        )
    if not review_standards_markdown:
        raise DevAgentError(
            "Review standards artifact is empty: {0}".format(
                review_path if review_path else DEFAULT_REVIEW_STANDARDS_NAME
            )
        )

    return (
        normalized_brd,
        task_markdown,
        architecture_markdown,
        dev_plan_markdown,
        code_standards_markdown,
        review_standards_markdown,
    )


class DevAgent(object):
    """LLM-backed Dev agent."""

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

    def generate(
        self,
        normalized_brd,
        task_markdown,
        architecture_markdown,
        dev_plan_markdown,
        code_standards_markdown,
        review_standards_markdown,
    ):
        system_prompt = self._load_prompt(self.prompt_path)
        user_prompt = self._build_user_prompt(
            normalized_brd,
            task_markdown,
            architecture_markdown,
            dev_plan_markdown,
            code_standards_markdown,
            review_standards_markdown,
        )
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
                user_prompt=self._build_repair_prompt(user_prompt, first_response, str(parse_error)),
                temperature=0.0,
            )
            try:
                draft_plan = self._parse_plan(repair_response)
            except (ValueError, ValidationError) as second_error:
                raise DevAgentError(
                    "Dev model returned invalid JSON after retry: {0}".format(second_error)
                )
        except ValidationError as validation_error:
            raise DevAgentError(
                "Dev model returned JSON but schema validation failed: {0}".format(
                    validation_error
                )
            )

        return self._review(user_prompt, draft_plan)

    @staticmethod
    def _build_user_prompt(
        normalized_brd,
        task_markdown,
        architecture_markdown,
        dev_plan_markdown,
        code_standards_markdown,
        review_standards_markdown,
    ):
        return (
            "Normalized BRD JSON:\n"
            "{0}\n\n"
            "BA task markdown:\n"
            "{1}\n\n"
            "SA architecture markdown:\n"
            "{2}\n\n"
            "SA development plan markdown:\n"
            "{3}\n\n"
            "Code standards markdown (must be followed):\n"
            "{4}\n\n"
            "Review standards markdown (must be followed):\n"
            "{5}\n\n"
            "Return ONLY valid JSON following this schema:\n"
            "{6}\n"
        ).format(
            normalized_brd.json(indent=2),
            task_markdown,
            architecture_markdown,
            dev_plan_markdown,
            code_standards_markdown,
            review_standards_markdown,
            DevPlan.schema_json(indent=2),
        )

    @staticmethod
    def _build_repair_prompt(user_prompt, invalid_output, parse_error):
        return (
            "Your previous output was invalid JSON.\n"
            "Error: {0}\n\n"
            "Return ONLY valid JSON following this schema:\n"
            "{1}\n\n"
            "Original context:\n"
            "{2}\n\n"
            "Previous output to repair:\n"
            "{3}\n"
        ).format(parse_error, DevPlan.schema_json(indent=2), user_prompt, invalid_output)

    @staticmethod
    def _parse_plan(raw_output):
        cleaned = _strip_json_code_fence(raw_output)
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as error:
            raise ValueError(str(error))
        return DevPlan.parse_obj(payload)

    def _load_prompt(self, prompt_path):
        if not prompt_path.exists():
            raise DevAgentError("Prompt file not found: {0}".format(prompt_path))
        return prompt_path.read_text(encoding="utf-8")

    def _review(self, user_prompt, initial_plan):
        current_plan = initial_plan
        current_score = self._score_plan(initial_plan)
        review_prompt = self._load_prompt(self.review_prompt_path)

        for _ in range(self.review_iterations):
            response = self.llm_client.complete(
                system_prompt=review_prompt,
                user_prompt=(
                    "Context:\n{0}\n\n"
                    "Draft Dev JSON:\n{1}\n\n"
                    "Rubric scores to improve:\n{2}\n\n"
                    "Return improved Dev JSON only."
                ).format(
                    user_prompt,
                    current_plan.json(indent=2),
                    json.dumps(current_score, indent=2),
                ),
                temperature=0.0,
            )
            try:
                candidate = self._parse_plan(response)
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
        if plan.implementation_summary:
            completeness += 20
        if plan.setup_steps:
            completeness += 20
        if plan.module_plan:
            completeness += 20
        if plan.code_artifacts:
            completeness += 20
        if plan.verification_steps:
            completeness += 20

        implementability = min(100, len(plan.code_artifacts) * 25 + len(plan.module_plan) * 10)
        testability = min(100, len(plan.verification_steps) * 20)

        ambiguity_penalty = 0
        if not plan.open_questions and not plan.assumptions:
            ambiguity_penalty = 10

        overall = max(
            0,
            int((completeness * 0.35) + (implementability * 0.4) + (testability * 0.25) - ambiguity_penalty),
        )
        return {
            "completeness": int(completeness),
            "implementability": int(implementability),
            "testability": int(testability),
            "ambiguity_penalty": int(ambiguity_penalty),
            "overall": int(overall),
        }


def deterministic_generate_dev_plan(normalized_brd, task_markdown, architecture_markdown, dev_plan_markdown):
    """Deterministic Dev plan used for deterministic and hybrid fallback modes."""
    return DevPlan(
        implementation_summary=(
            "Implement core modules for {0} based on BA/SA artifacts, then validate by staged testing."
        ).format(normalized_brd.project_name),
        setup_steps=[
            "Create isolated virtual environment and install project dependencies.",
            "Set required environment variables for LLM-backed flows.",
            "Run baseline test suite before development changes.",
        ],
        module_plan=[
            "Implement BRD ingestion and normalization service boundaries.",
            "Implement planning services for BA and SA artifacts.",
            "Implement orchestration pipeline entrypoint and gate checks.",
        ],
        code_artifacts=[
            DevCodeArtifact(
                file_path="src/brd_agent/services/orchestrator.py",
                language="python",
                purpose="Coordinate BA -> SA -> Dev -> QA stages with per-step review passes.",
                code_snippet=(
                    "class PipelineOrchestrator(object):\n"
                    "    def run(self, input_path, output_dir):\n"
                    "        # run stage, validate gate, then continue\n"
                    "        return {'status': 'ok'}"
                ),
            ),
            DevCodeArtifact(
                file_path="src/brd_agent/services/dev_agent.py",
                language="python",
                purpose="Generate implementation-oriented code artifact plan from BRD/BA/SA outputs.",
                code_snippet=(
                    "def generate_dev_plan(normalized_brd, task_markdown, architecture_markdown, dev_plan_markdown):\n"
                    "    # parse LLM JSON, validate schema, review once\n"
                    "    return DevPlan()"
                ),
            ),
        ],
        verification_steps=[
            "Run unit tests for loader, analyzer, BA, SA, Dev, and QA services.",
            "Execute end-to-end pipeline command and verify all artifacts are written.",
            "Validate gates do not pass empty artifacts.",
        ],
        risks=list(normalized_brd.risks),
        assumptions=list(normalized_brd.assumptions),
        open_questions=list(normalized_brd.open_questions),
    )


def generate_dev_plan(
    normalized_brd,
    task_markdown,
    architecture_markdown,
    dev_plan_markdown,
    code_standards_markdown,
    review_standards_markdown,
    llm_client=None,
):
    """Generate Dev artifact plan with configurable execution mode."""
    if not isinstance(normalized_brd, NormalizedBRD):
        raise DevAgentError("normalized_brd must be a NormalizedBRD instance.")

    mode = load_dev_agent_mode()
    if mode == "deterministic":
        return deterministic_generate_dev_plan(
            normalized_brd,
            task_markdown,
            architecture_markdown,
            dev_plan_markdown,
            code_standards_markdown,
            review_standards_markdown,
        )

    settings = load_dev_llm_settings()
    client = llm_client or LiteLLMClient(
        model_name=settings.model_name,
        api_key=settings.api_key,
        base_url=settings.base_url,
    )
    agent = DevAgent(
        llm_client=client,
        prompt_path=settings.prompt_path,
        review_prompt_path=load_dev_review_prompt_path(),
        review_iterations=load_dev_review_iterations(),
        temperature=settings.temperature,
    )

    if mode == "llm":
        return agent.generate(
            normalized_brd,
            task_markdown,
            architecture_markdown,
            dev_plan_markdown,
            code_standards_markdown,
            review_standards_markdown,
        )

    # hybrid
    try:
        return agent.generate(
            normalized_brd,
            task_markdown,
            architecture_markdown,
            dev_plan_markdown,
            code_standards_markdown,
            review_standards_markdown,
        )
    except Exception:
        return deterministic_generate_dev_plan(
            normalized_brd,
            task_markdown,
            architecture_markdown,
            dev_plan_markdown,
        )
