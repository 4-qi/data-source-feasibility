# Phase E — Feed compatibility evidence and remaining checks

Review date: November 3, 2026 (America/Los_Angeles).

**Conclusion:** offline compatibility is verified for the explicitly tested scalar JSON/Atom profiles. Actual-feed structural compatibility remains **pending bounded validation under separate authorization**. No retained raw Apple response was found in the inspected evidence locations. In particular, absence of nested XML/XHTML is **not established**. Existing nested-content rejection stays in place; it is an unsupported-input boundary, not proof that such a feed is invalid. If a later authorized read encounters legitimate nested content, stop with an operational **COMPATIBILITY_BLOCKED** finding and implement/review correct full-content support before continuing. Do not skip those records or leave that source permanently classified invalid.

This review made no network requests, collected no new source evidence, saved no real review text or authors, and changed neither parser behavior nor `apple-observed-v1`. It does not authorize a limited read, Phase F, retention, deployment or a seven-day pilot.

## 1. Bounded inventory and evidence levels

Inspected locations were this checkout's `results/mainstream/`, `results/mobile_quality/`, `src/feasibility/apple_validation.py`, `probes/mobile_quality.py`, `research/previous_evidence/`, and the adjacent `../data-ingestion-research/research/` and `Project_Kickoff/` file inventory. Hidden/ignored filenames were included for the bounded result/probe directories. No unrelated home, browser cache, temporary inspection, backup or Git-history search was performed. PDF/DOCX reports and screenshots were inventoried as documents; they are not treated as raw JSON/Atom responses or extracted for private review text.

| Location | Stored format and classification | What it supports | What it cannot support |
| --- | --- | --- | --- |
| [`results/mainstream/apple_rss_access.json`](../results/mainstream/apple_rss_access.json) | Sanitized diagnostic JSON; 10 run records and 35 parsed record occurrences; `raw_review_text_saved=false`, `author_values_saved=false` | Dated request outcomes, projected fingerprints/body hashes, lengths, rating, field-presence flags | Original JSON labels, XML content attributes/children, complete title/body, entity spelling or raw response replay |
| [`results/mainstream/apple_xml_review_sample.json`](../results/mainstream/apple_xml_review_sample.json) | Sanitized XML-route diagnostic saved as JSON; 2 run records, 10 occurrences; raw text and authors explicitly absent | Dated XML-route parsing and projected field presence | An Atom document, child/tail structure, content `type`, complete text or proof of no nested content; the filename does not make this a raw XML sample |
| [`results/mainstream/apple_empty_feed_diagnostic.json`](../results/mainstream/apple_empty_feed_diagnostic.json) | Three request summaries, each `raw_body_saved=false` | The recorded top-level `feed` object, absent `entry` member, and feed key names (`author`, `icon`, `id`, `link`, `rights`, `title`, `updated`) for those requests | Actual values, review entry schemas, a permanent empty-feed rule or reason for absence |
| [`results/mainstream/apple_online_readiness.json`](../results/mainstream/apple_online_readiness.json) | Eight JSON/XML request summaries, each `raw_body_saved=false` | Recorded format/status/review counts and time extrema; one recorded empty XML result | Replaying bodies, child structure, current availability, full-format readiness or source ordering guarantees |
| [`results/mainstream/app_sample_manifest.json`](../results/mainstream/app_sample_manifest.json) | Eight-app catalog/sampling-frame metadata; raw catalog not saved | Fixed app identity, US storefront and analytical category | Review RSS response schema or a review counter from its historical `reviews_collected` field |
| [`results/mobile_quality/collection.json`](../results/mobile_quality/collection.json) | Sanitized comparison JSON; 16 Apple requests, 71 Apple occurrences; JSON/XML formats; `raw_content_saved=false` | Dated mappings for ID/content/rating/updated/version, normalized body hashes, lengths, formats and timestamps | Original full text/title, XML type/children, raw JSON/Atom replay; hashes cannot reconstruct text |
| [`results/mobile_quality/content_review.json`](../results/mobile_quality/content_review.json), [`comparison_summary.json`](../results/mobile_quality/comparison_summary.json), [`verification.json`](../results/mobile_quality/verification.json) | Abstract annotations, aggregate checks and verification metadata | Historical AI-assisted inspection provenance and the recorded removal of temporary prefixes | Independent human labels, complete original text, nested-markup absence or compatibility proof |
| [`research/current_evidence.md`](../research/current_evidence.md), [`results/mobile_review_comparison.md`](../results/mobile_review_comparison.md) | Maintained explanatory reports | Temporary inspection prefixes were outside the repository and removed; the saved evidence is hashes/metadata/abstract reasons | A retained raw-response corpus; historical inspection is not new full-fidelity validation |
| [`src/feasibility/apple_validation.py`](../src/feasibility/apple_validation.py) | Adapter/probe **code**, not a saved response | JSON `feed`/dictionary-or-list `entry` handling and Atom/iTunes tag-to-field mapping, including title | Exact source formatting encountered historically; its XML `findtext` does not establish complete descendant/tail capture |
| [`probes/mobile_quality.py`](../probes/mobile_quality.py) | Historical comparison **code**, not a response | Recorded field projection and source of the old lossy text normalization | Full-title mapping (omitted there), full-fidelity hashing or evidence that no nested nodes were missed |
| [`research/previous_evidence/`](../research/previous_evidence/) | Seven root-level JSON reports inspected structurally; no `feed` envelope objects or Apple `customerreviews` URL strings; other files are reports/manifests | Earlier acquisition/document provenance in the bounded inventory | A discovered raw Apple feed |
| `../data-ingestion-research/research/probes/` and adjacent research documents | Six root-level JSON reports inspected structurally; no `feed` envelope objects or Apple `customerreviews` URL strings; named images/text concern earlier browser/source probes | Earlier research inventory; no candidate Apple raw JSON/Atom file found there | A claim that no raw feed exists anywhere on the machine, or that a document/image proves XML structure |

