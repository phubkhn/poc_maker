import json
import os

from typer.testing import CliRunner

from brd_agent.main import app
from brd_agent.schemas.brd import NormalizedBRD
from brd_agent.schemas.qa import QAPlan
from brd_agent.services.artifact_writer import (
    render_qa_test_cases_markdown,
    render_qa_test_plan_markdown,
    write_qa_artifacts,
)
from brd_agent.services.qa_agent import QAAgent, generate_qa_plan, load_qa_inputs

runner = CliRunner()


class FakeLLMClient(object):
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def complete(self, system_prompt, user_prompt, temperature=0.0):
        self.calls += 1
        if self.responses:
            return self.responses.pop(0)
        return "{}"


def _normalized_payload():
    return {
        "project_name": "Customer Support Ticket Prioritization",
        "business_goal": "Improve response time and consistency.",
        "problem_statement": "Ticket prioritization is inconsistent.",
        "in_scope": ["Prioritize tickets", "Route to resolver groups"],
        "out_of_scope": [],
        "actors": ["Support Lead", "Agent"],
        "features": ["Priority assignment"],
        "functional_requirements": ["Assign High/Medium/Low priority"],
        "non_functional_requirements": [],
        "inputs": ["Support ticket"],
        "outputs": ["Prioritized ticket"],
        "constraints": ["Manual override must remain"],
        "assumptions": [],
        "dependencies": [],
        "risks": [],
        "acceptance_criteria": ["95% SLA compliance"],
        "open_questions": ["Who approves rule changes?"],
    }


def _qa_json():
    return (
        '{"strategy_summary":"Risk-based testing",'
        '"test_levels":["Unit","Integration"],'
        '"environments":["Local"],'
        '"functional_scenarios":["Validate prioritization"],'
        '"non_functional_scenarios":["Latency"],'
        '"test_cases":[{"test_id":"QA-001","title":"Happy path","test_type":"integration","preconditions":["Data exists"],"steps":["Run flow"],"expected_results":["Success"],"trace_to_requirements":["FR-1"]}],'
        '"automation_candidates":["CLI smoke"],'
        '"quality_risks":[],"assumptions":[],"open_questions":[],"exit_criteria":["All pass"]}'
    )


def test_qa_agent_input_handling(tmp_path):
    brd_path = tmp_path / "brd_normalized.json"
    task_path = tmp_path / "task.md"
    architecture_path = tmp_path / "architecture.md"
    dev_plan_path = tmp_path / "dev_plan.md"
    generated_code_path = tmp_path / "generated_code.md"

    brd_path.write_text(json.dumps(_normalized_payload()), encoding="utf-8")
    task_path.write_text("# Project Task Breakdown\n\n## Epics\n- Epic 1", encoding="utf-8")
    architecture_path.write_text("# Architecture Plan\n\n## Main Components", encoding="utf-8")
    dev_plan_path.write_text("# Development Plan\n\n## Work Breakdown", encoding="utf-8")
    generated_code_path.write_text("# Generated Code Plan", encoding="utf-8")

    result = load_qa_inputs(
        brd_path,
        task_path,
        architecture_path,
        dev_plan_path,
        generated_code_path,
    )

    assert isinstance(result[0], NormalizedBRD)
    assert "Project Task Breakdown" in result[1]


def test_qa_agent_output_generation_with_mocked_llm():
    os.environ["QA_AGENT_MODE"] = "llm"
    llm = FakeLLMClient([_qa_json(), _qa_json()])
    agent = QAAgent(
        llm_client=llm,
        prompt_path="prompts/qa_test_plan_prompt.md",
        review_prompt_path="prompts/qa_review_prompt.md",
        temperature=0.2,
    )

    plan = agent.generate(
        NormalizedBRD.parse_obj(_normalized_payload()),
        "# BA",
        "# Architecture",
        "# Dev plan",
        "# Generated code",
    )

    assert llm.calls == 2
    assert isinstance(plan, QAPlan)
    assert plan.test_cases[0].test_id == "QA-001"


def test_qa_artifact_file_creation(tmp_path):
    plan = QAPlan(strategy_summary="Summary")
    test_plan_content = render_qa_test_plan_markdown(plan)
    test_cases_content = render_qa_test_cases_markdown(plan)
    paths = write_qa_artifacts(test_plan_content, test_cases_content, tmp_path)

    assert paths["qa_test_plan"].exists()
    assert paths["qa_test_cases"].exists()


def test_cli_happy_path_generate_qa(tmp_path):
    os.environ["QA_AGENT_MODE"] = "llm"
    brd_path = tmp_path / "brd_normalized.json"
    task_path = tmp_path / "task.md"
    architecture_path = tmp_path / "architecture.md"
    dev_plan_path = tmp_path / "dev_plan.md"
    generated_code_path = tmp_path / "generated_code.md"

    brd_path.write_text(json.dumps(_normalized_payload()), encoding="utf-8")
    task_path.write_text("# Project Task Breakdown\n\n## Epics\n- Epic 1", encoding="utf-8")
    architecture_path.write_text("# Architecture Plan\n\n## Main Components", encoding="utf-8")
    dev_plan_path.write_text("# Development Plan\n\n## Work Breakdown", encoding="utf-8")
    generated_code_path.write_text("# Generated Code Plan", encoding="utf-8")

    def fake_complete(self, system_prompt, user_prompt, temperature=0.0):
        return _qa_json()

    from brd_agent.services import qa_agent

    original = qa_agent.LiteLLMClient.complete
    qa_agent.LiteLLMClient.complete = fake_complete
    try:
        result = runner.invoke(
            app,
            [
                "generate-qa",
                "--brd",
                str(brd_path),
                "--tasks",
                str(task_path),
                "--architecture",
                str(architecture_path),
                "--dev-plan",
                str(dev_plan_path),
                "--generated-code",
                str(generated_code_path),
                "--output-dir",
                str(tmp_path),
            ],
        )
    finally:
        qa_agent.LiteLLMClient.complete = original

    assert result.exit_code == 0
    assert (tmp_path / "qa_test_plan.md").exists()
    assert (tmp_path / "qa_test_cases.md").exists()


def test_qa_hybrid_fallback_to_deterministic():
    os.environ["QA_AGENT_MODE"] = "hybrid"
    plan = generate_qa_plan(
        NormalizedBRD.parse_obj(_normalized_payload()),
        "# BA",
        "# Architecture",
        "# Dev plan",
        "# Generated code",
        llm_client=FakeLLMClient(["bad-json", "still-bad"]),
    )
    assert isinstance(plan, QAPlan)
    assert len(plan.test_cases) > 0
