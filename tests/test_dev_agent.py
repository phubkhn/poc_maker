import json
import os

from typer.testing import CliRunner

from brd_agent.main import app
from brd_agent.schemas.brd import NormalizedBRD
from brd_agent.schemas.dev import DevPlan
from brd_agent.services.artifact_writer import render_dev_code_markdown, write_dev_artifacts
from brd_agent.services.dev_agent import DevAgent, generate_dev_plan, load_dev_inputs

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


def _dev_json():
    return (
        '{"implementation_summary":"Build core modules",'
        '"setup_steps":["Create venv"],'
        '"module_plan":["Build loader"],'
        '"code_artifacts":[{"file_path":"src/example.py","language":"python","purpose":"Example","code_snippet":"def run():\\n    return True"}],'
        '"verification_steps":["pytest"],'
        '"risks":[],"assumptions":[],"open_questions":[]}'
    )


def test_dev_agent_input_handling(tmp_path):
    brd_path = tmp_path / "brd_normalized.json"
    task_path = tmp_path / "task.md"
    architecture_path = tmp_path / "architecture.md"
    dev_plan_path = tmp_path / "dev_plan.md"

    brd_path.write_text(json.dumps(_normalized_payload()), encoding="utf-8")
    task_path.write_text("# Project Task Breakdown\n\n## Epics\n- Epic 1", encoding="utf-8")
    architecture_path.write_text("# Architecture Plan\n\n## Main Components", encoding="utf-8")
    dev_plan_path.write_text("# Development Plan\n\n## Work Breakdown", encoding="utf-8")

    (
        normalized_brd,
        task_markdown,
        architecture_markdown,
        sa_dev_plan_markdown,
        code_standards_markdown,
        review_standards_markdown,
    ) = load_dev_inputs(
        brd_path,
        task_path,
        architecture_path,
        dev_plan_path,
    )

    assert isinstance(normalized_brd, NormalizedBRD)
    assert "Project Task Breakdown" in task_markdown
    assert "Architecture Plan" in architecture_markdown
    assert "Development Plan" in sa_dev_plan_markdown
    assert "Code Standards" in code_standards_markdown
    assert "Review Standards" in review_standards_markdown


def test_dev_agent_output_generation_with_mocked_llm():
    os.environ["DEV_AGENT_MODE"] = "llm"
    llm = FakeLLMClient([_dev_json(), _dev_json()])
    agent = DevAgent(
        llm_client=llm,
        prompt_path="prompts/dev_code_prompt.md",
        review_prompt_path="prompts/dev_review_prompt.md",
        temperature=0.2,
    )

    plan = agent.generate(
        NormalizedBRD.parse_obj(_normalized_payload()),
        "# BA",
        "# Architecture",
        "# Dev plan",
        "# Code Standards",
        "# Review Standards",
    )

    assert llm.calls == 2
    assert isinstance(plan, DevPlan)
    assert plan.code_artifacts[0].file_path == "src/example.py"


def test_generated_code_file_creation(tmp_path):
    plan = DevPlan(implementation_summary="Summary")
    content = render_dev_code_markdown(plan)
    paths = write_dev_artifacts(content, tmp_path)

    assert paths["generated_code"].exists()
    assert "Generated Code Plan" in paths["generated_code"].read_text(encoding="utf-8")


def test_cli_happy_path_generate_dev(tmp_path):
    os.environ["DEV_AGENT_MODE"] = "llm"
    brd_path = tmp_path / "brd_normalized.json"
    task_path = tmp_path / "task.md"
    architecture_path = tmp_path / "architecture.md"
    dev_plan_path = tmp_path / "dev_plan.md"

    brd_path.write_text(json.dumps(_normalized_payload()), encoding="utf-8")
    task_path.write_text("# Project Task Breakdown\n\n## Epics\n- Epic 1", encoding="utf-8")
    architecture_path.write_text("# Architecture Plan\n\n## Main Components", encoding="utf-8")
    dev_plan_path.write_text("# Development Plan\n\n## Work Breakdown", encoding="utf-8")

    def fake_complete(self, system_prompt, user_prompt, temperature=0.0):
        return _dev_json()

    from brd_agent.services import dev_agent

    original = dev_agent.LiteLLMClient.complete
    dev_agent.LiteLLMClient.complete = fake_complete
    try:
        result = runner.invoke(
            app,
            [
                "generate-dev",
                "--brd",
                str(brd_path),
                "--tasks",
                str(task_path),
                "--architecture",
                str(architecture_path),
                "--dev-plan",
                str(dev_plan_path),
                "--output-dir",
                str(tmp_path),
            ],
        )
    finally:
        dev_agent.LiteLLMClient.complete = original

    assert result.exit_code == 0
    assert (tmp_path / "generated_code.md").exists()


def test_dev_hybrid_fallback_to_deterministic():
    os.environ["DEV_AGENT_MODE"] = "hybrid"
    plan = generate_dev_plan(
        NormalizedBRD.parse_obj(_normalized_payload()),
        "# BA",
        "# Architecture",
        "# Dev plan",
        "# Code Standards",
        "# Review Standards",
        llm_client=FakeLLMClient(["bad-json", "still-bad"]),
    )
    assert isinstance(plan, DevPlan)
    assert len(plan.code_artifacts) > 0
