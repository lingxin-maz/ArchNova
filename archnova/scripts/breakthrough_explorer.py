# -*- coding: utf-8 -*-
"""B->C architecture exploration: novelty, mechanism, falsification and evidence gates."""
import argparse,itertools,json,math
from pathlib import Path
from orchestrator import atomic_write,digest
from network_system import validate_system

def _component_id(c): return c.get('component_id') or c.get('id') or c.get('name')
def _family(c): return c.get('family') or c.get('functional_group') or c.get('operator_family') or 'unknown'
def generate_candidates(system,components,budget=8):
 validate_system(system);base=set(c['id'] for c in system['components']);pool=[c for c in components if _component_id(c) not in base]
 candidates=[]
 for size in (1,2,3):
  for combo in itertools.combinations(pool,size):
   ids=sorted(_component_id(c) for c in combo);families=sorted(set(_family(c) for c in combo));
   if not ids or not families:continue
   novelty=min(1.0,(len(set(ids)-base)+len(families))/6.0)
   mechanism=' + '.join(families)+' introduces a distinct computational or state pathway; verify causality and interface contracts.'
   candidate={'id':'candidate:'+digest({'system':system['system_id'],'components':ids})[:16],'system_id':system['system_id'],'component_ids':ids,'families':families,'novelty_score':round(novelty,6),'mechanism_hypothesis':mechanism,'complexity_proxy':len(ids)*len(families),'status':'design_only'}
   candidates.append(candidate)
 candidates.sort(key=lambda c:(-c['novelty_score'],c['complexity_proxy'],c['id']))
 return candidates[:max(1,min(budget,32))]
def build_validation_plan(candidate,baseline=None,task=None):
 gates=[{'id':'baseline','test':'Run candidate and fixed baseline on identical development and holdout splits','pass_condition':'candidate improves locked objective without violating constraints','required_receipts':['candidate_metrics','baseline_metrics']},{'id':'ablation','test':'Remove each proposed component and rerun controlled experiment','pass_condition':'claimed mechanism has measurable contribution','required_receipts':['ablation_metrics']},{'id':'counterexample','test':'Search adversarial or boundary inputs','pass_condition':'no known counterexample violates the declared claim','required_receipts':['counterexample_receipt']},{'id':'repeatability','test':'Repeat with independent seeds and frozen environment','pass_condition':'effect survives declared seed threshold','required_receipts':['seed_receipts']},{'id':'complexity','test':'Compare memory and operation proxy to baseline','pass_condition':'cost remains within declared budget','required_receipts':['cost_receipt']}]
 return {'candidate_id':candidate['id'],'baseline_id':baseline.get('id') if baseline else None,'task_hash':digest(task) if task else None,'gates':gates,'holdout_access':'validation_only_after_structure_is_frozen'}
def score_candidate(candidate,baseline=None):
 base=baseline or {};novelty=float(candidate.get('novelty_score',0));complexity=float(candidate.get('complexity_proxy',1));base_complexity=float(base.get('complexity_proxy',complexity or 1));efficiency=1.0 if complexity<=base_complexity*2 else max(0.0,base_complexity/complexity)
 return {'novelty':novelty,'mechanism_specificity':1.0 if candidate.get('mechanism_hypothesis') else 0.0,'complexity_efficiency':round(efficiency,6),'breakthrough_score':round(0.5*novelty+0.3*(1.0 if candidate.get('mechanism_hypothesis') else 0.0)+0.2*efficiency,6),'score_status':'heuristic_prior'}
def evaluate_promotion(candidate,receipts):
 required={'candidate_metrics','baseline_metrics','ablation_metrics','counterexample_receipt','seed_receipts','cost_receipt'};missing=sorted(required-set(receipts or {}))
 if missing:return {'status':'blocked','reason':'Missing validation receipts','missing':missing}
 if not receipts.get('baseline_improvement'):return {'status':'unresolved','reason':'Baseline improvement not established'}
 if not receipts.get('mechanism_supported'):return {'status':'unresolved','reason':'Mechanism contribution not established'}
 if receipts.get('counterexample_found'):return {'status':'blocked','reason':'Counterexample violates claim'}
 if not receipts.get('repeatable'):return {'status':'unresolved','reason':'Repeated-seed effect not established'}
 return {'status':'validated_candidate','reason':'All declared promotion gates have receipts'}
def build_exploration(system,components,baseline=None,budget=8,task=None):
 candidates=[]
 for c in generate_candidates(system,components,budget):
  c['score']=score_candidate(c,baseline);c['validation_plan']=build_validation_plan(c,baseline,task);candidates.append(c)
 return {'schema_version':'1.0','exploration_id':'breakthrough:'+digest(system)[:16],'system_id':system['system_id'],'system_snapshot_hash':digest(system),'candidates':candidates,'search_mode':'mechanism_constrained_open_composition','promotion_policy':'No candidate is breakthrough proof without baseline, ablation, counterexample, repeatability, cost and evidence receipts.','status':'design_only'}
def main():
 p=argparse.ArgumentParser();p.add_argument('--system',required=True);p.add_argument('--components',required=True);p.add_argument('--budget',type=int,default=8);p.add_argument('-o','--output',required=True);a=p.parse_args()
 try:
  system=json.loads(Path(a.system).read_text(encoding='utf8'));raw=json.loads(Path(a.components).read_text(encoding='utf8'));components=raw.get('components',raw if isinstance(raw,list) else []);result=build_exploration(system,components,budget=a.budget);atomic_write(a.output,result);print(json.dumps({'status':result['status'],'candidates':len(result['candidates']),'output':a.output}))
 except (ValueError,OSError,KeyError) as exc:p.error(str(exc))
if __name__=='__main__':main()
