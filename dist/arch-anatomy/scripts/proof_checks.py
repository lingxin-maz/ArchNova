# -*- coding: utf-8 -*-
"""Exact, budgeted rational identities. This is not a general theorem prover."""
import ast
from fractions import Fraction
import itertools
import io
import tokenize


class Algebra:
    def __init__(self,variables):
        if len(variables)>6 or len(set(variables))!=len(variables) or any(not v.isidentifier() or v.startswith('_') for v in variables):
            raise ValueError('Use at most six unique variable identifiers')
        self.variables=variables;self.zero=(0,)*len(variables);self.operations=0
    def const(self,value):return {self.zero:Fraction(value)} if value else {}
    def bounded(self,p):
        p={k:v for k,v in p.items() if v}
        if len(p)>512 or any(sum(k)>48 or v.numerator.bit_length()>4096 or v.denominator.bit_length()>4096 for k,v in p.items()):
            raise ValueError('Algebra expansion/coefficient budget exceeded')
        return p
    def add(self,p,q,sign=1):
        out=dict(p)
        for k,v in q.items():out[k]=out.get(k,Fraction(0))+sign*v
        return self.bounded(out)
    def mul(self,p,q):
        self.operations+=len(p)*len(q)
        if self.operations>50000:raise ValueError('Algebra operation budget exceeded')
        out={}
        for a,av in p.items():
            for b,bv in q.items():
                k=tuple(x+y for x,y in zip(a,b));out[k]=out.get(k,Fraction(0))+av*bv
        return self.bounded(out)
    def power(self,p,n):
        out=self.const(1)
        for _ in range(n):out=self.mul(out,p)
        return out
    def parse(self,expression):
        if not isinstance(expression,str) or len(expression)>512:raise ValueError('Expression length budget exceeded')
        tree=ast.parse(expression,mode='eval')
        source_lines=expression.splitlines()
        self.number_literals={(t.start[0],len(source_lines[t.start[0]-1][:t.start[1]].encode('utf-8'))):t.string.replace('_','')
                              for t in tokenize.generate_tokens(io.StringIO(expression).readline) if t.type==tokenize.NUMBER}
        if len(list(ast.walk(tree)))>128:raise ValueError('Expression node budget exceeded')
        return self.walk(tree.body)
    def walk(self,node,depth=0):
        if depth>32:raise ValueError('Expression nesting budget exceeded')
        one=self.const(1)
        if isinstance(node,ast.Num) and not isinstance(node.n,bool):
            value=Fraction(self.number_literals[(node.lineno,node.col_offset)])
            return self.bounded(self.const(value)),one,[]
        if isinstance(node,ast.Name) and node.id in self.variables:
            mon=list(self.zero);mon[self.variables.index(node.id)]=1
            return {tuple(mon):Fraction(1)},one,[]
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.UAdd,ast.USub)):
            n,d,needs=self.walk(node.operand,depth+1)
            return ({k:-v for k,v in n.items()} if isinstance(node.op,ast.USub) else n),d,needs
        if not isinstance(node,ast.BinOp) or not isinstance(node.op,(ast.Add,ast.Sub,ast.Mult,ast.Div,ast.Pow)):
            raise ValueError('Unsupported syntax; only rational arithmetic is machine-checked')
        an,ad,needs=self.walk(node.left,depth+1)
        if isinstance(node.op,ast.Pow):
            sign=1;ex=node.right
            if isinstance(ex,ast.UnaryOp) and isinstance(ex.op,(ast.UAdd,ast.USub)):
                sign=-1 if isinstance(ex.op,ast.USub) else 1;ex=ex.operand
            if not isinstance(ex,ast.Num) or isinstance(ex.n,bool) or not isinstance(ex.n,int) or abs(ex.n)>8:
                raise ValueError('Exponent must be a literal integer in -8..8')
            power=sign*ex.n
            if power<0:
                if not an:raise ValueError('Negative power of identically zero expression')
                return self.power(ad,-power),self.power(an,-power),needs+[an]
            if power==0:
                if not an:raise ValueError('Undefined 0**0 excluded from this checker')
                needs=needs+[an]
            return self.power(an,power),self.power(ad,power),needs
        bn,bd,bneeds=self.walk(node.right,depth+1);needs+=bneeds
        if isinstance(node.op,(ast.Add,ast.Sub)):
            return self.add(self.mul(an,bd),self.mul(bn,ad),-1 if isinstance(node.op,ast.Sub) else 1),self.mul(ad,bd),needs
        if isinstance(node.op,ast.Mult):return self.mul(an,bn),self.mul(ad,bd),needs
        if not bn:raise ValueError('Division by identically zero expression')
        return self.mul(an,bd),self.mul(ad,bn),needs+[bn]
    def canonical(self,p):
        if not p:raise ValueError('Impossible nonzero assumption')
        divisor=p[sorted(p)[0]]
        return tuple((k,str(v/divisor)) for k,v in sorted(p.items()))
    def describe(self,p):
        terms=[]
        for powers,coefficient in sorted(p.items()):
            factors=[v+('**'+str(n) if n!=1 else '') for v,n in zip(self.variables,powers) if n]
            terms.append(str(coefficient)+('*'+'*'.join(factors) if factors else ''))
        return ' + '.join(terms) or '0'
    def at(self,p,values):
        out=Fraction(0)
        for powers,coefficient in p.items():
            value=coefficient
            for x,power in zip(values,powers):value*=x**power
            out+=value
        return out


