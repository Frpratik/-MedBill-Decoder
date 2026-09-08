"""Statistical boundary tests use labeled synthetic arrays; integration uses CMS."""
from copy import deepcopy
from decimal import Decimal
import json
import unittest

from medbill.compare import Comparator, distribution
from medbill.ocr import ROOT


class DistributionTests(unittest.TestCase):
    def test_nearest_rank_boundary(self):
        # Synthetic unit-test cents, NOT a Medicare reference dataset.
        values=list(range(100,2100,100))
        at=distribution(values,1900)
        above=distribution(values,1901)
        self.assertEqual(at['p95_usd'],'19.00')
        self.assertFalse(at['flag'])
        self.assertTrue(above['flag'])
        self.assertEqual(at['percentile_rank'],'92.50')

    def test_small_cohort_has_no_flag(self):
        result=distribution([100,200],10000)
        self.assertIsNone(result['flag'])
        self.assertEqual(result['availability'],'insufficient_cohort')

    def test_uniform_rates_have_no_statistical_flag(self):
        result=distribution([100]*20,10000)
        self.assertIsNone(result['flag'])
        self.assertEqual(result['availability'],'no_geographic_variation')

    def test_tied_midrank(self):
        result=distribution([100]*10+[200]*10,100)
        self.assertEqual(result['percentile_rank'],'25.00')


class ComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine=Comparator(carrier='01112',locality='05',setting='nonfacility',category='nonQP')
        cls.clean=json.loads((ROOT/'docs/phase2/01_clean.json').read_text())
        cls.skewed=json.loads((ROOT/'docs/phase2/02_skewed.json').read_text())
        cls.degraded=json.loads((ROOT/'docs/phase2/03_degraded.json').read_text())

    def test_known_local_difference(self):
        item=self.engine.compare_item(self.clean['items'][0])
        self.assertEqual(item['unit_benchmark_usd'],'117.58')
        self.assertEqual(item['amount_above_benchmark_usd'],'132.42')
        self.assertEqual(item['statistics']['p95_usd'],'111.96')
        self.assertTrue(item['flag'])

    def test_locality_rate_itself_is_not_flagged(self):
        row=deepcopy(self.clean['items'][0]); row['charged_cents']=11758
        result=self.engine.compare_item(row)
        self.assertFalse(result['flag'])
        self.assertEqual(result['amount_above_benchmark_usd'],'0.00')
        self.assertTrue(result['statistics']['flag'])  # Local rate is above national p95.

    def test_below_benchmark_is_zero_excess(self):
        row=deepcopy(self.clean['items'][0]); row['charged_cents']=5000
        result=self.engine.compare_item(row)
        self.assertFalse(result['flag'])
        self.assertEqual(result['amount_above_benchmark_usd'],'0.00')

    def test_quantity_normalizes_charge(self):
        result=self.engine.compare_item(self.skewed['items'][0])
        self.assertEqual(result['unit_charge_usd'],'90.00')
        self.assertEqual(result['line_benchmark_usd'],'71.82')
        self.assertEqual(result['amount_above_benchmark_usd'],'108.18')

    def test_review_rows_never_repaired_from_raw_values(self):
        row=deepcopy(self.skewed['items'][1])
        self.assertEqual(row['raw_columns']['quantity'],'1')
        result=self.engine.compare_item(row)
        self.assertEqual(result['availability'],'ocr_review_required')
        self.assertIsNone(result['flag'])

    def test_absent_rates_remain_unknown(self):
        result=self.engine.compare_item(self.clean['items'][3])
        self.assertEqual(result['availability'],'no_matching_rate')
        self.assertIsNone(result['amount_above_benchmark_usd'])

    def test_invalid_numeric_input_rejected(self):
        for quantity in ['0','-1','NaN','Infinity',None]:
            row=deepcopy(self.clean['items'][0]); row['quantity']=quantity
            self.assertEqual(self.engine.compare_item(row)['availability'],'invalid_input')
        for charge in [-1,True,'25000',25000.5]:
            row=deepcopy(self.clean['items'][0]); row['charged_cents']=charge
            self.assertEqual(self.engine.compare_item(row)['availability'],'invalid_input')

    def test_cohort_one_observation_per_locality_and_exact_dimensions(self):
        c=self.engine.cohort('71046','26','2026-07-15')
        pairs={(m['carrier'],m['locality']) for m in c['members']}
        self.assertEqual(len(c['members']),109)
        self.assertEqual(len(pairs),109)
        self.assertEqual(c['definition']['modifier'],'26')
        self.assertEqual(c['definition']['category'],'nonQP')
        local=next(m for m in c['members'] if m['carrier']=='01112' and m['locality']=='05')
        self.assertEqual(local['benchmark_cents'],1159)

    def test_bill_summaries_exclude_unpriced_and_uncertain_rows(self):
        for extraction,compared,excluded,expected in [(self.clean,3,1,'384.44'),(self.skewed,2,2,'223.96'),(self.degraded,1,4,'153.60')]:
            result=self.engine.compare(extraction)['summary']
            self.assertEqual(result['compared_rows'],compared)
            self.assertEqual(result['excluded_rows'],excluded)
            self.assertEqual(result['amount_above_medicare_benchmark_usd'],expected)

    def test_no_comparable_rows_does_not_imply_zero(self):
        result=self.engine.compare({'items':[self.clean['items'][3]]})
        self.assertIsNone(result['summary']['amount_above_medicare_benchmark_usd'])

    def test_unsupported_date_excluded(self):
        row=deepcopy(self.clean['items'][0]); row['service_date']='2025-01-01'
        self.assertEqual(self.engine.compare_item(row)['availability'],'unsupported_date')


if __name__=='__main__': unittest.main()
