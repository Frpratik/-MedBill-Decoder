"""Print actual reference lookups and save a reproducible Phase 1 evidence file."""
import json

from medbill.reference import DEFAULT_DB, connect, lookup


def main():
    context = dict(carrier='01112', locality='05', category='nonQP',
                   setting='nonfacility', service_date='2026-07-15')
    cases = [
        ('Office visit, nonfacility', '99213', {}),
        ('Office visit, facility', '99213', {'setting':'facility'}),
        ('Office visit, QP', '99213', {'category':'QP'}),
        ('Chest X-ray, global', '71046', {}),
        ('Chest X-ray, professional component', '71046', {'modifier':'26'}),
        ('ECG', '93000', {}),
        ('July revision example', '46505', {}),
        ('Unsupported lab reference', '80053', {}),
        ('Unknown code', 'ZZZZZ', {}),
        ('Unsupported service date', '99213', {'service_date':'2026-10-01'}),
        ('Rarely/never performed setting', '71046', {'setting':'facility'}),
        ('Terminated HCPCS', 'J0135', {}),
        ('Conflicting CMS status', 'A4100', {}),
    ]
    results = [{'case':title, **lookup(code, **(context | changes))} for title,code,changes in cases]
    with connect() as db:
        counts = {row['name']:db.execute(f'SELECT count(*) FROM {row["name"]}').fetchone()[0]
                  for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    output = {'table_counts':counts, 'lookups':results}
    DEFAULT_DB.with_suffix('.examples.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
    print('case | code | description | benchmark USD | availability')
    for row in results:
        print(f'{row["case"]} | {row["code"]} | {row["description"]} | {row["benchmark_usd"]} | {row["availability"]}')
    print(json.dumps(counts,indent=2))


if __name__ == '__main__':
    main()
