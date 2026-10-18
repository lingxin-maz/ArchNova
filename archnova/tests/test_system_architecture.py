import sys,unittest,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
class SystemArchitectureTests(unittest.TestCase):
 def test_profiles_cover_llm_and_non_llm_families(self):
  from network_system import profile,validate_system
  for family in ('llm','cnn','rnn','state_space','diffusion','gnn','neural_operator','multimodal'):
   record=profile(family);self.assertEqual(validate_system(record)['family'],family);self.assertTrue(record['views']['training']); self.assertTrue(record['lifecycle']); self.assertTrue(record['state_transitions'])
 def test_unknown_view_component_and_duplicate_ids_are_rejected(self):
  from network_system import profile,validate_system
  record=profile('llm');record['views']['inference'].append('missing')
  with self.assertRaises(ValueError):validate_system(record)
 def test_research_candidate_extracts_architecture_tags_and_ai_contract(self):
  from research_watch import _norm,ai_prompt
  item=_norm({'id':'W1','title':'Paged Attention with FSDP MoE','publication_date':'2026-10-01','authorships':[],'abstract_inverted_index':{'kv':[0],'cache':[1],'fsdp':[2],'mixture':[3],'of':[4],'experts':[5]}},'nvidia','q')
  self.assertIn('kv_cache',item['architecture_tags']);self.assertIn('optimizer_state',item['architecture_tags']);self.assertEqual(ai_prompt(item)['status'] if 'status' in ai_prompt(item) else 'pending_host_ai_review','pending_host_ai_review')
 def test_frontier_capability_design_is_design_only_and_requires_all_gates(self):
  from frontier_capability_design import build_design,validate_design
  record=validate_design(build_design());self.assertEqual(len(record['capabilities']),6);self.assertTrue(all(c['status']=='design_only' for c in record['capabilities']));self.assertTrue(all(len(c['validation_gates'])>=2 for c in record['capabilities']))
 def test_innovation_pipeline_creates_evidence_gated_design_and_blocks_without_execution_inputs(self):
  from innovation_pipeline import run_pipeline
  from orchestrator import atomic_write
  from network_system import profile
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);atomic_write(r/'system.json',profile('llm'));result=run_pipeline(r/'system.json',r/'result.json');self.assertEqual(result['promotion'],'blocked');self.assertEqual(result['claims']['architecture_creation']['status'],'blocked');self.assertTrue((r/'result.json').is_file())
if __name__=='__main__':unittest.main()





