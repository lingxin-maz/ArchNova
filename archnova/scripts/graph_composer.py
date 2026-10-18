# -*- coding: utf-8 -*-
"""Typed GraphIR composition, edit actions, anti-stacking diagnostics and ablation plans."""
import copy,hashlib,json
from orchestrator import digest

def _port(component,port_id,direction=None):
 for p in component.get('ports',[]):
  if p['id']==port_id and (direction is None or p['direction']==direction):return p
 return None

def _split(ref):
 return ref.split('.',1) if '.' in ref else (ref,None)

def _node_ports(node,components):
 c=components.get(node['component_id'])
 if c is None:raise ValueError('Unknown component: '+node['component_id'])
 return c

def _compatible(edge_type,port):
 if not port:return False
 for key in ('shape','dtype','layout','state'):
  if key in edge_type and key in port and edge_type[key]!=port[key]:return False
 return True

def validate_graph(graph,components):
 if graph.get('schema_version')!='1.0':raise ValueError('GraphIR schema version required')
 nodes=graph.get('nodes',[]);edges=graph.get('edges',[]);ids=[n.get('id') for n in nodes]
 if len(ids)!=len(set(ids)):raise ValueError('Duplicate GraphIR node id')
 if set(graph.get('inputs',[]))&set(ids) or set(graph.get('outputs',[]))&set(ids):raise ValueError('GraphIR endpoint collides with node')
 if len(nodes)>graph.get('constraints',{}).get('max_nodes',10**9):raise ValueError('GraphIR node budget exceeded')
 seen_edges=set();incoming={i:0 for i in ids};outgoing={i:0 for i in ids}
 for node in nodes:
  c=_node_ports(node,components);mutable=node.get('mutable',{})
  if not isinstance(mutable,dict):raise ValueError('Mutation surface must be an object')
  for key,value in mutable.items():
   if not isinstance(value,list) or not value:raise ValueError('Mutation surface choices must be nonempty lists')
 for edge in edges:
  if edge.get('id') in seen_edges:raise ValueError('Duplicate GraphIR edge id')
  seen_edges.add(edge.get('id'));src,src_port=_split(edge.get('from',''));dst,dst_port=_split(edge.get('to',''))
  if src not in ids and src not in graph.get('inputs',[]):raise ValueError('Unknown GraphIR edge source')
  if dst not in ids and dst not in graph.get('outputs',[]):raise ValueError('Unknown GraphIR edge destination')
  if dst in ids:
   c=_node_ports(next(n for n in nodes if n['id']==dst),components);p=_port(c,dst_port,'input')
   if not _compatible(edge.get('type',{}),p):raise ValueError('Typed edge incompatible with destination port: '+str(edge.get('to')))
   incoming[dst]+=1
  if src in ids:
   c=_node_ports(next(n for n in nodes if n['id']==src),components);p=_port(c,src_port,'output')
   if not _compatible(edge.get('type',{}),p):raise ValueError('Typed edge incompatible with source port: '+str(edge.get('from')))
   outgoing[src]+=1
 reachable=set(graph.get('inputs',[]));changed=True
 while changed:
  changed=False
  for e in edges:
   src,srcp=_split(e['from']);dst,_=_split(e['to'])
   if src in reachable and dst in ids and dst not in reachable:reachable.add(dst);changed=True
 if any(n not in reachable for n in ids):raise ValueError('GraphIR orphan node')
 if any(incoming[n]==0 for n in ids):raise ValueError('GraphIR node lacks input edge')
 if not any(_split(e['to'])[0] in graph.get('outputs',[]) for e in edges):raise ValueError('GraphIR has no output path')
 return graph

def apply_edit(graph,edit,components):
 g=copy.deepcopy(graph);op=edit.get('op');ids={n['id'] for n in g['nodes']}
 if op=='insert':
  node=copy.deepcopy(edit['node']);nid=node['id']
  if nid in ids:raise ValueError('Inserted node already exists')
  g['nodes'].append(node);src=edit['edge_src'];dst=edit['edge_dst'];new=[]
  for e in g['edges']:
   if e['from']==src and e['to']==dst:
    new.extend([{'id':e['id']+':a','from':src,'to':nid+'.'+_port(components[node['component_id']],'in','input')['id'],'type':copy.deepcopy(e['type'])},{'id':e['id']+':b','from':nid+'.'+_port(components[node['component_id']],'out','output')['id'],'to':dst,'type':copy.deepcopy(e['type'])}])
   else:new.append(e)
  g['edges']=new
 elif op=='prune':
  nid=edit['node_id'];g['nodes']=[n for n in g['nodes'] if n['id']!=nid];g['edges']=[e for e in g['edges'] if _split(e['from'])[0]!=nid and _split(e['to'])[0]!=nid]
 elif op=='rewire':
  for e in g['edges']:
   if e['id']==edit['edge_id']:e['to']=edit['new_dst']
 elif op=='replace':
  target=edit['node_id'];node=next(n for n in g['nodes'] if n['id']==target);node['component_id']=edit['component_id'];node['mutable']=edit.get('mutable',node.get('mutable',{}))
 elif op=='duplicate_branch':
  source=next(n for n in g['nodes'] if n['id']==edit['node_id']);clone=copy.deepcopy(source);clone['id']=edit['new_id'];g['nodes'].append(clone)
 elif op=='merge':
  raise ValueError('Merge requires an explicit typed component and merge port contract')
 else:raise ValueError('Unsupported GraphIR edit: '+str(op))
 return validate_graph(g,components)

def ablation_plan(graph):
 return [{'id':'ablate:'+n['id'],'target':n['id'],'action':'prune','pass_condition':'candidate contribution falls below threshold only if component is necessary','retrain_required':True} for n in graph.get('nodes',[])]

def score_graph(graph,components):
 ids=[n['component_id'] for n in graph.get('nodes',[])];repeated=len(ids)-len(set(ids));depth=len(graph.get('nodes',[]));cross_branch=sum(1 for e in graph.get('edges',[]) if _split(e['from'])[0] in {n['id'] for n in graph['nodes']} and _split(e['to'])[0] in {n['id'] for n in graph['nodes']})
 identity_chain=1 if all(n.get('component_id') not in ('identity','residual_identity') for n in graph.get('nodes',[])) else 0
 return {'depth_penalty':max(0,depth-1)*0.02,'repeated_subgraph_penalty':repeated*0.1,'cross_branch_information_reward':min(1.0,cross_branch/3),'anti_stack_penalty':round(max(0,depth-3)*0.05+repeated*0.1+(0 if identity_chain else 0.2),6),'structural_score':round(min(1.0,0.4*min(1,cross_branch/3)+0.6/(1+repeated)),6)}
