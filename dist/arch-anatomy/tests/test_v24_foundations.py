# -*- coding: utf-8 -*-
import copy,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))

def outline(premises=()):
    return {'statement':'A stated identity','domain':'real scalars','quantifiers':'all x','assumptions':[],
        'steps':[{'id':'step:1','statement':'identity','justification':'Premises','premise_ids':list(premises)}],
        'evidence_claim_ids':[]}

def claim(cid,premises=()):
    return {'claim_id':cid,'subject':'part:A','predicate':'equals','object':'identity','claim_type':'derivation',
            'evidence':[],'proof_outline':outline(premises)}

class ProofGraphTests(unittest.TestCase):
    def test_direct_and_cross_claim_cycles_are_rejected(self):
        from proof_dependencies import dependency_graph
        for claims in ([claim('claim:A',['claim:A'])],
                       [claim('claim:A',['claim:B']),claim('claim:B',['claim:A'])]):
            graph=dependency_graph({'claims':claims})
            self.assertTrue(any('cycle' in e.lower() for e in graph['issues']))
    def test_transitive_dependency_material_is_in_task_hash(self):
        from semantic_review import build_tasks
        data={'claims':[claim('claim:A'),claim('claim:B',['claim:A']),claim('claim:C',['claim:B'])]}
        tasks={t['target_id']:t for t in build_tasks(data,Path('.'))}
        self.assertEqual(set(tasks['claim:C']['dependency_ids']),{'claim:A','claim:B'})
        data['claims'][0]['object']='changed foundational assertion'
        updated={t['target_id']:t for t in build_tasks(data,Path('.'))}
        self.assertNotEqual(tasks['claim:C']['input_hash'],updated['claim:C']['input_hash'])
    def test_unresolved_premise_prevents_positive_conclusion(self):
        from semantic_review import validate_response
        task={'kind':'mathematics','target_id':'claim:B','obligation_ids':['S1'],
              'payload':{'proof_outline':outline(),'evidence':[],'machine_checks':[]},
              'prerequisite_status':{'claim:A':'insufficient'}}
        result={'verdict':'supported','rationale':'Assuming A','scope_limits':['Conditional on A'],
            'obligations':[{'id':'S1','status':'satisfied','reason':'A'}],'evidence_ids':[],'counterexample':None}
        with self.assertRaises(ValueError):validate_response(task,result)
    def test_actual_subgraph_and_interfaces_are_supplied(self):
        from architecture_context import review_context
        data={'interface_contract':{'input_object':'causal sequence'},
            'parts':[{'id':'A','io_in':'x','io_out':'state'},{'id':'B','io_in':'state','io_out':'y'}],
            'dataflow':{'node_parts':['A','B'],'ports':[{'id':'a','owner':'A','direction':'output','state':'recurrence'},
            {'id':'b','owner':'B','direction':'input','state':'recurrence'}],
            'edges':[{'id':'e','source':'a','target':'b','kind':'state','delay':1}],
            'shared_parameters':[{'id':'w','parts':['A','B']}],'bindings':[],'coupled_replacements':[]}}
        context=review_context(data,{'part_id':'A','relation':'behaviorally_equivalent'})
        self.assertEqual(context['interface_contract']['input_object'],'causal sequence')
        self.assertEqual({p['id'] for p in context['parts']},{'A','B'})
        self.assertEqual(context['dataflow']['edges'][0]['delay'],1)
        self.assertIn('comparison_semantics',context)

