# Apple Review ABSA Processing Contract

ABSA preparation v1 produces one review-level record for future aspect
extraction and aspect-level sentiment classification. It preserves wording,
context and source provenance for multilingual review analysis.

**PostgreSQL → Current Review Retrieval → Private CSV Export → Deterministic ABSA Preparation → Analysis-ready CSV**

## Input and identity

Use one completed, unmodified private export from the
[Apple review retrieval contract](APPLE_REVIEW_RETRIEVAL_CONTRACT.md).
Its directory contains `reviews.csv` with the exact current-review header and
`manifest.json` with the retrieval contract version, dataset label, filters,
export timestamp and row count. The exporter selects a single application
from a single explicitly verified database in a read-only snapshot.

The processor checks the header, row width, null escaping, required fields,
scalar formats, manifest version, application and row count. It rejects
duplicate source review IDs, internal review IDs and version IDs. Source
identity is `(source, source_application_id, source_review_id)`. The dataset
label scopes internal IDs to the selected database. Keep it unique across
databases and process their exports separately. The upstream manifest records
a caller-supplied label and has no input checksum or database name field.
Database identity and current-version selection are established by the
approved exporter. The processor cannot authenticate a hand-edited export
or independently infer either fact from CSV rows.

Observation counts pass through as provenance. Different source identities
remain separate when their title and body coincide. Output is ordered by
numeric internal review ID and contains one row for every valid input row,
including reviews excluded from text analysis.

## Text preparation

1. Interpret null and empty title as absent for text construction. A null body
   is malformed under the retrieval contract. An empty body is valid.
2. For each field, convert CRLF and lone CR to LF, normalize to Unicode NFC
   and trim the Unicode White_Space characters fixed in the v1 implementation
   from both edges. Internal spaces and meaningful line breaks are preserved.
3. Join nonempty components in title-then-body order with two LF characters.
   If both components are empty after preparation, return an empty string.
4. Set `has_text` and `is_analysis_eligible` from whether `analysis_text` is
   nonempty. Set `text_length` to its Unicode code point count, including any
   separator. Exclude text with no content after preparation. Use
   `missing_text` when both source fields are null or empty and
   `whitespace_only` when at least one contains whitespace but neither has
   content. A one-character response can be eligible.
5. Set `language_status` to `unknown`. The current retrieval projection
   supplies no reliable language field. All languages remain in scope.
   Any future English-only selection requires reliable language metadata.

NFC makes canonically equivalent forms consistent while preserving
punctuation, emoji, capitalization, negation and numbers. Those signals can
matter to both the aspect and the sentiment it expresses. Eligibility
measures text presence. The pilot's manual U0–U3 usefulness rubric stays
separate from the preparation rules. Rating is unchanged metadata.

Synthetic examples below use `\r` and `\n` to display line endings.

| Original title | Original body | Analysis text | Eligible | Exclusion reason |
| --- | --- | --- | --- | --- |
| `"  Settings  "` | `"I do NOT want ads. 😕\r\nFix the price!"` | `"Settings\n\nI do NOT want ads. 😕\nFix the price!"` | True | NULL |
| NULL | `"好"` | `"好"` | True | NULL |
| `""` | `" \t"` | `""` | False | `whitespace_only` |
| NULL | `""` | `""` | False | `missing_text` |

## CSV and manifest

The output is UTF-8 with CRLF record delimiters and normal CSV quoting.
Use the retrieval decoder after CSV parsing. Its reserved `\N` means NULL.
An additional leading backslash escapes a non-null value beginning with a
backslash. Inherited fields preserve their decoded values exactly. In
particular, NULL, empty string, literal `\N` and multiline values stay
distinct. Keep source identifiers as strings.

| Columns in order | Meaning |
| --- | --- |
| `source`, `source_application_id`, `source_review_id`, `review_id`, `version_id`, `version_number` | Original review and exact current-version identity |
| `title`, `body`, `rating`, `application_version`, `source_updated_at` | Original stored version fields |
| `first_observed_at`, `last_observed_at`, `version_first_observed_at`, `detecting_run_id`, `detecting_batch_id`, `detecting_run_status`, `storefront`, `sort_by`, `observation_count`, `conflict_occurrence_count` | Original collection provenance |
| `analysis_text`, `has_text`, `text_length`, `is_analysis_eligible`, `exclusion_reason`, `language_status` | Derived string, boolean, integer, boolean, nullable reason and language status. CSV booleans are `True` and `False`. |
| `source_dataset_label`, `processing_contract_version`, `processing_config_id` | Input dataset label and reproducible preparation identifiers |

