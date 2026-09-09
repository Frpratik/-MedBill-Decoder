"""Local-only FastAPI app. Upload bytes are bounded and never spooled to disk."""
import asyncio
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware

from medbill.compare import Comparator
from medbill.explain import Explainer
from medbill.ocr import MAX_BYTES, OCRError, extract
from medbill.reference import connect

ROOT = Path(__file__).resolve().parents[1]
app = FastAPI(title='MedBill Decoder', docs_url=None, redoc_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', 'testserver'])
app.mount('/static', StaticFiles(directory=ROOT / 'web'), name='static')
# PDFium is not thread-safe; a single job also bounds CPU/memory for this local demo.
processing = asyncio.Lock()
SAMPLES = {'clean': ROOT / 'output/pdf/01_clean.pdf',
           'skewed': ROOT / 'samples/02_skewed.png',
           'degraded': ROOT / 'output/pdf/03_degraded.pdf'}


@app.middleware('http')
async def local_headers(request, call_next):
    if request.method == 'POST' and request.headers.get('origin') not in (
            None, f'http://{request.headers.get("host")}'):
        return JSONResponse({'detail': 'Use the local app to submit a sample.'}, status_code=403)
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'")
    return response


@app.get('/')
def home():
    return FileResponse(ROOT / 'web/index.html')


@app.get('/api/localities')
def localities():
    with connect() as db:
        return [dict(row) for row in db.execute(
            'SELECT DISTINCT carrier,locality FROM payment_rates ORDER BY carrier,locality')]


@app.get('/api/samples/{sample}')
def sample_file(sample: Literal['clean', 'skewed', 'degraded']):
    return FileResponse(SAMPLES[sample], media_type='image/png' if sample == 'skewed' else 'application/pdf')


def decode(data, context):
    extraction = extract(data)
    report = Explainer(synthetic=True).explain(Comparator(**context).compare(extraction))
    report['ocr'] = {'engine': extraction['engine'], 'page_count': len(extraction['pages']),
                     'candidate_rows': len(extraction['items'])}
    report['notice'] = 'Synthetic samples only. Processing is local. Uploads and reports are not saved by the app.'
    return report


@app.post('/api/decode')
async def decode_upload(request: Request, synthetic: Literal['true'],
                        setting: Literal['facility', 'nonfacility'],
                        category: Literal['QP', 'nonQP'],
                        carrier: str = Query(pattern=r'^\d{5}$'),
                        locality: str = Query(pattern=r'^\d{2}$')):
    """Raw application/octet-stream file bytes, not multipart UploadFile/tempfiles."""
    if request.headers.get('content-type', '').split(';')[0] != 'application/octet-stream':
        raise HTTPException(415, 'Send the file as application/octet-stream.')
    with connect() as db:
        if not db.execute('SELECT 1 FROM payment_rates WHERE carrier=? AND locality=? LIMIT 1',
                          (carrier, locality)).fetchone():
            raise HTTPException(422, 'Select a carrier/locality pair from the reference list.')
    length = request.headers.get('content-length')
    if length:
        try:
            size = int(length)
        except ValueError:
            raise HTTPException(400, 'Invalid upload length.')
        if size > MAX_BYTES:
            raise HTTPException(413, 'File exceeds the 20 MiB limit.')
    if processing.locked():
        raise HTTPException(429, 'Another sample is processing. Please try again shortly.')
    async with processing:
        data = bytearray()
        async for chunk in request.stream():
            if len(data) + len(chunk) > MAX_BYTES:
                raise HTTPException(413, 'File exceeds the 20 MiB limit.')
            data.extend(chunk)
        if not data:
            raise HTTPException(400, 'Choose a nonempty PDF or image.')
        try:
            return await run_in_threadpool(decode, bytes(data), dict(
                carrier=carrier, locality=locality, setting=setting, category=category))
        except OCRError as error:
            raise HTTPException(422, str(error)) from error
        except Exception as error:
            # Do not echo OCR text, file bytes or internal paths in error responses.
            raise HTTPException(500, 'Processing failed. Check the local reference data and OCR installation.') from error


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8000, access_log=False)
