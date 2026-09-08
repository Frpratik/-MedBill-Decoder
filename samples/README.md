# Synthetic OCR fixtures

All identities, account labels, dates and charges in these fixtures are fabricated test inputs. No real patient data, provider branding, contact details, or payment instructions are used. Test charges must never enter the CMS reference database.

| Fixture | Actual OCR input | Purpose |
| --- | --- | --- |
| 01_clean | `output/pdf/01_clean.pdf` | Digital PDF, four service rows and separate bill totals; all pages are rasterized before OCR |
| 02_skewed | `samples/02_skewed.png` | 200-DPI synthetic scan, +3-degree rotation, light blur/noise/gradient; description precedes code; unit price and line charge are separate |
| 03_degraded | `output/pdf/03_degraded.pdf` | Image-only PDF from a 180-DPI synthetic scan, -2-degree rotation, blur/noise/gradient; three intentionally missing or obscured fields |

`output/pdf/02_skewed.pdf` is the clean source rendering for the second fixture. Its PNG is the actual OCR test input. Missing code and amount are printed as question marks, and missing quantity as a dash; these are intentional test defects, not invented readable ground truth.

## Format references

These are original layouts based on published fields and sample statement structures, not replicas of a particular provider's forms:

- [Hazel Hawkins Memorial Hospital: Understanding Your Hospital Bill](https://www.hazelhawkins.com/images/Understanding-Your-Hospital-Bill-Updated-12.3.2025.pdf), page 1, describes service dates, units, service codes/descriptions, total charges, adjustments, and patient balance. This supplies the common itemized-row field set for all three fixtures.
- [CMS: How to read your medical bill](https://www.cms.gov/initiatives/your-patient-rights/medical-bill-rights/get-help/medical-bill-guides-resources/how-read-your-medical-bill) distinguishes statement date from service date and charges from payments and balance. This informs the headers and separately labeled totals in fixtures 1 and 2.
- [Southeast Iowa Regional Medical Center: Understanding Your Bill](https://res.cloudinary.com/dpmykpsih/image/upload/great-river-site-504/media/653850fef5604999acf4f4a3eeacf772/understanding-your-bill_southeast_iowa_regional_medical_center.pdf) shows a labeled sample statement with a title, account summary, total charges, insurance payments, and patient amount due. This informs the summary block. Its front page is a summary, not a CPT line-item grid; the itemized table here is our own construction from the published hospital field definitions.

Code strings are real CPT/HCPCS examples represented in the downloaded CMS data. Row descriptions are short synthetic bill labels. The missing-code row has no claimed CPT/HCPCS identity.

Regenerate with `python -m medbill.samples`. The generator uses fixed seeds and ReportLab's invariant output mode. `manifest.json` records expected printed fields for evaluation; neither OCR nor the parser imports it. Regeneration and evaluation intentionally write synthetic fixtures and evidence files; the runtime `extract(bytes)` function does not.
