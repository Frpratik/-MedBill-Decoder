# Phase 2 checkpoint: OCR and line-item parsing

This document records the completed Phase 2 checkpoint, subsequently approved by the user. Phase 2 implements actual Tesseract/OpenCV processing and conservative line-item extraction. Phase 3 results are documented separately.

## Implementation

`medbill/ocr.py` rasterizes every PDF page at 300 DPI with PDFium; it never reads embedded PDF text. Images receive EXIF orientation correction and grayscale conversion. OpenCV applies median denoising, projection-profile deskew within +/-5 degrees, adaptive Gaussian thresholding, and removal of long table rules. Small images are upscaled within a pixel limit. The deskew search maximizes horizontal-row sharpness; the Laplacian variance is a diagnostic, not a claim of OCR accuracy.

Tesseract 5.5.3 with the official English fast model receives PNG bytes on stdin and returns TSV words, coordinates, and confidence on stdout. No vision API or LLM is involved. No temporary input/output files are created by this implementation. The evaluator deliberately writes only the synthetic fixtures' outputs for this checkpoint.

`medbill/parser.py` detects code, description, quantity, charge, and optional unit-price column positions from OCR headers. It retains service date, modifier, raw row text, raw columns, confidence and review reasons. Summary totals and payments are excluded from line items. Without recognized headers, regex extraction is retained as a candidate requiring review. Missing quantities never become one; ambiguous prices, invalid dates, negative/credit amounts, and unreadable fields require review.

## Actual run

| Fixture | Candidate rows | Complete rows | Review rows | Deskew correction |
| --- | ---: | ---: | ---: | ---: |
| Clean PDF | 4 | 4 | 0 | 0 degrees |
| Skewed PNG | 4 | 2 | 2 | -3 degrees |
| Degraded image-only PDF | 5 | 2 | 3 | +2 degrees |
| Total | 13 | 8 | 5 | |

All 13 printed service rows were found. Eight rows were complete under the review policy. This is a three-fixture regression result, not a general accuracy estimate.

Actual output for the clean sample:

```text
99213 | quantity 1 | charged $250.00 | parsed
71046 | quantity 1 | charged $180.00 | parsed
93000 | quantity 1 | charged $135.00 | parsed
80053 | quantity 1 | charged  $95.00 | parsed
```

Actual output for the skewed sample:

```text
97110    | quantity 2    | charged $180.00 | parsed
71046-26 | quantity null | charged  $75.00 | low_confidence_quantity
93000    | quantity 1    | charged $135.00 | parsed
null     | quantity 1    | charged  $40.00 | low_confidence_code
```

The therapy row's `$90.00` unit price was correctly separated from its `$180.00` line charge. Tesseract correctly recognized the X-ray quantity as `1` but assigned confidence 74.04; it correctly recognized `G0008` but assigned confidence 69.53. Both are deliberately withheld by the conservative threshold, so the evaluator reports these readable fields as not recovered in canonical output. Raw values remain visible.

Actual output for the degraded sample:

```text
99214 | quantity 1    | charged $320.00 | parsed
J1885 | quantity 2    | charged  $60.00 | parsed
null  | quantity 1    | charged  $88.00 | low_confidence_code
80053 | quantity null | charged  $95.00 | missing_or_ambiguous_quantity
99213 | quantity 1    | charged    null | missing_or_ambiguous_charge
```

The third row intentionally prints `?????`. Tesseract read that as `22272`, with word confidence 68.01 but row-average confidence 92.19. An initial version relying only on the row average accepted that wrong code. The final parser checks individual critical fields, withholds the code, and preserves `22272` in raw OCR evidence. It does not replace it with a guessed real code. The obscured amount was read as `222?`; because it is not valid currency, it remains null.

## Confidence policy and limits

- Critical code/quantity/charge/date confidence below 80 triggers review. This is an explicit heuristic, not a calibrated probability. It catches the observed wrong code but also sends two correct fields to review. High-confidence errors can still occur.
- The fixtures test upright English, single-column service tables with one printed line per service. Arbitrary multi-column layouts, wrapped service rows, handwriting, severe perspective distortion, rotations outside +/-5 degrees, and other currencies/languages are not validated. Unrecognized lines are retained in the output; finding a subset of rows does not prove the bill is complete.
- OCR extracts what is printed. It does not determine clinical correctness, billing validity, or whether a code is current; reference validation is separate.
- Input limits are 20 MiB, 20 megapixels per page and ten PDF pages. Multipage TIFF is rejected instead of silently reading only page one.
- The CLI requires `--synthetic`, a user attestation rather than PHI detection. Do not supply real patient data. This phase has no upload endpoint.
- The three fixtures share a generator; the evaluation is a development regression, not an independent benchmark. Expected fields never reach OCR/parser functions.

## Evidence and verification

`docs/phase2/01_clean.json`, `02_skewed.json`, and `03_degraded.json` contain complete extracted rows, raw OCR words, coordinates, confidence, preprocessing diagnostics and input hashes. Corresponding `.txt` files contain actual OCR text. `evaluation.json` records the expected-versus-actual discrepancies without modifying recognition output.

`docs/PHASE_2_OCR_OUTPUT.txt` captures the run summary. `docs/PHASE_2_TEST_OUTPUT.txt` captures parser regressions, real OCR runs and Phase 1 reference tests. The tests exercise the three real inputs, ambiguity/credit handling, confidence withholding, code modifiers, summary exclusion, empty/damaged files, and absence of file creation in the working directory during extraction.

All three PDFs were rendered using Poppler and visually inspected. The third intentionally contains skew, degradation, and missing-field markers; its layout remains legible. These are explicit test conditions, not accidental layout defects.

## Reproduce

```powershell
.\.venv\Scripts\python.exe -m medbill.samples
.\.venv\Scripts\python.exe -m medbill.evaluate_ocr
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m medbill.ocr output/pdf/01_clean.pdf --synthetic
```

Install Python dependencies from `requirements.txt`. Install Tesseract and English traineddata. On this Windows workstation, `scripts/setup_windows_ocr.ps1` extracts the pinned upstream Windows release into `.tools/tesseract` using 7-Zip and verifies download hashes. It does not run the installer or change system PATH. On other systems use the official Tesseract installation instructions; `TESSERACT_CMD` can select an executable. The English model is pinned by SHA-256 even though its download URL tracks upstream `main`.

## Sources and deviations

Bill format citations and the exact role of each source are in `samples/README.md`. The grids are original constructions based on published itemized-bill fields; no real patient bill was used or copied. Charges are fabricated test inputs, never Medicare reference prices.

- [Tesseract installation](https://tesseract-ocr.github.io/tessdoc/Installation.html) and [command-line TSV output](https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html)
- [OpenCV thresholding](https://docs.opencv.org/4.13.0/d7/d4d/tutorial_py_thresholding.html) and [geometric transforms](https://docs.opencv.org/4.13.0/da/d6e/tutorial_py_geometric_transformations.html)

PDFium is used for runtime in-memory PDF rendering, while Poppler is used for visual QA. This is an implementation choice within the specified Tesseract/OpenCV architecture. There are no LLM substitutions or synthetic reference amounts.

Phase 3 remains pending checkpoint approval: implement explainable Medicare benchmark comparisons and run them against these extracted synthetic line items, withholding uncertain fields.
