#!/usr/bin/env python3
"""
QLoRA fine-tune for Qwen2.5-Math-1.5B-Instruct on Kaggle T4.

Dataset format:
  JSONL rows with a `messages` list, for example:
    {"messages": [{"role": "system", ...}, {"role": "user", ...},
                  {"role": "assistant", ...}]}

Kaggle quick start:
  1. Add your dataset to the notebook.
  2. Run:
       !pip install -q -U "transformers>=4.45.0" "accelerate>=0.33.0" \
           "datasets>=2.20.0" "peft>=0.13.0" "bitsandbytes>=0.44.0"
       !python /path/to/train_qwen25_math_kaggle_t4.py

The script auto-finds these files under /kaggle/input:
  - qwen_merged_train_byid.jsonl
  - qwen_resplit_val_byid.jsonl

It also checks this Kaggle dataset path first:
  - /kaggle/input/datasets/vitduq/train-and-val/

Working fallback points to Kaggle's /kaggle/working folder.
"""

from __future__ import annotations

import argparse
import glob
import inspect
import json
import math
import os
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
from datasets import Dataset, DatasetDict, load_dataset
from peft import LoraConfig, TaskType, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    EarlyStoppingCallback,
    Trainer,
    TrainingArguments,
    set_seed,
)


BASE_MODEL = "Qwen/Qwen2.5-Math-1.5B-Instruct"
KAGGLE_TRAIN = r"/kaggle/input/datasets/vitduq/train-and-val/qwen_merged_train_byid.jsonl"
KAGGLE_VAL = r"/kaggle/input/datasets/vitduq/train-and-val/qwen_resplit_val_byid.jsonl"
LOCAL_TRAIN = r"/kaggle/working/qwen_merged_train_byid.jsonl"
LOCAL_VAL = r"/kaggle/working/qwen_resplit_val_byid.jsonl"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fine-tune Qwen2.5-Math-1.5B-Instruct with QLoRA on chat JSONL."
    )
    parser.add_argument("--train_file", default=None, help="Path to train JSONL.")
    parser.add_argument("--val_file", default=None, help="Path to validation JSONL.")
    parser.add_argument("--model_name", default=BASE_MODEL)
    parser.add_argument("--output_dir", default="/kaggle/working/qwen25_math_1p5b_vi_lora")
    parser.add_argument("--max_length", type=int, default=2048)
    parser.add_argument("--num_train_epochs", type=float, default=2.0)
    parser.add_argument("--per_device_train_batch_size", type=int, default=1)
    parser.add_argument("--per_device_eval_batch_size", type=int, default=1)
    parser.add_argument("--gradient_accumulation_steps", type=int, default=16)
    parser.add_argument("--learning_rate", type=float, default=5e-5)
    parser.add_argument("--warmup_ratio", type=float, default=0.05)
    parser.add_argument("--weight_decay", type=float, default=0.01)
    parser.add_argument("--logging_steps", type=int, default=25)
    parser.add_argument("--eval_steps", type=int, default=500)
    parser.add_argument("--save_steps", type=int, default=500)
    parser.add_argument("--save_total_limit", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--lora_r", type=int, default=32)
    parser.add_argument("--lora_alpha", type=int, default=64)
    parser.add_argument("--lora_dropout", type=float, default=0.05)
    parser.add_argument(
        "--lora_targets",
        default="q_proj,v_proj,o_proj",
        help=(
            "Comma-separated LoRA target module names. "
            "Default keeps only 3 attention modules for Kaggle T4 memory."
        ),
    )
    parser.add_argument(
        "--no_4bit",
        action="store_true",
        help="Disable 4-bit loading. Not recommended for Kaggle T4.",
    )
    parser.add_argument(
        "--max_train_samples",
        type=int,
        default=None,
        help="Optional debug cap for train samples.",
    )
    parser.add_argument(
        "--max_eval_samples",
        type=int,
        default=None,
        help="Optional debug cap for validation samples.",
    )
    parser.add_argument(
        "--resume_from_checkpoint",
        default=None,
        help="Checkpoint path, or 'auto' to resume from the latest checkpoint.",
    )
    parser.add_argument(
        "--merge_and_save",
        action="store_true",
        help="Also save a merged fp16 model in output_dir/merged. Uses extra RAM.",
    )
    args, unknown_args = parser.parse_known_args()
    if unknown_args:
        print(f"Ignoring notebook/kernel args: {unknown_args}")
    return args


def first_existing_path(paths: list[str]) -> str | None:
    for path in paths:
        if path and os.path.exists(path):
            return path
    return None


def find_data_file(
    cli_path: str | None,
    kaggle_path: str,
    local_path: str,
    filename: str,
) -> str:
    candidates = []
    if cli_path:
        candidates.append(cli_path)
    candidates.extend(
        [
            kaggle_path,
            f"/kaggle/input/{filename}",
            *glob.glob(f"/kaggle/input/**/{filename}", recursive=True),
            local_path,
            str(Path("DATA") / filename),
        ]
    )
    found = first_existing_path(candidates)
    if not found:
        raise FileNotFoundError(
            f"Cannot find {filename}. Pass it explicitly with --train_file/--val_file."
        )
    return found


def load_jsonl_dataset(train_file: str, val_file: str) -> DatasetDict:
    data_files = {"train": train_file, "validation": val_file}
    return load_dataset("json", data_files=data_files)


def role_is_assistant(message: dict[str, Any]) -> bool:
    return str(message.get("role", "")).lower() == "assistant"


def find_last_assistant(messages: list[dict[str, Any]]) -> int:
    for idx in range(len(messages) - 1, -1, -1):
        if role_is_assistant(messages[idx]):
            return idx
    return -1


def validate_messages(example: dict[str, Any]) -> bool:
    messages = example.get("messages")
    if not isinstance(messages, list) or len(messages) < 2:
        return False
    assistant_idx = find_last_assistant(messages)
    if assistant_idx <= 0:
        return False
    for msg in messages:
        if not isinstance(msg, dict):
            return False
        if "role" not in msg or "content" not in msg:
            return False
    return True


def print_dataset_preview(ds: DatasetDict, train_file: str, val_file: str) -> None:
    print("=" * 72)
    print("Dataset")
    print("=" * 72)
    print(f"Train file: {train_file}")
    print(f"Val file:   {val_file}")
    print(f"Train rows: {len(ds['train']):,}")
    print(f"Val rows:   {len(ds['validation']):,}")
    if len(ds["train"]) > 0:
        row = ds["train"][0]
        messages = row.get("messages", [])
        print("First train roles:", [m.get("role") for m in messages])
        user = next((m.get("content", "") for m in messages if m.get("role") == "user"), "")
        assistant = next(
            (m.get("content", "") for m in messages if m.get("role") == "assistant"),
            "",
        )
        print("User preview:", user[:160].replace("\n", " "))
        print("Assistant preview:", assistant[:160].replace("\n", " "))
    print("=" * 72)


def make_chat_encoder(tokenizer: AutoTokenizer, max_length: int):
    def encode(example: dict[str, Any]) -> dict[str, list[int]]:
        messages = example["messages"]
        assistant_idx = find_last_assistant(messages)
        prompt_messages = messages[:assistant_idx]
        full_messages = messages[: assistant_idx + 1]

        prompt_text = tokenizer.apply_chat_template(
            prompt_messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        full_text = tokenizer.apply_chat_template(
            full_messages,
            tokenize=False,
            add_generation_prompt=False,
        )

        prompt_ids = tokenizer(prompt_text, add_special_tokens=False)["input_ids"]
        full_ids = tokenizer(full_text, add_special_tokens=False)["input_ids"]

        if full_ids[: len(prompt_ids)] == prompt_ids:
            answer_ids = full_ids[len(prompt_ids) :]
        else:
            # Conservative fallback if a tokenizer template changes.
            answer_text = messages[assistant_idx]["content"]
            answer_ids = tokenizer(answer_text, add_special_tokens=False)["input_ids"]
            eos_id = tokenizer.eos_token_id
            if eos_id is not None and (not answer_ids or answer_ids[-1] != eos_id):
                answer_ids.append(eos_id)

        if len(prompt_ids) >= max_length:
            keep_prompt = max(1, max_length // 2)
            prompt_ids = prompt_ids[-keep_prompt:]

        answer_budget = max_length - len(prompt_ids)
        if answer_budget <= 0:
            answer_budget = 1
            prompt_ids = prompt_ids[-(max_length - 1) :]

        if len(answer_ids) > answer_budget:
            answer_ids = answer_ids[:answer_budget]

        input_ids = prompt_ids + answer_ids
        labels = [-100] * len(prompt_ids) + answer_ids
        attention_mask = [1] * len(input_ids)

        return {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "labels": labels,
        }

    return encode


@dataclass
class CausalLMCollator:
    tokenizer: AutoTokenizer

    def __call__(self, features: list[dict[str, list[int]]]) -> dict[str, torch.Tensor]:
        labels = [feature["labels"] for feature in features]
        batch = self.tokenizer.pad(
            {
                "input_ids": [feature["input_ids"] for feature in features],
                "attention_mask": [feature["attention_mask"] for feature in features],
            },
            padding=True,
            return_tensors="pt",
        )

        max_len = batch["input_ids"].shape[1]
        padded_labels = torch.full((len(labels), max_len), -100, dtype=torch.long)
        for idx, label in enumerate(labels):
            length = min(len(label), max_len)
            padded_labels[idx, :length] = torch.tensor(label[:length], dtype=torch.long)
        batch["labels"] = padded_labels
        return batch


def maybe_limit(ds: DatasetDict, max_train: int | None, max_eval: int | None) -> DatasetDict:
    if max_train is not None:
        ds["train"] = ds["train"].select(range(min(max_train, len(ds["train"]))))
    if max_eval is not None:
        ds["validation"] = ds["validation"].select(
            range(min(max_eval, len(ds["validation"])))
        )
    return ds


def latest_checkpoint(output_dir: str) -> str | None:
    if not os.path.isdir(output_dir):
        return None
    checkpoints = []
    for path in glob.glob(os.path.join(output_dir, "checkpoint-*")):
        name = os.path.basename(path)
        try:
            step = int(name.rsplit("-", 1)[1])
        except (IndexError, ValueError):
            continue
        checkpoints.append((step, path))
    if not checkpoints:
        return None
    checkpoints.sort()
    return checkpoints[-1][1]


def load_model_and_tokenizer(args: argparse.Namespace):
    tokenizer = AutoTokenizer.from_pretrained(args.model_name, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    model_kwargs: dict[str, Any] = {
        "torch_dtype": torch.float16,
        "device_map": "auto",
        "trust_remote_code": True,
    }
    if not args.no_4bit:
        model_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
        )

    print("=" * 72)
    print("Model")
    print("=" * 72)
    print(f"Base model: {args.model_name}")
    print(f"4-bit QLoRA: {'no' if args.no_4bit else 'yes'}")
    model = AutoModelForCausalLM.from_pretrained(args.model_name, **model_kwargs)

    if not args.no_4bit:
        model = prepare_model_for_kbit_training(
            model,
            use_gradient_checkpointing=True,
        )

    model.config.use_cache = False
    try:
        model.gradient_checkpointing_enable(
            gradient_checkpointing_kwargs={"use_reentrant": False}
        )
    except TypeError:
        model.gradient_checkpointing_enable()

    target_modules = [item.strip() for item in args.lora_targets.split(",") if item.strip()]
    lora_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        target_modules=target_modules,
        lora_dropout=args.lora_dropout,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()
    print("=" * 72)
    return model, tokenizer


def build_training_args(args: argparse.Namespace) -> TrainingArguments:
    total_batch = (
        args.per_device_train_batch_size * args.gradient_accumulation_steps
    )
    print(f"Effective train batch size: {total_batch}")

    kwargs = dict(
        output_dir=args.output_dir,
        overwrite_output_dir=False,
        num_train_epochs=args.num_train_epochs,
        per_device_train_batch_size=args.per_device_train_batch_size,
        per_device_eval_batch_size=args.per_device_eval_batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        learning_rate=args.learning_rate,
        warmup_ratio=args.warmup_ratio,
        weight_decay=args.weight_decay,
        max_grad_norm=0.3,
        lr_scheduler_type="cosine",
        optim="paged_adamw_8bit" if not args.no_4bit else "adamw_torch",
        fp16=True,
        bf16=False,
        gradient_checkpointing=True,
        logging_steps=args.logging_steps,
        eval_steps=args.eval_steps,
        save_strategy="steps",
        save_steps=args.save_steps,
        save_total_limit=args.save_total_limit,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        report_to="none",
        dataloader_num_workers=2,
        remove_unused_columns=False,
    )

    signature = inspect.signature(TrainingArguments.__init__)
    if "eval_strategy" in signature.parameters:
        kwargs["eval_strategy"] = "steps"
    else:
        kwargs["evaluation_strategy"] = "steps"
    if "gradient_checkpointing_kwargs" in signature.parameters:
        kwargs["gradient_checkpointing_kwargs"] = {"use_reentrant": False}

    return TrainingArguments(**kwargs)


def merge_and_save(model, tokenizer, output_dir: str) -> None:
    merged_dir = os.path.join(output_dir, "merged")
    print(f"Merging LoRA adapter to fp16 model: {merged_dir}")
    merged = model.merge_and_unload()
    merged.save_pretrained(merged_dir, safe_serialization=True)
    tokenizer.save_pretrained(merged_dir)


def main() -> None:
    args = parse_args()
    set_seed(args.seed)
    random.seed(args.seed)

    if torch.cuda.is_available():
        print(f"CUDA device: {torch.cuda.get_device_name(0)}")
    else:
        print("WARNING: CUDA is not available. Kaggle GPU must be enabled.")

    train_file = find_data_file(
        args.train_file,
        KAGGLE_TRAIN,
        LOCAL_TRAIN,
        "qwen_merged_train_byid.jsonl",
    )
    val_file = find_data_file(
        args.val_file,
        KAGGLE_VAL,
        LOCAL_VAL,
        "qwen_resplit_val_byid.jsonl",
    )

    ds = load_jsonl_dataset(train_file, val_file)
    ds = ds.filter(validate_messages)
    ds = maybe_limit(ds, args.max_train_samples, args.max_eval_samples)
    print_dataset_preview(ds, train_file, val_file)

    model, tokenizer = load_model_and_tokenizer(args)

    encode = make_chat_encoder(tokenizer, args.max_length)
    tokenized = ds.map(
        encode,
        remove_columns=ds["train"].column_names,
        desc="Tokenizing chat rows",
    )

    lengths = [len(row["input_ids"]) for row in tokenized["train"].select(range(min(512, len(tokenized["train"]))))]  # noqa: E501
    if lengths:
        print(
            "Tokenized length sample: "
            f"min={min(lengths)} mean={math.floor(sum(lengths) / len(lengths))} "
            f"max={max(lengths)}"
        )

    training_args = build_training_args(args)
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized["train"],
        eval_dataset=tokenized["validation"],
        data_collator=CausalLMCollator(tokenizer),
    )
    trainer.add_callback(
        EarlyStoppingCallback(
            early_stopping_patience=3,
            early_stopping_threshold=0.001,
        )
    )

    resume = args.resume_from_checkpoint
    if resume == "auto":
        resume = latest_checkpoint(args.output_dir)
        if resume:
            print(f"Auto resume from: {resume}")
        else:
            print("Auto resume requested, but no checkpoint was found.")

    print("=" * 72)
    print("Training")
    print("=" * 72)
    print(f"Output dir: {args.output_dir}")
    print(f"Epochs: {args.num_train_epochs}")
    print(f"Max length: {args.max_length}")
    print(f"Train rows: {len(tokenized['train']):,}")
    print(f"Val rows: {len(tokenized['validation']):,}")
    print("=" * 72)

    trainer.train(resume_from_checkpoint=resume)

    final_dir = os.path.join(args.output_dir, "final")
    trainer.save_model(final_dir)
    tokenizer.save_pretrained(final_dir)
    print(f"Saved LoRA adapter and tokenizer: {final_dir}")

    metrics = trainer.evaluate()
    print("Final eval metrics:", metrics)

    if args.merge_and_save:
        merge_and_save(model, tokenizer, args.output_dir)


if __name__ == "__main__":
    main()
