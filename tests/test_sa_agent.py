import json
import os

from typer.testing import CliRunner

from brd_agent.main import app
from brd_agent.schemas.brd import NormalizedBRD
from brd_agent.schemas.sa import SAArchitecturePlan, SADevelopmentPlan
from brd_agent.services.artifact_writer import write_sa_artifacts
from brd_agent.services.sa_agent import SAAgent, generate_sa_artifacts, load_sa_inputs

runner = CliRunner()


class FakeLLMClient(object):
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def complete(self, system_prompt, user_prompt, temperature=0.0):
        self.calls += 1
        return self.responses.pop(0)


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


def test_sa_agent_input_handling(tmp_path):
    brd_path = tmp_path / "brd_normalized.json"
    task_path = tmp_path / "task.md"
    brd_path.write_text(json.dumps(_normalized_payload()), encoding="utf-8")
    task_path.write_text("# Project Task Breakdown\n\n## Epics\n- Epic 1", encoding="utf-8")

    normalized_brd, task_markdown = load_sa_inputs(brd_path, task_path)

    assert isinstance(normalized_brd, NormalizedBRD)
    assert "Project Task Breakdown" in task_markdown


def test_mocked_generation_of_architecture_and_dev_plan():
    os.environ["SA_AGENT_MODE"] = "llm"
    llm = FakeLLMClient(
        [
            (
                '{"system_overview":"Architecture output",'
                '"goals_and_constraints":["Goal A"],'
                '"high_level_architecture":"Layered",'
                '"architecture_decisions":[],"components":[{"name":"Module A","responsibility":"Does A","interfaces":[]}],'
                '"data_flow":["Flow A"],'
                '"integration_points":[],"external_integrations":[],"data_storage_considerations":[],"security_considerations":[],"observability_considerations":[],"non_functional_considerations":[],'
                '"risks_and_tradeoffs":[],"open_questions":[]}'
            ),
            (
                '{"implementation_strategy":"Plan output",'
                '"development_phases":["Phase 1"],'
                '"deliverables_by_phase":[],"module_breakdown":["Module A"],'
                '"implementation_order":["Step 1"],'
                '"risks_and_dependencies":[],"testing_considerations":[],"rollout_and_release_notes":[],"clarification_items":[]}'
            ),
            (
                '{"system_overview":"Architecture output",'
                '"goals_and_constraints":["Goal A"],'
                '"high_level_architecture":"Layered",'
                '"architecture_decisions":[],"components":[{"name":"Module A","responsibility":"Does A","interfaces":[]}],'
                '"data_flow":["Flow A"],'
                '"integration_points":[],"external_integrations":[],"data_storage_considerations":[],"security_considerations":[],"observability_considerations":[],"non_functional_considerations":[],'
                '"risks_and_tradeoffs":[],"open_questions":[]}'
            ),
            (
                '{"implementation_strategy":"Plan output",'
                '"development_phases":["Phase 1"],'
                '"module_breakdown":["Module A"],'
                '"deliverables_by_phase":[],'
                '"implementation_order":["Step 1"],'
                '"risks_and_dependencies":[],"testing_considerations":[],"rollout_and_release_notes":[],"clarification_items":[]}'
            ),
        ]
    )
    agent = SAAgent(
        llm_client=llm,
        architecture_prompt_path="prompts/sa_architecture_prompt.md",
        dev_plan_prompt_path="prompts/sa_dev_plan_prompt.md",
        architecture_review_prompt_path="prompts/sa_architecture_review_prompt.md",
        dev_plan_review_prompt_path="prompts/sa_dev_plan_review_prompt.md",
        temperature=0.2,
    )
    architecture_plan, dev_plan = agent.generate(
        NormalizedBRD.parse_obj(_normalized_payload()),
        "# Project Task Breakdown\n\n## Epics\n- Epic 1",
    )

    assert llm.calls == 4
    assert isinstance(architecture_plan, SAArchitecturePlan)
    assert isinstance(dev_plan, SADevelopmentPlan)


def test_sa_artifact_file_creation(tmp_path):
    paths = write_sa_artifacts(
        "# Architecture Plan\n\nA",
        "# Development Plan\n\nB",
        tmp_path,
    )

    assert paths["architecture"].exists()
    assert paths["dev_plan"].exists()


def test_cli_happy_path_generate_sa(tmp_path):
    os.environ["SA_AGENT_MODE"] = "llm"
    brd_path = tmp_path / "brd_normalized.json"
    task_path = tmp_path / "task.md"
    brd_path.write_text(json.dumps(_normalized_payload()), encoding="utf-8")
    task_path.write_text("# Project Task Breakdown\n\n## Epics\n- Epic 1", encoding="utf-8")

    def fake_complete(self, system_prompt, user_prompt, temperature=0.0):
        if "development plan" in system_prompt.lower():
            return (
                '{"implementation_strategy":"Plan output",'
                '"development_phases":["Phase 1"],'
                '"deliverables_by_phase":[],"module_breakdown":["Module A"],'
                '"implementation_order":["Step 1"],'
                '"risks_and_dependencies":[],"testing_considerations":[],"rollout_and_release_notes":[],"clarification_items":[]}'
            )
        return (
            '{"system_overview":"Architecture output",'
            '"goals_and_constraints":["Goal A"],'
            '"high_level_architecture":"Layered",'
            '"architecture_decisions":[],"components":[{"name":"Module A","responsibility":"Does A","interfaces":[]}],'
            '"data_flow":["Flow A"],'
            '"integration_points":[],"external_integrations":[],"data_storage_considerations":[],"security_considerations":[],"observability_considerations":[],"non_functional_considerations":[],'
            '"risks_and_tradeoffs":[],"open_questions":[]}'
        )

    from brd_agent.services import sa_agent

    original = sa_agent.LiteLLMClient.complete
    sa_agent.LiteLLMClient.complete = fake_complete

    try:
        result = runner.invoke(
            app,
            [
                "generate-sa",
                "--brd",
                str(brd_path),
                "--tasks",
                str(task_path),
                "--output-dir",
                str(tmp_path),
            ],
        )
    finally:
        sa_agent.LiteLLMClient.complete = original

    assert result.exit_code == 0
    assert (tmp_path / "architecture.md").exists()
    assert (tmp_path / "dev_plan.md").exists()


def test_sa_hybrid_fallback_to_deterministic():
    os.environ["SA_AGENT_MODE"] = "hybrid"
    architecture, dev_plan = generate_sa_artifacts(
        NormalizedBRD.parse_obj(_normalized_payload()),
        "# Project Task Breakdown\n\n## Epics\n- Epic 1",
        llm_client=FakeLLMClient(["bad-json", "bad-json", "bad-json", "bad-json"]),
    )
    assert isinstance(architecture, SAArchitecturePlan)
    assert isinstance(dev_plan, SADevelopmentPlan)
