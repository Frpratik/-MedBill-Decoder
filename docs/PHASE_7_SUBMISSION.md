# Phase 7: submission handoff

## Deliverables

- `README.md`: setup from a fresh clone, exact source links, architecture, measured results, troubleshooting, runtime limitations and the distinction between local OCR/rules and LLMs.
- `NOTICE.md`: retained source attribution and third-party notices; no blanket redistribution or license claim.
- `docs/DEVPOST_DRAFT.md`: project description with inspiration, implementation, challenges, results, limitations, future work and accurate AI-assistance disclosure.
- `docs/DEMO_VIDEO_SCRIPT.md`: suggested three-minute screen/narration plan, verified demo amounts and judge-question answers.
- `medbill/download_sources.py`: setup-only source acquisition, checksum validation and an offline check mode.
- `scripts/package_source.py`: clean-commit ZIP export with an integrity check, required-file check, excluded-path check and SHA-256 manifest.

## Actual validation

All **71 tests pass** in `docs/PHASE_7_TEST_OUTPUT.txt`. The three added setup tests confirm matching-file reuse, failure without overwriting a checksum mismatch, and no writes/downloads in missing-file check-only mode.

All five local CMS archives matched their pinned checksums (`docs/PHASE_7_SOURCE_CHECK.txt`). A live setup test downloaded the July payment archive into an isolated temporary folder: **315,623 bytes, checksum verified** (`docs/PHASE_7_DOWNLOAD_TEST.txt`). The existing reference verification also passed, with 2,075,578 payment rows and the documented lookup values (`docs/PHASE_7_REFERENCE_CHECK.txt`). This validates the downloader and configured workstation; it is not a claim that a clean installation has been tested on every operating system.

The app behavior remains as validated in Phases 5–6. Earlier detailed evidence is retained rather than rewritten to imply newly collected measurements. Full reference archives, generated SQLite, environment directories and executables are excluded from packaging; the package includes small source excerpts and explicitly synthetic fixtures/reports. End users acquire the public reference files during setup and retain the associated notices.

## Build the source archive

From a clean committed checkout:

```powershell
.\.venv\Scripts\python.exe scripts/package_source.py
```

Outputs are `dist/MedBillDecoder-source.zip` and `dist/MedBillDecoder-source.manifest.json`. The manifest records the exact Git commit, ZIP hash, byte count, file list and verification results. `dist/` is ignored by Git to avoid committing a duplicate archive. The package script exports only committed files, refuses a dirty checkout and checks that reference/runtime directories are absent. The downloaded ZIP can be extracted and set up by following its README; Python, dependencies, CMS sources and Tesseract must still be installed/acquired.

## Remaining actions for the submitter

1. Check the actual event submission form for eligibility, track, fields, deadline and video duration. These rules have not been verified or represented as known.
2. Enter real contributor details and roles. Review the draft for your own voice and accurate authorship disclosure.
3. Record the actual local demo using only synthetic examples. Review it, upload the recording, and add its real video URL.
4. Use the GitHub repository as the source link. Do not use the loopback URL as a public hosted demo link.
5. Review source/dependency terms applicable to your intended reuse. The package does not ship full CMS/AMA/ADA tables or grant third-party rights.
6. Submit the reviewed entry yourself. No Devpost entry, video, team identity or external message has been posted by the agent.

All seven implementation/documentation phases are delivered. Manual recording and submission were outside the automated build scope from the start. The app remains a synthetic-data prototype with Q3 2026 Medicare comparisons, not a real-patient billing or claims system.
