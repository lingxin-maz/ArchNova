import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from component_library import build_index, load_index, validate_component
from component_retrieval import retrieve

LIB=Path(__file__).resolve().parents[1]/'component-library'
class ComponentLibraryTests(unittest.TestCase):
    def test_reference_seeds_are_explicitly_unverified(self):
        index=build_index(LIB)
        self.assertGreaterEqual(len(index['components']),4)
        for e in index['components']:
            self.assertEqual(e['component']['verification_status'],'unverified')
            self.assertEqual(e['component']['provenance'][0]['kind'],'proposed')

    def test_schema_rejects_untraceable_or_incomplete_records(self):
        original=build_index(LIB)['components'][0]['component']
        for key in ('provenance','interface','equation','complexity'):
            c=copy.deepcopy(original);del c[key]
            with self.assertRaises(ValueError):validate_component(c)
        c=copy.deepcopy(original);c['verification_status']='verified'
        with self.assertRaises(ValueError):validate_component(c)
        c=copy.deepcopy(original);c['provenance'][0]['kind']='invented_fact'
        with self.assertRaises(ValueError):validate_component(c)

    def test_index_digests_duplicates_and_changed_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); c=build_index(LIB)['components'][0]['component']
            path=root/'a'/'component.json';path.parent.mkdir();path.write_text(json.dumps(c),encoding='utf8')
            out=root/'component-index.json';a=build_index(root,out)
            self.assertEqual(load_index(out),a)
            changed=copy.deepcopy(a);changed['components'][0]['component']['name']='changed'
            out.write_text(json.dumps(changed),encoding='utf8')
            with self.assertRaises(ValueError):load_index(out)
            c['equation']='a new equation';path.write_text(json.dumps(c),encoding='utf8')
            self.assertNotEqual(build_index(root)['index_hash'],a['index_hash'])
            other=root/'b'/'component.json';other.parent.mkdir();other.write_text(json.dumps(c),encoding='utf8')
            with self.assertRaises(ValueError):build_index(root)

    def test_constraints_exclude_stateful_and_incompatible_parts(self):
        index=build_index(LIB)
        result=retrieve(index,'',{'input_shape':['B','N','D'],'state':'none'})
        self.assertTrue(result['candidates'])
        self.assertTrue(any(r['component_id']=='operator:state_space_update' for r in result['rejected']))
        self.assertTrue(all(c['equivalence']=='unverified' for c in result['candidates']))
        self.assertEqual(retrieve(index,'',{'input_shape':['N','D']})['candidates'],[])
        self.assertEqual(retrieve(index,'',{'invariants':['unproven_invariant']})['candidates'],[])
        with self.assertRaises(ValueError):retrieve(index,'',{'unknown':True})
        with self.assertRaises(ValueError):retrieve(index,'',{'invariants':'x'})
        with self.assertRaises(ValueError):retrieve(index,'',limit=0)
        with self.assertRaises(ValueError):retrieve(index,'',required=['state'])

    def test_lexical_rank_is_deterministic_and_not_equivalence(self):
        index=build_index(LIB)
        result=retrieve(index,'attention global')
        self.assertEqual(result['candidates'][0]['component_id'],'operator:softmax_attention')
        self.assertEqual(result,retrieve(index,'attention global'))
        self.assertEqual(retrieve(index,'unmatched_keyword')['candidates'],[])
        self.assertEqual(retrieve(index,'注意力')['candidates'][0]['compatibility'],'unchecked')

if __name__=='__main__':unittest.main()
