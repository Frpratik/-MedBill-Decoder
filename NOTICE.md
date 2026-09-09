# Sources and third-party notices

The project uses public CMS reference files. Public download access is not a grant of unrestricted redistribution rights. The source package excludes `data/raw`, `data/processed`, `.tools` and `.venv`; obtain reference files from CMS and review their applicable terms before reuse. Small source excerpts and synthetic evaluation reports remain in the project for traceability. This notice does not grant rights to third-party content.

The payment archives contain the following notices, retained in the local database's `sources.copyright_notice` fields:

> CPT CODES AND DESCRIPTIONS ONLY ARE COPYRIGHT 2026 AMERICAN MEDICAL ASSOCIATION.
> ALL RIGHTS RESERVED. APPLICABLE FARS/DFARS APPLY.
> THE FOLLOWING STATEMENT APPLIES TO ALL DENTAL CODES (HCPCS START WITH LETTER D):
> COPYRIGHT 2026 AMERICAN DENTAL ASSOCIATION. ALL RIGHTS RESERVED.

The RVU source also identifies CPT codes/descriptions as copyright 2026 AMA and dental codes as copyright 2026 ADA. CMS is the source of the reference amounts; it does not endorse this prototype.

The project installs third-party software through `requirements.txt` and the Windows OCR setup script. Their licenses remain with the respective distributions, including Tesseract, its English traineddata, OpenCV, PDFium/pypdfium2, Pillow, pandas, NumPy, ReportLab, FastAPI, Starlette, Uvicorn and HTTPX. Installed distributions and executables are not bundled in the source archive. No blanket license is applied here to CMS/AMA/ADA material or third-party dependencies.

All bill identities and billed charges in the fixtures are fabricated software-test inputs. They are not real patient records, observed commercial prices or reference prices. Sample-format sources are credited in `samples/README.md`; those source documents are not redistributed as bill fixtures.
