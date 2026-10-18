import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
class BreakthroughExplorerTests(unittest.TestCase):
 def test_generates_distinct_candidates_and_fail_closed_promotion(self):
  from network_system import profile
  from breakthrough_explorer import build_exploration,evaluate_promotion
  system=profile('hybrid');components=[{'id':'attention_plus','family':'attention'},{'id':'memory_router','family':'memory'},{'id':'spectral_bridge','family':'operator'}]
  result=build_exploration(system,components,budget=4);self.assertEqual(result['status'],'design_only');self.assertTrue(result['candidates']);self.assertTrue(all(c['validation_plan']['gates'] for c in result['candidates']))
  self.assertEqual(evaluate_promotion(result['candidates'][0],{})['status'],'blocked')
 def test_promotion_requires_all_receipts_and_rejects_counterexample(self):
  from breakthrough_explorer import evaluate_promotion
  receipts={'candidate_metrics':{},'baseline_metrics':{},'ablation_metrics':{},'counterexample_receipt':{},'seed_receipts':{},'cost_receipt':{},'baseline_improvement':True,'mechanism_supported':True,'repeatable':True,'counterexample_found':True}
  self.assertEqual(evaluate_promotion({'id':'c'},receipts)['status'],'blocked')
 def test_architecture_design_emits_required_deliverables_and_checks_attention_heads(self):
  from architecture_design import design,validate_design
  record=validate_design(design('long_context_nlp',[128,64],[128,320],sequence_length=128,depth=4,width=256,attention_heads=8));self.assertEqual(record['architecture_choice']['family'],'hybrid');self.assertIn('parameter_analysis',record['deliverables']);self.assertTrue(record['design_principles']['skip_connections'])
  with self.assertRaises(ValueError):design('nlp',[128,64],[128,320],sequence_length=128,width=250,attention_heads=8)
 def test_model_diagnostics_summarize_deficits_strategies_and_micro_designs(self):
  from model_diagnostics import diagnose
  task={'schema_version':'1.0','task_id':'d','goal':'x','symbols':{'B':1},'inputs':[{'name':'x','shape':['B',2],'dtype':'float64','unit':'1'}],'outputs':[{'name':'y','shape':['B',2],'dtype':'float64','unit':'1'}],'constraints':{'allowed_ops':['identity','linear','add','relu','tanh','scale','matmul','layernorm','softmax'],'nonnegative_outputs':False},'budgets':{'max_nodes':8,'max_parameters':16,'max_candidates':2},'objective':{'metric':'mse','direction':'lower_better','maximum':1.,'min_improvement':0.},'dataset':{'path':'unused','sha256':'0'*64}}
  model={'schema_version':'1.0','inputs':[{'id':'x','shape':['B',2],'dtype':'float64'}],'parameters':[],'nodes':[{'id':'n','op':'identity','inputs':['x'],'attributes':{},'parameters':{}}],'outputs':{'y':'n'}}
  result=diagnose(model,task);self.assertTrue(result['deficits']);self.assertTrue(result['training_strategies']);self.assertIn('evidence_policy',result)
 def test_architecture_design_selects_components_by_function_across_families(self):
  from architecture_design import design
  r=design('image_classification',[32,32,3],[10],required_functions=['long_range_dependency','spectral_or_physics'],component_catalog=[{'id':'ssm','family':'state_space'},{'id':'fno','family':'neural_operator'}])
  self.assertEqual(r['architecture_choice']['component_sources'],['ssm','fno']);self.assertEqual(r['architecture_choice']['functional_requirements'],['long_range_dependency','spectral_or_physics'])
if __name__=='__main__':unittest.main()



