"""Evaluate local explanations on actual saved synthetic comparison outputs."""
import json
from collections import Counter
from pathlib import Path
from medbill.explain import Explainer


def main():
    target = Path('docs/phase4')
    target.mkdir(parents=True, exist_ok=True)
    totals = Counter()
    for source in sorted(Path('docs/phase3').glob('*.json')):
        result = Explainer(synthetic=True).explain(json.loads(source.read_text(encoding='utf-8')))
        # Keep evidence compact; full numerical provenance remains in Phase 3.
        evidence = {'input': source.as_posix(), 'summary': result['explanation_summary'],
                    'items': [{'code': i['code'], **i['explanation_result']} for i in result['items']]}
        (target / source.name).write_text(json.dumps(evidence, indent=2), encoding='utf-8')
        totals.update(result['explanation_summary']['counts'])
        print(source.stem, json.dumps(evidence['summary']))
        for item in evidence['items']:
            print(f"  {item['code']}: {item['method']}: {item['explanation']}")
    print('TOTAL', json.dumps(dict(totals)))


if __name__ == '__main__':
    main()
