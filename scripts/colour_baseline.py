"""Rewrite survey/tests/colour_baseline.json — the number of colour literals each creator
stylesheet and template may hold (change design-tokens).

Run it after REMOVING literals (moving a component onto css/tokens.css), never to let new ones in:

    python scripts/colour_baseline.py
"""
import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def main():
    spec = importlib.util.spec_from_file_location('ratchet', REPO / 'survey/tests/test_design_tokens.py')
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(REPO))
    spec.loader.exec_module(module)
    counts = module.colour_counts()
    module.BASELINE.write_text(json.dumps(counts, indent=1, sort_keys=True) + '\n')
    print(f'{sum(counts.values())} colour literals in {len(counts)} files')


if __name__ == '__main__':
    main()
