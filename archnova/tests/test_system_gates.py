import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

class SystemGateTests(unittest.TestCase):
    def test_eci_requires_end_to_end_witness(self):
        from system_gates import eci_witness_chain
        source = {"source_id": "s", "principal_id": "p", "task_id": "t", "root_authorization": "r", "policy_id": "pol"}
        effects = [{"id": "e", "witness_id": "w"}]
        self.assertEqual(eci_witness_chain(source, effects, [{"id": "w", "source_id": "s"}])["status"], "passed")
        self.assertEqual(eci_witness_chain(source, effects, [])["status"], "blocked")

    def test_physical_and_bias_gates_fail_closed(self):
        from system_gates import physical_substrate_feasibility, inductive_bias_compatibility
        hw = {"substrate_id": "chiplet", "interconnect_bandwidth": 10, "power_budget": 20, "partition_constraints": {}}
        self.assertEqual(physical_substrate_feasibility({}, hw)["status"], "unresolved")
        self.assertEqual(inductive_bias_compatibility({"required_biases": ["locality"]}, [{"biases": []}])["status"], "blocked")

    def test_invisible_layers_and_admission(self):
        from system_gates import invisible_layer_audit, system_admission
        result = invisible_layer_audit([{"id": "a", "assumption": "sync", "required_layer": "sync_boundary"}], [], [])
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(system_admission([{"gate": "eci", "status": "unresolved"}])["status"], "unresolved")

if __name__ == "__main__":
    unittest.main()
