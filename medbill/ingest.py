"""Build a Q3 2026 CMS reference snapshot from pinned original ZIPs.

Only public reference data is persisted. pandas handles ingestion; SQLite
provides exact indexed lookups. Source rows and revision records are retained.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import zipfile

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ARCHIVES = {
    'annual': ('pfrev26a-updated-12-29-2025.zip', 'CE670F78702767644A7D1A5888B6FD3FD9AB8EA9947C2C8192841B0091CEC867'),
    'april': ('pfrev26b-updated-03-10-2026.zip', '5366677E02E7050D8520F4D3045E4F14682DE1718B9FD4647A7D70098298B647'),
    'july': ('pfrev26c-posted-06-30-2026.zip', 'BE1222DCF3967FCD22846CD2E043EC91F00C5B089BBC0F4CA9A693072B5FEFBF'),
    'rvu': ('rvu26c-updated-06-30-2026.zip', 'D45A158E02694C1539E7F88192C611883E377181EDA86DC213359707BCACBACB'),
    'hcpcs': ('july-2026-alpha-numeric-hcpcs-file.zip', '5591FED257E4D2307C1D2DC9C66ABC8E346B1F4C076E9E48559799E2DE14B70A'),
}
PAY_COLUMNS = ['year', 'carrier', 'locality', 'code', 'modifier', 'nonfacility_cents',
               'facility_cents', 'filler', 'pctc', 'status', 'multiple_surgery',
               'therapy_nonfacility_cents', 'therapy_facility_cents', 'opps_indicator',
               'opps_nonfacility_cents', 'opps_facility_cents']
KEY = ['category', 'carrier', 'locality', 'code', 'modifier']
RATE_COLUMNS = PAY_COLUMNS + ['category', 'source_id', 'source_row']


def schema(db):
    db.executescript('''
    PRAGMA foreign_keys=ON;
    CREATE TABLE sources(id TEXT PRIMARY KEY, url TEXT NOT NULL, archive TEXT NOT NULL,
      sha256 TEXT NOT NULL, member TEXT NOT NULL, release TEXT NOT NULL,
      retrieved_date TEXT NOT NULL, copyright_notice TEXT NOT NULL);
    CREATE TABLE code_descriptions(code TEXT NOT NULL, modifier TEXT NOT NULL,
      description TEXT NOT NULL, source_id TEXT NOT NULL REFERENCES sources(id),
      source_row INTEGER NOT NULL, PRIMARY KEY(code,modifier)) WITHOUT ROWID;
    CREATE TABLE rvu_policy(code TEXT NOT NULL, modifier TEXT NOT NULL, category TEXT NOT NULL,
      status TEXT NOT NULL, nonfacility_na TEXT NOT NULL, facility_na TEXT NOT NULL,
      source_id TEXT NOT NULL REFERENCES sources(id), source_row INTEGER NOT NULL,
      PRIMARY KEY(code,modifier,category)) WITHOUT ROWID;
    CREATE TABLE hcpcs_descriptions(code TEXT PRIMARY KEY, long_description TEXT NOT NULL,
      short_description TEXT NOT NULL, added_date TEXT NOT NULL, action_date TEXT NOT NULL,
      termination_date TEXT NOT NULL, action TEXT NOT NULL, coverage TEXT NOT NULL,
      source_id TEXT NOT NULL REFERENCES sources(id), source_row INTEGER NOT NULL);
    CREATE TABLE hcpcs_modifiers AS SELECT * FROM hcpcs_descriptions WHERE 0;
    CREATE TABLE ingestion_issues(kind TEXT NOT NULL, source_id TEXT NOT NULL, count INTEGER NOT NULL,
      detail TEXT NOT NULL);
    CREATE TABLE build_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
    ''')
    columns = ','.join(f'{c} ' + ('INTEGER NOT NULL CHECK(' + c + '>=0)' if c.endswith('_cents') or c == 'source_row'
                                else 'TEXT NOT NULL') for c in RATE_COLUMNS)
    db.execute(f'''CREATE TABLE payment_rates({columns},
        FOREIGN KEY(source_id) REFERENCES sources(id), PRIMARY KEY({','.join(KEY)})) WITHOUT ROWID''')
    db.execute(f'CREATE TABLE payment_revisions AS SELECT * FROM payment_rates WHERE 0')
    db.executemany('INSERT INTO build_metadata VALUES (?,?)', [
        ('supported_start', '2026-07-01'), ('supported_end', '2026-09-30'),
        ('meaning', 'Q3 release snapshot; not historical effective-date adjudication'),
        ('patient_data', 'none'), ('schema_version', '1')])


def add_source(db, kind, member, source_id, notice=''):
    name, digest = ARCHIVES[kind]
    db.execute('INSERT INTO sources VALUES (?,?,?,?,?,?,?,?)',
               (source_id, 'https://www.cms.gov/files/zip/' + name, name, digest, member,
                kind, '2026-09-08', notice))


def cents(series):
    # String arithmetic avoids binary floating-point errors in source money.
    if not series.str.fullmatch(r'\d+\.\d{2}').all():
        raise ValueError('Invalid or missing source monetary amount')
    return series.str.replace('.', '', regex=False).astype('int64')


def validate_keys(frame, columns):
    if frame.duplicated(columns).any():
        raise ValueError('Duplicate source keys; refusing to choose a record silently')


def validate_hcpcs_corrections(base, corrections):
    """Verify code/description corrections; report pricing metadata conflicts.

    Fail if a future source disagrees. Normalize only case/whitespace when
    comparing descriptions; keep the published main-workbook text unchanged.
    """
    indexed = base.set_index('HCPC')
    pricing_conflicts = []
    normalize = lambda value: ' '.join(value.split()).casefold()
    for _, row in corrections.iterrows():
        code, action = row['HCPCS/MOD Code'], row['Action']
        if action.startswith('Remove'):
            if code in indexed.index:
                raise ValueError(f'Unapplied HCPCS removal: {code}')
        elif action.startswith('Revise') or action == 'Add':
            if code not in indexed.index or normalize(indexed.loc[code, 'LONG DESCRIPTION']) != normalize(row['Long Description']):
                raise ValueError(f'Unapplied HCPCS description correction: {code}')
            if action == 'Add':
                for actual, expected in [('SHORT DESCRIPTION','Short Description'), ('TOS1','TOS'),
                                         ('BETOS','BETOS'), ('COV','Coverage')]:
                    if normalize(indexed.loc[code,actual]) != normalize(row[expected]):
                        raise ValueError(f'Unapplied HCPCS addition field: {code} {actual}')
                if indexed.loc[code,'PRICE1'] != row['Pricing']:
                    pricing_conflicts.append({'code':code, 'workbook_price_indicator':indexed.loc[code,'PRICE1'],
                                              'corrections_price_indicator':row['Pricing']})
        else:
            raise ValueError(f'Unknown HCPCS correction action: {action}')
    return {'checked_rows':len(corrections), 'pricing_conflicts':pricing_conflicts}


def ingest_payments(db, raw, kind, category):
    with zipfile.ZipFile(raw / ARCHIVES[kind][0]) as outer:
        nested = [n for n in outer.namelist() if n.endswith('_' + category + '.zip')]
        if len(nested) != 1:
            raise ValueError('Expected one category-specific payment archive')
        with zipfile.ZipFile(io.BytesIO(outer.read(nested[0]))) as inner:
            member, = [n for n in inner.namelist() if n.lower().endswith('.txt')]
            source_id = f'{kind}_{category}'
            add_source(db, kind, nested[0] + '!' + member, source_id)
            records, trailers, offset = 0, [], 0
            db.execute('CREATE TEMP TABLE seen(carrier TEXT,locality TEXT,code TEXT,modifier TEXT,PRIMARY KEY(carrier,locality,code,modifier)) WITHOUT ROWID')
            with inner.open(member) as stream:
                for frame in pd.read_csv(stream, names=PAY_COLUMNS, dtype=str, keep_default_na=False,
                                         chunksize=50000, encoding='cp1252'):
                    frame['source_row'] = range(offset + 1, offset + len(frame) + 1)
                    offset += len(frame)
                    is_trailer = frame.year.str.startswith('TRL')
                    trailers.extend(frame.loc[is_trailer, 'year'].tolist())
                    frame = frame.loc[~is_trailer].copy()
                    for col in PAY_COLUMNS:
                        frame[col] = frame[col].str.strip()
                    for col, pattern in [('year', '2026'), ('carrier', r'\d{5}'), ('locality', r'\d{2}'),
                                         ('code', r'[A-Z0-9]{5}'), ('modifier', r'([A-Z0-9]{2})?')]:
                        if not frame[col].str.fullmatch(pattern).all():
                            raise ValueError(f'Invalid {col} in {source_id}')
                    validate_keys(frame, ['carrier', 'locality', 'code', 'modifier'])
                    db.executemany('INSERT INTO seen VALUES (?,?,?,?)',
                                   frame[['carrier', 'locality', 'code', 'modifier']].itertuples(index=False,name=None))
                    for col in PAY_COLUMNS:
                        if col.endswith('_cents'):
                            frame[col] = cents(frame[col])
                    frame['category'], frame['source_id'] = category, source_id
                    frame = frame[RATE_COLUMNS]
                    if kind != 'annual':
                        frame.to_sql('payment_revisions', db, if_exists='append', index=False)
                    updates = ','.join(f'{c}=excluded.{c}' for c in RATE_COLUMNS if c not in KEY)
                    sql = f"INSERT INTO payment_rates VALUES ({','.join('?' for _ in RATE_COLUMNS)})"
                    if kind != 'annual':
                        sql += f" ON CONFLICT({','.join(KEY)}) DO UPDATE SET {updates}"
                    db.executemany(sql, frame.itertuples(index=False, name=None))
                    records += len(frame)
            db.execute('DROP TABLE seen')
            if len(trailers) != 4:
                raise ValueError(f'Unexpected trailer count in {source_id}: {len(trailers)}')
            db.execute('UPDATE sources SET copyright_notice=? WHERE id=?', ('\n'.join(trailers), source_id))
            db.execute('INSERT INTO ingestion_issues VALUES (?,?,?,?)',
                       ('excluded_copyright_trailers', source_id, len(trailers), '\n'.join(trailers)))
            db.commit()
            print(f'{source_id}: {records:,} data rows; {len(trailers)} copyright trailers excluded', flush=True)
            return records


def ingest_descriptions(db, raw):
    with zipfile.ZipFile(raw / ARCHIVES['rvu'][0]) as z:
        for category, suffix in [('nonQP', 'nonQPP'), ('QP', 'QPP')]:
            member = f'PPRRVU2026_Jul_{suffix}.csv'
            content = z.read(member).decode('cp1252')
            if 'HCPCS,MOD,DESCRIPTION' not in content.splitlines()[9]:
                raise ValueError('RVU header moved; review source schema')
            f = pd.read_csv(io.StringIO(content), skiprows=10, header=None, dtype=str, keep_default_na=False)
            if len(f.columns) != 32:
                raise ValueError('RVU column count changed')
            f = f.map(lambda v: v.strip())
            validate_keys(f, [0, 1])
            source_id = 'rvu_' + category
            add_source(db, 'rvu', member, source_id, '\n'.join(content.splitlines()[1:3]))
            for index, row in f.iterrows():
                existing = db.execute('SELECT description FROM code_descriptions WHERE code=? AND modifier=?', (row[0],row[1])).fetchone()
                if existing and existing[0] != row[2]:
                    raise ValueError('Conflicting QP/non-QP descriptions')
                db.execute('INSERT OR IGNORE INTO code_descriptions VALUES (?,?,?,?,?)',
                           (row[0],row[1],row[2],source_id,index+11))
                db.execute('INSERT INTO rvu_policy VALUES (?,?,?,?,?,?,?,?)',
                           (row[0],row[1],category,row[3],row[7],row[9],source_id,index+11))
            print(f'{source_id}: {len(f):,} rows', flush=True)
    with zipfile.ZipFile(raw / ARCHIVES['hcpcs'][0]) as z:
        member = 'HCPC2026_JUL_ANWEB_06172026.xlsx'
        f = pd.read_excel(io.BytesIO(z.read(member)), dtype=str, keep_default_na=False).map(lambda v: v.strip())
        validate_keys(f, ['HCPC'])
        corrections = pd.read_excel(io.BytesIO(z.read('HCPC2026_JUL_ANWEB_Corrections.xlsx')),
                                    dtype=str, keep_default_na=False)
        correction_check = validate_hcpcs_corrections(f, corrections)
        if not f.RECID.isin(['3', '7']).all():
            raise ValueError('Unexpected HCPCS continuation records in workbook')
        add_source(db, 'hcpcs', member, 'hcpcs')
        db.execute('INSERT INTO ingestion_issues VALUES (?,?,?,?)',
                   ('hcpcs_correction_pricing_conflicts','hcpcs',len(correction_check['pricing_conflicts']),
                    json.dumps(correction_check)))
        for index, row in f.iterrows():
            dates = []
            for col in ['ADD DT', 'ACT EFF DT', 'TERM DT']:
                value = row[col]
                dates.append(pd.to_datetime(value, format='%Y%m%d').date().isoformat() if value else '')
            table = 'hcpcs_descriptions' if row.RECID == '3' else 'hcpcs_modifiers'
            db.execute(f'INSERT INTO {table} VALUES (?,?,?,?,?,?,?,?,?,?)',
                       (row.HCPC, row['LONG DESCRIPTION'], row['SHORT DESCRIPTION'], *dates,
                        row['ACTION CD'],row.COV,'hcpcs',index+2))
        print(f'hcpcs: {len(f):,} rows ({sum(f.RECID == "3"):,} procedures, {sum(f.RECID == "7"):,} modifiers)', flush=True)
    db.commit()


def audit(db, input_counts):
    counts = {t: db.execute(f'SELECT count(*) FROM {t}').fetchone()[0] for t in
              ['payment_rates','payment_revisions','code_descriptions','rvu_policy','hcpcs_descriptions','hcpcs_modifiers','sources']}
    gaps = db.execute('''SELECT DISTINCT p.code,p.modifier FROM payment_rates p LEFT JOIN
        code_descriptions d USING(code,modifier) WHERE d.code IS NULL ORDER BY p.code,p.modifier''').fetchall()
    policy_gaps = db.execute('''SELECT count(*) FROM payment_rates p LEFT JOIN rvu_policy r
        USING(code,modifier,category) WHERE r.code IS NULL''').fetchone()[0]
    conflicts = db.execute('''SELECT count(*) FROM payment_rates p JOIN rvu_policy r
        USING(code,modifier,category) WHERE p.status != r.status''').fetchone()[0]
    for kind, count, detail in [('missing_descriptions',len(gaps),json.dumps(gaps)),
                               ('missing_policy_rows',policy_gaps,'Withhold benchmark when missing'),
                               ('status_conflicts',conflicts,'Withhold benchmark on conflicting metadata')]:
        db.execute('INSERT INTO ingestion_issues VALUES (?,?,?,?)', (kind,'all',count,detail))
    result = {'input_rows':input_counts,'table_counts':counts,'missing_description_keys':gaps,
              'missing_policy_rate_rows':policy_gaps,'status_conflict_rate_rows':conflicts,
              'distinct_payment_codes':db.execute('SELECT count(DISTINCT code) FROM payment_rates').fetchone()[0],
              'carrier_locality_pairs':db.execute('SELECT count(*) FROM (SELECT DISTINCT carrier,locality FROM payment_rates)').fetchone()[0],
              'current_rows_by_source':dict(db.execute('SELECT source_id,count(*) FROM payment_rates GROUP BY source_id')),
              'status_counts':dict(db.execute('SELECT status,count(*) FROM payment_rates GROUP BY status')),
              'issues':[dict(zip(['kind','source_id','count','detail'],row)) for row in db.execute('SELECT * FROM ingestion_issues')],
              'integrity_check':db.execute('PRAGMA integrity_check').fetchone()[0],
              'foreign_key_violations':db.execute('PRAGMA foreign_key_check').fetchall()}
    if result['integrity_check'] != 'ok' or result['foreign_key_violations']:
        raise ValueError('SQLite validation failed')
    db.commit()
    return result


def build(raw, output):
    for name, expected in ARCHIVES.values():
        actual = hashlib.file_digest((raw / name).open('rb'), 'sha256').hexdigest().upper()
        if actual != expected:
            raise ValueError(f'Source SHA-256 mismatch: {name}; review before updating pin')
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix('.building.sqlite')
    if temporary.exists():
        temporary.unlink()
    db = sqlite3.connect(temporary)
    try:
        # Only the disposable build file uses relaxed journaling. The validated
        # artifact replaces the previous database after all checks pass.
        db.execute('PRAGMA journal_mode=MEMORY')
        db.execute('PRAGMA synchronous=OFF')
        schema(db)
        counts = {}
        for kind in ['annual', 'april', 'july']:
            for category in ['nonQP', 'QP']:
                counts[f'{kind}_{category}'] = ingest_payments(db, raw, kind, category)
        ingest_descriptions(db, raw)
        db.execute('CREATE INDEX rates_code ON payment_rates(code,modifier,category)')
        result = audit(db, counts)
        schema_text = '\n\n'.join(row[0] + ';' for row in db.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type,name"))
    finally:
        db.close()
    temporary.replace(output)
    output.with_suffix('.audit.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    output.with_suffix('.schema.sql').write_text(schema_text, encoding='utf-8')
    print(json.dumps(result, indent=2), flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--raw', type=Path, default=ROOT/'data/raw')
    p.add_argument('--output', type=Path, default=ROOT/'data/processed/reference.sqlite')
    args=p.parse_args()
    build(args.raw,args.output)


if __name__ == '__main__':
    main()
