# Source Route Reassessment

**Assessment date: October 27, 2026 PDT.**

> **Earlier study.** This report preserves the access observations and route assessment preceding the [focused mobile comparison](mobile_review_comparison.md). Use the [Source Recommendation](source_recommendation.md) for current selection. The later eight-app comparison supersedes the single-app Google and temporary Duolingo missing-entry observations.

## Conclusion

**The reassessment identified additional technically accessible routes among previously screened platforms.** Technical access, source suitability and permitted downstream use are separate decisions. This recheck verified two previously untested alternatives: Google Play's web review transport and Bluesky's public live stream. Mastodon also passed another small paginated read. No source is declared universally inaccessible.

At the time of this reassessment, Apple had the strongest broader-category evidence, based on reviews from seven applications. Google Play had demonstrated third-party review retrieval and pagination for one application, making it a suitable candidate for the subsequent comparison. Bluesky and Mastodon were also technically accessible as social-text sources, although their content and filtering requirements differed from product and app reviews. These findings did not establish production readiness or unrestricted data-use rights.

## Platform dispositions

| Platform | Evidence available | Assessment |
| --- | --- | --- |
| Steam | Preserved 20/20 successful requests, 27 baseline IDs and four additional targeted negative IDs | Technically validated baseline; gaming specificity limits broad-domain fit |
| GitHub Issues | Preserved 8/9 successful requests, 11 distinct retained records; one quota denial | Technically usable quota-dependent software-feedback backup; not a failed platform |
| Hacker News | Preserved 19/19 successful requests and nine distinct story/comment records | Technically usable discussion source; weaker review standardization and topic fit |
| Apple App Store | Preserved 23 successful RSS diagnostic GETs; 40 distinct parsed records from seven apps across four strata | Promising broad app-review technical candidate; format inconsistencies, one missing app, sustained updates and project-use basis remain unresolved |
| Google Play | New two-page web-transport probe: 2/2 HTTP 200, six distinct reviews, zero page overlap | Third-party review text is technically obtainable in this probe; official developer authorization is not a platform-wide access conclusion |
| Bluesky | Search still 403; separate public Jetstream connection received three new-post text events | Live ingestion is technically demonstrated; keyword search remains unverified/denied in this environment |
| Mastodon | Earlier two-instance successes; new mastodon.social hashtag pages: 2/2 HTTP 200 and six non-overlapping IDs | Technically usable for the tested instance/route; not a rating-based review platform |
| Amazon | Historical browser visibility varied; current broad raw-review route and suitable authorization not established | No new review scraping performed under the existing scope boundary; not proven technically impossible |
| Walmart | Earlier browser challenge; current GET 307; a separate HEAD identifies redirect to `/blocked` | Tested anonymous route is blocked in this environment; no finding about every product, visitor, supplier or future agreement |
| Best Buy | Earlier browser read and long-review expansion succeeded; distinct second-page records not established; current direct GET timed out | Public reading was demonstrated historically; automated repeatable collection remains unvalidated. Lower priority by project scope, not a proven technical impossibility |
| Yelp | Webpage again 403; official contracted full-text Partner API documented | Web route denied in this environment; a contract-based acquisition route exists and is untested here |
| CFPB | Official announcement and Release 24 ended current narrative publication; earlier 403 cause unknown | Current database fails the continuing-original-text requirement; not a claim that its structured API or historical archive is unusable |

The October 16 observations documented the limitations of individual access attempts. A failed request or missing authorization for one route does not establish that an entire platform is unavailable. Earlier browser evidence and later HTTP checks remain separate rather than overwriting each other.

## New executed checks

The [HTTP-route evidence](route_recheck/source_route_recheck.json) records seven attempted GETs: Bluesky search, two Mastodon pages, Walmart, Best Buy, Yelp and the Google Play app page. Best Buy timed out before an HTTP response; it is not a recorded source rejection. The [Walmart HEAD diagnostic](route_recheck/walmart_redirect_check.json) classifies the 307 destination as `/blocked`, with query parameters omitted and no challenge followed.

