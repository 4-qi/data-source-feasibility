# Mainstream Review Source Assessment

**Assessment date: October 27, 2026 PDT.**

> **Earlier study.** This report preserves the access observations and route assessment preceding the [focused mobile comparison](mobile_review_comparison.md). Use the [Source Recommendation](source_recommendation.md) for current selection. The later eight-app comparison supersedes the single-app Google and temporary Duolingo missing-entry observations.

## Engineering conclusion

**The initial Apple RSS assessment demonstrated technically feasible cross-category review retrieval in a bounded PoC.** At this stage, Apple was the strongest newly tested candidate, while production suitability remained unresolved. The JSON probe returned text from five of eight sampled apps; XML checks recovered reviews for two more, giving seven of eight apps across four analytical categories. Page-2 and short-interval repeat checks succeeded for one app. Duolingo remained without entries in both tested formats. Sustained freshness, completeness and project-specific use rights remain unresolved.

Commercial cross-app review APIs also exist. AppFollow, Appbot, 42matters and AppTweak document review access for Apple and Google Play. Their standard offerings do not, by themselves, establish permission for ongoing review collection, storage, and downstream model use. Specific restrictions and the exact access prerequisites are recorded below rather than treating all suppliers as unavailable.

Steam served as the established technical baseline, with GitHub Issues as the quota-dependent backup for software-feedback collection. Mobile app reviews are a broader-domain candidate, not a demonstrated representative sample of general consumer-product reviews. Amazon's completed assessment is unchanged. CFPB is excluded from ongoing original-text ingestion because narrative publication ended.

## Actual Apple RSS validation

The public path tested was:

```text
https://itunes.apple.com/us/rss/customerreviews/page={page}/id={appId}/sortby=mostrecent/json
```

