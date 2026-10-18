# -*- coding: utf-8 -*-
import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))

class ProofTests(unittest.TestCase):
    def test_rational_identity_is_checked_exactly(self):
        from proof_checks import check_identity
        result=check_identity({'variables':['x','y'],'lhs':'(x+y)**2','rhs':'x**2+2*x*y+y**2','nonzero':[]})
        self.assertEqual(result['status'],'verified_identity')
        self.assertEqual(result['scope'],'rational_expressions_over_reals')

    def test_cancellation_keeps_domain_restriction(self):
        from proof_checks import check_identity
        case={'variables':['x'],'lhs':'x/x','rhs':'1','nonzero':[]}
        self.assertEqual(check_identity(case)['status'],'conditional_identity')
        case['nonzero']=['x']
        self.assertEqual(check_identity(case)['status'],'verified_identity')

    def test_false_equivalence_has_checked_counterexample(self):
        from proof_checks import check_identity
        result=check_identity({'variables':['x'],'lhs':'x','rhs':'2*x','nonzero':[]})
        self.assertEqual(result['status'],'counterexample')
        self.assertNotEqual(result['counterexample']['lhs'],result['counterexample']['rhs'])

    def test_unsupported_theorem_is_not_declared_proved(self):
        from proof_checks import check_identity
        result=check_identity({'variables':['x'],'lhs':'sin(x)','rhs':'x','nonzero':[]})
        self.assertEqual(result['status'],'inconclusive')

    def test_invalid_domain_and_budget_are_rejected(self):
        from proof_checks import check_identity
        for case in [{'variables':['x'],'lhs':'x','rhs':'x','nonzero':['0']},
                     {'variables':['x'],'lhs':'(x+1)**100000','rhs':'0','nonzero':[]}]:
            self.assertNotEqual(check_identity(case)['status'],'verified_identity')

    def test_decimal_literals_are_not_rounded_before_exact_check(self):
        from proof_checks import check_identity
        result=check_identity({'variables':[],'lhs':'0.10000000000000001','rhs':'0.1','nonzero':[]})
        self.assertEqual(result['status'],'counterexample')

