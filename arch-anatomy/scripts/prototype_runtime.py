# -*- coding: utf-8 -*-
"""Reference runtime for bounded rank-1..4 nested tensors."""
import math
from tensor_runtime import tensor_shape,elementwise,binary,matmul_tensor,reshape_tensor,transpose_tensor,concat_tensor,linear_tensor

def _softmax(x):
 if not isinstance(x,list) or not x:return x
 if not isinstance(x[0],list):
  m=max(x); ex=[math.exp(v-m) for v in x];z=sum(ex);return [v/z for v in ex]
 return [_softmax(v) for v in x]

def _layernorm(x,eps):
 if not isinstance(x,list) or not x:return x
 if not isinstance(x[0],list):
  mean=sum(x)/len(x);var=sum((v-mean)**2 for v in x)/len(x);scale=(var+eps)**-0.5;return [(v-mean)*scale for v in x]
 return [_layernorm(v,eps) for v in x]

def _zeros(shape):
 if len(shape)==1:return [[0.0 for _ in range(shape[0])]][0]
 return [_zeros(shape[1:]) for _ in range(shape[0])]

def predict(model,inputs):
 if set(inputs)!={p['id'] for p in model['inputs']}:raise ValueError('Runtime input signature mismatch')
 env={name:(tensor_shape(value),value)[1] for name,value in inputs.items()};params={p['id']:p['value'] for p in model['parameters']}
 if not 1<=len(model['nodes'])<=64:raise ValueError('Node budget')
 for node in model['nodes']:
  op=node['op'];xs=[env[name] for name in node['inputs']];a=xs[0]
  if op=='identity':out=elementwise(a,lambda v:v)
  elif op=='scale':out=elementwise(a,lambda v:v*node['attributes']['factor'])
  elif op=='relu':out=elementwise(a,lambda v:max(0.,v))
  elif op=='tanh':out=elementwise(a,math.tanh)
  elif op=='add':out=binary(a,xs[1],lambda x,y:x+y)
  elif op=='matmul':out=matmul_tensor(a,xs[1])
  elif op=='transpose':
   axes=node['attributes'].get('axes',list(reversed(range(len(tensor_shape(a))))));out=transpose_tensor(a,axes)
  elif op=='softmax':out=_softmax(a)
  elif op=='layernorm':out=_layernorm(a,node['attributes']['eps'])
  elif op=='reshape':out=reshape_tensor(a,node['attributes']['shape'])
  elif op=='concat':out=concat_tensor(a,xs[1],node['attributes']['axis'])
  elif op=='linear':out=linear_tensor(a,params[node['parameters']['weight']],params[node['parameters']['bias']] if 'bias' in node['parameters'] else None)
  else:raise ValueError('Unsupported runtime op: '+str(op))
  tensor_shape(out);env[node['id']]=out
 return {name:env[ref] for name,ref in model['outputs'].items()}
