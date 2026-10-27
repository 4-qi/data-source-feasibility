from ..http import StopCollection
from ..model import Record, Collected

BASE = "https://hacker-news.firebaseio.com/v0"


def normalize(raw, kind, parent=None):
    rid = raw.get("id")
    return Record("hackernews", kind, str(rid) if rid is not None else None, raw.get("text"),
        parent=parent, created=raw.get("time"),
        fields={x: raw.get(x) is not None for x in ["id", "text", "time"] + (["parent"] if kind == "comment" else ["title", "kids"])},
        metadata={"type": raw.get("type"), "parent_matches": str(raw.get("parent")) == parent if parent else None,
                  "comment_count": raw.get("descendants") if kind == "story" else None})


def collect(client, max_records=9, stories=3, story_ids=None):
    out = Collected(excluded={"deleted_or_dead_or_null": 0})
    client.collected = out
    if story_ids is None:
        ids = client.get(f"{BASE}/askstories.json")
        if not isinstance(ids, list) or any(not isinstance(x, int) for x in ids):
            raise StopCollection("unexpected_hn_index_schema")
        story_ids = ids[:stories]
    out.repeat_config = {"story_ids": list(story_ids)}
    for sid in story_ids[:stories]:
        if len(out.records) >= max_records:
            break
        raw = client.get(f"{BASE}/item/{sid}.json")
        if raw is None or (isinstance(raw, dict) and (raw.get("dead") or raw.get("deleted"))):
            out.excluded["deleted_or_dead_or_null"] += 1
            continue
        if not isinstance(raw, dict) or raw.get("type") != "story" or raw.get("id") != sid:
            raise StopCollection("unexpected_hn_story_schema")
        out.records.append(normalize(raw, "story"))
        kids = raw.get("kids", [])
        if not isinstance(kids, list):
            raise StopCollection("unexpected_hn_kids_schema")
        for cid in kids[:2]:
            if len(out.records) >= max_records:
                break
            child = client.get(f"{BASE}/item/{cid}.json")
            if child is None or (isinstance(child, dict) and (child.get("deleted") or child.get("dead"))):
                out.excluded["deleted_or_dead_or_null"] += 1
                continue
            if not isinstance(child, dict) or child.get("type") != "comment" or child.get("parent") != sid:
                raise StopCollection("unexpected_hn_comment_schema")
            out.records.append(normalize(child, "comment", str(sid)))
        out.observations.append({"story_id": sid, "declared_comments": raw.get("descendants"),
                                 "children_inspected_at_most": 2, "nested_replies_not_traversed": True})
    return out
