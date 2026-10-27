# Execution plan — 2026-10-20 PDT

> **Historical record, October 20, 2026.** Current decisions are in the [source recommendation](../results/source_recommendation.md) and [Amazon acquisition matrix](../results/amazon_acquisition_options.md). This record does not authorize a new execution.

This historical plan defined the bounded automated collection PoC following the research-only stage. The original research workspace and copied evidence were preserved with checksums. The validation is complete; this plan records its scope rather than outstanding work.

1. Build requests-based collectors with no retries, explicit request/record limits, a disclosed agent, bounded response sizes and timeout; stop a source after access/rate denial.
2. Steam: two games (620,413150), two small Recent pages and one Updated page per game; repeat the same bounded operation.
3. GitHub: vscode public issue listing, exclude PRs, bounded comments with relationships; repeat under remaining quota.
4. HN: bounded Ask HN index/story/comment sample, no recursive crawl; repeat the same selected stories.
5. Responses are held only in memory. Save aggregate quality metrics and non-author record fingerprints for overlap; never save author values or full raw text. Heuristic text eligibility is separate from human opinion validation.
6. Unit tests use synthetic fixtures. Live runs are clearly distinct from historical evidence. The Amazon assessment evaluates official access services without automated review scraping.
7. Analyze actual outcomes, recommend a pilot and backup under an explicit domain assumption, and document Amazon integration prerequisites. Keep code, sanitized metrics and analysis in local version control; publication is separate from technical validation.
