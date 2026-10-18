# -*- coding: utf-8 -*-
"""Execute a bounded architecture-revision loop against frozen development and holdout data.
This is a reference operator search, not a neural weight-training or arbitrary code agent.
"""
import argparse,copy,hashlib,json,math,shutil
from pathlib import Path
from orchestrator import atomic_write,digest
from task_spec import load_task,load_dataset,read_json,matrix_shape
from architecture_ir import validate_ir,semantic_hash,propose_repairs
from prototype_builder import build_prototype,verify_prototype,adapter_reference,file_hash
from experiment_runner import run_experiment,replay_receipt,validate_spec
from jsonschema import Draft4Validator
from numeric_checks import evaluate_decision
from training_runtime import train_ir,replay_training
from benchmark_runtime import benchmark_ir
from lifecycle_runtime import make_receipt,validate_receipt
REFERENCE="import json,sys\nrequest=json.load(sys.stdin)\nprint(json.dumps({'outputs':request['targets']},allow_nan=False))\n"

def _summary(receipt,task,data,split):
    replay=replay_receipt(receipt)
    if replay['status']!=receipt['status'] or replay['comparisons_completed']!=receipt['comparisons_completed']:raise ValueError('Receipt stored status differs from replay')
    wanted={r['id']:r for r in data if r['split']==split}
    if len(receipt['observations'])!=len(wanted):raise ValueError('Not all target dataset cases were executed: observations=%s wanted=%s'%(len(receipt['observations']),len(wanted)))
    errors=[];violations=[];seen=set()
    for observation in receipt['observations']:
        cid=observation['case_id'];source=wanted.get(cid)
        if source is None or cid in seen or (observation.get('execution_error') and set(observation.get('responses',{})) != {'reference','candidate'}):raise ValueError('Missing/duplicate/failed target case: cid=%s source=%s seen=%s exec=%s roles=%s'%(cid,source is not None,cid in seen,bool(observation.get('execution_error')),sorted(observation.get('responses',{}))))
        seen.add(cid)
        responses=observation['responses']
        expected=source['targets'];reference=json.loads(responses['reference']['raw_json'])['outputs'];candidate=json.loads(responses['candidate']['raw_json'])['outputs']
        if digest(reference)!=digest(expected) or set(candidate)!=set(expected):raise ValueError('Reference/target output signature mismatch')
        for key,target in expected.items():
            value=candidate[key]
            if matrix_shape(value)!=matrix_shape(target):raise ValueError('Executed prototype output shape changed')
            for i,row in enumerate(target):
                for j,t in enumerate(row):
                    v=value[i][j];errors.append((float(v)-float(t))**2)
                    if task['constraints']['nonnegative_outputs'] and v<0:violations.append(cid+': negative output '+key)
    value=sum(errors)/len(errors) if task['objective']['metric']=='mse' else math.sqrt(max(errors))
    if not math.isfinite(value):raise ValueError('Nonfinite objective metric')
    return {'metric':value,'cases':len(wanted),'constraint_violations':violations,'comparison_status':replay['status'],
            'scope':'Declared finite samples only; equalities and constraints are not universal guarantees'}

def _evaluate(prototype_path,task,data,split,out,tag):
    prototype=verify_prototype(prototype_path,expected_task_hash=digest(task));root=Path(out).resolve()
    ref=root/'reference.py'
    if ref.read_text(encoding='utf8')!=REFERENCE:raise ValueError('Target reference adapter changed')
    cases=[{'id':row['id'],'input':{'inputs':row['inputs'],'targets':row['targets']},'checks':['outputs']} for row in data if row['split']==split]
    spec={'id':tag,'target_id':task['task_id'],'target_snapshot_hash':prototype['model_hash'],
          'reference':{'path':'reference.py','sha256':file_hash(ref)},'candidate':adapter_reference(prototype_path,root),
          'cases':cases,'atol':1e-12,'rtol':0.,'timeout_seconds':3,'total_timeout_seconds':60,'repetitions':1}
    receipt=run_experiment(spec,root,execute=True)
    path=root/'receipts'/(tag+'.json');atomic_write(path,receipt);receipt=read_json(path)
    summary=_summary(receipt,task,data,split)
    summary.update(receipt_path=path.relative_to(root).as_posix(),receipt_sha256=file_hash(path),model_hash=prototype['model_hash'])
    return summary

