"""Real OCR edge-case and streaming-limit regression checks."""
import asyncio
import unittest
from fastapi.testclient import TestClient
from starlette.requests import Request
from fastapi import HTTPException
from medbill.app import app, decode_upload, processing
from medbill.edge_samples import fixtures
from medbill.ocr import MAX_BYTES

PARAMS=dict(synthetic='true',carrier='01112',locality='05',setting='nonfacility',category='nonQP')


class EdgeCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs=fixtures()

    def test_real_edge_cases_do_not_invent_comparisons(self):
        with TestClient(app) as client:
            for name,data in self.inputs.items():
                with self.subTest(name=name):
                    response=client.post('/api/decode',params=PARAMS,content=data,
                        headers={'content-type':'application/octet-stream'})
                    self.assertEqual(response.status_code,200)
                    report=response.json()
                    self.assertIsNone(report['summary']['amount_above_medicare_benchmark_usd'])
                    self.assertEqual(report['summary']['flagged_rows'],0)
                    if name in ('blank','severely_blurred'):
                        self.assertEqual(report['outcome'],'no_service_rows')
                        self.assertEqual(report['items'],[])
                    else:
                        self.assertEqual(len(report['items']),1)
                        self.assertEqual(report['items'][0]['availability'],name)
                        self.assertEqual(report['outcome'],'no_comparable_rows')

    def test_streamed_limit_without_content_length(self):
        async def scenario():
            count=0
            async def receive():
                nonlocal count
                count+=1
                return {'type':'http.request','body':b'x'*(1024*1024),'more_body':True}
            request=Request({'type':'http','headers':[(b'content-type',b'application/octet-stream')]},receive)
            with self.assertRaises(HTTPException) as caught:
                await decode_upload(request,**PARAMS)
            self.assertEqual(caught.exception.status_code,413)
            self.assertEqual(count,21)
            self.assertFalse(processing.locked())
        asyncio.run(scenario())

    def test_busy_job_rejected_before_body_read(self):
        async def scenario():
            async def receive():
                self.fail('Busy request must not consume a bill body')
            request=Request({'type':'http','headers':[(b'content-type',b'application/octet-stream')]},receive)
            async with processing:
                with self.assertRaises(HTTPException) as caught:
                    await decode_upload(request,**PARAMS)
                self.assertEqual(caught.exception.status_code,429)
        asyncio.run(scenario())

    def test_corrupt_upload_then_good_upload_releases_gate(self):
        with TestClient(app) as client:
            for data,expected in [(b'broken',422),(self.inputs['blank'],200)]:
                response=client.post('/api/decode',params=PARAMS,content=data,
                                    headers={'content-type':'application/octet-stream'})
                self.assertEqual(response.status_code,expected)
            self.assertFalse(processing.locked())


if __name__=='__main__':
    unittest.main()
