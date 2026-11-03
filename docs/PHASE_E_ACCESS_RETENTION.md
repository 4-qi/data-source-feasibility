# Phase E — Access and retention conditions

**Checked:** November 3, 2026, America/Los_Angeles.  
**Decision state:** explicit long-term technical intent selected; project-specific
access/retention arrangements remain open for review with John. They are not
collector Boolean gates; this preparation task makes no real request.  
**Scope:** the existing eight third-party applications, US customer-review RSS,
small bounded requests, retained full-text observed versions and private human
assessment. No model training, publication of review bodies, alternate source
search, supplier activation or contact submission is included.

This memo distinguishes retrieved official statements from their unresolved
application to this external ingestion project. It is not a declaration that
all Apple review storage is forbidden, nor a general license inferred from a
public endpoint. Engineering success, technical enablement and removing administrative software
checks cannot themselves establish source/data-use rights.

## Confirmed current official material

The following are **documentation retrievals**, not RSS collection requests.
No customer-review endpoint or RSS generator was contacted. Original feasibility
evidence is preserved; these observations belong to the new readiness review.

| Official material | Current documented fact | What remains unestablished |
| --- | --- | --- |
| [US Apple Media Services terms, §F](https://www.apple.com/legal/internet-services/itunes/us/terms.html) | The page identifies September 14, 2026 as its last update. It limits service/content use, includes automated extraction/copying/measurement/analysis/monitoring restrictions, and addresses model/software improvement use. | How these provisions and any applicable permission or exception govern this exact approved-RSS external research workflow. |
| [App Review Guidelines, 4.5.1 and 5.2.2](https://developer.apple.com/app-store/review/guidelines/) | Guidelines allow approved Apple RSS feeds in apps, distinguish that use from scraping Apple sites, and require applicable third-party-service permission. | They do not identify this eight-app review-retention project as an approved feed use or resolve its relationship to the Media Services terms. They are app-review guidelines, not a project-specific external research grant. |
| [Apple RSS/link page](https://www.apple.com/sg/itunes/link/) | Apple describes the feed generator for popular/catalog lists and provides linking tools. | No reviewed text on that page grants this customer-review database a particular storage duration or downstream-use scope. The linked RSS generator was not opened. |
| [Customer Reviews API documentation](https://developer.apple.com/documentation/appstoreconnectapi/customer-reviews?changes=_5) and [Connect help](https://developer.apple.com/help/app-store-connect/monitor-ratings-and-reviews/view-ratings-and-reviews) | The API and Connect workflow are described for reviews of the developer's own app; help identifies required account roles. | This project has not established owner/account authorization for the eight third-party apps. That route is not silently substituted for public RSS. |
| [Ratings/reviews guidance](https://developer.apple.com/app-store/ratings-and-reviews/) | Guidance specifically conditions marketing use of written customer reviews on reviewer permission. | Private bounded storage/assessment is a different use; this marketing statement neither authorizes nor categorically settles that use. |

The JavaScript-only Customer Reviews landing page did not expose its body via
ordinary retrieval; its Markdown link failed in the retrieval tool. The official
indexed API page and readable Connect help supported the narrow own-app finding.
No authenticated API or app-account access was performed. Search results from
third parties were not used as a legal or protocol authority.

## Project applicability and review with John

**Engineering inference:** the client/internship project should not assume its
purpose is covered by a personal-use allowance. Likewise, an approved-RSS
reference should not be treated as an unrestricted external collection license.
The responsible project owner must resolve the actual applicable basis for the
precise purpose and endpoint, recording any conditions or unresolved limits.
The reviewed materials establish a concrete applicability concern, not a
finding that every possible permission arrangement is unavailable.

| Review item | Current project state | Project-management follow-up (not collector input) |
| --- | --- | --- |
| Access basis | No project-specific decision covering this route/scope was supplied. | A named responsible decision maker and reviewable basis/reference covering the selected app(s), US endpoint, bounded automated access and any applicable conditions. |
| Full-text/version retention | The intended technical model is explicit `long_term`, without a preset expiry; applicable arrangements remain unconfirmed. | Responsible-owner confirmation and policy references covering complete versions, observations/history, private artifacts, backups, future obligations and any required changes. No invented finite duration is required. |
| Human analysis | Tooling is prepared; actual human assessment has not occurred. | Confirmation that the intended private assessment and access roles fit the approved data-use basis. |
| Personal data handling | Removing author fields does not remove personal information embedded in text. | Access controls and a project process for privacy/retention requests and incident handling within the selected scope. |
| Distribution/downstream use | No review-body publication, external transfer or training is part of this phase. | Separate review before expanding purpose; do not infer rights from technical accessibility. |
| Operational start | This task keeps execution and targets disabled. | An operator explicitly enables the selected technical scope/window for a later run; there is no per-run approval document. Phase F does not start automatically. |

These questions remain documented for the responsible project owner and John.
The collector does not decide them, require an approval document, or treat a
Boolean as evidence of rights. Removing those software gates does not resolve
these project considerations. This memo does not contact anyone or prescribe a
particular legal route. Actual source denial/rate limits and engineering failures
still stop the collector; scope or purpose decisions remain project management.

## Retention configuration boundary

The intended technical model is `long_term` with `duration_days=null`, no preset
expiry and no automatic history deletion. `mode`/`duration_days` describe storage
intent; owner, references and the old `arrangement_confirmed` are documentation
metadata, not live-preflight conditions. Legacy confirmation fields can be read
without requiring true and are omitted from canonical new configuration.
See [the local deployment](APPLE_INGESTION_LOCAL_DEPLOYMENT.md).

No universal 24-hour/30-day RSS limit is invented or transferred from a supplier.
Finite-day configurations remain compatible, but `long_term` requires no finite
day count. The operational prerequisites are explicit project/target enablement,
valid technical scope/window and actual database/diagnostic safety. Unknown data
use or retention applicability stays in this project-review document; software
removal is not a confirmation that unrestricted retention is permitted.

The intended policy preserves complete accepted title/body, metadata, observed
versions, observations and collection history without a preset expiry. A review
leaving the RSS window never implies deletion. If applicable obligations require
a later change, the maintenance plan must cover relational history, authorized
exports, spool/operational artifacts and backups. An expiry operation would be
administrative retention, not an inferred source deletion. Runtime ingestion
must keep its append-only/version and no-delete restrictions; no purge command,
automatic deletion job or production retention operation is implemented or run
by this readiness task.

A reviewer should specify how any future required retention change or deletion
would be enforced and verified, including backups and exports. The private local
database and isolated backup/restore have now been tested; unresolved arrangements
are not resolved by either technical deployment or a policy field in JSON. Full-text storage is not replaced by hashes
as a workaround for unresolved conditions.

## First bounded technical validation: explicit operator start required

A later explicitly enabled limited run should state selected target(s), one
execution, unchanged per-target page/request/spacing/size/time limits and a
specific stop/recovery procedure. It should inspect representation/namespace
compatibility without retaining raw responses in ordinary diagnostics. New
nested/XHTML structures, schema failures, access/rate denial, indeterminate
persistence, disabled/out-of-scope execution or unsafe logging require stopping and review;
none authorizes alternate endpoints, relaxed thresholds or a seven-day schedule.

No live source behavior, DNS/TLS route, current feed response, fresh arrival,
edit ordering or seven-day continuity was tested in this memo. Those gaps
remain distinct from offline requests-adapter/database integration tests.
