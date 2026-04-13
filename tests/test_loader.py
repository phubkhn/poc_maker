from pathlib import Path

import pytest
from typer.testing import CliRunner

from brd_agent.main import app
from brd_agent.services.artifact_writer import write_brd_artifacts
from brd_agent.services.brd_loader import load_brd

runner = CliRunner()


def test_loader_success():
    sample_path = Path("input/sample_brd.md")
    document = load_brd(sample_path)

    assert isinstance(document.title, str)
    assert document.title.strip() != ""
    assert len(document.raw_markdown.strip()) > 0


def test_loader_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_brd("input/does_not_exist.md")


def test_artifact_writer_creates_files(tmp_path):
    normalized = {
        "project_name": "Customer Support Ticket Prioritization",
        "business_goal": "Improve response time.",
        "problem_statement": "Priorities are inconsistent.",
        "in_scope": ["Intake tickets", "Assign priority levels"],
        "out_of_scope": [],
        "actors": [],
        "features": [],
        "functional_requirements": [],
        "non_functional_requirements": [],
        "inputs": [],
        "outputs": [],
        "constraints": [],
        "assumptions": [],
        "dependencies": [],
        "risks": [],
        "acceptance_criteria": [],
        "open_questions": [],
    }
    from brd_agent.schemas.brd import NormalizedBRD

    normalized_model = NormalizedBRD.parse_obj(normalized)
    paths = write_brd_artifacts(normalized_model, tmp_path)

    normalized_path = paths["brd_normalized"]
    context_path = paths["context"]
    gaps_path = paths["gaps"]

    assert normalized_path.exists()
    assert context_path.exists()
    assert gaps_path.exists()
    assert "project_name" in normalized_path.read_text(encoding="utf-8")
    assert "BRD Context Summary" in context_path.read_text(encoding="utf-8")
    assert "BRD Gap Report" in gaps_path.read_text(encoding="utf-8")


def test_cli_happy_path(tmp_path):
    def fake_complete(self, system_prompt, user_prompt, temperature=0.0):
        return (
            '{"project_name":"Customer Support Ticket Prioritization",'
            '"business_goal":"Improve response time","problem_statement":"Inconsistent prioritization",'
            '"in_scope":["Intake tickets"],"open_questions":["Who owns SLA policy?"]}'
        )

    from brd_agent.services import brd_analyzer

    original = brd_analyzer.LiteLLMClient.complete
    brd_analyzer.LiteLLMClient.complete = fake_complete

    try:
        result = runner.invoke(
            app,
            [
                "read-brd",
                "--input",
                "input/sample_brd.md",
                "--output-dir",
                str(tmp_path),
            ],
        )
    finally:
        brd_analyzer.LiteLLMClient.complete = original

    assert result.exit_code == 0
    assert (tmp_path / "brd_normalized.json").exists()
    assert (tmp_path / "context.md").exists()
    assert (tmp_path / "brd_gaps.md").exists()
