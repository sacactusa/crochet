import json
import os
import re
import hashlib
import subprocess

def compute_sha256(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

SYSTEM_PROMPT = """You are a crochet compiler. Translate the next instruction NL into one line of CrochetPARADE DSL.
Use consistent naming and syntax.

Important rules for translations:
1. Make sure your output ONLY contains the DSL code, nothing else.
2. Use the previous examples to understand the pattern of translation.
3. Be consistent in naming conventions with the examples.
4. Your output should be exactly one line of DSL code."""

files = [
    ('early', 'data/crochetbench_repo/data/step_level_test_1_2.json'),
    ('mid', 'data/crochetbench_repo/data/step_level_test_3_4.json'),
    ('late', 'data/crochetbench_repo/data/step_level_test_5_6.json')
]

raw_items = []
empty_items = []

for group, fpath in files:
    with open(fpath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    for idx, item in enumerate(data):
        item_key = f"{group}_{idx}"
        prompt = item.get('prompt', '')
        
        target_nl = ""
        if 'Now translate the NL into DSL:' in prompt:
            parts = prompt.split('Now translate the NL into DSL:')
            after = parts[-1]
            if 'NL:' in after:
                nl_part = after.split('NL:')[1]
                if 'DSL:' in nl_part:
                    target_nl = nl_part.split('DSL:')[0].strip()
                else:
                    target_nl = nl_part.strip()
        elif 'NL:' in prompt:
            nl_parts = prompt.split('NL:')
            target_nl = nl_parts[-1].split('DSL:')[0].strip()

        # Extract prefix DSL lines
        prefix_part = prompt.split('Now translate the NL into DSL:')[0] if 'Now translate the NL into DSL:' in prompt else prompt
        # Match DSL: blocks up to the next NL: or end
        dsl_blocks = []
        for p in prefix_part.split('NL:'):
            if 'DSL:' in p:
                val = p.split('DSL:')[1].strip()
                if val:
                    dsl_blocks.append(val)

        item_data = {
            "item_key": item_key,
            "group": group,
            "index_in_group": idx,
            "id": item.get('id', ''),
            "pattern_name": item.get('pattern_name', ''),
            "target_nl": target_nl,
            "prefix_dsl_blocks": dsl_blocks,
            "prefix_dsl_context": "\n".join(dsl_blocks),
            "prompt": prompt,
            "prompt_hash": compute_sha256(prompt),
            "full_prompt_with_system": f"{SYSTEM_PROMPT}\n\n{prompt}",
            "full_prompt_hash": compute_sha256(f"{SYSTEM_PROMPT}\n\n{prompt}")
        }
        raw_items.append(item_data)
        if not target_nl:
            empty_items.append(item_data)

# Save raw dataset
with open('data/dataset_raw.json', 'w', encoding='utf-8') as f:
    json.dump(raw_items, f, indent=2)

print(f"Total raw items: {len(raw_items)}")
print(f"Empty target items: {len(empty_items)}")

# Standalone set (119 items)
standalone_items = [it for it in raw_items if it['target_nl']]
with open('data/items_standalone.json', 'w', encoding='utf-8') as f:
    json.dump(standalone_items, f, indent=2)

# Verify prefix compilation using Node harness
def compile_dsl_with_harness(dsl_text):
    res = subprocess.run(
        ['node', 'harness/compiler.js', dsl_text],
        capture_output=True,
        text=True
    )
    try:
        return json.loads(res.stdout)
    except Exception:
        return {"valid": False, "error": res.stderr}

prefix_compilation_results = {}
invalid_prefix_items = []

for it in standalone_items:
    item_key = it['item_key']
    prefix = it['prefix_dsl_context']
    if prefix:
        comp_res = compile_dsl_with_harness(prefix)
        prefix_compilation_results[item_key] = comp_res
        if not comp_res.get('valid'):
            invalid_prefix_items.append({
                "item_key": item_key,
                "id": it['id'],
                "pattern_name": it['pattern_name'],
                "error": comp_res.get('error'),
                "prefix": prefix
            })
    else:
        prefix_compilation_results[item_key] = {"valid": True, "error": None}

print(f"Items with invalid prefix: {len(invalid_prefix_items)}")
for inv in invalid_prefix_items:
    print(f"  {inv['item_key']} ({inv['id']} - {inv['pattern_name']}): {inv['error'][:80]}")

# Contextual set (117 items)
excluded_contextual_keys = set(x['item_key'] for x in invalid_prefix_items)
contextual_items = [it for it in standalone_items if it['item_key'] not in excluded_contextual_keys]

with open('data/items_contextual.json', 'w', encoding='utf-8') as f:
    json.dump(contextual_items, f, indent=2)

# Excluded items logging
excluded_log = {
    "empty_target_items_count": len(empty_items),
    "empty_target_items": [
        {"item_key": it['item_key'], "id": it['id'], "pattern_name": it['pattern_name'], "reason": "Instruksi target kosong"}
        for it in empty_items
    ],
    "invalid_prefix_contextual_count": len(invalid_prefix_items),
    "invalid_prefix_contextual_items": invalid_prefix_items
}
with open('logs/excluded_items.json', 'w', encoding='utf-8') as f:
    json.dump(excluded_log, f, indent=2)

# Save prompts
prompts_dict = {}
for it in standalone_items:
    prompts_dict[it['item_key']] = {
        "item_key": it['item_key'],
        "id": it['id'],
        "prompt": it['prompt'],
        "prompt_hash": it['prompt_hash'],
        "full_prompt_with_system": it['full_prompt_with_system'],
        "full_prompt_hash": it['full_prompt_hash']
    }
with open('prompts/prompts.json', 'w', encoding='utf-8') as f:
    json.dump(prompts_dict, f, indent=2)

print("\nTabel 3.3 Verifikasi:")
groups = ['early', 'mid', 'late']
for g in groups:
    raw_g = len([x for x in raw_items if x['group'] == g])
    stand_g = len([x for x in standalone_items if x['group'] == g])
    cont_g = len([x for x in contextual_items if x['group'] == g])
    print(f"  {g.capitalize()}: Raw={raw_g}, Standalone={stand_g}, Contextual={cont_g}")

print(f"  Total: Raw={len(raw_items)}, Standalone={len(standalone_items)}, Contextual={len(contextual_items)}")

