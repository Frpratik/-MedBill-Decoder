# Phase 1 checkpoint: reference data pipeline

Phase 0 sources and benchmark wording were approved by the user. This phase implements ingestion and lookups only. Phase 2 (OCR and parsing) remains pending approval.

## Implemented

- pandas ingestion directly from all five original ZIPs, including nested QP/non-QP archives. Exact SHA-256 verification happens before ingestion.
- A SQLite snapshot for July 1–September 30, 2026, with exact code/modifier/carrier/locality/category keys. Facility and nonfacility amounts are separate columns, in integer cents.
- Baseline followed by April and July revisions. Matching keys are replaced; new keys are inserted. Unmentioned baseline records remain. Revisions are not treated as independent price observations. Original archives and revision rows remain auditable.
- Source archive URL, SHA-256, internal member name, copyright notices, and row number retained for provenance.
- Code descriptions, HCPCS long descriptions/modifiers, and setting/status policy metadata. No LLM calls or invented prices.
- A command-line lookup, an evidence generator, and regression tests. The runtime opens SQLite read-only. No bill uploads or patient data exist in this phase.

SQLite avoids loading million-row CSV files for each query; pandas remains responsible for ingestion. The database is about 208 MB. A disposable build database is checked before it replaces the previous artifact.

## Actual data counts

| Source/table | Data rows |
| --- | ---: |
| Annual payment baseline, non-QP | 1,035,391 |
| Annual payment baseline, QP | 1,035,391 |
| April revisions, each category | 4,033 |
| July revisions, each category | 1,635 |
| Final payment records, both categories | 2,075,578 |
| Retained revision records | 11,336 |
| CPT/HCPCS short descriptions, code + modifier | 19,356 |
| RVU policy records, both categories | 31,265 |
| HCPCS procedure descriptions | 8,725 |
| HCPCS modifier descriptions | 384 |

The payment lookup contains 7,857 distinct procedure codes across 109 carrier/locality pairs. Each payment record holds both setting amounts; the table count is not a count of distinct codes or market observations.

All payment keys have matching short descriptions and category-specific RVU metadata. There are 218 conflicting status rows, detailed below. SQLite integrity check returned `ok`, with no foreign-key violations. Invalid monetary fields or duplicate input keys cause the build to fail rather than silently select or impute data.

## Actual lookup output

These examples use service date July 15, 2026, carrier `01112`, locality `05` (San Francisco in the bundled payment documentation). The default shown is non-QP, nonfacility, unmodified service.

| Code | Source description | Context | Benchmark USD |
| --- | --- | --- | ---: |
| 99213 | Office o/p est low 20 min | Nonfacility | 117.58 |
| 99213 | Office o/p est low 20 min | Facility | 64.37 |
| 99213 | Office o/p est low 20 min | QP, nonfacility | 118.17 |
| 71046 | X-ray exam chest 2 views | Global, nonfacility | 43.76 |
| 71046 | X-ray exam chest 2 views | Modifier 26, nonfacility | 11.59 |
| 93000 | Electrocardiogram complete | Nonfacility | 19.22 |
| 46505 | Chemodenervation anal musc | July revision, nonfacility | 432.49 |

Actual withheld results:

| Input | Result |
| --- | --- |
| 80053 | Description found; no matching PFS rate |
| ZZZZZ | Unknown code; no benchmark |
| 99213 dated October 1, 2026 | Unsupported date; no benchmark |
| 71046 in facility setting | RVU metadata says rarely/never performed in that setting; benchmark withheld |
| J0135 | Terminated HCPCS code; no benchmark |
| A4100 | Conflicting CMS status; benchmark withheld |

Full JSON includes source URLs, hashes, source row numbers, status indicators, and warnings. See `data/processed/reference.examples.json` and the captured `docs/PHASE_1_LOOKUP_OUTPUT.txt`.

## Schema

| Table | Key and purpose |
| --- | --- |
| payment_rates | `(category, carrier, locality, code, modifier)`; both setting amounts, therapy and OPPS amounts, payment-policy indicators, source and row |
| payment_revisions | Original April/July records, retaining source identity |
| code_descriptions | `(code, modifier)`; published short description and provenance |
| rvu_policy | `(code, modifier, category)`; status and setting NA flags |
| hcpcs_descriptions | Code; full description, short description, added/action/termination dates, coverage indicator and provenance |
| hcpcs_modifiers | Modifier descriptions, kept separate from procedure codes |
| sources | URL, ZIP name/hash, internal filename, release label, retrieval date, copyright text |
| ingestion_issues | Counted exclusions and unresolved source discrepancies |
| build_metadata | Supported Q3 interval, schema version, and scope |

