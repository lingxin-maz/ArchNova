import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

class MetaSearchTests(unittest.TestCase):
    def test_adaptive_fitness_and_operator_meta_evolution_are_reviewable(self):
        from meta_search import adaptive_fitness, meta_evolve_operator_catalog
        policy = adaptive_fitness([{"score": 1, "stack_rate": 0.8}] * 3)
        self.assertTrue(policy["requires_review"])
        result = meta_evolve_operator_catalog({"insert": {}}, [{"operation": "insert", "status": "blocked"}] * 4)
        self.assertEqual(result["recommendations"][0]["action"], "deprecate_or_repair")

    def test_pareto_and_complexity_niches(self):
        from meta_search import hardware_pareto, complexity_niches
        points = [{"id": "a", "quality": 0.9, "latency": 2, "energy": 2, "memory": 2, "area": 2, "complexity": 1}, {"id": "b", "quality": 0.8, "latency": 1, "energy": 1, "memory": 1, "area": 1, "complexity": 2}, {"id": "c", "quality": 0.7, "latency": 3, "energy": 3, "memory": 3, "area": 3, "complexity": 3}]
        self.assertEqual(set(hardware_pareto(points)["frontier_ids"]), {"a", "b"})
        self.assertEqual(len(complexity_niches(points, bins=2)["niches"]), 3)

    def test_component_growth_and_static_symbolic_check(self):
        from meta_search import detect_component_gaps, propose_component_growth, static_symbolic_check
        gap = detect_component_gaps([{"required_capability": "global_memory", "id": "obs-1"}], ["local_mixing"])
        self.assertEqual(gap["status"], "gaps_detected")
        self.assertEqual(propose_component_growth(gap["gaps"][0], [{"id": "obs-1"}])["status"], "design_only")
        self.assertEqual(static_symbolic_check({"nodes": [{"id": "a"}, {"id": "b"}], "edges": [{"id": "e", "from": "a", "to": "b"}]})["status"], "passed")
        self.assertEqual(static_symbolic_check({"nodes": [{"id": "a"}], "edges": [{"id": "e", "from": "a", "to": "a"}]})["status"], "blocked")

if __name__ == "__main__":
    unittest.main()
