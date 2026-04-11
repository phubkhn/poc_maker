# AGENTS.md

## Purpose

Repository instructions for future Codex runs in this project.

## Scope Rules

- Keep implementation Python `>=3.9,<3.10`.
- Do not use Python 3.10+ syntax or features.
- Keep modules small, explicit, and testable.
- Prefer synchronous code unless async is explicitly requested.
- Avoid over-engineering and speculative abstractions.

## Architecture Direction (Step 1)

- This step is only a scaffold for a future BRD-to-engineering pipeline.
- Future roles (BA, SA, Dev, Test) are planned but not implemented yet.
- No multi-agent orchestration in current step.

## Development Workflow

1. Create a virtual environment and install dependencies with pip:
   - `pip3 install -e ".[dev]"`
2. Run tests:
   - `pytest`
3. Run CLI:
   - `python -m brd_agent.main read-brd --input input/sample_brd.md`

## Coding Conventions

- Keep service functions focused and single-purpose.
- Use Pydantic models for structured payloads.
- Keep side effects isolated in service modules.
- Add tests for new behavior before expanding orchestration.

## Directory Expectations

- `input/`: source BRD markdown files.
- `artifacts/`: generated JSON/markdown artifacts.
- `templates/`: future Jinja templates.
- `prompts/`: future role-specific prompt templates.
- `src/brd_agent/`: application source.
- `tests/`: unit tests.