def _train_candidate(candidate_model, task, task_path, root, index):
    config=task.get('training')
    if not config or not config.get('enabled'):
        return candidate_model, None
    receipt_path=root/'training'/('attempt-%02d.json'%index);receipt_path.parent.mkdir(parents=True,exist_ok=True)
    trained=train_ir(copy.deepcopy(candidate_model),task_path,receipt_path,config['epochs'],config['learning_rate'])
    allowed=set(config['trainable_parameter_ids'])
    if set(trained['trainable_parameter_ids'])!=allowed:
        raise ValueError('Training receipt trainable parameter set differs from task contract')
    return trained['model'], {'path':receipt_path.relative_to(root).as_posix(),'sha256':file_hash(receipt_path),'final_metric':trained['final_metric'],'model_hash':trained['final_model_hash']}

def _benchmark_model(model, task, root, index):
    config=task.get('benchmark')
    if not config:
        return []
    results=[]
    for device in config['devices']:
        measured=benchmark_ir(model,task,device,config['repetitions'],config['warmup'])
        path=root/'benchmarks'/('attempt-%02d-%s.json'%(index,device));path.parent.mkdir(parents=True,exist_ok=True);atomic_write(path,measured)
        measured=dict(measured);measured.update(path=path.relative_to(root).as_posix(),sha256=file_hash(path));results.append(measured)
    return results

def _replay_benchmarks(root, attempt, task):
    config=task.get('benchmark')
    records=attempt.get('benchmarks',[])
    if not config:
        if records: raise ValueError('Benchmark receipts present without benchmark contract')
        return
    if len(records)!=len(config['devices']): raise ValueError('Benchmark receipt coverage differs from task contract')
    by={r.get('device'):r for r in records}
    if set(by)!=set(config['devices']): raise ValueError('Benchmark device coverage differs from task contract')
    for device,record in by.items():
        path=(root/record.get('path','')).resolve()
        if root not in path.parents or file_hash(path)!=record.get('sha256'): raise ValueError('Benchmark receipt changed or escaped bundle')
        raw=read_json(path)
        if raw.get('device')!=device or raw.get('repetitions')!=config['repetitions'] or raw.get('warmup')!=config['warmup'] or raw.get('status')!=record.get('status'):
            raise ValueError('Benchmark receipt contract mismatch')

def _decide(summary,baseline,task):
    goal=task['objective']
    rule={'metric_id':goal['metric'],'condition_id':'fixed_task','aggregation':'mean','min_seeds':2,'expression':'candidate','operator':'gt','threshold':{'value':goal['maximum'],'unit':'1'}}
    pending=evaluate_decision(rule,{'id':goal['metric'],'unit':'1'})
    if pending['status']!='pending':raise ValueError('Unexpected decision schema state')
    return not summary['constraint_violations'] and summary['metric']<=goal['maximum'] and baseline-summary['metric']>=goal['min_improvement']

def _save(root,result):atomic_write(Path(root)/'result.json',result);return result

