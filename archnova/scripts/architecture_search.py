# -*- coding: utf-8 -*-
"""Bounded structural search over explicit IR repair rules; no hidden training or holdout access."""
import argparse,json
from pathlib import Path
from orchestrator import atomic_write,digest
from task_spec import load_task
from architecture_ir import validate_ir,semantic_hash,propose_repairs

def search_ir(model,task_path,output,rules,expected_task_hash=None):
 task=task_path if isinstance(task_path,dict) else load_task(task_path)
 if expected_task_hash and digest(task)!=expected_task_hash:raise ValueError('Task target contract changed')
 validate_ir(model,task);rules=list(dict.fromkeys(rules))
 if any(r not in ('relu','absolute') for r in rules):raise ValueError('Unsupported search rule')
 candidates=[];seen={semantic_hash(model)}
 for item in propose_repairs(model,task,rules):
  h=semantic_hash(item['model'])
  if h in seen:continue
  seen.add(h);candidates.append({'id':'candidate-'+str(len(candidates)),'rule':item['rule'],'semantic_hash':h,'parent_hash':semantic_hash(model),'eligible':item['eligible'],'reason':item.get('reason'),'model':item['model']})
  if len(candidates)>=task['budgets']['max_candidates']-1:break
 result={'schema_version':'1.0','status':'planned','task_hash':digest(task),'base_model_hash':semantic_hash(model),'rules':rules,'candidates':candidates,'budget':task['budgets']['max_candidates'],'holdout_accessed':False,'scope_limits':['Static supported IR search only; no learned architecture search, hardware-aware objective or holdout access.']}
 atomic_write(output,result);return result


def main():
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--model',required=True);p.add_argument('--task',required=True);p.add_argument('--rules',nargs='+',choices=['relu','absolute'],required=True);p.add_argument('--expected-task-hash');p.add_argument('-o','--output',required=True);a=p.parse_args();result=search_ir(json.loads(Path(a.model).read_text(encoding='utf8')),a.task,a.output,a.rules,a.expected_task_hash);print(json.dumps({'status':result['status'],'candidates':len(result['candidates'])}))
if __name__=='__main__':main()
