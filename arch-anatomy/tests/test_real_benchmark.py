import copy,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from architecture_benchmark import validate_cases,validate_prediction,score,match_units
from orchestrator import digest

class RealBenchmarkTests(unittest.TestCase):
 def data(self):
  case={'id':'c','mode':'code-only','materials':[{'source_id':'s','lines':[{'line':i,'text':'x'} for i in range(1,21)]}],'edits':[{'id':'e1'},{'id':'e2'}]};case['input_hash']=digest(case)
  units=[{'id':'a','kind':'linear','anchors':[{'source_id':'s','start_line':1,'end_line':1}]},{'id':'b','kind':'linear','anchors':[{'source_id':'s','start_line':2,'end_line':2}]}]
  ref={'human_review_status':'pending','cases_hash':digest([case]),'cases':{'c':{'units':units,'reviews':{'e1':{'verdict':'reject','rationale':'negative fixture','evidence':[{'source_id':'s','start_line':1,'end_line':1}]},'e2':{'verdict':'admit','rationale':'positive fixture','evidence':[{'source_id':'s','start_line':1,'end_line':1}]}},'human_review_status':'pending','scope':'two invocations'}}}
  op={'id':'p','kind':'linear','name':'one coarse op','rationale':'coarse','evidence':[{'source_id':'s','start_line':1,'end_line':2}]}
  p={'case_id':'c','input_hash':case['input_hash'],'operators':[op],'reviews':[{'id':eid,'verdict':'admit','rationale':'reason','evidence':[{'source_id':'s','start_line':1,'end_line':1}]} for eid in ('e1','e2')],'scope_limits':['fixture only']}
  return case,ref,p
 def test_no_coarse_prediction_double_credit(self):
  c,r,p=self.data();out=score([c],r,[p]);self.assertEqual(out['all_cases']['miss_rate'],.5);self.assertEqual(out['all_cases']['unsafe_admit_rate'],1.0);self.assertFalse(out['reference_is_human_approved'])
 def test_all_reject_does_not_pass_positive_control(self):
  c,r,p=self.data()
  for e in p['reviews']:e['verdict']='reject'
  out=score([c],r,[p]);self.assertEqual(out['all_cases']['unsafe_admit_rate'],0);self.assertEqual(out['all_cases']['safe_admit_recall'],0)
 def test_no_stale_predictions_or_oversized_evidence(self):
  c,r,p=self.data();p['input_hash']='x'
  with self.assertRaises(ValueError):score([c],r,[p])
  c,r,p=self.data();p['operators'][0]['evidence'][0]['end_line']=20
  with self.assertRaises(ValueError):score([c],r,[p])
 def test_incomplete_or_duplicate_runs_and_reference_binding_rejected(self):
  c,r,p=self.data()
  for predictions in ([],[p,p]):
   with self.assertRaises(ValueError):score([c],r,predictions)
  r['cases_hash']='x'
  with self.assertRaises(ValueError):score([c],r,[p])
 def test_out_of_scope_citations_and_unknown_verdict_fail(self):
  c,r,p=self.data();p['reviews'][0]['evidence'][0]['start_line']=21;p['reviews'][0]['evidence'][0]['end_line']=21
  with self.assertRaises(ValueError):validate_prediction(p,c)
  c,r,p=self.data();p['reviews'][0]['verdict']='pass'
  with self.assertRaises(ValueError):validate_prediction(p,c)
 def test_new_gate_rejects_not_applicable_core_checks(self):
  from task_contracts import example_artifact,validate_artifact
  d=example_artifact('replacement_review');d.update(verdict='admit',relation='exact_equivalence',unresolved=[])
  d['evidence'][0]['kind']='derived';d['proof_evidence_ids']=['ev:proposal']
  for c in d['checks']:c.update(status='not_applicable',evidence_ids=['ev:proposal'])
  with self.assertRaises(ValueError):validate_artifact(d)


 def test_blank_human_sheet_is_never_auto_approved(self):
  from architecture_benchmark import export_annotation_sheet,apply_human_sheet
  c,r,p=self.data()
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'review.csv';export_annotation_sheet([c],r,path)
   with self.assertRaises(ValueError):apply_human_sheet([c],r,path)
 def test_bad_reference_evidence_is_rejected_too(self):
  c,r,p=self.data();r['cases']['c']['units'][0]['anchors'][0]['end_line']=19
  with self.assertRaises(ValueError):score([c],r,[p])
 def test_every_critical_admission_check_is_required(self):
  from task_contracts import example_artifact,validate_artifact
  for missing in ('interface','function_class'):
   d=example_artifact('replacement_review');d.update(verdict='admit',relation='interface_only',unresolved=[])
   d['evidence'][0]['kind']='code_observed'
   for c in d['checks']:c.update(status='satisfied',evidence_ids=['ev:proposal'])
   next(c for c in d['checks'] if c['dimension']==missing)['status']='not_applicable'
   with self.assertRaises(ValueError):validate_artifact(d)
 def test_unsupported_non_applicability_cannot_admit(self):
  from task_contracts import example_artifact,validate_artifact
  d=example_artifact('replacement_review');d.update(verdict='admit',relation='interface_only',unresolved=[]);d['evidence'][0]['kind']='code_observed'
  for c in d['checks']:c.update(status='satisfied',evidence_ids=['ev:proposal'])
  d['checks'][2].update(status='not_applicable',evidence_ids=[])
  with self.assertRaises(ValueError):validate_artifact(d)

if __name__=='__main__':unittest.main()
