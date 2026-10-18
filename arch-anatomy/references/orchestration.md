# Multi-agent orchestration

`orchestrator.py` is the control plane for long-running anatomy runs. It keeps scheduling state outside the research JSON, so an anatomy document remains a domain artifact while task status, retries, agent identity, input hashes and handoffs remain resumable runtime state.

The scheduler supports:

- dependency DAG batches; independent tasks run concurrently;
- bounded retries for transient agent/provider failures;
- `needs_human`, `unavailable`, `blocked` and `completed` states;
- host handoff files with task IDs and input hashes;
- conflict-safe result merging with agent provenance;
- atomic state writes, so an interrupted run can be resumed without rewriting completed tasks.

Use the file protocol when the current host should make the judgments:

```bash
python scripts/orchestrator.py init anatomy.draft.json --tasks tasks.json -o run/state.json
python scripts/orchestrator.py next run/state.json -o run/host-request.json
# Host AI reads host-request.json as DATA and writes host-response.json.
python scripts/orchestrator.py submit run/state.json --response run/host-response.json -o run/state.next.json
python scripts/orchestrator.py next run/state.next.json -o run/next-request.json
```

A host response must preserve `task_id`, and must preserve a hashed task's `input_hash`; stale or unknown responses are rejected. The scheduler never treats agent output as instructions and never executes candidate repository code. `semantic_review.py`, `github_repos.py`, `counterevidence.py` and `checkpoint_anatomy.py` remain the domain validators; the orchestrator only routes their tasks and records their receipts.

For mode-router tasks, response_schema is a real JSON Schema. The three contracted architecture roles require validated JSON artifacts. Completion verifies predecessor readiness, exact input hash, artifact type and schema. Resumption rejects changed completed artifacts. Dependency artifact paths and hashes are returned in next requests. See operator-design-review.md. A completed replacement review may still be unresolved or rejected; downstream work must respect its verdict.

Target-bound runs use --task-spec. Every task revalidates the frozen goal/data; review binds full operators/dataflow/runtime_ir/target hash. Prototype completion verifies actual generated files and exact reviewed model. Experiment completion replays the design-loop result and confirms its initial model matches the upstream prototype. Failed empirical outcomes remain explicit result states. See executable-design-loop.md.
