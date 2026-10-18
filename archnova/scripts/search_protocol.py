"""Adaptive search and validation protocol for contract-driven architecture exploration."""
from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any, Dict, Iterable, List

EDIT_CATALOG: Dict[str, Dict[str, Any]] = {
    "insert": {"scopes": ["node", "subgraph"], "failure_modes": ["interface_violation", "causality_violation", "budget_overflow"], "repair_prompt": "Add a typed projection or causal-safe placement, then re-check budget."},
    "replace": {"scopes": ["node", "subgraph"], "failure_modes": ["interface_violation", "dependency_break", "budget_overflow"], "repair_prompt": "Select a component from the compatible replacement family and preserve downstream contracts."},
    "rewire": {"scopes": ["edge", "subgraph"], "failure_modes": ["interface_violation", "orphan_node", "dependency_break"], "repair_prompt": "Rewire only between compatible ports and prove every producer and consumer remains reachable."},
    "duplicate_branch": {"scopes": ["subgraph"], "failure_modes": ["budget_overflow", "duplicate_subgraph"], "repair_prompt": "Inject a distinct information path or remove the duplicate branch; report its expected information-flow change."},
    "merge": {"scopes": ["edge", "subgraph"], "failure_modes": ["shape_mismatch", "state_conflict", "unverified_merge_contract"], "repair_prompt": "Declare the merge operator, align shapes and state semantics, and attach a merge contract."},
    "prune": {"scopes": ["node", "edge", "subgraph"], "failure_modes": ["orphan_node", "required_path_removed", "ablation_nonconclusive"], "repair_prompt": "Restore a reachable path or retain the node until leave-one-out evidence is conclusive."},
}


def validate_edit_action(action: Dict[str, Any]) -> Dict[str, Any]:
    op = action.get("op")
    if op not in EDIT_CATALOG:
        raise ValueError(f"unsupported edit operation: {op}")
    reason = str(action.get("reason", "")).strip()
    if not reason:
        raise ValueError("edit operation requires a semantic reason")
    if op in {"duplicate_branch", "merge", "rewire"} and not any(token in reason.lower() for token in ("information", "branch", "state", "route", "memory")):
        raise ValueError(f"{op} requires an information-flow or state reason")
    return {"status": "accepted", "operation": op, "scope": action.get("scope", EDIT_CATALOG[op]["scopes"][0]), "reason": reason, "failure_modes": EDIT_CATALOG[op]["failure_modes"]}


def diagnose_edit_failure(error: Any) -> Dict[str, Any]:
    text = str(error).lower()
    rules = [
        (("shape", "dtype", "layout", "interface"), "interface_violation", "Insert a typed projection or choose a compatible port.", True),
        (("causal", "future token"), "causality_violation", "Move the edit behind a causal boundary or mark the operation non-causal.", True),
        (("orphan", "unreachable", "reachability"), "reachability_violation", "Reconnect the node and prove input-to-output reachability.", True),
        (("budget", "flop", "memory", "cost"), "budget_overflow", "Reduce width or branch count and rerun the budget check.", True),
        (("duplicate", "isomorphic", "redundant"), "duplicate_subgraph", "Change the information path or reject the redundant branch.", True),
    ]
    for needles, cls, repair, retryable in rules:
        if any(n in text for n in needles):
            return {"class": cls, "repair": repair, "retryable": retryable, "raw_error": str(error)}
    return {"class": "unknown_violation", "repair": "Request validator evidence and preserve the candidate as deferred.", "retryable": False, "raw_error": str(error)}


def group_relative_score(rows: Iterable[Dict[str, Any]], lower_is_better: bool = True) -> Dict[str, Any]:
    rows = list(rows)
    by_seed: Dict[Any, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if "candidate_id" not in row or "metric" not in row or "seed" not in row:
            raise ValueError("each evaluation row requires candidate_id, metric, and seed")
        by_seed[row["seed"]].append(row)
    if not by_seed or any(len(items) < 2 for items in by_seed.values()):
        raise ValueError("each common cohort must contain at least two candidates")
    values: Dict[str, List[float]] = defaultdict(list)
    advantages: Dict[str, List[float]] = defaultdict(list)
    for seed, cohort in by_seed.items():
        cohort_values = [float(x["metric"]) for x in cohort]
        center = mean(cohort_values)
        for row in cohort:
            candidate = str(row["candidate_id"])
            value = float(row["metric"])
            values[candidate].append(value)
            advantages[candidate].append((center - value) if lower_is_better else (value - center))
    trimmed = {}
    for candidate, vals in values.items():
        ordered = sorted(vals)
        trimmed[candidate] = mean(ordered[1:-1] if len(ordered) >= 3 else ordered)
    relative = {candidate: mean(vals) for candidate, vals in advantages.items()}
    best = max(relative, key=relative.get)
    return {"status": "scored", "candidate_seeds": {k: len(v) for k, v in values.items()}, "trimmed_means": trimmed, "relative_advantage": relative, "best_candidate": best, "evaluation_policy": {"common_cohort": True, "trimmed_mean": True, "lower_is_better": lower_is_better}}


def cross_scale_promotion(record: Dict[str, Any]) -> Dict[str, Any]:
    if not record.get("peer_pass"):
        return {"status": "blocked", "reason": "peer_relative_evaluation_failed"}
    if "large_scale_gain" not in record:
        return {"status": "unresolved", "reason": "large_scale_evidence_missing"}
    gain = float(record["large_scale_gain"])
    if gain < 0:
        return {"status": "blocked", "reason": "large_scale_regression", "large_scale_gain": gain}
    if float(record.get("small_scale_gain", 0)) > 0 and gain >= 0:
        return {"status": "promote_to_large_scale", "large_scale_gain": gain}
    return {"status": "unresolved", "reason": "insufficient_positive_gain"}


def parameter_matched_baseline(candidate: Dict[str, Any], baseline: Dict[str, Any]) -> Dict[str, Any]:
    target = int(candidate.get("params", candidate.get("parameter_count", 0)))
    return {"status": "required", "target_params": target, "source_baseline": baseline.get("id", baseline.get("name", "baseline")), "strategy": "match_parameter_count_or_compute_budget", "required_receipts": ["matched_capacity_config", "matched_capacity_result", "structural_gain_comparison"]}


def decompose_slots(graph: Dict[str, Any]) -> List[Dict[str, Any]]:
    slots: List[Dict[str, Any]] = []
    for index, node in enumerate(graph.get("nodes", [])):
        slots.append({"slot_id": f"slot:{index}", "scope": node.get("scope", "block"), "candidate_node_ids": [node.get("id")], "mutable": node.get("mutable", {}), "search_role": "module_combination"})
    return slots


def validator_feedback(error: Any) -> Dict[str, Any]:
    diagnosis = diagnose_edit_failure(error)
    return {"diagnosis": diagnosis, "repair_actions": [{"action": "repair_and_retry", "prompt": diagnosis["repair"]}] if diagnosis["retryable"] else [{"action": "defer", "prompt": diagnosis["repair"]}]}
