import copy,hashlib,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from orchestrator import atomic_write,digest,validate_completion
from task_contracts import example_artifact

class DesignLoopTests(unittest.TestCase):
 def fixture(self,root):
  data=[{'id':str(i),'split':split,'inputs':{'x':[[x]]},'targets':{'y':[[abs(x)]]}} for i,(x,split) in enumerate([(-2.,'development'),(1.,'development'),(-3.,'holdout'),(.5,'holdout')])]
  atomic_write(root/'data.json',data)
  task={'schema_version':'1.0','task_id':'task:absolute','goal':'Fit absolute value with a small feed-forward network; no training claims',
        'symbols':{'B':1},'inputs':[{'name':'x','shape':['B',1],'dtype':'float64','unit':'1'}],'outputs':[{'name':'y','shape':['B',1],'dtype':'float64','unit':'1'}],
        'constraints':{'allowed_ops':['identity','scale','relu','tanh','linear','add','matmul'],'nonnegative_outputs':True},
        'budgets':{'max_nodes':16,'max_parameters':32,'max_candidates':3},'objective':{'metric':'mse','direction':'lower_better','maximum':1e-10,'min_improvement':0.0},
        'dataset':{'path':'data.json','sha256':hashlib.sha256((root/'data.json').read_bytes()).hexdigest()}}
  atomic_write(root/'task.json',task)
  model={'schema_version':'1.0','inputs':[{'id':'x','shape':['B',1],'dtype':'float64'}],'parameters':[],
         'nodes':[{'id':'n','op':'identity','inputs':['x'],'attributes':{},'parameters':{}}],'outputs':{'y':'n'}}
  return task,model
 def test_full_operator_semantics_bound_between_design_and_review(self):
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);design=example_artifact('design');atomic_write(r/'design.json',design)
   dep={'task_id':'d','artifact_contract':{'kind':'design'},'artifact_path':str(r/'design.json'),'artifact_sha256':hashlib.sha256((r/'design.json').read_bytes()).hexdigest()}
   review=example_artifact('replacement_review','a'*64);review['operators'][0]['equation']='y=2*x';review['upstream_artifacts']=[{'task_id':'d','sha256':dep['artifact_sha256']}];atomic_write(r/'review.json',review)
   task={'task_id':'r','input_hash':'a'*64,'artifact_contract':{'kind':'replacement_review'}}
   with self.assertRaises(ValueError):validate_completion(task,{'status':'completed','input_hash':'a'*64,'artifact_path':str(r/'review.json')},dependencies=[dep])
 def test_task_contract_checks_dataset_and_signature(self):
  from task_spec import load_task
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);task,model=self.fixture(r);load_task(r/'task.json')
   (r/'data.json').write_text('[]',encoding='utf8')
   with self.assertRaises(ValueError):load_task(r/'task.json')
 def test_reject_target_drift(self):
  from task_spec import load_task
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);task,model=self.fixture(r);locked=digest(task);task['objective']['maximum']=10;atomic_write(r/'task.json',task)
   with self.assertRaises(ValueError):load_task(r/'task.json',expected_hash=locked)
 def test_ir_semantics_shapes_and_cost_budget(self):
  from architecture_ir import validate_ir,semantic_hash
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);task,m=self.fixture(r);summary=validate_ir(m,task);self.assertEqual(summary['nodes'],1)
   changed=copy.deepcopy(m);changed['nodes'][0].update(op='scale',attributes={'factor':2.})
   self.assertNotEqual(semantic_hash(m),semantic_hash(changed))
   bad=copy.deepcopy(m);bad['nodes'][0]['op']='arbitrary_python'
   with self.assertRaises(ValueError):validate_ir(bad,task)
   task['budgets']['max_nodes']=0
   with self.assertRaises(ValueError):validate_ir(m,task)
 def test_ir_parameter_shape_mismatch_and_dead_nodes_fail(self):
  from architecture_ir import validate_ir
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);t,m=self.fixture(r);m['nodes'][0].update(op='linear',parameters={'weight':'w'});m['parameters']=[{'id':'w','value':[[1.,2.]],'trainable':False}]
   with self.assertRaises(ValueError):validate_ir(m,t)
   t,m=self.fixture(r);m['nodes'].append({'id':'unused','op':'identity','inputs':['x'],'attributes':{},'parameters':{}})
   with self.assertRaises(ValueError):validate_ir(m,t)
 def test_runtime_handles_shared_branch_network(self):
  from prototype_runtime import predict
  from architecture_ir import propose_repairs
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);t,m=self.fixture(r);repaired=propose_repairs(m,t,['absolute'])[0]['model']
   self.assertEqual(predict(repaired,{'x':[[-2.]]})['y'],[[2.]])
   self.assertEqual(predict(repaired,{'x':[[3.]]})['y'],[[3.]])
 def test_prototype_is_real_and_detects_tampering(self):
  from prototype_builder import build_prototype,verify_prototype
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);t,m=self.fixture(r);manifest=build_prototype(m,r/'task.json',r/'bundle')
   verify_prototype(r/'bundle/prototype.json',expected_task_hash=digest(t))
   self.assertTrue((r/'bundle/adapter.py').is_file())
   self.assertNotIn("['targets']",(r/'bundle/adapter.py').read_text(encoding='utf8'))
   (r/'bundle/model.json').write_text('{}',encoding='utf8')
   with self.assertRaises(ValueError):verify_prototype(r/'bundle/prototype.json')
 def test_loop_executes_failure_revision_and_heldout(self):
  from design_loop import run_loop,replay_loop
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);t,m=self.fixture(r);atomic_write(r/'model.json',m)
   result=run_loop(r/'task.json',r/'model.json',r/'run',execute=True,repairs=['relu','absolute'])
   self.assertEqual(result['status'],'accepted')
   self.assertEqual(len(result['attempts']),3)
   self.assertEqual(result['attempts'][0]['decision'],'revise')
   self.assertEqual(result['attempts'][1]['decision'],'revise')
   self.assertEqual(result['holdout']['candidate_metric'],0.)
   self.assertTrue(result['holdout']['evaluated_once'])
   self.assertEqual(replay_loop(r/'run/result.json')['status'],'accepted')
 def test_loop_integrates_declared_training_and_benchmark_receipts(self):
  from design_loop import run_loop,replay_loop
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);t,m=self.fixture(r)
   t['training']={'enabled':True,'epochs':3,'learning_rate':0.1,'trainable_parameter_ids':['w']}
   t['benchmark']={'devices':['cpu','cuda'],'repetitions':2,'warmup':1}
   m['nodes'][0].update(op='linear',parameters={'weight':'w','bias':'b'})
   m['parameters']=[{'id':'w','value':[[0.5]],'trainable':True},{'id':'b','value':[[0.]],'trainable':False}]
   atomic_write(r/'task.json',t);atomic_write(r/'model.json',m)
   result=run_loop(r/'task.json',r/'model.json',r/'run',execute=True,repairs=['absolute'])
   self.assertTrue(result['attempts'][0]['training'])
   self.assertEqual(result['attempts'][0]['benchmarks'][0]['status'],'completed')
   self.assertEqual(result['attempts'][0]['benchmarks'][1]['status'],'unavailable')
   self.assertEqual(replay_loop(r/'run/result.json')['status'],result['status'])

 def test_loop_never_claims_execution_without_execute(self):
  from design_loop import run_loop
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);t,m=self.fixture(r);atomic_write(r/'model.json',m)
   result=run_loop(r/'task.json',r/'model.json',r/'run')
   self.assertEqual(result['status'],'planned')
   self.assertFalse(result['attempts'])
 def test_loop_stops_at_budget_and_never_relaxes_goal(self):
  from design_loop import run_loop
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);t,m=self.fixture(r);t['budgets']['max_candidates']=1;atomic_write(r/'task.json',t);atomic_write(r/'model.json',m)
   result=run_loop(r/'task.json',r/'model.json',r/'run',execute=True,repairs=['absolute'])
   self.assertEqual(result['status'],'budget_exhausted');self.assertEqual(result['task_hash'],digest(t));self.assertIsNone(result['holdout'])
 def test_loop_does_not_search_using_holdout_failure(self):
  from design_loop import run_loop
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);t,m=self.fixture(r);data=json.loads((r/'data.json').read_text(encoding='utf8'));data[-1]['targets']['y']=[[999.]];atomic_write(r/'data.json',data);t['dataset']['sha256']=hashlib.sha256((r/'data.json').read_bytes()).hexdigest();atomic_write(r/'task.json',t);atomic_write(r/'model.json',m)
   result=run_loop(r/'task.json',r/'model.json',r/'run',execute=True,repairs=['absolute','relu'])
   self.assertEqual(result['status'],'holdout_failed');self.assertEqual(len(result['attempts']),2);self.assertTrue(result['holdout']['evaluated_once'])
 def test_executed_task_receipt_must_exist_and_replay(self):
  from task_contracts import validate_artifact
  d=example_artifact('design');d['experiment'].update(status='executed',receipt_refs=['missing.json'])
  with self.assertRaises(ValueError):validate_artifact(d)
 def test_prototype_role_cannot_complete_without_actual_artifact(self):
  with self.assertRaises(ValueError):validate_completion({'task_id':'p','role':'prototype_generator','input_hash':'a'*64},{'status':'completed','input_hash':'a'*64})


 def test_task_bound_ir_rejects_formula_and_external_signature_drift(self):
  from task_contracts import validate_artifact
  from architecture_ir import make_task_artifact
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);task,m=self.fixture(r);d=make_task_artifact(m,task,'design')
   validate_artifact(d,target_task=task)
   changed=copy.deepcopy(d);changed['operators'][0]['equation']='y=2*x'
   with self.assertRaises(ValueError):validate_artifact(changed,target_task=task)
   changed=copy.deepcopy(d);changed['runtime_ir']['outputs']={'wrong':'n'}
   with self.assertRaises(ValueError):validate_artifact(changed,target_task=task)
   changed=copy.deepcopy(d);changed['experiment']['decision_rule']['threshold']['value']=999
   with self.assertRaises(ValueError):validate_artifact(changed,target_task=task)
 def test_target_bound_route_has_actual_experiment_task(self):
  from input_modes import build_mode
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);task,m=self.fixture(r);(r/'source.py').write_text('def f(x): return x',encoding='utf8')
   plan=build_mode('code-only',code=r/'source.py',task_spec=r/'task.json');by={t['role']:t for t in plan['tasks']}
   self.assertEqual(by['prototype_generator']['artifact_contract']['kind'],'prototype')
   self.assertEqual(by['experiment_loop']['artifact_contract']['kind'],'design_loop')
   self.assertEqual(by['new_architecture_designer']['target_contract']['sha256'],digest(task))
 def test_prototype_submission_implements_the_exact_reviewed_model(self):
  from architecture_ir import make_task_artifact
  from prototype_builder import build_prototype
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);task,m=self.fixture(r);review=make_task_artifact(m,task,'replacement_review');review['verdict']='admit';atomic_write(r/'review.json',review)
   h=hashlib.sha256((r/'review.json').read_bytes()).hexdigest();deps=[{'task_id':'review','artifact_contract':{'kind':'replacement_review'},'artifact_path':str(r/'review.json'),'artifact_sha256':h}]
   proto=build_prototype(m,r/'task.json',r/'bundle',input_hash='b'*64,upstream_artifacts=[{'task_id':'review','sha256':h}])
   pt={'task_id':'p','role':'prototype_generator','input_hash':'b'*64,'artifact_contract':{'kind':'prototype'},'target_contract':{'path':str(r/'task.json'),'sha256':digest(task)}}
   response={'task_id':'p','input_hash':'b'*64,'status':'completed','artifact_path':str(r/'bundle/prototype.json')}
   validate_completion(pt,response,dependencies=deps)
   review['verdict']='reject';atomic_write(r/'review.json',review)
   with self.assertRaises(ValueError):validate_completion(pt,response,dependencies=deps)
 def test_real_linear_parameters_and_matmul_are_executed(self):
  from architecture_ir import validate_ir
  from prototype_runtime import predict
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);task,m=self.fixture(r);m['nodes'][0].update(op='linear',parameters={'weight':'w','bias':'b'});m['parameters']=[{'id':'w','value':[[2.]],'trainable':False},{'id':'b','value':[[1.]],'trainable':False}]
   self.assertEqual(validate_ir(m,task)['parameters'],2)
   self.assertEqual(predict(m,{'x':[[3.]]})['y'],[[7.]])
 def test_loop_replay_rejects_edited_decision_threshold_or_receipt(self):
  from design_loop import run_loop,replay_loop
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);task,m=self.fixture(r);atomic_write(r/'model.json',m);result=run_loop(r/'task.json',r/'model.json',r/'run',execute=True,repairs=['absolute'])
   result['holdout']['candidate_metric']=42;atomic_write(r/'run/result.json',result)
   with self.assertRaises(ValueError):replay_loop(r/'run/result.json')
   result['holdout']['candidate_metric']=0;atomic_write(r/'run/result.json',result)
   receipt=r/'run'/result['attempts'][0]['development']['receipt_path'];data=json.loads(receipt.read_text(encoding='utf8'));data['status']='passed';atomic_write(receipt,data)
   with self.assertRaises(ValueError):replay_loop(r/'run/result.json')
 def test_loop_replay_rejects_task_changes_and_missing_prototype(self):
  from design_loop import run_loop,replay_loop
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);task,m=self.fixture(r);atomic_write(r/'model.json',m);run_loop(r/'task.json',r/'model.json',r/'run')
   task['objective']['maximum']=99;atomic_write(r/'run/inputs/task.json',task)
   with self.assertRaises(ValueError):replay_loop(r/'run/result.json')
 def test_development_holdout_data_overlap_is_rejected(self):
  from task_spec import load_task
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);task,m=self.fixture(r);data=json.loads((r/'data.json').read_text(encoding='utf8'));data[-1]['inputs']=data[0]['inputs'];atomic_write(r/'data.json',data);task['dataset']['sha256']=hashlib.sha256((r/'data.json').read_bytes()).hexdigest();atomic_write(r/'task.json',task)
   with self.assertRaises(ValueError):load_task(r/'task.json')
 def test_runtime_engine_change_cannot_be_hidden_by_updating_manifest_hash(self):
  from prototype_builder import build_prototype,verify_prototype
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);task,m=self.fixture(r);manifest=build_prototype(m,r/'task.json',r/'bundle')
   (r/'bundle/engine.py').write_text('def predict(m,x): return x',encoding='utf8');manifest['files']['engine.py']=hashlib.sha256((r/'bundle/engine.py').read_bytes()).hexdigest();atomic_write(r/'bundle/prototype.json',manifest)
   with self.assertRaises(ValueError):verify_prototype(r/'bundle/prototype.json')


 def test_full_file_protocol_design_review_prototype_experiment(self):
  from architecture_ir import make_task_artifact
  from prototype_builder import build_prototype
  from design_loop import run_loop
  from orchestrator import main as route,init_state
  import contextlib,io
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);target,m=self.fixture(r);atomic_write(r/'initial.json',m);atomic_write(r/'plan.json',{})
   roles=[('design','design'),('replacement_review','replacement_review'),('prototype_generator','prototype'),('experiment_loop','design_loop')]
   tasks=[]
   for i,(role,kind) in enumerate(roles):
    tasks.append({'task_id':'t'+str(i),'role':role,'executor':'host','depends_on':['t'+str(i-1)] if i else [],'status':'pending','input_hash':digest({'i':i}),'artifact_contract':{'kind':kind},'target_contract':{'path':str(r/'task.json'),'sha256':digest(target)}})
   atomic_write(r/'state.json',init_state(r/'plan.json',tasks))
   for i,task in enumerate(tasks):
    with contextlib.redirect_stdout(io.StringIO()):route(['next',str(r/'state.json'),'-o',str(r/'request.json')])
    request=json.loads((r/'request.json').read_text(encoding='utf8'));self.assertEqual(request['tasks'][0]['task_id'],task['task_id'])
    upstream=[{'task_id':d['task_id'],'sha256':d['artifact_sha256']} for d in request['dependency_artifacts'][task['task_id']]]
    if i in (0,1):
     artifact=make_task_artifact(m,target,'design' if i==0 else 'replacement_review',task['input_hash']);artifact['upstream_artifacts']=upstream
     if i==1:
      artifact.update(verdict='admit',relation='interface_only',unresolved=[]);artifact['evidence'][0]['kind']='code_observed'
      for check in artifact['checks']:check.update(status='satisfied',evidence_ids=['ev:proposal'])
     path=r/('a'+str(i)+'.json');atomic_write(path,artifact)
    elif i==2:
     build_prototype(m,r/'task.json',r/'bundle',task['input_hash'],upstream);path=r/'bundle/prototype.json'
    else:
     run_loop(r/'task.json',r/'initial.json',r/'loop',execute=True,repairs=['relu','absolute'],input_hash=task['input_hash'],upstream_artifacts=upstream);path=r/'loop/result.json'
    atomic_write(r/'response.json',[{'task_id':task['task_id'],'input_hash':task['input_hash'],'status':'completed','artifact_path':str(path)}])
    with contextlib.redirect_stdout(io.StringIO()):route(['submit',str(r/'state.json'),'--response',str(r/'response.json'),'-o',str(r/'state.json')])
   with contextlib.redirect_stdout(io.StringIO()):route(['next',str(r/'state.json'),'-o',str(r/'done.json')])
   self.assertEqual(json.loads((r/'done.json').read_text(encoding='utf8'))['action'],'complete')
   # The protocol uses explicit synthetic review judgments; it is not evidence of real AI mathematical proof.

if __name__=='__main__':unittest.main()
