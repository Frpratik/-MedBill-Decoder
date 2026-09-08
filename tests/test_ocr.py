"""Parser regressions and actual local Tesseract runs on synthetic fixtures."""
import io
import os
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image

from medbill.ocr import OCRError, ROOT, extract, preprocess, rasterize, rotate, tesseract_path
from medbill.parser import money, parse_text, parse_lines


class ParserTests(unittest.TestCase):
    def test_exact_amount_and_quantity(self):
        item=parse_text('07/15/2026 99213 Office visit 2 $1,250.29')['items'][0]
        self.assertEqual((item['code'],item['quantity'],item['charged_cents']),('99213','2',125029))

    def test_modifier_preserved(self):
        item=parse_text('07/15/2026 71046-26 Chest X-ray 1 $75.00')['items'][0]
        self.assertEqual((item['code'],item['modifier']),('71046','26'))

    def test_multiple_prices_without_headers_withheld(self):
        item=parse_text('07/15/2026 97110 Therapy 2 $90.00 $180.00')['items'][0]
        self.assertIsNone(item['charged_cents'])
        self.assertIn('ambiguous_amount_columns',item['issues'])

    def test_quantity_never_defaults_to_one(self):
        item=parse_text('07/15/2026 99213 Office visit $250.00')['items'][0]
        self.assertIsNone(item['quantity'])

    def test_headerless_layout_requires_review(self):
        item=parse_text('07/15/2026 99213 Office visit 1 $250.00')['items'][0]
        self.assertEqual(item['status'],'needs_review')
        self.assertIn('unverified_layout_without_headers',item['issues'])

    def test_credit_never_becomes_positive_charge(self):
        item=parse_text('07/15/2026 99213 Office visit 1 -$25.00')['items'][0]
        self.assertIsNone(item['charged_cents'])

    def test_total_not_parsed_as_service(self):
        result=parse_text('Total charges: $500.00\nInsurance payments: $100.00\nPatient balance: $400.00')
        self.assertEqual(result['items'],[])

    def test_invalid_date_flagged(self):
        item=parse_text('02/30/2026 99213 Office visit 1 $250.00')['items'][0]
        self.assertIsNone(item['service_date'])

    def test_missing_code_keeps_row(self):
        item=parse_text('07/15/2026 ????? Unknown service 1 $88.00')['items'][0]
        self.assertIsNone(item['code'])
        self.assertEqual(item['charged_cents'],8800)

    def test_malformed_money_not_repaired(self):
        for value in ['$12.OO','$1,23.45','$10.001','-$5.00','($5.00)']:
            self.assertIsNone(money(value))


class ImageTests(unittest.TestCase):
    def test_empty_and_invalid_inputs_rejected(self):
        for data in [b'',b'not an image',b'%PDF-broken']:
            with self.subTest(data=data),self.assertRaises(OCRError):
                list(rasterize(data))

    def test_preprocess_blank_has_no_rotation(self):
        image=Image.new('RGB',(800,1000),'white')
        result,metadata=preprocess(image)
        self.assertEqual(metadata['deskew_correction_degrees'],0)
        self.assertEqual(int(result.min()),255)


class RealOCRTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Deliberately fail instead of claiming a pass when the engine is absent.
        tesseract_path()
        cls.clean=extract((ROOT/'output/pdf/01_clean.pdf').read_bytes())
        cls.skewed=extract((ROOT/'samples/02_skewed.png').read_bytes())
        cls.degraded=extract((ROOT/'output/pdf/03_degraded.pdf').read_bytes())

    def test_clean_four_rows_exact(self):
        self.assertEqual(self.clean['summary']['parsed_rows'],4)
        self.assertEqual([(i['code'],i['charged_cents']) for i in self.clean['items']],
                         [('99213',25000),('71046',18000),('93000',13500),('80053',9500)])

    def test_skew_and_unit_price_column(self):
        self.assertAlmostEqual(self.skewed['pages'][0]['deskew_correction_degrees'],-3,delta=.3)
        item=self.skewed['items'][0]
        self.assertEqual((item['quantity'],item['charged_cents']),('2',18000))
        self.assertEqual(item['raw_columns']['unit_price'],'$90.00')

    def test_damaged_fields_not_invented(self):
        items=self.degraded['items']
        self.assertEqual(len(items),5)
        self.assertIsNone(items[2]['code'])
        self.assertIsNone(items[3]['quantity'])
        self.assertEqual(items[3]['charged_cents'],9500)
        self.assertIsNone(items[4]['charged_cents'])
        self.assertTrue(all(i['status']=='needs_review' for i in items[2:]))

    def test_raw_misrecognition_is_retained(self):
        item=self.degraded['items'][2]
        self.assertTrue(item['raw_columns']['code'])
        self.assertIn('low_confidence_code',item['issues'])

    def test_summary_lines_excluded(self):
        self.assertEqual(len(self.clean['items']),4)
        self.assertEqual(sum(i['reason']=='summary_not_line_item' for i in self.clean['ignored_lines']),3)

    def test_extract_writes_no_files_in_working_directory(self):
        original=Path.cwd()
        image=Image.new('RGB',(400,500),'white')
        buffer=io.BytesIO(); image.save(buffer,format='PNG')
        with tempfile.TemporaryDirectory() as folder:
            try:
                os.chdir(folder)
                result=extract(buffer.getvalue())
                self.assertEqual(list(Path(folder).iterdir()),[])
                self.assertEqual(result['items'],[])
            finally:
                os.chdir(original)


if __name__=='__main__': unittest.main()
