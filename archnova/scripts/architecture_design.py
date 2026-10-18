# -*- coding: utf-8 -*-
"""Generate a structured neural architecture design from task and tensor contracts."""
import argparse,json
from pathlib import Path
from jsonschema import Draft4Validator
from orchestrator import atomic_write,digest
ROOT=Path(__file__).resolve().parents[1]
FUNCTION_COMPONENTS={'local_spatial':['cnn','neural_operator'],'long_range_dependency':['transformer','state_space'],'memory_state':['state_space','rnn','transformer'],'spectral_or_physics':['neural_operator','cnn'],'sparse_routing':['transformer','hybrid'],'cross_modal_alignment':['transformer','hybrid'],'graph_relation':['gnn'],'stable_optimization':['normalization','residual','state_space'],'low_latency':['state_space','cnn','mlp']}
FAMILY={'tabular_classification':'mlp','image_classification':'cnn','object_detection':'cnn','time_series':'state_space','sequence_modeling':'rnn','nlp':'transformer','long_context_nlp':'hybrid','deep_image':'hybrid','neural_operator':'neural_operator','multimodal':'hybrid','custom':'hybrid'}
def _params_mlp(inp,out,width,depth):return inp*width+width+max(0,depth-1)*(width*width+width)+width*out+out
def design(task_type,input_shape,output_shape,dtype='float32',layout='auto',sequence_length=None,feature_dim=None,depth=6,width=256,attention_heads=None,normalization='layernorm',regularization=None,activation='gelu',required_functions=None,component_catalog=None):
 if task_type not in FAMILY:raise ValueError('Unknown task type')
 family=FAMILY[task_type];required_functions=required_functions or [];component_catalog=component_catalog or []
 selected=[]
 for fn in required_functions:
  if fn not in FUNCTION_COMPONENTS: raise ValueError('Unknown functional requirement: '+fn)
  preferred=FUNCTION_COMPONENTS[fn]
  matches=[c for c in component_catalog if c.get('family') in preferred or c.get('functional_group') in preferred or c.get('kind') in preferred]
  selected.extend(matches[:2] if matches else [{'id':'functional:'+fn,'family':preferred[0],'status':'proposed'}])
 selected_ids=[]
 for c in selected:
  cid=c.get('id') or c.get('component_id')
  if cid and cid not in selected_ids:selected_ids.append(cid)
 regularization=regularization or ['weight_decay','dropout']
 if family=='cnn':
  receptive=1+2*depth;layers=[{'name':'stem','kind':'conv2d','channels':width,'kernel':[3,3],'stride':[2,2]},{'name':'blocks','kind':'residual_conv','count':depth,'channels':width,'normalization':normalization,'activation':activation},{'name':'head','kind':'global_pool_linear','outputs':output_shape[-1]}];params=width*3*3*input_shape[-1]+width*output_shape[-1]
 elif family=='transformer':
  heads=attention_heads or 8
  if width%heads:raise ValueError('attention_heads must divide width')
  receptive=sequence_length or input_shape[0];layers=[{'name':'blocks','kind':'transformer','count':depth,'width':width,'heads':heads,'norm':normalization,'activation':activation},{'name':'head','kind':'linear','outputs':output_shape[-1]}];params=depth*(4*width*width+2*width*width)+width*output_shape[-1]
 elif family=='state_space':
  receptive=sequence_length or input_shape[0];layers=[{'name':'state_blocks','kind':'selective_state_space','count':depth,'width':width,'state_size':width},{'name':'head','kind':'linear','outputs':output_shape[-1]}];params=depth*(4*width*width)+width*output_shape[-1]
 elif family=='neural_operator':
  receptive=input_shape[1] if len(input_shape)>1 else input_shape[0];layers=[{'name':'lifting','kind':'linear','width':width},{'name':'operator_blocks','kind':'spectral_or_kernel','count':depth,'width':width},{'name':'projection','kind':'linear','outputs':output_shape[-1]}];params=2*width*width+width*output_shape[-1]
 else:
  receptive=None;layers=[{'name':'input','kind':'linear','width':width},{'name':'blocks','kind':family+'_block','count':depth,'width':width,'norm':normalization,'activation':activation},{'name':'head','kind':'linear','outputs':output_shape[-1]}];params=_params_mlp(input_shape[-1],output_shape[-1],width,depth)
 skips=[{'from':'block:'+str(i),'to':'block:'+str(i+2),'kind':'residual'} for i in range(max(0,depth-2))]
 return {'schema_version':'1.0','design_id':'architecture:'+task_type+':'+digest({'task_type':task_type,'input':input_shape,'output':output_shape})[:12],'task_type':task_type,'input_contract':{'shape':input_shape,'dtype':dtype,'layout':layout,'sequence_length':sequence_length,'feature_dim':feature_dim},'output_contract':{'shape':output_shape,'dtype':dtype},'architecture_choice':{'family':family,'rationale':'Task type supplies a prior; functional requirements may source components across all registered neural families.','functional_requirements':required_functions,'component_sources':selected_ids,'alternatives_rejected':['Unmatched families require a different receptive field, state model or modality contract.']},'design_principles':{'depth':depth,'width':width,'skip_connections':skips,'normalization':normalization,'regularization':regularization,'activation':activation,'attention_heads':attention_heads,'receptive_field':receptive},'deliverables':{'network_definition':{'family':family,'layers':layers},'parameter_analysis':{'trainable_parameters':params,'formula':'Bounded proxy; verify against implementation','assumptions':['No tied weights unless explicitly declared']},'layer_descriptions':layers,'dataflow_graph':{'nodes':[x['name'] for x in layers],'edges':[{'from':layers[i]['name'],'to':layers[i+1]['name']} for i in range(len(layers)-1)]+skips},'benchmark_plan':{'metrics':['quality','latency','peak_memory','throughput'],'baselines':['simple_baseline','current_best'],'splits':['development','holdout','ood'],'seeds':[1,2,3]},'deployment_requirements':{'dtype':dtype,'shape_contract':input_shape,'runtime':'reviewed backend required','state':['inference_cache_or_state_if_declared']}},'validation_gates':[{'id':'shape','test':'Validate every layer input/output shape','pass_condition':'No incompatible tensor interfaces'},{'id':'mechanism','test':'Run ablation of depth/width/skip/normalization choices','pass_condition':'Claimed mechanism contributes under locked split'},{'id':'baseline','test':'Compare against declared baselines','pass_condition':'Improvement survives repeated seeds and holdout'}]}
