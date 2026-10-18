"""Meta-search control plane: evolve search policies, hardware Pareto niches and component growth."""
from __future__ import annotations

from collections import Counter
from statistics import mean
from typing import Any, Dict, Iterable, List, Sequence, Tuple


def _metric(point: Dict[str, Any], key: str, default: float = 0.0) -> float:
    value = point.get(key, default)
    return float(value) if value is not None else default


def adaptive_fitness(history: Sequence[Dict[str, Any]], base_weights: Dict[str, float] | None = None) -> Dict[str, Any]:
    """Return a traceable fitness policy; never silently changes the objective."""
    weights = dict(base_weights or {"task": 0.55, "structure": 0.2, "hardware": 0.15, "diversity": 0.1})
    if not history:
        return {"status": "initial", "weights": weights, "controller": "adaptive_fitness", "reason": "no_search_history"}
    recent = list(history)[-8:]
    scores = [_metric(x, "score") for x in recent]
    stagnated = len(scores) >= 3 and max(scores) - min(scores) < 1e-6
    stack_rate = mean(_metric(x, "stack_rate") for x in recent)
    if stagnated:
        weights["diversity"] = min(0.35, weights.get("diversity", 0.1) + 0.1)
        weights["structure"] = min(0.4, weights.get("structure", 0.2) + 0.05)
        weights["task"] = max(0.25, weights.get("task", 0.55) - 0.1)
    if stack_rate > 0.5:
        weights["structure"] = min(0.5, weights.get("structure", 0.2) + 0.1)
        weights["task"] = max(0.2, weights.get("task", 0.55) - 0.1)
    total = sum(weights.values()) or 1.0
    weights = {k: round(v / total, 6) for k, v in weights.items()}
    return {"status": "adapted", "weights": weights, "controller": "adaptive_fitness", "stagnated": stagnated, "stack_rate": round(stack_rate, 6), "history_window": len(recent), "requires_review": True}


def meta_evolve_operator_catalog(catalog: Dict[str, Dict[str, Any]], outcomes: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Recommend catalog changes from receipts; recommendations remain drafts."""
    stats: Dict[str, List[float]] = {}
    for outcome in outcomes:
        op = outcome.get("operation")
        if not op:
            continue
        stats.setdefault(op, []).append(1.0 if outcome.get("status") in {"accepted", "validated", "promoted"} else 0.0)
    recommendations = []
    for op, values in stats.items():
        success = mean(values)
        if success < 0.25 and op in catalog:
            recommendations.append({"action": "deprecate_or_repair", "operation": op, "success_rate": round(success, 6), "reason": "low_receipt_success"})
        elif success > 0.8 and op in catalog:
            recommendations.append({"action": "increase_sampling", "operation": op, "success_rate": round(success, 6)})
    return {"status": "recommendation", "operator_stats": {k: {"runs": len(v), "success_rate": round(mean(v), 6)} for k, v in stats.items()}, "recommendations": recommendations, "requires_human_review": True}


def plan_execute_summarize(plan: Dict[str, Any], execution: Dict[str, Any] | None = None) -> Dict[str, Any]:
    required = {"defect", "operation", "success_condition"}
    missing = sorted(required - set(plan))
    if missing:
        raise ValueError("PES plan missing: " + ",".join(missing))
    result = execution or {"status": "planned"}
    return {"phase": "summarize" if execution else "plan", "defect": plan["defect"], "operation": plan["operation"], "success_condition": plan["success_condition"], "execution": result, "next_action": "retain" if result.get("status") in {"validated", "promoted"} else "diagnose_and_revise"}


def pareto_frontier(points: Sequence[Dict[str, Any]], objectives: Sequence[Tuple[str, str]]) -> Dict[str, Any]:
    """Return nondominated points. Directions are 'min' or 'max'."""
    if not objectives:
        raise ValueError("at least one objective is required")
    def dominates(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
        better_or_equal = all((_metric(a, key) <= _metric(b, key)) if direction == "min" else (_metric(a, key) >= _metric(b, key)) for key, direction in objectives)
        strictly = any((_metric(a, key) < _metric(b, key)) if direction == "min" else (_metric(a, key) > _metric(b, key)) for key, direction in objectives)
        return better_or_equal and strictly
    frontier = [p for p in points if not any(dominates(other, p) for other in points if other is not p)]
    return {"status": "scored", "frontier": frontier, "frontier_ids": [p.get("id") for p in frontier], "objectives": [{"name": k, "direction": d} for k, d in objectives]}


def complexity_niches(points: Sequence[Dict[str, Any]], bins: int = 4) -> Dict[str, Any]:
    if bins < 1:
        raise ValueError("bins must be positive")
    complexities = sorted(_metric(p, "complexity") for p in points)
    if not complexities:
        return {"status": "empty", "niches": []}
    low, high = min(complexities), max(complexities)
    width = (high - low) / bins if high > low else 1.0
    niches = []
    for p in points:
        index = min(bins - 1, int((_metric(p, "complexity") - low) / width))
        niches.append({"id": p.get("id"), "niche": index, "complexity": _metric(p, "complexity")})
    return {"status": "partitioned", "bins": bins, "range": [low, high], "niches": niches, "descriptor": "complexity"}


def hardware_pareto(points: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    objectives = [("quality", "max"), ("latency", "min"), ("energy", "min"), ("memory", "min"), ("area", "min")]
    result = pareto_frontier(points, objectives)
    result["deployment_requirements"] = ["hardware_config_id", "measurement_or_lookup_receipt", "feasible_partition"]
    return result


def detect_component_gaps(observations: Sequence[Dict[str, Any]], available_capabilities: Iterable[str]) -> Dict[str, Any]:
    available = set(available_capabilities)
    required = Counter(str(x.get("required_capability")) for x in observations if x.get("required_capability"))
    gaps = [{"capability": cap, "evidence_count": count, "action": "grow_component_or_collect_evidence"} for cap, count in required.items() if cap not in available]
    return {"status": "gaps_detected" if gaps else "no_gap_observed", "gaps": gaps, "failure_is_diagnostic": True}


def propose_component_growth(gap: Dict[str, Any], evidence: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    if not gap.get("capability"):
        raise ValueError("component growth requires a capability gap")
    return {"status": "design_only", "component_proposal": {"capability": gap["capability"], "interface_contract": "待补充", "calculation_contract": "待补充", "implementation_options": ["discover_from_mixed_traces", "synthesize_and_validate"]}, "evidence_ids": [x.get("id") for x in evidence if x.get("id")], "verification_gates": ["static_contract", "symbolic_or_numeric_consistency", "ablation", "reproducible_implementation"]}


def static_symbolic_check(graph: Dict[str, Any]) -> Dict[str, Any]:
    ids = {n.get("id") for n in graph.get("nodes", [])}
    errors = []
    for edge in graph.get("edges", []):
        if edge.get("from") not in ids or edge.get("to") not in ids:
            errors.append({"class": "unknown_endpoint", "edge": edge.get("id")})
    adjacency = {node: [] for node in ids}
    for edge in graph.get("edges", []):
        if edge.get("from") in ids and edge.get("to") in ids:
            adjacency[edge["from"]].append(edge["to"])
    visiting, visited = set(), set()
    def visit(node: str) -> None:
        if node in visiting:
            errors.append({"class": "cycle", "node": node}); return
        if node in visited: return
        visiting.add(node)
        for child in adjacency[node]: visit(child)
        visiting.remove(node); visited.add(node)
    for node in ids: visit(node)
    return {"status": "passed" if not errors else "blocked", "errors": errors, "checks": ["endpoints", "acyclicity", "symbolic_dependency_consistency"]}
