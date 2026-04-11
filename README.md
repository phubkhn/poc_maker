# BRD Agent Pipeline

Artifact-driven pipeline cho flow `BRD -> BA -> SA`, tập trung vào output đủ chi tiết để làm input tốt cho bước tạo code sau này.

## Mục Tiêu

- Đọc BRD từ file và chuẩn hóa dữ liệu.
- Sinh BA task breakdown theo cấu trúc rõ ràng.
- Sinh SA `architecture.md` và `dev_plan.md`.
- Mỗi bước hỗ trợ:
  - mode `deterministic | llm | hybrid`
  - 1 vòng review/enhance tự động (configurable)
  - consistency gate để bắt lỗi thiếu coverage.

## Yêu Cầu Môi Trường

- Python `>=3.9,<3.10` (mục tiêu chính: `3.9.6`)
- `pip3`

## Cài Đặt Nhanh

```bash
python3 -m venv .venv
source .venv/bin/activate
pip3 install --upgrade pip
pip3 install -e ".[dev]"
```

## Cấu Hình

Copy file mẫu:

```bash
cp .env.example .env
```

Export biến môi trường (ví dụ):

```bash
export OPENAI_API_KEY=your_key_here

export BRD_ANALYZER_MODE=hybrid
export BRD_LLM_MODEL=gpt-4o-mini
export BRD_LLM_TEMPERATURE=0
export BRD_EXTRACTION_PROMPT_PATH=prompts/brd_extraction_prompt.md

export BA_AGENT_MODE=hybrid
export BA_LLM_MODEL=gpt-4o-mini
export BA_LLM_TEMPERATURE=0.2
export BA_TASK_PROMPT_PATH=prompts/ba_task_prompt.md
export BA_REVIEW_PROMPT_PATH=prompts/ba_review_prompt.md
export BA_REVIEW_ITERATIONS=1

export SA_AGENT_MODE=hybrid
export SA_LLM_MODEL=gpt-4o-mini
export SA_LLM_TEMPERATURE=0.2
export SA_ARCH_PROMPT_PATH=prompts/sa_architecture_prompt.md
export SA_DEV_PLAN_PROMPT_PATH=prompts/sa_dev_plan_prompt.md
export SA_ARCH_REVIEW_PROMPT_PATH=prompts/sa_architecture_review_prompt.md
export SA_DEV_PLAN_REVIEW_PROMPT_PATH=prompts/sa_dev_plan_review_prompt.md
export SA_REVIEW_ITERATIONS=1

export DEV_REVIEW_PROMPT_PATH=prompts/dev_review_prompt.md
```

Note: app đọc trực tiếp từ environment shell; `.env` chỉ là file tham chiếu.

## Chạy Theo Từng Bước

### 1) BRD Extraction

```bash
python3 -m brd_agent.main read-brd --input input/sample_brd.md --output-dir artifacts
```

Output:

- `artifacts/brd_normalized.json`
- `artifacts/context.md`
- `artifacts/brd_gaps.md`

### 2) BA Generation

```bash
python3 -m brd_agent.main generate-ba --input artifacts/brd_normalized.json --output-dir artifacts
```

Output:

- `artifacts/task.md`

### 3) SA Generation

```bash
python3 -m brd_agent.main generate-sa --brd artifacts/brd_normalized.json --tasks artifacts/task.md --output-dir artifacts
```

Output:

- `artifacts/architecture.md`
- `artifacts/dev_plan.md`

## Chạy Full Pipeline

```bash
python3 -m brd_agent.main run-pipeline --input input/sample_brd.md --output-dir artifacts
```

Pipeline sẽ chạy BRD -> BA -> SA, có trace timing từng step.

## Mode Điều Khiển

Mỗi stage hỗ trợ:

- `deterministic`: không gọi LLM.
- `llm`: bắt buộc LLM, lỗi thì fail.
- `hybrid`: thử LLM trước, lỗi thì fallback deterministic.

Biến điều khiển:

- `BRD_ANALYZER_MODE`
- `BA_AGENT_MODE`
- `SA_AGENT_MODE`

Khuyến nghị mặc định: `hybrid`.

## Cơ Chế Chất Lượng Output

- JSON contract validation bằng Pydantic cho BA/SA.
- Review/enhance loop:
  - BA: `BA_REVIEW_ITERATIONS` (mặc định `1`)
  - SA: `SA_REVIEW_ITERATIONS` (mặc định `1`)
- Rubric scoring nội bộ:
  - completeness
  - implementability
  - testability
  - ambiguity penalty
- Consistency gate:
  - BA gate: coverage epic/task và trace từ BRD.
  - SA gate: coverage component/phase/module và tính khả thi kế hoạch.

## Test

```bash
pytest -q
```

## Cấu Trúc Repo (rút gọn)

```text
src/brd_agent/
  main.py
  config.py
  llm/client.py
  schemas/
    brd.py
    ba.py
    sa.py
  services/
    brd_loader.py
    brd_analyzer.py
    ba_agent.py
    sa_agent.py
    consistency_gate.py
    artifact_writer.py
  templates/
    context.md.j2
    brd_gaps.md.j2
    task.md.j2
    architecture.md.j2
    dev_plan.md.j2

prompts/
  brd_extraction_prompt.md
  ba_task_prompt.md
  ba_review_prompt.md
  sa_architecture_prompt.md
  sa_architecture_review_prompt.md
  sa_dev_plan_prompt.md
  sa_dev_plan_review_prompt.md
  dev_review_prompt.md
```

## Phạm Vi Hiện Tại

Đã có:

- BRD/BA/SA pipeline
- deterministic + llm + hybrid
- review loop 1 lần (configurable)
- consistency gate
- full pipeline command + trace

Chưa có (cố ý):

- Dev agent tạo code
- QA/Test agent
- orchestration framework nhiều agent
- review gates đa vòng tự động cho toàn pipeline
