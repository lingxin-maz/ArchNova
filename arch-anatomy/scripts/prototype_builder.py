# -*- coding: utf-8 -*-
"""Compile a bounded validated matrix IR into a portable, hash-bound Python bundle."""
import argparse,hashlib,json,shutil
from pathlib import Path
from orchestrator import atomic_write,digest
from task_spec import load_task,load_dataset,read_json
from architecture_ir import validate_ir,semantic_hash
from jsonschema import Draft4Validator
ROOT=Path(__file__).resolve().parents[1]
FILES={'adapter.py','engine.py','tensor_runtime.py','model.json','task_spec.json','dataset.json'}
ADAPTER="""import importlib.util,json,sys
from pathlib import Path
root=Path(__file__).resolve().parent
sys.path.insert(0,str(root))
spec=importlib.util.spec_from_file_location("bounded_engine",root/"engine.py")
engine=importlib.util.module_from_spec(spec);spec.loader.exec_module(engine)
model=json.loads((root/"model.json").read_text(encoding="utf8"))
request=json.load(sys.stdin)
result=engine.predict(model,request["inputs"])
print(json.dumps({"outputs":result},allow_nan=False))
"""

def file_hash(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def build_prototype(model,task_path,output,input_hash=None,upstream_artifacts=None):
    task_path=Path(task_path).resolve();task=load_task(task_path);summary=validate_ir(model,task)
    out=Path(output).resolve()
    if out.exists():raise ValueError('Choose a new prototype output directory')
    out.mkdir(parents=True)
    atomic_write(out/'model.json',model);atomic_write(out/'task_spec.json',task)
    shutil.copyfile(task_path.parent/task['dataset']['path'],out/'dataset.json')
    shutil.copyfile(ROOT/'scripts/prototype_runtime.py',out/'engine.py');shutil.copyfile(ROOT/'scripts/tensor_runtime.py',out/'tensor_runtime.py')
    (out/'adapter.py').write_text(ADAPTER,encoding='utf8')
    manifest={'schema_version':'1.0','artifact_kind':'prototype','runtime':'python_stdlib_rank1_4_v2','task_hash':digest(task),'model_hash':semantic_hash(model),
              'task_input_hash':input_hash,'upstream_artifacts':upstream_artifacts or [],
              'files':{name:file_hash(out/name) for name in sorted(FILES)},'summary':summary,
              'scope_limits':['Forward-only deterministic rank-1..4 tensor graph; no parameter training or general arbitrary network compilation.',
                              'Cost summary is an operation proxy, not hardware performance.']}
    atomic_write(out/'prototype.json',manifest)
    return manifest

def verify_prototype(path,expected_task_hash=None,expected_model_hash=None):
    path=Path(path).resolve();manifest=read_json(path);root=path.parent
    errors=list(Draft4Validator(read_json(ROOT/'assets/prototype.schema.json')).iter_errors(manifest))
    if errors:raise ValueError('Prototype schema: '+errors[0].message)
    fields={'schema_version','artifact_kind','runtime','task_hash','model_hash','files','summary','scope_limits','task_input_hash','upstream_artifacts'}
    if not isinstance(manifest,dict) or set(manifest)!=fields or manifest['schema_version']!='1.0' or manifest['artifact_kind']!='prototype' or manifest['runtime'] not in ('python_stdlib_rank2_v1','python_stdlib_rank1_4_v2'):raise ValueError('Invalid prototype manifest')
    if manifest['task_input_hash'] is not None and (not isinstance(manifest['task_input_hash'],str) or len(manifest['task_input_hash'])!=64):raise ValueError('Invalid prototype task input hash')
    refs=manifest['upstream_artifacts']
    if not isinstance(refs,list) or any(not isinstance(x,dict) or set(x)!={'task_id','sha256'} for x in refs) or len({x['task_id'] for x in refs})!=len(refs):raise ValueError('Invalid prototype upstream binding')
    if not isinstance(manifest['files'],dict) or set(manifest['files'])!=FILES:raise ValueError('Prototype file set mismatch')
    for name,sha in manifest['files'].items():
        p=root/name
        if p.is_symlink() or not p.is_file() or file_hash(p)!=sha:raise ValueError('Prototype dependency changed/missing: '+name)
    if (root/'adapter.py').read_text(encoding='utf8')!=ADAPTER:raise ValueError('Adapter is not the generated target-independent runtime entry')
    if file_hash(root/'engine.py')!=file_hash(ROOT/'scripts/prototype_runtime.py'):raise ValueError('Unsupported runtime engine revision; rebuild bundle')
    task=read_json(root/'task_spec.json')
    from task_spec import validate_task
    validate_task(task);load_dataset(task,root,override=root/'dataset.json')
    if digest(task)!=manifest['task_hash'] or (expected_task_hash and expected_task_hash!=manifest['task_hash']):raise ValueError('Prototype target contract changed')
    model=read_json(root/'model.json');summary=validate_ir(model,task)
    if semantic_hash(model)!=manifest['model_hash'] or (expected_model_hash and expected_model_hash!=manifest['model_hash']):raise ValueError('Prototype model semantics changed')
    if digest(summary)!=digest(manifest['summary']):raise ValueError('Prototype cost/shape summary changed')
    return manifest

def adapter_reference(path,bundle_root=None):
    manifest=verify_prototype(path);root=Path(path).resolve().parent
    base=Path(bundle_root).resolve() if bundle_root else root
    return {'path':(root/'adapter.py').relative_to(base).as_posix(),'sha256':manifest['files']['adapter.py'],'dependencies':[{'path':(root/name).relative_to(base).as_posix(),'sha256':sha} for name,sha in manifest['files'].items() if name!='adapter.py']}

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='cmd',required=True)
    a=sub.add_parser('build');a.add_argument('--model',required=True);a.add_argument('--task',required=True);a.add_argument('-o','--output',required=True);a.add_argument('--input-hash');a.add_argument('--upstream',help='JSON task_id/sha256 array from dependency_artifacts')
    a=sub.add_parser('verify');a.add_argument('manifest')
    a=p.parse_args()
    try:
        result=build_prototype(read_json(a.model),a.task,a.output,a.input_hash,read_json(a.upstream) if a.upstream else None) if a.cmd=='build' else verify_prototype(a.manifest)
        print(json.dumps({'task_hash':result['task_hash'],'model_hash':result['model_hash'],'status':'prototype_verified'}))
    except (ValueError,OSError,KeyError) as exc:p.error(str(exc))
if __name__=='__main__':main()




