# -*- coding: utf-8 -*-
"""Explicit local-adapter comparisons. Subprocess limits are NOT a security sandbox."""
import argparse,hashlib,json,math,os,subprocess,sys,tempfile,time
from pathlib import Path
from datetime import datetime,timezone
from evidence_snapshots import bundled_path

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')).hexdigest()
def file_hash(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def verify_adapter(adapter,root):
    path=bundled_path(root,adapter['path'])
    if path.suffix!='.py' or file_hash(path)!=adapter['sha256']:raise ValueError('Adapter missing, non-Python or content changed: '+adapter['path'])
    for item in adapter.get('dependencies',[]):
        if file_hash(bundled_path(root,item['path']))!=item['sha256']:raise ValueError('Adapter dependency changed: '+item['path'])
    return path

def validate_spec(spec,root):
    for key in ('id','target_id','target_snapshot_hash'):
        if not isinstance(spec.get(key),str) or not spec[key].strip():raise ValueError('Missing experiment '+key)
    if len(spec['target_snapshot_hash'])!=64:raise ValueError('Invalid target snapshot hash')
    paths={key:verify_adapter(spec[key],root) for key in ('reference','candidate')}
    cases=spec.get('cases',[])
    if not isinstance(cases,list) or not 1<=len(cases)<=30:raise ValueError('Use 1..30 declared cases')
    ids=set()
    for case in cases:
        if not case.get('id') or case['id'] in ids:raise ValueError('Unique case IDs required')
        ids.add(case['id'])
        if not isinstance(case.get('checks'),list) or not case['checks'] or set(case['checks'])-{'outputs','state','gradients'}:raise ValueError('Specify outputs/state/gradients checks')
        if 'input' not in case or len(json.dumps(case['input'],allow_nan=False).encode())>131072:raise ValueError('Case input missing or too large')
    for key in ('atol','rtol'):
        value=spec.get(key)
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<=value<=1:raise ValueError('Finite explicit tolerances in [0,1] required')
    timeout=spec.get('timeout_seconds',3)
    if isinstance(timeout,bool) or not isinstance(timeout,(int,float)) or not 0.05<=timeout<=15:raise ValueError('timeout_seconds must be 0.05..15')
    total=spec.get('total_timeout_seconds',30)
    if isinstance(total,bool) or not isinstance(total,(int,float)) or not math.isfinite(total) or not 0.1<=total<=120:raise ValueError('total_timeout_seconds must be finite in 0.1..120')
    repetitions=spec.get('repetitions',1)
    if type(repetitions)!=int or not 1<=repetitions<=5:raise ValueError('repetitions must be 1..5')
    if len(cases)*repetitions>60:raise ValueError('Case/repetition budget exceeded')
    return paths

def invoke(path,input_value,timeout,root):
    # No shell or environment credentials. -I excludes cwd/PYTHONPATH auto imports.
    # Adapters can explicitly load reviewed code; neither -I nor cwd confines file/network access.
    env={key:value for key,value in os.environ.items() if key.upper() in ('SYSTEMROOT','WINDIR','TEMP','TMP','PATH')}
    with tempfile.TemporaryDirectory(prefix='anatomy-experiment-') as tmp:
        directory=Path(tmp);input_path=directory/'input.json'
        input_path.write_bytes(json.dumps(input_value,allow_nan=False).encode('utf-8'))
        with input_path.open('rb') as source,(directory/'stdout').open('w+b') as out,(directory/'stderr').open('w+b') as err:
            start=time.perf_counter()
            child=subprocess.Popen([sys.executable,'-I','-B',str(path)],stdin=source,stdout=out,stderr=err,cwd=str(directory),env=env)
            try:
                while child.poll() is None:
                    if time.perf_counter()-start>timeout:raise ValueError('Adapter timeout')
                    if os.fstat(out.fileno()).st_size+os.fstat(err.fileno()).st_size>2*1024*1024:raise ValueError('Adapter output budget exceeded')
                    time.sleep(0.01)
                elapsed=time.perf_counter()-start
                if child.returncode!=0:raise ValueError('Adapter exit '+str(child.returncode))
                out.seek(0);body=out.read(2*1024*1024+1)
                if len(body)>2*1024*1024:raise ValueError('Adapter response too large')
                try:value=json.loads(body.decode('utf-8'))
                except (ValueError,UnicodeError):raise ValueError('Adapter must emit exactly one UTF-8 JSON response')
                if not isinstance(value,dict):raise ValueError('Adapter response must be an object')
                return value,{'wall_seconds_including_startup':elapsed,'response_sha256':hashlib.sha256(body).hexdigest(),'raw_json':body.decode('utf-8')}
            finally:
                if child.poll() is None:child.kill()
                child.wait()

def compare(reference,candidate,atol,rtol,path='$'):
    if isinstance(reference,dict):
        if not isinstance(candidate,dict) or set(reference)!=set(candidate):return [path+': object keys differ']
        return [error for key in reference for error in compare(reference[key],candidate[key],atol,rtol,path+'.'+str(key))]
    if isinstance(reference,list):
        if not isinstance(candidate,list) or len(reference)!=len(candidate):return [path+': shape differs']
        return [error for i,(a,b) in enumerate(zip(reference,candidate)) for error in compare(a,b,atol,rtol,path+'['+str(i)+']')]
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in (reference,candidate)):
        return [path+': expected finite numeric leaves']
    return [] if abs(reference-candidate)<=atol+rtol*abs(reference) else [path+': numeric mismatch']

