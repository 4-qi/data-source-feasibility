# Duolingo Review Coverage Experiment Results

## Objective

Determine whether deeper daily collection or shallower twice-daily collection
better maintains review-window overlap for Duolingo, and compare the request
cost and distinct-ID reach of each option.

## Experimental Design

The experiment tested whether more frequent collection or deeper pagination improved continuity for Duolingo (570060128), US storefront, sorted by `mostrecent`. Seven fixed-depth acquisitions collected pages 1–10 at nominal 12-hour intervals. Four strategies were evaluated offline by selecting five- or ten-page prefixes and using a lag of one or two observations. A and B use W0, W2, W4 and W6 for primary comparisons and W1, W3 and W5 for supplementary comparisons. C and D use all seven windows. An overlap passes when at least two pages are present, at least 20 IDs are shared, and shared IDs account for at least 20% of distinct IDs in the current window.

A prefix requires contiguous, validated pages and acceptable integrity checks. A failure after page 5 can leave a valid five-page prefix even when the ten-page window is indeterminate. All required prefixes were valid in this series. The recorded failed W0 from the first series used one HTTP 200 request, parsed 50 entries and committed zero observations. It was recovered as interrupted with indeterminate coverage, and its request and data were excluded from the replacement series and all strategy comparisons. [Experiment plan](APPLE_HIGH_VOLUME_COVERAGE_EXPERIMENT.md) · [Runner repair and replacement](APPLE_COVERAGE_EXPERIMENT_REPAIR.md) · [Original activation](APPLE_COVERAGE_EXPERIMENT_ACTIVATION.md)

## Collection Results

All dates are in November 2026. Actual start is the timestamp used by the offline comparer at runner entry. The first-to-last start span was 71 h 59 min 59.644 s. Each observation succeeded and used 10 physical JSON requests, all HTTP 200, with 10 pages committed and 500 parsed occurrences. There were no missed observations, retries, fallbacks, parsing failures, conflicts, or unresolved request reservations.

| Window | Planned UTC | Actual start UTC | Distinct IDs in 5 / 10 pages | First stored / changed / unchanged | Duplicate occurrences | Stored coverage |
| --- | --- | --- | ---: | ---: | ---: | --- |
| W0 | Nov 14 05:00:00 | Nov 14 05:00:04.838 | 250 / 500 | 500 / 0 / 0 | 0 | Baseline |
| W1 | Nov 14 17:00:00 | Nov 14 17:00:04.727 | 250 / 500 | 98 / 1 / 401 | 0 | Sufficient |
| W2 | Nov 15 05:00:00 | Nov 15 05:00:05.098 | 200 / 450 | 64 / 1 / 385 | 50 | Sufficient |
| W3 | Nov 15 17:00:00 | Nov 15 17:00:04.588 | 250 / 500 | 162 / 0 / 338 | 0 | Sufficient |
| W4 | Nov 16 05:00:00 | Nov 16 05:00:04.661 | 200 / 450 | 128 / 0 / 322 | 50 | Sufficient |
| W5 | Nov 16 17:00:00 | Nov 16 17:00:04.609 | 250 / 500 | 146 / 0 / 354 | 0 | Sufficient |
| W6 | Nov 17 05:00:00 | Nov 17 05:00:04.482 | 250 / 500 | 149 / 0 / 351 | 0 | Sufficient |

The 100 cross-page duplicate occurrences were concentrated on W2 pages 3–4 and W4 pages 4–5. They reduced distinct window sizes without causing conflicts. PostgreSQL contained 1,247 distinct reviews, 1,249 stored versions and 3,400 observation rows. First-stored reviews are counted relative to the isolated database.

## Strategy Comparison

| Strategy | Schedule | Primary sufficient / evaluable / planned | Supplementary sufficient / evaluable | Requests on primary trajectory | Requests per actual elapsed day, including initial window | Distinct IDs across primary windows |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| A | 24 h, 5 pages | 0 / 3 / 3 | 0 / 2 | 20 | 6.67 | 862 |
| B | 24 h, 10 pages | 3 / 3 / 3 | 2 / 2 | 40 | 13.33 | 1,247 |
| C | 12 h, 5 pages | 6 / 6 / 6 | — | 35 | 11.67 | 997 |
| D | 12 h, 10 pages | 6 / 6 / 6 | — | 70 | 23.33 | 1,247 |

Costs are the physical requests recorded through the candidate depth in the selected windows, including each trajectory's initial window. Actual acquisition cost was **70 of the 140 allowed requests**, with 10 of 20 allowed at each slot. Reserved requests with unknown outcomes would count against the budget. There were zero in this series. The earlier seven-request pagination probe and the one failed original W0 request are separate costs.

The cells below show shared distinct IDs over current distinct IDs and the resulting percentage. A dash marks a comparison outside the strategy's defined trajectory. Rows ending at W2, W4 and W6 form the common-endpoint comparison.

