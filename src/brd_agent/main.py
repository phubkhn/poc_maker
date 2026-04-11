"""CLI entrypoint for the BRD agent scaffold."""

from pathlib import Path

import typer

from brd_agent.config import (
    DEFAULT_ARCHITECTURE_NAME,
    DEFAULT_ARTIFACT_DIR,
    DEFAULT_BRD_NORMALIZED_NAME,
    DEFAULT_CODE_STANDARDS_NAME,
    DEFAULT_DEV_PLAN_NAME,
    DEFAULT_GENERATED_CODE_NAME,
    DEFAULT_REVIEW_STANDARDS_NAME,
    DEFAULT_TASK_NAME,
)
from brd_agent.services.artifact_writer import (
    render_ba_task_markdown,
    render_code_standards_markdown,
    render_dev_code_markdown,
    render_qa_test_cases_markdown,
    render_qa_test_plan_markdown,
    render_review_standards_markdown,
    render_sa_architecture_markdown,
    render_sa_dev_plan_markdown,
    write_ba_artifacts,
    write_brd_artifacts,
    write_dev_artifacts,
    write_qa_artifacts,
    write_sa_artifacts,
    write_standards_artifacts,
)
from brd_agent.services.ba_agent import BAAgentError, generate_ba_plan, load_normalized_brd
from brd_agent.services.brd_analyzer import BRDAnalysisError, normalize_brd
from brd_agent.services.brd_loader import load_brd
from brd_agent.services.consistency_gate import (
    check_ba_consistency,
    check_dev_consistency,
    check_qa_consistency,
    check_sa_consistency,
)
from brd_agent.services.dev_agent import DevAgentError, generate_dev_plan, load_dev_inputs
from brd_agent.services.orchestrator import OrchestrationError, PipelineOrchestrator
from brd_agent.services.qa_agent import QAAgentError, generate_qa_plan, load_qa_inputs
from brd_agent.services.sa_agent import SAAgentError, generate_sa_artifacts, load_sa_inputs

app = typer.Typer(help="BRD agent CLI.")


@app.command("generate-standards")
def generate_standards(
    output_dir: str = typer.Option(
        str(DEFAULT_ARTIFACT_DIR),
        "--output-dir",
        help="Directory where standards artifacts will be written.",
    ),
):
    """Generate default code and review standards artifacts."""
    code_md = render_code_standards_markdown()
    review_md = render_review_standards_markdown()
    paths = write_standards_artifacts(code_md, review_md, output_dir)

    typer.echo("Standards generation completed.")
    typer.echo("Artifacts written to: {0}".format(Path(output_dir).resolve()))
    typer.echo("- {0}".format(paths["code_standards"].name))
    typer.echo("- {0}".format(paths["review_standards"].name))


@app.command("read-brd")
def read_brd(
    input: str = typer.Option(..., "--input", help="Path to BRD markdown file."),
    output_dir: str = typer.Option(
        str(DEFAULT_ARTIFACT_DIR),
        "--output-dir",
        help="Directory where BRD artifacts will be written.",
    ),
):
    """Read BRD, normalize it by configured mode, and write artifacts."""
    try:
        brd_document = load_brd(input)
        normalized_brd = normalize_brd(brd_document)
        paths = write_brd_artifacts(normalized_brd, output_dir)
    except (FileNotFoundError, BRDAnalysisError, ValueError) as error:
        typer.echo("BRD processing failed: {0}".format(error), err=True)
        raise typer.Exit(code=1)

    typer.echo("BRD processed: {0}".format(brd_document.title))
    typer.echo("Artifacts written to: {0}".format(Path(output_dir).resolve()))
    typer.echo("- {0}".format(paths["brd_normalized"].name))
    typer.echo("- {0}".format(paths["context"].name))
    typer.echo("- {0}".format(paths["gaps"].name))


@app.command("generate-ba")
def generate_ba(
    input: str = typer.Option(
        str(DEFAULT_ARTIFACT_DIR / DEFAULT_BRD_NORMALIZED_NAME),
        "--input",
        help="Path to normalized BRD JSON artifact.",
    ),
    output_dir: str = typer.Option(
        str(DEFAULT_ARTIFACT_DIR),
        "--output-dir",
        help="Directory where BA artifacts will be written.",
    ),
):
    """Generate BA task breakdown markdown from normalized BRD."""
    try:
        normalized_brd = load_normalized_brd(input)
        ba_plan = generate_ba_plan(normalized_brd)
        ba_consistency = check_ba_consistency(normalized_brd, ba_plan)
        if not ba_consistency["ok"]:
            raise BAAgentError(
                "BA consistency gate failed: {0}".format(
                    "; ".join(ba_consistency["issues"])
                )
            )
        task_markdown = render_ba_task_markdown(ba_plan)
        paths = write_ba_artifacts(task_markdown, output_dir)
    except (FileNotFoundError, BAAgentError, ValueError) as error:
        typer.echo("BA generation failed: {0}".format(error), err=True)
        raise typer.Exit(code=1)

    typer.echo("BA task generation completed.")
    for warning in ba_consistency["warnings"]:
        typer.echo("BA warning: {0}".format(warning))
    typer.echo("Artifacts written to: {0}".format(Path(output_dir).resolve()))
    typer.echo("- {0}".format(paths["task"].name))


