from typer.testing import CliRunner

from brd_agent.main import app
from brd_agent.services.artifact_writer import (
    render_code_standards_markdown,
    render_review_standards_markdown,
    write_standards_artifacts,
)

runner = CliRunner()


def test_render_default_standards_content():
    code_md = render_code_standards_markdown()
    review_md = render_review_standards_markdown()

    assert "Code Standards" in code_md
    assert "Security Baseline" in code_md
    assert "Review Standards" in review_md
    assert "Severity Levels" in review_md


def test_write_standards_artifacts(tmp_path):
    code_md = render_code_standards_markdown()
    review_md = render_review_standards_markdown()

    paths = write_standards_artifacts(code_md, review_md, tmp_path)

    assert paths["code_standards"].exists()
    assert paths["review_standards"].exists()


def test_generate_standards_cli(tmp_path):
    result = runner.invoke(
        app,
        [
            "generate-standards",
            "--output-dir",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0
    assert (tmp_path / "code_standards.md").exists()
    assert (tmp_path / "review_standards.md").exists()
