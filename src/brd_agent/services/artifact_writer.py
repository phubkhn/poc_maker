"""Write generated artifacts to disk."""

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from brd_agent.config import (
    DEFAULT_ACCEPTANCE_NAME,
    DEFAULT_ARCHITECTURE_NAME,
    DEFAULT_BRD_NORMALIZED_NAME,
    DEFAULT_CODE_STANDARDS_NAME,
    DEFAULT_CONTEXT_NAME,
    DEFAULT_DEV_PLAN_NAME,
    DEFAULT_GAPS_NAME,
    DEFAULT_GENERATED_CODE_NAME,
    DEFAULT_QA_TEST_CASES_NAME,
    DEFAULT_QA_TEST_PLAN_NAME,
    DEFAULT_REVIEW_STANDARDS_NAME,
    DEFAULT_TASK_NAME,
)
from brd_agent.schemas.ba import BAPlan
from brd_agent.schemas.dev import DevPlan
from brd_agent.schemas.qa import QAPlan
from brd_agent.schemas.sa import SAArchitecturePlan, SADevelopmentPlan
from brd_agent.services.standards import (
    default_code_standards_context,
    default_review_standards_context,
)


def write_json_artifact(data, output_path):
    """Persist dictionary-like data as indented JSON."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def write_markdown_artifact(content, output_path):
    """Persist markdown content to disk."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _template_environment():
    template_dir = Path(__file__).resolve().parent.parent / "templates"
    return Environment(loader=FileSystemLoader(str(template_dir)), autoescape=False)


def _render_template(template_name, context):
    env = _template_environment()
    template = env.get_template(template_name)
    return template.render(**context)


def _missing_information(normalized):
    missing = []
    if (not normalized.problem_statement) or normalized.problem_statement.startswith(
        "Problem statement not explicitly provided"
    ):
        missing.append("Problem statement")
    if not normalized.actors:
        missing.append("Actors")
    if not normalized.non_functional_requirements:
        missing.append("Non-functional requirements")
    if not normalized.inputs:
        missing.append("Inputs")
    if not normalized.dependencies:
        missing.append("Dependencies")
    return missing


def _unclear_requirements(normalized):
    ambiguous = []
    if not normalized.functional_requirements:
        ambiguous.append("Functional requirements are not explicitly defined.")
    if normalized.in_scope and not normalized.out_of_scope:
        ambiguous.append("In-scope exists, but out-of-scope boundaries are missing.")
    return ambiguous


def write_brd_artifacts(normalized_brd, output_dir):
    """Write normalized JSON, context markdown, and BRD gaps markdown."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    normalized_json_path = write_json_artifact(
        normalized_brd.dict(),
        output_path / DEFAULT_BRD_NORMALIZED_NAME,
    )

    context_markdown = _render_template(
        "context.md.j2",
        {"brd": normalized_brd},
    )
    context_path = output_path / DEFAULT_CONTEXT_NAME
    context_path.write_text(context_markdown, encoding="utf-8")

    gaps_markdown = _render_template(
        "brd_gaps.md.j2",
        {
            "missing_information": _missing_information(normalized_brd),
            "unclear_requirements": _unclear_requirements(normalized_brd),
            "assumptions": normalized_brd.assumptions,
            "open_questions": normalized_brd.open_questions,
        },
    )
    gaps_path = output_path / DEFAULT_GAPS_NAME
    gaps_path.write_text(gaps_markdown, encoding="utf-8")

    return {
        "brd_normalized": normalized_json_path,
        "context": context_path,
        "gaps": gaps_path,
    }


def write_ba_artifacts(task_markdown, output_dir, acceptance_markdown=None):
    """Write BA artifacts (task.md and optional acceptance_criteria.md)."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    task_path = write_markdown_artifact(task_markdown, output_path / DEFAULT_TASK_NAME)
    paths = {"task": task_path}

    if acceptance_markdown:
        acceptance_path = write_markdown_artifact(
            acceptance_markdown, output_path / DEFAULT_ACCEPTANCE_NAME
        )
        paths["acceptance_criteria"] = acceptance_path

    return paths