def validate_design(record):
 schema=json.loads((ROOT/'assets/architecture-design.schema.json').read_text(encoding='utf8'));errors=list(Draft4Validator(schema).iter_errors(record))
 if errors:raise ValueError('Architecture design: '+errors[0].message)
 if record['architecture_choice']['family']=='transformer' and record['design_principles']['attention_heads'] and record['design_principles']['width']%record['design_principles']['attention_heads']:raise ValueError('Attention heads must divide width')
 return record
def main():
 p=argparse.ArgumentParser();p.add_argument('--task-type',required=True,choices=sorted(FAMILY));p.add_argument('--input-shape',required=True);p.add_argument('--output-shape',required=True);p.add_argument('--sequence-length',type=int);p.add_argument('--feature-dim',type=int);p.add_argument('--functions',nargs='*',choices=sorted(FUNCTION_COMPONENTS));p.add_argument('--components');p.add_argument('--depth',type=int,default=6);p.add_argument('--width',type=int,default=256);p.add_argument('--attention-heads',type=int);p.add_argument('-o','--output',required=True);a=p.parse_args();
 try:catalog=json.loads(Path(a.components).read_text(encoding='utf8')) if a.components else [];catalog=catalog.get('components',catalog if isinstance(catalog,list) else []);r=design(a.task_type,json.loads(a.input_shape),json.loads(a.output_shape),sequence_length=a.sequence_length,feature_dim=a.feature_dim,depth=a.depth,width=a.width,attention_heads=a.attention_heads,required_functions=a.functions,component_catalog=catalog);validate_design(r);atomic_write(a.output,r);print(json.dumps({'status':'design_only','output':a.output,'family':r['architecture_choice']['family']}))
 except (ValueError,OSError,KeyError) as exc:p.error(str(exc))
if __name__=='__main__':main()


