# Demo recording script

Suggested duration: about 3 minutes. This is an editing plan, not a verified event duration requirement. Check the submission form's limit before recording. Record the actual local app; no prerecorded JSON or mocked outputs are needed. Use only the included synthetic fixtures.

## Before recording

1. Run `.\.venv\Scripts\python.exe -m medbill.app` from the project root and open `http://127.0.0.1:8000`.
2. Use the default San Francisco area (`01112 / 05`), nonfacility, non-QP. These match the measured demo numbers below.
3. Run `.\.venv\Scripts\python.exe -m medbill.evaluate_edges` once if the edge images need regenerating. This intentionally saves synthetic test evidence under `docs/phase6`.
4. Close personal tabs/notifications, use a readable browser size and verify the three sample buttons work. Let each OCR job finish before starting another.
5. Keep the repository's Phase 3 and Phase 6 reports ready if you want a brief evidence cutaway. Do not expose unrelated files or credentials.

## Timeline and narration

| Time | Screen action | Suggested narration |
| --- | --- | --- |
| 0:00–0:20 | Show the local upload screen. | “Medical bills contain codes and charges, but that doesn't make them easy to understand. MedBill Decoder turns a synthetic itemized bill into explanations, reference comparisons and questions to ask.” |
| 0:20–0:40 | Click **Clean PDF**; show the actual processing message. | “This runs locally. We rasterize the PDF, preprocess it with OpenCV and read it with Tesseract. We do not use a vision API or an LLM.” |
| 0:40–1:10 | Show the four-row report and expand 99213's reference details. | “Three of these four rows have usable Medicare comparisons. Code 99213 has a $250 charge and a $117.58 local reference rate. Its $132.42 difference contributes to this sample's $384.44 total. The laboratory panel has no matching price here and is excluded.” |
| 1:10–1:35 | Show the flag explanation and billing-office questions. | “A flag requires the unit charge to exceed both the local rate and the 95th percentile across matching Medicare localities. Medicare rates are administrative benchmarks. This is not proof of an overcharge or a refund estimate.” |
| 1:35–2:00 | Click **Skewed image**, wait, and expand 97110. | “Units matter. This line is $180 for two units, so we compare $90 per unit with $35.91. Two other rows need reading review. We don't silently repair them with reference data.” |
| 2:00–2:25 | Click **Degraded PDF**, then show withheld fields. | “A damaged bill should not produce confident guesses. This sample compares only one of five rows. Unknown or uncertain values stay out of the total.” |
| 2:25–2:45 | Upload `docs/phase6/severely_blurred.png`, check the synthetic box, and decode. | “When no service rows can be read, the app asks for a clearer bill and says ‘Not calculated’—not zero dollars.” |
| 2:45–3:00 | Show questions or briefly show the repository/evidence. | “The goal is a better-informed conversation. Every benchmark uses real CMS data, explanations are local templates, and the app has no implemented upload persistence. Our tests and scoped audit are in the repository.” |

Do not cut processing footage to imply a measured speed claim. If trimming waits for time, make the edit apparent. Narration may need shortening to fit your delivery pace.

## Demonstration facts to keep consistent

| Sample | Compared / extracted | Positive difference from Medicare benchmark |
| --- | ---: | ---: |
| Clean | 3 / 4 | $384.44 |
| Skewed | 2 / 4 | $223.96 |
| Degraded | 1 / 5 | $153.60 |

All fixture charges are fabricated test inputs. Six comparable rows are not a general accuracy or error-detection rate. Template coverage is 8/13 of all candidate rows (61.54%), or all eight accepted readings—not an established 80% of real bills.

## Questions judges may ask

- **“How do you know it's overcharged?”** We do not establish that. We identify a difference from matched Medicare benchmarks and show the method and source.
- **“Where is the AI?”** Tesseract performs local OCR. Matching, statistics and explanations are deterministic; no LLM is part of the runtime.
- **“Why no commercial prices?”** This prototype chose the CMS PFS reference option. Commercial-price comparison would require additional verified, comparable data.
- **“Do you save the bill?”** The application processes bytes in memory and uses OCR pipes. The audit found no Python file mutations, no leftover scratch files and no database change in the measured cases; it does not trace all native/OS behavior.
- **“What can't it do?”** Real patient use, claim adjudication, insurer-benefit interpretation, all hospital/drug/lab prices, dates outside Q3 2026, or reliable reading of every layout/handwriting case.

## After recording

Review the video for readable text and accurate numbers. Upload it through your chosen video service yourself, then put the real link in the submission. The video recording and final submission remain your actions; the draft has not been posted anywhere.