def run_loop(task_path,initial_model_path,output,execute=False,repairs=None,input_hash=None,upstream_artifacts=None):
    task_path=Path(task_path).resolve();task=load_task(task_path);locked=digest(task);data=load_dataset(task,task_path.parent)
    model=read_json(initial_model_path);validate_ir(model,task);repairs=list(repairs or ['relu','absolute'])
    if len(repairs)>8 or any(r not in ('relu','absolute') for r in repairs):raise ValueError('Use bounded supported repair rules')
    out=Path(output).resolve()
    if out.exists():raise ValueError('Choose a new loop output directory; never overwrite earlier failed experiments')
    # Create a portable immutable-in-practice target snapshot; compare hashes before every experiment.
    out.mkdir(parents=True);inputs=out/'inputs';inputs.mkdir()
    atomic_write(inputs/'task.json',task)
    destination=(inputs/task['dataset']['path']).resolve()
    if destination in (inputs/'task.json',inputs/'initial.json'):raise ValueError('Dataset path collides with contract artifacts')
    destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(task_path.parent/task['dataset']['path'],destination)
    atomic_write(inputs/'initial.json',model);(out/'reference.py').write_text(REFERENCE,encoding='utf8')
    result={'schema_version':'1.0','artifact_kind':'design_loop','task_hash':locked,'initial_model_hash':semantic_hash(model),'task_path':'inputs/task.json','initial_path':'inputs/initial.json',
            'task_input_hash':input_hash,'upstream_artifacts':upstream_artifacts or [],'repairs':repairs,'status':'planned','attempts':[],'holdout':None,'events':[],'lifecycle':make_receipt('forward',['task','inputs'],['development_receipts','holdout_receipts'],['model_state'],status='planned',contract_hash=locked),
            'scope_limits':['Bounded deterministic forward graph search; training is enabled only when the task contract explicitly declares scalar trainable parameters.',
                            'Finite task samples and literal static shapes only; no generalization, speed or theorem guarantee.',
                            'Local execution receipts are replayable records, not cryptographic execution attestations.']}
    initial_path=out/'prototype-00'/'prototype.json';build_prototype(model,task_path,initial_path.parent)
    result['initial_prototype']='prototype-00/prototype.json';_save(out,result)
    if not execute:return result
    candidates=[{'rule':'initial','model':model,'eligible':True,'parent_hash':None}];baseline_dev=None;selected=None
    index=0
    while index<len(candidates) and len(result['attempts'])<task['budgets']['max_candidates']:
        load_task(task_path,expected_hash=locked);load_task(inputs/'task.json',expected_hash=locked)
        candidate=candidates[index];index+=1
        if not candidate['eligible']:
            result['events'].append({'event':'candidate_blocked','rule':candidate['rule'],'reason':candidate['reason']});continue
        n=len(result['attempts']);prototype_path=(out/'prototype-trained-00'/'prototype.json') if (n==0 and task.get('training',{}).get('enabled')) else (initial_path if n==0 else out/('prototype-%02d'%n)/'prototype.json')
        trained_model,training_receipt=_train_candidate(candidate['model'],task,task_path,out,n)
        if training_receipt:
            build_prototype(trained_model,task_path,prototype_path.parent)
        elif n:
            build_prototype(trained_model,task_path,prototype_path.parent)
        measured=_evaluate(prototype_path,task,data,'development',out,'attempt-%02d-development'%n)
        benchmark_receipts=_benchmark_model(trained_model,task,out,n)
        if baseline_dev is None:baseline_dev=measured['metric']
        acceptable=_decide(measured,baseline_dev,task)
        attempt={'index':n,'rule':candidate['rule'],'parent_hash':candidate['parent_hash'],'model_hash':semantic_hash(trained_model),
                 'proposal_model_hash':semantic_hash(candidate['model']),'prototype_path':prototype_path.relative_to(out).as_posix(),'prototype_sha256':file_hash(prototype_path),'development':measured,
                 'training':training_receipt,'benchmarks':benchmark_receipts,
                 'decision':'select_for_holdout' if acceptable else 'revise','reason':'Target threshold, improvement and sampled constraints satisfied' if acceptable else 'Development objective or sampled constraints failed'}
        result['attempts'].append(attempt);result['events'].append({'event':attempt['decision'],'index':n,'metric':measured['metric'],'task_hash':locked});_save(out,result)
        if acceptable:selected=attempt;break
        if n==0:
            # Structural repair generation sees only model/task, never holdout records or targets.
            candidates.extend(propose_repairs(model,task,repairs))
            result['events'].append({'event':'repair_candidates_generated_after_failure','parent_hash':semantic_hash(model),'rules':repairs,'data_access':'none; only model and fixed task contract'})
    if selected is None:
        result['status']='budget_exhausted' if len(result['attempts'])>=task['budgets']['max_candidates'] else 'no_viable_candidate'
        return _save(out,result)
    load_task(task_path,expected_hash=locked)
    baseline_holdout=_evaluate(initial_path,task,data,'holdout',out,'baseline-holdout')
    candidate_holdout=baseline_holdout if selected['index']==0 else _evaluate(out/selected['prototype_path'],task,data,'holdout',out,'selected-holdout')
    accepted=_decide(candidate_holdout,baseline_holdout['metric'],task)
    result['holdout']={'baseline':baseline_holdout,'candidate':candidate_holdout,'baseline_metric':baseline_holdout['metric'],'candidate_metric':candidate_holdout['metric'],
                       'selected_model_hash':selected['model_hash'],'evaluated_once':True,'search_terminated':True}
    result['status']='accepted' if accepted else 'holdout_failed';result['events'].append({'event':result['status'],'holdout_repair_allowed':False})
    load_task(task_path,expected_hash=locked)
    return _save(out,result)

