# AGENTS.md

## Purpose

Repository instructions for future Codex runs in this project.

## Scope Rules

- Keep implementation Python `>=3.9,<3.10`.
- Do not use Python 3.10+ syntax or features.
- Keep modules small, explicit, and testable.
- Prefer synchronous code unless async is explicitly requested.
- Avoid over-engineering and speculative abstractions.

## Current Architecture

- Artifact-driven multi-stage pipeline:
  - BRD -> BA -> SA -> Dev -> QA
- Default standards artifacts:
  - `artifacts/code_standards.md`
  - `artifacts/review_standards.md`
- Each stage has:
  - mode `deterministic | llm | hybrid`
  - one review/enhance pass by default (`*_REVIEW_ITERATIONS=1`)
  - consistency gate before moving to next stage.
- Orchestration entrypoint:
  - `python3 -m brd_agent.main run-pipeline --input input/sample_brd.md --output-dir artifacts`

## Development Workflow

1. Create venv + install dependencies:
   - `python3 -m venv .venv`
   - `source .venv/bin/activate`
   - `pip3 install -e ".[dev]"`
2. Run tests:
   - `pytest -q`
3. Run commands per stage (when debugging):
   - `read-brd`
   - `generate-ba`
   - `generate-sa`
   - `generate-dev`
   - `generate-qa`

## Coding Conventions

- Keep service functions focused and single-purpose.
- Use Pydantic models for structured payloads.
- Keep side effects isolated in service modules.
- Add deterministic fallback for LLM stages where practical.
- New stage must include:
  - schema
  - prompt
  - writer/template (if markdown artifact)
  - consistency gate
  - tests

## Directory Expectations

- `input/`: source BRD markdown files.
- `artifacts/`: generated artifacts.
- `prompts/`: role-specific generation/review prompts.
- `src/brd_agent/schemas`: stage contracts.
- `src/brd_agent/services`: stage logic + orchestration.
- `src/brd_agent/templates`: markdown rendering templates.
- `tests/`: unit/CLI pipeline tests.