def render_ba_task_markdown(ba_plan):
    """Render task markdown from BAPlan object."""
    if not isinstance(ba_plan, BAPlan):
        raise TypeError("ba_plan must be a BAPlan instance.")
    return _render_template("task.md.j2", {"plan": ba_plan})


def render_sa_architecture_markdown(sa_architecture):
    """Render architecture markdown from SAArchitecturePlan object."""
    if not isinstance(sa_architecture, SAArchitecturePlan):
        raise TypeError("sa_architecture must be a SAArchitecturePlan instance.")
    return _render_template("architecture.md.j2", {"plan": sa_architecture})


def render_sa_dev_plan_markdown(sa_dev_plan):
    """Render development plan markdown from SADevelopmentPlan object."""
    if not isinstance(sa_dev_plan, SADevelopmentPlan):
        raise TypeError("sa_dev_plan must be a SADevelopmentPlan instance.")
    return _render_template("dev_plan.md.j2", {"plan": sa_dev_plan})


def write_sa_artifacts(architecture_markdown, dev_plan_markdown, output_dir):
    """Write SA artifacts (architecture.md and dev_plan.md)."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    architecture_path = write_markdown_artifact(
        architecture_markdown,
        output_path / DEFAULT_ARCHITECTURE_NAME,
    )
    dev_plan_path = write_markdown_artifact(
        dev_plan_markdown,
        output_path / DEFAULT_DEV_PLAN_NAME,
    )
    return {
        "architecture": architecture_path,
        "dev_plan": dev_plan_path,
    }


def render_dev_code_markdown(dev_plan):
    """Render generated code markdown from DevPlan object."""
    if not isinstance(dev_plan, DevPlan):
        raise TypeError("dev_plan must be a DevPlan instance.")
    return _render_template("generated_code.md.j2", {"plan": dev_plan})


def write_dev_artifacts(generated_code_markdown, output_dir):
    """Write Dev artifacts."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    generated_code_path = write_markdown_artifact(
        generated_code_markdown,
        output_path / DEFAULT_GENERATED_CODE_NAME,
    )
    return {"generated_code": generated_code_path}


def render_qa_test_plan_markdown(qa_plan):
    """Render QA test strategy markdown from QAPlan object."""
    if not isinstance(qa_plan, QAPlan):
        raise TypeError("qa_plan must be a QAPlan instance.")
    return _render_template("qa_test_plan.md.j2", {"plan": qa_plan})


def render_qa_test_cases_markdown(qa_plan):
    """Render QA test cases markdown from QAPlan object."""
    if not isinstance(qa_plan, QAPlan):
        raise TypeError("qa_plan must be a QAPlan instance.")
    return _render_template("qa_test_cases.md.j2", {"plan": qa_plan})


def write_qa_artifacts(test_plan_markdown, test_cases_markdown, output_dir):
    """Write QA artifacts."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    test_plan_path = write_markdown_artifact(
        test_plan_markdown,
        output_path / DEFAULT_QA_TEST_PLAN_NAME,
    )
    test_cases_path = write_markdown_artifact(
        test_cases_markdown,
        output_path / DEFAULT_QA_TEST_CASES_NAME,
    )
    return {
        "qa_test_plan": test_plan_path,
        "qa_test_cases": test_cases_path,
    }


def render_code_standards_markdown():
    """Render default code standards markdown."""
    return _render_template(
        "code_standards.md.j2",
        default_code_standards_context(),
    )


def render_review_standards_markdown():
    """Render default review standards markdown."""
    return _render_template(
        "review_standards.md.j2",
        default_review_standards_context(),
    )


def write_standards_artifacts(code_standards_markdown, review_standards_markdown, output_dir):
    """Write standards artifacts used by Dev and review stages."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    code_standards_path = write_markdown_artifact(
        code_standards_markdown,
        output_path / DEFAULT_CODE_STANDARDS_NAME,
    )
    review_standards_path = write_markdown_artifact(
        review_standards_markdown,
        output_path / DEFAULT_REVIEW_STANDARDS_NAME,
    )
    return {
        "code_standards": code_standards_path,
        "review_standards": review_standards_path,
    }
    DEFAULT_CODE_STANDARDS_NAME,
