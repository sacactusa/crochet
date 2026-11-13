#!/usr/bin/env python3
"""
build_experiment_queue.py

Constructs the complete frozen experiment queue for FASE 4:
- 119 CrochetBench-Dstep items x 6 experimental conditions = 714 requests.
- Randomly shuffled with fixed seed (SEED = 42), then frozen.
- Tracks status (pending, done, failed), attempts, error history, and timestamps.
- Preserves reproducibility and resumability.
"""

import os
import json
import random
import hashlib
from datetime import datetime

SEED = 42

CONDITIONS = [
    {
        "condition": "L25L-OFF",
        "family": "2.5",
        "model_id": "gemini-2.5-flash-lite",
        "key_alias": "key_25",
        "client_timeout_sec": 180,
        "config": {
            "thinking_budget": 0,
            "max_output_tokens": 32768
        }
    },
    {
        "condition": "L25L-ON",
        "family": "2.5",
        "model_id": "gemini-2.5-flash-lite",
        "key_alias": "key_25",
        "client_timeout_sec": 180,
        "config": {
            "thinking_budget": -1,
            "max_output_tokens": 32768
        }
    },
    {
        "condition": "L25F-OFF",
        "family": "2.5",
        "model_id": "gemini-2.5-flash",
        "key_alias": "key_25",
        "client_timeout_sec": 180,
        "config": {
            "thinking_budget": 0,
            "max_output_tokens": 32768
        }
    },
    {
        "condition": "L25F-ON",
        "family": "2.5",
        "model_id": "gemini-2.5-flash",
        "key_alias": "key_25",
        "client_timeout_sec": 180,
        "config": {
            "thinking_budget": -1,
            "max_output_tokens": 32768
        }
    },
    {
        "condition": "L38F-LOW",
        "family": "3.8",
        "model_id": "gemini-3.8-flash",
        "key_alias": "key_38",
        "client_timeout_sec": 600,
        "config": {
            "thinking_level": "low",
            "max_output_tokens": 32768
        }
    },
    {
        "condition": "L38F-HIGH",
        "family": "3.8",
        "model_id": "gemini-3.8-flash",
        "key_alias": "key_38",
        "client_timeout_sec": 600,
        "config": {
            "thinking_level": "high",
            "max_output_tokens": 32768
        }
    }
]

def build_queue():
    prompts_path = "prompts/prompts.json"
    if not os.path.exists(prompts_path):
        raise FileNotFoundError(f"Missing {prompts_path}")

    with open(prompts_path, "r", encoding="utf-8") as f:
        prompts = json.load(f)

    # Sort item keys deterministically before cartesian product
    item_keys = sorted(prompts.keys())
    print(f"Total dataset items found: {len(item_keys)}")

    queue_entries = []
    for item_key in item_keys:
        p_entry = prompts[item_key]
        for cond in CONDITIONS:
            entry = {
                "item_id": item_key,
                "dataset_id": p_entry.get("id"),
                "condition": cond["condition"],
                "family": cond["family"],
                "model_id": cond["model_id"],
                "key_alias": cond["key_alias"],
                "client_timeout_sec": cond["client_timeout_sec"],
                "config": cond["config"],
                "prompt_hash": p_entry.get("prompt_hash"),
                "full_prompt_hash": p_entry.get("full_prompt_hash"),
                "status": "pending",  # pending | done | failed
                "attempts": 0,
                "error_history": [],
                "completed_at": None
            }
            queue_entries.append(entry)

    total_requests = len(queue_entries)
    print(f"Total Cartesian combinations: {total_requests} (119 items x 6 conditions)")

    # Shuffle with fixed SEED = 42
    random.seed(SEED)
    random.shuffle(queue_entries)

    # Assign sequential request IDs after shuffle
    for idx, entry in enumerate(queue_entries, start=1):
        entry["request_id"] = f"REQ-{idx:04d}"

    # Build container
    container = {
        "metadata": {
            "created_at": datetime.now().isoformat(),
            "seed": SEED,
            "total_requests": total_requests,
            "total_items": len(item_keys),
            "conditions": [c["condition"] for c in CONDITIONS],
            "description": "Frozen randomized experiment queue for Phase 4 LLM translation"
        },
        "queue": queue_entries
    }

    out_path = "data/experiment_queue.json"
    os.makedirs("data", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(container, f, indent=2, ensure_ascii=False)

    with open(out_path, "rb") as f:
        q_sha = hashlib.sha256(f.read()).hexdigest()

    print(f"Experiment queue generated and frozen at: {out_path}")
    print(f"File SHA-256: {q_sha}")
    print(f"Family 2.5 requests: {sum(1 for e in queue_entries if e['family'] == '2.5')}")
    print(f"Family 3.8 requests: {sum(1 for e in queue_entries if e['family'] == '3.8')}")

if __name__ == "__main__":
    build_queue()

