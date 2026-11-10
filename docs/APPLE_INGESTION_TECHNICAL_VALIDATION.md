# Apple ingestion technical validation

The seven-day Apple ingestion pilot and the 80-review human usefulness assessment are complete.
Engineering and sample-level content-quality evidence support bounded review ingestion and analysis.
Coverage and provenance limitations are included in the validation findings.

Read the [pilot report](APPLE_INGESTION_PILOT_REPORT.md) for the project conclusion
and the [review quality assessment](APPLE_REVIEW_QUALITY_ASSESSMENT.md) for the
complete human-review method and validation. The historical Phase identifiers
remain in supporting evidence filenames.

## Evidence scope

Seven actual batches ran November 3–9, 2026, at planned 09:00 America/Los_Angeles (17:00 UTC).
All 56 scheduled application runs have persisted records. There were 52 successful, one partial and three failed runs.
Validation cross-checked the companion JSON, seven daily reports and actual PostgreSQL state.
The isolated Etsy diagnostic database is excluded from all pilot totals and reference selection.
Validation covered the sample manifest, completed assessment records, database state,
daily execution evidence and backup restoration.

## Demonstrated engineering results

The original eight apps, US storefront and mostrecent sort used 2–5 logical pages, at most ten requests per target/run,
zero retries, global spacing of at least two seconds and the existing timeouts and transaction protections.
Actual runs used at most five HTTP requests each. All 155 pilot HTTP responses were 200, with zero transport failures.
There were 147 committed pages and 7,350 observations: 4,257 first-in-database records, zero changed versions and 3,093 unchanged observations.
First-in-database does not establish original publication time. No observed edits leaves real source-edit behavior unresolved.

### Daily execution

| Day | Planned UTC | Actual start UTC | Status counts |
| --- | --- | --- | --- |
| 1 | 2026-11-03T17:00:00+00:00 | 2026-11-03T17:00:50.412440+00:00 | succeeded=8 |
| 2 | 2026-11-04T17:00:00+00:00 | 2026-11-04T17:00:02.462429+00:00 | succeeded=7, failed=1 |
| 3 | 2026-11-05T17:00:00+00:00 | 2026-11-05T17:00:03.768119+00:00 | succeeded=8 |
| 4 | 2026-11-06T17:00:00+00:00 | 2026-11-06T17:00:02.537940+00:00 | succeeded=8 |
| 5 | 2026-11-07T17:00:00+00:00 | 2026-11-07T17:00:03.353966+00:00 | succeeded=8 |
| 6 | 2026-11-08T17:00:00+00:00 | 2026-11-08T17:00:03.234593+00:00 | partial=1, succeeded=5, failed=2 |
| 7 | 2026-11-09T17:00:00+00:00 | 2026-11-09T17:00:03.140676+00:00 | succeeded=8 |

All seven dates ran. The original summary flag all_seven_batches_completed=false means that not every batch was wholly successful.
It does not indicate a missing date.

### Per-application totals

Distinct reviews are review IDs actually observed by the seven formal batches. Counts exclude the separate diagnostic collection.
There were 4,357 distinct pilot-observed reviews: 4,257 new-to-database records plus 100 retained Smoke reviews.
The full database has 4,507 reviews because it also retains 150 Smoke reviews not observed in the formal pilot.

| Application | Success/partial/failure | Requests | Pages | Distinct reviews | Observations | New/changed/unchanged |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Todoist | 6/1/0 | 15 | 13 | 103 | 650 | 3/0/647 |
| Microsoft To Do | 7/0/0 | 17 | 17 | 258 | 850 | 258/0/592 |
| Duolingo | 6/0/1 | 30 | 28 | 1296 | 1400 | 1296/0/104 |
| Khan Academy | 7/0/0 | 17 | 17 | 265 | 850 | 265/0/585 |
| Amazon Shopping | 7/0/0 | 18 | 18 | 555 | 900 | 555/0/345 |
| Etsy | 5/0/2 | 17 | 13 | 400 | 650 | 400/0/250 |
| Uber | 7/0/0 | 23 | 23 | 852 | 1150 | 852/0/298 |
| Lyft | 7/0/0 | 18 | 18 | 628 | 900 | 628/0/272 |

## Coverage findings