The old XML adapters read direct element text with `findtext`. The comparison probe then HTML-unescapes, collapses whitespace and may retain a 500-character inspection prefix. Therefore even a matching historical normalized body hash establishes equality of that old projection, not that all nested descendants/tails were captured. It cannot serve as a full-fidelity `apple-observed-v1` vector.

The source files above were only read. The current probe must not be imported as a runtime compatibility library: it reads historical files and creates a requests session at import. The new tests import only the pure legacy `decode_feed` mapping and never execute a probe or create a transport session.

### Inventory checksums

These hashes identify the exact preserved historical artifacts inspected, not raw responses:

| Artifact | SHA-256 |
| --- | --- |
| `results/mainstream/apple_rss_access.json` | `756c7d4f7657f464dc8727f171cdf3225f5ab73106de68dbc949753397a0364c` |
| `results/mainstream/apple_xml_review_sample.json` | `031c2287471fe34738fab5b69211bf7967e7303f081ea33030f47fec480861f1` |
| `results/mainstream/apple_empty_feed_diagnostic.json` | `2f291b4e2bca652fbe3474eccd3e46a6f499ade2bcba3536bc31fb3babb92d71` |
| `results/mainstream/apple_online_readiness.json` | `9a4f582013cdfecd01b3988916217af77b21449722752cce13572fae533f420d` |
| `results/mobile_quality/collection.json` | `b9299c14085189782943d1b6a5894e8efe77014036a2e8549baeb8e748b4f2f2` |

## 2. Verified offline profile

All content in [`tests/test_apple_ingestion_feed_compatibility.py`](../tests/test_apple_ingestion_feed_compatibility.py) is invented and wrapped with `evidence_kind='synthetic'`. The historical JSON files are used only to verify that a sanitized report cannot masquerade as a feed replay. No real body or author is printed or reproduced.