class SemanticTests(unittest.TestCase):
    def task(self):
        return {'kind':'citation','target_id':'claim:one','input_hash':'a'*64,
          'payload':{'claim':{'object':'Accuracy improved on every dataset'},'evidence':[{'id':'evidence:0','quote':'Improvement was measured on one dataset only.'}]},
          'obligation_ids':['scope','quantifiers','conditions','causality']}
    def review(self,task,verdict='supported'):
        return {'verdict':verdict,'rationale':'A concrete comparison of the claim with the quoted evidence.',
          'obligations':[{'id':key,'status':'satisfied','reason':'Checked against the source material.'} for key in task['obligation_ids']],
          'evidence_ids':['evidence:0'],'counterexample':None,'scope_limits':['Model review; not a formal proof']}
    def test_unresolved_obligation_cannot_support_claim(self):
        from semantic_review import validate_response
        task=self.task();result=self.review(task);result['obligations'][0]['status']='unknown'
        with self.assertRaises(ValueError):validate_response(task,result)
    def test_fabricated_evidence_reference_is_rejected(self):
        from semantic_review import validate_response
        task=self.task();result=self.review(task);result['evidence_ids']=['evidence:99']
        with self.assertRaises(ValueError):validate_response(task,result)
    def test_stale_review_does_not_apply_to_changed_input(self):
        from semantic_review import validate_record
        task=self.task();record=dict(self.review(task),kind='citation',target_id='claim:one',input_hash='b'*64,
          reviewer={'backend':'host','identity':'test-host','model':'test'},reviewed_at='2026-10-17T00:00:00Z')
        with self.assertRaises(ValueError):validate_record(task,record)
    def test_math_review_requires_complete_proof_obligations(self):
        from semantic_review import validate_response
        task={'kind':'mathematics','target_id':'theory:one','input_hash':'a'*64,
          'payload':{'proof_outline':{'steps':[{'id':'S1','statement':'S1'}]},'evidence':[],'machine_checks':[]},'obligation_ids':['A1','S1']}
        result=self.review(task);result['evidence_ids']=[];result['obligations']=result['obligations'][:1]
        with self.assertRaises(ValueError):validate_response(task,result)
    def test_machine_counterexample_overrules_positive_model_review(self):
        from semantic_review import validate_response
        task={'kind':'mathematics','target_id':'claim:one','input_hash':'a'*64,
          'payload':{'proof_outline':{'steps':[{'id':'S1','statement':'S1'}]},'evidence':[],
            'machine_checks':[{'id':'check:bad','result':{'status':'counterexample','counterexample':{'x':1}}}]},'obligation_ids':['S1']}
        result=self.review(task);result['evidence_ids']=[]
        with self.assertRaises(ValueError):validate_response(task,result)

    def test_supported_review_cannot_carry_a_counterexample(self):
        from semantic_review import validate_response
        task=self.task();result=self.review(task);result['counterexample']='A counterexample to the exact stated claim'
        with self.assertRaises(ValueError):validate_response(task,result)

    def test_missing_material_does_not_call_reviewer(self):
        from semantic_review import run_reviews
        task=self.task();task['payload']['material_issues']=['Missing verified snapshot']
        def forbidden(task):raise AssertionError('Missing material must not be sent for a positive review')
        result=run_reviews([task],forbidden,{'backend':'host','identity':'test','model':'test'})
        self.assertEqual(result['reviews'][0]['verdict'],'insufficient')

    def test_forward_proof_premise_is_unresolved(self):
        from semantic_review import proof_outline_issues
        outline={'statement':'Identity','domain':'reals','quantifiers':'all x','assumptions':[],
                 'steps':[{'id':'S1','statement':'x=x','justification':'S2','premise_ids':['S2']} ]}
        issues,ids=proof_outline_issues(outline,{})
        self.assertTrue(any('forward' in i for i in issues))

    def test_snapshot_and_claim_changes_invalidate_task_binding(self):
        import json,tempfile,hashlib
        from semantic_review import build_tasks
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);body=b'Only dataset A improved. Context.'
            (root/'source.txt').write_bytes(body)
            sha=hashlib.sha256(body).hexdigest()
            snapshot={'id':'snap:1','source_id':'source:1','source_version':'1','original_path':'source.txt','text_path':'source.txt',
                'original_sha256':sha,'text_sha256':sha,'extraction':{'tool':'test','version':'1','retrieved_at':'2026-10-17T00:00:00Z'}}
            data={'sources':[{'id':'source:1','kind':'synthetic'}],'evidence_snapshots':[snapshot],
                'claims':[{'claim_id':'claim:one','claim_type':'paper_fact','object':'Only dataset A improved.',
                 'evidence':[{'source_id':'source:1','snapshot_id':'snap:1','content_hash':sha,
                   'span':{'start':0,'end':len('Only dataset A improved.')},'quote':'Only dataset A improved.'}]}]}
            task=build_tasks(data,root)[0]
            self.assertEqual(task['payload']['material_issues'],[])
            data['claims'][0]['object']='Every dataset improved.'
            self.assertNotEqual(task['input_hash'],build_tasks(data,root)[0]['input_hash'])
            (root/'source.txt').write_bytes(b'Changed material')
            self.assertTrue(build_tasks(data,root)[0]['payload']['material_issues'])

    def test_apply_preserves_existing_blocking_items(self):
        import json,tempfile,contextlib,io
        from semantic_review import main
        data=json.loads((Path(__file__).resolve().parents[1]/'assets/anatomy.fixture.json').read_text(encoding='utf-8'))
        data['stage'].update(stage_status='blocked',blocking_items=['Missing experimental controls'])
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'input.json';target=root/'output.json';reviews=root/'reviews.json'
            source.write_text(json.dumps(data),encoding='utf-8');reviews.write_text('{"reviews":[]}',encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):rc=main(['apply',str(source),'--reviews',str(reviews),'-o',str(target)])
            self.assertEqual(rc,0)
            self.assertEqual(json.loads(target.read_text(encoding='utf-8'))['stage']['blocking_items'],['Missing experimental controls'])

    def test_math_review_binding_includes_interface(self):
        from semantic_review import build_tasks
        data={'claims':[{'claim_id':'claim:math','claim_type':'derivation','evidence':[]}],
              'interface_contract':{'input_object':'sequence'}}
        task=build_tasks(data,Path('.'))[0]
        data['interface_contract']['input_object']='unordered set'
        self.assertNotEqual(task['input_hash'],build_tasks(data,Path('.'))[0]['input_hash'])

    def test_optional_api_adapter_serializes_task_and_validates_json(self):
        from semantic_review import api_reviewer
        from unittest.mock import patch
        import json
        task=self.task();response=self.review(task)
        class Reply:
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self,n):return json.dumps({'choices':[{'message':{'content':json.dumps(response)}}]}).encode()
        with patch('semantic_review.urllib.request.urlopen',return_value=Reply()) as remote:
            result=api_reviewer('https://example.invalid/v1/chat/completions','test-model')(task)
        self.assertEqual(result['verdict'],'supported')
        body=json.loads(remote.call_args[0][0].data.decode())
        self.assertEqual(body['model'],'test-model')
        self.assertEqual(json.loads(body['messages'][1]['content'])['target_id'],task['target_id'])

if __name__=='__main__':unittest.main()
