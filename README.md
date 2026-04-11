# BRD Agent Pipeline

Artifact-driven pipeline for `BRD -> BA -> SA -> Dev -> QA`, with one auto review/enhance pass at each stage before moving to the next stage.

## Current Capabilities

- BRD ingestion and normalization.
- BA agent generates `task.md`.
- SA agent generates `architecture.md` and `dev_plan.md`.
- Dev agent generates `generated_code.md`.
- QA agent generates `qa_test_plan.md` and `qa_test_cases.md`.
- Default standards artifacts:
  - `code_standards.md`
  - `review_standards.md`
- Multi-agent orchestration via `run-pipeline`.
- Consistency gates for BA/SA/Dev/QA outputs.

## Environment Requirements

- Python `>=3.9,<3.10` (target: `3.9.6`)
- `pip3`

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip3 install --upgrade pip
pip3 install -e ".[dev]"
```

## Configuration

```bash
cp .env.example .env
```

The app reads configuration from shell environment variables.

```bash
export OPENAI_API_KEY=your_key_here

export BRD_ANALYZER_MODE=hybrid
export BA_AGENT_MODE=hybrid
export SA_AGENT_MODE=hybrid
export DEV_AGENT_MODE=hybrid
export QA_AGENT_MODE=hybrid

export BA_REVIEW_ITERATIONS=1
export SA_REVIEW_ITERATIONS=1
export DEV_REVIEW_ITERATIONS=1
export QA_REVIEW_ITERATIONS=1
```

## Run Commands

### BRD Stage

```bash
python3 -m brd_agent.main read-brd --input input/sample_brd.md --output-dir artifacts
```

Produces:
- `artifacts/brd_normalized.json`
- `artifacts/context.md`
- `artifacts/brd_gaps.md`

### Standards Stage

```bash
python3 -m brd_agent.main generate-standards --output-dir artifacts
```

Produces:
- `artifacts/code_standards.md`
- `artifacts/review_standards.md`

### BA Stage

```bash
python3 -m brd_agent.main generate-ba --input artifacts/brd_normalized.json --output-dir artifacts
```

Produces:
- `artifacts/task.md`

### SA Stage

```bash
python3 -m brd_agent.main generate-sa --brd artifacts/brd_normalized.json --tasks artifacts/task.md --output-dir artifacts
```

Produces:
- `artifacts/architecture.md`
- `artifacts/dev_plan.md`

### Dev Stage

```bash
python3 -m brd_agent.main generate-dev \
  --brd artifacts/brd_normalized.json \
  --tasks artifacts/task.md \
  --architecture artifacts/architecture.md \
  --dev-plan artifacts/dev_plan.md \
  --code-standards artifacts/code_standards.md \
  --review-standards artifacts/review_standards.md \
  --output-dir artifacts
```

Produces:
- `artifacts/generated_code.md`

Note:
- If standards files are not provided or missing, Dev uses built-in default standards.

### QA Stage

```bash
python3 -m brd_agent.main generate-qa \
  --brd artifacts/brd_normalized.json \
  --tasks artifacts/task.md \
  --architecture artifacts/architecture.md \
  --dev-plan artifacts/dev_plan.md \
  --generated-code artifacts/generated_code.md \
  --output-dir artifacts
```

Produces:
- `artifacts/qa_test_plan.md`
- `artifacts/qa_test_cases.md`

## Run Full Pipeline

```bash
python3 -m brd_agent.main run-pipeline --input input/sample_brd.md --output-dir artifacts
```

Internal sequence:
1. BRD normalize
2. Generate standards
3. BA generate + review + gate
4. SA generate + review + gate
5. Dev generate + review + gate
6. QA generate + review + gate

## Run Tests

```bash
pytest -q
```

Current status:
- `38 passed`

## Main Structure

```text
src/brd_agent/
  main.py
  config.py
  llm/client.py
  schemas/
    brd.py
    ba.py
    sa.py
    dev.py
    qa.py
  services/
    brd_loader.py
    brd_analyzer.py
    ba_agent.py
    sa_agent.py
    dev_agent.py
    qa_agent.py
    orchestrator.py
    standards.py
    consistency_gate.py
    artifact_writer.py
  templates/
    context.md.j2
    brd_gaps.md.j2
    task.md.j2
    architecture.md.j2
    dev_plan.md.j2
    generated_code.md.j2
    qa_test_plan.md.j2
    qa_test_cases.md.j2
    code_standards.md.j2
    review_standards.md.j2

prompts/
  brd_extraction_prompt.md
  ba_task_prompt.md
  ba_review_prompt.md
  sa_architecture_prompt.md
  sa_architecture_review_prompt.md
  sa_dev_plan_prompt.md
  sa_dev_plan_review_prompt.md
  dev_code_prompt.md
  dev_review_prompt.md
  qa_test_plan_prompt.md
  qa_review_prompt.md
```

## Intentionally Not Implemented

- Auto-applying generated snippets directly into the real source tree.
- Human approval workflow between stages.
- Runtime sandbox/execution for snippets in `generated_code.md`.