| Input/profile | Offline result | Evidence boundary |
| --- | --- | --- |
| JSON `feed.entry` as dictionary or list, string `label` fields | Accept complete ID/title/content/rating/version/updated mappings; opaque ID is unchanged; duplicates retain order | Synthetic mapping validation; no retained raw JSON source shape |
| Atom namespace with default or arbitrary prefix, iTunes rating/version namespace | Same complete record/canonical values as equivalent JSON | Synthetic scalar-entry profile; not all possible Atom content types |
| Scalar title/content with absent `type`, `type='text'` or `type='html'` | Preserve decoded strings fully, including literal markup strings and trailing content | XML escaping is decoded by the XML parser once; HTML strings are not additionally unescaped or rendered |
| CDATA containing literal HTML | Preserve CDATA text as a string | CDATA text is distinct from actual nested XML elements |
| Missing optional title/version/updated | Produce `None`; empty title remains distinct from missing title | Explicit JSON `label:null`, numeric/boolean labels and malformed wrappers are rejected rather than coerced |
| Complete long content, Unicode, CRLF/CR, literal entities | Store decoded text without truncation/collapse; comparison alone uses LF/NFC | XML's own line-ending decoding is expected; no extra HTML decoding |
| Aware timestamp with up to six fractional digits and valid offset | Canonical UTC serialization has exactly six fractional digits and `Z` | More than microsecond precision remains explicitly unsupported, not silently truncated; no actual-feed precision distribution is established |
| Missing JSON `entry` versus malformed envelope | Distinct valid-empty metadata versus `FEED_SCHEMA` failure | Missing entries/empty pages still do not imply end-of-feed or absence of reviews |
| Recognizable Application catalog marker without review fields | Deterministically ignored under the existing narrow rule | Whether all real catalog-entry variants fit this marker is not established |
| Nested text/HTML/XHTML, including title suffixes, paragraph/br/tail content | Reject the entire page as `ENTRY_SCHEMA`; no partial records escape | Current unsupported-profile safety boundary, not a source-validity conclusion |
| DTD/entity declarations, external-src content, invalid namespaces, bad candidate fields | Existing safe failure tests remain unchanged | These tests validate containment, not current upstream behavior |

The tested profile therefore has **offline mechanics evidence**. It does not justify `actual Atom fully compatible`, `no nested XHTML`, `all eight feeds ready`, or permission/freshness/completeness claims.

## 3. Nested XML/XHTML candidate support — not enabled

A concrete candidate fixture is a `content type='xhtml'` element with one XHTML-namespace `div`, paragraphs, inline elements, `br`, leading text and tails. The same issue can affect title. XML parser external-resource/DTD protections must remain active for any extension. `findtext`, first-child-only capture, stripping unknown children, or `''.join(itertext())` alone is inadequate: `START<p>FIRST<br/>NEXT</p>TAIL<p>LAST</p>END` can collapse to `STARTFIRSTNEXTTAILLASTEND`, losing boundaries. Dropping unknown elements/attributes can also omit meaningful content.

Two small implementation directions exist, but choosing one changes the representation supplied to comparison and requires an explicit decision after actual structure is known:

| Candidate | Benefit | Required decision/risks |
| --- | --- | --- |
| Preserve the complete decoded XHTML fragment as markup in the existing text fields | Retains nodes, attributes, text and tails; does not silently discard non-text content | Must define stable serialization for namespaces, attributes, empty tags and whitespace. Equivalent JSON HTML strings may not match that serialization. Rendering remains separately escaped/private. Existing scalar `type='html'` strings must not be silently reinterpreted. |
| Deterministic text projection over the whole known XHTML profile | Can preserve full human-readable text with deliberate paragraph/br boundaries and tail order | Must specify leading/trailing whitespace, block boundaries, nested inline text, links, alt text and unknown nodes. A projection is not lossless markup retention. Unknown meaningful structures must fail the whole page until supported. JSON/Atom equivalence needs actual paired examples. |

