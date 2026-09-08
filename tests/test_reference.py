"""Regression tests for source fidelity and unsafe lookup fallbacks.

Integration tests use only downloaded public CMS references; no patient data.
"""
import sqlite3
import unittest
import io
import zipfile

import pandas as pd

from medbill.ingest import ROOT, ARCHIVES, cents, validate_keys, validate_hcpcs_corrections
from medbill.reference import DEFAULT_DB, connect, lookup


class ParsingTests(unittest.TestCase):
    def test_money_preserves_cents(self):
        self.assertEqual(cents(pd.Series(['0000117.58','0000000.00','0000000.29'])).tolist(), [11758,0,29])

    def test_invalid_money_is_not_imputed(self):
        for value in ['', 'NA', '-1.00', '1.001', '1e2']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                cents(pd.Series([value]))

    def test_duplicate_source_keys_fail(self):
        with self.assertRaises(ValueError):
            validate_keys(pd.DataFrame({'code':['99213','99213']}), ['code'])


@unittest.skipUnless(DEFAULT_DB.exists(), 'Build the CMS reference database first')
class SourceIntegrationTests(unittest.TestCase):
    def get(self, code='99213', **changes):
        args = dict(carrier='01112', locality='05', setting='nonfacility', category='nonQP',
                    service_date='2026-07-15', modifier='')
        args.update(changes)
        return lookup(code, **args)

    def test_verified_raw_office_visit(self):
        result = self.get()
        self.assertEqual(result['description'], 'Office o/p est low 20 min')
        self.assertEqual(result['benchmark_usd'], '117.58')
        self.assertEqual(result['source']['id'], 'annual_nonQP')

    def test_hcpcs_corrections_already_in_main_workbook(self):
        with zipfile.ZipFile(ROOT / 'data/raw' / ARCHIVES['hcpcs'][0]) as archive:
            base = pd.read_excel(io.BytesIO(archive.read('HCPC2026_JUL_ANWEB_06172026.xlsx')),
                                 dtype=str, keep_default_na=False)
            corrections = pd.read_excel(io.BytesIO(archive.read('HCPC2026_JUL_ANWEB_Corrections.xlsx')),
                                        dtype=str, keep_default_na=False)
            result = validate_hcpcs_corrections(base, corrections)
            self.assertEqual(result['checked_rows'], 8)
            self.assertEqual(result['pricing_conflicts'], [{'code':'G0577',
                'workbook_price_indicator':'13','corrections_price_indicator':'11'}])
            self.assertIsNone(self.get('G0577')['benchmark_usd'])

    def test_setting_changes_reference(self):
        self.assertEqual(self.get(setting='facility')['benchmark_usd'], '64.37')

    def test_qp_is_not_nonqp(self):
        self.assertNotEqual(self.get(category='QP')['benchmark_usd'], self.get()['benchmark_usd'])

    def test_dates_never_silently_fallback(self):
        for date in ['2026-06-30','2026-10-01','2025-07-15']:
            result = self.get(service_date=date)
            self.assertEqual(result['availability'], 'unsupported_date')
            self.assertIsNone(result['benchmark_usd'])
        for date in ['2026-07-01','2026-09-30']:
            self.assertEqual(self.get(service_date=date)['availability'], 'published_benchmark')

    def test_missing_locality_and_modifier_never_fallback(self):
        for args in [dict(locality='88'),dict(modifier='26')]:
            self.assertIsNone(self.get(**args)['benchmark_usd'])

    def test_unknown_code_never_gets_price(self):
        result = self.get('ZZZZZ')
        self.assertEqual(result['availability'], 'unknown_code')
        self.assertIsNone(result['benchmark_usd'])

    def test_na_setting_does_not_use_positive_source_amount(self):
        result = self.get('71046', setting='facility')
        self.assertEqual(result['availability'], 'setting_rarely_or_never_performed')
        self.assertIsNone(result['benchmark_usd'])

    def test_terminated_hcpcs_not_used(self):
        result = self.get('J0135')
        self.assertEqual(result['availability'], 'terminated_code')
        self.assertIsNone(result['benchmark_usd'])

    def test_conflicting_cms_status_is_withheld(self):
        result = self.get('A4100')
        self.assertEqual(result['availability'], 'conflicting_status_metadata')
        self.assertIsNone(result['benchmark_usd'])

    def test_invalid_context_rejected(self):
        for args in [dict(carrier='1112'),dict(category=''),dict(setting='hospital'),dict(service_date='2026-02-30')]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.get(**args)

    def test_runtime_database_is_read_only(self):
        with connect() as db, self.assertRaises(sqlite3.OperationalError):
            db.execute("INSERT INTO build_metadata VALUES ('test','test')")

    def test_every_last_revision_matches_current_row(self):
        with connect() as db:
            failures = db.execute('''WITH ranked AS (
                SELECT *,row_number() OVER (
                    PARTITION BY category,carrier,locality,code,modifier
                    ORDER BY CASE WHEN source_id LIKE 'july_%' THEN 2 ELSE 1 END DESC
                ) AS revision_rank FROM payment_revisions)
                SELECT count(*) FROM ranked r
                LEFT JOIN payment_rates p USING(category,carrier,locality,code,modifier)
                WHERE r.revision_rank=1 AND
                    (p.code IS NULL OR r.nonfacility_cents != p.nonfacility_cents
                     OR r.facility_cents != p.facility_cents OR r.source_id != p.source_id
                     OR r.status != p.status)''').fetchone()[0]
            self.assertEqual(failures, 0)


if __name__ == '__main__':
    unittest.main()
