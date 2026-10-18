import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from input_modes import build_mode, main
from orchestrator import atomic_write, build_batches, main as orchestrate

class InputModesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.paper = self.root/'paper.txt'; self.paper.write_text('A paper architecture', encoding='utf8')
        self.code = self.root/'repo'; self.code.mkdir()
        (self.code/'model.py').write_text('def forward(x): return x', encoding='utf8')

    def test_modes_and_content_bound_hashes(self):
        for mode,paper,code in [('paper-only',self.paper,None),('code-only',None,self.code),('paper-and-code',self.paper,self.code)]:
            a=build_mode(mode,paper,code); b=build_mode(mode,paper,code)
            self.assertEqual(a,b)
            roles=[t['role'] for t in a['tasks']]
            self.assertEqual('paper_code_aligner' in roles, bool(paper and code))
            self.assertIn('component_library_indexer',roles)
            self.assertIn('prototype_planner',roles)
            self.assertEqual(len(build_batches(a['tasks'])[0]),2 if paper and code else 1)
        a=build_mode('code-only',code=self.code)
        (self.code/'model.py').write_text('def forward(x): return x+x',encoding='utf8')
        b=build_mode('code-only',code=self.code)
        self.assertNotEqual(a['input_hash'],b['input_hash'])
        self.assertNotEqual(a['tasks'][-1]['input_hash'],b['tasks'][-1]['input_hash'])

    def test_missing_extra_inputs_and_budgets_fail(self):
        for mode,paper,code in [('paper-only',None,None),('code-only',self.paper,self.code),('paper-and-code',self.paper,None)]:
            with self.assertRaises(ValueError): build_mode(mode,paper,code)
        with self.assertRaises(ValueError): build_mode('paper-only',self.root/'absent')
        with self.assertRaises(ValueError): build_mode('code-only',code=self.code,max_bytes=1)
        (self.code/'other.py').write_text('x=1',encoding='utf8')
        with self.assertRaises(ValueError): build_mode('code-only',code=self.code,max_files=1)
        empty=self.root/'empty';empty.mkdir()
        with self.assertRaises(ValueError): build_mode('code-only',code=empty)

    def test_remote_paper_remains_unretrieved(self):
        result=build_mode('paper-only','https://example.org/paper.pdf')
        self.assertEqual(result['paper_status'],'retrieval_pending')
        self.assertIsNone(result['sources']['paper']['sha256'])
        self.assertEqual(result['implementation_status'],'unverified')

    def test_all_modes_resume_through_full_host_protocol(self):
        for mode in ('paper-only','code-only','paper-and-code'):
            plan=self.root/(mode+'.json');state=self.root/(mode+'-state.json')
            args=[mode,'-o',str(plan),'--state',str(state)]
            if mode!='code-only': args+=['--paper',str(self.paper)]
            if mode!='paper-only': args+=['--code',str(self.code)]
            with contextlib.redirect_stdout(io.StringIO()): main(args)
            completed=set()
            for _ in range(20):
                req=self.root/'request.json'
                with contextlib.redirect_stdout(io.StringIO()): orchestrate(['next',str(state),'-o',str(req)])
                request=json.loads(req.read_text(encoding='utf8'))
                if request['action']=='complete': break
                self.assertEqual(request['action'],'request_host')
                results=[]
                for task in request['tasks']:
                    self.assertTrue(set(task['depends_on']).issubset(completed))
                    completed.add(task['task_id'])
                    artifact_path='synthetic-test-artifact'
                    if task.get('artifact_contract'):
                        from task_contracts import example_artifact
                        artifact_path=str(self.root/(mode+'-'+task['role']+'.json'))
                        artifact=example_artifact(task['artifact_contract']['kind'],task['input_hash'])
                        artifact['upstream_artifacts']=[{'task_id':d['task_id'],'sha256':d['artifact_sha256']} for d in request['dependency_artifacts'][task['task_id']] if d['artifact_sha256']]
                        atomic_write(artifact_path,artifact)
                    results.append({'task_id':task['task_id'],'input_hash':task['input_hash'],'status':'completed','artifact_path':artifact_path})
                response=self.root/'response.json';atomic_write(response,results)
                with contextlib.redirect_stdout(io.StringIO()): orchestrate(['submit',str(state),'--response',str(response),'-o',str(state)])
            else: self.fail('did not complete DAG')
            self.assertEqual(len(completed),len(json.loads(plan.read_text(encoding='utf8'))['tasks']))

    def test_failed_predecessor_is_blocked_not_complete(self):
        plan=self.root/'plan.json';state=self.root/'state.json'
        with contextlib.redirect_stdout(io.StringIO()): main(['code-only',str(self.code),'-o',str(plan),'--state',str(state)])
        data=json.loads(state.read_text(encoding='utf8'));data['tasks'][0]['status']='failed';atomic_write(state,data)
        out=self.root/'next.json'
        with contextlib.redirect_stdout(io.StringIO()): orchestrate(['next',str(state),'-o',str(out)])
        self.assertEqual(json.loads(out.read_text(encoding='utf8'))['action'],'blocked')

if __name__=='__main__':unittest.main()
