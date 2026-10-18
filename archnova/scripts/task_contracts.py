# -*- coding: utf-8 -*-
"""Typed architecture task artifacts. Structural checks are not proofs of scientific truth."""
import argparse
import copy
import json
from pathlib import Path
from jsonschema import Draft4Validator
from architecture_checks import check_architecture
from orchestrator import atomic_write
from numeric_checks import evaluate_expression, evaluate_decision, unit_dimensions

ROOT=Path(__file__).resolve().parents[1]
ROLE_KINDS={'operator_extractor':'decomposition','new_architecture_designer':'design','operator_replacement_checker':'replacement_review'}
DIMENSIONS=('interface','function_class','state','causality','symmetry','stability','precision','gradient','cost','sharing','training')

class Report:
    def __init__(self):self.errors=[];self.warnings=[]
    def err(self,path,message):self.errors.append(str(path)+': '+message)
    def warn(self,path,message):self.warnings.append(str(path)+': '+message)

def validate_artifact(data, expected_hash=None, expected_kind=None, bundle_root=None, target_task=None):
    schema=json.loads((ROOT/'assets/architecture-task.schema.json').read_text(encoding='utf8'))
    errors=sorted(Draft4Validator(schema).iter_errors(data),key=lambda e:str(list(e.path)))
    if errors:raise ValueError('Task schema: '+'; '.join(str(list(e.path))+': '+e.message for e in errors))
    if expected_hash is not None and data['input_hash']!=expected_hash:raise ValueError('Stale artifact input_hash')
    if expected_kind and data['artifact_kind']!=expected_kind:raise ValueError('Wrong artifact_kind')
    if target_task is not None:
        from architecture_ir import check_artifact_binding
        check_artifact_binding(data,target_task)
    elif data.get('runtime_ir') is not None or data.get('task_spec_hash') is not None:
        raise ValueError('Task-bound artifact requires the actual validated target contract')
    operators=data['operators']; ids=[o['id'] for o in operators]
    if len(set(ids))!=len(ids):raise ValueError('Duplicate operator id')
    evidence={e['id']:e for e in data['evidence']}
    if len(evidence)!=len(data['evidence']):raise ValueError('Duplicate evidence id')
    for op in operators:
        if set(op['evidence_ids'])-set(evidence):raise ValueError('Unresolved operator evidence')
    if set(data['dataflow']['node_parts'])!=set(ids):raise ValueError('Operator graph coverage mismatch')
    neutral={'claimed_centrality':{'status':'not_claimed','claim_ids':[]},'theoretical_dependency':{'status':'not_claimed','claim_ids':[]},'ablation_ids':[],'interaction_ids':[]}
    parts=[{'id':o['id'],'importance':copy.deepcopy(neutral),'swap_assessments':[]} for o in operators]
    graph_data={'dataflow':data['dataflow'],'parts':parts,'claims':[],'metrics':[],'ablations':[],'interactions':[],'proposals':[]}
    report=Report();check_architecture(graph_data,report)
    if report.errors:raise ValueError('Invalid graph: '+'; '.join(report.errors))
    if 'affected_parts' in data:
        affected=set(data['affected_parts'])
        if affected-set(ids):raise ValueError('Unknown affected operator')
        for group in data['dataflow']['coupled_replacements']:
            members=set(group['parts'])
            if members & affected and not members<=affected:raise ValueError('Missing coupled replacement owners')
        shared={g['id']:g for g in data['dataflow']['shared_parameters']}
        for gid in data['changes_shared_parameters']:
            if gid not in shared or not set(shared[gid]['parts'])<=affected:raise ValueError('Changed shared parameters need all owners')
    upstream=data['upstream_artifacts']
    if len({e['task_id'] for e in upstream})!=len(upstream):raise ValueError('Duplicate upstream artifact task_id')
    if data['artifact_kind']=='design':
        for cost in data['cost_predictions']:
            value=evaluate_expression(cost['expression'],cost['variables'])
            if value['value']<0 or value['dimensions']!=unit_dimensions(cost['unit']):raise ValueError('Invalid cost units or negative prediction')
        alternatives=data['alternatives']
        if len({c['id'] for c in alternatives})!=len(alternatives) or sum(c['decision']=='select' for c in alternatives)!=1:
            raise ValueError('Design needs unique alternatives and exactly one selected candidate')
        trial=data['experiment']
        if trial['baseline']!=data['baseline']:raise ValueError('Experiment baseline differs from design baseline')
        if trial['metric_definition']['id']!=trial['metric']:raise ValueError('Experiment metric reference mismatch')
        if trial['decision_rule']['min_seeds']>len(trial['seeds']):raise ValueError('Trial seeds below decision minimum')
        evaluate_decision(trial['decision_rule'],trial['metric_definition'])
        if trial['status']=='executed':
            if not trial['receipt_refs'] or bundle_root is None:raise ValueError('Executed experiment needs resolvable replay receipts and bundle root')
            from evidence_snapshots import bundled_path
            from experiment_runner import replay_receipt,validate_spec
            from architecture_ir import artifact_semantics
            for ref in trial['receipt_refs']:
                path=bundled_path(bundle_root,ref)
                receipt=json.loads(path.read_text(encoding='utf8'))
                expected_target=digest(artifact_semantics(data))
                if receipt.get('target_snapshot_hash')!=expected_target:raise ValueError('Experiment receipt is bound to different operator semantics')
                validate_spec(receipt['spec'],bundle_root)
                replay=replay_receipt(receipt)
                if replay['status']!=receipt.get('status') or replay['comparisons_completed']!=receipt.get('comparisons_completed'):raise ValueError('Stored experiment outcome disagrees with replay')
    if data['artifact_kind']=='replacement_review':
        checks=data['checks']; dimensions=[c['dimension'] for c in checks]
        if set(dimensions)!=set(DIMENSIONS):raise ValueError('Review must cover every dimension exactly once')
        for c in checks:
            if set(c['evidence_ids'])-set(evidence):raise ValueError('Unresolved review evidence')
            if c['status']=='satisfied' and not c['evidence_ids']:raise ValueError('Satisfied check needs evidence')
        proof=data['proof_evidence_ids']
        if set(proof)-set(evidence):raise ValueError('Unresolved proof evidence')
        if data['relation']=='exact_equivalence' and not any(evidence[e]['kind']=='derived' for e in proof):
            raise ValueError('Exact equivalence needs a derivation; still requires semantic proof review')
        if data['verdict']=='admit':
            by_dimension={c['dimension']:c for c in checks}
            for dimension in ('interface','function_class'):
                if by_dimension[dimension]['status']!='satisfied':
                    raise ValueError('Admission requires explicit satisfied '+dimension+'; cannot mark it not_applicable')
            for c in checks:
                if c['status']=='not_applicable' and not c['evidence_ids']:
                    raise ValueError('Admission requires evidence-backed non-applicability for '+c['dimension'])
            if data['relation']=='exact_equivalence' and (not proof or any(evidence[e]['kind']!='derived' for e in proof)):
                raise ValueError('All exact equivalence proof references must be derivations')
            if data['relation']=='unknown' or data['unresolved'] or report.warnings or any(c['status'] not in ('satisfied','not_applicable') for c in checks):
                raise ValueError('Cannot admit unresolved/violated review')
            refs={eid for c in checks for eid in c['evidence_ids']}
            if not refs or all(evidence[e]['kind']=='proposed' for e in refs):raise ValueError('Proposals alone cannot support admission')
        if any(c['status']=='violated' for c in checks) and data['verdict'] not in ('reject','conditional'):
            raise ValueError('Violated constraint must reject or explicitly condition the replacement')
    return {'status':'structurally_valid','warnings':report.warnings,'scientific_verification':'unverified'}

