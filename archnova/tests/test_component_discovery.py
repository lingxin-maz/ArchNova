import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

class ComponentDiscoveryTests(unittest.TestCase):
    def test_symbolic_component_is_a_proposal_with_contract_gates(self):
        from component_discovery import discover_symbolic_component
        result = discover_symbolic_component([{"inputs": [1, 2]}], "x0 + sin(x1)", .01, 3)
        self.assertEqual(result["status"], "proposed")
        self.assertIn("typed_ports", result["verification_gates"])

    def test_causal_gate_requires_shift_stability(self):
        from component_discovery import causal_necessity_gate
        self.assertEqual(causal_necessity_gate({}, {"candidate_ood": .8, "baseline_ood": .7, "subgraph_stable": True})["status"], "passed")
        self.assertEqual(causal_necessity_gate({}, None)["status"], "unresolved")

    def test_fairness_robustness_and_cmi_are_non_substitutable(self):
        from component_discovery import fairness_robustness_pareto, cmi_prefilter
        points = [{"id": "a", "quality": .9, "fairness_gap": .1, "robustness": .8, "ood_score": .8}, {"id": "b", "quality": .8, "fairness_gap": .2, "robustness": .7, "ood_score": .7}]
        self.assertEqual(fairness_robustness_pareto(points)["frontier_ids"], ["a"])
        self.assertEqual(cmi_prefilter({}, .7)["status"], "passed")
        self.assertEqual(cmi_prefilter({}, .2)["status"], "blocked")

if __name__ == "__main__":
    unittest.main()
