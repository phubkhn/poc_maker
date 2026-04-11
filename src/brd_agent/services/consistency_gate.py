"""Cross-artifact consistency checks for BRD, BA, SA, Dev, and QA outputs."""


def check_ba_consistency(normalized_brd, ba_plan):
    """Validate BA plan coverage against normalized BRD."""
    issues = []
    warnings = []

    if not ba_plan.epics:
        issues.append("BA plan has no epics.")
    else:
        total_tasks = 0
        for epic in ba_plan.epics:
            total_tasks += len(epic.tasks)
        if total_tasks == 0:
            issues.append("BA plan has no tasks across epics.")

    if normalized_brd.in_scope and not ba_plan.scope_summary:
        warnings.append("Scope summary is empty while BRD has in-scope items.")

    if normalized_brd.open_questions and not ba_plan.open_questions:
        warnings.append("BA plan does not carry forward BRD open questions.")

    return {
        "ok": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
    }


def check_sa_consistency(normalized_brd, task_markdown, architecture_plan, dev_plan):
    """Validate SA artifacts against BRD and BA task context."""
    issues = []
    warnings = []

    if not architecture_plan.components:
        issues.append("Architecture plan has no components.")
    if not dev_plan.development_phases:
        issues.append("Development plan has no development phases.")
    if not dev_plan.module_breakdown:
        issues.append("Development plan has no module breakdown.")

    if normalized_brd.non_functional_requirements and not architecture_plan.non_functional_considerations:
        warnings.append("NFRs exist in BRD but SA NFR considerations are empty.")

    if "## Epics" in task_markdown and not dev_plan.implementation_order:
        warnings.append("BA tasks exist but implementation order is empty.")

    return {
        "ok": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
    }


def check_dev_consistency(normalized_brd, task_markdown, architecture_markdown, dev_plan):
    """Validate Dev artifacts against BRD/BA/SA context."""
    issues = []
    warnings = []

    if not dev_plan.module_plan:
        issues.append("Dev plan has no module plan.")
    if not dev_plan.code_artifacts:
        issues.append("Dev plan has no code artifacts.")
    if not dev_plan.verification_steps:
        issues.append("Dev plan has no verification steps.")

    if normalized_brd.open_questions and not dev_plan.open_questions:
        warnings.append("Dev plan does not carry BRD open questions.")
    if "## Main Components" in architecture_markdown and len(dev_plan.module_plan) < 2:
        warnings.append("Architecture defines components but module plan is sparse.")
    if "## Epics" in task_markdown and len(dev_plan.code_artifacts) < 1:
        warnings.append("BA epics exist but no code artifact proposal found.")

    return {
        "ok": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
    }


def check_qa_consistency(normalized_brd, qa_plan):
    """Validate QA artifacts against BRD context."""
    issues = []
    warnings = []

    if not qa_plan.test_levels:
        issues.append("QA plan has no test levels.")
    if not qa_plan.test_cases:
        issues.append("QA plan has no test cases.")
    if not qa_plan.exit_criteria:
        issues.append("QA plan has no exit criteria.")

    if normalized_brd.functional_requirements and not qa_plan.functional_scenarios:
        warnings.append("BRD has functional requirements but QA functional scenarios are empty.")
    if normalized_brd.non_functional_requirements and not qa_plan.non_functional_scenarios:
        warnings.append("BRD has non-functional requirements but QA non-functional scenarios are empty.")

    return {
        "ok": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
    }