def _replay_summary(root,summary,task,data,split,prototype_path):
    path=root/summary['receipt_path']
    if root not in path.resolve().parents or file_hash(path)!=summary['receipt_sha256']:raise ValueError('Loop receipt changed or escaped bundle')
    receipt=read_json(path);manifest=verify_prototype(prototype_path,expected_task_hash=digest(task),expected_model_hash=summary['model_hash'])
    spec=receipt['spec']
    if spec['target_snapshot_hash']!=manifest['model_hash'] or spec['target_id']!=task['task_id']:raise ValueError('Receipt target model/contract mismatch')
    expected_cases=[{'id':r['id'],'input':{'inputs':r['inputs'],'targets':r['targets']},'checks':['outputs']} for r in data if r['split']==split]
    if digest(spec['cases'])!=digest(expected_cases) or spec['candidate']!=adapter_reference(prototype_path,root):raise ValueError('Receipt cases/adapter are not from frozen task')
    if (root/'reference.py').read_text(encoding='utf8')!=REFERENCE or spec['reference']!={'path':'reference.py','sha256':file_hash(root/'reference.py')}:raise ValueError('Target reference adapter mismatch')
    validate_spec(spec,root);recomputed=_summary(receipt,task,data,split)
    for key,value in recomputed.items():
        if summary.get(key)!=value:raise ValueError('Metric/constraint summary differs from raw-response replay: '+key)
    return recomputed

