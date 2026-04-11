import json
import os

from typer.testing import CliRunner

from brd_agent.main import app
from brd_agent.schemas.ba import BAPlan
from brd_agent.schemas.brd import NormalizedBRD
from brd_agent.services.artifact_writer import render_ba_task_markdown, write_ba_artifacts
from brd_agent.services.ba_agent import BAAgent, generate_ba_plan, load_normalized_brd

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


def test_ba_agent_input_loading(tmp_path):
    input_path = tmp_path / "brd_normalized.json"
    input_path.write_text(json.dumps(_normalized_payload()), encoding="utf-8")

    normalized = load_normalized_brd(input_path)

    assert isinstance(normalized, NormalizedBRD)
    assert normalized.project_name == "Customer Support Ticket Prioritization"


def test_ba_agent_output_generation_with_mocked_llm():
    os.environ["BA_AGENT_MODE"] = "llm"
    valid_json = (
        '{"project_summary":"Generated summary",'
        '"scope_summary":"Generated scope",'
        '"epics":[{"name":"Epic A","objective":"Obj","summary":"Summary","out_of_scope_notes":[],"tasks":[{"title":"Task 1","description":"Do task","module_hint":"Core","dependency_notes":[],"risk_notes":[],"open_questions":[],"acceptance_criteria":["Done"]}]}],'
        '"implementation_notes":[],"cross_epic_dependencies":[],"dependencies":[],"risks":[],"assumptions":[],"open_questions":[]}'
    )
    llm = FakeLLMClient([valid_json, valid_json])
    agent = BAAgent(
        llm_client=llm,
        prompt_path="prompts/ba_task_prompt.md",
        review_prompt_path="prompts/ba_review_prompt.md",
        temperature=0.2,
    )
    plan = agent.generate_plan(NormalizedBRD.parse_obj(_normalized_payload()))

    assert llm.calls == 2
    assert isinstance(plan, BAPlan)
    assert plan.epics[0].name == "Epic A"


def test_task_markdown_file_creation(tmp_path):
    plan = BAPlan(project_summary="Summary", scope_summary="Scope", epics=[])
    task_content = render_ba_task_markdown(plan)
    paths = write_ba_artifacts(task_content, tmp_path)

    assert paths["task"].exists()
    assert "Project Task Breakdown" in paths["task"].read_text(encoding="utf-8")


def test_cli_happy_path_generate_ba(tmp_path):
    os.environ["BA_AGENT_MODE"] = "llm"
    input_path = tmp_path / "brd_normalized.json"
    input_path.write_text(json.dumps(_normalized_payload()), encoding="utf-8")

    def fake_complete(self, system_prompt, user_prompt, temperature=0.0):
        return (
            '{"project_summary":"Generated summary",'
            '"scope_summary":"Generated scope",'
            '"epics":[{"name":"Epic A","objective":"Obj","summary":"Summary","out_of_scope_notes":[],"tasks":[{"title":"Task 1","description":"Do task","module_hint":"Core","dependency_notes":[],"risk_notes":[],"open_questions":[],"acceptance_criteria":["Done"]}]}],'
            '"implementation_notes":[],"cross_epic_dependencies":[],"dependencies":[],"risks":[],"assumptions":[],"open_questions":[]}'
        )

    from brd_agent.services import ba_agent

    original = ba_agent.LiteLLMClient.complete
    ba_agent.LiteLLMClient.complete = fake_complete

    try:
        result = runner.invoke(
            app,
            [
                "generate-ba",
                "--input",
                str(input_path),
                "--output-dir",
                str(tmp_path),
            ],
        )
    finally:
        ba_agent.LiteLLMClient.complete = original

    assert result.exit_code == 0
    assert (tmp_path / "task.md").exists()


def test_ba_hybrid_fallback_to_deterministic():
    os.environ["BA_AGENT_MODE"] = "hybrid"
    plan = generate_ba_plan(
        NormalizedBRD.parse_obj(_normalized_payload()),
        llm_client=FakeLLMClient(["bad-json", "still-bad"]),
    )
    assert isinstance(plan, BAPlan)
    assert len(plan.epics) > 0
