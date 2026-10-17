# -*- coding: utf-8 -*-
"""Deterministic, resumable multi-agent orchestration primitives."""
from __future__ import annotations
import argparse, copy, hashlib, json, os, tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def now(): return datetime.now(timezone.utc).isoformat()

def _tid(task): return task.get('id') or task.get('task_id')

def build_batches(tasks):
    tasks=[copy.deepcopy(t) for t in tasks]; ids=[_tid(t) for t in tasks]
    if any(not isinstance(i,str) or not i for i in ids) or len(set(ids))!=len(ids): raise ValueError('Tasks need unique nonempty ids')
    by={_tid(t):t for t in tasks}
    for t in tasks:
        deps=t.get('depends_on',[]) or []
        if not isinstance(deps,list) or any(d not in by for d in deps): raise ValueError('Missing task dependency for '+_tid(t))
    done=set(); batches=[]
    while len(done)<len(tasks):
        ready=[t for t in tasks if _tid(t) not in done and all(d in done for d in (t.get('depends_on',[]) or []))]
        if not ready: raise ValueError('Task dependency cycle detected')
        # Preserve caller order for deterministic review priority; dependency readiness is the only ordering constraint.
        batches.append(ready); done.update(_tid(t) for t in ready)
    return batches

def _normalize(result,task,attempt):
    if not isinstance(result,dict): raise ValueError('Agent result must be an object')
    out=copy.deepcopy(result); out.setdefault('task_id',_tid(task)); out.setdefault('attempt',attempt)
    if out['task_id']!=_tid(task): raise ValueError('Agent result task_id mismatch')
    if out.get('status') not in ('completed','failed','needs_human','unavailable','blocked'): raise ValueError('Unknown agent result status')
    return out

def execute_schedule(tasks,runner,max_workers=4,max_retries=0):
    batches=build_batches(tasks); results={}; pending=set(_tid(t) for t in tasks); handoffs={}; errors={}
    for batch in batches:
        runnable=[t for t in batch if all(d in results for d in (t.get('depends_on',[]) or []))]
        if len(runnable)!=len(batch):
            return {'status':'blocked','results':results,'pending':sorted(pending-set(results)),'human_handoffs':handoffs,'errors':errors}
        def one(task):
            last=None
            for attempt in range(1,max_retries+2):
                try:
                    value=_normalize(runner(task,attempt),task,attempt)
                    if value['status']=='failed' and attempt<=max_retries: last=value; continue
                    return value
                except Exception as exc:
                    last={'task_id':_tid(task),'status':'failed','attempt':attempt,'error':str(exc)}
                    if attempt<=max_retries: continue
                    return last
            return last
        with ThreadPoolExecutor(max_workers=max(1,int(max_workers))) as pool:
            futures={pool.submit(one,t):t for t in runnable}
            batch_results=[f.result() for f in as_completed(futures)]
        for result in sorted(batch_results,key=lambda x:x['task_id']):
            tid=result['task_id']
            if result['status']=='completed': results[tid]=result; pending.discard(tid)
            elif result['status']=='needs_human': handoffs[tid]=result; pending.discard(tid)
            else: errors[tid]=result; pending.discard(tid)
        if handoffs:
            descendants={_tid(t):set(t.get('depends_on',[]) or []) for t in tasks}
            blocked=set(handoffs)
            changed=True
            while changed:
                changed=False
                for tid,deps in descendants.items():
                    if tid not in blocked and deps & blocked: blocked.add(tid); changed=True
            return {'status':'needs_human','results':results,'pending':sorted(pending & blocked),'human_handoffs':handoffs,'errors':errors}
        if errors:
            return {'status':'failed','results':results,'pending':sorted(pending),'human_handoffs':handoffs,'errors':errors}
    return {'status':'completed','results':results,'pending':[],'human_handoffs':handoffs,'errors':errors}

def merge_agent_results(results):
    merged={'results':{},'provenance':[]}
    for item in results:
        if not isinstance(item,dict) or not item.get('task_id'): raise ValueError('Result requires task_id')
        tid=item['task_id']; clean=copy.deepcopy(item)
        if tid in merged['results']:
            if digest(merged['results'][tid])!=digest(clean): raise ValueError('Conflicting result for task '+tid)
            continue
        merged['results'][tid]=clean
        merged['provenance'].append({'task_id':tid,'agent':clean.get('agent'),'input_hash':clean.get('input_hash'),'output_hash':digest(clean)})
    return merged

def atomic_write(path,value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=path.name+'.',dir=str(path.parent)); os.close(fd)
    try: Path(tmp).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def init_state(anatomy_path,tasks,run_id=None):
    path=Path(anatomy_path); return {'schema_version':'1.0','run_id':run_id or 'run:'+digest({'path':str(path.resolve()),'time':now()})[:16],'anatomy_path':str(path.resolve()),'anatomy_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'phase':'INIT','phase_status':'pending','tasks':tasks,'receipts':[],'blockers':[],'events':[]}

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__); sub=ap.add_subparsers(dest='cmd',required=True)
    p=sub.add_parser('init');p.add_argument('anatomy');p.add_argument('-o','--output',required=True);p.add_argument('--tasks',required=True)
    p=sub.add_parser('next');p.add_argument('state');p.add_argument('-o','--output',required=True)
    p=sub.add_parser('submit');p.add_argument('state');p.add_argument('--response',required=True);p.add_argument('-o','--output',required=True)
    p=sub.add_parser('status');p.add_argument('state')
    a=ap.parse_args(argv)
    if a.cmd=='init': atomic_write(a.output,init_state(a.anatomy,json.loads(Path(a.tasks).read_text(encoding='utf-8')))); print(a.output)
    elif a.cmd=='status': print(json.dumps(json.loads(Path(a.state).read_text(encoding='utf-8')),ensure_ascii=False,indent=2))
    elif a.cmd=='submit':
        state=json.loads(Path(a.state).read_text(encoding='utf-8')); response=json.loads(Path(a.response).read_text(encoding='utf-8')); submitted=response if isinstance(response,list) else response.get('results',[])
        by={t.get('id') or t.get('task_id'):t for t in state['tasks']}
        for item in submitted:
            tid=item.get('task_id'); task=by.get(tid)
            if task is None: raise SystemExit('Unknown host task: '+str(tid))
            if item.get('input_hash') and task.get('input_hash') and item['input_hash']!=task['input_hash']: raise SystemExit('Stale host response: '+tid)
            task['status']=item.get('status','completed'); task['artifact_path']=item.get('artifact_path'); task['updated_at']=now()
            state['events'].append({'event':'host_submitted','task_id':tid,'at':now(),'input_hash':item.get('input_hash')})
        state['phase_status']='pending' if all(t.get('status')=='completed' for t in state['tasks']) else 'waiting_host'; atomic_write(a.output,state); print(a.output)
    else:
        state=json.loads(Path(a.state).read_text(encoding='utf-8')); pending=[t for t in state['tasks'] if t.get('status','pending')=='pending']; batch=build_batches(pending)[0] if pending else []; out={'action':'request_host' if any(t.get('executor','host')=='host' for t in batch) else ('complete' if not batch else 'run_local'),'tasks':batch,'run_id':state['run_id'],'anatomy_sha256':state['anatomy_sha256']}; atomic_write(a.output,out); print(a.output)
if __name__=='__main__': main()