def run_experiment(spec,bundle_root,execute=False):
    root=Path(bundle_root).resolve();paths=validate_spec(spec,root)
    result={'id':spec['id'],'target_id':spec['target_id'],'target_snapshot_hash':spec['target_snapshot_hash'],
        'spec':spec,'spec_hash':digest(spec),'status':'planned','comparisons_completed':0,'observations':[],'errors':[],
        'observed_at':datetime.now(timezone.utc).isoformat(),
        'runtime':{'python':sys.version,'executable_sha256':file_hash(sys.executable)},
        'limits':['Only the declared cases and adapters were compared; this is not universal equivalence',
                  'Wall times include process startup; no kernel speedup claim',
                  'Subprocess limits are not an OS sandbox; undeclared dependencies and child processes are not confined']}
    if not execute:return result
    deadline=time.perf_counter()+min(float(spec.get('total_timeout_seconds',30)),120)
    for repeat in range(spec.get('repetitions',1)):
        for case in spec['cases']:
            entry={'case_id':case['id'],'repeat':repeat,'responses':{}}
            try:
                responses={}
                for name in ('reference','candidate'):
                    remaining=deadline-time.perf_counter()
                    if remaining<=0:raise ValueError('Total experiment time budget exceeded')
                    value,receipt=invoke(paths[name],case['input'],min(spec.get('timeout_seconds',3),remaining),root)
                    responses[name]=value;entry['responses'][name]=dict(receipt,value=value)
                errors=[]
                for key in case['checks']:
                    if key not in responses['reference'] or key not in responses['candidate']:errors.append(key+': requested observable missing')
                    else:errors.extend(compare(responses['reference'][key],responses['candidate'][key],spec['atol'],spec['rtol'],key))
                result['comparisons_completed']+=1
                result['errors'].extend(case['id']+': '+message for message in errors)
            except (ValueError,OSError) as exc:result['errors'].append(case['id']+': '+str(exc))
            if 'reference' not in entry['responses'] or 'candidate' not in entry['responses']:entry['execution_error']=result['errors'][-1] if result['errors'] else 'Incomplete execution'
            result['observations'].append(entry)
            if time.perf_counter()>=deadline:break
        if time.perf_counter()>=deadline:break
    expected=len(spec['cases'])*spec.get('repetitions',1)
    if result['comparisons_completed']!=expected:result['errors'].append('Not all declared comparisons completed')
    # Detect adapter mutation during execution as well as stale pre-run receipts.
    for name in ('reference','candidate'):
        try:verify_adapter(spec[name],root)
        except ValueError as exc:result['errors'].append(str(exc))
    result['status']='failed' if result['errors'] else 'passed'
    return result

