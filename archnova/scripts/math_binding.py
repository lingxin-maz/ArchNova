# -*- coding: utf-8 -*-
"""Syntactic target/equation correspondence; semantic formalization still needs review."""
import ast,hashlib,json
from proof_checks import Algebra

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')).hexdigest()
def natural_statement(target):
    return target.get('statement') or (target.get('predicate','')+' '+target.get('object','')).strip() or target.get('conditions','')
def normalized(expression):return ast.dump(ast.parse(expression.strip(),mode='eval'),include_attributes=False)

def make_binding(check,target):
    formal=target.get('formal_statement')
    if not isinstance(formal,dict):raise ValueError('Target needs explicit formal_statement')
    target_id=target.get('id') or target.get('claim_id')
    if check.get('target_id')!=target_id:raise ValueError('Check names a different target')
    if formal.get('natural_statement')!=natural_statement(target):raise ValueError('Formalization does not quote the actual target statement')
    if formal.get('semantics')!='real_scalar' or formal.get('quantifier')!='forall' or formal.get('relation')!='equals':raise ValueError('Exact binding currently supports universal real-scalar equalities only')
    variables=formal.get('variables',[])
    if not isinstance(variables,list) or any(not isinstance(v,dict) or v.get('type')!='real_scalar' or not isinstance(v.get('meaning'),str) or not v['meaning'].strip() for v in variables):raise ValueError('Every symbol needs real_scalar type and actual meaning')
    symbols=[v['symbol'] for v in variables];algebra=Algebra(symbols);case=check['case']
    if case.get('semantics','real_scalar')!='real_scalar' or case.get('variables')!=symbols:raise ValueError('Variable mapping/type/semantics differs from formal target')
    for side in ('lhs','rhs'):
        algebra.parse(formal[side]);algebra.parse(case[side])
        if normalized(formal[side])!=normalized(case[side]):raise ValueError('Machine equation does not encode the formal target: '+side)
    expected=formal.get('nonzero');actual=case.get('nonzero')
    if not isinstance(expected,list) or not isinstance(actual,list) or {normalized(e) for e in expected}!={normalized(e) for e in actual}:raise ValueError('Machine nonzero domain differs from formal target')
    for expression in expected:algebra.parse(expression)
    return {'target_hash':digest(target),'formal_hash':digest(formal),'case_hash':digest(case),
        'mapping_note':'Exact symbol/type/domain/operator correspondence only; natural-language meaning requires the formalization review obligations'}

def validate_binding(check,target):
    if check.get('binding')!=make_binding(check,target):raise ValueError('Mathematical target/case binding is stale or altered')
    return True

def main(argv=None):
    import argparse,copy
    from pathlib import Path
    from proof_dependencies import target_registry
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('anatomy');ap.add_argument('--check-id',required=True);ap.add_argument('-o','--output',required=True)
    a=ap.parse_args(argv);target=Path(a.output)
    if target.exists():ap.error('Choose a new output file')
    try:
        data=json.loads(Path(a.anatomy).read_text(encoding='utf-8-sig'));registry=dict(target_registry(data))
        checks=[c for c in data['mathematical_checks'] if c['id']==a.check_id]
        if len(checks)!=1:raise ValueError('Check ID must resolve exactly once')
        check=checks[0];check['binding']=make_binding(check,registry[check['target_id']])
        blockers=data.get('stage',{}).get('blocking_items',[])
        data['stage']={'stage':'G8','stage_status':'blocked' if blockers else 'pending','blocking_items':blockers,'receipts':[]}
        target.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(str(target));return 0
    except (ValueError,KeyError,TypeError,OSError,SyntaxError) as exc:ap.error(str(exc))
if __name__=='__main__':raise SystemExit(main())
