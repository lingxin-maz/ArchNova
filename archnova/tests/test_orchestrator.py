# -*- coding: utf-8 -*-
"""Contract tests for the planned multi-agent orchestration layer.

These tests intentionally run before the scheduler implementation.  The
contract keeps scheduling deterministic while allowing the executor to use a
thread/process pool internally.
"""
import sys
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


class MultiAgentSchedulingTests(unittest.TestCase):
    def tasks(self):
        return [
            {"id": "extract", "agent": "reader", "depends_on": []},
            {"id": "math", "agent": "proof", "depends_on": ["extract"]},
            {"id": "github", "agent": "repo", "depends_on": ["extract"]},
            {"id": "synthesis", "agent": "synth", "depends_on": ["math", "github"]},
        ]

    def test_build_batches_respects_dag_and_parallelizes_independent_tasks(self):
        from orchestrator import build_batches

        batches = build_batches(self.tasks())
        self.assertEqual([[t["id"] for t in batch] for batch in batches], [
            ["extract"], ["math", "github"], ["synthesis"]
        ])

    def test_build_batches_rejects_missing_dependencies_and_cycles(self):
        from orchestrator import build_batches

        with self.assertRaises(ValueError):
            build_batches([{"id": "a", "agent": "x", "depends_on": ["missing"]}])
        with self.assertRaises(ValueError):
            build_batches([
                {"id": "a", "agent": "x", "depends_on": ["b"]},
                {"id": "b", "agent": "y", "depends_on": ["a"]},
            ])

    def test_execute_schedule_runs_independent_batch_concurrently(self):
        from orchestrator import execute_schedule

        lock = threading.Lock()
        active = 0
        max_active = 0

        def runner(task, attempt):
            nonlocal active, max_active
            with lock:
                active += 1
                max_active = max(max_active, active)
            time.sleep(0.04)
            with lock:
                active -= 1
            return {"task_id": task["id"], "status": "completed", "attempt": attempt}

        result = execute_schedule(self.tasks(), runner, max_workers=2)
        self.assertEqual(result["status"], "completed")
        self.assertGreaterEqual(max_active, 2)
        self.assertEqual(set(result["results"]), {"extract", "math", "github", "synthesis"})

    def test_failed_agent_is_retried_then_downstream_runs_once(self):
        from orchestrator import execute_schedule

        attempts = {}

        def runner(task, attempt):
            attempts[task["id"]] = attempts.get(task["id"], 0) + 1
            if task["id"] == "math" and attempt == 1:
                raise RuntimeError("transient provider failure")
            return {"task_id": task["id"], "status": "completed", "attempt": attempt}

        result = execute_schedule(self.tasks(), runner, max_retries=1)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(attempts["math"], 2)
        self.assertEqual(attempts["synthesis"], 1)
        self.assertEqual(result["results"]["math"]["attempt"], 2)

    def test_needs_human_pauses_dependents_and_returns_resumable_state(self):
        from orchestrator import execute_schedule

        def runner(task, attempt):
            if task["id"] == "math":
                return {
                    "task_id": task["id"],
                    "status": "needs_human",
                    "reason": "formal proof target is ambiguous",
                    "handoff": {"questions": ["Which domain is intended?"]},
                }
            return {"task_id": task["id"], "status": "completed", "attempt": attempt}

        result = execute_schedule(self.tasks(), runner)
        self.assertEqual(result["status"], "needs_human")
        self.assertIn("math", result["human_handoffs"])
        self.assertNotIn("synthesis", result["results"])
        self.assertIn("synthesis", result["pending"])

    def test_merge_results_rejects_conflicts_and_preserves_provenance(self):
        from orchestrator import merge_agent_results

        merged = merge_agent_results([
            {"task_id": "extract", "status": "completed", "value": {"parts": ["A"]},
             "agent": {"identity": "reader-1", "model": "m1"}, "input_hash": "a" * 64},
            {"task_id": "math", "status": "completed", "value": {"proof": "ok"},
             "agent": {"identity": "proof-1", "model": "m2"}, "input_hash": "b" * 64},
        ])
        self.assertEqual(set(merged["results"]), {"extract", "math"})
        self.assertEqual(merged["results"]["math"]["agent"]["model"], "m2")
        self.assertEqual(len(merged["provenance"]), 2)

        with self.assertRaises(ValueError):
            merge_agent_results([
                {"task_id": "math", "status": "completed", "value": {"proof": "ok"}, "input_hash": "b" * 64},
                {"task_id": "math", "status": "completed", "value": {"proof": "wrong"}, "input_hash": "b" * 64},
            ])


if __name__ == "__main__":
    unittest.main()