def replay_receipt(record):
    """Verify saved raw bytes and recompute every declared observable without executing adapters."""
    spec=record['spec']
    if digest(spec)!=record.get('spec_hash') or record.get('id')!=spec['id'] or record.get('target_id')!=spec['target_id'] or record.get('target_snapshot_hash')!=spec['target_snapshot_hash']:raise ValueError('Receipt identity/spec binding changed')
    # Validate budgets and types without requiring the original adapter location.
    for key in ('atol','rtol'):
        if isinstance(spec[key],bool) or not isinstance(spec[key],(int,float)) or not math.isfinite(spec[key]) or spec[key]<0:raise ValueError('Invalid replay tolerance')
    cases=spec['cases'];repetitions=spec.get('repetitions',1)
    if not 1<=len(cases)<=30 or type(repetitions)!=int or not 1<=repetitions<=5 or len(cases)*repetitions>60:raise ValueError('Replay budget exceeded')
    if len({c['id'] for c in cases})!=len(cases):raise ValueError('Duplicate declared cases')
    bycase={c['id']:c for c in cases};expected_keys={(c['id'],repeat) for repeat in range(repetitions) for c in cases}
    observations=record.get('observations',[]);seen=set();errors=[];completed=0
    if len(observations)>len(expected_keys):raise ValueError('Too many replay observations')
    for observation in observations:
        repeat=observation.get('repeat')
        if type(repeat)!=int:raise ValueError('Repeat index must be an integer')
        key=(observation.get('case_id'),repeat)
        if key not in expected_keys or key in seen:raise ValueError('Unknown or duplicate case/repetition observation')
        seen.add(key);case=bycase[key[0]];responses=observation.get('responses',{})
        if not isinstance(responses,dict) or set(responses)-{'reference','candidate'}:raise ValueError('Invalid response roles')
        for name,response in responses.items():
            raw=response.get('raw_json')
            if not isinstance(raw,str) or len(raw.encode('utf-8'))>2*1024*1024:raise ValueError('Receipt lacks bounded raw JSON bytes; rerun old experiments')
            if hashlib.sha256(raw.encode('utf-8')).hexdigest()!=response.get('response_sha256'):raise ValueError('Raw response hash mismatch')
            try:parsed=json.loads(raw)
            except ValueError:raise ValueError('Saved raw response is not JSON')
            if not isinstance(parsed,dict) or digest(parsed)!=digest(response.get('value')):raise ValueError('Saved response value differs from raw JSON')
        if set(responses)!={'reference','candidate'}:
            message=observation.get('execution_error')
            if not isinstance(message,str) or not message.strip():raise ValueError('Missing responses require explicit execution failure')
            errors.append(case['id']+': '+message);continue
        if observation.get('execution_error'):raise ValueError('Complete comparison cannot carry an execution error')
        checks=case['checks']
        if not checks or set(checks)-{'outputs','state','gradients'}:raise ValueError('Invalid observable checks')
        for observable in checks:
            a=responses['reference']['value'];b=responses['candidate']['value']
            if observable not in a or observable not in b:errors.append(case['id']+': '+observable+': requested observable missing')
            else:errors.extend(case['id']+': '+message for message in compare(a[observable],b[observable],spec['atol'],spec['rtol'],observable))
        completed+=1
    if seen!=expected_keys or completed!=len(expected_keys):errors.append('Not all declared comparisons completed')
    return {'status':'failed' if errors else 'passed','comparisons_completed':completed,'errors':errors,
        'replayed_from':record.get('id'),'limitation':'Raw response hashes plus arithmetic replay detect inconsistent records, not forged execution history'}

def check_experiment_receipts(data,rep,bundle_root):
    from repository_coverage import target_hash
    targets={p['id']:p for p in data.get('proposals',[])};seen=set()
    for item in data.get('implementation_experiments',[]):
        try:
            path=bundled_path(bundle_root,item['receipt_path'])
            if file_hash(path)!=item['sha256']:raise ValueError('Experiment receipt file changed')
            result=json.loads(path.read_text(encoding='utf-8-sig'));spec=result['spec']
            if result['id'] in seen:raise ValueError('Duplicate experiment id')
            seen.add(result['id'])
            if digest(spec)!=result['spec_hash'] or spec['target_id']!=item['target_id']:raise ValueError('Experiment spec/target mismatch')
            if item['target_id'] not in targets or result['target_snapshot_hash']!=target_hash(data,targets[item['target_id']]):raise ValueError('Experiment target/interface changed')
            validate_spec(spec,bundle_root)
            replay=replay_receipt(result)
            if result['status']!=replay['status'] or result['comparisons_completed']!=replay['comparisons_completed']:raise ValueError('Stored experiment status/count disagrees with raw-response replay')
            if result['status']=='passed' and (result['errors'] or replay['errors']):raise ValueError('Passing receipt hides comparison errors')
        except (KeyError,ValueError,OSError,TypeError) as exc:rep.err('implementation_experiments',str(exc))
    return {'receipts':len(seen),'limitation':'Local receipts detect changes but do not attest that external executions were genuine'}

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('spec');ap.add_argument('--bundle');ap.add_argument('--replay',action='store_true',help='Recompute stored receipt without running code')
    ap.add_argument('--execute',action='store_true',help='Explicitly run the reviewed local adapters; not a security sandbox')
    ap.add_argument('-o','--output',required=True);a=ap.parse_args(argv);target=Path(a.output)
    if target.exists():ap.error('Choose a new output file')
    try:
        source=json.loads(Path(a.spec).read_text(encoding='utf-8-sig'))
        if a.replay and a.execute:raise ValueError('Choose replay or execute')
        result=replay_receipt(source) if a.replay else run_experiment(source,a.bundle or Path(a.spec).resolve().parent,a.execute)
    except (ValueError,KeyError,OSError,TypeError) as exc:ap.error(str(exc))
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(result['status'])
    return 1 if result['status']=='failed' else 0
if __name__=='__main__':raise SystemExit(main())
