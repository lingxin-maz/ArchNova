# -*- coding: utf-8 -*-
"""Pair-prefix tree implementation; independent central-difference gradients."""
import json,sys
v=json.load(sys.stdin)
def compose(a,b):return b[0]*a[0],b[0]*a[1]+b[1]
def prefix(pairs):
    if len(pairs)<2:return pairs
    midpoint=len(pairs)//2;left=prefix(pairs[:midpoint]);right=prefix(pairs[midpoint:])
    return left+[compose(left[-1],item) for item in right]
def forward(value):
    if len(value['sequence'])!=len(value['gates']):raise ValueError('Mismatched lengths')
    pairs=prefix(list(zip(value['gates'],value['sequence'])))
    outputs=[a*value['initial_state']+b for a,b in pairs]
    return outputs,outputs[-1] if outputs else value['initial_state']
def loss(value):
    outputs,state=forward(value);return sum(outputs)+state
h=1e-6;gradients={}
for key in ('sequence','gates'):
    gradients[key]=[]
    for i in range(len(v[key])):
        plus={k:list(x) if isinstance(x,list) else x for k,x in v.items()};minus={k:list(x) if isinstance(x,list) else x for k,x in v.items()}
        plus[key][i]+=h;minus[key][i]-=h
        gradients[key].append((loss(plus)-loss(minus))/(2*h))
plus=dict(v,initial_state=v['initial_state']+h);minus=dict(v,initial_state=v['initial_state']-h)
gradients['initial_state']=(loss(plus)-loss(minus))/(2*h)
outputs,state=forward(v)
json.dump({'outputs':outputs,'state':state,'gradients':gradients},sys.stdout)
