import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

class MechanismGateTests(unittest.TestCase):
    def test_compositional_probe_is_hard_and_baseline_bound(self):
        from mechanism_gates import compositional_generalization_probe
        self.assertEqual(compositional_generalization_probe({}, {}, {"candidate_score": .8, "baseline_score": .7})["status"], "passed")
        self.assertEqual(compositional_generalization_probe({}, {}, None)["status"], "unresolved")

    def test_consensus_requires_independent_unanimity(self):
        from mechanism_gates import consensus_gate
        rows = [{"agent": "a", "verdict": "accept"}, {"agent": "b", "verdict": "accept"}, {"agent": "c", "verdict": "accept"}]
        self.assertEqual(consensus_gate(rows)["status"], "passed")
        self.assertEqual(consensus_gate(rows[:2])["status"], "unresolved")

    def test_reversible_safety_and_weight_gates_fail_closed(self):
        from mechanism_gates import reversibility_certificate, safety_harness_gate, conditional_weight_feasibility, mechanism_admission
        self.assertEqual(reversibility_certificate({})["status"], "blocked")
        self.assertEqual(safety_harness_gate({}, "agent")["status"], "unresolved")
        self.assertEqual(conditional_weight_feasibility({"parameterized": True})["status"], "blocked")
        self.assertEqual(mechanism_admission([{"gate": "x", "status": "blocked"}])["status"], "blocked")

if __name__ == "__main__":
    unittest.main()
