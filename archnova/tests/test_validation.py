import copy
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import check_anatomy as checker
from validation_core import stage_digest, STAGE_FIELDS


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / 'assets/anatomy.fixture.json').read_text(encoding='utf-8'))

    def run_checker(self, data, *args, **kwargs):
        data = copy.deepcopy(data)
        if kwargs.get('refresh_receipts', True) and 'stage' in data and isinstance(data['stage'], dict):
            data['stage']['receipts'] = [{'stage': sid, 'status': 'passed', 'digest': stage_digest(data, sid)} for sid in STAGE_FIELDS]

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'anatomy.json'
            path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
            out = io.StringIO()
            with patch.object(checker, 'verify_refs') as network, contextlib.redirect_stdout(out):
                rc = checker.main([str(path), '--json'] + list(args))
            return rc, json.loads(out.getvalue()), network.call_count

    def test_fixture_passes(self):
        self.assertEqual(self.run_checker(self.data)[0], 0)

    def test_invalid_stage(self):
        self.data['stage']['stage'] = 'G999'
        self.assertNotEqual(self.run_checker(self.data)[0], 0)

    def test_release_requires_terminal_stage(self):
        self.data['stage']['stage'] = 'G0'
        rep = checker.Report()
        checker.check_stage(self.data, rep, release=True)
        self.assertTrue(rep.errors)

    def test_claim_subject_must_exist(self):
        self.data['claims'][0]['subject'] = 'nonexistent-part'
        self.assertNotEqual(self.run_checker(self.data)[0], 0)

    def test_claim_subject_must_match_part(self):
        self.data['parts'][0]['claim_ids'] = self.data['parts'][1]['claim_ids']
        self.assertNotEqual(self.run_checker(self.data)[0], 0)

    def test_source_must_exist(self):
        self.data['claims'][0]['evidence'][0]['source_id'] = 'fake:missing-source'
        self.assertNotEqual(self.run_checker(self.data)[0], 0)

    def test_f_requires_primary_source(self):
        primary = self.data['paper'].get('source_id')
        if primary:
            other = next(s['id'] for s in self.data['sources'] if s['id'] != primary)
        else:
            other = 'arXiv:2108.08481'
        self.data['claims'][0]['evidence'][0]['source_id'] = other
        self.assertNotEqual(self.run_checker(self.data)[0], 0)

    def test_no_cost_dominant_parts(self):
        for part in self.data['parts']:
            part['cost_dominant'] = False
        self.data['cost_model']['dominant_term'] = 'bogus'
        self.assertNotEqual(self.run_checker(self.data)[0], 0)

    def test_metric_direction_enum(self):
        self.data['metrics'][0]['direction'] = 'nonsense'
        self.assertNotEqual(self.run_checker(self.data)[0], 0)

    def test_refs_cover_primary_downstream_claims(self):
        source = self.data['sources'][0]
        source.update(kind='publication', ref='arXiv:1706.03762')
        paths = [p for p, _, _ in checker.collect_refs(self.data)]
        self.assertTrue(any(p.startswith('paper') for p in paths))
        self.assertTrue(any(p.startswith('downstream') for p in paths))
        self.assertTrue(any(p.startswith('claims') for p in paths))

    def test_v1_requires_explicit_legacy_mode(self):
        self.data.pop('schema_version', None)
        self.assertNotEqual(self.run_checker(self.data)[0], 0)

    def test_legacy_cannot_release(self):
        self.data.pop('schema_version', None)
        rc, _, calls = self.run_checker(self.data, '--legacy', '--release')
        self.assertNotEqual(rc, 0)
        self.assertEqual(calls, 0)

    def test_stage_receipt_cannot_be_stale(self):
        self.data['parts'][0]['name'] += ' changed'
        self.assertNotEqual(self.run_checker(self.data, refresh_receipts=False)[0], 0)

    def test_invalid_input_types_are_errors_not_tracebacks(self):
        for field in ['parts', 'claims', 'metrics', 'stage']:
            with self.subTest(field=field):
                data = copy.deepcopy(self.data)
                data[field] = [None, 3, []]
                self.assertNotEqual(self.run_checker(data)[0], 0)

    def test_synthetic_cannot_release(self):
        rc, _, calls = self.run_checker(self.data, '--release')
        self.assertNotEqual(rc, 0)
        self.assertEqual(calls, 0)

    def test_schema_validator_and_python_agree(self):
        from validation_core import schema_check
        rep = checker.Report()
        self.assertTrue(schema_check(self.data, rep), rep.errors)

    def test_part_slot_and_group_agree(self):
        self.data['parts'][0]['slot'] = 'M2'
        self.assertNotEqual(self.run_checker(self.data)[0], 0)

    def test_dominant_ids_are_exact(self):
        self.data['cost_model']['dominant_part_ids'] = ['M20']
        self.assertNotEqual(self.run_checker(self.data)[0], 0)

    def test_missing_claim_ids_is_error(self):
        self.data['parts'][0].pop('claim_ids')
        self.assertNotEqual(self.run_checker(self.data)[0], 0)

    def test_empty_f_claim_ids_is_error(self):
        self.data['parts'][0]['claim_ids'] = []
        self.assertNotEqual(self.run_checker(self.data)[0], 0)

    def test_gap_reference_requires_exact_id(self):
        self.data['upstream'][0]['fills_gap'] = self.data['gaps'][0]['item']
        self.assertNotEqual(self.run_checker(self.data)[0], 0)

    def test_missing_dependency_receipt(self):
        self.data['stage']['receipts'].pop(0)
        self.assertNotEqual(self.run_checker(self.data, refresh_receipts=False)[0], 0)

    def test_changed_report_rejected(self):
        from render_report import render
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / 'report.md'
            report.write_text(render(self.data) + '\nInjected claim', encoding='utf-8')
            self.assertNotEqual(self.run_checker(self.data, '--report', str(report))[0], 0)

    def test_generated_report_passes(self):
        from render_report import render
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / 'report.md'
            report.write_text(render(self.data), encoding='utf-8')
            rc, result, _ = self.run_checker(self.data, '--report', str(report))
            self.assertEqual(rc, 0, result)
            self.assertEqual(result['warnings'], [])

    def test_render_preserves_evidence_and_cost(self):
        from render_report import render
        text = render(self.data)
        self.assertIn(self.data['claims'][0]['claim_id'], text)
        self.assertIn(self.data['cost_model']['flops_per_unit'], text)
        self.assertIn(self.data['metrics'][0]['definition'], text)
        self.assertEqual(text, render(copy.deepcopy(self.data)))

    def test_explicit_legacy_warns(self):
        self.data.pop('schema_version')
        rc, result, _ = self.run_checker(self.data, '--legacy')
        self.assertEqual(rc, 0, result)
        self.assertTrue(result['warnings'])


    def test_migration_does_not_invent_evidence(self):
        from migrate_anatomy import migrate
        legacy = copy.deepcopy(self.data)
        for key in ('schema_version', 'claims', 'sources', 'metrics', 'stage'):
            legacy.pop(key, None)
        migrated = migrate(legacy)
        self.assertNotIn('schema_version', legacy)
        self.assertEqual(migrated['schema_version'], checker.ONTOLOGY_VERSION)
        self.assertEqual(migrated['claims'], [])
        self.assertEqual(migrated['stage']['stage_status'], 'blocked')
        self.assertEqual(migrated['stage']['receipts'], [])
        self.assertTrue(migrated['stage']['blocking_items'])
        self.assertNotEqual(self.run_checker(migrated)[0], 0)

    def test_checkpoint_validates_before_stamp(self):
        from checkpoint_anatomy import finalize
        bad = copy.deepcopy(self.data)
        bad['parts'][0]['claim_ids'] = ['claim:missing']
        finalized, result = finalize(bad)
        self.assertIsNone(finalized)
        self.assertFalse(result['passed'])
        self.assertEqual(bad['parts'][0]['claim_ids'], ['claim:missing'])
        good = copy.deepcopy(self.data)
        good['stage'] = {'stage': 'G0', 'stage_status': 'pending', 'blocking_items': [], 'receipts': []}
        finalized, result = finalize(good)
        self.assertTrue(result['passed'], result)
        self.assertEqual(finalized['stage']['stage'], 'G8')
        self.assertEqual(len(finalized['stage']['receipts']), 9)
        self.assertEqual(good['stage']['stage'], 'G0')

    def test_unknown_top_level_is_not_ignored(self):
        self.data['metricz'] = self.data.pop('metrics')
        self.assertNotEqual(self.run_checker(self.data)[0], 0)

    def test_bad_nested_types(self):
        for key in ('core_architecture', 'interface_contract'):
            data = copy.deepcopy(self.data)
            data[key] = {'evidence': ['bad']}
            self.assertNotEqual(self.run_checker(data)[0], 0)

    def test_release_needs_report(self):
        rc, result, _ = self.run_checker(self.data, '--release')
        self.assertTrue(any('--report' in error for error in result['errors']))


    def test_release_requires_publication_primary(self):
        self.data['sources'][0]['kind'] = 'local'
        from validation_core import check_graph
        rep = checker.Report()
        check_graph(self.data, rep, release=True)
        self.assertTrue(any('primary' in e.lower() for e in rep.errors))

    def test_release_network_error_fails(self):
        from render_report import render
        data = copy.deepcopy(self.data)
        for source in data['sources']:
            if source['kind'] == 'synthetic':
                source.update(kind='publication', ref='arXiv:1706.03762', title='Attention Is All You Need')
        data['paper']['ids'] = {'arxiv':'1706.03762'}
        data['paper']['title'] = 'Attention Is All You Need'
        for claim in data['claims']:
            for ev in claim['evidence']:
                ev.update(quote='test-only quotation', retrieved_at='2026-10-17T00:00:00Z', content_hash='a'*64)
        data['stage']['receipts'] = [{'stage': sid, 'status': 'passed', 'digest': stage_digest(data, sid)} for sid in STAGE_FIELDS]
        with tempfile.TemporaryDirectory() as tmp:
            path, report = Path(tmp) / 'anatomy.json', Path(tmp) / 'report.md'
            import hashlib
            content = b'test-only quotation'
            (Path(tmp) / 'original.txt').write_bytes(content)
            (Path(tmp) / 'text.txt').write_bytes(content)
            digest = hashlib.sha256(content).hexdigest()
            data['evidence_snapshots'] = []
            for source in data['sources']:
                if source['kind'] == 'publication':
                    data['evidence_snapshots'].append({'id':'snap:'+source['id'], 'source_id':source['id'],
                        'source_version':'test-only','original_path':'original.txt','original_sha256':digest,
                        'text_path':'text.txt','text_sha256':digest,
                        'extraction':{'tool':'test','version':'1','retrieved_at':'2026-10-17T00:00:00Z'}})
            for claim in data['claims']:
                for ev in claim['evidence']:
                    if any(s['source_id'] == ev['source_id'] for s in data['evidence_snapshots']):
                        ev.update(snapshot_id='snap:'+ev['source_id'],span={'start':0,'end':len(content)},content_hash=digest)
            # Complete the review transport contract using an explicitly test-only reviewer.
            # These records establish plumbing, not the truth of synthetic research claims.
            from semantic_review import build_tasks, run_reviews
            outline = {'statement':'Test-only identity x=x','domain':'Real x',
                'quantifiers':'For every real x','assumptions':[],
                'steps':[{'id':'step:reflexivity','statement':'x=x','justification':'Reflexivity','premise_ids':[]}],
                'evidence_claim_ids':[]}
            for target in data['claims'] + data['theory']:
                if target.get('claim_type') in ('derivation','theorem'):
                    target['proof_outline'] = copy.deepcopy(outline)
            for part in data['parts']:
                for swap in part.get('swap_assessments',[]):
                    if swap.get('relation') in ('behaviorally_equivalent','implementation_equivalent'):
                        swap['proof_outline'] = copy.deepcopy(outline)
            # Real counter-search normalization/coverage runs; only HTTP transport is stubbed.
            import counterevidence
            from proof_dependencies import target_registry
            import hashlib
            raw_counter = json.dumps({'message':{'items':[]}})
            def counter_transport(url):
                return {'ok':True,'url':url,'observed_at':'2026-10-17T00:00:00Z','raw_text':raw_counter,
                        'response_sha256':hashlib.sha256(raw_counter.encode('utf-8')).hexdigest()}
            needed=[key for key,target in target_registry(data) if target.get('claim_type') in ('paper_fact','upstream_fact','derivation','measurement','assumption','theorem')]
            needed += [p['id'] for p in data['proposals']]
            with patch.object(counterevidence,'fetch',side_effect=counter_transport):
                data['counterevidence_searches']=[counterevidence.search({'target_id':key,'rationale':'Test-only falsification transport coverage',
                    'queries':[{'provider':'crossref','intent':'failure','query':'test-only failed replication'}]},data) for key in needed]
            tasks = build_tasks(data, Path(tmp))
            def test_reviewer(task):
                return {'verdict':'supported','rationale':'Test-only review transport response',
                    'obligations':[{'id':oid,'status':'satisfied','reason':'Test transport stub'} for oid in task['obligation_ids']],
                    'evidence_ids':[e['id'] for e in task['payload'].get('evidence',[])],
                    'counterexample':None,'scope_limits':['Transport test only; no scientific endorsement']}
            review_result = run_reviews(tasks, test_reviewer,
                {'backend':'host','identity':'unit-test-stub','model':'unit-test'})
            self.assertEqual(review_result['errors'], [])
            data['semantic_reviews'] = review_result['reviews']
            data['publication']={'mode':'supported_conclusions','conclusions':[{'kind':r['kind'],'target_id':r['target_id'],'disposition':'endorsed','rationale':'Test-only contract response','conditions':[]} for r in data['semantic_reviews']]}
            from repository_coverage import target_hash
            data['repository_explorations']=[{'proposal_id':p['id'],'status':'skipped','reason':'Transport contract test; not a live research proposal','target_snapshot_hash':target_hash(data,p),'discovery_plan_hashes':[]} for p in data['proposals']]
            data['stage']['receipts'] = [{'stage':sid,'status':'passed','digest':stage_digest(data,sid)} for sid in STAGE_FIELDS]
            path.write_text(json.dumps(data), encoding='utf-8')
            report.write_text(render(data), encoding='utf-8')
            for title, expected in [('Attention Is All You Need', 0), (None, 1)]:
                out = io.StringIO()
                # Replace the remote transport only; schema, graph, report and reference collection execute.
                def resolve(ref):
                    return (title, 'test transport', 'test-url') if title is None else (next((t for _, r, t in checker.collect_refs(data) if r == ref and t), title), 'test transport', 'test-url')
                with patch.object(checker, 'resolve_ref', side_effect=resolve) as remote, contextlib.redirect_stdout(out):
                    rc = checker.main([str(path), '--release', '--report', str(report), '--json'])
                self.assertEqual(rc, expected, json.loads(out.getvalue()))
                self.assertTrue(remote.called)


    def test_reference_cache_rechecks_title_per_occurrence(self):
        data = copy.deepcopy(self.data)
        data['upstream'][1]['id'] = data['upstream'][0]['id']
        data['upstream'][1]['title'] = 'Completely unrelated made up title'
        rep = checker.Report()
        with patch.object(checker, 'resolve_ref', return_value=('Attention Is All You Need', 'test', 'test')):
            checker.verify_refs(data, rep)
        self.assertTrue(any('upstream[1]' in e for e in rep.errors))

    def test_package_contains_sources_and_matches_disk(self):
        from build_package import build
        import zipfile
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'test.skill'
            build(ROOT, target)
            with zipfile.ZipFile(str(target)) as archive:
                names = archive.namelist()
                for required in ['ontology.json', 'requirements.txt', 'scripts/validation_core.py', 'scripts/render_report.py', 'tests/test_validation.py']:
                    entry = ROOT.name + '/' + required
                    self.assertIn(entry, names)
                    self.assertEqual(archive.read(entry), (ROOT / required).read_bytes())
                self.assertFalse(any('__pycache__' in n or n.endswith('.pyc') for n in names))


    def test_checkpoint_preserves_unresolved_blockers(self):
        from checkpoint_anatomy import finalize
        self.data['stage'].update(stage_status='blocked', blocking_items=['Unresolved paper evidence'])
        result, report = finalize(self.data)
        self.assertIsNone(result)
        self.assertFalse(report['passed'])


    def test_theory_prefixed_arxiv_is_resolved(self):
        paths = [path for path, _, _ in checker.collect_refs(self.data)]
        self.assertTrue(any(path.startswith('theory') for path in paths))

    def test_upstream_fact_cannot_use_local_source_on_release(self):
        claim = next(c for c in self.data['claims'] if c['claim_type'] == 'upstream_fact')
        claim['evidence'][0]['source_id'] = 'self:derivation'
        from validation_core import check_graph
        rep = checker.Report()
        check_graph(self.data, rep, release=True)
        self.assertTrue(any('Publication evidence' in e for e in rep.errors))



if __name__ == '__main__':
    unittest.main()
