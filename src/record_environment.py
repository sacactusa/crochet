import json
import os
import platform
import subprocess
from datetime import datetime

# Get git commit hash of CrochetPARADE
try:
    commit_hash = subprocess.check_output(
        ['git', '-C', 'harness/crochetparade', 'rev-parse', 'HEAD'],
        text=True
    ).strip()
    commit_date = subprocess.check_output(
        ['git', '-C', 'harness/crochetparade', 'log', '-1', '--format=%cI'],
        text=True
    ).strip()
except Exception as e:
    commit_hash = "unknown"
    commit_date = "unknown"

# Node version
try:
    node_ver = subprocess.check_output(['node', '--version'], text=True).strip()
except Exception:
    node_ver = "unknown"

# Python google-genai version
try:
    import google.genai
    import importlib.metadata
    genai_ver = importlib.metadata.version('google-genai')
except Exception:
    genai_ver = "unknown"

try:
    import scipy
    scipy_ver = scipy.__version__
except Exception:
    scipy_ver = "unknown"

try:
    import pandas
    pandas_ver = pandas.__version__
except Exception:
    pandas_ver = "unknown"

env_info = {
    "seed": 42,
    "timestamp": datetime.now().isoformat(),
    "os": {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine()
    },
    "tools": {
        "python": platform.python_version(),
        "node": node_ver,
        "google_genai_sdk": genai_ver,
        "scipy": scipy_ver,
        "pandas": pandas_ver
    },
    "crochetparade": {
        "repository": "https://codeberg.org/crochetparade/CrochetPARADE",
        "commit_hash": commit_hash,
        "commit_date": commit_date,
        "compiler_file": "parse64.js",
        "translator_file": "deterministic_translator.js"
    },
    "crochetbench": {
        "repository": "https://github.com/Peiyu-Georgia-Li/crochetBench",
        "dataset_files": [
            "data/crochetbench_repo/data/step_level_test_1_2.json",
            "data/crochetbench_repo/data/step_level_test_3_4.json",
            "data/crochetbench_repo/data/step_level_test_5_6.json"
        ]
    }
}

os.makedirs('logs', exist_ok=True)
with open('logs/environment.json', 'w', encoding='utf-8') as f:
    json.dump(env_info, f, indent=2)

print("Saved logs/environment.json:")
print(json.dumps(env_info, indent=2))

