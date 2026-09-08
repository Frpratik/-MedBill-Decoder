# Phase 3 checkpoint: statistical Medicare benchmark comparison

This phase implements the interpretation approved at Phase 0: **amount above Medicare benchmark**, not a confirmed overcharge. All comparisons use actual Phase 2 OCR results and real CMS prices. Expected sample-manifest values never enter the engine.

## Method

For an accepted line, let:

- `C` = printed line charge, in cents.
- `q` = positive billing quantity extracted from the line.
- `L` = the matched single-unit Medicare rate, in cents.
- `R` = the sorted set of matching, eligible Medicare locality rates, one equally weighted observation per carrier/locality.

The match holds code, modifier, setting, payment category and service date fixed. It uses the approved Q3 2026 snapshot. The selected demo context is **carrier 01112 / locality 05, nonfacility, non-QP**, as in Phase 1. This context is explicitly supplied for synthetic demonstrations, not inferred from the OCR or a real patient location.

```text
unit charge u = C / q
line benchmark B = round_half_up(q * L) to integer cents
positive benchmark difference D = max(0, C - B)

n = number of eligible carrier/locality pairs
k = ceiling(0.95 * n)
p95 = R[k]                         # one-based index; nearest-rank definition
percentile rank = 100 * (count(R < u) + 0.5 * count(R = u)) / n

flag = (u > L) AND (u > p95)
```

The flag comparison uses the unrounded unit charge. Displayed money is rounded to cents. The charge-to-local-benchmark ratio is also returned. The report sums positive differences only over rows actually compared; lower-than-benchmark charges do not offset positive differences elsewhere.

**Why both thresholds?** San Francisco's Medicare rate can itself exceed the national geographic p95. Charging exactly the local Medicare rate must not trigger a flag just because the locality is relatively expensive. A regression test covers that boundary.

The p95 is a transparent screening choice, not a scientifically established overcharge threshold. At least 20 valid locality observations and nonzero geographic variation are required for a statistical flag. The minimum of 20 is an explicit product guardrail, not proof of statistical power. With too few observations or uniform rates, the statistical flag is null, even if a matched local benchmark remains available.

This describes a distribution of administrative Medicare rates. Localities are not randomly sampled hospitals, are not weighted by patients or claim volume, and are not independent observations of commercial prices. No normal-distribution assumption, z-score, p-value, confidence interval, error probability, or recoverable-savings claim is made.

## Eligibility and exclusions

- Only rows marked `parsed` with no parser issues enter calculations. Low-confidence raw fields are not substituted back into canonical fields.
- Codes, dates, quantities, charges, settings and modifiers must be valid. Amounts use Decimal/integer arithmetic. Negative, nonfinite and otherwise invalid inputs are excluded.
- The local reference must be a usable active (`A`) PFS rate. Missing prices, conflicting metadata, terminated codes, unsupported dates/settings and conditional (`R`/`T`) payments are excluded.
- Each cohort member is checked through the same Phase 1 lookup, including setting and OPPS-cap rules. QP/non-QP and professional/global components are never pooled.
- Multiple-procedure, therapy, bundling and other claim-level adjustments are not adjudicated. A quantity-based benchmark is an unadjusted full single-service-rate comparison; the existing CMS policy warnings remain attached.
- Missing references are not treated as zero. If there are no comparable rows, the summary amount is null rather than zero.

## Actual results

Every cohort below has **109 distinct carrier/locality pairs**. Dates come from the OCR rows. All six comparable charges exceed both thresholds; their midrank percentiles are 100.00 because they exceed all eligible locality rates in these cohorts.

| Sample | Code | Quantity | Charge per unit | Local rate per unit | Geographic p95 | Positive line difference | Flag |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| Clean | 99213 | 1 | $250.00 | $117.58 | $111.96 | $132.42 | Yes |
| Clean | 71046 | 1 | $180.00 | $43.76 | $41.22 | $136.24 | Yes |
| Clean | 93000 | 1 | $135.00 | $19.22 | $18.26 | $115.78 | Yes |
| Skewed | 97110 | 2 | $90.00 | $35.91 | $34.20 | $108.18 | Yes |
| Skewed | 93000 | 1 | $135.00 | $19.22 | $18.26 | $115.78 | Yes |
| Degraded | 99214 | 1 | $320.00 | $166.40 | $158.59 | $153.60 | Yes |

For `97110`, the printed line charge is $180.00 for two units. The line benchmark is `2 * $35.91 = $71.82`, giving `$180.00 - $71.82 = $108.18`. The engine compares the $90.00 unit charge with the per-unit distribution, not the $180.00 line total. Therapy reduction rules may apply to an actual claim and are not calculated here.

| Sample | Extracted rows | Compared | Excluded | Flagged | Amount above Medicare benchmark, compared rows only |
| --- | ---: | ---: | ---: | ---: | ---: |
| Clean | 4 | 3 | 1 | 3 | $384.44 |
| Skewed | 4 | 2 | 2 | 2 | $223.96 |
| Degraded | 5 | 1 | 4 | 1 | $153.60 |

Exclusions: five OCR-review rows, plus `80053` on the clean sample and `J1885` on the degraded sample, which have no matching PFS rate in this source. The samples' fabricated charges were designed for software testing; six flags here do not establish performance on real bills.

## Implementation and evidence

- `medbill/compare.py`: pure Decimal statistics, cohort construction, row gating and partial-report summaries. No LLM or fabricated reference data.
- `medbill/evaluate_comparison.py`: runs against the saved actual OCR JSON. The three reports contain an SHA-256 of their OCR input, every included cohort member's carrier/locality/rate, source row, source URL/hash, thresholds, ratios and exclusion reasons.
- `docs/PHASE_3_COMPARISON_OUTPUT.txt`: captured command output.
- `docs/phase3/01_clean.json`, `02_skewed.json`, `03_degraded.json`: complete machine-readable evidence.
- `docs/PHASE_3_TEST_OUTPUT.txt`: actual test output. New tests cover nearest-rank boundaries, ties, insufficient/uniform cohorts, local-rate protection, unit normalization, missing references, input rejection, exact cohort dimensions and partial totals. Existing reference and actual OCR regressions also run.

## Run

From the project root, using the configured local environment:

```powershell
.\.venv\Scripts\python.exe -m medbill.evaluate_comparison
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m medbill.compare docs/phase2/01_clean.json --synthetic --carrier 01112 --locality 05 --setting nonfacility --category nonQP
```

To rerun OCR before comparison, run `python -m medbill.evaluate_ocr` in the same environment. The comparison engine itself does not write bill data; the evaluator writes only these synthetic evidence reports. The reference SQLite database remains read-only.

## Judge-facing interpretation

“We match the extracted service, billing units and context to cited CMS Medicare rates. We show the local benchmark and where the charge falls among comparable Medicare locality rates. A flag means the charge exceeds both the local benchmark and that distribution's 95th percentile. It identifies a question to investigate; it does not establish an erroneous charge or what the patient should owe.”

Sources: the [CMS PFS payment files](https://www.cms.gov/medicare/payment/fee-schedules/physician/national-payment-amount-file) and their bundled layout/policy documents supply the actual amounts. [NIST's percentile discussion](https://www.itl.nist.gov/div898/handbook/prc/section2/prc262.htm) explains order-statistic percentile concepts and the existence of multiple definitions; this implementation explicitly uses nearest-rank rather than attributing a universal percentile convention to NIST. No source claims the selected screening threshold proves overcharging.

No new data source or scope change was introduced. The limitations and benchmark wording follow the approved Phase 0 decision. Phase 4 (templates and a real Claude fallback demonstration) remains pending approval.
