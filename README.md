# The math latex crawl and ML

Project crawl bài toán LaTeX và fine-tune Qwen2.5-Math-1.5B-Instruct với kiến trúc 5-agent cho toán tiếng Việt.

## Pipeline ACTIVE

```
DATA/datasheet_final.json
        │
        ▼
scripts/expand_dataset.py
        │
        ▼
DATA/5agent_expanded/        (train/val/test × agent1..agent5)
        │
        ▼
train_model/qwen25_math_5agent_lora_kaggle.py   ← train LoRA 5 adapter
        │
        ▼
train_model/inference_5agent_kaggle.py         ← inference 5-agent
```

## Cấu trúc thư mục

- **DATA/** — dữ liệu
  - `datasheet_final.json` — input gốc (templates + examples)
  - `5agent_expanded/` — đang dùng để train (output của expand_dataset.py)
  - `5agent_final/` — backup
  - `extra_domain_problems.json` — bài toán bổ sung
- **scripts/**
  - `expand_dataset.py` — tạo 5agent_expanded từ datasheet
  - `convert_datasheet_to_agents.py` — convert sang format 5-agent (legacy)
  - `optimize_dataset.py` — tối ưu dataset
  - `transform_for_5agent.py` — transform cho pipeline 5-agent
- **train_model/**
  - `qwen25_math_5agent_lora_kaggle.py` — train LoRA trên Kaggle
  - `inference_5agent_kaggle.py` — inference
  - `inference_vietnamese.py` — inference tiếng Việt
- **src/** — TypeScript crawlers (export-from-json.ts, index.ts)
- **src_python_support/** — Python helpers (convert_datasheet.py, enrich_datasheet.py, normalize_sympy.py, dedup.py)
- **docs/** — tài liệu, hướng dẫn
- **archive/** — code/logs cũ đã archive
  - `dead_scripts/` — script không còn dùng
  - `temp_scripts/` — script tmp_*.py
  - `logs/` — file .log/.txt cũ
  - `legacy_code/` — code cũ khác (js, wrap-math.js)

## Tài liệu

Xem `docs/`:
- `working_rule.md` — quy tắc làm việc
- `pipeline_plan_vietnamese_math.md` — kế hoạch pipeline tiếng Việt
- `HUONG_DAN_SU_DUNG_SAU_FIX.md` — hướng dẫn sau fix

## Cleanup gần đây (2026-08-07)

- Đổi tên file docs tiếng Việt bị lỗi font (`HƯỚNG_DẪN_...md` → `HUONG_DAN_...md`)
- Xóa `venv/` (~1.1 GB) và `.venv/` — không cần thiết, tạo lại bằng `python -m venv venv`
- Xóa `__pycache__/` (2115 thư mục con)
- Xóa `logs/` rỗng ở root
- Cập nhật `.gitignore` để ignore: `.venv`, `archive/`, `.cursor/`, `.agents/`, `.codex/`, `.gemini/`, `*.safetensors`, `checkpoints/`, generated `DATA/qwen_*.jsonl`
- Lưu ý: KHÔNG xóa `dist/` — vẫn được `npm run build` sử dụng

## Cấu trúc inference

- `train_model/inference_5agent_kaggle.py` — bản gốc (có HTML, cho Kaggle notebook)
- `train_model/inference_terminal.py` — bản terminal thuần, không HTML
- `train_model/inference_vietnamese.py` — bản tiếng Việt
