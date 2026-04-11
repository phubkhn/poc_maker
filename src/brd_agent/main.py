"""CLI entrypoint for the BRD agent scaffold."""

import time
from pathlib import Path

import typer

from brd_agent.config import DEFAULT_ARTIFACT_DIR, DEFAULT_BRD_NORMALIZED_NAME
from brd_agent.services.artifact_writer import (
    render_ba_task_markdown,
    render_sa_architecture_markdown,
    render_sa_dev_plan_markdown,
    write_ba_artifacts,
    write_brd_artifacts,
    write_sa_artifacts,
)
from brd_agent.services.ba_agent import BAAgentError, generate_ba_plan, load_normalized_brd
from brd_agent.services.brd_analyzer import BRDAnalysisError, normalize_brd
from brd_agent.services.brd_loader import load_brd
from brd_agent.services.consistency_gate import check_ba_consistency, check_sa_consistency
from brd_agent.services.sa_agent import SAAgentError, generate_sa_artifacts, load_sa_inputs

app = typer.Typer(help="BRD agent CLI.")


def _trace(message, enabled):
    if enabled:
        typer.echo("[trace] {0}".format(message))


def _run_step(step_name, enabled, func):
    start = time.perf_counter()
    _trace("{0}: start".format(step_name), enabled)
    result = func()
    duration = time.perf_counter() - start
    _trace("{0}: done in {1:.2f}s".format(step_name, duration), enabled)
    return result


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
        str(DEFAULT_ARTIFACT_DIR / "task.md"),
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
    """Run end-to-end BRD -> BA -> SA pipeline with traced execution."""
    output_path = Path(output_dir)
    try:
        brd_document = _run_step(
            "load_brd",
            trace,
            lambda: load_brd(input),
        )
        normalized_brd = _run_step(
            "normalize_brd",
            trace,
            lambda: normalize_brd(brd_document),
        )
        _run_step(
            "write_brd_artifacts",
            trace,
            lambda: write_brd_artifacts(normalized_brd, output_path),
        )

        normalized_brd_from_artifact = _run_step(
            "load_normalized_brd",
            trace,
            lambda: load_normalized_brd(output_path / DEFAULT_BRD_NORMALIZED_NAME),
        )
        ba_plan = _run_step(
            "generate_ba_plan",
            trace,
            lambda: generate_ba_plan(normalized_brd_from_artifact),
        )
        ba_consistency = _run_step(
            "check_ba_consistency",
            trace,
            lambda: check_ba_consistency(normalized_brd_from_artifact, ba_plan),
        )
        if not ba_consistency["ok"]:
            raise BAAgentError(
                "BA consistency gate failed: {0}".format(
                    "; ".join(ba_consistency["issues"])
                )
            )
        task_markdown = _run_step(
            "render_ba_task",
            trace,
            lambda: render_ba_task_markdown(ba_plan),
        )
        _run_step(
            "write_ba_artifacts",
            trace,
            lambda: write_ba_artifacts(task_markdown, output_path),
        )

        normalized_brd_for_sa, task_markdown_for_sa = _run_step(
            "load_sa_inputs",
            trace,
            lambda: load_sa_inputs(
                output_path / DEFAULT_BRD_NORMALIZED_NAME,
                output_path / "task.md",
            ),
        )
        architecture_plan, dev_plan = _run_step(
            "generate_sa_plans",
            trace,
            lambda: generate_sa_artifacts(
                normalized_brd_for_sa,
                task_markdown_for_sa,
            ),
        )
        sa_consistency = _run_step(
            "check_sa_consistency",
            trace,
            lambda: check_sa_consistency(
                normalized_brd_for_sa,
                task_markdown_for_sa,
                architecture_plan,
                dev_plan,
            ),
        )
        if not sa_consistency["ok"]:
            raise SAAgentError(
                "SA consistency gate failed: {0}".format(
                    "; ".join(sa_consistency["issues"])
                )
            )
        architecture_md = _run_step(
            "render_architecture",
            trace,
            lambda: render_sa_architecture_markdown(architecture_plan),
        )
        dev_plan_md = _run_step(
            "render_dev_plan",
            trace,
            lambda: render_sa_dev_plan_markdown(dev_plan),
        )
        _run_step(
            "write_sa_artifacts",
            trace,
            lambda: write_sa_artifacts(architecture_md, dev_plan_md, output_path),
        )
    except (FileNotFoundError, BRDAnalysisError, BAAgentError, SAAgentError, ValueError) as error:
        typer.echo("Pipeline failed: {0}".format(error), err=True)
        raise typer.Exit(code=1)

    typer.echo("Pipeline completed successfully.")
    for warning in ba_consistency["warnings"]:
        typer.echo("BA warning: {0}".format(warning))
    for warning in sa_consistency["warnings"]:
        typer.echo("SA warning: {0}".format(warning))
    typer.echo("Artifacts written to: {0}".format(output_path.resolve()))


if __name__ == "__main__":
    app()