class DependencyExecutionTests(unittest.TestCase):
    def test_review_states_propagate_unknown_and_accept_joint_batch(self):
        from semantic_review import build_tasks,run_reviews
        data={'claims':[claim('claim:A'),claim('claim:B',['claim:A'])]}
        tasks=build_tasks(data,Path('.'))
        def reviewer(task):return {'verdict':'supported','rationale':'Local identity under declared real domain',
            'obligations':[{'id':key,'status':'satisfied','reason':'Checked inference'} for key in task['obligation_ids']],
            'evidence_ids':[],'counterexample':None,'scope_limits':['Only declared scalar identities']}
        result=run_reviews(tasks,reviewer,{'backend':'host','identity':'test','model':'test'})
        self.assertEqual([r['verdict'] for r in result['reviews']],['supported','supported'])
        data['semantic_reviews']=result['reviews']
        updated=build_tasks(data,Path('.'))
        self.assertEqual(updated[1]['prerequisite_status'],{'claim:A':'supported'})
        data['semantic_reviews'][0]['verdict']='insufficient'
        updated=build_tasks(data,Path('.'))
        self.assertEqual(updated[1]['prerequisite_status'],{'claim:A':'insufficient'})

class MathSemanticsTests(unittest.TestCase):
    def test_symbolic_zero_power_keeps_nonzero_domain(self):
        from proof_checks import check_identity
        case={'variables':['x'],'lhs':'x**0','rhs':'1','nonzero':[]}
        self.assertEqual(check_identity(case)['status'],'conditional_identity')
        case['nonzero']=['x']
        self.assertEqual(check_identity(case)['status'],'verified_identity')
    def test_matrix_and_float_semantics_are_not_exact_real_proofs(self):
        from proof_checks import check_identity
        for semantics in ('matrix','floating_point'):
            result=check_identity({'semantics':semantics,'variables':['x'],'lhs':'x+x','rhs':'2*x','nonzero':[]})
            self.assertEqual(result['status'],'inconclusive')

class RepositoryCoverageTests(unittest.TestCase):
    def test_missing_proposal_exploration_is_detected(self):
        from repository_coverage import check_explorations
        class Report:
            def __init__(self):self.errors=[]
            def err(self,path,message):self.errors.append(message)
        rep=Report();check_explorations({'proposals':[{'id':'p1'}],'repository_explorations':[],
                                      'repository_discoveries':[]},rep,release=True)
        self.assertTrue(rep.errors)
    def test_import_following_fetches_core_implementation(self):
        import github_repos
        from unittest.mock import patch
        files=[{'path':'pkg/wrapper.py','text':'from .core import scan\n','commit_sha':'a'*40}]
        tree=[{'path':'pkg/wrapper.py','type':'blob'},{'path':'pkg/core.py','type':'blob'}]
        import base64
        response={'ok':True,'data':{'encoding':'base64','content':base64.b64encode(b'def scan(x): return x').decode(),'sha':'b'*40}}
        with patch.object(github_repos,'get_json',return_value=response):
            result=github_repos.follow_imports('owner/repo','a'*40,tree,files,max_files=1)
        self.assertEqual(result['files'][0]['path'],'pkg/core.py')
        self.assertEqual(result['files'][0]['discovered_from'],'pkg/wrapper.py')
    def test_external_imports_become_leads_not_automatic_trust(self):
        from github_repos import import_leads
        result=import_leads('pkg/wrapper.py','from assoc_scan import AssocScan\n')
        self.assertEqual(result['external_modules'],['assoc_scan'])

class ReleasePolicyTests(unittest.TestCase):
    def check(self,mode,disposition,verdict):
        from publication_policy import check_publication
        class Report:
            def __init__(self):self.errors=[]
            def err(self,path,message):self.errors.append(message)
        data={'publication':{'mode':mode,'conclusions':[{'kind':'citation','target_id':'claim:A',
            'disposition':disposition,'rationale':'Explicitly report the unresolved finding','conditions':[]}]}}
        states={('citation','claim:A'):verdict};rep=Report();check_publication(data,states,rep,True);return rep
    def test_honest_report_can_publish_open_or_negative_findings(self):
        self.assertFalse(self.check('honest_report','open','insufficient').errors)
        self.assertFalse(self.check('honest_report','rejected','contradicted').errors)
    def test_unsupported_endorsement_is_rejected(self):
        self.assertTrue(self.check('honest_report','endorsed','partial').errors)
        self.assertTrue(self.check('supported_conclusions','open','insufficient').errors)

if __name__=='__main__':unittest.main()
