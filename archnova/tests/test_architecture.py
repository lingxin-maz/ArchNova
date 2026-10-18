# -*- coding: utf-8 -*-
"""Behavioral regressions for architecture contracts and causal attribution."""
import copy
import unittest
import test_validation as _support


class ArchitectureTests(unittest.TestCase):
    setUp = _support.ValidationTests.setUp
    run_checker = _support.ValidationTests.run_checker
    def test_same_interface_does_not_merge_parts(self):
        for key in ('io_in', 'io_out', 'invariant'):
            self.data['parts'][1][key] = self.data['parts'][0][key]
        rc, result, _ = self.run_checker(self.data)
        self.assertEqual(rc, 0, result)
        self.assertEqual(result['warnings'], [])

    def test_no_load_bearing_is_not_a_rejection(self):
        for part in self.data['parts']:
            part['load_bearing'] = False
        rc, result, _ = self.run_checker(self.data)
        self.assertEqual(rc, 0, result)
        self.assertEqual(result['warnings'], [])

    def test_non_dominant_target_with_rationale_is_valid(self):
        self.data['proposals'][0].update(targets_part='E3', affected_parts=['E3'],
            contribution_rationale='Test activation smoothness for second derivatives')
        rc, result, _ = self.run_checker(self.data)
        self.assertEqual(rc, 0, result)
        self.assertEqual(result['warnings'], [])

    def test_port_dimension_mismatch_is_rejected(self):
        self.data['dataflow']['ports'][1]['shape'] = [999, 3]
        self.assertNotEqual(self.run_checker(self.data)[0], 0)

    def test_unit_mismatch_is_rejected(self):
        self.data['dataflow']['ports'][1]['unit'] = 'kelvin'
        self.assertNotEqual(self.run_checker(self.data)[0], 0)

    def test_axis_semantics_mismatch_is_rejected(self):
        self.data['dataflow']['ports'][1]['axes'] = ['feature', 'sample']
        self.assertNotEqual(self.run_checker(self.data)[0], 0)

    def test_unknown_edge_endpoint_is_rejected(self):
        self.data['dataflow']['edges'][0]['target'] = 'port:missing'
        self.assertNotEqual(self.run_checker(self.data)[0], 0)

    def test_required_input_must_be_connected(self):
        self.data['dataflow']['edges'].pop(0)
        self.assertNotEqual(self.run_checker(self.data)[0], 0)

    def test_duplicate_port_is_rejected(self):
        self.data['dataflow']['ports'].append(copy.deepcopy(self.data['dataflow']['ports'][0]))
        self.assertNotEqual(self.run_checker(self.data)[0], 0)

    def test_data_cycle_rejected_but_delayed_state_allowed(self):
        graph = self.data['dataflow']
        graph['edges'].append({'id':'edge:cycle','source':'R2:out','target':'R1:in','kind':'data','delay':0})
        self.assertNotEqual(self.run_checker(self.data)[0], 0)
        graph['edges'].pop()
        graph['ports'] += [dict(graph['ports'][0], id='R1:state-in', owner='R1', direction='input', state='hidden'),
                           dict(graph['ports'][0], id='R2:state-out', owner='R2', direction='output', state='hidden')]
        graph['edges'].append({'id':'edge:state','source':'R2:state-out','target':'R1:state-in','kind':'state','delay':1})
        rc, result, _ = self.run_checker(self.data)
        self.assertEqual(rc, 0, result)
        graph['edges'][-1]['delay'] = 0
        self.assertNotEqual(self.run_checker(self.data)[0], 0)

    def test_coupled_replacement_cannot_claim_independence(self):
        self.data['dataflow']['coupled_replacements'] = [{'id':'coupled:one','parts':['M2','E1'],'reason':'synthetic coupled contract'}]
        self.assertNotEqual(self.run_checker(self.data)[0], 0)
        for proposal in self.data['proposals']:
            proposal.update(affected_parts=['M2','E1'], replacement_scope='coupled')
        self.assertEqual(self.run_checker(self.data)[0], 0)

    def test_shared_parameter_change_covers_all_owners(self):
        self.data['dataflow']['shared_parameters'] = [{'id':'param:shared','parts':['M2','E1'],'description':'shared projection'}]
        self.data['proposals'][0]['changes_shared_parameters'] = ['param:shared']
        self.assertNotEqual(self.run_checker(self.data)[0], 0)

    def test_equivalence_needs_evidence(self):
        assessment = self.data['parts'][0]['swap_assessments'][0]
        assessment.update(relation='behaviorally_equivalent', evidence_claim_ids=[])
        self.assertNotEqual(self.run_checker(self.data)[0], 0)

    def test_unknown_importance_is_allowed(self):
        for part in self.data['parts']:
            part['load_bearing'] = False
            part['importance'] = {'claimed_centrality':{'status':'unknown','claim_ids':[]},
                'theoretical_dependency':{'status':'unknown','claim_ids':[]},
                'ablation_ids':[], 'interaction_ids':[]}
        rc, result, _ = self.run_checker(self.data)
        self.assertEqual(rc, 0, result)
        self.assertEqual(result['warnings'], [])

    def test_abstract_mention_does_not_prove_causal_effect(self):
        part = self.data['parts'][0]
        part['importance']['causal_status'] = 'established'
        self.assertNotEqual(self.run_checker(self.data)[0], 0)

    def test_ablation_requires_control_metadata(self):
        self.data['ablations'][0]['controls'].pop('training_budget')
        self.assertNotEqual(self.run_checker(self.data)[0], 0)

    def test_ablation_metric_must_resolve(self):
        self.data['ablations'][0]['metric_id'] = 'missing-metric'
        self.assertNotEqual(self.run_checker(self.data)[0], 0)

    def test_confounded_ablation_cannot_be_causal(self):
        ablation = self.data['ablations'][0]
        ablation['attribution'] = 'controlled_comparison'
        ablation['controls']['training_budget'] = 'unmatched'
        self.assertNotEqual(self.run_checker(self.data)[0], 0)

    def test_graph_mutation_invalidates_receipt(self):
        self.data['dataflow']['ports'][0]['unit'] = 'changed'
        self.assertNotEqual(self.run_checker(self.data, refresh_receipts=False)[0], 0)

    def test_controlled_comparison_accepts_complete_metadata(self):
        ablation = self.data['ablations'][0]
        ablation['controls'] = {k:'matched' for k in ablation['controls']}
        ablation.update(retraining='yes', seeds=[0, 1], attribution='controlled_comparison')
        rc, result, _ = self.run_checker(self.data)
        self.assertEqual(rc, 0, result)

    def test_claimed_centrality_needs_evidence(self):
        self.data['parts'][0]['importance']['claimed_centrality'] = {'status':'documented','claim_ids':[]}
        self.assertNotEqual(self.run_checker(self.data)[0], 0)

    def test_multi_part_ablation_needs_measurements_for_each_part(self):
        self.data['ablations'][0]['part_ids'].append('M2')
        self.assertNotEqual(self.run_checker(self.data)[0], 0)

    def test_multiple_producers_need_explicit_merge(self):
        self.data['dataflow']['edges'].append({'id':'edge:duplicate-producer','source':'R1:out','target':'R2:in','kind':'data','delay':0})
        self.assertNotEqual(self.run_checker(self.data)[0], 0)

    def test_dtype_measure_and_state_mismatch(self):
        for key, value in [('dtype','float64'),('measure','Lebesgue'),('state','hidden')]:
            with self.subTest(key=key):
                data = copy.deepcopy(self.data)
                data['dataflow']['ports'][1][key] = value
                self.assertNotEqual(self.run_checker(data)[0], 0)

    def test_unknown_parts_and_empty_node_coverage(self):
        self.data['dataflow']['bindings'].pop()
        self.assertNotEqual(self.run_checker(self.data)[0], 0)

    def test_swap_equivalence_accepts_recorded_derivation_only(self):
        claim = copy.deepcopy(self.data['claims'][0])
        claim.update(claim_id='claim:r1-equivalence', claim_type='derivation', predicate='conditional_equivalence', object='Synthetic conditional equivalence proof example')
        self.data['claims'].append(claim)
        part = self.data['parts'][0]
        part['claim_ids'].append(claim['claim_id'])
        part['swap_assessments'][0].update(relation='behaviorally_equivalent', evidence_claim_ids=[claim['claim_id']])
        rc, result, _ = self.run_checker(self.data)
        self.assertEqual(rc, 0, result)

    def test_shared_parameter_group_accepts_all_owners(self):
        self.data['dataflow']['shared_parameters'] = [{'id':'param:shared','parts':['M2','E1'],'description':'shared projection'}]
        self.data['proposals'][0].update(affected_parts=['M2','E1'],replacement_scope='coupled',changes_shared_parameters=['param:shared'])
        rc, result, _ = self.run_checker(self.data)
        self.assertEqual(rc, 0, result)

    def test_pairwise_interaction_checks_baseline_and_contrast(self):
        base = self.data['ablations'][0]
        claim = copy.deepcopy(self.data['claims'][-1])
        claim.update(claim_id='claim:m2-measure', subject='M2')
        self.data['claims'].append(claim)
        next(p for p in self.data['parts'] if p['id']=='M2')['claim_ids'].append(claim['claim_id'])
        b = copy.deepcopy(base)
        b.update(id='ablation:m2', part_ids=['M2'], evidence_claim_ids=['claim:m2-measure'])
        joint = copy.deepcopy(base)
        joint.update(id='ablation:joint', part_ids=['R2','M2'], evidence_claim_ids=['claim:r2-measure','claim:m2-measure'])
        self.data['ablations'] += [b, joint]
        self.data['interactions'] = [{'id':'interaction:r2-m2','part_ids':['R2','M2'],'metric_id':base['metric_id'],
            'ablation_ids':[base['id'],b['id'],joint['id']], 'contrast':-0.1,'confidence_interval':[-1,1], 'attribution':'associational'}]
        next(p for p in self.data['parts'] if p['id']=='R2')['importance']['interaction_ids']=['interaction:r2-m2']
        rc, result, _ = self.run_checker(self.data)
        self.assertEqual(rc, 0, result)
        self.data['interactions'][0]['contrast'] = 0.7
        self.assertNotEqual(self.run_checker(self.data)[0], 0)
        self.data['interactions'][0]['contrast'] = -0.1
        joint['control_id'] = 'other-control'
        self.assertNotEqual(self.run_checker(self.data)[0], 0)

    def test_v20_migration_marks_new_knowledge_missing(self):
        from migrate_anatomy import migrate
        old = copy.deepcopy(self.data)
        old['schema_version'] = '2.0.0'
        for key in ('dataflow','ablations','interactions'):
            old.pop(key)
        for part in old['parts']:
            part.pop('importance', None)
            part.pop('swap_assessments', None)
        migrated = migrate(old)
        self.assertEqual(migrated['schema_version'], _support.checker.ONTOLOGY_VERSION)
        self.assertEqual(migrated['dataflow']['node_parts'], [])
        self.assertEqual(migrated['ablations'], [])
        self.assertEqual(migrated['stage']['stage_status'], 'blocked')
        self.assertTrue(migrated['stage']['blocking_items'])
        for part in migrated['parts']:
            self.assertEqual(part['importance']['claimed_centrality']['status'], 'unknown')
        self.assertNotEqual(self.run_checker(migrated)[0], 0)

    def test_report_exposes_graph_and_importance_before_raw_snapshot(self):
        from render_report import render
        text = render(self.data)
        body = text.split('### 完整数据快照')[0]
        self.assertIn('R1:out', body)
        self.assertIn('claimed_centrality', body)
        self.assertIn('ablation:r2', body)
        self.assertIn('controlled_comparison', render(dict(self.data, ablations=[dict(self.data['ablations'][0],attribution='controlled_comparison')])).split('### 完整数据快照')[0])

    def test_unused_internal_output_is_rejected(self):
        port = copy.deepcopy(self.data['dataflow']['ports'][0])
        port['id'] = 'R1:dead-output'
        self.data['dataflow']['ports'].append(port)
        self.assertNotEqual(self.run_checker(self.data)[0], 0)

    def test_nonfinite_interaction_is_rejected(self):
        # Schema accepts JSON numbers; semantic validation must reject NaN/Infinity.
        self.data['ablations'][0]['effect'] = {'delta':float('nan'),'confidence_interval':[float('-inf'),float('inf')]}
        self.assertNotEqual(self.run_checker(self.data)[0], 0)
