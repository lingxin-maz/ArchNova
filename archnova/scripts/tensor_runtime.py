# -*- coding: utf-8 -*-
"""Bounded nested tensor primitives shared by IR, training and benchmarks."""
import math

def tensor_shape(value,max_rank=4):
 if not isinstance(value,list) or not value: raise ValueError('Tensor must be a nonempty nested list')
 def walk(node,depth):
  if not isinstance(node,list) or not node: raise ValueError('Tensor dimensions must be nonempty lists')
  if depth>max_rank: raise ValueError('Tensor rank exceeds bound')
  if isinstance(node[0],list):
   child=walk(node[0],depth+1)
   if any(not isinstance(x,list) or tensor_shape(x,max_rank)!=child for x in node): raise ValueError('Ragged tensor')
   return [len(node)]+child
  for x in node:
   if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or abs(x)>1e100: raise ValueError('Finite bounded tensor values required')
  return [len(node)]
 return walk(value,1)

def flatten(value):
 tensor_shape(value);out=[]
 def rec(x):
  if isinstance(x,list):
   for y in x: rec(y)
  else: out.append(float(x))
 rec(value);return out

def reshape_tensor(values,shape):
 if not isinstance(shape,list) or not 1<=len(shape)<=4 or any(type(x)!=int or not 1<=x<=64 for x in shape): raise ValueError('Invalid target tensor shape')
 flat=flatten(values) if isinstance(values,list) else [float(x) for x in values]
 total=1
 for d in shape: total*=d
 if total!=len(flat): raise ValueError('Reshape element count mismatch')
 it=iter(flat)
 def build(dims):
  if len(dims)==1:return [next(it) for _ in range(dims[0])]
  return [build(dims[1:]) for _ in range(dims[0])]
 return build(shape)

def elementwise(value,fn):
 if isinstance(value,list):return [elementwise(x,fn) for x in value]
 return fn(float(value))

def binary(a,b,fn):
 sa,sb=tensor_shape(a),tensor_shape(b)
 if sa!=sb:raise ValueError('Tensor shape mismatch')
 def rec(x,y):
  if isinstance(x,list):return [rec(i,j) for i,j in zip(x,y)]
  return fn(float(x),float(y))
 return rec(a,b)

def transpose_tensor(value,axes):
 shape=tensor_shape(value);rank=len(shape)
 if sorted(axes)!=list(range(rank)):raise ValueError('Invalid transpose axes')
 out_shape=[shape[i] for i in axes];flat=flatten(value)
 def get(idx):
  cur=value
  for i in idx:cur=cur[i]
  return cur
 def build(dims,prefix):
  if not dims:return get([prefix[axes.index(i)] for i in range(rank)])
  return [build(dims[1:],prefix+[i]) for i in range(dims[0])]
 return build(out_shape,[])

def concat_tensor(a,b,axis):
 sa,sb=tensor_shape(a),tensor_shape(b)
 if len(sa)!=len(sb) or not 0<=axis<len(sa) or any(x!=y for i,(x,y) in enumerate(zip(sa,sb)) if i!=axis):raise ValueError('Concat shape mismatch')
 if axis==0:return a+b
 return [concat_tensor(x,y,axis-1) for x,y in zip(a,b)]

def matmul_tensor(a,b):
 sa,sb=tensor_shape(a),tensor_shape(b)
 if len(sa)<2 or len(sb)<2 or sa[:-2]!=sb[:-2] or sa[-1]!=sb[-2]:raise ValueError('Batched matmul shape mismatch')
 prefix=sa[:-2];m,k=sa[-2:];n=sb[-1]
 def get(x,idx):
  for i in idx:x=x[i]
  return x
 def build(pref):
  if len(pref)<len(prefix):return [build(pref+[i]) for i in range(prefix[len(pref)])]
  return [[[sum(get(a,pref+[i,t])*get(b,pref+[t,j]) for t in range(k)) for j in range(n)] for i in range(m)]] [0]
 return build([]) if prefix else [[sum(a[i][t]*b[t][j] for t in range(k)) for j in range(n)] for i in range(m)]

def linear_tensor(a,w,bias=None):
 sa,sw=tensor_shape(a),tensor_shape(w)
 if len(sw)!=2 or sa[-1]!=sw[0]: raise ValueError('Linear tensor shape mismatch')
 out=matmul_tensor(a,w)
 if bias is not None: out=binary(out,reshape_tensor(bias,[1,sw[1]]),lambda x,y:x+y) if len(sa)==2 else _add_bias(out,bias)
 return out

def _add_bias(value,bias):
 if not isinstance(value,list) or not value or not isinstance(value[0],list): return value
 if not isinstance(value[0][0],list): return [ [v+bias[0][j] for j,v in enumerate(row)] for row in value]
 return [_add_bias(x,bias) for x in value]
