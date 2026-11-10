# Pre-Live Engineering Baseline — commit review

Review date: November 3, 2026. The local engineering milestone was committed
after review, with **no push and no real collection**.
Parent: `474736abcee2a67f186299f09d196125400eb1ab` on `main`.
This record is included in the milestone; use Git history to resolve its commit
ID rather than embedding a self-referential hash here.

## Review outcome

**PASS for the local milestone.** The change set contains the approved design,
existing seven-table migration, formal ingestion code, dependency/environment
contracts, synthetic tests, deployment examples and operating documentation.
No unrelated change or deletion was identified. The only previously tracked
files changed are README, project dependency declarations and `.gitignore`.
All other original tracked files retain their bytes.

| Check | Result |
| --- | --- |
| Real database passwords/connection files | Excluded. Four actual local passwords and three complete role DSNs were compared in memory with candidate contents; no match. Values were never printed or copied into the review record. |
| Private keys/tokens/personal review data | No private-key/token finding or newly added real review-body/author dataset identified. Credential-like test literals are explicitly invented privacy/error-handling fixtures; two email-shaped matches are example URL components. |
| PostgreSQL files, backups, spool, receipts | None in the candidate set. Actual deployment/configuration/runtime files remain outside the checkout. Added ignore rules protect known private filenames and local database/backup directories. |
| Deployment/authorization examples | Public templates contain environment references rather than credential values. Retention decisions are pending; project execution/access flags remain false, policy IDs/windows unset. No fabricated approval is included. |
| Historical feasibility work | Original results, research, probes and feasibility tests retained unchanged. Fourteen previously ignored historical files remain on disk and ignored; none were forced into this commit or deleted. |
| Engineering completeness | Design, Alembic, seven-table code, full-text version handling, tests, project-policy preparation and runbooks included together. |
| Unrelated work | None found in the candidate diff; no change to the adjacent research checkout is included. |

The documentation intentionally retains nonsecret local operating paths, role
and database names, port/socket information and prior validation identifiers.
Those explain the actual WSL deployment. They are distinct from the private
connection/configuration files, credentials and real review text, which are not
part of the milestone.

## Verification and traceability

The audit enumerated all tracked/visible candidate paths and checked
file types, sizes, scope and hashes, and classified every heuristic secret-scan
finding. Independent read-only checks covered documentation/deployment/test data
and code/migrations/scripts. No reviewer changed the files or ran collection.

A clean 153-file export of the proposed engineering tree, containing no ignored
historical/local state or `.git` metadata, ran the complete suite with the shared
Conda interpreter and an independent temporary PostgreSQL cluster:

```sh
PYTHONPATH=<clean-export>/src PYTHONNOUSERSITE=1 APPLE_TEST_PYTHON=/home/l2838/miniconda3/envs/data-source-feasibility/bin/python bash scripts/test_apple_ingestion_postgres.sh --full-suite -q --junitxml=/tmp/apple-prelive-clean-full-suite.xml
```

**668 passed in 66.54 seconds; 0 failures, 0 errors, 0 skipped, no pytest
warnings.** This checks that the engineering delivery does not depend on the
ignored research directories or real local deployment. PostgreSQL used a private
temporary Unix socket, with TCP disabled, and its cluster was cleaned up. HTTP
responses were injected fixtures, not Apple requests. Existing production/local
databases and targets were not changed by this audit.

The report and final README/progress pointers are documentation-only additions
after that export. Staged whitespace inspection found intentional Markdown hard
breaks and a blank migration EOF line: `.gitattributes` explicitly preserves the
Markdown convention, and only the redundant migration EOF newline was removed.
The migration Python AST is identical; no DDL or schema behavior changed. All
other code, examples, tests and smoke procedure remain byte-identical to the
tested export. Before commit, stage only the audited path
list, verify staged blob contents against the final SHA-256 manifest, check
protected historical hashes and run `git diff --cached --check`.

Detailed local audit artifacts (not committed runtime evidence):

- `/tmp/apple-prelive-secret-audit.json`: value-suppressed findings and hashes.
- `/tmp/apple-prelive-clean-export.json`: exact clean-export file hashes.
- `/tmp/apple-prelive-clean-full-suite.xml`: complete regression result.
- `/tmp/apple-prelive-protected-baseline.json`: protected-file checksums.

Supported delivery is a repository checkout with the documented editable
installation on Linux/WSL. A standalone wheel containing migrations/manifests,
Windows-native acceptance and production/cloud infrastructure are not claimed.

## Preserved live boundary

This milestone records engineering readiness, not live-source acceptance.
The last actual read-only check found eight disabled targets and no collection
history. Project execution/data-use confirmation and long-term arrangements
remain unconfirmed. The reusable project workflow does not require daily
approval files or receipts, but still checks scope, validity, limits, actual
deployment and retention readiness.

No Apple RSS request, target enablement or Phase F scheduling/pilot
was performed. The first live smoke remains subject to the concrete prerequisites
in the [smoke runbook](APPLE_FIRST_LIVE_SMOKE_TEST.md). This task commits the
reviewed source locally and stops without pushing.
