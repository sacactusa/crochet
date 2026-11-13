#!/usr/bin/env python3
"""
normalize.py

Normalizes raw outputs from LLM (raw/llm.jsonl) and Rule-Based (raw/rule_based.jsonl)
Strict Normalization Rules per Proposal:
- Only strip markdown code fences (```dsl, ```crochet, ```) and edge whitespace.
- Prose responses or responses with more than one line are flagged as format errors (invalid).
- Retains pure DSL string for compiler evaluation.
"""

import os
import re
import json

def clean_dsl(text):
    if not text:
        return "", True, "Empty response"
    
    s = text.strip()
    
    # 1. Strip markdown code fences if present
    fence_match = re.search(r"```(?:dsl|crochet)?\s*\n?(.*?)\n?```", s, re.DOTALL | re.IGNORECASE)
    if fence_match:
        s = fence_match.group(1).strip()
    
    # 2. Strip edge whitespace
    s = s.strip()
    lines = [line.strip() for line in s.splitlines() if line.strip()]
    if not lines:
        return "", True, "Empty response"
    
    # Format error rule: more than one line is an invalid format error
    if len(lines) > 1:
        return s, True, f"Format error: multi-line response ({len(lines)} lines)"
    
    single_line = lines[0].strip("`'\"").strip()
    
    # Format error rule: conversational prose
    lower = single_line.lower()
    if lower.startswith(("here is", "i cannot", "sorry,", "sure,", "as an ai", "the translation")) and len(single_line.split()) > 6:
        return single_line, True, "Format error: prose response instead of DSL"
    
    return single_line, False, None

def run_normalization():
    records = []
    
    # 1. Read Rule-Based records
    rb_path = "raw/rule_based.jsonl"
    if os.path.exists(rb_path):
        with open(rb_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                d = json.loads(line)
                raw_text = d.get("raw_response") or d.get("dsl_output", "")
                dsl, is_fmt_err, fmt_msg = clean_dsl(raw_text)
                d["condition"] = d.get("condition_id") or d.get("condition") or d.get("mode")
                d["normalized_dsl"] = dsl
                d["format_error"] = is_fmt_err
                d["format_error_reason"] = fmt_msg
                d["source"] = "rule_based"
                records.append(d)
        print(f"Loaded {len(records)} rule-based records.")
        
    # 2. Read LLM records
    llm_path = "raw/llm.jsonl"
    llm_count = 0
    if os.path.exists(llm_path):
        with open(llm_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                d = json.loads(line)
                # Only process done records
                if d.get("status") == "done" and d.get("raw_response_text") is not None:
                    raw_text = d.get("raw_response_text", "")
                    dsl, is_fmt_err, fmt_msg = clean_dsl(raw_text)
                    d["normalized_dsl"] = dsl
                    d["format_error"] = is_fmt_err
                    d["format_error_reason"] = fmt_msg
                    d["source"] = "llm"
                    records.append(d)
                    llm_count += 1
        print(f"Loaded {llm_count} LLM records.")

    out_path = "data/normalized_records.json"
    os.makedirs("data", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
        
    print(f"Total {len(records)} normalized records written to {out_path}")
    return records

if __name__ == "__main__":
    run_normalization()
