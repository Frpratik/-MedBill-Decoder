# Phase 0 checkpoint: MedBill Decoder

Status: approved by the user on September 8, 2026, including the proposed benchmark wording. The remainder records the original Phase 0 checkpoint; Phase 1 results are documented separately.

## Downloaded official CMS sources

Retrieved September 8, 2026. Originals are in data/raw.

| Archive | Direct source | Bytes |
| --- | --- | ---: |
| Annual PFS payment baseline | https://www.cms.gov/files/zip/pfrev26a-updated-12-29-2025.zip | 20811509 |
| April PFS update | https://www.cms.gov/files/zip/pfrev26b-updated-03-10-2026.zip | 338053 |
| July PFS update | https://www.cms.gov/files/zip/pfrev26c-posted-06-30-2026.zip | 315623 |
| July relative values and CPT/HCPCS short descriptions | https://www.cms.gov/files/zip/rvu26c-updated-06-30-2026.zip | 6160522 |
| July HCPCS Level II descriptions and record layout | https://www.cms.gov/files/zip/july-2026-alpha-numeric-hcpcs-file.zip | 2499217 |

Catalog pages:
- https://www.cms.gov/medicare/payment/fee-schedules/physician/national-payment-amount-file
- https://www.cms.gov/medicare/payment/fee-schedules/physician/pfs-relative-value-files
- https://www.cms.gov/medicare/coding-billing/healthcare-common-procedure-system/quarterly-update

July chosen for a Q3 2026 prototype. October files are future-effective at retrieval. Bill service dates must determine the applicable release; other dates must not silently receive July prices.

## Actual inspection output

Annual non-QP payment file: 1,035,395 physical lines.
July non-QP payment update: 1,639 physical lines.
HCPCS text: 16,826 physical lines (not a distinct-code count; long descriptions can span records).

Annual raw CSV record:
```csv
"2026","01112","05","99213","  ","0000117.58","0000064.37"," ","0","A","0","0000049.56","0000000.00","9","0000000.00","0000000.00"
```

Raw RVU CSV record:
```csv
99213,,Office o/p est low 20 min,A,,1.30,1.46,,0.33,,0.09,2.85,1.72,0,XXX,0.00,0.00,0.00,0,0,0,0,0,9,,33.4009,09,0,99,0.00,0.00,0.00
```

HCPCS first record begins with sequence/code `A1001007` and description `Dressing for one wound`. Exact fixed-width source is retained in data/raw/hcpcs/HCPC2026_JUL_ANWEB_06172026.txt. Its interpretation must follow HCPC2026_recordlayout.txt.

These are raw samples, not validated joined lookups. Payment field interpretation and adjustment rules must be verified against the bundled PF26PAR.pdf / PF26PB.pdf before ingestion. Annual baseline and both quarterly updates include QP and non-QP variants; neither should be silently merged into the other.

## Proposed Phase 1 structure

Use pandas for ingestion and SQLite for the read-only runtime lookup: indexed composite keys and explicit provenance are better suited than repeatedly loading a million-row CSV in API requests. Only public reference data goes into SQLite, never bills.

1. Read bundled record-layout documentation before assigning payment column names. Preserve codes, modifiers, carrier and locality as strings, including leading zeros.
2. Ingest annual baseline, then apply April and July updates by their documented rules. Retain effective dates and source version. Do not concatenate updates into statistical observations.
3. Keep QP/non-QP, facility/nonfacility, modifier and locality dimensions distinct. Preserve status and payment-policy indicators. Do not treat zero or unavailable payments as free services.
4. Read the RVU CSV after its nine metadata/header-prefix rows using an explicit schema; preserve its copyright notice. Join short descriptions by code and modifier. Reconstruct HCPCS long descriptions using the supplied fixed-width record layout and sequence fields.
5. Record unmatched codes, conflicting keys, invalid amounts, source row counts, release dates and archive SHA-256 hashes. Never impute unknown descriptions or prices.
6. Suggested tables: sources; code_descriptions; payment_rates (code, modifier, carrier, locality, setting, QP category, effective interval, amount, status, source); ingestion_issues.
7. Show actual cleaned row counts, schema, coverage, and representative joined lookups before requesting Phase 2 approval.

## Limitations and proposed interpretation requiring approval

The chosen sources satisfy the Medicare reference option in the specification. They cover physician-schedule services and HCPCS descriptions, not every hospital, drug, or laboratory charge. Unsupported items must remain unmatched; HCPCS description coverage does not imply PFS price coverage.

PFS values are administratively set Medicare benchmarks, not an observed distribution of commercial hospital charges. Percentiles across localities would describe geographic variation in that benchmark, not the probability that a bill is erroneous. There is no defensible confirmed overcharge or recoverable-savings total from these data alone.

Proposal for Phase 3: show a matched Medicare benchmark, charge-to-benchmark ratio, and (only when a sufficiently sized, comparable cohort is available) an explicitly labeled percentile across Medicare locality rates. Keep modifiers, setting, QP status and date fixed. Do not use arbitrary multipliers as statistical evidence. Where no valid cohort exists, report insufficient comparison data.

Proposed wording change: replace "estimated overcharge" with "amount above Medicare benchmark" and describe flags as questions to investigate. This is a proposed change, not yet approved or implemented. If observed regional market-price outliers are essential, source comparable hospital transparency data before Phase 1 instead.

The RVU source explicitly states CPT descriptions are copyright 2026 AMA; public download does not itself establish unrestricted redistribution rights. Preserve attribution and examine applicable terms before packaging those descriptions for public distribution. HCPCS Level II is not the complete CPT long-description table.

Unknown codes must never be identified from LLM memory as verified facts. Phase 4 will need a verified description for fallback generation, otherwise the result must remain unknown. Template coverage of 80% is a target to measure, not an established result. A real Claude fallback demonstration will require API access at that phase.

## Reproduce inspection (PowerShell, from project root)

```powershell
Get-ChildItem data/raw/*.zip | Select-Object Name,Length
Get-FileHash data/raw/*.zip -Algorithm SHA256
Get-Content data/raw/rvu/PPRRVU2026_Jul_nonQPP.csv -TotalCount 12
Select-String -Path data/raw/payments/annual/nonqp/PFALL26AR.txt -Pattern '"99213"' | Select-Object -First 1
Get-Content data/raw/hcpcs/HCPC2026_JUL_ANWEB_06172026.txt -TotalCount 2
```

No patient data was used. Approval required by the user's master prompt, Phase 0: "Do not proceed until I confirm the data sources are legitimate and sufficient."
