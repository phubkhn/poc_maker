"""Pipeline orchestration across BRD, BA, SA, Dev, and QA stages."""

import time
from pathlib import Path

from brd_agent.config import (
    DEFAULT_ARCHITECTURE_NAME,
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
from brd_agent.services.qa_agent import QAAgentError, generate_qa_plan, load_qa_inputs
from brd_agent.services.sa_agent import SAAgentError, generate_sa_artifacts, load_sa_inputs


class OrchestrationError(Exception):
    """Raised when the orchestration pipeline fails."""


def _run_step(step_name, trace_enabled, func):
    start = time.perf_counter()
    if trace_enabled:
        print("[trace] {0}: start".format(step_name))
    result = func()
    if trace_enabled:
        duration = time.perf_counter() - start
        print("[trace] {0}: done in {1:.2f}s".format(step_name, duration))
    return result


class PipelineOrchestrator(object):
    """Run sequential multi-agent pipeline with per-step review and gates."""

    def run(self, input_path, output_dir, trace=True):
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        try:
            brd_document = _run_step("load_brd", trace, lambda: load_brd(input_path))
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
            standards_code_md = _run_step(
                "render_code_standards",
                trace,
                render_code_standards_markdown,
            )
            standards_review_md = _run_step(
                "render_review_standards",
                trace,
                render_review_standards_markdown,
            )
            _run_step(
                "write_standards_artifacts",
                trace,
                lambda: write_standards_artifacts(
                    standards_code_md,
                    standards_review_md,
                    output_path,
                ),
            )

            normalized_brd_from_artifact = _run_step(
                "load_normalized_brd",
                trace,
                lambda: load_normalized_brd(output_path / DEFAULT_BRD_NORMALIZED_NAME),
            )
            ba_plan = _run_step(
                "generate_ba",
                trace,
                lambda: generate_ba_plan(normalized_brd_from_artifact),
            )
            ba_consistency = _run_step(
                "gate_ba",
                trace,
                lambda: check_ba_consistency(normalized_brd_from_artifact, ba_plan),
            )
            if not ba_consistency["ok"]:
                raise OrchestrationError(
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
                    output_path / DEFAULT_TASK_NAME,
                ),
            )
            architecture_plan, sa_dev_plan = _run_step(
                "generate_sa",
                trace,
                lambda: generate_sa_artifacts(
                    normalized_brd_for_sa,
                    task_markdown_for_sa,
                ),
            )
            sa_consistency = _run_step(
                "gate_sa",
                trace,
                lambda: check_sa_consistency(
                    normalized_brd_for_sa,
                    task_markdown_for_sa,
                    architecture_plan,
                    sa_dev_plan,
                ),
            )
            if not sa_consistency["ok"]:
                raise OrchestrationError(
                    "SA consistency gate failed: {0}".format(
                        "; ".join(sa_consistency["issues"])
                    )
                )
            architecture_md = _run_step(
                "render_architecture",
                trace,
                lambda: render_sa_architecture_markdown(architecture_plan),
            )
            sa_dev_plan_md = _run_step(
                "render_sa_dev_plan",
                trace,
                lambda: render_sa_dev_plan_markdown(sa_dev_plan),
            )
            _run_step(
                "write_sa_artifacts",
                trace,
                lambda: write_sa_artifacts(architecture_md, sa_dev_plan_md, output_path),
            )

            (
                normalized_brd_for_dev,
                task_markdown_for_dev,
                architecture_markdown_for_dev,
                dev_plan_markdown_for_dev,
                code_standards_markdown,
                review_standards_markdown,
            ) = _run_step(
                "load_dev_inputs",
                trace,
                lambda: load_dev_inputs(
                    output_path / DEFAULT_BRD_NORMALIZED_NAME,
                    output_path / DEFAULT_TASK_NAME,
                    output_path / DEFAULT_ARCHITECTURE_NAME,
                    output_path / DEFAULT_DEV_PLAN_NAME,
                    output_path / DEFAULT_CODE_STANDARDS_NAME,
                    output_path / DEFAULT_REVIEW_STANDARDS_NAME,
                ),
            )
            dev_plan = _run_step(
                "generate_dev",
                trace,
                lambda: generate_dev_plan(
                    normalized_brd_for_dev,
                    task_markdown_for_dev,
                    architecture_markdown_for_dev,
                    dev_plan_markdown_for_dev,
                    code_standards_markdown,
                    review_standards_markdown,
                ),
            )
            dev_consistency = _run_step(
                "gate_dev",
                trace,
                lambda: check_dev_consistency(
                    normalized_brd_for_dev,
                    task_markdown_for_dev,
                    architecture_markdown_for_dev,
                    dev_plan,
                ),
            )
            if not dev_consistency["ok"]:
                raise OrchestrationError(
                    "Dev consistency gate failed: {0}".format(
                        "; ".join(dev_consistency["issues"])
                    )
                )
            generated_code_md = _run_step(
                "render_generated_code",
                trace,
                lambda: render_dev_code_markdown(dev_plan),
            )
            _run_step(
                "write_dev_artifacts",
                trace,
                lambda: write_dev_artifacts(generated_code_md, output_path),
            )

            (
                normalized_brd_for_qa,
                task_markdown_for_qa,
                architecture_markdown_for_qa,
                dev_plan_markdown_for_qa,
                generated_code_markdown,
            ) = _run_step(
                "load_qa_inputs",
                trace,
                lambda: load_qa_inputs(
                    output_path / DEFAULT_BRD_NORMALIZED_NAME,
                    output_path / DEFAULT_TASK_NAME,
                    output_path / DEFAULT_ARCHITECTURE_NAME,
                    output_path / DEFAULT_DEV_PLAN_NAME,
                    output_path / DEFAULT_GENERATED_CODE_NAME,
                ),
            )
            qa_plan = _run_step(
                "generate_qa",
                trace,
                lambda: generate_qa_plan(
                    normalized_brd_for_qa,
                    task_markdown_for_qa,
                    architecture_markdown_for_qa,
                    dev_plan_markdown_for_qa,
                    generated_code_markdown,
                ),
            )
            qa_consistency = _run_step(
                "gate_qa",
                trace,
                lambda: check_qa_consistency(normalized_brd_for_qa, qa_plan),
            )
            if not qa_consistency["ok"]:
                raise OrchestrationError(
                    "QA consistency gate failed: {0}".format(
                        "; ".join(qa_consistency["issues"])
                    )
                )
            qa_test_plan_md = _run_step(
                "render_qa_test_plan",
                trace,
                lambda: render_qa_test_plan_markdown(qa_plan),
            )
            qa_test_cases_md = _run_step(
                "render_qa_test_cases",
                trace,
                lambda: render_qa_test_cases_markdown(qa_plan),
            )
            _run_step(
                "write_qa_artifacts",
                trace,
                lambda: write_qa_artifacts(qa_test_plan_md, qa_test_cases_md, output_path),
            )

            return {
                "output_dir": output_path,
                "warnings": {
                    "ba": ba_consistency["warnings"],
                    "sa": sa_consistency["warnings"],
                    "dev": dev_consistency["warnings"],
                    "qa": qa_consistency["warnings"],
                },
            }
        except (
            FileNotFoundError,
            BRDAnalysisError,
            BAAgentError,
            SAAgentError,
            DevAgentError,
            QAAgentError,
            ValueError,
        ) as error:
            raise OrchestrationError(str(error))
