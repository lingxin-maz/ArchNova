# -*- coding: utf-8 -*-
"""Safe framework graph adapter probes. Never imports candidate code into this process."""
import ast,hashlib,importlib.util,json,subprocess,sys,tempfile
from pathlib import Path
from lifecycle_runtime import make_receipt

def _safe_ast(path,framework,entry):
 body=Path(path).read_bytes();tree=ast.parse(body.decode('utf8'));classes=[n.name for n in tree.body if isinstance(n,ast.ClassDef)];functions=[n.name for n in tree.body if isinstance(n,ast.FunctionDef)]
 if entry not in classes+functions:return {'status':'failed','reason':'entry not found: '+entry}
 ops=[]
 for n in ast.walk(tree):
  if isinstance(n,ast.Call):
   name=n.func.attr if isinstance(n.func,ast.Attribute) else n.func.id if isinstance(n.func,ast.Name) else 'call'
   if name in ('relu','tanh','linear','matmul','add','conv2d','einsum','dot','jit','grad','vmap'):ops.append(name)
 return {'status':'completed','framework':framework,'entry':entry,'source_sha256':hashlib.sha256(body).hexdigest(),'operators':ops,'static_only':True,'scope_limits':['No framework runtime available; AST names are hypotheses, not execution graph.']}

def _torch_fx(path,entry,example_inputs):
 import importlib.util,torch,torch.fx
 spec=importlib.util.spec_from_file_location('arch_anatomy_reviewed_module',str(path));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 target=getattr(module,entry,None)
 if target is None: raise ValueError('entry not found: '+entry)
 instance=target() if isinstance(target,type) else target
 values=[] if example_inputs is None else [torch.tensor(v,dtype=torch.float32) for v in (example_inputs.values() if isinstance(example_inputs,dict) else example_inputs)]
 graph=torch.fx.symbolic_trace(instance) if isinstance(instance,torch.nn.Module) else torch.fx.symbolic_trace(target)
 supported={'relu':'relu','tanh':'tanh','matmul':'matmul','add':'add','linear':'linear','softmax':'softmax','transpose':'transpose','reshape':'reshape'};nodes=[];unsupported=[]
 for node in graph.graph.nodes:
  if node.op=='placeholder': nodes.append({'name':node.name,'op':'input'})
  elif node.op=='output': nodes.append({'name':node.name,'op':'output'})
  else:
   name=node.target.__name__ if callable(node.target) and hasattr(node.target,'__name__') else str(node.target)
   op=supported.get(name)
   if op is None: unsupported.append(name)
   nodes.append({'name':node.name,'op':op or 'unsupported','target':name,'inputs':[x.name for x in node.all_input_nodes]})
 return {'status':'completed' if not unsupported else 'partial','framework':'pytorch','entry':entry,'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'torch_version':torch.__version__,'operators':nodes,'unsupported_operators':sorted(set(unsupported)),'runtime_traced':True,'scope_limits':['Explicit allow_runtime=True reviewed import; FX trace is concrete-shape and does not prove dynamic control flow.'],'lifecycle':make_receipt('lowering',['source','example_inputs'],['normalized_graph'],['framework_graph'])}

def extract_graph(framework,path,entry,example_inputs=None,allow_runtime=False):
 if framework not in ('pytorch','jax'):raise ValueError('framework must be pytorch or jax')
 path=Path(path).resolve()
 if not path.is_file():raise ValueError('source file missing')
 module='torch' if framework=='pytorch' else 'jax'
 if importlib.util.find_spec(module) is None:return {'status':'unavailable','framework':framework,'entry':entry,'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'reason':module+' runtime is not installed','fallback':_safe_ast(path,framework,entry)}
 if framework=='pytorch' and allow_runtime:
  try:return _torch_fx(path,entry,example_inputs)
  except Exception as exc:return {'status':'failed','framework':framework,'entry':entry,'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'reason':'Reviewed FX trace failed: '+str(exc),'fallback':_safe_ast(path,framework,entry)}
 return {'status':'unavailable','framework':framework,'entry':entry,'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'reason':module+' runtime extraction requires explicit allow_runtime=True; source was not imported automatically','fallback':_safe_ast(path,framework,entry)}


def main():
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--framework',choices=['pytorch','jax'],required=True);p.add_argument('--source',required=True);p.add_argument('--entry',required=True);p.add_argument('--inputs');p.add_argument('--allow-runtime',action='store_true');p.add_argument('-o','--output',required=True);a=p.parse_args()
 result=extract_graph(a.framework,a.source,a.entry,json.loads(Path(a.inputs).read_text(encoding='utf8')) if a.inputs else None,a.allow_runtime);Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\\n',encoding='utf8');print(json.dumps({'status':result['status'],'output':a.output}))
if __name__=='__main__':main()




