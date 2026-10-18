# -*- coding: utf-8 -*-
import copy,hashlib,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))

class EvaluationProvenanceTests(unittest.TestCase):
    def cases(self):return [{'id':'explicit_expected_answer_hint','kind':'citation','claim':'Only A improved','material':'A improved; other datasets were not tested'}]
    def test_prepare_uses_opaque_ids_and_no_gold(self):
        from review_evaluation import prepare_session
        session,key=prepare_session(self.cases())
        self.assertNotEqual(session['tasks'][0]['id'],self.cases()[0]['id'])
        self.assertNotIn('gold',session)
        self.assertEqual(key['mapping'][session['tasks'][0]['id']],'explicit_expected_answer_hint')
    def test_inference_does_not_receive_key_and_wrong_echo_is_rejected(self):
        from review_evaluation import run_evaluation
        seen=[]
        def reviewer(request):
            seen.append(request)
            return {'case_id':'wrong','input_hash':'a'*64,'verdict':'supported','rationale':'Wrong binding'}
        with self.assertRaises(ValueError):run_evaluation(self.cases(),reviewer,{'backend':'host','identity':'unit test','model':'test'},'r1',prior_exposure='known')
        self.assertNotIn('mapping',seen[0])
    def test_unverified_rows_are_not_model_accuracy(self):
        from review_evaluation import prepare_cases,score_document
        cases=prepare_cases(self.cases());case=cases[0]
        rows=[{'case_id':case['id'],'input_hash':case['input_hash'],'verdict':'supported','rationale':'Scope matched','run_id':'r1'}]
        result=score_document(cases,{case['id']:{'verdict':'supported'}},{'predictions':rows,'evidence_type':'simulation'})
        self.assertFalse(result['model_accuracy_measured'])
    def test_host_run_raw_responses_bound_and_prior_exposure_reported(self):
        from review_evaluation import run_evaluation,prepare_cases,score_document
        def reviewer(request):
            task=request['task'];return {'case_id':task['id'],'input_hash':task['input_hash'],'verdict':'supported','rationale':'Claim matches the bounded source'}
        doc=run_evaluation(self.cases(),reviewer,{'backend':'host','identity':'unit test','model':'test'},'r1',prior_exposure='known')
        result=score_document(prepare_cases(self.cases()),{'explicit_expected_answer_hint':{'verdict':'supported'}},doc)
        self.assertTrue(result['model_accuracy_measured'])
        self.assertFalse(result['independent_blind_estimate'])
        doc['receipts'][0]['response']['verdict']='contradicted'
        with self.assertRaises(ValueError):score_document(prepare_cases(self.cases()),{'explicit_expected_answer_hint':{'verdict':'supported'}},doc)

    def test_nested_answer_keys_do_not_reach_inference(self):
        from review_evaluation import prepare_session
        cases=self.cases();cases[0]['metadata']={'gold':{'verdict':'supported'}}
        with self.assertRaises(ValueError):prepare_session(cases)

class ReceiptReplayTests(unittest.TestCase):
    def receipt(self):
        from test_v24_execution_eval import ExperimentTests
        from experiment_runner import run_experiment
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        root=Path(tmp.name);return run_experiment(ExperimentTests().prepare(root),root,True)
    def test_actual_receipt_replays(self):
        from experiment_runner import replay_receipt
        result=replay_receipt(self.receipt());self.assertEqual(result['status'],'passed');self.assertEqual(result['comparisons_completed'],2)
    def test_passed_field_cannot_hide_wrong_output(self):
        from experiment_runner import replay_receipt
        record=self.receipt();record['observations'][0]['responses']['candidate']['value']['gradients']=[999]
        with self.assertRaises(ValueError):replay_receipt(record)
    def test_missing_and_duplicate_observations_fail(self):
        from experiment_runner import replay_receipt
        for duplicate in (False,True):
            record=self.receipt()
            if duplicate:record['observations'][1]=copy.deepcopy(record['observations'][0])
            else:record['observations'].pop()
            if duplicate:
                with self.assertRaises(ValueError):replay_receipt(record)
            else:self.assertEqual(replay_receipt(record)['status'],'failed')

class MathBindingTests(unittest.TestCase):
    def target(self):
        return {'id':'theory:one','statement':'For real x, x+x=2*x','formal_statement':{
            'natural_statement':'For real x, x+x=2*x','semantics':'real_scalar','quantifier':'forall','relation':'equals',
            'variables':[{'symbol':'x','meaning':'real scalar input','type':'real_scalar'}],
            'nonzero':[],'lhs':'x+x','rhs':'2*x'}}
    def test_same_equation_different_target_does_not_bind(self):
        from math_binding import make_binding,validate_binding
        target=self.target();check={'id':'c1','target_id':'theory:one','case':{'variables':['x'],'lhs':'x+x','rhs':'2*x','nonzero':[]}}
        check['binding']=make_binding(check,target);validate_binding(check,target)
        target['statement']='All neural architectures are equivalent'
        with self.assertRaises(ValueError):validate_binding(check,target)
    def test_irrelevant_identity_domain_or_operator_cannot_bind(self):
        from math_binding import make_binding
        for field,value in [('lhs','x'),('nonzero',['x']),('semantics','floating_point')]:
            case={'variables':['x'],'lhs':'x+x','rhs':'2*x','nonzero':[]};case[field]=value
            with self.assertRaises(ValueError):make_binding({'id':'c1','target_id':'theory:one','case':case},self.target())

