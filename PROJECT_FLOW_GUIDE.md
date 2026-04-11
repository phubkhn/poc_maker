# Project Flow Guide

Step-by-step guide to understand and operate the `BRD -> BA -> SA -> Dev -> QA` project flow.

## 0) Flow Overview

Pipeline execution order:
1. BRD ingestion and normalization
2. Generate default standards (`code_standards.md`, `review_standards.md`)
3. BA generation + review + consistency gate
4. SA generation + review + consistency gate
5. Dev generation + review + consistency gate
6. QA generation + review + consistency gate

## 1) Prepare Environment

Requirements:
- Python `>=3.9,<3.10` (target: `3.9.6`)
- pip3

```bash
cd /Users/dirak/Documents/AI/POC_MAKER
python3 -m venv .venv
source .venv/bin/activate
pip3 install --upgrade pip
pip3 install -e ".[dev]"
```

## 2) Configure Environment Variables

Copy example file:

```bash
cp .env.example .env
```

Quick setup:

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

## 3) BRD Step (`read-brd`)

Input:
- `input/sample_brd.md` (or any BRD markdown/text file)

Run:

```bash
python3 -m brd_agent.main read-brd --input input/sample_brd.md --output-dir artifacts
```

Output:
- `artifacts/brd_normalized.json`
- `artifacts/context.md`
- `artifacts/brd_gaps.md`

## 4) Standards Step (`generate-standards`)

Input:
- None

Run:

```bash
python3 -m brd_agent.main generate-standards --output-dir artifacts
```

Output:
- `artifacts/code_standards.md`
- `artifacts/review_standards.md`

Meaning:
- Dev and review flows use these standards as the default baseline.

## 5) BA Step (`generate-ba`)

Input:
- `artifacts/brd_normalized.json`

Run:

```bash
python3 -m brd_agent.main generate-ba --input artifacts/brd_normalized.json --output-dir artifacts
```

Output:
- `artifacts/task.md`

## 6) SA Step (`generate-sa`)

Input:
- `artifacts/brd_normalized.json`
- `artifacts/task.md`

Run:

```bash
python3 -m brd_agent.main generate-sa --brd artifacts/brd_normalized.json --tasks artifacts/task.md --output-dir artifacts
```

Output:
- `artifacts/architecture.md`
- `artifacts/dev_plan.md`

## 7) Dev Step (`generate-dev`)

Input:
- `artifacts/brd_normalized.json`
- `artifacts/task.md`
- `artifacts/architecture.md`
- `artifacts/dev_plan.md`
- (optional) `artifacts/code_standards.md`
- (optional) `artifacts/review_standards.md`

Run:

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

Output:
- `artifacts/generated_code.md`

Note:
- If standards are not provided or files do not exist, built-in defaults are used.

## 8) QA Step (`generate-qa`)

Input:
- `artifacts/brd_normalized.json`
- `artifacts/task.md`
- `artifacts/architecture.md`
- `artifacts/dev_plan.md`
- `artifacts/generated_code.md`

Run:

```bash
python3 -m brd_agent.main generate-qa \
  --brd artifacts/brd_normalized.json \
  --tasks artifacts/task.md \
  --architecture artifacts/architecture.md \
  --dev-plan artifacts/dev_plan.md \
  --generated-code artifacts/generated_code.md \
  --output-dir artifacts
```

Output:
- `artifacts/qa_test_plan.md`
- `artifacts/qa_test_cases.md`

## 9) Run Full Pipeline in One Command

```bash
python3 -m brd_agent.main run-pipeline --input input/sample_brd.md --output-dir artifacts
```

Full output set:
- `brd_normalized.json`
- `context.md`
- `brd_gaps.md`
- `code_standards.md`
- `review_standards.md`
- `task.md`
- `architecture.md`
- `dev_plan.md`
- `generated_code.md`
- `qa_test_plan.md`
- `qa_test_cases.md`

## 10) Validate With Tests

```bash
pytest -q
```

Current status:
- `38 passed`

## 11) Suggested Artifact Reading Order Before Real Coding

Recommended order:
1. `artifacts/task.md`
2. `artifacts/architecture.md`
3. `artifacts/dev_plan.md`
4. `artifacts/code_standards.md`
5. `artifacts/review_standards.md`
6. `artifacts/generated_code.md`
7. `artifacts/qa_test_plan.md`

Goal:
- Ensure requirement completeness,
- keep BRD scope alignment,
- ensure technical feasibility,
- and enforce coding/review standards before real implementation in source code.