ID overlap measures the intersection of observed windows. It does not prove complete source coverage.
The overlap ratio divides matching IDs by current committed distinct IDs. Baselines have no prior reference.
Partial runs retain their measured observations but remain ineligible as reliable comparison references.

| Application | D1 | D2 | D3 | D4 | D5 | D6 | D7 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Todoist | 100.00% | 99.00% | 100.00% | 100.00% | 98.00% | partial (100.00%) | 100.00% |
| Microsoft To Do | baseline | 99.00% | 99.00% | 98.00% | 99.00% | 98.00% | 99.00% |
| Duolingo | baseline | 10.00% insufficient | 20.67% | 0.00% insufficient | 19.20% insufficient | failed | 0.00% insufficient |
| Khan Academy | baseline | 99.00% | 98.00% | 92.00% | 98.00% | 100.00% | 98.00% |
| Amazon Shopping | baseline | 50.00% | 77.00% | 44.67% | 57.00% | 41.00% | 53.00% |
| Etsy | baseline | failed | 63.00% | 61.00% | 81.00% | failed | 45.00% |
| Uber | baseline | 23.00% | 67.00% | 28.00% | 38.67% | 27.50% | 26.00% |
| Lyft | baseline | 45.00% | 57.00% | 21.00% | 44.00% | 39.33% | 46.00% |

Reference intervals were approximately 24 hours except for documented gaps. Todoist Day 1 references same-day Smoke at 3.941060 hours.
Etsy Day 3 references Day 1 at 47.980820 hours. Todoist, Duolingo and Etsy Day 7 reference Day 5 at approximately 48 hours,
excluding the partial/failed Day 6 runs. All selected intervals were below the 72-hour warning threshold.

### Duolingo

Overlap was 25/250 (10%) on Day 2, 31/150 (20.67%) on Day 3, 0/250 on Day 4, 48/250 (19.2%) on Day 5 and 0/250 on Day 7.
Days 2, 4, 5 and 7 reached five pages with insufficient overlap. Day 5 met the 20-ID count but missed the 20% ratio.
Day 6 failed; the next reference interval extended to 48.000540 hours. Day 5 correctly referenced the otherwise clean Day 4 run,
confirming that insufficient overlap did not break the comparison chain. This is not the low-volume absolute-threshold case.
The immediate reason is insufficient intersection of bounded windows. The contributions of new source arrivals, visibility changes
and ordering cannot be separated from current evidence. Daily collection with five pages has not demonstrated sufficient continuous coverage for this app.

## Day 2 and Day 6 anomalies

### Day 2 Etsy

Run 148dca7b-3047-407b-9bca-b2c77b6df453 received 873-byte JSON with no feed.entry and fell back to 113,503-byte Atom XML.
XML/Atom envelope parsing passed, but ENTRY_SCHEMA rejected the page. Field-level diagnostics were not yet available.
The original response was not retained. The separate later diagnostic returned valid JSON, so the historical field failure remains unknown.

### Day 6 confirmed failure path

All three Atom failures recorded category=duplicate_field, field=content, entry_index=1 (one-based).
The parser detected a second Atom content child in the same entry before attempting nested-text extraction.

| Application | Run ID | Outcome |
| --- | --- | --- |
| Todoist | fdfb327f-dc9f-4900-956f-ce810acafe5c | Page 1 retained 50 unchanged observations. Page 2 JSON omitted entry; Atom fallback failed. Partial. |
| Duolingo | d12a126b-a294-473d-802c-9a700edac0b2 | Page 1 JSON omitted entry; Atom fallback failed. No committed pages. |
| Etsy | 2d94d994-e77a-4b69-bfa5-7d7d6f8b1a54 | Page 1 JSON omitted entry; Atom fallback failed. No committed pages. |

