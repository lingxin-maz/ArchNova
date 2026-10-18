# -*- coding: utf-8 -*-
"""Hash-locked target contracts for a bounded deterministic matrix-runtime scope."""
import argparse,hashlib,json,math
from pathlib import Path
from jsonschema import Draft4Validator
from orchestrator import digest
ROOT=Path(__file__).resolve().parents[1]

def read_json(path):
    def invalid(value):raise ValueError('Nonfinite JSON constant: '+value)
    return json.loads(Path(path).read_text(encoding='utf8'),parse_constant=invalid)

def validate_task(task):
    schema=read_json(ROOT/'assets/task-spec.schema.json')
    errors=list(Draft4Validator(schema).iter_errors(task))
    if errors:raise ValueError('Task contract: '+errors[0].message)
    if task.get('training',{}).get('enabled') and not task['training'].get('trainable_parameter_ids'):raise ValueError('Training enabled requires explicit trainable_parameter_ids')
    if task.get('search') and task['search']['max_candidates']>task['budgets']['max_candidates']:raise ValueError('Search budget exceeds task candidate budget')
    for key in ('maximum','min_improvement'):
        value=task['objective'][key]
        if not math.isfinite(value):raise ValueError('Finite objective thresholds required')
    for group in ('inputs','outputs'):
        names=[p['name'] for p in task[group]]
        if len(names)!=len(set(names)):raise ValueError('Duplicate task '+group)
        for p in task[group]:resolve_shape(p['shape'],task['symbols'])
    rel=Path(task['dataset']['path'])
    if rel.is_absolute() or '..' in rel.parts:raise ValueError('Dataset path must stay within task bundle')
    return task

def resolve_shape(shape,symbols):
    result=[]
    for dim in shape:
        value=symbols.get(dim) if isinstance(dim,str) else dim
        if type(value)!=int or not 1<=value<=64:raise ValueError('Unbound or oversized shape dimension: '+str(dim))
        result.append(value)
    return result

def tensor_shape(value,max_rank=4):
    from tensor_runtime import tensor_shape as _tensor_shape
    return _tensor_shape(value,max_rank)

def matrix_shape(value):
    if not isinstance(value,list) or not 1<=len(value)<=64 or not all(isinstance(row,list) and 1<=len(row)<=64 for row in value):raise ValueError('Expected bounded rank-2 matrix')
    width=len(value[0])
    if any(len(row)!=width for row in value):raise ValueError('Ragged matrix')
    for row in value:
        for x in row:
            if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or abs(x)>1e100:raise ValueError('Finite bounded matrix values required')
    return [len(value),width]

def load_dataset(task,root,override=None):
    path=Path(override).resolve() if override else (Path(root)/task['dataset']['path']).resolve()
    if override is None and Path(root).resolve() not in path.parents:raise ValueError('Dataset escapes task root')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=task['dataset']['sha256']:raise ValueError('Dataset hash changed')
    data=read_json(path)
    if not isinstance(data,list) or not 2<=len(data)<=20:raise ValueError('Use 2..20 dataset records')
    ids=set();splits=set();inputs_by_split={}
    for row in data:
        if not isinstance(row,dict) or set(row)!={'id','split','inputs','targets'} or not isinstance(row['id'],str) or not row['id'] or row['id'] in ids:raise ValueError('Unique dataset records required')
        ids.add(row['id'])
        if row['split'] not in ('development','holdout'):raise ValueError('Unknown dataset split')
        splits.add(row['split'])
        for key,ports in [('inputs',task['inputs']),('targets',task['outputs'])]:
            values=row[key]
            if not isinstance(values,dict) or set(values)!={p['name'] for p in ports}:raise ValueError('Dataset task signature mismatch')
            for p in ports:
                if tensor_shape(values[p['name']])!=resolve_shape(p['shape'],task['symbols']):raise ValueError('Dataset tensor shape mismatch')
        fingerprint=digest(row['inputs'])
        if fingerprint in inputs_by_split and inputs_by_split[fingerprint]!=row['split']:raise ValueError('Identical input leaked across development/holdout')
        inputs_by_split[fingerprint]=row['split']
    if splits!={'development','holdout'}:raise ValueError('Separate development and holdout data required')
    return data

def load_task(path,expected_hash=None):
    path=Path(path).resolve();task=validate_task(read_json(path))
    if expected_hash is not None and digest(task)!=expected_hash:raise ValueError('Task target contract changed')
    load_dataset(task,path.parent)
    return task

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('task');a=p.parse_args()
    try:t=load_task(a.task)
    except (ValueError,KeyError,OSError) as e:p.error(str(e))
    print(json.dumps({'task_hash':digest(t),'task_id':t['task_id'],'status':'validated','scope':'deterministic_rank2_float64'}))
if __name__=='__main__':main()


