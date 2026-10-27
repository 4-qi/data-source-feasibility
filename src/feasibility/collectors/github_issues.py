from ..http import StopCollection
from ..model import Record, Collected

BASE = "https://api.github.com"
HEADERS = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}


def normalize(raw, repo, kind="issue", parent=None):
    if not isinstance(raw, dict):
        raise StopCollection("unexpected_github_record_schema")
    rid = raw.get("id")
    user = raw.get("user") if isinstance(raw.get("user"), dict) else {}
    fields = ["id", "body", "created_at", "updated_at"] + (["number", "title", "state", "labels"] if kind == "issue" else [])
    # Titles are retained only in memory as part of the text being screened.
    text = "\n".join(x for x in [raw.get("title") if kind == "issue" else None, raw.get("body")] if isinstance(x, str))
    return Record("github", kind, f"{repo}/{rid}" if rid is not None else None, text,
        parent=parent, created=raw.get("created_at"), updated=raw.get("updated_at"),
        author_type=user.get("type"), fields={x: raw.get(x) is not None for x in fields},
        metadata={"repository": repo, "state": raw.get("state"), "author_type": user.get("type"),
                  "author_association": raw.get("author_association"),
                  "body_present": bool(raw.get("body")), "labels_count": len(raw.get("labels") or [])})


def collect(client, max_records=24, repo="microsoft/vscode", page_size=10, pages=2, comment_issues=2):
    import re
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ValueError("Expected owner/repository")
    out = Collected(excluded={"pull_requests": 0, "records_beyond_cap": 0})
    client.collected = out
    comments = []
    raw_ids = set()
    for number in range(1, pages + 1):
        remaining = max_records - len(out.records)
        if remaining <= 0:
            break
        data = client.get(f"{BASE}/repos/{repo}/issues", params={"state": "all", "sort": "updated",
                         "direction": "desc", "per_page": min(page_size, remaining), "page": number}, headers=HEADERS)
        if not isinstance(data, list):
            raise StopCollection("unexpected_github_list_schema")
        page_ids = set()
        for raw in data:
            if not isinstance(raw, dict):
                raise StopCollection("unexpected_github_record_schema")
            if raw.get("id") is not None:
                page_ids.add(raw["id"])
            if "pull_request" in raw:
                out.excluded["pull_requests"] += 1
                continue
            if len(out.records) >= max_records:
                out.excluded["records_beyond_cap"] += 1
                continue
            rec = normalize(raw, repo)
            out.records.append(rec)
            if raw.get("comments", 0) and isinstance(raw.get("number"), int) and len(comments) < comment_issues:
                if not any(n == raw["number"] for n, _ in comments):
                    comments.append((raw["number"], rec.key))
        out.observations.append({"kind": "issue_list", "page": number, "raw_records": len(data),
            "overlap_with_previous_pages": len(page_ids & raw_ids)})
        raw_ids |= page_ids
        if not data or len(data) < min(page_size, remaining):
            break
    for number, parent in comments:
        size = min(2, max_records - len(out.records))
        if size <= 0:
            break
        data = client.get(f"{BASE}/repos/{repo}/issues/{number}/comments", params={"per_page": size}, headers=HEADERS)
        if not isinstance(data, list):
            raise StopCollection("unexpected_github_comments_schema")
        out.records.extend(normalize(x, repo, "comment", parent) for x in data[:size])
        out.observations.append({"kind": "comment_list", "parent_issue_number": number, "records": len(data[:size])})
    return out
