import os

from typer.testing import CliRunner

from brd_agent.main import app

runner = CliRunner()


def test_run_pipeline_happy_path(tmp_path):
    os.environ["BRD_ANALYZER_MODE"] = "llm"
    os.environ["BA_AGENT_MODE"] = "llm"
    os.environ["SA_AGENT_MODE"] = "llm"

    def fake_complete(self, system_prompt, user_prompt, temperature=0.0):
        lower_prompt = system_prompt.lower()
        if "business analyst generating" in lower_prompt or "strict ba reviewer" in lower_prompt:
            return (
                '{"project_summary":"Generated summary",'
                '"scope_summary":"Generated scope",'
                '"epics":[{"name":"Epic A","objective":"Obj","summary":"Summary","out_of_scope_notes":[],"tasks":[{"title":"Task 1","description":"Do task","module_hint":"Core","dependency_notes":[],"risk_notes":[],"open_questions":[],"acceptance_criteria":["Done"]}]}],'
                '"implementation_notes":[],"cross_epic_dependencies":[],"dependencies":[],"risks":[],"assumptions":[],"open_questions":[]}'
            )
        if "development plan" in lower_prompt or "development planning" in lower_prompt:
            return (
                '{"implementation_strategy":"Plan output",'
                '"development_phases":["Phase 1"],'
                '"deliverables_by_phase":[],"module_breakdown":["Module A"],'
                '"implementation_order":["Step 1"],'
                '"risks_and_dependencies":[],"testing_considerations":[],"rollout_and_release_notes":[],"clarification_items":[]}'
            )
        if "solution architect creating" in lower_prompt or "solution architecture reviewer" in lower_prompt:
            return (
                '{"system_overview":"Architecture output",'
                '"goals_and_constraints":["Goal A"],'
                '"high_level_architecture":"Layered",'
                '"architecture_decisions":[],"components":[{"name":"Module A","responsibility":"Does A","interfaces":[]}],'
                '"data_flow":["Flow A"],'
                '"integration_points":[],"external_integrations":[],"data_storage_considerations":[],"security_considerations":[],"observability_considerations":[],"non_functional_considerations":[],'
                '"risks_and_tradeoffs":[],"open_questions":[]}'
            )
        return (
            '{"project_name":"Customer Support Ticket Prioritization",'
            '"business_goal":"Improve response time","problem_statement":"Inconsistent prioritization",'
            '"in_scope":["Intake tickets"],"open_questions":["Who owns SLA policy?"]}'
        )

    from brd_agent.llm.client import LiteLLMClient

    original_complete = LiteLLMClient.complete
    LiteLLMClient.complete = fake_complete

    try:
        result = runner.invoke(
            app,
            [
                "run-pipeline",
                "--input",
                "input/sample_brd.md",
                "--output-dir",
                str(tmp_path),
            ],
        )
    finally:
        LiteLLMClient.complete = original_complete

    assert result.exit_code == 0
    assert (tmp_path / "brd_normalized.json").exists()
    assert (tmp_path / "task.md").exists()
    assert (tmp_path / "architecture.md").exists()
    assert (tmp_path / "dev_plan.md").exists()
