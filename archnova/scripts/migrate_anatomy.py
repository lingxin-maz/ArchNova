# -*- coding: utf-8 -*-
"""Explicit v1/v2.0 -> current contract draft migration. Never manufacture claims or passed gates."""
import argparse
import copy
import json
from pathlib import Path
from ontology_gen import ONTOLOGY_VERSION, SLOT_GROUP, SLOTS
from validation_core import canonical_ref


def migrate(original):
    if original.get('schema_version') not in (None, '2.0.0', '2.1.0', '2.2.0', '2.3.0', '2.4.0'):
        raise ValueError('Only unversioned v1, 2.0.0, 2.1.0, 2.2.0, 2.3.0 or 2.4.0 documents may be migrated')
    data = copy.deepcopy(original)
    data['schema_version'] = ONTOLOGY_VERSION
    data.setdefault('depth', 'standard')
    data.setdefault('claims', [])
    data.setdefault('metrics', [])
    data.setdefault('sources', [])
    data.setdefault('evidence_snapshots', [])
    data.setdefault('dataflow', {'node_parts': [], 'ports': [], 'edges': [], 'bindings': [],
                                 'shared_parameters': [], 'coupled_replacements': []})
    data.setdefault('ablations', [])
    data.setdefault('interactions', [])
    data['semantic_reviews'] = []
    data.setdefault('counterevidence_searches', [])
    data['publication'] = {'mode':'honest_report','conclusions':[]}
    data['repository_explorations'] = []
    data.setdefault('implementation_experiments', [])
    data.setdefault('mathematical_checks', [])
    data.setdefault('repository_discoveries', [])
    for check in data['mathematical_checks']:
        check.setdefault('binding',{'target_hash':'0'*64,'formal_hash':'0'*64,'case_hash':'0'*64,'mapping_note':'Migration did not establish target formalization; bind and review explicitly'})
    for i, theory in enumerate(data.get('theory', []), 1):
        theory.setdefault('id', 'theory:migrated-%d' % i)
    paper = data.setdefault('paper', {})
    if not paper.get('source_id'):
        paper['source_id'] = 'source:paper'
    if not any(s.get('id') == paper['source_id'] for s in data['sources']):
        ref = next((v for v in paper.get('ids', {}).values() if canonical_ref(v)), None)
        source = {'id': paper['source_id'], 'kind': 'publication' if ref else 'local',
                  'title': paper.get('title') or 'Unknown primary paper'}
        if ref:
            source['ref'] = ref
        data['sources'].append(source)
    for part in data.get('parts', []):
        for i, swap in enumerate(part.get('swap_assessments', []), 1):
            swap.setdefault('id', 'swap:' + str(part.get('id', 'unknown')) + ':' + str(i))
        part.setdefault('claim_ids', [])
        part.setdefault('importance', {
            'claimed_centrality': {'status': 'unknown', 'claim_ids': []},
            'theoretical_dependency': {'status': 'unknown', 'claim_ids': []},
            'ablation_ids': [], 'interaction_ids': []})
        candidates = part.get('swap_family') or ['<unresolved>']
        part.setdefault('swap_assessments', [{'candidate': candidates[0], 'relation': 'unknown',
            'conditions': 'Migration did not verify interface or behavior equivalence', 'evidence_claim_ids': []}])
        for i, swap in enumerate(part['swap_assessments'], 1):
            swap.setdefault('id', 'swap:' + str(part.get('id', 'unknown')) + ':' + str(i))
        slot = part.get('slot')
        if slot not in SLOTS:
            candidates = [sid for sid, name in SLOTS.items()
                          if name == slot and SLOT_GROUP[sid] == part.get('group')]
            if len(candidates) == 1:
                part['slot'] = candidates[0]
    for i, gap in enumerate(data.get('gaps', [])):
        gap.setdefault('id', 'gap:migrated-%d' % (i + 1))
    for i, proposal in enumerate(data.get('proposals', []), 1):
        proposal.setdefault('id', 'proposal:migrated-%d' % i)
        proposal.setdefault('numerical_prediction', {})
        proposal.setdefault('decision_rule', {})
        proposal.setdefault('affected_parts', [])
        proposal.setdefault('replacement_scope', 'unknown')
        proposal.setdefault('changes_shared_parameters', [])
        proposal.setdefault('contribution_rationale', '')
    # No inference of dominant parts, claims, experimental metrics or evidence support.
    data.setdefault('cost_model', {}).setdefault('dominant_part_ids', [])
    data['cost_model'].setdefault('calculation', {})
    data['stage'] = {'stage': 'G0', 'stage_status': 'blocked', 'receipts': [],
                     'blocking_items': ['Review sources/claims/metrics, typed dataflow, importance/ablations, affected parts and evidence snapshots, executable calculations/decision rules and all unresolved migration fields; then run checker and checkpoint_anatomy.py']}
    return data


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('anatomy')
    ap.add_argument('-o', '--output', required=True)
    a = ap.parse_args(argv)
    source, target = Path(a.anatomy), Path(a.output)
    if source.resolve() == target.resolve() or target.exists():
        ap.error('Choose a new output file; migration never overwrites an input or existing result')
    data = migrate(json.loads(source.read_text(encoding='utf-8-sig')))
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(str(target) + ': blocked draft; evidence requires review')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
