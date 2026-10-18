# -*- coding: utf-8 -*-
"""Provide actual declared computation context, never just an opaque digest."""
def review_context(data,target):
    parts={p['id']:p for p in data.get('parts',[])};graph=data.get('dataflow',{})
    selected={target.get('part_id') or target.get('subject')} & set(parts)
    if not selected:selected=set(parts)
    ports={p['id']:p for p in graph.get('ports',[])}
    changed=True
    while changed:
        before=set(selected)
        for binding in graph.get('bindings',[]):
            group={binding['part_id']}|set(binding.get('node_parts',[]))
            if group & selected:selected.update(group)
        for group in graph.get('shared_parameters',[])+graph.get('coupled_replacements',[]):
            if set(group['parts']) & selected:selected.update(group['parts'])
        for edge in graph.get('edges',[]):
            a=ports.get(edge['source'],{}).get('owner');b=ports.get(edge['target'],{}).get('owner')
            if a in selected or b in selected:selected.update(x for x in (a,b) if x in parts)
        changed=selected!=before
    selected_ports={key for key,port in ports.items() if port['owner'] in selected}
    subset={'node_parts':[p for p in graph.get('node_parts',[]) if p in selected and p in parts],
        'ports':[port for port in graph.get('ports',[]) if port['id'] in selected_ports],
        'edges':[e for e in graph.get('edges',[]) if e['source'] in selected_ports or e['target'] in selected_ports],
        'bindings':[b for b in graph.get('bindings',[]) if b.get('part_id') in selected and b.get('part_id') in parts and all(x in parts for x in b.get('node_parts',[]))],
        'shared_parameters':[g for g in graph.get('shared_parameters',[]) if set(g['parts']) & selected],
        'coupled_replacements':[g for g in graph.get('coupled_replacements',[]) if set(g['parts']) & selected]}
    return {'interface_contract':data.get('interface_contract',{}),'parts':[parts[p] for p in sorted(selected) if p in parts],
        'dataflow':subset,'selection':'Connected dependency closure including state, shared parameters and bindings',
        'comparison_semantics':target.get('comparison_contract') or {
            'kind':target.get('relation','mathematical_statement'),'domain':'Must be established from statement and interfaces',
            'observables':['outputs','state transitions','training/inference conditions'],
            'numeric_semantics':'Real function equality differs from floating point program behavior',
            'tolerance':'No implicit tolerance; approximate equivalence requires an explicit contract'},
        'limits':['Declared graph only; operator code and undeclared hidden state may be missing']}
