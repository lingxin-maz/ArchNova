# -*- coding: utf-8 -*-
"""Rank reference parts under explicit interface constraints, without equivalence claims."""
import argparse
import copy
from jsonschema import Draft4Validator
import json
import re
from component_library import load_index, SCHEMA
from orchestrator import atomic_write

def retrieve(index, query='', required=None, limit=10):
    if required is not None and not isinstance(required, dict):
        raise ValueError('Constraints must be an object')
    required = required or {}
    allowed = {'input_shape', 'output_shape', 'state', 'dtype', 'layout', 'invariants', 'functional_group','ports','state_kind'}
    if set(required)-allowed: raise ValueError('Unknown constraints: ' + str(sorted(set(required)-allowed)))
    for key, value in required.items():
        if key == 'ports':
            port_schema=copy.deepcopy(json.loads(SCHEMA.read_text(encoding='utf8'))['definitions']['port'])
            port_schema['required']=['id']
            for k in ('owner','external'):del port_schema['properties'][k]
            if not isinstance(value,list) or not value or any(list(Draft4Validator(port_schema).iter_errors(p)) for p in value):
                raise ValueError('ports must contain named, typed partial port constraints')
            if len({p['id'] for p in value})!=len(value):raise ValueError('Duplicate port constraint')
            continue
        if key in ('input_shape', 'output_shape', 'invariants'):
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                raise ValueError(key + ' must be an array of strings')
        elif not isinstance(value, str): raise ValueError(key + ' must be a string')
    if limit < 1: raise ValueError('limit must be positive')
    tokens = set(re.findall(r'\w+', query.casefold()))
    candidates = []; rejected = []
    for entry in index['components']:
        c = entry['component']; mismatches = []
        for key, expected in required.items():
            if key == 'ports':
                ports={p['id']:p for p in c['ports']}
                for port in expected:
                    actual=ports.get(port['id'])
                    if actual is None or any(actual.get(k)!=v for k,v in port.items()):
                        mismatches.append({'field':'ports.'+port['id'],'required':port,'actual':actual})
                continue
            if key == 'state_kind':
                actual=c['state_contract']['kind']
                if actual!=expected:mismatches.append({'field':key,'required':expected,'actual':actual})
                continue
            actual = c.get(key) if key in ('functional_group', 'invariants') else c['interface'].get(key)
            matches = set(expected).issubset(actual or []) if key == 'invariants' else actual == expected
            if not matches: mismatches.append({'field': key, 'required': expected, 'actual': actual})
        if mismatches:
            rejected.append({'component_id': c['component_id'], 'mismatches': mismatches}); continue
        text = json.dumps({k: c[k] for k in ('name', 'functional_group', 'operator_family', 'tags')}, ensure_ascii=False).casefold()
        score = len(tokens & set(re.findall(r'\w+', text)))
        if tokens and score == 0: continue
        candidates.append({'component_id': c['component_id'], 'score': score,
                           'path': entry['path'], 'component': c,
                           'compatibility': 'declared_constraints_match' if required else 'unchecked',
                           'equivalence': 'unverified', 'requires_retraining': 'unknown',
                           'remaining_checks': ['symbolic shape bindings/adapters', 'causality and symmetry assumptions',
                                                'state semantics', 'numerical behavior', 'complexity under target sizes']})
    candidates.sort(key=lambda c: (-c['score'], c['component_id']))
    return {'query': query, 'required': required, 'candidates': candidates[:limit], 'rejected': rejected,
            'scope_limits': ['Lexical ranking over supplied metadata; no semantic search or proof of equivalence.',
                             'Shape matching is literal; different symbols require explicit review.',
                             'Complexity strings are assumptions, not measured performance.']}

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--index', required=True); p.add_argument('--query', default='')
    p.add_argument('--require', help='JSON file containing explicit interface constraints')
    p.add_argument('--limit', type=int, default=10); p.add_argument('-o', '--output', required=True)
    a = p.parse_args(argv)
    try:
        from pathlib import Path
        constraints = json.loads(Path(a.require).read_text(encoding='utf-8')) if a.require else {}
        result = retrieve(load_index(a.index), a.query, constraints, a.limit)
        atomic_write(a.output, result)
    except (ValueError, KeyError, OSError) as exc: p.error(str(exc))
    print(json.dumps({'candidates': len(result['candidates']), 'output': a.output}))

if __name__ == '__main__': main()
