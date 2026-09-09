"""HTTP contract and real OCR integration; no substituted pipeline outputs."""
import json
from pathlib import Path
import unittest
from fastapi.testclient import TestClient
from medbill.app import app, SAMPLES
from medbill.ocr import MAX_BYTES

PARAMS = dict(synthetic='true', carrier='01112', locality='05', setting='nonfacility', category='nonQP')


class AppTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def post(self, data=b'not a bill', params=None, headers=None):
        return self.client.post('/api/decode', params=params or PARAMS, content=data,
                                headers=headers or {'content-type': 'application/octet-stream'})

    def test_page_and_local_assets(self):
        for path in ['/', '/static/app.js', '/static/style.css']:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers['cache-control'], 'no-store')
        self.assertEqual(self.client.get('/docs').status_code, 404)

    def test_localities_are_real_unique_pairs(self):
        values = self.client.get('/api/localities').json()
        self.assertEqual(len(values), 109)
        self.assertEqual(len({(r['carrier'],r['locality']) for r in values}),109)

    def test_attestation_and_context_required(self):
        self.assertEqual(self.post(params=PARAMS | {'synthetic':'false'}).status_code,422)
        self.assertEqual(self.post(params=PARAMS | {'locality':'99'}).status_code,422)
        self.assertEqual(self.post(params=PARAMS | {'setting':'hospital'}).status_code,422)

    def test_upload_failures(self):
        self.assertEqual(self.post(data=b'').status_code,400)
        self.assertEqual(self.post().status_code,422)
        self.assertEqual(self.post(headers={'content-type':'multipart/form-data'}).status_code,415)
        self.assertEqual(self.post(headers={'content-type':'application/octet-stream',
                                           'content-length':str(MAX_BYTES+1)}).status_code,413)

    def test_cross_origin_rejected(self):
        response=self.post(headers={'content-type':'application/octet-stream','origin':'https://example.com'})
        self.assertEqual(response.status_code,403)

    def test_samples_whitelisted(self):
        self.assertEqual(self.client.get('/api/samples/not-a-sample').status_code,422)
        self.assertEqual(self.client.get('/api/samples/clean').content, SAMPLES['clean'].read_bytes())

    def test_all_three_real_uploads_match_prior_comparison(self):
        for sample, stem in [('clean','01_clean'),('skewed','02_skewed'),('degraded','03_degraded')]:
            with self.subTest(sample=sample):
                response=self.post(data=SAMPLES[sample].read_bytes())
                self.assertEqual(response.status_code,200,response.text[:300])
                report=response.json()
                prior=json.loads(Path(f'docs/phase3/{stem}.json').read_text(encoding='utf-8'))
                self.assertEqual(report['summary'],prior['summary'])
                self.assertEqual(report['ocr']['engine'],'Tesseract')
                self.assertEqual(report['ocr']['page_count'],1)
                self.assertTrue(all('explanation_result' in row for row in report['items']))


if __name__ == '__main__':
    unittest.main()
