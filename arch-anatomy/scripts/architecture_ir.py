# -*- coding: utf-8 -*-
"""A bounded explicit operator IR: wiring, attributes, parameters and static shape inference."""
import copy,json,math
from pathlib import Path
from jsonschema import Draft4Validator
from orchestrator import digest
from task_spec import read_json,validate_task,resolve_shape,matrix_shape
ROOT=Path(__file__).resolve().parents[1]
def _prod(values):
    result=1
    for value in values: result*=value
    return result

def semantic_hash(model):return digest(model)

def artifact_semantics(artifact):
    # Bind the complete declared mathematical object, not just port topology.
    return {key:copy.deepcopy(artifact[key]) for key in ('operators','dataflow','runtime_ir','task_spec_hash') if key in artifact}

def validate_ir(model,task):
    validate_task(task)
    if any(p['unit']!='1' for p in task['inputs']+task['outputs']):raise ValueError('Reference runtime supports dimensionless tensors only; explicit physical-unit adapter required')
    errors=list(Draft4Validator(read_json(ROOT/'assets/runtime-ir.schema.json')).iter_errors(model))
    if errors:raise ValueError('Runtime IR: '+errors[0].message)
    expected={p['name']:p for p in task['inputs']}
    if len({p['id'] for p in model['inputs']})!=len(model['inputs']) or {p['id'] for p in model['inputs']}!=set(expected):raise ValueError('Model input signature differs from target')
    shapes={};dtypes={}
    for inp in model['inputs']:
        spec=expected[inp['id']]
        shape=resolve_shape(inp['shape'],task['symbols'])
        if shape!=resolve_shape(spec['shape'],task['symbols']) or inp['dtype']!=spec['dtype']:raise ValueError('Model input type/shape mismatch')
        shapes[inp['id']]=shape;dtypes[inp['id']]=inp['dtype']
    params={};parameter_count=0
    for param in model['parameters']:
        pid=param['id']
        if pid in params:raise ValueError('Duplicate parameter id')
        shape=matrix_shape(param['value']);params[pid]=shape;parameter_count+=shape[0]*shape[1]
    if len(model['nodes'])>task['budgets']['max_nodes'] or parameter_count>task['budgets']['max_parameters']:raise ValueError('Target resource budget exceeded')
    node_ids=[n['id'] for n in model['nodes']]
    if len(set(node_ids))!=len(node_ids) or set(node_ids)&set(shapes):raise ValueError('Duplicate/ambiguous node id')
    used_parameters=set();cost=0
    for node in model['nodes']:
        nid,op=node['id'],node['op'];refs=node['inputs'];attrs=node['attributes'];bindings=node['parameters']
        if op not in task['constraints']['allowed_ops']:raise ValueError('Operator forbidden by task contract: '+op)
        if any(ref not in shapes for ref in refs):raise ValueError('IR needs topologically ordered resolvable inputs; cycles unsupported')
        if any(pid not in params for pid in bindings.values()):raise ValueError('Unresolved parameter binding')
        used_parameters.update(bindings.values());a=shapes[refs[0]];b=shapes[refs[1]] if len(refs)>1 else None
        if op=='scale':
            if len(refs)!=1 or set(attrs)!={'factor'} or bindings:raise ValueError('Invalid scale contract')
            factor=attrs['factor']
            if isinstance(factor,bool) or not isinstance(factor,(int,float)) or not math.isfinite(factor) or abs(factor)>1e100:raise ValueError('Invalid finite scale factor')
            out=list(a);cost+=a[0]*a[1]
        elif op in ('identity','relu','tanh'):
            if len(refs)!=1 or attrs or bindings:raise ValueError('Invalid unary operator contract')
            out=list(a);cost+=a[0]*a[1]
        elif op=='add':
            if len(refs)!=2 or a!=b or attrs or bindings:raise ValueError('Addition requires identical shape and no implicit broadcast')
            out=list(a);cost+=a[0]*a[1]
        elif op=='matmul':
            if len(refs)!=2 or a[1]!=b[0] or attrs or bindings:raise ValueError('Matrix product dimension mismatch')
            out=a[:-2]+[a[-2],b[-1]];cost+=2*(a[-2])*a[-1]*b[-1] * (1 if not a[:-2] else __import__('math').prod(a[:-2]))
        elif op=='transpose':
            if len(refs)!=1 or bindings or (attrs and set(attrs)!= {'axes'}):raise ValueError('Transpose requires one input and optional axes')
            axes=attrs.get('axes',list(reversed(range(len(a)))))
            if sorted(axes)!=list(range(len(a))):raise ValueError('Transpose axes must be a permutation')
            out=[a[i] for i in axes];cost+=_prod(a)
        elif op=='softmax':
            if len(refs)!=1 or set(attrs)!={'axis'} or attrs['axis']!='feature' or bindings:raise ValueError('Softmax requires axis=feature')
            out=list(a);cost+=5*_prod(a)
        elif op=='layernorm':
            if len(refs)!=1 or set(attrs)!={'axis','eps'} or attrs['axis']!='feature' or bindings:raise ValueError('Layernorm requires axis=feature and eps')
            eps=attrs['eps']
            if isinstance(eps,bool) or not isinstance(eps,(int,float)) or not math.isfinite(eps) or not 0<eps<=1:raise ValueError('Invalid layernorm eps')
            out=list(a);cost+=8*_prod(a)
        elif op=='reshape':
            if len(refs)!=1 or set(attrs)!={'shape'} or bindings:raise ValueError('Reshape requires a static shape')
            shape=attrs['shape']
            if not isinstance(shape,list) or not 1<=len(shape)<=4 or any(type(x)!=int or not 1<=x<=64 for x in shape) or _prod(shape)!=_prod(a):raise ValueError('Reshape must preserve bounded element count')
            out=list(shape);cost+=a[0]*a[1]
        elif op=='concat':
            if len(refs)!=2 or set(attrs)!={'axis'} or type(attrs['axis']) is not int or not 0<=attrs['axis']<len(a) or bindings:raise ValueError('Concat requires a valid axis')
            axis=attrs['axis']
            if len(a)!=len(b) or any(x!=y for i,(x,y) in enumerate(zip(a,b)) if i!=axis):raise ValueError('Concat non-axis dimensions must match')
            out=list(a);out[axis]+=b[axis];cost+=_prod(out)
        elif op=='linear':
            if len(refs)!=1 or attrs or not {'weight'}<=set(bindings) or set(bindings)-{'weight','bias'}:raise ValueError('Linear requires explicit weight and optional bias')
            w=params[bindings['weight']]
            if len(w)!=2 or a[-1]!=w[0]:raise ValueError('Linear weight shape mismatch; convention is last input dimension @ W')
            out=a[:-1]+[w[1]];cost+=2*_prod(a[:-1] or [1])*a[-1]*w[1]
            if 'bias' in bindings:
                if params[bindings['bias']]!=[1,w[1]]:raise ValueError('Bias must be [1,output_width]')
                cost+=_prod(out)
        else:raise ValueError('Unsupported IR op')
        if max(out)>64 or cost>1000000:raise ValueError('Prototype execution budget exceeded')
        shapes[nid]=out;dtypes[nid]='float64'
    if set(params)!=used_parameters:raise ValueError('Unused parameters must be removed or explicitly implemented')
    outputs={p['name']:p for p in task['outputs']}
    if set(model['outputs'])!=set(outputs):raise ValueError('Model output signature differs from target')
    for name,ref in model['outputs'].items():
        if ref not in shapes or shapes[ref]!=resolve_shape(outputs[name]['shape'],task['symbols']):raise ValueError('Model output shape mismatch')
    by={n['id']:n for n in model['nodes']};active=set();stack=list(model['outputs'].values())
    while stack:
        ref=stack.pop()
        if ref in active:continue
        active.add(ref)
        if ref in by:stack.extend(by[ref]['inputs'])
    if not set(node_ids)<=active:raise ValueError('Unreachable/dead operator in candidate graph')
    return {'nodes':len(node_ids),'parameters':parameter_count,'scalar_operation_proxy':cost,'shapes':shapes,'semantic_hash':semantic_hash(model),'scope':'Static rank-1..4 tensor operations; not measured FLOPs, latency or memory'}

