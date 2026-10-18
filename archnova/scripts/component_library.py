# -*- coding: utf-8 -*-
"""Validate and index reusable operator records, without executing implementations."""
import argparse
import copy
import json
from pathlib import Path
from jsonschema import Draft4Validator
from orchestrator import atomic_write, digest

SCHEMA = Path(__file__).resolve().parents[1]/'assets'/'component-schema.json'

def validate_component(record):
    schema = json.loads(SCHEMA.read_text(encoding='utf-8'))
    errors = sorted(Draft4Validator(schema).iter_errors(record), key=lambda e: str(list(e.path)))
    if errors:
        raise ValueError('Invalid component: ' + '; '.join(str(list(e.path)) + ': ' + e.message for e in errors))
    ids = [p['id'] for p in record['ports']]
    if len(ids) != len(set(ids)): raise ValueError('Duplicate component port id')
    if not any(p['direction']=='input' for p in record['ports']) or not any(p['direction']=='output' for p in record['ports']):
        raise ValueError('Component requires input and output ports')
    for p in record['ports']:
        if p['owner'] != record['component_id'] or len(p['shape']) != len(p['axes']):
            raise ValueError('Port owner/rank mismatch')
        if p['object_type']=='scalar' and p['shape']: raise ValueError('Scalar port has nonempty shape')
    state = record['state_contract']['kind']
    state_ports = [p for p in record['ports'] if p['object_type']=='state']
    if state=='stateless' and (state_ports or record['interface']['state']!='none'):
        raise ValueError('Stateless contract contradicts state metadata')
    if state=='recurrent' and (record['interface']['state']=='none' or any(p['state']=='none' for p in state_ports)):
        raise ValueError('Recurrent contract contradicts state metadata')
    if state=='recurrent' and (not any(p['direction']=='input' for p in state_ports) or not any(p['direction']=='output' for p in state_ports)):
        raise ValueError('Recurrent component needs explicit state input and output')
    ev = {e['id']:e for e in record['provenance']}
    if len(ev)!=len(record['provenance']): raise ValueError('Duplicate provenance id')
    for pointer, refs in record['field_evidence'].items():
        if set(refs)-set(ev): raise ValueError('Unresolved field evidence')
        value = record
        try:
            if not pointer.startswith('/'): raise ValueError('Invalid JSON pointer')
            for token in pointer[1:].split('/'):
                token=token.replace('~1','/').replace('~0','~')
                value=value[int(token)] if isinstance(value,list) else value[token]
        except (KeyError,IndexError,TypeError,ValueError): raise ValueError('Invalid field evidence pointer: '+pointer)
    if '/equation' not in record['field_evidence'] or '/ports' not in record['field_evidence']:
        raise ValueError('Equation and ports require field-level provenance')
    for e in ev.values():
        if e['kind'] in ('paper_fact','code_observed') and not e.get('sha256'):
            raise ValueError('Observed facts require a snapshot hash')
    specs=record['parameter_specs']
    if len({p['id'] for p in specs})!=len(specs): raise ValueError('Duplicate parameter id')
    receipts=record['verification']
    if len({v['id'] for v in receipts})!=len(receipts): raise ValueError('Duplicate verification id')
    if set(record['verification_refs'])-{v['id'] for v in receipts}: raise ValueError('Unresolved verification_refs')
    if record['verification_status']=='verified':
        if state=='unknown' or any(p['dtype']=='unknown' or '?' in p['shape'] for p in record['ports']):
            raise ValueError('Verified component cannot contain unknown port/state contracts')
        referenced=[v for v in receipts if v['id'] in record['verification_refs']]
        if not referenced or any(v['status']!='passed' for v in referenced):
            raise ValueError('Verified status requires passed referenced receipts; replay still required')
    return record

