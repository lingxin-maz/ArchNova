# -*- coding: utf-8 -*-
"""Bounded arithmetic and dimensional checks. No eval, calls or attribute access."""
import ast
import math
import operator
import statistics

BASE_UNITS = {'FLOP','byte','second','token','sample','parameter'}
OPERATORS = {'gt':operator.gt,'ge':operator.ge,'lt':operator.lt,'le':operator.le}


def finite(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError('Expected a finite numeric value')
    try:
        value = float(value)
    except (ValueError, OverflowError):
        raise ValueError('Numeric value outside supported range')
    if not math.isfinite(value) or abs(value) > 1e200:
        raise ValueError('Numeric value outside supported finite range')
    return value


def quantity(value, dimensions):
    return {'value':value,'dimensions':{k:v for k,v in dimensions.items() if v}}


def _power(node):
    sign = 1
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        sign = -1 if isinstance(node.op, ast.USub) else 1
        node = node.operand
    if not isinstance(node, ast.Num) or isinstance(node.n, bool) or not isinstance(node.n, int):
        raise ValueError('Exponent must be a literal integer')
    power = sign * node.n
    if abs(power) > 8:
        raise ValueError('Exponent outside -8..8')
    return power


def _parse(expression):
    if not isinstance(expression, str) or len(expression) > 512:
        raise ValueError('Expression must be a string of at most 512 characters')
    try:
        tree = ast.parse(expression, mode='eval')
        if len(list(ast.walk(tree))) > 128:
            raise ValueError('Expression exceeds node budget')
    except (SyntaxError, RecursionError, MemoryError) as exc:
        raise ValueError('Invalid expression: ' + type(exc).__name__)
    return tree.body


def _walk(node, variables, symbolic=False, unit_mode=False, depth=0):
    if depth > 32:
        raise ValueError('Expression exceeds nesting budget')
    if isinstance(node, ast.Num) and not isinstance(node.n, bool):
        return quantity(None if symbolic else finite(node.n), {})
    if isinstance(node, ast.Name) and node.id in variables:
        return variables[node.id]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)) and not unit_mode:
        item = _walk(node.operand,variables,symbolic,unit_mode,depth+1)
        return quantity(None if symbolic else (-item['value'] if isinstance(node.op,ast.USub) else item['value']),item['dimensions'])
    if not isinstance(node,ast.BinOp) or not isinstance(node.op,(ast.Add,ast.Sub,ast.Mult,ast.Div,ast.Pow)):
        raise ValueError('Unsupported expression node or unknown variable: ' + type(node).__name__)
    a = _walk(node.left,variables,symbolic,unit_mode,depth+1)
    if isinstance(node.op,ast.Pow):
        power = _power(node.right)
        try:
            return quantity(None if symbolic else finite(a['value'] ** power),{k:v*power for k,v in a['dimensions'].items()})
        except (ZeroDivisionError,OverflowError):
            raise ValueError('Invalid power arithmetic')
    b = _walk(node.right,variables,symbolic,unit_mode,depth+1)
    if isinstance(node.op,(ast.Add,ast.Sub)):
        if unit_mode or a['dimensions'] != b['dimensions']:
            raise ValueError('Addition/subtraction requires identical dimensions')
        value = None if symbolic else finite(a['value'] + (b['value'] if isinstance(node.op,ast.Add) else -b['value']))
        return quantity(value,a['dimensions'])
    dims = dict(a['dimensions'])
    sign = -1 if isinstance(node.op,ast.Div) else 1
    for key,value in b['dimensions'].items():dims[key] = dims.get(key,0) + sign*value
    try:
        value = None if symbolic else finite(a['value']/b['value'] if sign==-1 else a['value']*b['value'])
    except (ZeroDivisionError,OverflowError):
        raise ValueError('Invalid multiplication/division arithmetic')
    return quantity(value,dims)


def unit_dimensions(unit):
    variables={key:quantity(1,{key:1}) for key in BASE_UNITS}
    try:
        result=_walk(_parse(unit),variables,unit_mode=True)
    except ValueError as exc:
        raise ValueError('Unknown or invalid unit expression %r: %s' % (unit, exc))
    if result['value'] != 1:
        raise ValueError('Units cannot include scaling factors; represent conversions explicitly')
    return result['dimensions']


def evaluate_expression(expression, variables, symbolic=False):
    env={}
    for key,value in variables.items():
        if not isinstance(key,str) or not key.isidentifier() or key.startswith('_'):
            raise ValueError('Invalid variable identifier')
        dims = value.get('dimensions')
        if dims is None:dims=unit_dimensions(value['unit'])
        env[key]=quantity(None if symbolic else finite(value['value']),dims)
    return _walk(_parse(expression),env,symbolic=symbolic)


