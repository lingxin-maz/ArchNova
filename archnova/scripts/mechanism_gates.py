"""Mechanism-level admission gates for composition, trust and deployability."""
from __future__ import annotations
from typing import Any, Dict, Iterable, Sequence


def compositional_generalization_probe(candidate: Dict[str, Any], baseline: Dict[str, Any], results: Dict[str, Any] | None = None, margin: float = 0.0) -> Dict[str, Any]:
    if not results or "candidate_score" not in results or "baseline_score" not in results:
        return {"status": "unresolved", "gate": "compositional_generalization", "reason": "probe_receipt_missing", "required_receipts": ["probe_tasks", "candidate_probe_score", "matched_baseline_probe_score", "permutation_or_recombination_receipt"]}
    gain = float(results["candidate_score"]) - float(results["baseline_score"])
    passed = gain > margin
    return {"status": "passed" if passed else "blocked", "gate": "compositional_generalization", "gain": gain, "margin": margin, "probe_family": results.get("probe_family", "recombination"), "reason": "candidate_outperforms_matched_baseline" if passed else "no_structural_composition_gain"}


def consensus_gate(assessments: Sequence[Dict[str, Any]], required_agents: int = 3) -> Dict[str, Any]:
    if len(assessments) < required_agents:
        return {"status": "unresolved", "gate": "heterogeneous_consensus", "reason": "insufficient_independent_assessments", "required_agents": required_agents}
    verdicts = [str(a.get("verdict", "")).lower() for a in assessments]
    accepted = all(v in {"accept", "approve", "pass"} for v in verdicts)
    independent = len({a.get("agent") for a in assessments}) == len(assessments)
    return {"status": "passed" if accepted and independent else "blocked", "gate": "heterogeneous_consensus", "agents": [a.get("agent") for a in assessments], "verdicts": verdicts, "unanimous": accepted, "independent": independent, "reason": "unanimous_independent_review" if accepted and independent else "consensus_or_independence_failed"}


def reversibility_certificate(contract: Dict[str, Any], receipt: Dict[str, Any] | None = None) -> Dict[str, Any]:
    if not contract.get("reversible_primitives") and not contract.get("reversible_wrapper"):
        return {"status": "blocked", "gate": "reversible_faithful", "reason": "no_reversible_path_declared"}
    if not receipt:
        return {"status": "unresolved", "gate": "reversible_faithful", "reason": "certificate_receipt_missing", "required_receipts": ["reconstruction_error", "contribution_sum_error", "reverse_execution_receipt"]}
    errors = [float(receipt.get(k, 1.0)) for k in ("reconstruction_error", "contribution_sum_error")]
    passed = max(errors) <= float(receipt.get("tolerance", 1e-9)) and receipt.get("reverse_execution") is True
    return {"status": "passed" if passed else "blocked", "gate": "reversible_faithful", "errors": errors, "tolerance": receipt.get("tolerance", 1e-9), "reason": "exact_reverse_certificate" if passed else "certificate_failed"}


def safety_harness_gate(candidate: Dict[str, Any], domain: str, receipt: Dict[str, Any] | None = None) -> Dict[str, Any]:
    if not domain:
        raise ValueError("safety harness requires a deployment domain")
    if not receipt:
        return {"status": "unresolved", "gate": "safety_harness", "domain": domain, "reason": "domain_specific_harness_missing", "required_receipts": ["generated_policy", "executable_constraints", "adversarial_review", "utility_safety_tradeoff"]}
    passed = receipt.get("adversarial_review") is True and receipt.get("structure_bound") is True and receipt.get("utility_safety_tradeoff") is not None
    return {"status": "passed" if passed else "blocked", "gate": "safety_harness", "domain": domain, "structure_bound": bool(receipt.get("structure_bound")), "reason": "structure_and_domain_bound" if passed else "harness_not_revalidated"}


def conditional_weight_feasibility(structure: Dict[str, Any], alignment: Dict[str, Any] | None = None) -> Dict[str, Any]:
    if not structure.get("parameterized", True):
        return {"status": "not_applicable", "gate": "conditional_weights", "reason": "structure_has_no_trainable_parameters"}
    if not alignment or not alignment.get("canonicalization") or not alignment.get("checkpoint_compatibility"):
        return {"status": "blocked", "gate": "conditional_weights", "reason": "representation_alignment_missing", "required": ["permutation_or_scale_canonicalization", "checkpoint_compatibility", "functional_equivalence_check"]}
    return {"status": "planned", "gate": "conditional_weights", "reason": "aligned_weight_generation_can_reduce_screening_cost", "requires": ["generator_receipt", "functional_equivalence_check", "full_training_confirmation"]}


def mechanism_admission(gates: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    gates = list(gates)
    statuses = {g.get("gate", str(i)): g.get("status") for i, g in enumerate(gates)}
    if any(s == "blocked" for s in statuses.values()):
        return {"status": "blocked", "gate_statuses": statuses, "reason": "mechanism_gate_failed"}
    if any(s in {"unresolved", "planned"} for s in statuses.values()):
        return {"status": "unresolved", "gate_statuses": statuses, "reason": "mechanism_receipts_incomplete"}
    return {"status": "admissible", "gate_statuses": statuses, "reason": "all_mechanism_gates_passed"}


def record_failure_memory(history: list[Dict[str, Any]], gate: Dict[str, Any], candidate_id: str) -> list[Dict[str, Any]]:
    if gate.get("status") == "passed":
        return history
    history.append({"candidate_id": candidate_id, "gate": gate.get("gate"), "reason": gate.get("reason"), "repair": gate.get("required_receipts", [])})
    return history
