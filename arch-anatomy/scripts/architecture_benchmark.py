# -*- coding: utf-8 -*-
"""Source-locked architecture diagnostics; AI reference drafts are never human gold."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
from orchestrator import atomic_write, digest

VERDICTS={'admit','conditional','reject','unresolved'}
KINDS={'linear','reshape','matmul','scale','mask','softmax','dropout','normalization','residual_add','activation','convolution','conditional_projection','spectral_transform','spectral_shift','spectral_truncate','spectral_multiply','allocation','bias_add','other'}

def validate_cases(cases):
    if not isinstance(cases,list) or not cases:raise ValueError('Nonempty cases required')
    ids=set()
    for case in cases:
        cid=case['id']
        if cid in ids:raise ValueError('Duplicate case id')
        ids.add(cid)
        if case.get('input_hash')!=digest({k:v for k,v in case.items() if k!='input_hash'}):raise ValueError('Stale case input hash')
        if not case['materials'] or len({m['source_id'] for m in case['materials']})!=len(case['materials']):raise ValueError('Missing/duplicate source material')
        for m in case['materials']:
            lines=[r['line'] for r in m['lines']]
            if len(set(lines))!=len(lines):raise ValueError('Duplicate material line')
        if len({e['id'] for e in case['edits']})!=len(case['edits']):raise ValueError('Duplicate edit id')
    return {c['id']:c for c in cases}

def validate_spans(spans,case):
    if not isinstance(spans,list) or not spans:raise ValueError('Precise evidence required')
    material={m['source_id']:{r['line'] for r in m['lines']} for m in case['materials']}
    for span in spans:
        if not isinstance(span,dict) or set(span)!={'source_id','start_line','end_line'}:raise ValueError('Invalid evidence envelope')
        lo,hi=span['start_line'],span['end_line']
        if type(lo)!=int or type(hi)!=int or lo<1 or hi<lo or hi-lo+1>12:raise ValueError('Evidence must span 1..12 exact source lines')
        if span['source_id'] not in material or not set(range(lo,hi+1))<=material[span['source_id']]:raise ValueError('Evidence outside supplied source scope')

def validate_prediction(prediction,case):
    required={'case_id','input_hash','operators','reviews','scope_limits'}
    if not isinstance(prediction,dict) or not required<=set(prediction) or set(prediction)-required-{'run_metadata'}:raise ValueError('Invalid prediction envelope')
    if prediction['case_id']!=case['id'] or prediction['input_hash']!=case['input_hash']:raise ValueError('Prediction case/hash mismatch')
    if not isinstance(prediction['operators'],list) or len(prediction['operators'])>80:raise ValueError('Operator budget exceeded')
    ids=set()
    for op in prediction['operators']:
        if set(op)!={'id','name','kind','evidence','rationale'} or not all(isinstance(op.get(k),str) and op[k].strip() for k in ('id','name','rationale')):raise ValueError('Invalid operator record')
        if op['id'] in ids or op['kind'] not in KINDS:raise ValueError('Duplicate operator id or invalid kind')
        ids.add(op['id']);validate_spans(op['evidence'],case)
    expected={e['id'] for e in case['edits']};seen=set()
    for row in prediction['reviews']:
        if set(row)!={'id','verdict','evidence','rationale'} or row['id'] not in expected or row['id'] in seen:raise ValueError('Unknown/duplicate review')
        if row['verdict'] not in VERDICTS or not isinstance(row['rationale'],str) or not row['rationale'].strip():raise ValueError('Invalid review verdict/rationale')
        validate_spans(row['evidence'],case);seen.add(row['id'])
    if seen!=expected:raise ValueError('Incomplete reviews; abstentions must be explicit')
    if not isinstance(prediction['scope_limits'],list) or not prediction['scope_limits']:raise ValueError('Explicit scope limits required')
    return prediction

def overlaps(a,b):return a['source_id']==b['source_id'] and max(a['start_line'],b['start_line'])<=min(a['end_line'],b['end_line'])

def match_units(units,operators):
    # Maximum bipartite matching: a single coarse prediction cannot cover many reference invocations.
    options=[]
    for unit in units:
        choices=[]
        for i,op in enumerate(operators):
            if op['kind']!=unit['kind'] or not any(overlaps(a,b) for a in unit['anchors'] for b in op['evidence']):continue
            if unit.get('terms_any') and not any(term.casefold() in (op['name']+' '+op['rationale']).casefold() for term in unit['terms_any']):continue
            choices.append(i)
        options.append(choices)
    assigned={}
    def visit(u,seen):
        for op in options[u]:
            if op in seen:continue
            seen.add(op)
            if op not in assigned or visit(assigned[op],seen):assigned[op]=u;return True
        return False
    for u in range(len(units)):visit(u,set())
    matched={u:op for op,u in assigned.items()}
    return {'matches':[{'reference_id':units[u]['id'],'prediction_id':operators[op]['id']} for u,op in sorted(matched.items())],
            'missed':[unit['id'] for u,unit in enumerate(units) if u not in matched],
            'unmatched_predictions':[op['id'] for i,op in enumerate(operators) if i not in assigned]}

def score(cases,reference,predictions):
    known=validate_cases(cases)
    if set(reference['cases'])!=set(known):raise ValueError('Reference coverage differs from cases')
    if reference.get('cases_hash')!=digest(cases):raise ValueError('Reference is not bound to frozen cases')
    if len(predictions)!=len(cases) or len({p['case_id'] for p in predictions})!=len(cases):raise ValueError('Complete unique predictions required')
    rows=[]
    for pred in predictions:
        cid=pred['case_id']
        if cid not in known:raise ValueError('Unknown prediction case')
        case=known[cid];validate_prediction(pred,case);ref=reference['cases'][cid]
        if not ref['units'] or len({u['id'] for u in ref['units']})!=len(ref['units']):raise ValueError('Missing or duplicate reference unit')
        for unit in ref['units']:
            if unit['kind'] not in KINDS:raise ValueError('Invalid reference operator kind')
            validate_spans(unit['anchors'],case)
        for label in ref['reviews'].values():
            if label['verdict'] not in VERDICTS:raise ValueError('Invalid reference verdict')
            validate_spans(label['evidence'],case)
        if set(ref['reviews'])!={e['id'] for e in case['edits']}:raise ValueError('Reference edit coverage mismatch')
        matching=match_units(ref['units'],pred['operators']);judgments={p['id']:p for p in pred['reviews']}
        negatives=[i for i,v in ref['reviews'].items() if v['verdict']!='admit'];positives=[i for i,v in ref['reviews'].items() if v['verdict']=='admit']
        unsafe=[i for i in negatives if judgments[i]['verdict']=='admit']
        correct_safe=[i for i in positives if judgments[i]['verdict']=='admit']
        exact=sum(judgments[i]['verdict']==label['verdict'] for i,label in ref['reviews'].items())
        rows.append({'case_id':cid,'mode':case['mode'],'reference_units':len(ref['units']),'matched_units':len(matching['matches']),
                     'missed_units':len(matching['missed']),'miss_rate':len(matching['missed'])/len(ref['units']) if ref['units'] else None,
                     'negative_edits':len(negatives),'false_admits':len(unsafe),'unsafe_admit_rate':len(unsafe)/len(negatives) if negatives else None,
                     'positive_edits':len(positives),'correct_safe_admits':len(correct_safe),'safe_admit_recall':len(correct_safe)/len(positives) if positives else None,
                     'review_exact':exact,'reviews':len(ref['reviews']),'unsafe_edit_ids':unsafe,'matching':matching,
                     'reference_status':ref['human_review_status'],'granularity':ref['scope']})
    def aggregate(selected):
        sums={k:sum(row[k] for row in selected) for k in ('reference_units','matched_units','missed_units','negative_edits','false_admits','positive_edits','correct_safe_admits','review_exact','reviews')}
        sums.update(miss_rate=sums['missed_units']/sums['reference_units'] if sums['reference_units'] else None,
                    unsafe_admit_rate=sums['false_admits']/sums['negative_edits'] if sums['negative_edits'] else None,
                    safe_admit_recall=sums['correct_safe_admits']/sums['positive_edits'] if sums['positive_edits'] else None)
        return sums
    human=reference.get('human_review_status')=='approved' and all(r['reference_status']=='approved' for r in rows)
    return {'schema_version':'1.0','reference_is_human_approved':human,'evaluation_kind':'source_locked_prediction_scoring','inference_execution_attested':False,
            'all_cases':aggregate(rows),'code_scoped_cases':aggregate([r for r in rows if r['mode']!='paper-only']),
            'paper_only_cases':aggregate([r for r in rows if r['mode']=='paper-only']),'per_case':rows,
            'cases_hash':digest(cases),'reference_hash':digest(reference),'predictions_hash':digest(predictions),
            'limitations':['Pending AI annotations are not independent human gold.',
                           'One model-family run per case, no confidence interval or generalization estimate.',
                           'Source-span/kind matching measures declared reference-unit coverage, not semantic correctness of all explanations.',
                           'Unmatched predictions may be valid finer-grained operations and are not automatically hallucinations.',
                           'Paper templates and code invocations use different granularity; inspect separate metrics.',
                           'Evaluator exposure and backend declarations are provenance, not cryptographic proof of blindness.']}

def export_annotation_sheet(cases,reference,output):
    validate_cases(cases)
    reference_hash=digest(reference)
    with Path(output).open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f);writer.writerow(['case_id','record_type','record_id','proposed_label','evidence_or_scope','input_hash','reference_hash','human_decision','corrected_label','reviewer','rationale'])
        for case in cases:
            ref=reference['cases'][case['id']]
            for u in ref['units']:writer.writerow([case['id'],'operator',u['id'],u['kind'],json.dumps(u['anchors'],ensure_ascii=False),case['input_hash'],reference_hash,'','','',''])
            for eid,row in ref['reviews'].items():writer.writerow([case['id'],'replacement',eid,row['verdict'],row['rationale'],case['input_hash'],reference_hash,'','','',''])

def apply_human_sheet(cases,reference,sheet):
    import copy
    from datetime import datetime,timezone
    known=validate_cases(cases);result=copy.deepcopy(reference);expected={}
    for cid,case in reference['cases'].items():
        for unit in case['units']:expected[(cid,'operator',unit['id'])]=unit['kind']
        for eid,label in case['reviews'].items():expected[(cid,'replacement',eid)]=label['verdict']
    with Path(sheet).open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    if len(rows)!=len(expected):raise ValueError('Every annotation row needs a human decision')
    seen=set();receipts=[]
    for row in rows:
        key=(row['case_id'],row['record_type'],row['record_id'])
        if key not in expected or key in seen:raise ValueError('Unknown or duplicate human review row')
        seen.add(key)
        if row['reference_hash']!=digest(reference) or row['input_hash']!=known[key[0]]['input_hash'] or row['proposed_label']!=expected[key]:raise ValueError('Stale annotation review sheet')
        if row['human_decision'] not in ('approve','correct','exclude') or not row['reviewer'].strip() or not row['rationale'].strip():raise ValueError('Explicit decision, reviewer and rationale required')
        cid,kind,rid=key
        if row['human_decision']=='exclude':
            if kind!='operator':raise ValueError('Do not drop difficult replacement judgments; use unresolved')
            result['cases'][cid]['units']=[u for u in result['cases'][cid]['units'] if u['id']!=rid]
        elif row['human_decision']=='correct':
            if kind=='operator':
                if row['corrected_label'] not in KINDS:raise ValueError('Invalid corrected operator kind')
                next(u for u in result['cases'][cid]['units'] if u['id']==rid)['kind']=row['corrected_label']
            else:
                if row['corrected_label'] not in VERDICTS:raise ValueError('Invalid corrected verdict')
                result['cases'][cid]['reviews'][rid]['verdict']=row['corrected_label']
        receipts.append(row)
    for case in result['cases'].values():
        if not case['units']:raise ValueError('Human exclusions cannot empty a case')
        case['human_review_status']='approved'
    result['human_review_status']='approved'
    result['human_review']={'origin':'explicitly completed reviewer sheet','reviewed_at':datetime.now(timezone.utc).isoformat(),'source_reference_hash':digest(reference),'sheet_sha256':hashlib.sha256(Path(sheet).read_bytes()).hexdigest(),'rows':receipts,'authentication_limit':'Reviewer identity is declared, not independently authenticated. Do not fill this sheet as an AI and call it human.'}
    return result

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='cmd',required=True)
    for name in ('score','annotation-sheet','apply-human'):
        a=sub.add_parser(name);a.add_argument('--cases',required=True);a.add_argument('--reference',required=True);a.add_argument('-o','--output',required=True)
        if name=='score':a.add_argument('--predictions-dir',required=True)
        if name=='apply-human':a.add_argument('--sheet',required=True)
    a=p.parse_args(argv)
    try:
        cases=json.loads(Path(a.cases).read_text(encoding='utf8'));ref=json.loads(Path(a.reference).read_text(encoding='utf8'))
        if a.cmd=='score':
            predictions=[json.loads((Path(a.predictions_dir)/(c['id']+'.json')).read_text(encoding='utf8')) for c in cases]
            result=score(cases,ref,predictions);atomic_write(a.output,result);print(json.dumps(result['all_cases']))
        elif a.cmd=='apply-human':atomic_write(a.output,apply_human_sheet(cases,ref,a.sheet));print(a.output)
        else:export_annotation_sheet(cases,ref,a.output);print(a.output)
    except (ValueError,OSError,KeyError) as exc:p.error(str(exc))
if __name__=='__main__':main()
