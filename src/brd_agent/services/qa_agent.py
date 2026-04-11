"""QA/Test agent for quality strategy and test case generation."""

import json
from pathlib import Path

from pydantic import ValidationError

from brd_agent.config import (
    load_qa_agent_mode,
    load_qa_llm_settings,
    load_qa_review_iterations,
    load_qa_review_prompt_path,
)
from brd_agent.llm.client import LiteLLMClient
from brd_agent.schemas.brd import NormalizedBRD
from brd_agent.schemas.qa import QAPlan, QATestCase
from brd_agent.services.ba_agent import load_normalized_brd


class QAAgentError(Exception):
    """Raised when QA generation fails."""


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


def load_qa_inputs(
    brd_input_path,
    task_input_path,
    architecture_input_path,
    dev_plan_input_path,
    generated_code_input_path,
):
    """Load artifacts required by QA agent."""
    normalized_brd = load_normalized_brd(brd_input_path)

    artifact_paths = {
        "task": Path(task_input_path),
        "architecture": Path(architecture_input_path),
        "dev_plan": Path(dev_plan_input_path),
        "generated_code": Path(generated_code_input_path),
    }
    for name, artifact_path in artifact_paths.items():
        if not artifact_path.exists():
            raise FileNotFoundError(
                "Required artifact not found ({0}): {1}".format(name, artifact_path)
            )

    task_markdown = artifact_paths["task"].read_text(encoding="utf-8").strip()
    architecture_markdown = artifact_paths["architecture"].read_text(encoding="utf-8").strip()
    dev_plan_markdown = artifact_paths["dev_plan"].read_text(encoding="utf-8").strip()
    generated_code_markdown = artifact_paths["generated_code"].read_text(encoding="utf-8").strip()

    if not task_markdown:
        raise QAAgentError("BA task artifact is empty: {0}".format(artifact_paths["task"]))
    if not architecture_markdown:
        raise QAAgentError(
            "SA architecture artifact is empty: {0}".format(artifact_paths["architecture"])
        )
    if not dev_plan_markdown:
        raise QAAgentError("SA development plan artifact is empty: {0}".format(artifact_paths["dev_plan"]))
    if not generated_code_markdown:
        raise QAAgentError(
            "Dev generated code artifact is empty: {0}".format(artifact_paths["generated_code"])
        )

    return (
        normalized_brd,
        task_markdown,
        architecture_markdown,
        dev_plan_markdown,
        generated_code_markdown,
    )


