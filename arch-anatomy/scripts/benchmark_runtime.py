# -*- coding: utf-8 -*-
"""Bounded CPU/GPU benchmark with explicit unavailable status and warmup/repetition policy."""
import importlib.util,time,statistics
from pathlib import Path
from tensor_runtime import tensor_shape
from lifecycle_runtime import make_receipt
from architecture_ir import validate_ir
from task_spec import load_task

def benchmark_ir(model,task_path,device='cpu',repetitions=20,warmup=5):
 if device not in ('cpu','cuda'):raise ValueError('device must be cpu or cuda')
 if type(repetitions)!=int or not 1<=repetitions<=1000 or type(warmup)!=int or not 0<=warmup<=100:raise ValueError('invalid benchmark budget')
 task=task_path if isinstance(task_path,dict) else load_task(task_path);validate_ir(model,task)
 if device=='cuda' and (not importlib.util.find_spec('torch')):return {'status':'unavailable','device':'cuda','reason':'torch runtime is not installed','repetitions':repetitions,'warmup':warmup,'lifecycle':make_receipt('benchmark',['model','inputs'],['benchmark_receipt'],['device_state'],'unavailable')}
 if device=='cuda':
  import torch
  if not torch.cuda.is_available():return {'status':'unavailable','device':'cuda','reason':'CUDA device is not available','repetitions':repetitions,'warmup':warmup,'lifecycle':make_receipt('benchmark',['model','inputs'],['benchmark_receipt'],['device_state'],'unavailable')}
 # Reference runtime benchmark is scalar CPU; GPU benchmark requires a reviewed torch adapter.
 if device=='cuda':return {'status':'unavailable','device':'cuda','reason':'No reviewed Torch lowering for this IR','repetitions':repetitions,'warmup':warmup,'lifecycle':make_receipt('benchmark',['model','inputs'],['benchmark_receipt'],['device_state'],'unavailable')}
 from prototype_runtime import predict
 def zeros(shape):
  if len(shape)==1:return [0.0 for _ in range(shape[0])]
  return [zeros(shape[1:]) for _ in range(shape[0])]
 inputs={p['name']:zeros([int(task['symbols'].get(dim,dim)) for dim in p['shape']]) for p in task['inputs']}
 for _ in range(warmup):predict(model,inputs)
 times=[]
 for _ in range(repetitions):
  start=time.perf_counter();predict(model,inputs);times.append(time.perf_counter()-start)
 return {'status':'completed','device':'cpu','repetitions':repetitions,'warmup':warmup,'median_seconds':statistics.median(times),'mean_seconds':statistics.mean(times),'min_seconds':min(times),'max_seconds':max(times),'samples_seconds':times,'scope_limits':['Wall-clock Python reference runtime; no GPU/kernel/compiled performance claim.'],'lifecycle':make_receipt('benchmark',['model','inputs'],['benchmark_receipt'],['device_state'])}


def main():
 import argparse,json
 p=argparse.ArgumentParser();p.add_argument('--model',required=True);p.add_argument('--task',required=True);p.add_argument('--device',choices=['cpu','cuda'],default='cpu');p.add_argument('--repetitions',type=int,default=20);p.add_argument('--warmup',type=int,default=5);p.add_argument('-o','--output',required=True);a=p.parse_args();result=benchmark_ir(json.loads(Path(a.model).read_text(encoding='utf8')),a.task,a.device,a.repetitions,a.warmup);Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\\n',encoding='utf8');print(json.dumps({'status':result['status'],'device':result['device']}))
if __name__=='__main__':main()



