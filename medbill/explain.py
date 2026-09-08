"""Fully local description templates with explicit unknown-code handling.

No model or external API is used for explanations.
Only synthetic inputs are supported. No runtime input/output files are written.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

from medbill.reference import DEFAULT_DB, connect

PLAIN = {
    '99213': 'An office or outpatient visit with an established patient.',
    '99214': 'An office or outpatient visit with an established patient.',
    '71046': 'A chest X-ray with two views.',
    '93000': 'An electrocardiogram (ECG), a recording of electrical activity in the heart.',
    '97110': 'Therapeutic exercises.',
    '80053': 'A comprehensive metabolic panel, a group of blood tests.',
    'J1885': 'An injection of ketorolac tromethamine; the code describes each 15 mg billing unit.',
}


class Explainer:
    def __init__(self, *, synthetic, db_path=DEFAULT_DB):
        if synthetic is not True:
            raise ValueError('Only synthetic bill data is supported')
        self.db_path = db_path

    def explain_item(self, item):
        if item['availability'] in ('ocr_review_required', 'invalid_input'):
            return {'method': 'review_required', 'explanation':
                'This line needs a clearer image or a corrected reading before it can be explained.',
                'question': 'Can you provide a clear itemized copy showing the code, units and charge?'}
        if item['availability'] in ('unsupported_date', 'terminated_code', 'code_not_yet_effective'):
            return {'method': 'review_required', 'explanation':
                'The code or service date is outside the supported reference period.',
                'question': 'Can you confirm the service date and the code used on that date?'}
        with connect(self.db_path) as db:
            desc = db.execute('SELECT * FROM code_descriptions WHERE code=? AND modifier=?',
                              (item['code'], item.get('modifier') or '')).fetchone()
            hcpcs = db.execute('SELECT * FROM hcpcs_descriptions WHERE code=?', (item['code'],)).fetchone()
        if desc or hcpcs:
            row = dict(hcpcs or desc)
            official = row.get('long_description') or row['description']
            # Hand-written paraphrases are used only with a real local description.
            wording = PLAIN.get(item['code'], f'The local CMS description is: {official}.')
            if item.get('modifier'):
                wording += f' Modifier {item["modifier"]} is listed; confirm what part of the service it represents.'
            result = {'method': 'template', 'explanation': wording,
                'official_description': official, 'description_source_id': row['source_id'],
                'question': 'Can you explain what this service and its billed units include?'}
        else:
            result = {'method': 'unknown_code', 'reason': 'no_local_description'}
        if result['method'] == 'unknown_code':
            result |= {'explanation': 'No local code description is available. The service remains unverified.',
                       'question': 'Can you confirm the code and describe the service in plain language?'}
        if item['availability'] == 'compared':
            result['benchmark_explanation'] = (
                f'The charge per unit is ${item["unit_charge_usd"]}; the matched Medicare rate is '
                f'${item["unit_benchmark_usd"]}. The positive line difference is '
                f'${item["amount_above_benchmark_usd"]}. This is not proof of an overcharge or savings.')
            if item['flag'] is True:
                result['question'] = 'Why does this unit charge exceed both the local Medicare rate and the geographic 95th percentile?'
        else:
            result['benchmark_explanation'] = 'No usable price comparison is available for this line; no difference is estimated.'
        return result

    def explain(self, report):
        items = [item | {'explanation_result': self.explain_item(item)} for item in report['items']]
        counts = Counter(i['explanation_result']['method'] for i in items)
        return report | {'items': items, 'explanation_summary': {'total_rows': len(items),
            'counts': dict(counts), 'percent_of_all_rows': {
                key: round(100 * counts[key] / len(items), 2) if items else 0
                for key in ('template', 'review_required', 'unknown_code')}}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    parser.add_argument('--synthetic', action='store_true', required=True)
    args = parser.parse_args()
    result = Explainer(synthetic=args.synthetic).explain(
        json.loads(args.report.read_text(encoding='utf-8')))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