class QAAgent(object):
    """LLM-backed QA/Test generation agent."""

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
        generated_code_markdown,
    ):
        system_prompt = self._load_prompt(self.prompt_path)
        user_prompt = self._build_user_prompt(
            normalized_brd,
            task_markdown,
            architecture_markdown,
            dev_plan_markdown,
            generated_code_markdown,
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
                raise QAAgentError(
                    "QA model returned invalid JSON after retry: {0}".format(second_error)
                )
        except ValidationError as validation_error:
            raise QAAgentError(
                "QA model returned JSON but schema validation failed: {0}".format(
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
        generated_code_markdown,
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
            "Dev generated code markdown:\n"
            "{4}\n\n"
            "Return ONLY valid JSON following this schema:\n"
            "{5}\n"
        ).format(
            normalized_brd.json(indent=2),
            task_markdown,
            architecture_markdown,
            dev_plan_markdown,
            generated_code_markdown,
            QAPlan.schema_json(indent=2),
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
        ).format(parse_error, QAPlan.schema_json(indent=2), user_prompt, invalid_output)

    @staticmethod
    def _parse_plan(raw_output):
        cleaned = _strip_json_code_fence(raw_output)
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as error:
            raise ValueError(str(error))
        return QAPlan.parse_obj(payload)

    def _load_prompt(self, prompt_path):
        if not prompt_path.exists():
            raise QAAgentError("Prompt file not found: {0}".format(prompt_path))
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
                    "Draft QA JSON:\n{1}\n\n"
                    "Rubric scores to improve:\n{2}\n\n"
                    "Return improved QA JSON only."
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
        if plan.strategy_summary:
            completeness += 20
        if plan.test_levels:
            completeness += 20
        if plan.functional_scenarios:
            completeness += 20
        if plan.test_cases:
            completeness += 20
        if plan.exit_criteria:
            completeness += 20

        implementability = min(
            100,
            len(plan.test_cases) * 15 + len(plan.automation_candidates) * 8,
        )
        testability = min(
            100,
            len(plan.functional_scenarios) * 12 + len(plan.non_functional_scenarios) * 10,
        )

        ambiguity_penalty = 0
        if not plan.open_questions and not plan.assumptions:
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


def deterministic_generate_qa_plan(
    normalized_brd,
    task_markdown,
    architecture_markdown,
    dev_plan_markdown,
    generated_code_markdown,
):
    """Deterministic QA plan used for deterministic and hybrid fallback modes."""
    functional_scenarios = []
    for item in normalized_brd.functional_requirements or normalized_brd.in_scope:
        functional_scenarios.append("Validate requirement: {0}".format(item))

    if not functional_scenarios:
        functional_scenarios = ["Validate baseline BRD-to-artifact flow output."]

    return QAPlan(
        strategy_summary=(
            "Use risk-based testing to validate core BRD-driven pipeline behavior and artifact quality."
        ),
        test_levels=["Unit", "Integration", "CLI end-to-end"],
        environments=["Local Python 3.9.6", "CI pipeline"],
        functional_scenarios=functional_scenarios,
        non_functional_scenarios=[
            "Validate deterministic fallback behavior when LLM output is invalid.",
            "Verify pipeline execution remains reproducible across runs.",
        ],
        test_cases=[
            QATestCase(
                test_id="QA-001",
                title="Run full pipeline with sample BRD",
                test_type="integration",
                preconditions=["Sample BRD exists in input folder."],
                steps=[
                    "Run python3 -m brd_agent.main run-pipeline --input input/sample_brd.md --output-dir artifacts",
                    "Inspect generated artifacts.",
                ],
                expected_results=[
                    "Pipeline exits with code 0.",
                    "All expected BRD/BA/SA/Dev/QA artifacts are present.",
                ],
                trace_to_requirements=[
                    "Pipeline orchestration",
                    "Artifact generation",
                ],
            )
        ],
        automation_candidates=[
            "CLI regression test for run-pipeline command.",
            "Schema validation contract tests for agent outputs.",
        ],
        quality_risks=list(normalized_brd.risks),
        assumptions=list(normalized_brd.assumptions),
        open_questions=list(normalized_brd.open_questions),
        exit_criteria=[
            "All unit and integration tests pass.",
            "No critical consistency gate failures.",
        ],
    )


def generate_qa_plan(
    normalized_brd,
    task_markdown,
    architecture_markdown,
    dev_plan_markdown,
    generated_code_markdown,
    llm_client=None,
):
    """Generate QA plan with configurable execution mode."""
    if not isinstance(normalized_brd, NormalizedBRD):
        raise QAAgentError("normalized_brd must be a NormalizedBRD instance.")

    mode = load_qa_agent_mode()
    if mode == "deterministic":
        return deterministic_generate_qa_plan(
            normalized_brd,
            task_markdown,
            architecture_markdown,
            dev_plan_markdown,
            generated_code_markdown,
        )

    settings = load_qa_llm_settings()
    client = llm_client or LiteLLMClient(
        model_name=settings.model_name,
        api_key=settings.api_key,
        base_url=settings.base_url,
    )
    agent = QAAgent(
        llm_client=client,
        prompt_path=settings.prompt_path,
        review_prompt_path=load_qa_review_prompt_path(),
        review_iterations=load_qa_review_iterations(),
        temperature=settings.temperature,
    )

    if mode == "llm":
        return agent.generate(
            normalized_brd,
            task_markdown,
            architecture_markdown,
            dev_plan_markdown,
            generated_code_markdown,
        )

    # hybrid
    try:
        return agent.generate(
            normalized_brd,
            task_markdown,
            architecture_markdown,
            dev_plan_markdown,
            generated_code_markdown,
        )
    except Exception:
        return deterministic_generate_qa_plan(
            normalized_brd,
            task_markdown,
            architecture_markdown,
            dev_plan_markdown,
            generated_code_markdown,
        )
