"""Pure offline 5/10-page and 12/24-hour comparisons; no DB/network writes."""
from dataclasses import asdict
from datetime import datetime

from .contracts import IngestionConfig
from .pagination_probe import prefix_validity
from .reference import coverage_metrics


def _instant(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("UTC_OBSERVATION_TIMESTAMP_REQUIRED")
    return result


def window(observation, depth):
    if (observation is None or observation.get("verification_failed", False)
            or not prefix_validity(observation.get("pages", []), depth)):
        return None
    return {record["review_id"] for page in observation["pages"] if page["page"] <= depth
            for record in page.get("records", [])}


def request_cost(observation, depth):
    if observation is None:
        return None
    return sum(item["page"] <= depth for item in observation.get("attempt_timings", []))


def pair(current, reference, depth):
    ids = window(current, depth)
    previous = window(reference, depth)
    result = {"depth": depth, "status": "indeterminate",
              "requests": request_cost(current, depth)}
    if current is not None and reference is not None:
        result["interval_hours"] = (_instant(current["started_at"]) -
                                    _instant(reference["started_at"])).total_seconds() / 3600
    if ids is None or previous is None:
        return result
    metrics = coverage_metrics(ids, previous, depth, IngestionConfig())
    result.update(status="sufficient" if metrics.thresholds_met else "insufficient",
                  metrics=asdict(metrics), relative_new_ids=len(ids - previous),
                  current_distinct_ids=len(ids), reference_distinct_ids=len(previous),
                  current_overall_status=current["overall_status"],
                  reference_overall_status=reference["overall_status"])
    return result


def replay(observations, indexes, depth):
    """Virtual production early-stop chain; never rewrites actual run eligibility."""
    reference_ids = None
    reference_index = None
    results = []
    for index in indexes:
        current = observations[index]
        row = {"observation": index, "status": "indeterminate", "counterfactual_only": True,
               "virtual_reference_observation": reference_index}
        if current is None:
            results.append(row)
            continue
        row["actual_acquisition_status"] = current["overall_status"]
        if reference_index is not None:
            row["interval_hours"] = (_instant(current["started_at"]) -
                                    _instant(observations[reference_index]["started_at"])).total_seconds() / 3600
        chosen = None
        if reference_ids is None:
            chosen = depth if window(current, depth) is not None else None
            row["status"] = "baseline" if chosen else "indeterminate"
        else:
            for prefix in range(2, depth + 1):
                ids = window(current, prefix)
                if ids is None:
                    break
                metrics = coverage_metrics(ids, reference_ids, prefix, IngestionConfig())
                if metrics.thresholds_met or prefix == depth:
                    chosen = prefix
                    row.update(status="sufficient" if metrics.thresholds_met else "insufficient",
                               metrics=asdict(metrics), relative_new_ids=len(ids - reference_ids))
                    break
        row["stopped_depth"] = chosen
        row["requests"] = request_cost(current, chosen or depth)
        if chosen is not None:
            reference_ids = window(current, chosen)
            reference_index = index
        results.append(row)
    return results


def compare(observations):
    if len(observations) != 7:
        raise ValueError("SEVEN_OBSERVATION_SLOTS_REQUIRED")
    result = {"schema_version": "apple-coverage-comparison/1", "strategies": {},
              "acquisition_failures": [
                  {"observation": index, "status": item["overall_status"] if item else "missing"}
                  for index, item in enumerate(observations)
                  if item is None or item["overall_status"] != "succeeded"],
              "completeness_established": False}
    for name, lag, depth in (("A", 2, 5), ("B", 2, 10), ("C", 1, 5), ("D", 1, 10)):
        indexes = list(range(0, 7, lag))
        primary = [dict(observation=i, reference_observation=i-lag,
                        **pair(observations[i], observations[i-lag], depth))
                   for i in indexes[1:]]
        supplementary = [dict(observation=i, reference_observation=i-2,
                              **pair(observations[i], observations[i-2], depth))
                         for i in (3, 5)] if lag == 2 else []
        sufficient = sum(row["status"] == "sufficient" for row in primary)
        evaluated = sum(row["status"] != "indeterminate" for row in primary)
        costs = [request_cost(observations[i], depth) for i in indexes]
        consumed = sum(cost for cost in costs if cost is not None)
        complete_trajectory = all(observations[i] is not None for i in indexes)
        duration = ((_instant(observations[6]["started_at"]) - _instant(observations[0]["started_at"]))
                    .total_seconds() / 86400) if observations[0] and observations[6] else None
        result["strategies"][name] = {
            "interval_hours": 12*lag, "depth": depth, "primary": primary,
            "supplementary_24h": supplementary, "sufficient": sufficient,
            "evaluable": evaluated, "planned_pairs": len(primary),
            "evaluable_sufficiency_rate": sufficient/evaluated if evaluated else None,
            "planned_pair_sufficiency_rate": sufficient/len(primary),
            "preliminary_continuity_pass": sufficient == len(primary),
            "fixed_depth_requests_observed": consumed,
            "reserved_request_outcomes_unconfirmed": sum(
                item.get("status") == "reserved" for i in indexes if observations[i] is not None
                for item in observations[i].get("attempt_timings", []) if item["page"] <= depth),
            "cost_missing_observations": len([cost for cost in costs if cost is None]),
            "startup_inclusive_requests_per_actual_day": consumed/duration if duration and complete_trajectory else None,
            "nominal_json_requests_per_day": depth*24/(12*lag),
            "request_cap_per_day": depth*2*24/(12*lag),
            "replay": replay(observations, indexes, depth)}
    result["common_current_endpoints"] = {
        name: [dict(observation=i, reference_observation=i-lag,
                    **pair(observations[i], observations[i-lag], depth)) for i in (2,4,6)]
        for name, lag, depth in (("A",2,5),("B",2,10),("C",1,5),("D",1,10))}
    return result
