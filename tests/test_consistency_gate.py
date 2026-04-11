from brd_agent.schemas.ba import BAPlan
from brd_agent.schemas.brd import NormalizedBRD
from brd_agent.schemas.sa import SAArchitecturePlan, SAComponent, SADevelopmentPlan
from brd_agent.services.consistency_gate import check_ba_consistency, check_sa_consistency


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
