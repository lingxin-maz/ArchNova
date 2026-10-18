# -*- coding: utf-8 -*-
"""Independent sequential scalar recurrence reference with analytic loss gradients."""
import json,sys
v=json.load(sys.stdin);x=v['sequence'];g=v['gates'];initial=v['initial_state']
if len(x)!=len(g):raise ValueError('Mismatched sequence lengths')
states=[initial]
for gate,value in zip(g,x):states.append(gate*states[-1]+value)
carry=1.;dx=[0.]*len(x);dg=[0.]*len(x)
for i in reversed(range(len(x))):
    adjoint=1.+carry;dx[i]=adjoint;dg[i]=adjoint*states[i];carry=adjoint*g[i]
json.dump({'outputs':states[1:],'state':states[-1],
    'gradients':{'sequence':dx,'gates':dg,'initial_state':carry}},sys.stdout)
