# -*- coding: utf-8 -*-
import hashlib,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))

class ExperimentTests(unittest.TestCase):
    def prepare(self,root,candidate_body=None):
        reference="import json,sys\nx=json.load(sys.stdin)['x']\njson.dump({'outputs':[x*2], 'state':x*2, 'gradients':[2]},sys.stdout)\n"
        candidate=candidate_body or reference.replace('x*2','x+x')
        for name,body in [('reference.py',reference),('candidate.py',candidate)]: (root/name).write_bytes(body.encode())
        def adapter(path):return {'path':path,'sha256':hashlib.sha256((root/path).read_bytes()).hexdigest(),'dependencies':[]}
        return {'id':'experiment:one','target_id':'proposal:one','target_snapshot_hash':'a'*64,
            'reference':adapter('reference.py'),'candidate':adapter('candidate.py'),
            'cases':[{'id':'zero','input':{'x':0},'checks':['outputs','state','gradients']},
                     {'id':'positive','input':{'x':3},'checks':['outputs','state','gradients']}],
            'atol':1e-8,'rtol':1e-8,'timeout_seconds':2,'repetitions':1}
    def test_requires_explicit_execution_flag(self):
        from experiment_runner import run_experiment
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);spec=self.prepare(root)
            self.assertEqual(run_experiment(spec,root,execute=False)['status'],'planned')
    def test_actual_adapters_compare_outputs_state_and_gradient(self):
        from experiment_runner import run_experiment
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);result=run_experiment(self.prepare(root),root,execute=True)
            self.assertEqual(result['status'],'passed')
            self.assertEqual(result['comparisons_completed'],2)
    def test_wrong_gradient_is_detected(self):
        from experiment_runner import run_experiment
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);spec=self.prepare(root,"import json,sys\nx=json.load(sys.stdin)['x']\njson.dump({'outputs':[x*2], 'state':x*2, 'gradients':[0]},sys.stdout)\n")
            result=run_experiment(spec,root,execute=True)
            self.assertEqual(result['status'],'failed')
            self.assertTrue(any('gradients' in e for e in result['errors']))
    def test_stale_adapter_hash_is_rejected(self):
        from experiment_runner import run_experiment
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);spec=self.prepare(root);(root/'candidate.py').write_bytes(b'print(0)')
            with self.assertRaises(ValueError):run_experiment(spec,root,execute=True)
    def test_timeout_is_a_failure_not_equivalence(self):
        from experiment_runner import run_experiment
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);spec=self.prepare(root,'while True: pass\n');spec['timeout_seconds']=0.15
            self.assertEqual(run_experiment(spec,root,execute=True)['status'],'failed')

class EvaluationTests(unittest.TestCase):
    def test_unsafe_acceptance_and_abstention_denominators(self):
        from review_evaluation import score
        cases=[{'id':'a','input_hash':'a'*64},{'id':'b','input_hash':'b'*64},{'id':'c','input_hash':'c'*64}]
        gold={'a':{'verdict':'supported'},'b':{'verdict':'partial'},'c':{'verdict':'insufficient'}}
        predictions=[{'case_id':'a','input_hash':'a'*64,'verdict':'supported','run_id':'r1','rationale':'Scope matches'},
          {'case_id':'b','input_hash':'b'*64,'verdict':'supported','run_id':'r1','rationale':'Overconfident response'},
          {'case_id':'c','input_hash':'c'*64,'verdict':'insufficient','run_id':'r1','rationale':'Missing material'}]
        result=score(cases,gold,predictions)
        self.assertEqual(result['unsafe_acceptance_rate'],0.5)
        self.assertEqual(result['appropriate_abstention_rate'],1.0)
        self.assertEqual(result['exact_accuracy'],2/3)
    def test_missing_cases_are_not_silent_success(self):
        from review_evaluation import score
        with self.assertRaises(ValueError):score([{'id':'a','input_hash':'a'*64}],{'a':{'verdict':'supported'}},[])
    def test_prediction_hash_and_repeated_run_consistency(self):
        from review_evaluation import score
        cases=[{'id':'a','input_hash':'a'*64}];gold={'a':{'verdict':'partial'}}
        rows=[{'case_id':'a','input_hash':'a'*64,'verdict':'partial','run_id':'r1','rationale':'Bounded'},
              {'case_id':'a','input_hash':'a'*64,'verdict':'supported','run_id':'r2','rationale':'Different judgment'}]
        result=score(cases,gold,rows);self.assertEqual(result['repeat_agreement'],0.0)
        rows[0]['input_hash']='b'*64
        with self.assertRaises(ValueError):score(cases,gold,rows)

if __name__=='__main__':unittest.main()
