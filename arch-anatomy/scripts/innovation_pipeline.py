# -*- coding: utf-8 -*-
"""Evidence-gated neural architecture innovation pipeline."""
import argparse,copy,json,datetime
from pathlib import Path
from orchestrator import atomic_write,digest
from network_system import validate_system
from architecture_search import search_ir
from training_runtime import train_ir
from benchmark_runtime import benchmark_ir
from breakthrough_explorer import build_exploration
from model_diagnostics import diagnose

def _status(ok,reason,artifact=None):return {'status':'validated' if ok else 'blocked','reason':reason,'artifact':artifact}
def build_design(system,components=None):
 validate_system(system);components=components or []
 ids=[c.get('component_id') or c.get('id') for c in components]
 return {'design_id':'innovation:'+system['system_id'],'family':system['family'],'system_snapshot_hash':digest(system),'component_ids':ids,'composition':{'network_body':system['views'].get('inference',[])+[c['id'] for c in system['components'] if c['role']=='network_body'],'inference':system['views'].get('inference',[]),'training':system['views'].get('training',[]),'preprocess':system['views'].get('preprocess',[]),'distributed':system['views'].get('distributed',[])},'hypotheses':['The proposed composition preserves declared interfaces and may improve the task objective; this is a hypothesis until controlled experiments pass.'],'evidence_status':'candidate_requires_review'}
def run_pipeline(system_path,output,task_path=None,model_path=None,execute=False,components_path=None):
 system=json.loads(Path(system_path).read_text(encoding='utf8'));validate_system(system)
 components=[]
 if components_path:
  raw=json.loads(Path(components_path).read_text(encoding='utf8'));components=raw.get('components',raw if isinstance(raw,list) else [])
 design=build_design(system,components);exploration=build_exploration(system,components);result={'schema_version':'1.0','pipeline_id':'innovation-pipeline-v1','created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'design':design,'breakthrough_exploration':exploration,'claims':{},'validation':[],'promotion':'unresolved','scope_limits':['Candidate generation is evidence-bound; no automatic scientific proof.']}
 result['claims']['architecture_creation']=_status(bool(components),'Candidate composition generated from system profile and components; source evidence still required.')
 result['claims']['composition']=_status(bool(design['composition']['network_body']),'Interfaces are structurally composed; semantic equivalence is not established.')
 if not task_path or not model_path:
  result['claims']['training']=_status(False,'Task contract and initial model are required for executable training.')
  result['claims']['gpu']=_status(False,'Task/model and a reviewed GPU lowering are required for GPU validation.')
  result['claims']['generalization']=_status(False,'Untouched holdout task is required for generalization validation.')
 else:
  task=json.loads(Path(task_path).read_text(encoding='utf8'));model=json.loads(Path(model_path).read_text(encoding='utf8'));result['model_diagnostics']=diagnose(model,task,system)
  if execute:
   search=search_ir(model,task,None,rules=task.get('search',{}).get('rules',['relu','absolute']))
   result['validation'].append({'kind':'architecture_search','status':search['status'],'candidates':len(search['candidates']),'task_hash':search['task_hash']})
   if task.get('training',{}).get('enabled'):
    train=train_ir(model,task,None,task['training']['epochs'],task['training']['learning_rate']);result['validation'].append({'kind':'training','status':train['status'],'final_metric':train['final_metric'],'lifecycle':train['lifecycle']});result['claims']['training']=_status(True,'Bounded training receipt completed; this is not full framework backprop.')
   else: result['claims']['training']=_status(False,'Training is not enabled in the task contract.')
   bench=benchmark_ir(model,task,'cuda',task.get('benchmark',{}).get('repetitions',2),task.get('benchmark',{}).get('warmup',1));result['validation'].append({'kind':'benchmark','status':bench['status'],'device':'cuda','reason':bench.get('reason'),'lifecycle':bench.get('lifecycle')});result['claims']['gpu']=_status(bench['status']=='completed','CUDA validation requires an available device and reviewed lowering.')
   result['claims']['generalization']=_status('holdout' in task.get('dataset',{}),'Holdout presence is declared; superiority still requires baseline comparison and repeated runs.')
  else:
   result['claims']['training']=_status(False,'Execution disabled; pipeline produced a design plan only.');result['claims']['gpu']=_status(False,'Execution disabled; no GPU measurement performed.');result['claims']['generalization']=_status(False,'Execution disabled; no holdout evaluation performed.')
 result['promotion']='validated' if all(v['status']=='validated' for v in result['claims'].values()) else 'blocked' if any(v['status']=='blocked' for v in result['claims'].values()) else 'unresolved'
 atomic_write(output,result);return result
def main():
 p=argparse.ArgumentParser();p.add_argument('--system',required=True);p.add_argument('--task');p.add_argument('--model');p.add_argument('--components');p.add_argument('--execute',action='store_true');p.add_argument('-o','--output',required=True);a=p.parse_args()
 try:r=run_pipeline(a.system,a.output,a.task,a.model,a.execute,a.components);print(json.dumps({'status':r['promotion'],'output':a.output}))
 except (ValueError,OSError,KeyError) as exc:p.error(str(exc))
if __name__=='__main__':main()






