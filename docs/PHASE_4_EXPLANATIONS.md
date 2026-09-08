# Phase 4: fully local explanations

## Approved scope change

The user explicitly declined third-party APIs during Phase 4. The original Claude fallback requirement is replaced by deterministic unknown-code handling. There is no Claude integration, prompt, API credential, generated example or mocked model output in this implementation. No API calls are needed at runtime; initial public-data and dependency setup still needs downloads.

## Implementation

`medbill/explain.py` reads the actual local CMS description tables. Seven code-specific hand-written paraphrases cover the accepted sample codes. Other known codes use a general template quoting their official description. HCPCS long descriptions take priority where available. Source IDs and official descriptions accompany the wording. Modifiers remain explicit and receive a clarification prompt.

Unknown descriptions get an honest unverified-service message and a question for the billing office. Invalid or uncertain OCR rows are not repaired from their raw text. Unsupported dates and inactive-date results require review. A known description can still be explained when a matching price is absent.

Benchmark wording uses the existing comparison output. It cannot change the charge, reference amount, flag or summary. Questions address the billed units or the two benchmark thresholds. The explanation layer opens only the local reference database for reading and writes no input data. The evaluator saves explicitly synthetic demonstration evidence.

## Actual sample results

| Sample | Total rows | Templates | OCR review | LLM calls |
| --- | ---: | ---: | ---: | ---: |
| Clean | 4 | 4 (100%) | 0 | 0 |
| Skewed | 4 | 2 (50%) | 2 | 0 |
| Degraded | 5 | 2 (40%) | 3 | 0 |
| Total | 13 | 8 (61.54%) | 5 (38.46%) | 0 |

All eight accepted rows use templates. None of these samples has an accepted unknown code; a separate test verifies unknown-code handling without inventing a medical meaning. This small fixture set does not establish 80% coverage of real bills.

Examples captured from the actual evaluator:

- 71046: “A chest X-ray with two views.”
- 80053: “A comprehensive metabolic panel, a group of blood tests.” It remains unpriced by this PFS snapshot.
- J1885: “An injection of ketorolac tromethamine; the code describes each 15 mg billing unit.” This explains the code's billing unit, not a patient dose.
- An uncertain row: “This line needs a clearer image or a corrected reading before it can be explained.”

Full outputs: `docs/phase4/*.json` and `docs/PHASE_4_EXPLANATION_OUTPUT.txt`. Tests are captured in `docs/PHASE_4_TEST_OUTPUT.txt`.

## Run

```powershell
.\.venv\Scripts\python.exe -m medbill.evaluate_explanations
.\.venv\Scripts\python.exe -m medbill.explain docs/phase3/01_clean.json --synthetic
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Limits and next checkpoint

The generic template can retain medical jargon. The paraphrases are brief summaries, not exhaustive coding guidance; the official description remains visible. There is no model-based explanation for missing codes. Patient-specific coverage, medical necessity, treatment advice and recoverable savings are not inferred. The existing Medicare date and pricing limits remain in force.

Phase 5, the local FastAPI upload pipeline and frontend, awaits approval. It will use this local explanation layer without a third-party API.