### Google Play: initial HTML versus web review transport

The public Spotify app page returned 200. A generic JSON-LD review parser found no review objects. A separate [embedded-data check](route_recheck/google_play_embedded_recheck.json) parsed the initial callback datasets using a third-party source mapping, but returned no rows at the expected `ds:8` location. This may reflect a changed layout or absent initial rows; it does not prove that reviews are unavailable.

A bounded follow-up used the same site's publicly served web review transport:

```text
POST https://play.google.com/_/PlayStoreUi/data/batchexecute?hl=en&gl=us
```

This POST reads review data; it does not create a review or modify an account. Protocol and field mappings came from the maintainer's [request format source](https://github.com/JoMingyu/google-play-scraper/blob/master/google_play_scraper/constants/request.py), [review response handling](https://github.com/JoMingyu/google-play-scraper/blob/master/google_play_scraper/features/reviews.py) and [field definitions](https://github.com/JoMingyu/google-play-scraper/blob/master/google_play_scraper/constants/element.py). These are third-party implementation evidence, not Google documentation or a use license.

The [actual web-transport evidence](route_recheck/google_play_review_rpc_recheck.json) records two requests of three reviews each for `com.spotify.music`, including a continuation request. Both returned 200. All six parsed records had a source ID, text, numeric rating and date field. The samples had ratings 1, 3 and 5, with no ID overlap between pages. Only fingerprints, lengths, ratings and field presence were saved; no author values, review bodies or continuation token values were retained.

The probe used its own bounded HTTPS transport with TLS verification, no credentials, no automatic retries, no redirects and a 2 MB response cap. The third-party package was not executed: its inspected transport disables TLS verification and has retry behavior unsuitable for this diagnostic. No login, challenge workaround, IP rotation or access-control evasion was used.