@app.command("generate-sa")
def generate_sa(
    brd: str = typer.Option(
        str(DEFAULT_ARTIFACT_DIR / DEFAULT_BRD_NORMALIZED_NAME),
        "--brd",
        help="Path to normalized BRD JSON artifact.",
    ),
    tasks: str = typer.Option(
        str(DEFAULT_ARTIFACT_DIR / DEFAULT_TASK_NAME),
        "--tasks",
        help="Path to BA task markdown artifact.",
    ),
    output_dir: str = typer.Option(
        str(DEFAULT_ARTIFACT_DIR),
        "--output-dir",
        help="Directory where SA artifacts will be written.",
    ),
):
    """Generate architecture and development plan markdown artifacts."""
    try:
        normalized_brd, task_markdown = load_sa_inputs(brd, tasks)
        architecture_plan, dev_plan = generate_sa_artifacts(
            normalized_brd,
            task_markdown,
        )
        sa_consistency = check_sa_consistency(
            normalized_brd,
            task_markdown,
            architecture_plan,
            dev_plan,
        )
        if not sa_consistency["ok"]:
            raise SAAgentError(
                "SA consistency gate failed: {0}".format(
                    "; ".join(sa_consistency["issues"])
                )
            )
        architecture_md = render_sa_architecture_markdown(architecture_plan)
        dev_plan_md = render_sa_dev_plan_markdown(dev_plan)
        paths = write_sa_artifacts(architecture_md, dev_plan_md, output_dir)
    except (FileNotFoundError, SAAgentError, ValueError) as error:
        typer.echo("SA generation failed: {0}".format(error), err=True)
        raise typer.Exit(code=1)

    typer.echo("SA generation completed.")
    for warning in sa_consistency["warnings"]:
        typer.echo("SA warning: {0}".format(warning))
    typer.echo("Artifacts written to: {0}".format(Path(output_dir).resolve()))
    typer.echo("- {0}".format(paths["architecture"].name))
    typer.echo("- {0}".format(paths["dev_plan"].name))


@app.command("generate-dev")
def generate_dev(
    brd: str = typer.Option(
        str(DEFAULT_ARTIFACT_DIR / DEFAULT_BRD_NORMALIZED_NAME),
        "--brd",
        help="Path to normalized BRD JSON artifact.",
    ),
    tasks: str = typer.Option(
        str(DEFAULT_ARTIFACT_DIR / DEFAULT_TASK_NAME),
        "--tasks",
        help="Path to BA task markdown artifact.",
    ),
    architecture: str = typer.Option(
        str(DEFAULT_ARTIFACT_DIR / DEFAULT_ARCHITECTURE_NAME),
        "--architecture",
        help="Path to SA architecture markdown artifact.",
    ),
    dev_plan: str = typer.Option(
        str(DEFAULT_ARTIFACT_DIR / DEFAULT_DEV_PLAN_NAME),
        "--dev-plan",
        help="Path to SA dev plan markdown artifact.",
    ),
    code_standards: str = typer.Option(
        str(DEFAULT_ARTIFACT_DIR / DEFAULT_CODE_STANDARDS_NAME),
        "--code-standards",
        help="Path to code standards artifact. If missing, defaults are used.",
    ),
    review_standards: str = typer.Option(
        str(DEFAULT_ARTIFACT_DIR / DEFAULT_REVIEW_STANDARDS_NAME),
        "--review-standards",
        help="Path to review standards artifact. If missing, defaults are used.",
    ),
    output_dir: str = typer.Option(
        str(DEFAULT_ARTIFACT_DIR),
        "--output-dir",
        help="Directory where Dev artifacts will be written.",
    ),
):
    """Generate Dev implementation code artifact markdown."""
    try:
        (
            normalized_brd,
            task_markdown,
            architecture_markdown,
            dev_plan_markdown,
            code_standards_markdown,
            review_standards_markdown,
        ) = load_dev_inputs(
            brd,
            tasks,
            architecture,
            dev_plan,
            code_standards if Path(code_standards).exists() else None,
            review_standards if Path(review_standards).exists() else None,
        )
        dev_output = generate_dev_plan(
            normalized_brd,
            task_markdown,
            architecture_markdown,
            dev_plan_markdown,
            code_standards_markdown,
            review_standards_markdown,
        )
        dev_consistency = check_dev_consistency(
            normalized_brd,
            task_markdown,
            architecture_markdown,
            dev_output,
        )
        if not dev_consistency["ok"]:
            raise DevAgentError(
                "Dev consistency gate failed: {0}".format(
                    "; ".join(dev_consistency["issues"])
                )
            )
        generated_code_md = render_dev_code_markdown(dev_output)
        paths = write_dev_artifacts(generated_code_md, output_dir)
    except (FileNotFoundError, DevAgentError, ValueError) as error:
        typer.echo("Dev generation failed: {0}".format(error), err=True)
        raise typer.Exit(code=1)

    typer.echo("Dev generation completed.")
    for warning in dev_consistency["warnings"]:
        typer.echo("Dev warning: {0}".format(warning))
    typer.echo("Artifacts written to: {0}".format(Path(output_dir).resolve()))
    typer.echo("- {0}".format(paths["generated_code"].name))


