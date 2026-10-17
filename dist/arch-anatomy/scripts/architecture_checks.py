# -*- coding: utf-8 -*-
"""Conservative declared-contract checks, not execution or causal proof."""
from collections import defaultdict
import math


def unique(rows, rep, label):
    result = {}
    for row in rows:
        rid = row['id']
        if rid in result:
            rep.err(label, 'Duplicate id: ' + rid)
        result[rid] = row
    return result


def check_architecture(data, rep, release=False):
    graph = data['dataflow']
    parts = {p['id']: p for p in data['parts']}
    claims = {c['claim_id']: c for c in data['claims']}
    nodes = set(graph['node_parts'])
    for pid in nodes - set(parts):
        rep.err('dataflow.node_parts', 'Unknown part: ' + pid)
    bindings = {}
    for binding in graph['bindings']:
        pid = binding['part_id']
        if pid not in parts or pid in bindings or pid in nodes:
            rep.err('dataflow.bindings', 'Unknown, duplicate or also executable part: ' + pid)
        bindings[pid] = binding
        if set(binding['node_parts']) - nodes:
            rep.err('dataflow.bindings', 'Binding targets must be executable node_parts')
    for pid in set(parts) - nodes - set(bindings):
        rep.err('dataflow', 'Part lacks executable node or explicit binding: ' + pid)
    ports = unique(graph['ports'], rep, 'dataflow.ports')
    edges = unique(graph['edges'], rep, 'dataflow.edges')
    owners = defaultdict(set)
    for pid, port in ports.items():
        owner = port['owner']
        if owner not in nodes:
            rep.err(pid, 'Port owner not in node_parts: ' + owner)
        owners[owner].add(port['direction'])
        if len(port['shape']) != len(port['axes']):
            rep.err(pid, 'shape rank differs from axes rank')
        if port['object_type'] == 'scalar' and port['shape']:
            rep.err(pid, 'Scalar shape must be empty')
        if port['dtype'] == 'unknown' or any(v == '?' for v in port['shape']):
            rep.warn(pid, 'Unknown type/shape requires review; no compatibility proof')
    for node in nodes:
        if not owners[node]:
            rep.err(node, 'Executable node has no ports')
    incoming = defaultdict(int)
    outgoing = defaultdict(int)
    adjacency = defaultdict(set)
    for eid, edge in edges.items():
        source, target = ports.get(edge['source']), ports.get(edge['target'])
        if source is None or target is None:
            rep.err(eid, 'Unresolved source/target port')
            continue
        if source['direction'] != 'output' or target['direction'] != 'input':
            rep.err(eid, 'Edges must connect output -> input')
        incoming[edge['target']] += 1
        outgoing[edge['source']] += 1
        if target['external']:
            rep.err(eid, 'Externally supplied input cannot also have an incoming edge')
        for field in ('object_type', 'shape', 'axes', 'dtype', 'unit', 'measure', 'state'):
            if source[field] != target[field]:
                rep.err(eid, 'Incompatible port field: ' + field + '; use an explicit adapter node')
        if edge['kind'] == 'state':
            if edge['delay'] < 1 or source['state'] == 'none':
                rep.err(eid, 'State feedback requires delay >= 1 and an explicit state semantic')
        else:
            if edge['delay'] != 0:
                rep.err(eid, 'Data edge delay must be zero')
            adjacency[source['owner']].add(target['owner'])
    for pid, port in ports.items():
        if port['direction'] == 'output' and not port['external'] and outgoing[pid] == 0:
            rep.err(pid, 'Unused internal output; declare an external output or connect its consumer')
        if port['direction'] == 'input' and not port['external'] and incoming[pid] != 1:
            rep.err(pid, 'Internal input needs exactly one producer; use an explicit merge node')
    # Kahn traversal avoids recursion limits on large declared graphs.
    indegree = {node: 0 for node in nodes}
    for source in adjacency:
        for target in adjacency[source]:
            if target in indegree:
                indegree[target] += 1
    queue = [node for node in nodes if indegree[node] == 0]
    seen = 0
    while queue:
        node = queue.pop()
        seen += 1
        for target in adjacency[node]:
            if target in indegree:
                indegree[target] -= 1
                if indegree[target] == 0:
                    queue.append(target)
    if seen != len(nodes):
        rep.err('dataflow.edges', 'Instantaneous data cycle; recurrence needs a delayed state edge')
    shared = unique(graph['shared_parameters'], rep, 'shared_parameters')
    coupled = unique(graph['coupled_replacements'], rep, 'coupled_replacements')
    for item in list(shared.values()) + list(coupled.values()):
        if set(item['parts']) - set(parts):
            rep.err(item['id'], 'Unknown part in constraint')
    for i, proposal in enumerate(data['proposals']):
        path = 'proposals[%d]' % i
        affected = set(proposal['affected_parts'])
        if affected - set(parts) or proposal['targets_part'] not in affected:
            rep.err(path, 'affected_parts must resolve and contain targets_part')
        if proposal['replacement_scope'] == 'unknown':
            rep.warn(path, 'Replacement scope unresolved')
        if proposal['replacement_scope'] == 'independent' and affected != {proposal['targets_part']}:
            rep.err(path, 'Independent replacement must affect exactly its target')
        for constraint in coupled.values():
            required = set(constraint['parts'])
            if affected & required and not required <= affected:
                rep.err(path, 'Missing coupled parts: ' + constraint['id'])
        for gid in proposal['changes_shared_parameters']:
            if gid not in shared:
                rep.err(path, 'Unknown shared parameter group: ' + gid)
            elif not set(shared[gid]['parts']) <= affected:
                rep.err(path, 'Changed shared parameter requires all owners: ' + gid)
    for pid, part in parts.items():
        for swap in part['swap_assessments']:
            if swap['relation'] == 'unknown':
                rep.warn(pid, 'Swap compatibility unresolved')
            if swap['candidate'] not in part['swap_family']:
                rep.err(pid, 'Swap assessment candidate not in swap_family')
            evidence = [claims[cid] for cid in swap['evidence_claim_ids'] if cid in claims]
            if len(evidence) != len(swap['evidence_claim_ids']):
                rep.err(pid, 'Swap assessment contains unknown claim ids')
            if swap['relation'] in ('behaviorally_equivalent', 'implementation_equivalent'):
                if not any(c['subject'] == pid and c['claim_type'] == 'derivation' for c in evidence):
                    rep.err(pid, 'Equivalence assertion requires a same-part derivation claim; human proof review still required')
    check_importance(data, rep)