class CounterevidenceTests(unittest.TestCase):
    def data(self):return {'claims':[{'claim_id':'claim:A','predicate':'improves','object':'accuracy','subject':'part:A'}],'parts':[]}
    def plan(self):return {'target_id':'claim:A','rationale':'Look for failed replications and boundary conditions',
        'queries':[{'provider':'crossref','intent':'failure','query':'method A failure replication'}]}
    def test_search_failure_is_unavailable_not_negative_evidence(self):
        import counterevidence
        from unittest.mock import patch
        with patch.object(counterevidence,'fetch',return_value={'ok':False,'error':'HTTP 429','status':429}):
            result=counterevidence.search(self.plan(),self.data())
        self.assertEqual(result['status'],'unavailable');self.assertEqual(result['candidates'],[])
    def test_opposing_label_requires_verified_source(self):
        from counterevidence import validate_assessments,digest
        search={'id':'search:1','input_hash':'a'*64,'candidates':[{'id':'doi:10.1/test','title':'A study'}]}
        review={'search_hash':'a'*64,'reviewer':{'identity':'test','model':'test'},'reviewed_at':'2026-10-17T00:00:00Z',
                'assessments':[{'candidate_id':'doi:10.1/test','classification':'opposing','rationale':'Opposite result','evidence':[]}]}
        with self.assertRaises(ValueError):validate_assessments(search,review,self.data(),Path('.'))
    def test_search_plan_must_state_an_adversarial_intent(self):
        from counterevidence import search
        plan=self.plan();plan['queries'][0]['intent']='supporting'
        with self.assertRaises(ValueError):search(plan,self.data())

    def test_original_source_counterevidence_enters_task_and_obligations(self):
        import counterevidence
        from semantic_review import build_tasks
        from unittest.mock import patch
        data=self.data();data['claims'][0].update(claim_type='paper_fact',evidence=[])
        raw=json.dumps({'message':{'items':[{'DOI':'10.1234/opposition','title':['Failed method A replication']}]}})
        def transport(url):return {'ok':True,'url':url,'observed_at':'2026-10-17T00:00:00Z','raw_text':raw,
            'response_sha256':hashlib.sha256(raw.encode()).hexdigest()}
        with patch.object(counterevidence,'fetch',side_effect=transport):result=counterevidence.search(self.plan(),data)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);body=b'Method A failed on the stated benchmark.';(root/'source.txt').write_bytes(body);sha=hashlib.sha256(body).hexdigest()
            data['sources']=[{'id':'opponent','kind':'publication','ref':'doi:10.1234/opposition'}]
            data['evidence_snapshots']=[{'id':'snap:opponent','source_id':'opponent','source_version':'v1',
                'original_path':'source.txt','text_path':'source.txt','original_sha256':sha,'text_sha256':sha,
                'extraction':{'tool':'test','version':'1','retrieved_at':'2026-10-17T00:00:00Z'}}]
            evidence={'source_id':'opponent','snapshot_id':'snap:opponent','quote':body.decode(),'content_hash':sha,'span':{'start':0,'end':len(body)}}
            result['review']={'search_hash':result['input_hash'],'reviewer':{'identity':'test','model':'test'},'reviewed_at':'2026-10-17T00:00:00Z',
                'assessments':[{'candidate_id':'doi:10.1234/opposition','classification':'opposing','rationale':'Direct failure on this benchmark','evidence':[evidence]}]}
            data['counterevidence_searches']=[result]
            counterevidence.validate_assessments(result,result['review'],data,root)
            task=build_tasks(data,root)[0]
            self.assertEqual(task['payload']['evidence'][0]['classification'],'opposing')
            self.assertTrue(any(o.startswith('counterevidence:') for o in task['obligation_ids']))
            old_hash=task['input_hash'];result['review']['assessments'][0]['rationale']='Condition-specific failure, not universal impossibility'
            self.assertNotEqual(old_hash,build_tasks(data,root)[0]['input_hash'])

class StrongReplayTests(unittest.TestCase):
    def test_rehashed_wrong_values_are_recomputed_as_failure(self):
        from experiment_runner import replay_receipt
        record=ReceiptReplayTests.receipt(self)
        response=record['observations'][0]['responses']['candidate'];response['value']['gradients']=[123]
        response['raw_json']=json.dumps(response['value']);response['response_sha256']=hashlib.sha256(response['raw_json'].encode()).hexdigest()
        replay=replay_receipt(record)
        self.assertEqual(replay['status'],'failed')
        self.assertTrue(any('gradients' in e for e in replay['errors']))

if __name__=='__main__':unittest.main()


class RobustnessRegressionTests(unittest.TestCase):
    def test_context_filters_stale_graph_part_references(self):
        from architecture_context import review_context
        data={'parts':[{'id':'M2'}], 'interface_contract':{}, 'dataflow':{
            'node_parts':['M2','STALE'],
            'ports':[{'id':'M2:out','owner':'M2'},{'id':'STALE:in','owner':'STALE'}],
            'edges':[{'source':'M2:out','target':'STALE:in'}],
            'bindings':[{'part_id':'STALE','node_parts':['M2']}],
            'shared_parameters':[], 'coupled_replacements':[]}}
        result=review_context(data,{'part_id':'M2'})
        self.assertEqual([p['id'] for p in result['parts']],['M2'])
        self.assertEqual(result['dataflow']['node_parts'],['M2'])
        self.assertEqual(result['dataflow']['bindings'],[])
