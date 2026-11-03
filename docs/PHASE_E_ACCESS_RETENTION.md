# Phase E — Access and retention conditions

**Checked:** November 3, 2026, America/Los_Angeles.  
**Decision state:** explicit long-term technical intent selected; project-specific
access/retention arrangements remain unconfirmed; no live-run authorization.  
**Scope:** the existing eight third-party applications, US customer-review RSS,
small bounded requests, retained full-text observed versions and private human
assessment. No model training, publication of review bodies, alternate source
search, supplier activation or contact submission is included.

This memo distinguishes retrieved official statements from their unresolved
application to this external ingestion project. It is not a declaration that
all Apple review storage is forbidden, nor a general license inferred from a
public endpoint. Engineering approval and a local operator authorization record
cannot themselves create source/data-use rights.

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

## Project applicability and required decisions

**Engineering inference:** the client/internship project should not assume its
purpose is covered by a personal-use allowance. Likewise, an approved-RSS
reference should not be treated as an unrestricted external collection license.
The responsible project owner must resolve the actual applicable basis for the
precise purpose and endpoint, recording any conditions or unresolved limits.
The reviewed materials establish a concrete applicability concern, not a
finding that every possible permission arrangement is unavailable.

| Decision item | Current project state | Evidence needed before a real bounded run |
| --- | --- | --- |
| Access basis | No project-specific decision covering this route/scope was supplied. | A named responsible decision maker and reviewable basis/reference covering the selected app(s), US endpoint, bounded automated access and any applicable conditions. |
| Full-text/version retention | The intended technical model is explicit `long_term`, without a preset expiry; applicable arrangements remain unconfirmed. | Responsible-owner confirmation and policy references covering complete versions, observations/history, private artifacts, backups, future obligations and any required changes. No invented finite duration is required. |
| Human analysis | Tooling is prepared; actual human assessment has not occurred. | Confirmation that the intended private assessment and access roles fit the approved data-use basis. |
| Personal data handling | Removing author fields does not remove personal information embedded in text. | Access controls and a project process for privacy/retention requests and incident handling within the selected scope. |
| Distribution/downstream use | No review-body publication, external transfer or training is part of this phase. | Separate review before expanding purpose; do not infer rights from technical accessibility. |
| Execution authorization | The user authorized readiness preparation only. | A separate, explicit authorization for the first bounded request/run, with selected scope and limits; it must not schedule Phase F. |

An operator record should identify the decision and its conditions; it must not
claim Apple permission merely because a checkbox is true. A relevant source
restriction, missing applicability decision or incompatible retention condition
blocks live execution while leaving synthetic validation available. Alternative
contractual or other applicable bases may exist; this memo does not prescribe a
particular permission-acquisition route or contact any party.

## Retention configuration boundary

The project has now explicitly chosen technical `long_term` retention with
`duration_days=null`, no preset expiry and no automatic history deletion. This
is not a claim of unrestricted real-world permission. The private local config
keeps `arrangement_confirmed=false`; preflight distinguishes complete technical
documentation from unresolved applicable arrangements and blocks live execution.
See [the actual local deployment](APPLE_INGESTION_LOCAL_DEPLOYMENT.md).

There is no guessed 24-hour, 30-day or other universal Apple RSS period. Supplier-
specific conditions are not transferred to direct RSS. Legacy explicit finite-
day configurations remain supported, but a finite number is not required for
`long_term`. Missing applicable arrangements/policy confirmation, rather than
the intentionally null day count, are the current live blocker.

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

## First bounded technical validation: later authorization required

A later, separately authorized limited run should state selected target(s), one
execution, unchanged per-target page/request/spacing/size/time limits and a
specific stop/recovery procedure. It should inspect representation/namespace
compatibility without retaining raw responses in ordinary diagnostics. New
nested/XHTML structures, schema failures, access/rate denial, indeterminate
persistence, missing approvals or unsafe logging require stopping and review;
none authorizes alternate endpoints, relaxed thresholds or a seven-day schedule.

No live source behavior, DNS/TLS route, current feed response, fresh arrival,
edit ordering or seven-day continuity was tested in this memo. Those gaps
remain distinct from offline requests-adapter/database integration tests.