**What changed:** third-party Google Play review retrieval and one continuation are now `VERIFIED` for this app and environment. Cross-category coverage, repeated runs, fresh arrivals, edit/deletion handling and long-term maintenance remain `NOT_TESTED`. The interface is undocumented and may change. The [official Android Publisher interface](https://developers.google.com/android-publisher/reply-to-reviews) remains a different, authorized-app route. The [Google Play conditions](https://play.google.com/intl/en-us/about/play-terms/index.html) and intended collection, retention and analysis scope still need assessment before scheduled project use.

### Bluesky: search versus live ingestion

The original public search route again returned 403. It was not retried, case-modified or moved to another host to evade the denial. Its precise failure cause remains unknown.

The separate [official Jetstream documentation](https://bsky.network/docs/jetstream/) describes unauthenticated live ingestion, filtered by collection and event kind. The [live check](route_recheck/bluesky_jetstream_recheck.json) used exactly one connection to:

```text
wss://jetstream.us-east.bsky.network/xrpc/network.bsky.jetstream.subscribeEvents?collections=app.bsky.feed.post&kinds=commit
```

With subprotocol `xrpc.v1.json`, it received three `create` events containing post text, event time, sequence and creation fields, then closed. The bound was 20 seconds, ten frames and three text records; the observed duration was under one second. No post text or author identifiers were saved. The temporary diagnostic dependency was `websocket-client==1.9.2`; it was installed outside the repository.

**What changed:** live post ingestion is `VERIFIED`; search remains denied. Only three new-post events were observed, without topic or usefulness assessment. Keyword/product relevance filtering, sustained reliability, cursor replay, update/delete processing and historical access have not been validated. Official documentation treats live delivery and historical replay as different access paths; no historical export or authenticated operation was performed. A technical stream does not itself supply rating labels or grant model-training rights. The [developer guidelines](https://bsky.network/docs/developer-guidelines/) also require handling requested content deletion.

### Mastodon

The public `mastodon.social` Firefox hashtag timeline returned three records, followed by three different records using `max_id`. All six had text and creation fields; there was zero overlap. This confirms a usable online social-text route for this instance and endpoint. It does not establish topic usefulness, all-instance access or long-term update/deletion completeness. The [official timeline reference](https://docs.joinmastodon.org/methods/timelines/) describes route/instance access conditions.

## Restricted routes are not exhausted platforms

- **Walmart:** The [official Reviews API](https://developer.walmart.com/global-marketplace/docs/reviews-api-overview) concerns the seller Review Accelerator Program. Its enrollment/item management is not an established arbitrary-product full-review feed. The tested consumer page leads to a challenge; no CAPTCHA was solved or bypassed. Other authorized arrangements are untested, rather than disproven.
- **Best Buy:** The [official API reference](https://bestbuyapis.github.io/api-documentation/) documents catalog review aggregates and caching conditions, not a verified raw-review feed. Earlier UI pagination changed its selected range without verified different review content. The later timeout does not negate earlier readable reviews. No additional development is prioritized because the project previously reduced this platform's scope.
- **Yelp:** The [Private Reviews API](https://docs.developer.yelp.com/docs/private-reviews-api) explicitly documents full text, IDs, ratings and time for contracted partners. Coverage/sorting follow the agreement; this is not a private-message API. The ordinary [Places FAQ](https://docs.developer.yelp.com/docs/places-faq) has separate evaluation, caching and analytics conditions. No partner account or credentials were provided, and neither paid interface was called. The valid conclusion is a gated potential source, not absent full-text capability.
- **CFPB:** The [announcement](https://www.consumerfinance.gov/about-us/newsroom/the-cfpb-to-cease-discretionary-publication-of-complaint-narratives-and-visualizations/) and [Release 24](https://cfpb.github.io/api/ccdb/release-notes.html) are the continuity evidence. Solving a 403 would not restore a currently published narrative stream. No new CFPB request was necessary.
- **Amazon:** The [completed engineering assessment](amazon_decision.md) already limits its conclusion to assessed routes and current access conditions. No Amazon review scraping, new authorization claim or new Amazon collection was introduced.

The four mobile-review suppliers retain the specific API, trial, retention and downstream-use findings in the [mainstream assessment](mainstream_review_assessment.md). No account was created, paid trial enabled or vendor contacted. Supplier marketing does not establish a project-specific license.

## Reproduction diagnostics

The bounded diagnostic bodies are retained with CLI output-directory handling. The live evidence above was generated by their exploratory forms; no extra live run was made after adding CLI wrappers.

```sh
# Help only: these commands make no network requests.
python probes/http_routes.py --help
python probes/google_play_web.py --help
python probes/bluesky_live.py --help
```

Running without `--help` makes the bounded network checks and writes evidence to `results/route_recheck/` by default. Use a new `--output` directory to preserve existing evidence. [HTTP route probe](../probes/http_routes.py) uses requests; [Google web probe](../probes/google_play_web.py) performs at most two read-only requests; [Bluesky live probe](../probes/bluesky_live.py) additionally requires `websocket-client==1.9.2`. That optional diagnostic package is not required for the existing collectors or offline suite. These are isolated probes, not integrated production collectors. The main offline suite does not establish coverage of these diagnostic scripts; compilation and no-network help checks are reported separately.

## Recommendation and limits

At this stage, Apple had the broader executed sampling evidence, while Google Play had demonstrated a working but undocumented single-app review route. These findings informed the subsequent mobile comparison, which expanded both platforms to eight applications across four categories.

For a social-opinion objective, Bluesky live events and a selected Mastodon instance were technically viable candidates. Product/app reviews and social posts should not be treated as interchangeable data.

There is no justified blanket statement that all other websites failed. The remaining decisions concern content fit, intended use, contract conditions and sustained online operation. The new small probes do not establish semantic usefulness, representative sentiment, production access rights or deployment readiness.

Original experiment JSON, the fixed qualitative review, earlier mobile artifacts and all existing collector/test code remain unchanged. New HTTP attempts, the separate HEAD check and the WebSocket connection are not added to the original 47/48 baseline or Apple 23-request totals. [Recheck verification](route_recheck/verification.json) records offline tests, link checks and preservation hashes.