def migrate_component(record):
    """Explicit v1.0 -> v1.1 draft; never invent missing ports or parameter shapes."""
    schema=json.loads((SCHEMA.parent/'component-schema-v1.0.json').read_text(encoding='utf8'))
    errors=list(Draft4Validator(schema).iter_errors(record))
    if errors:raise ValueError('Not a valid legacy component')
    result=copy.deepcopy(record)
    result.update(schema_version='1.1',ports=[],parameter_specs=[],state_contract={
        'kind':'unknown','initialization':'待补充','update_equation':'待补充','reset':'待补充','gradient_policy':'待补充'},
        field_evidence={'/equation':[],'/ports':[]},verification=[])
    for i,e in enumerate(result['provenance']):e['id']='evidence:legacy:'+str(i)
    result['field_evidence']['/equation']=[e['id'] for e in result['provenance']]
    result['verification_status']='unverified';result['verification_refs']=[]
    return result

def check_replacements(records):
    ids={r['component']['component_id'] for r in records}
    for entry in records:
        c=entry['component']
        if set(c['replacement_candidates'])-ids:raise ValueError('Unresolved replacement candidate: '+c['component_id'])
        if c['component_id'] in c['replacement_candidates']:raise ValueError('Self replacement candidate')


def build_index(library, output=None):
    root = Path(library).resolve()
    if not root.is_dir(): raise ValueError('Library directory does not exist')
    if output and Path(output).resolve().parent!=root:raise ValueError('Index must be saved in library root')
    records = []; seen = set()
    for path in sorted(root.rglob('component.json')):
        if path.is_symlink() or root not in path.resolve().parents:
            raise ValueError('Component must stay within library')
        record = validate_component(json.loads(path.read_text(encoding='utf-8')))
        cid = record['component_id']
        if cid in seen: raise ValueError('Duplicate component_id: ' + cid)
        seen.add(cid)
        records.append({'path': path.relative_to(root).as_posix(), 'sha256': digest(record), 'component': record})
    check_replacements(records)
    result = {'schema_version': '1.0', 'components': records, 'index_hash': digest(records)}
    if output: atomic_write(output, result)
    return result

def load_index(path):
    index_path=Path(path).resolve()
    result = json.loads(index_path.read_text(encoding='utf-8'))
    if not isinstance(result,dict) or set(result)!={'schema_version','components','index_hash'} or not isinstance(result['components'],list):
        raise ValueError('Invalid index envelope')
    records = result['components']
    if result.get('schema_version') != '1.0' or result.get('index_hash') != digest(records):
        raise ValueError('Invalid or stale index hash; rebuild the index')
    seen = set()
    for entry in records:
        if not isinstance(entry,dict) or set(entry)!={'path','sha256','component'}:raise ValueError('Invalid index entry')
        rel=Path(entry['path'])
        source=(index_path.parent/rel).resolve()
        if rel.is_absolute() or index_path.parent not in source.parents:raise ValueError('Index path escapes library')
        if not source.is_file() or digest(json.loads(source.read_text(encoding='utf8')))!=entry['sha256']:
            raise ValueError('Stale index; component source changed or missing')
        record = validate_component(entry['component'])
        if entry.get('sha256') != digest(record): raise ValueError('Component digest mismatch')
        if record['component_id'] in seen: raise ValueError('Duplicate index component_id')
        seen.add(record['component_id'])
    check_replacements(records)
    return result

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('migrate'); p.add_argument('component'); p.add_argument('-o','--output',required=True)
    p = sub.add_parser('validate'); p.add_argument('component')
    p = sub.add_parser('index'); p.add_argument('library'); p.add_argument('-o', '--output', required=True)
    args = parser.parse_args(argv)
    try:
        if args.cmd == 'migrate':
            atomic_write(args.output,migrate_component(json.loads(Path(args.component).read_text(encoding='utf8'))))
            print('Migrated unverified draft; complete missing ports/state/parameter evidence before validation')
        elif args.cmd == 'validate':
            validate_component(json.loads(Path(args.component).read_text(encoding='utf-8')))
            print('component valid (structural validation only)')
        else:
            result = build_index(args.library, args.output)
            print(json.dumps({'components': len(result['components']), 'index_hash': result['index_hash']}))
    except (ValueError, OSError, KeyError) as exc: parser.error(str(exc))

if __name__ == '__main__': main()
