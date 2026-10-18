import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
ROOT=Path(__file__).resolve().parents[1]

class ContractUpgradeTests(unittest.TestCase):
    def fixture(self,kind='decomposition'):
        from task_contracts import example_artifact
        return example_artifact(kind,'a'*64)

    def test_graph_contract_accepts_explicit_unknowns_in_drafts(self):
        from task_contracts import validate_artifact
        for kind in ('decomposition','design','replacement_review'):
            validate_artifact(self.fixture(kind))

    def test_bad_wiring_and_cycles_fail(self):
        from task_contracts import validate_artifact
        d=self.fixture();d['dataflow']['ports'][1]['axes']=['wrong']
        with self.assertRaises(ValueError):validate_artifact(d)
        d=self.fixture();d['dataflow']['ports'][0]['external']=False
        with self.assertRaises(ValueError):validate_artifact(d)
        d=self.fixture();d['dataflow']['node_parts'].append('ghost')
        with self.assertRaises(ValueError):validate_artifact(d)

    def test_hash_and_field_provenance_are_enforced(self):
        from task_contracts import validate_artifact
        d=self.fixture()
        with self.assertRaises(ValueError):validate_artifact(d,expected_hash='b'*64)
        d['operators'][0]['evidence_ids']=['absent']
        with self.assertRaises(ValueError):validate_artifact(d)

    def test_design_requires_baseline_metric_and_falsifiable_trial(self):
        from task_contracts import validate_artifact
        d=self.fixture('design');del d['experiment']['kill_criterion']
        with self.assertRaises(ValueError):validate_artifact(d)
        d=self.fixture('design');d['alternatives'][1]['decision']='select'
        with self.assertRaises(ValueError):validate_artifact(d)
        d=self.fixture('design');d['affected_parts']=['absent']
        with self.assertRaises(ValueError):validate_artifact(d)

    def test_review_cannot_pass_with_unknown_or_missing_checks(self):
        from task_contracts import validate_artifact
        d=self.fixture('replacement_review');d['verdict']='admit'
        with self.assertRaises(ValueError):validate_artifact(d)
        d=self.fixture('replacement_review');d['checks']=d['checks'][:-1]
        with self.assertRaises(ValueError):validate_artifact(d)

    def test_claimed_equivalence_requires_derivation_and_domain(self):
        from task_contracts import validate_artifact
        d=self.fixture('replacement_review');d['relation']='exact_equivalence'
        with self.assertRaises(ValueError):validate_artifact(d)

    def test_component_ports_versions_and_parameter_refs(self):
        from component_library import build_index,validate_component
        c=build_index(ROOT/'component-library')['components'][0]['component']
        self.assertEqual(c['schema_version'],'1.1')
        x=copy.deepcopy(c);x['ports'][0]['axes']=[]
        with self.assertRaises(ValueError):validate_component(x)
        x=copy.deepcopy(c);x['field_evidence']['/equation']=['absent']
        with self.assertRaises(ValueError):validate_component(x)
        x=copy.deepcopy(c);x['schema_version']='999'
        with self.assertRaises(ValueError):validate_component(x)

    def test_index_detects_changed_source_and_dangling_replacements(self):
        from component_library import build_index,load_index
        c=build_index(ROOT/'component-library')['components'][0]['component']
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp);p=r/'part'/'component.json';p.parent.mkdir();p.write_text(json.dumps(c),encoding='utf8')
            out=r/'component-index.json';build_index(r,out)
            load_index(out)
            c['equation']='changed';p.write_text(json.dumps(c),encoding='utf8')
            with self.assertRaises(ValueError):load_index(out)
            c['replacement_candidates']=['operator:absent'];p.write_text(json.dumps(c),encoding='utf8')
            with self.assertRaises(ValueError):build_index(r)


    def test_numeric_cost_and_decision_units_cannot_be_faked(self):
        from task_contracts import validate_artifact
        d=self.fixture('design');d['cost_predictions'][0]['unit']='byte'
        with self.assertRaises(ValueError):validate_artifact(d)
        d=self.fixture('design');d['cost_predictions'][0]['expression']='__import__("os")'
        with self.assertRaises(ValueError):validate_artifact(d)
        d=self.fixture('design');d['experiment']['decision_rule']['threshold']['unit']='second'
        with self.assertRaises(ValueError):validate_artifact(d)
        d=self.fixture('design');d['experiment']['status']='executed'
        with self.assertRaises(ValueError):validate_artifact(d)

    def test_migration_does_not_invent_missing_contracts(self):
        from component_library import build_index,migrate_component,validate_component
        c=build_index(ROOT/'component-library')['components'][0]['component']
        for key in ('schema_version','ports','state_contract','parameter_specs','field_evidence','verification'):del c[key]
        for e in c['provenance']:del e['id']
        draft=migrate_component(c)
        self.assertEqual(draft['state_contract']['kind'],'unknown')
        self.assertEqual(draft['ports'],[])
        with self.assertRaises(ValueError):validate_component(draft)

    def test_multiport_retrieval_and_state_constraints(self):
        from component_library import build_index
        from component_retrieval import retrieve
        index=build_index(ROOT/'component-library')
        q={'ports':[{'id':'Q','direction':'input','shape':['B','N','D'],'dtype':'float32'}],'state_kind':'stateless'}
        found=retrieve(index,required=q)
        self.assertEqual([c['component_id'] for c in found['candidates']],['operator:softmax_attention'])
        q['ports'][0]['dtype']='float64'
        self.assertFalse(retrieve(index,required=q)['candidates'])

    def test_completion_rejects_missing_artifacts_hashes_and_wrong_kind(self):
        from orchestrator import validate_completion,atomic_write,verify_saved_artifacts
        task={'task_id':'t','input_hash':'a'*64,'artifact_contract':{'kind':'design'}}
        with self.assertRaises(ValueError):validate_completion(task,{'status':'completed'})
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'result.json';atomic_write(p,self.fixture('decomposition'))
            response={'status':'completed','input_hash':'a'*64,'artifact_path':str(p)}
            with self.assertRaises(ValueError):validate_completion(task,response)
            atomic_write(p,self.fixture('design'))
            saved=validate_completion(task,response)
            saved_task=dict(task,status='completed',**saved)
            verify_saved_artifacts([saved_task])
            p.write_text('{}',encoding='utf8')
            with self.assertRaises(ValueError):verify_saved_artifacts([saved_task])

    def test_review_binds_upstream_design_and_exact_graph(self):
        from orchestrator import validate_completion,atomic_write
        from orchestrator import digest
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);design=root/'design.json';atomic_write(design,self.fixture('design'))
            import hashlib
            h=hashlib.sha256(design.read_bytes()).hexdigest()
            dep={'task_id':'design','artifact_contract':{'kind':'design'},'artifact_path':str(design),'artifact_sha256':h}
            task={'task_id':'review','input_hash':'a'*64,'artifact_contract':{'kind':'replacement_review'}}
            review=root/'review.json';data=self.fixture('replacement_review');atomic_write(review,data)
            response={'input_hash':'a'*64,'status':'completed','artifact_path':str(review)}
            with self.assertRaises(ValueError):validate_completion(task,response,dependencies=[dep])
            data['upstream_artifacts']=[{'task_id':'design','sha256':h}];atomic_write(review,data)
            validate_completion(task,response,dependencies=[dep])
            data['dataflow']['ports'][0]['dtype']='float64';atomic_write(review,data)
            with self.assertRaises(ValueError):validate_completion(task,response,dependencies=[dep])

    def test_out_of_order_and_unknown_status_submissions_fail(self):
        import contextlib,io
        from orchestrator import atomic_write,init_state,main
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp);plan=r/'plan.json';atomic_write(plan,{})
            tasks=[{'task_id':'a','depends_on':[]},{'task_id':'b','depends_on':['a']}]
            state=r/'state.json';atomic_write(state,init_state(plan,tasks));response=r/'response.json'
            for item in ({'task_id':'b','status':'completed'},{'task_id':'a','status':'invented'}):
                atomic_write(response,[item])
                with self.assertRaises(ValueError),contextlib.redirect_stdout(io.StringIO()):
                    main(['submit',str(state),'--response',str(response),'-o',str(state)])
            self.assertTrue(all(t.get('status','pending')=='pending' for t in json.loads(state.read_text(encoding='utf8'))['tasks']))

    def test_schema_drafts_and_reused_graph_definitions_match(self):
        from jsonschema import Draft4Validator
        anatomy=json.loads((ROOT/'assets/anatomy.schema.json').read_text(encoding='utf8'))
        contract=json.loads((ROOT/'assets/architecture-task.schema.json').read_text(encoding='utf8'))
        for p in (ROOT/'assets').glob('*schema*.json'):Draft4Validator.check_schema(json.loads(p.read_text(encoding='utf8')))
        for name in ('dataflow','port','edge'):
            self.assertEqual(contract['definitions'][name],anatomy['definitions'][name])


    def test_real_data_cycle_and_shared_parameter_owners_fail(self):
        from task_contracts import validate_artifact
        d=self.fixture('design')
        second=copy.deepcopy(d['operators'][0]);second['id']='op:second';d['operators'].append(second)
        d['dataflow']['node_parts'].append('op:second')
        ports=d['dataflow']['ports']
        for p in copy.deepcopy(ports):
            p['id']='other:'+p['id'];p['owner']='op:second';ports.append(p)
        for p in ports:p['external']=False
        d['dataflow']['edges']=[{'id':'ab','source':'y','target':'other:x','kind':'data','delay':0},{'id':'ba','source':'other:y','target':'x','kind':'data','delay':0}]
        with self.assertRaisesRegex(ValueError,'cycle'):validate_artifact(d)
        for p in ports:p['external']=True
        d['dataflow']['edges']=[]
        d['dataflow']['shared_parameters']=[{'id':'shared:w','parts':['op:identity','op:second'],'description':'Tied weights'}]
        d['changes_shared_parameters']=['shared:w']
        with self.assertRaisesRegex(ValueError,'all owners'):validate_artifact(d)
        d['affected_parts'].append('op:second');validate_artifact(d)

    def test_executed_scheduler_also_enforces_task_artifacts(self):
        from orchestrator import execute_schedule
        task={'task_id':'design','role':'new_architecture_designer','input_hash':'a'*64,'artifact_contract':{'kind':'design'},'depends_on':[]}
        result=execute_schedule([task],lambda task,attempt:{'task_id':'design','input_hash':'a'*64,'status':'completed'})
        self.assertEqual(result['status'],'failed')
        self.assertIn('artifact_path',result['errors']['design']['error'])

    def test_host_envelope_and_partial_port_types_are_strict(self):
        from component_library import build_index
        from component_retrieval import retrieve
        index=build_index(ROOT/'component-library')
        for ports in ([{'id':['bad']}],[{'id':'Q','shape':'wrong'}],[{'id':'Q','direction':'sideways'}]):
            with self.assertRaises(ValueError):retrieve(index,required={'ports':ports})
        from orchestrator import validate_completion
        schema=json.loads((ROOT/'assets/host-response.schema.json').read_text(encoding='utf8'))
        with self.assertRaises(ValueError):validate_completion({'task_id':'a','input_hash':'a'*64,'response_schema':schema},{'task_id':'a','status':'completed','input_hash':'a'*64,'invented':True})

if __name__=='__main__':unittest.main()
