# -*- coding: utf-8 -*-
"""Audit capability files, schema links, integration edges, and distribution sync."""
import argparse,ast,hashlib,json
from pathlib import Path

REQUIRED_MODULES=['architecture_ir.py','architecture_search.py','graph_composer.py','search_protocol.py','meta_search.py','mechanism_gates.py','component_discovery.py','system_gates.py','system_gates.py','tensor_runtime.py','lifecycle_runtime.py','benchmark_runtime.py','design_loop.py','framework_adapters.py','input_modes.py','operator_registry.py','network_system.py','research_watch.py','frontier_capability_design.py','innovation_pipeline.py','breakthrough_explorer.py','architecture_design.py','model_diagnostics.py','prototype_builder.py','prototype_runtime.py','task_contracts.py','task_spec.py','training_runtime.py']
REQUIRED_SCHEMAS=['task-spec.schema.json','runtime-ir.schema.json','graph-ir.schema.json','meta-search.schema.json','mechanism-gates.schema.json','component-discovery.schema.json','system-gates.schema.json','system-gates.schema.json','prototype.schema.json','design-loop.schema.json','host-response.schema.json']
REQUIRED_DOCS=['executable-design-loop.md','framework-training-benchmark-search.md','neural-system-ontology.md','frontier-capability-design.md','breakthrough-exploration.md','architecture-design.md','graphir-composition.md','meta-search.md','mechanism-gates.md','component-discovery.md','system-gates.md','system-gates.md','model-diagnostics.md','input-modes.md','operator-design-review.md','architecture-benchmark.md']

def _check(identifier,ok,detail): return {'id':identifier,'status':'pass' if ok else 'fail','detail':detail}

def audit(root):
 root=Path(root).resolve(); scripts=root/'scripts'; assets=root/'assets'; refs=root/'references'; dist=root.parent/'dist'/'archnova'
 checks=[]
 missing=[n for n in REQUIRED_MODULES if not (scripts/n).is_file()]
 checks.append(_check('runtime_modules',not missing,'all required runtime modules present' if not missing else 'missing: '+','.join(missing)))
 missing=[n for n in REQUIRED_SCHEMAS if not (assets/n).is_file()]
 checks.append(_check('schemas',not missing,'all execution schemas present' if not missing else 'missing: '+','.join(missing)))
 missing=[n for n in REQUIRED_DOCS if not (refs/n).is_file()]
 checks.append(_check('references',not missing,'all capability references present' if not missing else 'missing: '+','.join(missing)))
 try:
  loop=(scripts/'design_loop.py').read_text(encoding='utf8')
  linked=all(x in loop for x in ('train_ir','benchmark_ir','propose_repairs','replay_training'))
 except OSError: linked=False
 checks.append(_check('design_loop_links',linked,'training, benchmark, search and replay hooks connected'))
 try:
  modes=(scripts/'input_modes.py').read_text(encoding='utf8'); orchestrator=(scripts/'orchestrator.py').read_text(encoding='utf8')
  linked=all(x in modes for x in ('prototype_generator','experiment_loop')) and all(x in orchestrator for x in ('design_loop','prototype'))
 except OSError: linked=False
 checks.append(_check('orchestration_links',linked,'target-bound roles and artifact kinds connected'))
 mismatches=[]; missing_dist=[]
 if root.parent.name=='dist' or (root.parent.name=='skills' and root.parent.parent.name=='.codex'):
  checks.append(_check('distribution_sync',True,'running inside a self-contained distribution copy'))
 else:
  if dist.is_dir():
   for p in root.rglob('*'):
    if not p.is_file() or '__pycache__' in p.parts or p.suffix=='.pyc': continue
    q=dist/p.relative_to(root)
    if not q.is_file(): missing_dist.append(str(p.relative_to(root)))
    elif hashlib.sha256(p.read_bytes()).digest()!=hashlib.sha256(q.read_bytes()).digest(): mismatches.append(str(p.relative_to(root)))
  else: missing_dist=[]
  checks.append(_check('distribution_sync',not missing_dist and not mismatches,('source and dist hashes match' if dist.is_dir() else 'source checkout; distribution has not been built') if not missing_dist and not mismatches else 'missing='+','.join(missing_dist)+' mismatch='+','.join(mismatches)))
 framework_status={}
 import importlib.util
 for label,name in (('pytorch','torch'),('jax','jax')):
  try: framework_status[label]='installed' if importlib.util.find_spec(name) is not None else 'unavailable'
  except Exception: framework_status[name]='unavailable'
 unavailable=[name for name,status in framework_status.items() if status!='installed']
 checks.append(_check('runtime_frameworks',True,'availability is reported explicitly; unavailable='+','.join(unavailable) if unavailable else 'torch and jax are installed; reviewed lowering still required'))
 status='complete' if all(c['status']=='pass' for c in checks if c['id']!='runtime_frameworks') else 'partial'
 return {'schema_version':'1.0','status':status,'checks':checks,'limits':{'frameworks':framework_status,'training':'bounded-matrix finite-difference IR only','benchmark':'CPU reference timing; CUDA requires reviewed lowering','search':'bounded relu/absolute structural candidates','evaluation':'human reference is still pending; current benchmark is not a gold score'},'next_actions':['Extend the explicit Torch FX path with parameterized modules, more lowering mappings, and frozen subprocess execution.','Add a reviewed JAX jaxpr adapter plus train/eval parity and gradient checks for framework adapters.','Add hidden human-reviewed cases covering dynamic control flow, shared state, complex tensors, odd grids and distributed state.']}

def main():
 p=argparse.ArgumentParser();p.add_argument('root',nargs='?',default='.');p.add_argument('-o','--output');a=p.parse_args();result=audit(a.root);text=json.dumps(result,ensure_ascii=False,indent=2)+'\n';Path(a.output).write_text(text,encoding='utf8') if a.output else print(text,end='');
if __name__=='__main__':main()