def check_identity(case):
    scope='rational_expressions_over_reals'
    try:
        if case.get('semantics','real_scalar')!='real_scalar':raise ValueError('Exact kernel supports real_scalar semantics only; matrices and floating programs need other validators')
        if len(case.get('nonzero',[]))>32:raise ValueError('Nonzero assumption budget exceeded')
        algebra=Algebra(case['variables'])
        ln,ld,lneeds=algebra.parse(case['lhs']);rn,rd,rneeds=algebra.parse(case['rhs'])
        guards=[]
        for expression in case.get('nonzero',[]):
            gn,gd,gneeds=algebra.parse(expression)
            if any(any(p) for p in gd):raise ValueError('Nonzero assumptions must be polynomials')
            algebra.canonical(gn);guards.append(gn)
        declared={algebra.canonical(p) for p in guards}
        needs={algebra.canonical(p):p for p in lneeds+rneeds if any(any(k) for k in p)}
        missing=[algebra.describe(p) for k,p in needs.items() if k not in declared]
        difference=algebra.add(algebra.mul(ln,rd),algebra.mul(rn,ld),-1)
        if not difference:
            return {'status':'conditional_identity' if missing else 'verified_identity','scope':scope,
                    'required_nonzero':missing,'declared_nonzero':case.get('nonzero',[]),
                    'method':'exact_fraction_polynomial_cross_multiplication','limitation':'Declared domain assumptions are not proved applicable to the architecture'}
        for values in itertools.islice(itertools.product(map(Fraction,[-2,-1,0,1,2]),repeat=len(case['variables'])),256):
            if any(algebra.at(g,values)==0 for g in guards):continue
            a,b=algebra.at(ld,values),algebra.at(rd,values)
            if not a or not b or any(algebra.at(g,values)==0 for g in lneeds+rneeds):continue
            lhs,rhs=algebra.at(ln,values)/a,algebra.at(rn,values)/b
            if lhs!=rhs:return {'status':'counterexample','scope':scope,'counterexample':{
                'assignment':dict(zip(case['variables'],map(str,values))),'lhs':str(lhs),'rhs':str(rhs)},
                'method':'exact_fraction_evaluation'}
        return {'status':'inconclusive','scope':scope,'reason':'Nonzero symbolic difference; no admissible witness in bounded search'}
    except (ValueError,SyntaxError,KeyError,TypeError,OverflowError,RecursionError,tokenize.TokenError) as exc:
        return {'status':'inconclusive','scope':scope,'reason':str(exc)}


def main():
    import argparse,json
    from pathlib import Path
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('case');ap.add_argument('-o','--output');a=ap.parse_args()
    result=check_identity(json.loads(Path(a.case).read_text(encoding='utf-8-sig')))
    text=json.dumps(result,ensure_ascii=False,indent=2)
    if a.output:Path(a.output).write_text(text+'\n',encoding='utf-8')
    print(text)
    return 0 if result['status']=='verified_identity' else (1 if result['status']=='counterexample' else 2)
if __name__=='__main__':raise SystemExit(main())