The sidecar records the input contract and filters, dataset label, processing
contract and configuration, Unicode database version, input/output counts,
eligibility and language counts, and SHA-256 of each CSV's exact bytes. The
configuration ID has the form
`apple-absa-processing/v1/nfc-ucd-<version>`. Pass the recorded Unicode
version to require a matching Python runtime. NFC uses that Unicode data
version and the rules are independent of locale. Run timestamps and local
paths are absent from the result. Identical input CSV bytes, dataset label,
filters and processing configuration reproduce both output files byte for
byte, regardless of the retrieval export timestamp.

Use a new absolute output directory outside a Git checkout. Its parent must
exist. The processor creates a mode-0700 directory and mode-0600 files on a
filesystem that supports these permissions. The sidecar appears only after
the CSV is complete. Keep both source and prepared CSVs in private project
storage. Review text, private paths and credentials are excluded from the
manifest and CLI output. Actual review content stays outside Git. The
processor works offline and opens no database connections.

## Run

Activate the project environment. For a fresh retrieval export, configure
`APPLE_INGESTION_REPORT_URL` privately for the retained Duolingo database.
Set `PRIVATE_DEPLOYMENT_FILE` and `PRIVATE_DATA_DIR` to the local deployment
file and an existing private directory, respectively.

```sh
python -m feasibility.apple_ingestion.retrieval_export \
  --deployment "$PRIVATE_DEPLOYMENT_FILE" \
  --expected-database apple_coverage_main_20261113_2100 \
  --dataset-label duolingo-coverage-20261113-2100 \
  --app-id 570060128 \
  --output-dir "$PRIVATE_DATA_DIR/retrieval"

python -m feasibility.apple_ingestion.absa_processing \
  --input-dir "$PRIVATE_DATA_DIR/retrieval" \
  --output-dir "$PRIVATE_DATA_DIR/processed" \
  --unicode-version 15.0.0
```

For an existing completed export, run only the second command. Re-run it
with a fresh output directory and compare the output CSV SHA-256 or both
files byte for byte. The same module provides `process_review` and
`process_reviews` for decoded CSV rows (input strings or `None`) and
`export_processed_reviews` for a complete export directory.

## Validation results

The retained Duolingo experiment database was read under the reporting role.
The approved exporter verified the database name. The active export
transaction was confirmed as read-only and REPEATABLE READ. The export used
app `570060128` without rating or time bounds. The preparation runs then
consumed this single export offline.

| Check | Result |
| --- | --- |
| Input → output | 1,247 → 1,247 |
| Distinct source review identities and exact version IDs | 1,247 each |
| Current version numbers | 1,245 version 1, two version 2 |
| Rating-only changes | Both current version 2 references preserved. Read-only history lookup confirmed version 1 with different ratings and identical title and body. |
| Inherited fields | All 21 values per row equal the decoded retrieval input, including original title, body, rating and provenance. Both input files stayed byte-identical. |
| Text presence | 1,247 eligible, zero excluded |
| Language status | 1,247 unknown |
| Repeatability | Two separate processing CLI invocations produced byte-identical CSVs and sidecars. |
| Input CSV SHA-256 | `b6d5dc4736f63bf2f207a7e759bf2833825b8646ce5872e4dc4ed6cef846b20b` |
| Processed CSV SHA-256 | `3412ebe4ac8de5701a1984cd9d5db3bd5d129618e49f2046b659493369fa100f` |

The 36 focused synthetic cases cover review/version identity, repeated
observations and historical-row rejection, ordering, fidelity, malformed
inputs, reproducible hashes and private export behavior. The full regression
suite passed all 786 tests using disposable PostgreSQL.

## Scope for subsequent modeling

This validation covers the retained Duolingo experiment snapshot. Text
eligibility records the presence of normalized text. The 1,247 eligible
reviews still require a separate assessment of usefulness, such as the
[pilot's manual U0–U3 rubric](APPLE_REVIEW_QUALITY_ASSESSMENT.md).
All language statuses are `unknown` because v1 performs no language
detection. An English-only model requires a separate language identification
method and a policy for reviews in other languages.

The retrieval schema has no source creation timestamp, so first-observed time
continues to represent entry into the dataset. Preparation holds one export
in memory, suitable for the bounded review datasets in this project.
Aspect extraction, segmentation, translation, language detection, sentiment
annotation and model training belong to later stages.
