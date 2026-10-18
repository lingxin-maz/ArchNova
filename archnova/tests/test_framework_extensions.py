import json,sys,tempfile,unittest,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from orchestrator import atomic_write,digest

class FrameworkExtensionTests(unittest.TestCase):
 def test_capability_audit_reports_complete_links_and_known_limits(self):
  from capability_audit import audit
  result=audit(Path(__file__).resolve().parents[1])
  self.assertTrue(result['status'] in ('complete','partial'))
  self.assertTrue(all(c['status']=='pass' for c in result['checks'] if c['id']!='runtime_frameworks'))
  self.assertIn('pytorch', result['limits']['frameworks']); self.assertIn('jax', result['limits']['frameworks'])

 def task(self,root):
  data=[{'id':'d'+str(i),'split':'development' if i<3 else 'holdout','inputs':{'x':[[float(i-1)]]},'targets':{'y':[[float(i-1)]]}} for i in range(5)]
  atomic_write(root/'data.json',data)
  task={'schema_version':'1.0','task_id':'t','goal':'identity','symbols':{'B':1},'inputs':[{'name':'x','shape':['B',1],'dtype':'float64','unit':'1'}],'outputs':[{'name':'y','shape':['B',1],'dtype':'float64','unit':'1'}],'constraints':{'allowed_ops':['identity','scale','relu','tanh','linear','add','matmul'],'nonnegative_outputs':False},'budgets':{'max_nodes':8,'max_parameters':8,'max_candidates':4},'objective':{'metric':'mse','direction':'lower_better','maximum':1e-8,'min_improvement':0},'dataset':{'path':'data.json','sha256':hashlib.sha256((root/'data.json').read_bytes()).hexdigest()}}
  atomic_write(root/'task.json',task);return task
 def model(self):return {'schema_version':'1.0','inputs':[{'id':'x','shape':['B',1],'dtype':'float64'}],'parameters':[],'nodes':[{'id':'n','op':'identity','inputs':['x'],'attributes':{},'parameters':{}}],'outputs':{'y':'n'}}
 def test_extended_tensor_ops_validate_shapes_and_execute(self):
  from architecture_ir import validate_ir
  from prototype_runtime import predict
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);task=self.task(r);task['symbols']={'B':2};task['inputs'][0]['shape']=['B',2];task['outputs'][0]['shape']=['B',2];task['constraints']['allowed_ops'] += ['transpose','softmax','reshape','concat','layernorm']
   x={'x':[[1.,2.],[3.,4.]]}
   models=[
    {'nodes':[{'id':'t','op':'transpose','inputs':['x'],'attributes':{},'parameters':{}},{'id':'s','op':'softmax','inputs':['t'],'attributes':{'axis':'feature'},'parameters':{}}],'out':'s'},
    {'nodes':[{'id':'c','op':'concat','inputs':['x','x'],'attributes':{'axis':1},'parameters':{}}],'out':'c','shape':['B',4]},
    {'nodes':[{'id':'r','op':'reshape','inputs':['x'],'attributes':{'shape':[1,4]},'parameters':{}}],'out':'r','shape':[1,4]},
    {'nodes':[{'id':'n','op':'layernorm','inputs':['x'],'attributes':{'axis':'feature','eps':1e-5},'parameters':{}}],'out':'n'}]
   for spec in models:
    task['outputs'][0]['shape']=spec.get('shape',['B',2])
    m={'schema_version':'1.0','inputs':[{'id':'x','shape':['B',2],'dtype':'float64'}],'parameters':[],'nodes':spec['nodes'],'outputs':{'y':spec['out']}}
    summary=validate_ir(m,task);result=predict(m,x)['y'];self.assertEqual([len(result),len(result[0])],summary['shapes'][spec['out']])

 def test_pytorch_extractor_handles_missing_runtime_and_extracts_safe_subset(self):
  from framework_adapters import extract_graph
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);src=r/'m.py';src.write_text('import torch\nclass M(torch.nn.Module):\n def forward(self,x):\n  return torch.relu(x)\n',encoding='utf8')
   out=extract_graph('pytorch',src,entry='M',example_inputs={'x':[[1.]]})
   self.assertIn(out['status'],('unavailable','completed'));self.assertEqual(out['source_sha256'],hashlib.sha256(src.read_bytes()).hexdigest())
   if out['status']=='unavailable':self.assertIn('torch',out['reason'].lower())
 def test_explicit_torch_fx_trace_returns_normalized_graph_when_available(self):
  import importlib.util
  if importlib.util.find_spec('torch') is None: self.skipTest('torch unavailable')
  from framework_adapters import extract_graph
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);src=r/'m.py';src.write_text('import torch\nclass M(torch.nn.Module):\n def forward(self,x): return torch.relu(x)\n',encoding='utf8')
   out=extract_graph('pytorch',src,'M',{'x':[[1.]]},allow_runtime=True)
   self.assertIn(out['status'],('completed','partial'));self.assertTrue(out.get('runtime_traced'));self.assertIn('relu',str(out['operators']))

 def test_jax_extractor_missing_runtime_is_explicit(self):
  from framework_adapters import extract_graph
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'m.py';p.write_text('def f(x): return x',encoding='utf8');out=extract_graph('jax',p,entry='f',example_inputs={'x':[[1.]]});self.assertEqual(out['status'],'unavailable');self.assertIn('jax',out['reason'].lower())
 def test_training_updates_only_declared_trainable_parameters_and_replays(self):
  from training_runtime import train_ir,replay_training
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);task=self.task(r);m=self.model();m['parameters']=[{'id':'w','value':[[0.]],'trainable':True}];m['nodes']=[{'id':'n','op':'linear','inputs':['x'],'attributes':{},'parameters':{'weight':'w'}}]
   result=train_ir(m,task,r/'train.json',epochs=25,learning_rate=.2);self.assertEqual(result['status'],'completed');self.assertGreater(result['final_metric'],0);self.assertLess(result['final_metric'],1);self.assertTrue(result['trainable_parameter_ids']==['w']);self.assertEqual(replay_training(r/'train.json')['status'],'completed')
   m['parameters'][0]['trainable']=False
   with self.assertRaises(ValueError):train_ir(m,task,r/'bad.json',epochs=2,learning_rate=.1)
 def test_gpu_benchmark_is_explicitly_unavailable_without_torch_and_validates_device(self):
  from benchmark_runtime import benchmark_ir
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);task=self.task(r);out=benchmark_ir(self.model(),task,device='cuda',repetitions=2,warmup=1);self.assertIn(out['status'],('unavailable','completed'));self.assertIn('device',out)
   with self.assertRaises(ValueError):benchmark_ir(self.model(),task,device='bad',repetitions=1,warmup=0)
 def test_operator_registry_validates_and_blocks_unimplemented_remote_operator(self):
  from operator_registry import validate_record,activate_record
  record={'schema_version':'1.0','operator_id':'swiglu','version':'1.0.0','kind':'custom','license':'Apache-2.0','source':{'url':'https://example.org/swiglu.json','sha256':'a'*64},'implementation':{'language':'torch','entry':'swiglu'},'verification':{'status':'reviewed'}}
  self.assertEqual(validate_record(record),record);self.assertEqual(activate_record(record)['status'],'blocked');self.assertEqual(activate_record(record,True)['status'],'available')
  record['source']['url']='http://example.org/x'
  with self.assertRaises(ValueError):validate_record(record)

 def test_architecture_search_deduplicates_and_respects_budgets(self):
  from architecture_search import search_ir
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);task=self.task(r);result=search_ir(self.model(),task,r/'search.json',rules=['relu','absolute','relu']);self.assertEqual(result['status'],'planned');self.assertLessEqual(len(result['candidates']),task['budgets']['max_candidates']);self.assertEqual(len({c['semantic_hash'] for c in result['candidates']}),len(result['candidates']));self.assertEqual(result['task_hash'],digest(task))
 def test_search_rejects_unknown_rule_and_target_drift(self):
  from architecture_search import search_ir
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);task=self.task(r)
   with self.assertRaises(ValueError):search_ir(self.model(),task,r/'x.json',rules=['unknown'])
   task['goal']='changed';
   with self.assertRaises(ValueError):search_ir(self.model(),task,r/'x.json',rules=['relu'],expected_task_hash='0'*64)

 def test_rank3_and_rank4_tensor_runtime_operations(self):
  from tensor_runtime import tensor_shape,flatten,reshape_tensor,elementwise,matmul_tensor
  x=[[[[1.,2.],[3.,4.]]]]
  self.assertEqual(tensor_shape(x),[1,1,2,2]);self.assertEqual(tensor_shape(reshape_tensor(flatten(x),[1,1,4])),[1,1,4])
  self.assertEqual(elementwise(x,lambda v:v+1)[0][0][0][0],2.)
  self.assertEqual(matmul_tensor([[[1.,2.]]],[[[3.],[4.]]]),[[[11.]]])
 def test_rank3_task_contract_and_identity_prototype_execute(self):
  from task_spec import load_task
  from architecture_ir import validate_ir
  from prototype_runtime import predict
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);data=[]
   for i,split in enumerate(['development','holdout']):
    x=[[[float(i),1.],[2.,3.]]];data.append({'id':str(i),'split':split,'inputs':{'x':x},'targets':{'y':x}})
   atomic_write(r/'data.json',data)
   import hashlib
   task={'schema_version':'1.0','task_id':'rank3','goal':'identity','symbols':{'B':1},'inputs':[{'name':'x','shape':['B',2,2],'dtype':'float64','unit':'1'}],'outputs':[{'name':'y','shape':['B',2,2],'dtype':'float64','unit':'1'}],'constraints':{'allowed_ops':['identity'],'nonnegative_outputs':False},'budgets':{'max_nodes':4,'max_parameters':0,'max_candidates':1},'objective':{'metric':'mse','direction':'lower_better','maximum':0.,'min_improvement':0.},'dataset':{'path':'data.json','sha256':hashlib.sha256((r/'data.json').read_bytes()).hexdigest()}}
   atomic_write(r/'task.json',task);loaded=load_task(r/'task.json');m={'schema_version':'1.0','inputs':[{'id':'x','shape':['B',2,2],'dtype':'float64'}],'parameters':[],'nodes':[{'id':'n','op':'identity','inputs':['x'],'attributes':{},'parameters':{}}],'outputs':{'y':'n'}};validate_ir(m,loaded);self.assertEqual(predict(m,data[0]['inputs'])['y'],data[0]['inputs']['x'])
if __name__=='__main__':unittest.main()


