# MedBill Decoder

Phases 1–4: a local CMS reference lookup, real Tesseract/OpenCV OCR and line-item parsing, statistical Medicare benchmark comparisons, and local explanations. The approved wording is **amount above Medicare benchmark**. API and UI remain for later phases. No third-party API or LLM integration is used or required.

## Setup

Python 3.11 or later:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
./scripts/setup_windows_ocr.ps1
.\.venv\Scripts\python.exe -m medbill.ingest
.\.venv\Scripts\python.exe -m medbill.verify
.\.venv\Scripts\python.exe -m medbill.evaluate_ocr
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The five downloaded archives must remain in `data/raw`. Exact official URLs and pinned hashes are in `medbill/ingest.py`, and source context is in `docs/PHASE_0_DATA_SOURCES.md`. The build validates every archive's SHA-256 before reading it. Changed releases require review and a deliberate pin update. The build runs offline once dependencies and archives are present. Expect several minutes and several hundred MB for the database and temporary build file.

The Windows OCR setup uses an existing 7-Zip installation to extract the pinned Tesseract release locally and downloads the official English model. Both downloads are checksum-verified. It does not run the installer or change system PATH. Alternatively, install Tesseract using the [official instructions](https://tesseract-ocr.github.io/tessdoc/Installation.html), with English traineddata, and set `TESSERACT_CMD` if the executable is not on PATH.

On the current workstation, the project-local `.venv` and `.tools/tesseract` are already configured:

```powershell
$medbillPython = '.\.venv\Scripts\python.exe'
& $medbillPython -m medbill.ingest
& $medbillPython -m medbill.verify
& $medbillPython -m unittest discover -s tests -v
```

## One lookup

```powershell
python -m medbill.reference 99213 --carrier 01112 --locality 05 --setting nonfacility --category nonQP --service-date 2026-07-15
```

For a professional component, supply `--modifier 26`. Blank modifier means the unmodified/global code; there is no fallback from an unmatched modifier to a global price. `QP` refers to the source's Qualifying APM Participant payment category, not participating/nonparticipating physician status.

The lookup requires a carrier/locality pair, setting, category, and date. It currently supports July 1–September 30, 2026. Other dates return `unsupported_date`. Facility amounts are physician-service amounts in a facility setting, not the hospital's facility charge. Published benchmarks are not insurance benefits, amounts owed, coverage determinations, or proof of an overcharge.

## OCR and parsing

```powershell
.\.venv\Scripts\python.exe -m medbill.ocr output/pdf/01_clean.pdf --synthetic
.\.venv\Scripts\python.exe -m medbill.evaluate_ocr
```

Only synthetic/public sample data is permitted. Every PDF is rasterized before local OCR; no text-layer shortcut or vision API is used. OpenCV denoises, deskews, thresholds and removes table rules. Tesseract returns word coordinates/confidence. Parsing preserves uncertain raw values and withholds low-confidence critical fields. The runtime passes images through stdin/stdout without writing temporary bill files.

Three synthetic fixtures and their generator are included. `samples/README.md` cites the bill-format references. `docs/PHASE_2_OCR_PARSING.md` records actual extraction results and failures: 13 candidate rows, eight complete and five requiring review, including two correct fields withheld by the conservative confidence policy. This is a small development regression, not a general OCR accuracy estimate. Handwriting, complex/wrapped layouts and severe camera distortion remain unvalidated.

## Benchmark comparison

```powershell
.\.venv\Scripts\python.exe -m medbill.evaluate_comparison
.\.venv\Scripts\python.exe -m medbill.compare docs/phase2/01_clean.json --synthetic --carrier 01112 --locality 05 --setting nonfacility --category nonQP
```

Only complete, accepted OCR rows with usable active CMS references are compared. The engine normalizes the line charge by quantity and flags it only when the unit charge exceeds both the matched local rate and the nearest-rank 95th percentile across matching Medicare localities. Cohorts with fewer than 20 eligible observations or no geographic variation receive no statistical flag. Uncertain and unpriced rows remain excluded. Reported amounts are partial benchmark differences, not confirmed overcharges or recoverable savings. See `docs/PHASE_3_BENCHMARK_COMPARISON.md` for formulas, actual numbers and limitations.

## Local explanations

```powershell
.\.venv\Scripts\python.exe -m medbill.evaluate_explanations
.\.venv\Scripts\python.exe -m medbill.explain docs/phase3/01_clean.json --synthetic
```

Seven code-specific paraphrases and a general CMS-description template explain known codes. Unknown codes receive a clarification question; uncertain OCR stays withheld. Prices and flags are copied from the comparison engine, never generated. All eight accepted sample rows use templates; five of the 13 total rows require OCR review. The requested Claude fallback was removed at the user's direction: the runtime stays local and needs no API key. See `docs/PHASE_4_EXPLANATIONS.md` for actual output and limits.

## Reference artifacts

- `data/processed/reference.sqlite`: indexed public reference snapshot, opened read-only at runtime.
- `data/processed/reference.audit.json`: ingestion counts and data gaps.
- `data/processed/reference.schema.sql`: actual database schema.
- `data/processed/reference.examples.json`: actual lookup output from `medbill.verify`.

Ingestion uses pandas; runtime lookups use Python's SQLite library. There are no LLM calls or invented reference amounts. Persisted artifacts comprise public references, explicitly synthetic bills and their test evidence. There is no upload endpoint or real patient-data processing in this phase.

CMS archives include AMA/ADA copyright notices. The pipeline retains the notices and provenance. Public availability does not establish unrestricted redistribution rights; raw and generated data are ignored by Git. Distribution terms must be addressed before submission packaging.
