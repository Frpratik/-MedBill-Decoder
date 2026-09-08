# MedBill Decoder

Phase 1: a deterministic local lookup of public CMS Medicare references. The user approved Phase 0 sources and the wording **amount above Medicare benchmark**. OCR, bill parsing, statistical comparisons, explanations, API, and UI are not implemented yet.

## Setup

Python 3.11 or later:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m medbill.ingest
.\.venv\Scripts\python.exe -m medbill.verify
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The five downloaded archives must remain in `data/raw`. Exact official URLs and pinned hashes are in `medbill/ingest.py`, and source context is in `docs/PHASE_0_DATA_SOURCES.md`. The build validates every archive's SHA-256 before reading it. Changed releases require review and a deliberate pin update. The build runs offline once dependencies and archives are present. Expect several minutes and several hundred MB for the database and temporary build file.

On the current Codex workstation, dependencies are already installed in the bundled runtime:

```powershell
$medbillPython = 'C:\Users\prati\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
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

## Outputs

- `data/processed/reference.sqlite`: indexed public reference snapshot, opened read-only at runtime.
- `data/processed/reference.audit.json`: ingestion counts and data gaps.
- `data/processed/reference.schema.sql`: actual database schema.
- `data/processed/reference.examples.json`: actual lookup output from `medbill.verify`.

Ingestion uses pandas; runtime lookups use Python's SQLite library. There are no LLM calls and no invented reference amounts. Only public references and their metadata are stored. No upload or patient-data processing exists in this phase.

CMS archives include AMA/ADA copyright notices. The pipeline retains the notices and provenance. Public availability does not establish unrestricted redistribution rights; raw and generated data are ignored by Git. Distribution terms must be addressed before submission packaging.
