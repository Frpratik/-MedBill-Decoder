# MedBill Decoder — Devpost draft

**Tagline:** Understand medical bill codes, compare charges with cited Medicare benchmarks, and prepare better questions—all locally.

This is copy-ready project text, not a submitted entry. Confirm the event's current fields, eligibility, track and video limits in its submission form before posting. No claims about event rules have been assumed.

## Inspiration

An itemized medical bill can be detailed without being understandable. Procedure codes, billing units and unfamiliar descriptions make it difficult to know what to ask next. We built MedBill Decoder to turn a confusing list of charges into an explainable report, while keeping uncertainty visible.

## What it does

MedBill Decoder accepts a synthetic bill image or PDF, reads its line items locally, explains known services and compares eligible charges against actual CMS Medicare reference rates. It shows which rows were compared, which need a clearer reading, and which lack a usable reference price. Each line includes a question for the billing office.

A flag means the unit charge exceeds both the matched local Medicare rate and the 95th percentile of matching Medicare locality rates. It does not prove an error, show what a patient owes or promise a refund. We call the total **amount above Medicare benchmark**, and exclude uncertain/unpriced rows from that total.

## How we built it

The pipeline has five concrete stages:

1. OpenCV denoises, deskews, thresholds and removes table rules. PDFs are rasterized before OCR.
2. Tesseract reads text and word coordinates. Header geometry and regular expressions identify dates, codes, quantities and charges. Low-confidence critical fields are withheld.
3. pandas ingests pinned CMS payment and code-description files into SQLite. Annual and quarterly updates are applied by key, with source rows and hashes retained. Runtime matching keeps locality, modifier, setting, payment category and date explicit.
4. Decimal arithmetic normalizes charges by units and computes the local benchmark difference and nearest-rank geographic percentile. At least 20 valid locality observations and geographic variation are required for a statistical flag.
5. FastAPI serves a plain HTML/CSS/JavaScript interface. Written templates explain known services. Unknown codes stay unknown. There are no LLM calls or third-party runtime APIs.

## Challenges we ran into

OCR sometimes misread obscured symbols as plausible digits. We retained the raw reading for traceability but withheld low-confidence canonical fields from calculations. The stricter rule also rejects some correctly recognized fields; that tradeoff is visible in the sample results.

Public reference data also required care. Medicare amounts are administrative benchmarks, not commercial hospital charges. Some codes have descriptions but no PFS price. Source status conflicts and unsupported dates must not turn into invented prices. We preserve those gaps instead of making every row look complete.

## Accomplishments we're proud of

The three synthetic demonstration bills run through the actual OCR and reference pipeline. Of 13 candidate rows, eight have accepted readings and local explanations; six have usable price comparisons. Five need OCR review, and two accepted rows lack matching prices. The clean sample compares three of four rows and shows a $384.44 positive difference from the matched Medicare benchmarks—not $384.44 in proven savings.

Additional tests cover blank and severely blurred images, an unknown code, an unsupported service date, invalid uploads, size limits and concurrent-job rejection. An application-level audit observed no Python file mutations or network connections during eight processing cases, no leftover files in the isolated test working/temp folders, and an unchanged reference database. This is a scoped measurement, not a guarantee about operating-system paging or every native process operation.

## What we learned

The useful output is often a clearer question rather than a confident-sounding verdict. Units, modifiers and location matter. Missing reference data should remain missing. A prototype is easier to defend when a reviewer can trace each benchmark to a real source and inspect actual failure cases.

## What's next

Broader validation on permitted, explicitly de-identified or synthetic formats; clearer geographic-area selection; accessible correction/review workflows; and additional verified reference sources. These are future directions, not implemented features. The current prototype supports only the July–September 2026 reference snapshot and prohibits real patient information.

## Built with

Python, FastAPI, SQLite, pandas, NumPy, OpenCV, Tesseract, PDFium/pypdfium2, Pillow, ReportLab, HTML, CSS, JavaScript.

## Links and submission fields

- Source: https://github.com/Frpratik/-MedBill-Decoder
- Data citations and setup: repository README.
- Demo: record the local app using `docs/DEMO_VIDEO_SCRIPT.md`, then add the actual video link.
- Hosting: local prototype only; do not present `127.0.0.1` as a public demo URL.
- Team/member details: enter the actual contributors and roles.
- AI assistance disclosure, if requested: Codex assisted implementation, debugging, testing and documentation. The app itself uses local OCR, deterministic matching/statistics and written templates; it does not call an LLM.