def propose_repairs(model,task,rules):
    """Generate bounded structural hypotheses, with no access to holdout targets."""
    validate_ir(model,task);proposals=[];seen={semantic_hash(model)}
    for rule in rules:
        if rule not in ('relu','absolute'):raise ValueError('Unsupported repair rule: '+str(rule))
        candidate=copy.deepcopy(model);existing={p['id'] for p in candidate['inputs']}|{n['id'] for n in candidate['nodes']}
        def fresh(base):
            value=base;index=0
            while value in existing:index+=1;value=base+'_'+str(index)
            existing.add(value);return value
        for name,ref in list(candidate['outputs'].items()):
            pos=fresh('repair_pos_'+name)
            candidate['nodes'].append({'id':pos,'op':'relu','inputs':[ref],'attributes':{},'parameters':{}})
            result=pos
            if rule=='absolute':
                neg=fresh('repair_neg_'+name);negact=fresh('repair_negact_'+name);joined=fresh('repair_sum_'+name)
                candidate['nodes'].extend([{'id':neg,'op':'scale','inputs':[ref],'attributes':{'factor':-1.},'parameters':{}},
                                          {'id':negact,'op':'relu','inputs':[neg],'attributes':{},'parameters':{}},
                                          {'id':joined,'op':'add','inputs':[pos,negact],'attributes':{},'parameters':{}}]);result=joined
            candidate['outputs'][name]=result
        h=semantic_hash(candidate)
        if h in seen:continue
        seen.add(h)
        try:validate_ir(candidate,task)
        except ValueError as exc:
            proposals.append({'rule':rule,'model':candidate,'eligible':False,'reason':str(exc),'parent_hash':semantic_hash(model)});continue
        proposals.append({'rule':rule,'model':candidate,'eligible':True,'parent_hash':semantic_hash(model),'hypothesis':'Output nonnegative activation/branch repair; must be tested, not assumed beneficial'})
    return proposals