@app.command("generate-qa")
def generate_qa(
    brd: str = typer.Option(
        str(DEFAULT_ARTIFACT_DIR / DEFAULT_BRD_NORMALIZED_NAME),
        "--brd",
        help="Path to normalized BRD JSON artifact.",
    ),
    tasks: str = typer.Option(
        str(DEFAULT_ARTIFACT_DIR / DEFAULT_TASK_NAME),
        "--tasks",
        help="Path to BA task markdown artifact.",
    ),
    architecture: str = typer.Option(
        str(DEFAULT_ARTIFACT_DIR / DEFAULT_ARCHITECTURE_NAME),
        "--architecture",
        help="Path to SA architecture markdown artifact.",
    ),
    dev_plan: str = typer.Option(
        str(DEFAULT_ARTIFACT_DIR / DEFAULT_DEV_PLAN_NAME),
        "--dev-plan",
        help="Path to SA dev plan markdown artifact.",
    ),
    generated_code: str = typer.Option(
        str(DEFAULT_ARTIFACT_DIR / DEFAULT_GENERATED_CODE_NAME),
        "--generated-code",
        help="Path to generated code markdown artifact.",
    ),
    output_dir: str = typer.Option(
        str(DEFAULT_ARTIFACT_DIR),
        "--output-dir",
        help="Directory where QA artifacts will be written.",
    ),
):
    """Generate QA test strategy and test cases markdown artifacts."""
    try:
        (
            normalized_brd,
            task_markdown,
            architecture_markdown,
            dev_plan_markdown,
            generated_code_markdown,
        ) = load_qa_inputs(
            brd,
            tasks,
            architecture,
            dev_plan,
            generated_code,
        )
        qa_plan = generate_qa_plan(
            normalized_brd,
            task_markdown,
            architecture_markdown,
            dev_plan_markdown,
            generated_code_markdown,
        )
        qa_consistency = check_qa_consistency(normalized_brd, qa_plan)
        if not qa_consistency["ok"]:
            raise QAAgentError(
                "QA consistency gate failed: {0}".format(
                    "; ".join(qa_consistency["issues"])
                )
            )
        qa_test_plan_md = render_qa_test_plan_markdown(qa_plan)
        qa_test_cases_md = render_qa_test_cases_markdown(qa_plan)
        paths = write_qa_artifacts(qa_test_plan_md, qa_test_cases_md, output_dir)
    except (FileNotFoundError, QAAgentError, ValueError) as error:
        typer.echo("QA generation failed: {0}".format(error), err=True)
        raise typer.Exit(code=1)

    typer.echo("QA generation completed.")
    for warning in qa_consistency["warnings"]:
        typer.echo("QA warning: {0}".format(warning))
    typer.echo("Artifacts written to: {0}".format(Path(output_dir).resolve()))
    typer.echo("- {0}".format(paths["qa_test_plan"].name))
    typer.echo("- {0}".format(paths["qa_test_cases"].name))


@app.command("run-pipeline")
def run_pipeline(
    input: str = typer.Option(..., "--input", help="Path to BRD markdown file."),
    output_dir: str = typer.Option(
        str(DEFAULT_ARTIFACT_DIR),
        "--output-dir",
        help="Directory where all artifacts will be written.",
    ),
    trace: bool = typer.Option(
        True,
        "--trace/--no-trace",
        help="Print per-step trace logs and timings.",
    ),
):
    """Run end-to-end BRD -> BA -> SA -> Dev -> QA pipeline."""
    try:
        orchestrator = PipelineOrchestrator()
        result = orchestrator.run(input, output_dir, trace=trace)
    except OrchestrationError as error:
        typer.echo("Pipeline failed: {0}".format(error), err=True)
        raise typer.Exit(code=1)

    typer.echo("Pipeline completed successfully.")
    for stage in ("ba", "sa", "dev", "qa"):
        for warning in result["warnings"][stage]:
            typer.echo("{0} warning: {1}".format(stage.upper(), warning))
    typer.echo("Artifacts written to: {0}".format(Path(output_dir).resolve()))


if __name__ == "__main__":
    app()