| Current | Actual 12 h interval (s) | C | D | Actual 24 h interval (s) | A | B |
| --- | ---: | --- | --- | ---: | --- | --- |
| W1 | 43,199.890 | 152/250 (60.8%) | 402/500 (80.4%) | — | — | — |
| W2 | 43,200.370 | 136/200 (68.0%) | 386/450 (85.8%) | 86,400.260 | 38/200 (19.0%) | 288/450 (64.0%) |
| W3 | 43,199.490 | 88/250 (35.2%) | 338/500 (67.6%) | 86,399.861 | 25/250 (10.0%) | 275/500 (55.0%) |
| W4 | 43,200.073 | 72/200 (36.0%) | 322/450 (71.6%) | 86,399.563 | 0/200 (0.0%) | 160/450 (35.6%) |
| W5 | 43,199.948 | 104/250 (41.6%) | 354/500 (70.8%) | 86,400.021 | 0/250 (0.0%) | 226/500 (45.2%) |
| W6 | 43,199.873 | 101/250 (40.4%) | 351/500 (70.2%) | 86,399.821 | 0/250 (0.0%) | 205/500 (41.0%) |

W3 and W5 are supplementary for A and B. At the common endpoints, B and C both passed all three pairs. The number of current IDs absent from the specified prior window at W2, W4 and W6 was respectively 162, 200 and 250 for A, 162, 290 and 295 for B, and 64, 128 and 149 for both C and D. These counts describe turnover relative to a chosen window.

### Production Early-Stop Replay

The offline replay starts each strategy with a full-depth baseline and then applies the production overlap stop using the prefix that its own preceding replay retained. A successful window at the depth cap can remain eligible as a reference despite insufficient overlap. The replay costs below are counterfactual and do not enter the collection ledger.

| Strategy | Pages selected per primary window | Sufficient / evaluated | Replay requests |
| --- | --- | ---: | ---: |
| A | 5, 5, 5, 5 | 0 / 3 | 20 |
| B | 10, 6, 9, 8 | 3 / 3 | 33 |
| C | 5, 3, 2, 5, 2, 4, 4 | 6 / 6 | 25 |
| D | 10, 3, 2, 5, 2, 4, 4 | 6 / 6 | 30 |

C retained sufficient overlap at the lowest replay cost among the passing strategies. D's five-request replay premium over C came entirely from initialization. Its fixed-depth premium is larger because the actual experiment continued fetching pages even after overlap could have been met.

## Version-Change Findings

Both changed observations retained the same source review identity across
versions. Each linked the new version to the observing run and page, and each
prior version had been observed before the change. Recomputed content and
metadata fingerprints matched the stored fingerprints for all four versions.

| Observation | Detecting run | Page | Version transition | Changed canonical field | Content fingerprint | Metadata fingerprint |
| --- | --- | ---: | --- | --- | --- | --- |
| W1 | `05f4e251-a9d4-4bd5-a8cc-d65b0af3fa6c` | 5 | 1 → 2 | Rating | Identical | Changed |
| W2 | `4160f30b-d80a-40d7-bc8e-f9b185101cbb` | 5 | 1 → 2 | Rating | Identical | Changed |

The stored rating integers differed. Title, body, application version and source
update timestamp were equal both before and after canonicalization. Text
normalization and timestamp representation therefore do not explain either
version change. Each event confirms a change in the rating observed for the
same source ID, with no confirmed text change. The feed evidence does not
identify an actor or establish whether either change was a user edit, a source
correction or another source-side update.

## Limitations

The study covers one app, one storefront and approximately 72 hours. The
strategies reuse shared observations and the comparisons are dependent. The
costs of early stopping are offline estimates. Distinct-ID reach and sufficient
overlap describe the sampled windows. Reviews absent from every window are
unmeasured. The preferred configuration may differ across apps or time periods.

## Recommendation and Next Steps

For Duolingo, use **12-hour collection with a maximum depth of five pages**
when the primary objective is efficient overlap continuity. Strategy C passed
all six primary comparisons at 35 recorded requests and would have used 25
under the offline early-stop replay. Strategy B remains a valid alternative
when broader observed reach or once-daily scheduling matters more. It passed
all three primary and both supplementary comparisons, reached 250 more IDs
than C on its primary trajectory, and used 40 recorded requests or 33 in replay.

The 35-versus-40 comparison includes each strategy's initial window. Both
strategies have a nominal fixed-depth cost of ten JSON requests per day after
initialization. Strategy D had higher 12-hour overlap than C at every pair, but
doubled its fixed-depth cost and surfaced the same ID union as B in this sample.
Strategy A failed the overlap criterion at all five evaluated pairs.

Depth and interval are candidates for future per-app tuning. Escalation,
cooldown and downgrade rules require separate validation.
[Adaptive collection strategy](APPLE_ADAPTIVE_COLLECTION_STRATEGY.md)

## Verification and closeout

The existing offline comparer reproduced the retained comparison. All seven verification receipts passed without pending attempts. The end-of-study SELECT-only check confirmed the 70 committed fetch attempts, zero enabled experiment targets and zero integrity issues. The execution manifest is disabled and retired. Both replacement Windows tasks, both original coverage tasks and both earlier pilot tasks are disabled. The original pilot database digest matches its baseline.

Project decisions about permitted data use and long-term retention remain open. This analysis concerns the technical results of the bounded collection. [Pilot report](APPLE_INGESTION_PILOT_REPORT.md)