def check_importance(data, rep):
    parts = {p['id']: p for p in data['parts']}
    claims = {c['claim_id']: c for c in data['claims']}
    metrics = {m['id'] for m in data['metrics']}
    ablations = unique(data['ablations'], rep, 'ablations')
    interactions = unique(data['interactions'], rep, 'interactions')
    for aid, ablation in ablations.items():
        if set(ablation['part_ids']) - set(parts):
            rep.err(aid, 'Ablation refers to unknown part')
        if ablation['metric_id'] not in metrics:
            rep.err(aid, 'Unknown metric_id')
        covered = set()
        for cid in ablation['evidence_claim_ids']:
            claim = claims.get(cid)
            if not claim or claim['subject'] not in ablation['part_ids'] or claim['claim_type'] != 'measurement':
                rep.err(aid, 'Ablation needs measurement evidence for an affected part')
            elif any(e['support'] == 'direct' for e in claim['evidence']):
                covered.add(claim['subject'])
        if set(ablation['part_ids']) - covered:
            rep.err(aid, 'Every affected part needs direct measurement evidence')
        lo, hi = ablation['effect']['confidence_interval']
        if not all(math.isfinite(x) for x in (lo, hi, ablation['effect']['delta'])) or not lo <= ablation['effect']['delta'] <= hi:
            rep.err(aid, 'Invalid effect confidence interval/delta')
        if ablation['attribution'] == 'controlled_comparison':
            if (any(value != 'matched' for value in ablation['controls'].values())
                    or ablation['retraining'] != 'yes' or len(ablation['seeds']) < 2):
                rep.err(aid, 'Controlled comparison needs matched budgets/data, retraining and multiple seeds; not a causal proof')
    for iid, interaction in interactions.items():
        group = set(interaction['part_ids'])
        if group - set(parts) or interaction['metric_id'] not in metrics:
            rep.err(iid, 'Interaction has unknown part or metric')
        experiments = [ablations[aid] for aid in interaction['ablation_ids'] if aid in ablations]
        if len(experiments) != 3:
            rep.err(iid, 'Pair interaction requires A, B and joint AB ablations')
            continue
        subsets = {frozenset(a['part_ids']) for a in experiments}
        expected = {frozenset([p]) for p in group} | {frozenset(group)}
        if subsets != expected or any(a['metric_id'] != interaction['metric_id'] for a in experiments):
            rep.err(iid, 'Interaction ablations must be singleton A, singleton B and joint AB on the same metric')
        if len({a['control_id'] for a in experiments}) != 1:
            rep.err(iid, 'Interaction ablations need the same control baseline')
        joint = next((a for a in experiments if set(a['part_ids']) == group), None)
        if joint:
            contrast = joint['effect']['delta'] - sum(a['effect']['delta'] for a in experiments if a is not joint)
            if not math.isclose(contrast, interaction['contrast'], rel_tol=1e-9, abs_tol=1e-12):
                rep.err(iid, 'Interaction contrast must equal delta_AB - delta_A - delta_B')
        if interaction['attribution'] == 'controlled_comparison' and any(a['attribution'] != 'controlled_comparison' for a in experiments):
            rep.err(iid, 'Controlled interaction requires controlled component ablations')
        lo, hi = interaction['confidence_interval']
        if not lo <= interaction['contrast'] <= hi:
            rep.err(iid, 'Invalid interaction confidence interval')
    for pid, part in parts.items():
        importance = part['importance']
        for field in ('claimed_centrality', 'theoretical_dependency'):
            assessment = importance[field]
            if assessment['status'] == 'documented' and not assessment['claim_ids']:
                rep.err(pid, 'Documented ' + field + ' requires evidence')
            for cid in assessment['claim_ids']:
                if cid not in claims or claims[cid]['subject'] != pid:
                    rep.err(pid, 'Importance evidence claim must resolve to this part')
        for aid in importance['ablation_ids']:
            if aid not in ablations or pid not in ablations[aid]['part_ids']:
                rep.err(pid, 'Unresolved or unrelated ablation id')
        for iid in importance['interaction_ids']:
            if iid not in interactions or pid not in interactions[iid]['part_ids']:
                rep.err(pid, 'Unresolved or unrelated interaction id')