The [verified sampling manifest](mainstream/app_sample_manifest.json) contains two apps per analytical stratum: Todoist and Microsoft To Do; Duolingo and Khan Academy; Amazon Shopping and Etsy; Uber and Lyft. Apple IDs, names, bundle IDs and official genres were verified through the [official catalog lookup interface](https://performance-partners.apple.com/search-api). Android package IDs were checked against the linked official Google Play listings. This is a purposive mainstream-app frame, not a representative sample. Amazon Shopping app feedback is not Amazon product-review data.

| Observed measure | Result |
| --- | --- |
| Main RSS requests | 10/10 HTTP 200: eight first pages, Todoist page 2, Todoist page-1 repeat |
| Apps returning review entries | 5/8: Todoist, Khan Academy, Amazon Shopping, Etsy and Lyft |
| Analytical strata with text | 4/4: productivity, education, shopping and transportation |
| Entries received across responses | 350 review entries, including repeats; not 350 distinct or fully assessed reviews |
| Parsing cap | First five reviews per response; 35 parsed occurrences, 30 distinct fingerprints |
| Fields in distinct parsed records | ID, text, title, updated field and app version present in 30/30; numeric ratings also 30/30 |
| Rating distribution of distinct parsed sample | 1 star: 8; 2 stars: 2; 3 stars: 1; 4 stars: 0; 5 stars: 19 |
| Basic length screen | 28/30 have at least 20 characters and four words; not a usefulness or sentiment score |
| Page separation | Todoist's first five page-2 IDs had zero overlap with its first five page-1 IDs |
| Short-interval repeat | Todoist returned the same five sampled page-1 IDs |

The [main request and field evidence](mainstream/apple_rss_access.json) preserves statuses, counts, field presence and fingerprints. It does not save review bodies or author values. Recommendation flags and star scores are distinct signals; no semantic usefulness assessment or sentiment-label accuracy test was performed on these new records.

Microsoft To Do, Duolingo and Uber each returned a valid feed without an `entry` member. The [three-request schema diagnostic](mainstream/apple_empty_feed_diagnostic.json) confirmed the same structure. This did not establish that these apps have no reviews. The cause of the missing JSON entries was not established. No alternative storefront, hostname, or access workaround was tested.

The [online-readiness check](mainstream/apple_online_readiness.json) used eight additional GETs: JSON dates for the five working feeds and XML for the three missing-entry feeds. The seven nonempty responses contained review `updated` dates extending to October 24–26, 2026. An updated field is not necessarily an original creation date, and recent timestamps do not prove sustained new arrivals. Microsoft To Do and Uber had 50 XML review entries each; Duolingo had none.

The separate [two-app XML field sample](mainstream/apple_xml_review_sample.json) parsed five records from each recovered feed. Across the JSON and XML samples, there are **40 distinct fingerprints from seven apps**, with ID/text/title/updated/version and numeric rating present in all 40. Ratings are 1 star: 11, 2 star: 4, 3 star: 4, 5 star: 21; 36/40 pass the basic length screen. The 40 records have not received the original semantic usefulness review, so no comparable usefulness percentage is claimed. The complete follow-up used **23 RSS GETs, all HTTP 200**: ten main JSON, three empty-feed schema checks, eight date/format checks and two XML field samples. Repeatedly returned entries are not added together as unique reviews.

The two catalog lookups are separate from review requests: the first returned JSON with a `text/javascript` MIME type, which the exploratory checker did not parse; the second explicitly parsed the JSON without executing JavaScript. All eight app IDs were then verified. The eight Google listing inspections are documentation retrieval, not Play API experiments. No ratings, usernames or review text from those pages were retained.

A bounded diagnostic is available as:

```sh
python -m feasibility.apple_validation --help
# Makes up to thirteen live requests when run without --help:
python -m feasibility.apple_validation
```

The published CLI combines the observed JSON record projection with Atom XML parsing, adds up to three XML fallbacks for missing-entry JSON feeds, validates the manifest/feed and writes timestamped output. It was checked offline and was not rerun live. It accepts exactly eight distinct numeric app IDs, has a thirteen-request total budget, disables ambient credentials and redirects, caps responses at 2 MB, uses timeouts and two-second spacing, and stops on the first denial or malformed response. No scheduler or ongoing crawler is implemented.

### Apple access conditions

The [Media Services conditions, section F](https://www.apple.com/legal/internet-services/itunes/us/terms.html) restrict automated extraction/analysis and model-related reuse. The [App Review Guidelines, 4.5.1 and 5.2.2](https://developer.apple.com/app-store/review/guidelines/) recognize approved RSS feeds and permitted third-party access, but do not establish an external review-analysis exception. These are documented project-fit concerns, not a finding that every feed request is unlawful or technically impossible.

The [official RSS/catalog link page](https://www.apple.com/sg/itunes/link/) describes catalog and chart uses rather than a bulk customer-review license. The [Rights and Permissions form](https://www.apple.com/legal/contact/rights-permissions.html) addresses Apple materials and trademarks; it is a possible clarification contact, not a demonstrated customer-review licensing program. It was inspected without submitting anything. The [App Store Connect review API](https://developer.apple.com/documentation/appstoreconnectapi/customer-reviews) separately concerns authorized developers' apps.

**Result:** RSS response access, some fields and limited pagination/repeatability are verified. An applicable basis for scheduled ingestion, retained review text and external model use is not established. A suitable written scope or an appropriately contracted supply route would address that separate production prerequisite. No claim is made that all possible Apple agreements have been exhausted.

## Cross-app review suppliers

Capabilities below are `DOCUMENTED`, except the explicitly recorded unauthenticated HTTP checks. Authenticated retrieval, delivered coverage and actual update latency have not been tested. See the [machine-readable route matrix](mainstream/vendor_route_matrix.json) and [access-check evidence](mainstream/vendor_access_checks.json).

| Supplier | Concrete technical route | Trial / cost boundary | Project-fit restriction |
| --- | --- | --- | --- |
| AppFollow | V2 reviews endpoint; token header; app ID, date range, page, review-ID/text/last-modified filters | 12 credits/request; 10-day product trial; API trial credits and current price require confirmation | Terms 4.2 restrict external ML use; 4.4 requires written consent for commercial collection in the customer's name |
| Appbot | REST JSON review export and competitor tracking; current detailed reference requires sign-in | 14-day no-card product trial; API is a paid Large/Premium add-on, not established as included in trial | G.3 internal use only and no commercialising reviews; G.4 public publication needs consent; G.6 no review rights transfer |
| 42matters | iOS and Android review endpoints; date/rating/language filters and page/limit | Small plan or above; 3 hits/request, 3 QPS; trial endpoint entitlement/current price unconfirmed | 3.5 limits persistent storage to 24 hours without written agreement; 3.8 does not grant underlying app-data rights |
| AppTweak | Reviews Search with body/ID, date/rating filters and offset/limit; daily fetching for tracked apps | 1 credit/review; 7-day trial requires billing and may auto-charge; API plans are separate from ASO plans | Self-serve 5.1.4 restricts database compilation and third-party processing; Enterprise has separate terms |

### AppFollow

Use `GET https://api.appfollow.io/api/v2/reviews`, with `X-AppFollow-API-Token`, an external app ID or collection, `from`, `to`, `country` and `page`. The [v2 reference](https://docs.api.appfollow.io/reference/reviews_api_v2_reviews_get-1) documents `last_modified` and review-ID filters, useful for incremental collection and deduplication. It does not document a selectable page size here. The [API overview](https://support.appfollow.io/hc/en-us/articles/360020833017-API-Overview) specifies 1,000 requests/hour/token and 10,000/hour/account. Legacy v1 response examples must not be treated as a verified v2 parser schema.

The [account setup guide](https://support.appfollow.io/hc/en-us/articles/4405602262161-Getting-Started-Prepping-Your-Account-For-Admins) describes a 10-day product trial, including monitoring selected apps; this does not confirm an API credit allocation. The retrieved [pricing page](https://appfollow.io/pricing) did not establish a numeric API quote. The [standard agreement](https://appfollow.io/terms) contains the restrictions summarized above. Access credentials alone would not resolve them.

**Concrete prerequisite:** an API-specific trial entitlement and written project scope covering historical storage, commercial analysis and any external ML use. This is an established acquisition product with a contract mismatch, not an absent API.

### Appbot

The [API product page](https://appbot.co/features/api/) explicitly supports JSON review export, BI reporting and integrations. The [FAQ](https://appbot.co/faqs/) supports competitor monitoring without owning the app. The [current reference URL](https://app.appbot.co/api) redirected to sign-in; no undocumented API route was guessed. A [public v2 migration guide](https://support.appbot.co/help-docs/whats-new-appbot-api-v2/) describes HTTP Basic API credentials, but does not replace the current authenticated reference.

The [plan page](https://appbot.co/plans/) lists Large from USD 166/month with annual billing or USD 219/month with monthly billing, before the separately priced API add-on. The product trial is 14 days without a card; API entitlement must be established separately. The [terms](https://appbot.co/terms/) support internal use under the restrictions above; external training and client-facing reuse must not be presumed licensed.

**Concrete prerequisite:** explicit API trial/add-on access and retention scope. This is the clearest documented internal-analytics option in this comparison, but that narrower use must not be substituted for the project's intended database/model scope.

### 42matters

The [iOS endpoint](https://42matters.com/docs/app-market-data/ios/apps/reviews) is `GET https://data.42matters.com/api/v5.0/ios/apps/reviews.json` with `id`; the [Android endpoint](https://42matters.com/docs/app-market-data/android/apps/reviews) uses `/android/apps/reviews.json` and package parameter `p`. Both require query parameter `access_token`, with `limit` from 1 to 100 and page-based retrieval. Default history is 30 days; dated windows are at most 30 days per request.

Documented fields include text, rating, date, language and version. No stable review ID is listed, and the documentation explicitly warns that `author_hash` must not track authors or reviews. Content hashes can identify exact repeated snapshots but do not establish stable edit identity. Any implementation must redact the token from URL/query logs; the existing generic client must not be used unchanged with token-bearing query parameters.

The [overview](https://42matters.com/docs/overview) offers trial registration but does not establish Reviews entitlement. A current numeric quote was not obtained from [pricing](https://42matters.com/pricing). **Concrete prerequisite:** a Reviews-enabled trial plus a written retention/use addendum addressing the [24-hour storage condition](https://42matters.com/tos). A normal subscription alone does not solve historical ingestion.

### AppTweak

Use `GET https://public-api.apptweak.com/api/public/store/apps/reviews/search.json` with `X-Apptweak-Key`, `apps`, `country`, `language`, `device`, `limit`, `offset` and dates. The [reference](https://developers.apptweak.com/reference/app-reviews-search) permits up to five app IDs/query, up to 500 reviews/page, and charges one credit/review. US English uses AppTweak's language code `us`, not `en`.

The [tracked-app guide](https://developers.apptweak.com/reference/tracked-applications-summary) describes an initial 24–48-hour delay and tracking-dependent retrieval; subsequent review fetching is daily, not real-time. That guide appeared in the official search index, while a direct open returned 404 in this environment; its exact current availability remains uncertain. The [overview](https://developers.apptweak.com/reference/overview) documents the token and quota model. The [pricing page](https://www.apptweak.com/en/pricing) displays API Lite at USD 166/month, but this is not a confirmed month-to-month quote or permission to enable billing. ASO and review-management prices are different products.

**Concrete prerequisite:** an Enterprise/API agreement explicitly permitting the ingestion database under the [separate applicable terms](https://www.apptweak.com/en/legal/terms-of-services), then tracking capacity and initial fetch time. No billing details were supplied, app-tracking POSTs made or trial activated.

## Google Play and CFPB disposition

The [Google developer guide](https://developers.google.com/android-publisher/reply-to-reviews) and [reviews.list](https://developers.google.com/android-publisher/api-ref/rest/v3/reviews/list) require application authorization. They remain viable for participating app owners, not arbitrary third-party apps. The suppliers above provide concrete cross-app alternatives. The initial supplier study did not implement a web-review probe. A later [route reassessment](source_route_reassessment.md) verified two read-only requests to Google's undocumented web review transport, yielding six distinct reviews with no page overlap for one app. This supersedes the untested web-route status, without changing developer-API authorization requirements or establishing downstream rights.

CFPB's [August 14 notice](https://www.consumerfinance.gov/about-us/newsroom/the-cfpb-to-cease-discretionary-publication-of-complaint-narratives-and-visualizations/) and [September Release 24](https://cfpb.github.io/api/ccdb/release-notes.html) establish the removal of narratives from the current database. The earlier [one-request 403 diagnostic](mainstream/cfpb_access_20261028T003324477168Z.json) remains preserved; its precise cause is unknown and is not the reason for excluding ongoing narrative ingestion. Historical archives do not meet the continuing-text requirement. No additional CFPB requests were made.

## Executed evidence and selection consequence

| Evidence group | Actual activity | What it establishes |
| --- | --- | --- |
| Original October 20 collection | Unchanged 47/48 successful requests | Steam/GitHub/HN baseline only |
| Earlier CFPB diagnostic | Unchanged one 403 | Access failure in that execution, not its cause |
| Apple catalog | Two 200 responses; second parsed | Eight-app metadata frame |
| Apple main JSON probe | Ten 200 responses; 30 distinct parsed IDs | Text in five apps, four strata; one limited page/repeat check |
| Apple schema/date/XML follow-up | Thirteen more 200 responses; ten additional parsed XML IDs | Seven apps with text across formats; recent timestamps; Duolingo still missing entries |
| Supplier access checks | AppFollow 401, AppTweak 401, 42matters 400 | Unauthenticated requests rejected; no authenticated review/schema/quality finding |

No vendor credentials were supplied. The 42matters 400 body was not retained or analyzed, so its exact error cause is not established; documentation separately requires a token. Appbot's documentation sign-in is a documentation observation, not a counted API request. Documentation retrieval is excluded from experiment totals. The original 47-record qualitative review, 27 baseline Steam IDs, four negative supplement IDs, 11 GitHub records and nine HN records are unchanged.

**Assessment outcome:** The initial Apple RSS experiments established cross-category technical feasibility and motivated the subsequent [mobile review comparison](mobile_review_comparison.md). That comparison expanded both Apple and Google Play to eight applications across four categories and evaluated their review content using a consistent rubric. The current source selection is documented in the [Source Recommendation](source_recommendation.md).

Commercial review suppliers remained conditional alternatives, subject to their specific access entitlements and data-use agreements.

This study established a limited Apple RSS technical PoC and assessed commercial acquisition routes. It did not establish continuous-ingestion readiness or project-specific data-use rights. Authenticated supplier access and production operation were outside its scope; Amazon review collection was not performed.
