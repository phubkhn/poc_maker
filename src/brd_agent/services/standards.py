"""Default standards used by Dev and review stages."""


def default_code_standards_context():
    return {
        "sections": [
            {
                "title": "Project Structure",
                "items": [
                    "Keep feature logic inside service modules under src/brd_agent/services.",
                    "Keep schemas under src/brd_agent/schemas and avoid mixing transport/data concerns.",
                    "Keep templates and prompts versioned and explicit.",
                ],
            },
            {
                "title": "Naming Conventions",
                "items": [
                    "Use snake_case for functions and variables.",
                    "Use PascalCase for classes and Pydantic models.",
                    "Use explicit, domain-readable names; avoid short ambiguous aliases.",
                ],
            },
            {
                "title": "Error Handling",
                "items": [
                    "Raise stage-specific exceptions with actionable messages.",
                    "Fail fast on missing artifacts and invalid schemas.",
                    "In hybrid mode, fallback to deterministic behavior where defined.",
                ],
            },
            {
                "title": "Logging and Traceability",
                "items": [
                    "Emit step-level trace logs in pipeline mode.",
                    "Preserve artifact lineage BRD -> BA -> SA -> Dev -> QA.",
                    "Include assumptions and open questions in stage outputs.",
                ],
            },
            {
                "title": "Testing",
                "items": [
                    "Add unit tests for each service and gate path.",
                    "Mock all LLM calls in tests; no network in test suite.",
                    "Maintain deterministic test fixtures and expected outputs.",
                ],
            },
            {
                "title": "Security Baseline",
                "items": [
                    "Never hardcode API keys or secrets.",
                    "Use environment variables for provider credentials.",
                    "Treat model output as untrusted input and validate with schema.",
                ],
            },
            {
                "title": "Performance Baseline",
                "items": [
                    "Keep stage execution synchronous and predictable.",
                    "Avoid unnecessary repeated reads/writes of large artifacts.",
                    "Prefer simple data transformations over heavy abstraction.",
                ],
            },
            {
                "title": "Documentation Baseline",
                "items": [
                    "Update README when adding commands, artifacts, or env variables.",
                    "Keep AGENTS.md aligned with current pipeline behavior.",
                    "Document intentional non-goals to avoid hidden scope creep.",
                ],
            },
        ]
    }


def default_review_standards_context():
    return {
        "severity_levels": [
            "Blocker: violates scope contract or breaks pipeline execution.",
            "Critical: major requirement missing or unsafe behavior likely.",
            "Major: important detail missing; output likely rework-heavy.",
            "Minor: clarity/style issue; does not block delivery.",
        ],
        "stage_checklists": [
            {
                "stage": "BA",
                "checks": [
                    "Every in-scope requirement maps to epic/task coverage.",
                    "Dependencies/risks/open questions are explicit.",
                    "Tasks are actionable and testable.",
                ],
            },
            {
                "stage": "SA",
                "checks": [
                    "Architecture components map to BA scope.",
                    "Data flow and integration points are explicit.",
                    "Dev plan phases and module order are implementable.",
                ],
            },
            {
                "stage": "Dev",
                "checks": [
                    "Code artifacts align with SA modules and interfaces.",
                    "Snippets follow project coding standards.",
                    "Verification steps are concrete and runnable.",
                ],
            },
            {
                "stage": "QA",
                "checks": [
                    "Test cases trace to BRD/BA/SA/Dev outputs.",
                    "Functional + non-functional scenarios are covered.",
                    "Exit criteria are objective and measurable.",
                ],
            },
        ],
        "definition_of_done": [
            "Output conforms to schema/template contract.",
            "Consistency gate passes for current stage.",
            "Open questions and assumptions are explicitly listed.",
        ],
    }
