# -*- coding: utf-8 -*-
import json
import sys
from pathlib import Path
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))

class NumericalTests(unittest.TestCase):
    def test_cost_and_units(self):
        from numeric_checks import evaluate_expression
        result=evaluate_expression('4*N*D**2*flop',{'N':{'value':8,'unit':'1'},'D':{'value':4,'unit':'1'},'flop':{'value':1,'unit':'FLOP'}})
        self.assertEqual(result['value'],512)
        self.assertEqual(result['dimensions'],{'FLOP':1})

    def test_incompatible_addition_rejected(self):
        from numeric_checks import evaluate_expression
        with self.assertRaises(ValueError):evaluate_expression('x+y',{'x':{'value':1,'unit':'byte'},'y':{'value':1,'unit':'second'}})

    def test_no_code_execution_or_unbounded_powers(self):
        from numeric_checks import evaluate_expression
        for expression in ["__import__('os').getcwd()",'x.real','[x][0]','2**100000000','x//2','lambda: 1']:
            with self.subTest(expression=expression),self.assertRaises(ValueError):
                evaluate_expression(expression,{'x':{'value':2,'unit':'1'}})

    def test_bad_arithmetic_is_not_a_result(self):
        from numeric_checks import evaluate_expression
        for expression in ['1/0','unknown+1']:
            with self.assertRaises(ValueError):evaluate_expression(expression,{})
        with self.assertRaises(ValueError):evaluate_expression('x',{'x':{'value':float('nan'),'unit':'1'}})

    def test_decision_reached_pending_and_units(self):
        from numeric_checks import evaluate_decision
        rule={'metric_id':'rel_l2','condition_id':'retrieval@8k','aggregation':'mean','min_seeds':2,
              'expression':'candidate/baseline-1','operator':'gt','threshold':{'value':0.2,'unit':'1'}}
        metric={'id':'rel_l2','unit':'1'}
        observation={'metric_id':'rel_l2','condition_id':'retrieval@8k','unit':'1','aggregation':'mean','seeds':[0,1], 'baseline':[1,1],'candidate':[1.3,1.3]}
        self.assertEqual(evaluate_decision(rule,metric,None)['status'],'pending')
        result=evaluate_decision(rule,metric,observation)
        self.assertEqual(result['status'],'evaluated');self.assertTrue(result['reject'])
        observation['candidate']=[1.1,1.1]
        self.assertFalse(evaluate_decision(rule,metric,observation)['reject'])
        observation['unit']='byte'
        with self.assertRaises(ValueError):evaluate_decision(rule,metric,observation)

    def test_decision_needs_matching_conditions_and_paired_seeds(self):
        from numeric_checks import evaluate_decision
        rule={'metric_id':'m','condition_id':'a','aggregation':'mean','min_seeds':2,'expression':'candidate-baseline','operator':'gt','threshold':{'value':1,'unit':'second'}}
        obs={'metric_id':'m','condition_id':'b','unit':'second','aggregation':'mean','seeds':[0,1],'baseline':[1,2],'candidate':[2,3]}
        with self.assertRaises(ValueError):evaluate_decision(rule,{'id':'m','unit':'second'},obs)
        obs.update(condition_id='a',seeds=[0,0])
        with self.assertRaises(ValueError):evaluate_decision(rule,{'id':'m','unit':'second'},obs)

class RetrievalTests(unittest.TestCase):
    def test_weak_title_match_never_selects_first(self):
        from literature import match_title
        result=match_title('Operator learning on variable domains',[{'id':'W1','title':'An unrelated physics paper'}])
        self.assertEqual(result['status'],'ambiguous');self.assertIsNone(result['work'])
        self.assertEqual(len(result['candidates']),1)

    def test_exact_duplicate_titles_remain_ambiguous(self):
        from literature import match_title
        result=match_title('Same Title',[{'id':'W1','title':'Same Title'},{'id':'W2','title':'Same Title'}])
        self.assertEqual(result['status'],'ambiguous')

    def test_unique_exact_title_is_only_title_identity(self):
        from literature import match_title
        result=match_title('Exact Title',[{'id':'W1','title':'Exact Title'}])
        self.assertEqual(result['status'],'resolved');self.assertEqual(result['identity_basis'],'title_only')

    def test_title_year_and_author_constraints(self):
        from literature import match_title
        works=[{'id':'W1','title':'Exact Title','publication_year':2020,'authorships':[{'author':{'display_name':'Alice Smith'}}]},
               {'id':'W2','title':'Exact Title','publication_year':2021,'authorships':[{'author':{'display_name':'Bob Jones'}}]}]
        self.assertEqual(match_title('Exact Title',works,author='Alice Smith',year=2020)['work']['id'],'W1')
        self.assertEqual(match_title('Exact Title',works,author='Carol',year=2020)['status'],'ambiguous')

    def test_network_wrapper_reports_query_receipt(self):
        import literature
        with patch.object(literature,'get_json',return_value={'results':[{'id':'W1','title':'No match'}]}):
            result=literature.resolve_title('Target title')
        self.assertEqual(result['status'],'ambiguous')
        self.assertTrue(result['receipt']['response_sha256']);self.assertIn('endpoint',result['receipt'])

if __name__=='__main__':unittest.main()
