import json
from ..http import StopCollection
from ..model import Record, Collected

ENDPOINT = "https://api.steampowered.com/IUserReviewsService/GetAppReviews/v1/"


def normalize(raw, appid):
    if not isinstance(raw, dict):
        raise StopCollection("unexpected_review_schema")
    rid = raw.get("recommendationid")
    author = raw.get("author") if isinstance(raw.get("author"), dict) else {}
    safe = ["recommendationid", "review", "language", "timestamp_created", "timestamp_updated",
            "voted_up", "votes_up", "votes_funny", "refunded", "steam_purchase", "received_for_free"]
    return Record("steam", "review", f"{appid}/{rid}" if rid is not None else None,
                  raw.get("review"), created=raw.get("timestamp_created"), updated=raw.get("timestamp_updated"),
                  fields={x: raw.get(x) is not None for x in safe},
                  metadata={"appid": appid, "language": raw.get("language"), "voted_up": raw.get("voted_up"),
                            "votes_up": raw.get("votes_up"), "votes_funny": raw.get("votes_funny"),
                            "playtime_at_review": author.get("playtime_at_review"),
                            "received_for_free": raw.get("received_for_free"), "refunded": raw.get("refunded")})


def page(client, appid, order, size, cursor="*", review_type=0):
    args = {"appid": appid, "filter": order, "languages": ["english"],
            "num_per_page": size, "purchase_type": 1, "review_type": review_type, "cursor": cursor}
    data = client.get(ENDPOINT, params={"input_json": json.dumps(args, separators=(",", ":"))})
    # Service response is sometimes wrapped in response; recognize only documented content.
    if isinstance(data, dict) and "response" in data:
        data = data["response"]
    if not isinstance(data, dict) or not isinstance(data.get("reviews"), list):
        raise StopCollection("unexpected_steam_schema")
    return data


def collect(client, max_records=32, appids=(620, 413150), page_size=6, pages=2):
    out = Collected()
    client.collected = out
    for appid in appids:
        for order in (1, 2):
            cursor, prior = "*", set()
            for index in range(pages if order == 1 else 1):
                remaining = max_records - len(out.records)
                if remaining <= 0:
                    return out
                size = min(page_size if order == 1 else 4, remaining)
                data = page(client, appid, order, size, cursor)
                raws = data["reviews"]
                if len(raws) > size:
                    raise StopCollection("source_exceeded_requested_page_size")
                records = [normalize(x, appid) for x in raws]
                keys = {r.key for r in records if r.key is not None}
                times = [r.created if order == 1 else r.updated for r in records]
                comparable = all(isinstance(t, int) for t in times)
                out.observations.append({"appid": appid, "order": "Recent" if order == 1 else "Updated",
                    "page": index + 1, "records": len(records), "overlap_with_previous_pages": len(prior & keys),
                    "descending_timestamps": all(a >= b for a, b in zip(times, times[1:])) if comparable else None,
                    "next_cursor_present": isinstance(data.get("cursor"), str) and bool(data["cursor"]),
                    "total_matching": data.get("total_matching"),
                    "created_before_updated_count": sum(isinstance(r.created, int) and isinstance(r.updated, int)
                                                         and r.created < r.updated for r in records)})
                out.records.extend(records)
                prior |= keys
                nxt = data.get("cursor")
                if not records or not isinstance(nxt, str) or not nxt or nxt == cursor:
                    break
                cursor = nxt
    return out


def collect_negative(client, max_records=4, appids=(620, 413150), page_size=2):
    """One tiny Recent/Negative page per game; no pagination or repeated experiment."""
    out = Collected()
    client.collected = out
    for appid in appids:
        size = min(page_size, max_records - len(out.records))
        if size <= 0:
            break
        data = page(client, appid, 1, size, review_type=2)
        if len(data['reviews']) > size:
            raise StopCollection('source_exceeded_requested_page_size')
        records = [normalize(x, appid) for x in data['reviews']]
        out.records.extend(records)
        flags = [x.metadata['voted_up'] for x in records]
        out.observations.append({'appid': appid, 'order': 'Recent', 'review_type': 2,
                                 'records': len(records), 'false_recommendation_flags': sum(x is False for x in flags)})
        if any(x is not False for x in flags):
            raise StopCollection('negative_filter_label_mismatch')
    return out