Atom limits an entry to one content element. The observed duplicate-field path violates that constraint, so strict rejection follows the approved behavior.
The reference is [RFC 4287 section 4.1.2](https://www.rfc-editor.org/rfc/rfc4287.html#section-4.1.2).
Content type attributes and raw responses were not saved, leaving the intended meaning of duplicate representations unknown.
No nested-XHTML defect was demonstrated by these diagnostics. Choosing one duplicate would require an explicit future compatibility decision.
The reason for missing JSON entries remains unknown. Equal response sizes alone cannot establish identical responses, denial or rate limiting.
Day 7 JSON succeeded for all three apps. The fallback failure nevertheless limits resilience to nonstandard Atom responses.
The exact Day 2 cause cannot be assigned retrospectively from Day 6.

## Database integrity, backups and retirement

- Technical preflight verified the seven ingestion tables, Alembic revision, eight-app seeds and actual owner/runtime/report logins.
- The database contains 57 runs and 160 fetch attempts including Smoke; 4,507 reviews/versions and 7,600 observations including Smoke.
- All 4,507 stored versions matched recalculated full title/body and metadata fingerprints. Every version number is 1. Six integrity issue counters were zero.
- Daily immutable requests, pages, observations and terminal results matched PostgreSQL and companion JSON. Age-dependent reference warnings were treated separately.
- Smoke retains 250 versions and 250 observations; its immutable checksums and Day 1 checksums matched. All failed and partial evidence is retained.
- All 14 pre/post-batch backups matched size and SHA-256 and passed archive listing, with mode 0600.
- The final backup was fully restored into an isolated private database. Counts, integrity and 4,507 fingerprints passed; that verification database was removed.
- Backups are on the local WSL storage. Independent-disk, off-host and whole-machine disaster recovery have not been demonstrated.
- Both Windows tasks were verified Disabled with Enabled=false. The collection task last exited 0 and has no next trigger.
- The disabled maintenance task retains its November 10 trigger definition. Its never-run status 267011 does not indicate a pilot failure.
- The retirement marker exists, targets are disabled and the project policy and later-day activation are false.
- Acceptance started the existing PostgreSQL service solely for audit. Collection was not restarted. Linux/WSL is the verified runtime.

## Human assessment summary

Reviewer R1 manually assessed 80 reviews, ten per application and 20 per
analytical category. Every review/version reference and sampled full text
matched PostgreSQL. Each assessment records a label, reason, language and
full-text reading declaration.
The sample contains 77 English, two Spanish and one Russian review.

The `summarize_assessment` pipeline calculated **47/80 useful reviews
(58.75%)**, where U2/U3 are useful. Counts are U3=21, U2=26, U1=28 and U0=5.
All 80 were assessed, with zero unassessed or sample shortfall. Each application's
rate has a denominator of ten, so a single judgement changes it by ten percentage
points. These describe the equal-allocation sample, rather than a volume-weighted
rate for the entire review corpus or an estimate for the App Store population.

| Category | Assessed | U3 | U2 | U1 | U0 | Useful (U2/U3) | Rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Education | 20 | 4 | 7 | 9 | 0 | 11 | 55.00% |
| Productivity | 20 | 9 | 7 | 3 | 1 | 16 | 80.00% |
| Shopping | 20 | 5 | 7 | 6 | 2 | 12 | 60.00% |
| Transportation | 20 | 3 | 5 | 10 | 2 | 8 | 40.00% |

| Application | Assessed | U3 | U2 | U1 | U0 | Useful (U2/U3) | Rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Todoist | 10 | 6 | 2 | 2 | 0 | 8 | 80.00% |
| Microsoft To Do | 10 | 3 | 5 | 1 | 1 | 8 | 80.00% |
| Duolingo | 10 | 2 | 4 | 4 | 0 | 6 | 60.00% |
| Khan Academy | 10 | 2 | 3 | 5 | 0 | 5 | 50.00% |
| Amazon Shopping | 10 | 2 | 5 | 2 | 1 | 7 | 70.00% |
| Etsy | 10 | 3 | 2 | 4 | 1 | 5 | 50.00% |
| Uber | 10 | 0 | 3 | 5 | 2 | 3 | 30.00% |
| Lyft | 10 | 3 | 2 | 5 | 0 | 5 | 50.00% |

Ratings were hidden in the existing HTML reading material. Usefulness evaluates
the information in the text independently of sentiment. Sentiment assessment
remains `NOT_PERFORMED`.
The optional fixed second-review subset contains 16 records.

### Assessment record validation

The completed assessment passed checks against the original sample manifest
and response schema. Labels, reasons, languages, reviewer identity and version
references remain intact. The private project state directory contains the
schema-compatible response copy and pipeline summary.

The original response file has SHA-256
`85e605f373ed53b752e52a0311763f7c14097d90aedef830c9c06f0c82c7a63e`.
The derived responses and validation record are in
`day7/human-assessment.validated/`, with directory mode 0700 and file mode 0600.
The original completed directory/files retain modes 0755/0644 within a private
0700 parent. The report contains aggregate results; review-level material remains private.

## Comparison with earlier feasibility evidence

In the initial Apple/Google feasibility comparison, 28/40 Apple reviews (70%)
were classified as useful. The assessment used the first five page-1 reviews
per app, AI-assisted judgements and a binary usefulness definition. Three Apple reviews
were limited to 500-character prefixes.

The pilot selected ten reviews per app from the accumulated LIVE corpus and
used full-text manual U0–U3 assessment. Both assessments used the same eight-app,
four-category frame and hid ratings. Different samples, reading limits and
assessment methods prevent interpreting 70% versus 58.75% as a quality trend
or agreement measurement.
The initial RSS field sample used a length screen without a semantic usefulness
percentage.

Historical comparisons are preserved in
[the mobile feasibility comparison](../results/mobile_review_comparison.md) and
[the initial RSS assessment](../results/mainstream_review_assessment.md).

## Technical conclusion

The bounded engineering pilot and human sample review are complete. The evidence supports the technical feasibility of private, bounded Apple review ingestion.
Five apps succeeded in all seven runs. Todoist had one partial run, Duolingo one failure and four insufficient-overlap windows, and Etsy two failures.
Human usefulness is demonstrated for 47 selected records, with substantial app/category variation and no independent second-review agreement estimate.
The applicable data-use basis, permitted scope and long-term full-text, backup and export retention arrangements remain unresolved.
The long_term technical setting imposes no automatic TTL. It does not determine applicable data-use rights.

## Daily run evidence index

The [technical evidence metadata](archive/APPLE_PHASE_F_FINAL_ACCEPTANCE_METADATA.json)
retains exact reference run IDs, intervals, anomaly metadata and backup checksums.
The [human assessment summary](archive/APPLE_PHASE_F_HUMAN_ASSESSMENT_SUMMARY.json)
contains the existing-pipeline aggregates and provenance validation.
| Application/day | Run ID | Execution/coverage | New/changed/unchanged | Overlap IDs/rate | Reference interval h |
| --- | --- | --- | --- | --- | --- |
| Todoist D1 | 5a12a0f1-abf9-4d19-b41b-93f09d29f253 | succeeded / overlap_sufficient | 0/0/100 | 100 / 100.00% | 3.941060 |
| Todoist D2 | f986a86e-6018-4d13-a56d-c76c19408c0d | succeeded / overlap_sufficient | 1/0/99 | 99 / 99.00% | 23.986678 |
| Todoist D3 | bb22c5b0-8974-414e-a0ff-7d0b26307697 | succeeded / overlap_sufficient | 0/0/100 | 100 / 100.00% | 24.000362 |
| Todoist D4 | 8b206ad4-3383-4b06-b4b8-dc86e490057b | succeeded / overlap_sufficient | 0/0/100 | 100 / 100.00% | 23.999661 |
| Todoist D5 | 25db6a4b-c2dd-4fb0-ba8f-cd1cca70d179 | succeeded / overlap_sufficient | 2/0/98 | 98 / 98.00% | 24.000224 |
| Todoist D6 | fdfb327f-dc9f-4900-956f-ce810acafe5c | partial / indeterminate | 0/0/50 | 50 / 100.00% | 23.999967 |
| Todoist D7 | 89967295-4cdc-4a12-ab64-3081910d3acf | succeeded / overlap_sufficient | 0/0/100 | 100 / 100.00% | 47.999941 |
| Microsoft To Do D1 | 4d26620b-1141-49d5-91de-af97856f06f5 | succeeded / baseline | 250/0/0 | — / — | — |
| Microsoft To Do D2 | 7218ec9d-8ea4-433e-b092-59d97c927a08 | succeeded / overlap_sufficient | 1/0/99 | 99 / 99.00% | 23.986666 |
| Microsoft To Do D3 | 521e7833-a27b-4f98-a8d8-45ef8ba24cd1 | succeeded / overlap_sufficient | 1/0/99 | 99 / 99.00% | 24.000500 |
| Microsoft To Do D4 | 12e6010a-e5aa-437c-bdd8-50162c6a1e95 | succeeded / overlap_sufficient | 2/0/98 | 98 / 98.00% | 23.999625 |
| Microsoft To Do D5 | fa87963e-8ced-4495-9b85-e7d45684bd6d | succeeded / overlap_sufficient | 1/0/99 | 99 / 99.00% | 24.000106 |
| Microsoft To Do D6 | fbb25667-e91b-49b7-9ed6-8721a06023d0 | succeeded / overlap_sufficient | 2/0/98 | 98 / 98.00% | 24.000275 |
| Microsoft To Do D7 | 6e678f74-c29e-4f96-9f1c-b7758242f768 | succeeded / overlap_sufficient | 1/0/99 | 99 / 99.00% | 24.000712 |
| Duolingo D1 | 988b3813-74e2-44cf-abbb-c63a90d0e7e1 | succeeded / baseline | 250/0/0 | — / — | — |
| Duolingo D2 | c880e9ec-b32c-4b85-9aa4-7dce547bb2aa | succeeded / overlap_insufficient | 225/0/25 | 25 / 10.00% | 23.984941 |
| Duolingo D3 | 3ca8761a-20d9-4db8-a684-0c00fe37d588 | succeeded / overlap_sufficient | 119/0/31 | 31 / 20.67% | 24.000186 |
| Duolingo D4 | 7cf27308-d7fc-40ab-b898-306804254c30 | succeeded / overlap_insufficient | 250/0/0 | 0 / 0.00% | 23.999818 |
| Duolingo D5 | f625b9d3-5e0e-4481-aa66-cc5564d15e80 | succeeded / overlap_insufficient | 202/0/48 | 48 / 19.20% | 24.000289 |
| Duolingo D6 | d12a126b-a294-473d-802c-9a700edac0b2 | failed / indeterminate | 0/0/0 | 0 / — | 24.000215 |
| Duolingo D7 | acf5a188-02db-4e84-b587-3efe1267acba | succeeded / overlap_insufficient | 250/0/0 | 0 / 0.00% | 48.000540 |
| Khan Academy D1 | 52fa95d8-f081-4b31-8b4e-5c413c423bfc | succeeded / baseline | 250/0/0 | — / — | — |
| Khan Academy D2 | 6355a41a-37c0-4edd-a060-daa0bd4ef84e | succeeded / overlap_sufficient | 1/0/99 | 99 / 99.00% | 23.984967 |
| Khan Academy D3 | 3114117a-7d99-472f-b441-791328c63e0d | succeeded / overlap_sufficient | 2/0/98 | 98 / 98.00% | 23.999034 |
| Khan Academy D4 | 6b14df25-2cbe-4c7f-b3e4-b0d41c6924b0 | succeeded / overlap_sufficient | 8/0/92 | 92 / 92.00% | 24.001050 |
| Khan Academy D5 | db2faf7d-82a3-43ad-b35e-902d4c72ff79 | succeeded / overlap_sufficient | 2/0/98 | 98 / 98.00% | 24.000175 |
| Khan Academy D6 | 70172729-8d3b-4412-85cc-3d6de6c0b05c | succeeded / overlap_sufficient | 0/0/100 | 100 / 100.00% | 23.998544 |
| Khan Academy D7 | d519c73f-226e-415a-846c-176cb70d2209 | succeeded / overlap_sufficient | 2/0/98 | 98 / 98.00% | 24.002025 |
| Amazon Shopping D1 | 9dc01631-eda2-4c03-b4c0-958a2ca4ddd9 | succeeded / baseline | 250/0/0 | — / — | — |
| Amazon Shopping D2 | ccd5e4e0-0a19-4513-b65a-e6e48c3ec39d | succeeded / overlap_sufficient | 50/0/50 | 50 / 50.00% | 23.983382 |
| Amazon Shopping D3 | 6c2e9afe-ac7b-45df-9865-d1f0b09f0a3b | succeeded / overlap_sufficient | 23/0/77 | 77 / 77.00% | 23.999244 |
| Amazon Shopping D4 | d2c0a44b-9cbc-4588-9854-2a0f703f7d82 | succeeded / overlap_sufficient | 83/0/67 | 67 / 44.67% | 24.001005 |
| Amazon Shopping D5 | 851deb6a-0bf2-4057-8a1d-e9b3a0c20ca9 | succeeded / overlap_sufficient | 43/0/57 | 57 / 57.00% | 24.000170 |
| Amazon Shopping D6 | d39a6b68-9b01-449b-b889-993af9a7631d | succeeded / overlap_sufficient | 59/0/41 | 41 / 41.00% | 23.998612 |
| Amazon Shopping D7 | 73031434-a214-4501-bb5a-374418648ac5 | succeeded / overlap_sufficient | 47/0/53 | 53 / 53.00% | 24.001763 |
| Etsy D1 | 787025a2-f9bc-47df-b667-ea440e2d341a | succeeded / baseline | 250/0/0 | — / — | — |
| Etsy D2 | 148dca7b-3047-407b-9bca-b2c77b6df453 | failed / indeterminate | 0/0/0 | 0 / — | 23.981607 |
| Etsy D3 | c212198a-f1e4-47c0-a943-046ee1097528 | succeeded / overlap_sufficient | 37/0/63 | 63 / 63.00% | 47.980820 |
| Etsy D4 | 6a089221-7d41-428f-b5b0-6c869e6bfcdc | succeeded / overlap_sufficient | 39/0/61 | 61 / 61.00% | 24.001646 |
| Etsy D5 | eaefbefc-487a-422e-b1c3-1d75973fb066 | succeeded / overlap_sufficient | 19/0/81 | 81 / 81.00% | 23.999583 |
| Etsy D6 | 2d94d994-e77a-4b69-bfa5-7d7d6f8b1a54 | failed / indeterminate | 0/0/0 | 0 / — | 23.998650 |
| Etsy D7 | de7ede30-b109-49b8-a02a-051c1876a680 | succeeded / overlap_sufficient | 55/0/45 | 45 / 45.00% | 48.000379 |
| Uber D1 | c0b60412-33a9-4f34-8475-13b53a181eb7 | succeeded / baseline | 250/0/0 | — / — | — |
| Uber D2 | 5fef54ec-d008-4378-a89e-a43e19990b12 | succeeded / overlap_sufficient | 77/0/23 | 23 / 23.00% | 23.979980 |
| Uber D3 | b653b42e-3b0c-4fee-9c8e-cf15af1182a3 | succeeded / overlap_sufficient | 33/0/67 | 67 / 67.00% | 23.999248 |
| Uber D4 | 71e04323-816c-4a56-a6b3-6aba3482766c | succeeded / overlap_sufficient | 144/0/56 | 56 / 28.00% | 24.001363 |
| Uber D5 | 175fdba7-fc2d-4696-a81e-b965ae786c68 | succeeded / overlap_sufficient | 92/0/58 | 58 / 38.67% | 23.999847 |
| Uber D6 | 2a3f7397-6e94-422a-a63a-a28d7f1fea92 | succeeded / overlap_sufficient | 145/0/55 | 55 / 27.50% | 23.998662 |
| Uber D7 | ae1c6233-af35-4404-a99d-cb56c610dcac | succeeded / overlap_sufficient | 111/0/39 | 39 / 26.00% | 24.001700 |
| Lyft D1 | c45228a3-af9e-4d1e-a868-193d97d4fb01 | succeeded / baseline | 250/0/0 | — / — | — |
| Lyft D2 | 6068ad7d-df15-4a17-8f18-839e54a648f0 | succeeded / overlap_sufficient | 55/0/45 | 45 / 45.00% | 23.978431 |
| Lyft D3 | fe59b310-7bd8-4a11-bdf9-b1e2a04fb5d2 | succeeded / overlap_sufficient | 43/0/57 | 57 / 57.00% | 23.999270 |
| Lyft D4 | 28ee4795-9d18-4706-9a9e-d0830df8fd55 | succeeded / overlap_sufficient | 79/0/21 | 21 / 21.00% | 24.002471 |
| Lyft D5 | a0dc7442-571f-4e74-9778-ed0f30bddb71 | succeeded / overlap_sufficient | 56/0/44 | 44 / 44.00% | 23.999245 |
| Lyft D6 | 6857cb58-4206-4294-978e-d50a314510c5 | succeeded / overlap_sufficient | 91/0/59 | 59 / 39.33% | 23.999226 |
| Lyft D7 | e373e1fc-2ecb-4afc-821b-099bcf867a5e | succeeded / overlap_sufficient | 54/0/46 | 46 / 46.00% | 24.001158 |

The diagnostics regression checkpoint recorded 676 passing tests before commit 022c70b.