def evaluate_decision(rule, metric, observation=None):
    if rule['metric_id'] != metric['id']:
        raise ValueError('Decision metric does not match metric definition')
    metric_unit=unit_dimensions(metric['unit'])
    typed={'baseline':quantity(None,metric_unit),'candidate':quantity(None,metric_unit)}
    dimensions=evaluate_expression(rule['expression'],typed,symbolic=True)['dimensions']
    if dimensions != unit_dimensions(rule['threshold']['unit']):
        raise ValueError('Decision threshold units do not match expression')
    threshold=finite(rule['threshold']['value'])
    if rule['operator'] not in OPERATORS:
        raise ValueError('Unknown comparison operator')
    if observation is None:return {'status':'pending','reject':None,'reason':'No observations supplied'}
    for field in ('metric_id','condition_id','aggregation'):
        if observation.get(field) != rule[field]:raise ValueError('Observation mismatch: '+field)
    if unit_dimensions(observation.get('unit','')) != metric_unit:
        raise ValueError('Observation units mismatch')
    seeds=observation.get('seeds',[])
    if not isinstance(seeds,list) or any(isinstance(s,bool) or not isinstance(s,int) for s in seeds) or len(set(seeds)) != len(seeds) or len(seeds)<rule['min_seeds']:
        raise ValueError('Insufficient or duplicate paired seeds')
    baseline,candidate=observation.get('baseline'),observation.get('candidate')
    if not isinstance(baseline,list) or not isinstance(candidate,list) or len(baseline)!=len(seeds) or len(candidate)!=len(seeds):
        raise ValueError('Baseline and candidate require one value per paired seed')
    aggregate={'mean':statistics.mean,'median':statistics.median}.get(rule['aggregation'])
    if aggregate is None:raise ValueError('Unsupported aggregation')
    env={'baseline':{'value':aggregate([finite(v) for v in baseline]),'unit':metric['unit']},
         'candidate':{'value':aggregate([finite(v) for v in candidate]),'unit':metric['unit']}}
    result=evaluate_expression(rule['expression'],env)
    return {'status':'evaluated','reject':OPERATORS[rule['operator']](result['value'],threshold),
            'value':result['value'],'threshold':threshold,'dimensions':result['dimensions'],
            'aggregation':rule['aggregation'],'paired_seeds':seeds}


def check_numeric(data, rep):
    model=data['cost_model']['calculation'];env=dict(model['variables']);terms={}
    for term in model['terms']:
        name=term['id']
        if name in env or name in terms:
            rep.err('calculation.'+name,'Duplicate calculation identifier');continue
        try:
            value=evaluate_expression(term['expression'],env)
            if value['dimensions']!=unit_dimensions(term['unit']) or value['value']<0:
                raise ValueError('Cost term unit mismatch or negative cost')
            if not math.isclose(value['value'],finite(term['expected_value']),rel_tol=1e-9,abs_tol=1e-8):
                raise ValueError('Expected cost value differs from evaluated expression')
            if term['part_id'] not in {p['id'] for p in data['parts']}:
                raise ValueError('Cost term points to unknown part')
            terms[name]=(term,value);env[name]=value
        except (ValueError,KeyError,TypeError) as exc:rep.err('calculation.'+name,str(exc))
    for name in model['dominant_term_ids']:
        if name not in terms:
            rep.err('calculation.dominant_term_ids','Unknown term '+name);continue
        term,value=terms[name]
        if term['role']!='current' or term['part_id'] not in data['cost_model']['dominant_part_ids']:
            rep.err(name,'Dominant cost must refer to a declared current dominant part')
        comparable=[v['value'] for t,v in terms.values() if t['role']=='current' and v['dimensions']==value['dimensions']]
        if comparable and value['value'] < max(comparable):rep.err(name,'Claimed dominant term is not maximal at the declared scale')
    metrics={m['id']:m for m in data['metrics']};seen=set()
    for proposal in data['proposals']:
        pid=proposal['id']
        if pid in seen:rep.err('proposals','Duplicate proposal id: '+pid)
        seen.add(pid)
        try:
            prediction=proposal['numerical_prediction'];result=evaluate_expression(prediction['expression'],env)
            if result['dimensions']!=unit_dimensions(prediction['unit']):raise ValueError('Prediction unit mismatch')
            if not math.isclose(result['value'],finite(prediction['expected_value']),rel_tol=1e-9,abs_tol=finite(prediction['tolerance'])):
                raise ValueError('Prediction value differs from evaluated expression')
            rule=proposal['decision_rule']
            if rule['metric_id'] not in metrics:raise ValueError('Unknown guardrail metric')
            evaluate_decision(rule,metrics[rule['metric_id']])
        except (ValueError,KeyError,TypeError) as exc:rep.err(pid,str(exc))
    for metric in data['metrics']:
        try:unit_dimensions(metric['unit'])
        except (ValueError,KeyError,TypeError) as exc:rep.err('metrics.'+metric['id'],str(exc))
