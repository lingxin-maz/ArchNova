# -*- coding: utf-8 -*-
"""Proof dependency graph. A reference being present does not make it true."""
from collections import deque

def target_registry(data):
    rows=[(c['claim_id'],c) for c in data.get('claims',[])]
    rows += [(t['id'],t) for t in data.get('theory',[])]
    rows += [(s['id'],dict(s,part_id=p['id'])) for p in data.get('parts',[]) for s in p.get('swap_assessments',[])]
    return rows

def dependency_graph(data):
    rows=target_registry(data);targets=dict(rows);issues=[];by_target={key:[] for key in targets}
    if len(rows)!=len(targets):issues.append('Target IDs must be globally unique')
    if len(targets)>4096:issues.append('Proof graph exceeds 4096 target budget')
    deps={key:set() for key in targets}
    for key,target in rows:
        outline=target.get('proof_outline',{})
        local={item.get('id') for item in outline.get('assumptions',[])+outline.get('steps',[])}
        if local & set(targets):by_target[key].append('Local proof ID collides with global target')
        refs=list(outline.get('evidence_claim_ids',[]))
        refs += [ref for step in outline.get('steps',[]) for ref in step.get('premise_ids',[]) if ref not in local]
        for ref in refs:
            if ref not in targets:by_target[key].append('Unresolved proof dependency: '+str(ref))
            else:deps[key].add(ref)
    pending={key:len(value) for key,value in deps.items()};users={key:set() for key in targets}
    for key,values in deps.items():
        for dep in values:users[dep].add(key)
    queue=deque(sorted(key for key,n in pending.items() if n==0));order=[]
    while queue:
        key=queue.popleft();order.append(key)
        for user in sorted(users[key]):
            pending[user]-=1
            if pending[user]==0:queue.append(user)
    cyclic=set(targets)-set(order)
    for key in cyclic:by_target[key].append('Proof dependency cycle or dependency on a cycle: '+key)
    for key in targets:
        issues.extend(key+': '+message for message in by_target[key])
    return {'targets':targets,'dependencies':deps,'order':order+sorted(cyclic),'issues':issues,'by_target':by_target}

def dependency_closure(graph,key):
    found=set();stack=list(graph['dependencies'].get(key,()))
    while stack:
        item=stack.pop()
        if item in found:continue
        found.add(item);stack.extend(graph['dependencies'].get(item,()))
    found.discard(key)
    return sorted(found)