def node_equation(node):
    return node['op']+'('+','.join(node['inputs'])+';attributes='+json.dumps(node['attributes'],sort_keys=True,separators=(',',':'))+';parameters='+json.dumps(node['parameters'],sort_keys=True,separators=(',',':'))+')'

def declared_graph(model,task):
    summary=validate_ir(model,task);shapes=summary['shapes'];by={n['id']:n for n in model['nodes']};ports=[];edges=[]
    axes=['batch','feature'];external_outputs=set(model['outputs'].values())
    for node in model['nodes']:
        nid=node['id']
        for i,ref in enumerate(node['inputs']):
            pid=nid+':in:'+str(i);external=ref not in by
            ports.append({'id':pid,'owner':nid,'direction':'input','object_type':'tensor','shape':shapes[ref],'axes':axes[:],'dtype':'float64','unit':'1','measure':'counting','state':'none','external':external})
            if not external:edges.append({'id':'edge:'+pid,'source':ref+':out','target':pid,'kind':'data','delay':0})
        ports.append({'id':nid+':out','owner':nid,'direction':'output','object_type':'tensor','shape':shapes[nid],'axes':axes[:],'dtype':'float64','unit':'1','measure':'counting','state':'none','external':nid in external_outputs})
    owners={p['id']:[] for p in model['parameters']}
    for node in model['nodes']:
        for pid in set(node['parameters'].values()):owners[pid].append(node['id'])
    shared=[{'id':'parameter:'+pid,'parts':members,'description':'Explicit shared parameter binding: '+pid} for pid,members in owners.items() if len(members)>1]
    return {'node_parts':[n['id'] for n in model['nodes']],'ports':ports,'edges':edges,'bindings':[],'shared_parameters':shared,'coupled_replacements':[]}

def check_artifact_binding(artifact,task):
    if artifact.get('task_spec_hash')!=digest(task):raise ValueError('Artifact target contract hash missing/changed')
    if artifact['artifact_kind'] not in ('design','replacement_review'):return
    model=artifact.get('runtime_ir')
    if model is None:raise ValueError('Executable design/review requires runtime_ir; unsupported model must remain blocked')
    validate_ir(model,task)
    if digest(artifact['dataflow'])!=digest(declared_graph(model,task)):raise ValueError('Declared dataflow differs from executable IR')
    nodes={n['id']:n for n in model['nodes']}
    if {o['id'] for o in artifact['operators']}!=set(nodes):raise ValueError('Declared operators differ from executable IR')
    for operator in artifact['operators']:
        node=nodes[operator['id']]
        if operator['equation']!=node_equation(node) or operator['component_id']!='runtime:'+node['op']:
            raise ValueError('Declared operator equation/component differs from executable semantics')
    if artifact['artifact_kind']=='design':
        trial=artifact['experiment'];rule=trial['decision_rule']
        if trial['metric']!=task['objective']['metric'] or trial['direction']!=task['objective']['direction']:
            raise ValueError('Design experiment changes task objective')
        if rule['expression']!='candidate' or rule['operator']!='gt' or rule['threshold']!={'value':task['objective']['maximum'],'unit':'1'}:
            raise ValueError('Design rejection threshold differs from fixed target contract')

def make_task_artifact(model,task,kind,input_hash='0'*64):
    from task_contracts import example_artifact
    data=example_artifact(kind,input_hash);data['task_spec_hash']=digest(task);data['runtime_ir']=copy.deepcopy(model);data['dataflow']=declared_graph(model,task)
    data['operators']=[{'id':n['id'],'component_id':'runtime:'+n['op'],'equation':node_equation(n),'domain':'Finite dimensionless rank-2 tensors under fixed task contract','discretization':'Explicit static matrix reference IR','evidence_ids':['ev:proposal'],'complexity_assumptions':['Reference scalar operation proxy; no measured hardware performance']} for n in model['nodes']]
    if kind in ('design','replacement_review'):
        data['affected_parts']=[n['id'] for n in model['nodes']];data['changes_shared_parameters']=[]
    if kind=='design':
        summary=validate_ir(model,task);data['baseline']='Initial model snapshot from the locked loop run';data['objectives']=[task['goal']]
        data['cost_predictions']=[{'id':'reference_scalar_ops','expression':'C','variables':{'C':{'value':summary['scalar_operation_proxy'],'unit':'1'}},'unit':'1','assumptions':['Computed from supported IR; proxy only, not latency']}]
        data['experiment'].update(baseline=data['baseline'],metric=task['objective']['metric'],direction='lower_better',metric_definition={'id':task['objective']['metric'],'unit':'1'},
            decision_rule={'metric_id':task['objective']['metric'],'condition_id':'locked_task','aggregation':'mean','min_seeds':2,'expression':'candidate','operator':'gt','threshold':{'value':task['objective']['maximum'],'unit':'1'}},
            dataset_split='Hash-locked development and heldout samples; loop search never repairs after heldout failure',budget_control='Fixed task node/parameter/candidate limits',kill_criterion='Reject if target maximum, improvement, sampled constraints or static budget fails')
    return data



