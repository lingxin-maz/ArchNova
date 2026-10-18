"""Component discovery and structure diagnostics for architecture search."""
from __future__ import annotations
from typing import Any, Dict, Sequence


def discover_symbolic_component(samples: Sequence[Dict[str, Any]], expression: str, residual: float, complexity: int, max_inputs: int = 4) -> Dict[str, Any]:
    if not expression or not samples:
        return {"status": "unresolved", "reason": "symbolic_regression_evidence_missing", "required": ["samples", "expression", "fit_receipt", "holdout_residual"]}
    dimensions = {len(item.get("inputs", [])) for item in samples if isinstance(item.get("inputs"), list)}
    if dimensions and max(dimensions) > max_inputs:
        return {"status": "blocked", "reason": "symbolic_regression_scope_exceeded", "max_inputs": max_inputs}
    return {"status": "proposed", "expression": expression, "residual": float(residual), "complexity": int(complexity), "component_contract": {"input_semantics": "待补充", "output_semantics": "待补充", "differentiability": "待补充"}, "verification_gates": ["holdout_fit", "symbolic_simplification", "typed_ports", "numeric_replay", "ablation"]}


def causal_necessity_gate(candidate: Dict[str, Any], shift_results: Dict[str, Any] | None = None, margin: float = 0.0) -> Dict[str, Any]:
    if not shift_results or "candidate_ood" not in shift_results or "baseline_ood" not in shift_results:
        return {"status": "unresolved", "gate": "causal_necessity", "reason": "distribution_shift_receipt_missing", "required_receipts": ["environments", "intervention_or_shift_definition", "candidate_ood", "baseline_ood", "subgraph_stability"]}
    gain = float(shift_results["candidate_ood"]) - float(shift_results["baseline_ood"])
    stable = bool(shift_results.get("subgraph_stable"))
    passed = gain > margin and stable
    return {"status": "passed" if passed else "blocked", "gate": "causal_necessity", "ood_gain": gain, "subgraph_stable": stable, "reason": "stable_shift_performance" if passed else "correlation_or_instability_detected"}


def fairness_robustness_pareto(points: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    objectives = [("quality", "max"), ("fairness_gap", "min"), ("robustness", "max"), ("ood_score", "max")]
    def dominates(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
        eq = all((float(a.get(k, 0)) <= float(b.get(k, 0))) if d == "min" else (float(a.get(k, 0)) >= float(b.get(k, 0))) for k, d in objectives)
        strict = any((float(a.get(k, 0)) < float(b.get(k, 0))) if d == "min" else (float(a.get(k, 0)) > float(b.get(k, 0))) for k, d in objectives)
        return eq and strict
    front = [p for p in points if not any(dominates(other, p) for other in points if other is not p)]
    return {"status": "scored", "frontier": front, "frontier_ids": [p.get("id") for p in front], "objectives": [{"name": k, "direction": d, "non_substitutable": True} for k, d in objectives], "required_reports": ["per_group_metrics", "shift_metrics", "robustness_definition"]}


def cmi_prefilter(graph: Dict[str, Any], cmi: float | None = None, threshold: float = 0.5) -> Dict[str, Any]:
    if cmi is None:
        return {"status": "unresolved", "gate": "circuit_modularity", "reason": "cmi_receipt_missing", "required_receipts": ["circuit_partition", "module_interaction_matrix", "cmi_value"]}
    value = float(cmi)
    return {"status": "passed" if value >= threshold else "blocked", "gate": "circuit_modularity", "cmi": value, "threshold": threshold, "reason": "modular_circuit_prior" if value >= threshold else "entangled_circuit_prior"}


def component_diagnostic_summary(symbolic: Dict[str, Any], causal: Dict[str, Any], pareto: Dict[str, Any], cmi: Dict[str, Any]) -> Dict[str, Any]:
    statuses = [symbolic.get("status"), causal.get("status"), pareto.get("status"), cmi.get("status")]
    return {"status": "retain_candidate" if all(s in {"proposed", "passed", "scored"} for s in statuses) else "needs_evidence", "checks": {"symbolic": symbolic.get("status"), "causal": causal.get("status"), "fairness_robustness": pareto.get("status"), "cmi": cmi.get("status")}, "non_substitutable": True}
