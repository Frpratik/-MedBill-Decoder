"""Deterministic CMS lookup. No LLMs, inferred prices, or patient records."""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import re
import sqlite3

DEFAULT_DB = Path(__file__).resolve().parents[1] / 'data/processed/reference.sqlite'
START, END = '2026-07-01', '2026-09-30'


def connect(path=DEFAULT_DB):
    db = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    return db


def lookup(code, *, carrier, locality, setting, category, service_date, modifier='', db_path=DEFAULT_DB):
    code, modifier = code.strip().upper(), modifier.strip().upper()
    if not re.fullmatch(r'[A-Z0-9]{5}', code):
        raise ValueError('Code must have five letters/digits.')
    if not re.fullmatch(r'([A-Z0-9]{2})?', modifier):
        raise ValueError('Modifier must be blank or two letters/digits.')
    if not re.fullmatch(r'\d{5}', carrier) or not re.fullmatch(r'\d{2}', locality):
        raise ValueError('Carrier/locality must be five/two digits, including leading zeros.')
    if setting not in ('facility', 'nonfacility') or category not in ('QP', 'nonQP'):
        raise ValueError('Explicit facility/nonfacility and QP/nonQP are required.')
    date = dt.date.fromisoformat(service_date).isoformat()
    result = dict(code=code, modifier=modifier, carrier=carrier, locality=locality,
                  setting=setting, category=category, service_date=date,
                  benchmark_usd=None, description=None, warnings=[])
    if not START <= date <= END:
        return result | {'availability': 'unsupported_date', 'supported_interval': [START, END]}
    with connect(db_path) as db:
        desc = db.execute('SELECT * FROM code_descriptions WHERE code=? AND modifier=?', (code, modifier)).fetchone()
        hcpcs = db.execute('SELECT * FROM hcpcs_descriptions WHERE code=?', (code,)).fetchone()
        if desc:
            result['description'] = desc['description']
            result['description_source_id'] = desc['source_id']
        if hcpcs:
            result['long_description'] = hcpcs['long_description']
            result['hcpcs_source_id'] = hcpcs['source_id']
            if not desc:
                result['description'] = hcpcs['short_description'] or hcpcs['long_description']
            if hcpcs['termination_date'] and date > hcpcs['termination_date']:
                return result | {'availability': 'terminated_code'}
            if hcpcs['added_date'] and date < hcpcs['added_date']:
                return result | {'availability': 'code_not_yet_effective'}
        row = db.execute('''SELECT * FROM payment_rates WHERE code=? AND modifier=?
            AND carrier=? AND locality=? AND category=?''',
            (code, modifier, carrier, locality, category)).fetchone()
        if row is None:
            known_code = desc or hcpcs or db.execute(
                'SELECT 1 FROM code_descriptions WHERE code=? LIMIT 1', (code,)).fetchone()
            return result | {'availability': 'no_matching_rate' if known_code else 'unknown_code'}
        row = dict(row)
        source = dict(db.execute('SELECT * FROM sources WHERE id=?', (row['source_id'],)).fetchone())
        policy = db.execute('SELECT * FROM rvu_policy WHERE code=? AND modifier=? AND category=?',
                            (code, modifier, category)).fetchone()
        result.update(source=source, source_row=row['source_row'], status=row['status'],
                      published_amount_usd=f"{row[setting + '_cents'] / 100:.2f}",
                      policy_indicators={k: row[k] for k in ('pctc', 'multiple_surgery', 'opps_indicator')})
        if policy is None:
            return result | {'availability': 'missing_policy_metadata'}
        if policy['status'] != row['status']:
            return result | {'availability': 'conflicting_status_metadata'}
        if policy[setting + '_na'] == 'NA':
            return result | {'availability': 'setting_rarely_or_never_performed'}
        if row['status'] not in ('A', 'R', 'T'):
            return result | {'availability': 'not_separately_priced_by_pfs'}
        amount = row[setting + '_cents']
        if amount <= 0:
            return result | {'availability': 'no_positive_published_rate'}
        if row['opps_indicator'] == '1':
            cap = row['opps_' + setting + '_cents']
            if cap <= 0:
                return result | {'availability': 'missing_opps_cap'}
            amount = min(amount, cap)
            result['warnings'].append('OPPS cap applied as the lower published amount.')
        if row['status'] in ('R', 'T'):
            result['warnings'].append('Restricted or conditional payment: coverage/bundling review required.')
        if row['multiple_surgery'] not in ('0', '9'):
            result['warnings'].append('Multiple-procedure adjustments may apply; this is a single-service benchmark.')
        result['warnings'].append('Medicare benchmark only; not patient responsibility or proof of an overcharge.')
        result['benchmark_usd'] = f'{amount / 100:.2f}'
        result['availability'] = 'published_benchmark'
        return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('code')
    p.add_argument('--modifier', default='')
    for name in ('carrier', 'locality', 'setting', 'category', 'service-date'):
        p.add_argument('--' + name, required=True)
    p.add_argument('--db-path', type=Path, default=DEFAULT_DB)
    args = vars(p.parse_args())
    try:
        print(json.dumps(lookup(**args), indent=2))
    except ValueError as error:
        p.error(str(error))


if __name__ == '__main__':
    main()
