import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

class SearchProtocolTests(unittest.TestCase):
    def test_edit_catalog_has_failure_modes_and_repair_prompts(self):
        from search_protocol import EDIT_CATALOG, validate_edit_action, diagnose_edit_failure
        self.assertTrue(EDIT_CATALOG["insert"]["failure_modes"])
        self.assertTrue(EDIT_CATALOG["insert"]["repair_prompt"])
        self.assertEqual(validate_edit_action({"op": "insert", "reason": "cross branch information exchange"})["status"], "accepted")
        self.assertEqual(diagnose_edit_failure("shape mismatch")["class"], "interface_violation")

    def test_group_relative_and_cross_scale_evaluation_require_common_cohort(self):
        from search_protocol import group_relative_score, cross_scale_promotion, parameter_matched_baseline
        rows = [{"candidate_id": "a", "metric": 1.0, "seed": 1}, {"candidate_id": "b", "metric": 2.0, "seed": 1}, {"candidate_id": "a", "metric": 1.2, "seed": 2}, {"candidate_id": "b", "metric": 1.8, "seed": 2}]
        result = group_relative_score(rows)
        self.assertEqual(result["best_candidate"], "a")
        self.assertTrue(result["trimmed_means"])
        self.assertEqual(cross_scale_promotion({"small_scale_gain": 0.1, "large_scale_gain": 0.03, "peer_pass": True})["status"], "promote_to_large_scale")
        self.assertEqual(parameter_matched_baseline({"params": 120}, {"params": 100})["target_params"], 120)

    def test_slot_decomposition_and_validator_feedback(self):
        from search_protocol import decompose_slots, validator_feedback
        graph = {"nodes": [{"id": "a", "component_id": "attn", "scope": "block"}, {"id": "b", "component_id": "mlp", "scope": "block"}], "edges": []}
        slots = decompose_slots(graph)
        self.assertEqual([s["slot_id"] for s in slots], ["slot:0", "slot:1"])
        self.assertIn("diagnosis", validator_feedback("orphan node"))

if __name__ == "__main__":
    unittest.main()
