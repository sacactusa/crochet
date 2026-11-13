import json
import re
from collections import Counter

files = [
    ('early', 'data/crochetbench_repo/data/step_level_test_1_2.json'),
    ('mid', 'data/crochetbench_repo/data/step_level_test_3_4.json'),
    ('late', 'data/crochetbench_repo/data/step_level_test_5_6.json')
]

empty_items = []
items_119 = []
all_dsl_lines = []

for group, fpath in files:
    with open(fpath, encoding='utf-8') as f:
        data = json.load(f)
    for idx, item in enumerate(data):
        prompt = item.get('prompt', '')
        
        target_nl = ''
        if 'Now translate the NL into DSL:' in prompt:
            parts = prompt.split('Now translate the NL into DSL:')
            after = parts[1]
            if 'NL:' in after:
                target_nl = after.split('NL:')[1].split('DSL:')[0].strip()
        elif 'NL:' in prompt:
            target_nl = prompt.split('NL:')[-1].split('DSL:')[0].strip()
            
        if not target_nl:
            empty_items.append({
                'group': group,
                'index': idx,
                'id': item.get('id'),
                'pattern_name': item.get('pattern_name')
            })
            continue
            
        # Extract prefix part
        prefix_part = prompt.split('Now translate the NL into DSL:')[0] if 'Now translate the NL into DSL:' in prompt else prompt
        
        # In prompt, steps are separated by NL: and DSL:
        # Let's extract each DSL: line
        dsl_matches = re.findall(r'DSL:\s*(.*?)(?=\n\s*NL:|$)', prefix_part, re.DOTALL)
        dsl_lines = [d.strip() for d in dsl_matches if d.strip()]
        
        items_119.append({
            'group': group,
            'orig_idx': idx,
            'id': item.get('id'),
            'pattern_name': item.get('pattern_name'),
            'target_nl': target_nl,
            'prefix_dsl': dsl_lines,
            'full_prompt': prompt
        })
        all_dsl_lines.extend(dsl_lines)

print(f"Total non-empty items: {len(items_119)}")
print(f"Empty items count: {len(empty_items)}")
for ei in empty_items:
    print(f"  Empty item: {ei['group']}_{ei['index']} ID: {ei['id']} Name: {ei['pattern_name']}")

early_count = len([x for x in items_119 if x['group'] == 'early'])
mid_count = len([x for x in items_119 if x['group'] == 'mid'])
late_count = len([x for x in items_119 if x['group'] == 'late'])
print(f"Breakdown: Early={early_count}, Mid={mid_count}, Late={late_count}")

lengths = [len(x['prefix_dsl']) for x in items_119]
print("Distribution of prefix lengths:", Counter(lengths))
print(f"Sum of prefix DSL lines across 119 items: {sum(lengths)}")

