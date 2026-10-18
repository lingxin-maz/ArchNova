"""System-level legality gates: security continuity, physical substrate, bias and invisible layers."""
from __future__ import annotations
from typing import Any, Dict, Iterable, Sequence


def eci_witness_chain(source: Dict[str, Any], effects: Sequence[Dict[str, Any]], witness: Sequence[Dict[str, Any]] | None = None) -> Dict[str, Any]:
    required = ["source_id", "principal_id", "task_id", "root_authorization", "policy_id"]
    missing = [key for key in required if not source.get(key)]
    if missing or not effects:
        return {"status": "unresolved", "gate": "eci", "reason": "security_context_incomplete", "missing": missing + (["effects"] if not effects else []), "required_receipts": ["field_provenance", "component_contracts", "policy_binding", "effect_witness"]}
    witness = list(witness or [])
    chain_ids = {item.get("id") for item in witness}
    complete = all(effect.get("witness_id") in chain_ids for effect in effects) and all(item.get("source_id") == source.get("source_id") for item in witness)
    return {"status": "passed" if complete else "blocked", "gate": "eci", "witness_count": len(witness), "effects": len(effects), "reason": "end_to_end_consequence_integrity" if complete else "security_context_discontinuity"}


def physical_substrate_feasibility(candidate: Dict[str, Any], hardware: Dict[str, Any], receipt: Dict[str, Any] | None = None) -> Dict[str, Any]:
    required = ["substrate_id", "interconnect_bandwidth", "power_budget", "partition_constraints"]
    missing = [key for key in required if key not in hardware]
    if missing:
        return {"status": "unresolved", "gate": "physical_substrate", "reason": "hardware_contract_missing", "missing": missing}
    if not receipt:
        return {"status": "unresolved", "gate": "physical_substrate", "reason": "chiplet_or_accelerator_receipt_missing", "required_receipts": ["partition_plan", "bandwidth_check", "power_check", "latency_or_throughput"]}
    feasible = all(receipt.get(key) is True for key in ("bandwidth_ok", "power_ok", "partition_ok"))
    return {"status": "passed" if feasible else "blocked", "gate": "physical_substrate", "substrate_id": hardware["substrate_id"], "reason": "physical_constraints_satisfied" if feasible else "physical_constraint_violation"}


def inductive_bias_compatibility(task: Dict[str, Any], components: Sequence[Dict[str, Any]], evidence: Dict[str, Any] | None = None) -> Dict[str, Any]:
    task_bias = set(task.get("required_biases", []))
    component_bias = set().union(*(set(item.get("biases", [])) for item in components)) if components else set()
    missing = sorted(task_bias - component_bias)
    if missing:
        return {"status": "blocked" if not evidence else "unresolved", "gate": "inductive_bias", "reason": "task_bias_not_covered", "missing_biases": missing, "required": ["task_bias_probe", "specialized_nonlinearity_or_component"]}
    if not evidence:
        return {"status": "unresolved", "gate": "inductive_bias", "reason": "transfer_evidence_missing", "required_receipts": ["task_family_split", "bias_ablation", "transfer_or_nontransfer_result"]}
    return {"status": "passed" if evidence.get("compatible") is True else "blocked", "gate": "inductive_bias", "reason": "bias_transfer_supported" if evidence.get("compatible") is True else "bias_incompatible_or_unproven"}


def invisible_layer_audit(assumptions: Sequence[Dict[str, Any]], contracts: Sequence[Dict[str, Any]], runtime_dependencies: Iterable[str]) -> Dict[str, Any]:
    declared = set(runtime_dependencies)
    for contract in contracts:
        declared.update(contract.get("provides", []))
        declared.update(contract.get("requires", []))
    missing = [{"id": item.get("id"), "assumption": item.get("assumption"), "required_layer": item.get("required_layer")} for item in assumptions if item.get("required_layer") and item.get("required_layer") not in declared]
    return {"status": "blocked" if missing else "passed", "gate": "invisible_layer", "missing_layers": missing, "reason": "implicit_dependency_not_constructed" if missing else "assumptions_explicitly_bound"}


def system_admission(gates: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    statuses = {gate.get("gate", str(index)): gate.get("status") for index, gate in enumerate(gates)}
    if any(value == "blocked" for value in statuses.values()):
        return {"status": "blocked", "gate_statuses": statuses, "reason": "system_legality_gate_failed"}
    if any(value in {"unresolved", "planned"} for value in statuses.values()):
        return {"status": "unresolved", "gate_statuses": statuses, "reason": "system_legality_evidence_incomplete"}
    return {"status": "admissible", "gate_statuses": statuses, "reason": "system_legality_gates_passed"}
