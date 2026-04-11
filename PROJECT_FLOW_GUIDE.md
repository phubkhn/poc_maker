# Project Flow Guide

Huong dan tung step de hieu va chay du an.

## 1) Chuan bi moi truong

```bash
cd /Users/dirak/Documents/AI/POC_MAKER
python3 -m venv .venv
source .venv/bin/activate
pip3 install -e ".[dev]"
```

## 2) Cau hinh mode + model

Khuyen nghi `hybrid`:

```bash
export BRD_ANALYZER_MODE=hybrid
export BA_AGENT_MODE=hybrid
export SA_AGENT_MODE=hybrid

export BRD_LLM_MODEL=gpt-4o-mini
export BA_LLM_MODEL=gpt-4o-mini
export SA_LLM_MODEL=gpt-4o-mini
export OPENAI_API_KEY=your_key_here
```

Tuy chon review loop:

```bash
export BA_REVIEW_ITERATIONS=1
export SA_REVIEW_ITERATIONS=1
```

## 3) Step BRD (`read-brd`)

Input:
- BRD markdown/text (vi du `input/sample_brd.md`)

Run:

```bash
python3 -m brd_agent.main read-brd --input input/sample_brd.md --output-dir artifacts
```

Output:
- `artifacts/brd_normalized.json`
- `artifacts/context.md`
- `artifacts/brd_gaps.md`

Y nghia:
- Parse BRD thanh schema chuan de cac buoc sau dung chung.

## 4) Step BA (`generate-ba`)

Input:
- `artifacts/brd_normalized.json`

Run:

```bash
python3 -m brd_agent.main generate-ba --input artifacts/brd_normalized.json --output-dir artifacts
```

Output:
- `artifacts/task.md`

Y nghia:
- BA tao task breakdown chi tiet (epic/task/dependency/risk/acceptance criteria/module hint).
- Co auto review-enhance 1 lan + consistency gate.

## 5) Step SA (`generate-sa`)

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

Y nghia:
- SA chuyen BRD + BA tasks thanh plan ky thuat chi tiet.
- Co auto review-enhance 1 lan + consistency gate.

## 6) Chay full pipeline 1 lenh

```bash
python3 -m brd_agent.main run-pipeline --input input/sample_brd.md --output-dir artifacts
```

Flow noi bo:
- BRD -> BA -> SA
- Co trace log thoi gian tung step.

## 7) Kiem thu

```bash
pytest -q
```

Trang thai hien tai:
- Test pass toan bo (`23 passed`).

## 8) Goi y doc output truoc khi sang Dev

Nen doc ky 3 file:
- `artifacts/task.md`
- `artifacts/architecture.md`
- `artifacts/dev_plan.md`

Muc tieu:
- Kiem tra do ro rang, do day du, va tinh kha thi truoc khi bat dau tao code.