def replay_loop(path):
    path=Path(path).resolve();root=path.parent;record=read_json(path)
    schema=read_json(Path(__file__).resolve().parents[1]/'assets/design-loop.schema.json')
    errors=list(Draft4Validator(schema).iter_errors(record))
    if errors:raise ValueError('Design loop schema: '+errors[0].message)
    initial_proto=(root/record['initial_prototype']).resolve()
    if root not in initial_proto.parents:raise ValueError('Initial prototype escapes run directory')
    task_path=(root/record['task_path']).resolve();initial=(root/record['initial_path']).resolve()
    if root not in task_path.parents or root not in initial.parents:raise ValueError('Loop input path escapes bundle')
    task=load_task(task_path,record['task_hash']);data=load_dataset(task,task_path.parent);model=read_json(initial)
    validate_ir(model,task)
    if semantic_hash(model)!=record['initial_model_hash']:raise ValueError('Initial model changed')
    verify_prototype(root/record['initial_prototype'],record['task_hash'],record['initial_model_hash'])
    if record.get('lifecycle'): validate_receipt(record['lifecycle'],'forward')
    if record['status']=='planned':
        if record['attempts'] or record['holdout']:raise ValueError('Planned result cannot contain execution outcomes')
        return {'status':'planned','executed':False}
    proposals=[{'rule':'initial','model':model,'eligible':True,'parent_hash':None}]+[p for p in propose_repairs(model,task,record['repairs']) if p['eligible']]
    if not record['attempts'] or len(record['attempts'])>task['budgets']['max_candidates'] or len(record['attempts'])>len(proposals):raise ValueError('Loop attempt budget/coverage mismatch')
    selected=None;baseline=None
    for i,attempt in enumerate(record['attempts']):
        expected=proposals[i];proto=(root/attempt['prototype_path']).resolve()
        if root not in proto.parents or file_hash(proto)!=attempt['prototype_sha256']:raise ValueError('Prototype manifest changed')
        if attempt['index']!=i or attempt.get('proposal_model_hash',attempt['model_hash'])!=semantic_hash(expected['model']) or attempt['rule']!=expected['rule'] or attempt['parent_hash']!=expected['parent_hash']:raise ValueError('Attempt is not a permitted structural repair')
        replay_model=expected['model']
        config=task.get('training')
        if config and config.get('enabled'):
            tr=attempt.get('training')
            if not tr: raise ValueError('Missing training receipt')
            tr_path=(root/tr['path']).resolve()
            if root not in tr_path.parents or file_hash(tr_path)!=tr['sha256']: raise ValueError('Training receipt changed or escaped bundle')
            replayed=train_ir(copy.deepcopy(expected['model']),root/'inputs/task.json', None,config['epochs'],config['learning_rate'])
            if replayed['final_model_hash']!=tr['model_hash'] or replayed['final_model_hash']!=attempt['model_hash']: raise ValueError('Training replay differs from recorded model')
            replay_model=replayed['model']
        elif attempt['model_hash']!=semantic_hash(expected['model']): raise ValueError('Attempt model is not a permitted structural repair')
        if semantic_hash(replay_model)!=attempt['model_hash']: raise ValueError('Attempt model hash mismatch')
        _replay_benchmarks(root,attempt,task)
        summary=_replay_summary(root,attempt['development'],task,data,'development',proto)
        if baseline is None:baseline=summary['metric']
        good=_decide(summary,baseline,task)
        if attempt['decision']!=('select_for_holdout' if good else 'revise'):raise ValueError('Development decision changed')
        if good:
            if i!=len(record['attempts'])-1:raise ValueError('Search continued after selection')
            selected=attempt
    if selected is None:
        expected='budget_exhausted' if len(record['attempts'])>=task['budgets']['max_candidates'] else 'no_viable_candidate'
        if record['holdout'] is not None or record['status']!=expected:raise ValueError('Failed search claims unsupported outcome')
        return {'status':expected,'executed':True,'attempts':len(record['attempts'])}
    holdout=record['holdout']
    if not holdout or not holdout['evaluated_once'] or not holdout['search_terminated'] or holdout['selected_model_hash']!=selected['model_hash']:raise ValueError('Holdout selection record mismatch')
    b=_replay_summary(root,holdout['baseline'],task,data,'holdout',root/record['initial_prototype'])
    c=_replay_summary(root,holdout['candidate'],task,data,'holdout',root/selected['prototype_path'])
    if holdout['baseline_metric']!=b['metric'] or holdout['candidate_metric']!=c['metric']:raise ValueError('Holdout metric changed')
    status='accepted' if _decide(c,b['metric'],task) else 'holdout_failed'
    if status!=record['status']:raise ValueError('Final decision differs from replay')
    return {'status':status,'executed':True,'attempts':len(record['attempts']),'scope':'Finite development/heldout records, no generalization proof'}

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='cmd',required=True)
    a=sub.add_parser('run');a.add_argument('--task',required=True);a.add_argument('--initial',required=True);a.add_argument('-o','--output',required=True);a.add_argument('--execute',action='store_true');a.add_argument('--repairs',nargs='+',choices=['relu','absolute'],default=['relu','absolute'])
    a.add_argument('--input-hash');a.add_argument('--upstream',help='JSON upstream task_id/sha256 array')
    a=sub.add_parser('replay');a.add_argument('result')
    a=p.parse_args()
    try:result=run_loop(a.task,a.initial,a.output,a.execute,a.repairs,a.input_hash,read_json(a.upstream) if a.upstream else None) if a.cmd=='run' else replay_loop(a.result)
    except (ValueError,OSError,KeyError,TypeError) as exc:p.error(str(exc))
    print(json.dumps({'status':result['status'],'attempts':len(result.get('attempts',[])) if isinstance(result.get('attempts'),list) else result.get('attempts',0)}))
if __name__=='__main__':main()