def example_artifact(kind='decomposition',input_hash='0'*64):
    # Synthetic example, never an endorsement or an empirical result.
    ports=[]
    for name,direction in [('x','input'),('y','output')]:
        ports.append({'id':name,'owner':'op:identity','direction':direction,'object_type':'tensor','shape':['B','D'],'axes':['batch','feature'],'dtype':'float32','unit':'1','measure':'counting','state':'none','external':True})
    data={'schema_version':'1.0','artifact_kind':kind,'input_hash':input_hash,'operators':[{'id':'op:identity','component_id':'operator:identity','equation':'y=x','domain':'finite tensors','discretization':'finite tensor axes','evidence_ids':['ev:proposal'],'complexity_assumptions':['Identity view; allocation and execution not measured.']}],
          'dataflow':{'node_parts':['op:identity'],'ports':ports,'edges':[],'bindings':[],'shared_parameters':[],'coupled_replacements':[]},
          'evidence':[{'id':'ev:proposal','kind':'proposed','ref':'synthetic-example','locator':'Identity design fixture only'}],
          'upstream_artifacts':[], 'scope_limits':['Synthetic task contract fixture; no paper, proof or execution validation.'],'unresolved':['Real evidence and experiments pending']}
    if kind=='decomposition':data['coverage']={'included':['Identity operator'],'excluded':[],'granularity_rationale':'Single primitive identity for protocol testing'}
    elif kind=='design':data.update(baseline='Unmodified identity fixture',objectives=['Preserve identity behavior'],affected_parts=['op:identity'],changes_shared_parameters=[],experiment={'baseline':'Unmodified identity fixture','metric':'RMSE','direction':'lower_better','dataset_split':'held-out synthetic inputs','budget_control':'Same samples and precision','seeds':[1,2],'ablation_plan':['Compare original and candidate on identical inputs'],'kill_criterion':'Reject if RMSE > 1e-6 on held-out inputs','status':'planned','receipt_refs':[]})
    elif kind=='replacement_review':data.update(relation='unknown',domain='finite tensors',parameter_mapping='Identity, no trainable parameters',proof_evidence_ids=[],checks=[{'dimension':d,'status':'unknown','conditions':['Pending evidence and semantic review'],'evidence_ids':[]} for d in DIMENSIONS],verdict='unresolved',affected_parts=['op:identity'],changes_shared_parameters=[])
    else:raise ValueError('Unknown artifact kind')
    if kind=='design':
        data['alternatives']=[{'id':'identity_view','mechanism':'Return an identity view','tradeoff':'Potential aliasing','decision':'select','reason':'Minimal reference fixture'}, {'id':'identity_copy','mechanism':'Copy the identity tensor','tradeoff':'Extra allocation','decision':'reject','reason':'No demonstrated need for a copy in this fixture'}]
        data['cost_predictions']=[{'id':'identity_elements','expression':'B*D','variables':{'B':{'value':2,'unit':'1'},'D':{'value':4,'unit':'1'}},'unit':'1','assumptions':['Element count proxy, not FLOPs or latency.']}]
        data['experiment']['metric_definition']={'id':'RMSE','unit':'1'}
        data['experiment']['decision_rule']={'metric_id':'RMSE','condition_id':'heldout','aggregation':'mean','min_seeds':2,'expression':'candidate','operator':'gt','threshold':{'value':1e-6,'unit':'1'}}
    return data

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='cmd',required=True)
    a=sub.add_parser('validate');a.add_argument('artifact');a.add_argument('--input-hash');a.add_argument('--kind',choices=list(ROLE_KINDS.values()));a.add_argument('--task-spec');a.add_argument('--bundle')
    a=sub.add_parser('example');a.add_argument('kind',choices=list(ROLE_KINDS.values()));a.add_argument('-o','--output',required=True)
    args=p.parse_args(argv)
    try:
        if args.cmd=='example':atomic_write(args.output,example_artifact(args.kind));print(args.output)
        else:
            from task_spec import load_task
            target=load_task(args.task_spec) if args.task_spec else None
            print(json.dumps(validate_artifact(json.loads(Path(args.artifact).read_text(encoding='utf8')),args.input_hash,args.kind,args.bundle or Path(args.artifact).resolve().parent,target)))
    except (ValueError,OSError,KeyError) as exc:p.error(str(exc))
if __name__=='__main__':main()