No candidate implementation is activated by this review. A representation choice must be fixture-reviewed and parser-versioned. If comparison semantics go beyond the existing LF/NFC-on-decoded-string contract, explicitly review the hash-contract transition as well; do not silently rewrite old versions or make normalization changes look like source edits. The seven tables need not change merely to choose a string representation, but schema stability does not remove that semantic decision.

If an authorized bounded observation actually contains legitimate nested structures, correct support becomes a prerequisite for continued use of that profile. Keeping an unsupported page rejected forever, ignoring the affected records, or accepting only a title/body prefix would not satisfy the full-fidelity requirement.

## 4. First separately authorized bounded validation

This is a proposed check specification, **not execution authorization**. The project owner retains the documented access/data-use and retention questions for review with John. These are not collector Boolean gates. Technical scope/operator/window/limits and explicit enablement remain required; current synthetic results are not actual source evidence.

1. Record exact fixed-manifest app, US storefront, page, format, request ceiling, timing, permitted private handling and stop procedure. A minimal initial diagnostic can be page 1 JSON and Atom for **one** manifest app, at most **two physical requests**, spaced at least two seconds. Any expansion to another app/page requires inclusion in that separately recorded authorization and the same configured caps; it is not a seven-day pilot. A paired-format diagnostic does not change the production JSON/fallback policy.
2. Use the reviewed bounded transport with no credentials/cookies, redirect following or retries; enforce 10/25-second connect/read timeouts, 2,000,000 decoded-byte cap and a fixed deadline. Never follow next links or infer termination from empty entries. Record request intent and outcome through the reviewed diagnostic path appropriate to the explicitly authorized run; do not claim a synthetic run as live.
3. Inspect responses only in permitted private memory/storage. Routine output contains status, byte count, envelope/namespace names, scalar field types, content `type`, child-tag paths/counts, missing/empty states and safe failure codes—never title/body/author values or exception strings. Saving raw bytes/full text is allowed only if the separate access/retention decision explicitly permits that handling; this document grants none.
4. For review candidates, check presence/type of ID, complete title/content, rating, optional version and aware updated timestamp, including precision/offset. Inspect **both title and content** for descendants/tails and external content references. Distinguish escaped HTML/CDATA strings from actual XML child nodes. Catalog-shaped entries and absence of `entry` need their own recorded shape outcomes.
5. Stop the target on denial/rate limit, redirect/non-200, cap/deadline, malformed schema or an unsupported legitimate structure. A nested-content encounter is reported as **COMPATIBILITY_BLOCKED** alongside the parser's safe unsupported-profile error, not skipped and not mislabeled as verified malformed source data. Retain only permitted private evidence or sanitized structural diagnostics for a follow-up fixture.
6. Reproduce the encountered structure offline using a permitted private exact sample or an explicitly invented/redacted structural fixture. Select the full-content representation and transition policy, add complete text/tail/boundary and safety tests, and review before any further use of that profile. A successful observation in one app/format proves only that observed window; it does not close compatibility for all eight apps or all later responses.

No code in this task bypasses the current live gate or starts a service/scheduler. The main Phase E owner controls readiness decisions, any separate limited-read authorization, and the distinction between those observations and Phase F.

## 5. Validation performed

```bash
PYTHONNOUSERSITE=1 /home/l2838/miniconda3/envs/data-source-feasibility/bin/python -m pytest tests/test_apple_ingestion_feed_compatibility.py tests/test_apple_ingestion_parser.py tests/test_apple_ingestion_normalizer.py -q
```

Result: **121 passed, 0 failed, 0 skipped**, including 36 new compatibility tests and the 85 existing parser/normalizer tests. Python TCP connections are blocked by the shared test guard. These pure parsing tests do not require PostgreSQL and do not prove live compatibility. Parser/normalizer source and versions were unchanged.