The exact generated SQL is `data/processed/reference.schema.sql`.

## Cleaning decisions and limitations

1. **Copyright trailers:** each of the six payment files has four trailer lines. They are excluded from payments, with their text preserved in `sources`. Phase 0 physical line counts included them.
2. **Exact money and identifiers:** amounts become integer cents using string arithmetic. Leading zeros in codes/localities/carriers remain intact. QP and non-QP are never merged. A blank modifier is an explicit unmodified/global lookup, not a fallback for an unmatched component.
3. **Quarterly coverage:** the artifact is a Q3 release snapshot. The supporting description/policy files are July files, so the lookup deliberately does not reconstruct January–June history or claim service-date accuracy outside Q3. CMS release dates are not assumed to resolve every retroactive policy change.
4. **HCPCS format:** used the official spreadsheet's complete description cells instead of reconstructing split text records. This changes the ingestion format, not source or coverage. The Phase 0 prefix `A1001007` was a fixed-width modifier record for **A1**, not procedure A1001; modifiers are now correctly separated.
5. **HCPCS corrections:** the eight correction-sheet entries' code additions/removals and descriptions are reflected in the dated main workbook (case/whitespace differences normalized only for comparison). However, G0577 has pricing indicator **13** in the main workbook and **11** in the corrections sheet. This conflict is logged. Both RVU variants list G0577 as carrier-priced (`C`), and no downloaded PFS payment row supplies its rate. No price is invented or derived from the conflicting indicator.
6. **A4100 disagreement:** the payment file says active (`A`), while both July RVU files say carrier-priced (`C`). This affects 109 localities × 2 categories = 218 records. Published amounts are retained for audit, but the lookup returns no usable benchmark.
7. **Payment eligibility:** zero/nonpositive rates, missing policy metadata, unavailable settings and conflicting status withhold a benchmark. Restricted/conditional payments and multiple-procedure indicators generate warnings. OPPS-capped services use the lower applicable published amount. The code does not calculate patient responsibility, coverage, or full claim adjustments.
8. **Meaning of the benchmark:** a facility-setting PFS amount is for the physician service, not a hospital facility bill. Geographic PFS values are Medicare administrative benchmarks, not observed commercial prices. Clinical labs and other non-PFS charges can have descriptions but no reference price here.
9. **Rights:** source AMA/ADA notices are preserved. Full source and generated datasets are excluded from Git; packaging rights still need attention before public redistribution of those datasets.

## Run and verify

With dependencies installed, from the project directory:

```powershell
python -m medbill.ingest
python -m medbill.verify
python -m unittest discover -s tests -v
python -m medbill.reference 99213 --carrier 01112 --locality 05 --setting nonfacility --category nonQP --service-date 2026-07-15
```

The README contains environment setup and the already-installed Codex runtime path for this workstation. The ingestion command can rebuild from the original ZIPs without using the manually extracted folders. Verification prints actual results and saves JSON. Tests cover source fidelity, revision propagation, QP/setting distinctions, source correction checks, missing matches, invalid money, date boundaries, terminated codes, conflicting status, and read-only access.

## Source documentation used

- Payment layout and status definitions: `PF26PAR.pdf` / `PF26PB.pdf` inside the downloaded payment ZIPs, available from https://www.cms.gov/medicare/payment/fee-schedules/physician/national-payment-amount-file
- Setting NA indicators and OPPS policy: `RVU26C.pdf` in https://www.cms.gov/files/zip/rvu26c-updated-06-30-2026.zip
- HCPCS workbook, correction sheet and record layout: https://www.cms.gov/files/zip/july-2026-alpha-numeric-hcpcs-file.zip

## Next checkpoint

Approve Phase 1 to begin Phase 2: real Tesseract/OpenCV processing and line-item parsing, tested on three explicitly synthetic bills with cited format references. No Phase 2 implementation is included in this checkpoint.
