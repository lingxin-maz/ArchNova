# -*- coding: utf-8 -*-
"""Validate and instantiate generic neural-network system architecture profiles."""
import argparse,json
from pathlib import Path
from jsonschema import Draft4Validator
from orchestrator import atomic_write,digest
ROOT=Path(__file__).resolve().parents[1]
FAMILY_ROLES={'llm':['embedding','transformer_block','lm_head','kv_cache','optimizer_state','tokenizer','tensor_parallel','pipeline_parallel'],'cnn':['stem','conv_block','normalization','head','activation_cache','optimizer_state','augmentation','data_parallel'],'rnn':['input_projection','recurrent_block','state','head','optimizer_state','tokenizer','pipeline_parallel'],'state_space':['input_projection','selective_scan','state','readout','optimizer_state','chunking','tensor_parallel'],'diffusion':['noise_schedule','denoiser','conditioning','sampler','optimizer_state','latent_encoder','data_parallel'],'gnn':['node_encoder','message_passing','aggregation','readout','optimizer_state','graph_batcher','neighbor_partition'],'neural_operator':['lifting','spectral_or_kernel_operator','projection','physics_constraints','optimizer_state','mesh_or_grid','domain_parallel'],'multimodal':['modality_encoder','fusion','cross_attention','decoder','optimizer_state','tokenizer','tensor_parallel'],'hybrid':['backbone','coupling','task_head','state','optimizer_state','preprocess','distributed']}
def validate_system(record):
 schema=json.loads((ROOT/'assets/network-system.schema.json').read_text(encoding='utf8'));errors=list(Draft4Validator(schema).iter_errors(record))
 if errors:raise ValueError('Network system: '+errors[0].message)
 ids=[c['id'] for c in record['components']]
 if len(ids)!=len(set(ids)):raise ValueError('Duplicate system component id')
 expected=set(FAMILY_ROLES.get(record['family'],[]));observed={p['kind'] for c in record['components'] for p in c['parts']}
 if expected and not expected.intersection(observed):raise ValueError('Profile has no recognized family parts')
 comp_ids=set(ids)
 for phase in record.get('lifecycle',[]):
  if set(phase['component_ids'])-comp_ids: raise ValueError('Unknown lifecycle component reference')
 for transition in record.get('state_transitions',[]):
  if (set(transition['reads'])|set(transition['writes']))-comp_ids: raise ValueError('Unknown state transition component reference')
 for component in record['components']:
  for interface in component.get('interfaces',[]):
   if interface['to'] not in comp_ids: raise ValueError('Unknown interface target: '+interface['to'])
 for view,refs in record['views'].items():
  if len(refs)!=len(set(refs)):raise ValueError('Duplicate '+view+' view reference')
  unknown=set(refs)-comp_ids
  if unknown:raise ValueError('Unknown '+view+' component references: '+','.join(sorted(unknown)))
 return record
def profile(family,system_id=None):
 if family not in FAMILY_ROLES:raise ValueError('Unknown network family')
 sid=system_id or family+'-system';groups=[]
 role_map={'inference':'inference','training':'training','preprocess':'preprocess','distributed':'distributed'}
 for kind in FAMILY_ROLES[family]:
  role='network_body'
  if kind in ('kv_cache','activation_cache','state','sampler'):role='inference'
  if kind in ('optimizer_state',):role='training'
  if kind in ('tokenizer','augmentation','chunking','latent_encoder','mesh_or_grid','graph_batcher','neighbor_partition','preprocess'):role='preprocess'
  if kind in ('tensor_parallel','pipeline_parallel','data_parallel','domain_parallel','neighbor_partition'):role='distributed'
  cid=kind
  groups.append({'id':cid,'role':role,'network_ontology':role=='network_body','parts':[{'name':kind,'kind':kind,'status':'proposed','details':{}}],'inputs':[],'outputs':[],'states':[],'evidence':[],'interfaces':[]})
 links={'embedding':['transformer_block'],'transformer_block':['lm_head'],'node_encoder':['message_passing'],'message_passing':['readout'],'lifting':['spectral_or_kernel_operator'],'spectral_or_kernel_operator':['projection'],'noise_schedule':['denoiser'],'denoiser':['sampler'],'modality_encoder':['fusion'],'fusion':['decoder']}
 for component in groups:
  component['interfaces']=[{'to':target,'kind':'dataflow','contract':'tensor/state contract pending evidence'} for target in links.get(component['id'],[]) if any(g['id']==target for g in groups)]
 views={k:[c['id'] for c in groups if c['role']==v] for k,v in role_map.items()}
 return {'schema_version':'1.0','system_id':sid,'family':family,'task':'待补充','components':groups,'state_transitions':[{'phase':'inference','reads':views['inference'],'writes':views['inference'],'condition':'runtime request'}],'lifecycle':[{'phase':'preprocess','component_ids':views['preprocess'],'purpose':'prepare inputs'},{'phase':'train','component_ids':views['training']+views['distributed'],'purpose':'update parameters and distributed state'},{'phase':'inference','component_ids':[c['id'] for c in groups if c['role'] in ('network_body','inference')],'purpose':'produce outputs'}],'views':views,'provenance':[{'id':'prov:profile','kind':'proposed','source':'arch-anatomy built-in family profile','observed_at':'generated'}],'scope_limits':['Profile is a structured hypothesis until bound to paper/code/runtime evidence.']}
def main():
 p=argparse.ArgumentParser();sub=p.add_subparsers(dest='cmd',required=True);g=sub.add_parser('profile');g.add_argument('--family',required=True);g.add_argument('--id');g.add_argument('-o','--output',required=True);v=sub.add_parser('validate');v.add_argument('path');a=p.parse_args()
 try:
  result=profile(a.family,a.id) if a.cmd=='profile' else validate_system(json.loads(Path(a.path).read_text(encoding='utf8')))
  if a.cmd=='profile':atomic_write(a.output,result)
  print(json.dumps({'status':'valid','system_id':result['system_id'],'digest':digest(result)}))
 except (ValueError,OSError,KeyError) as exc:p.error(str(exc))
if __name__=='__main__':main()

