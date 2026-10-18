# -*- coding: utf-8 -*-
"""Deterministic bounded training for the supported IR, with raw receipt replay."""
import argparse,copy,json,math,hashlib
from pathlib import Path
from orchestrator import atomic_write,digest
from task_spec import load_task,load_dataset
from architecture_ir import validate_ir
from prototype_runtime import predict
from tensor_runtime import flatten
from lifecycle_runtime import make_receipt

def _metric(model,data):
 errors=[]
 for row in data:
  pred=predict(model,row['inputs']);target=row['targets']
  for key in target:
   for x,y in zip(flatten(pred[key]),flatten(target[key])):errors.append((x-y)**2)
 return sum(errors)/len(errors) if errors else 0.0

def train_ir(model,task_path,output,epochs=25,learning_rate=.1):
 task=task_path if isinstance(task_path,dict) else load_task(task_path);data=load_dataset(task,Path(task_path).parent if not isinstance(task_path,dict) else Path(output).parent);validate_ir(model,task)
 if type(epochs)!=int or not 1<=epochs<=200 or not isinstance(learning_rate,(int,float)) or not 0<learning_rate<=1:raise ValueError('bounded training budget required')
 trainable=[p for p in model['parameters'] if p.get('trainable')]
 if not trainable:raise ValueError('No declared trainable parameters')
 if any(len(p['value'])>64 or len(p['value'][0])>64 for p in trainable):raise ValueError('Trainable parameter exceeds bounded matrix size')
 initial=copy.deepcopy(model);history=[]
 # finite-difference SGD is explicit and deterministic; it does not claim autodiff.
 for epoch in range(epochs):
  before=_metric(model,[r for r in data if r['split']=='development']);history.append({'epoch':epoch,'metric':before})
  for p in trainable:
   for i,row in enumerate(p['value']):
    for j,base in enumerate(row):
     eps=1e-5; p['value'][i][j]=base+eps; plus=_metric(model,[r for r in data if r['split']=='development']); p['value'][i][j]=base-eps; minus=_metric(model,[r for r in data if r['split']=='development']); p['value'][i][j]=base
     grad=(plus-minus)/(2*eps); p['value'][i][j]=base-learning_rate*grad
  validate_ir(model,task)
 final=_metric(model,[r for r in data if r['split']=='development']);result={'schema_version':'1.0','status':'completed','task_hash':digest(task),'initial_model_hash':digest(initial),'final_model_hash':digest(model),'trainable_parameter_ids':[p['id'] for p in trainable],'epochs':epochs,'learning_rate':learning_rate,'history':history,'final_metric':final,'model':model,'scope_limits':['Finite-difference bounded-matrix SGD on supported IR; no autodiff, momentum, distributed training, mixed precision or GPU.'],'lifecycle':make_receipt('training',['model','development_data'],['weights','training_receipt'],['parameters','gradients'],contract_hash=digest(task))}
 if output is not None:
  atomic_write(output,result)
 return result

def replay_training(path):
 result=json.loads(Path(path).read_text(encoding='utf8'));required={'schema_version','status','task_hash','initial_model_hash','final_model_hash','trainable_parameter_ids','epochs','learning_rate','history','final_metric','model','scope_limits','lifecycle'}
 if set(result)!=required or result['status']!='completed' or len(result['history'])!=result['epochs']:raise ValueError('Invalid training receipt')
 if digest(result['model'])!=result['final_model_hash']:raise ValueError('Training model hash changed')
 from lifecycle_runtime import validate_receipt
 validate_receipt(result['lifecycle'],'training')
 return {'status':'completed','final_metric':result['final_metric'],'epochs':result['epochs'],'model_hash':result['final_model_hash']}


def main():
 import argparse
 p=argparse.ArgumentParser();sub=p.add_subparsers(dest='cmd',required=True);a=sub.add_parser('train');a.add_argument('--model',required=True);a.add_argument('--task',required=True);a.add_argument('-o','--output',required=True);a.add_argument('--epochs',type=int,default=25);a.add_argument('--learning-rate',type=float,default=.1);b=sub.add_parser('replay');b.add_argument('receipt');x=p.parse_args()
 if x.cmd=='train':result=train_ir(json.loads(Path(x.model).read_text(encoding='utf8')),x.task,x.output,x.epochs,x.learning_rate);print(json.dumps({'status':result['status'],'final_metric':result['final_metric']}))
 else:print(json.dumps(replay_training(x.receipt)))
if __name__=='__main__':main()




