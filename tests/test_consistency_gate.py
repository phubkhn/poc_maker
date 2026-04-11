from brd_agent.schemas.ba import BAPlan
from brd_agent.schemas.brd import NormalizedBRD
from brd_agent.schemas.dev import DevCodeArtifact, DevPlan
from brd_agent.schemas.qa import QAPlan
from brd_agent.schemas.sa import SAArchitecturePlan, SAComponent, SADevelopmentPlan
from brd_agent.services.consistency_gate import (
    check_ba_consistency,
    check_dev_consistency,
    check_qa_consistency,
    check_sa_consistency,
)


def test_ba_consistency_detects_missing_tasks():
    brd = NormalizedBRD(project_name="A", in_scope=["Feature A"])
    ba_plan = BAPlan(project_summary="Summary", scope_summary="Scope", epics=[])

    report = check_ba_consistency(brd, ba_plan)

    assert report["ok"] is False
    assert len(report["issues"]) > 0


def test_sa_consistency_happy_path():
    brd = NormalizedBRD(project_name="A")
    architecture = SAArchitecturePlan(
        system_overview="Overview",
        components=[
            SAComponent(name="Component A", responsibility="Do A", interfaces=[])
        ],
    )
    dev_plan = SADevelopmentPlan(
        development_phases=["Phase 1"],
        module_breakdown=["Module A"],
    )
    report = check_sa_consistency(brd, "# Project Task Breakdown\n## Epics", architecture, dev_plan)

    assert report["ok"] is True


def test_dev_consistency_happy_path():
    brd = NormalizedBRD(project_name="A")
    dev_plan = DevPlan(
        module_plan=["Module A"],
        code_artifacts=[
            DevCodeArtifact(
                file_path="src/a.py",
                language="python",
                purpose="Example",
                code_snippet="def run():\n    return True",
            )
        ],
        verification_steps=["pytest"],
    )
    report = check_dev_consistency(
        brd,
        "# Project Task Breakdown\n## Epics",
        "# Architecture Plan\n## Main Components",
        dev_plan,
    )
    assert report["ok"] is True


def test_qa_consistency_detects_missing_test_cases():
    brd = NormalizedBRD(project_name="A", functional_requirements=["FR-1"])
    qa_plan = QAPlan(
        strategy_summary="Summary",
        test_levels=["Unit"],
        exit_criteria=["All tests pass"],
        test_cases=[],
    )
    report = check_qa_consistency(brd, qa_plan)
    assert report["ok"] is False
