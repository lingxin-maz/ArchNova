# -*- coding: utf-8 -*-
import hashlib
import sys
import tempfile
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        (self.root/'original.txt').write_bytes(b'Original synthetic document')
        (self.root/'text.txt').write_bytes('abc 中文 quote xyz'.encode('utf-8'))
        self.snapshot={'id':'snap:one','source_id':'source:one','source_version':'v1',
            'original_path':'original.txt','original_sha256':hashlib.sha256((self.root/'original.txt').read_bytes()).hexdigest(),
            'text_path':'text.txt','text_sha256':hashlib.sha256((self.root/'text.txt').read_bytes()).hexdigest(),
            'extraction':{'tool':'identity-test','version':'1','retrieved_at':'2026-10-17T00:00:00Z'}}
    def verify(self,evidence):
        from evidence_snapshots import verify_evidence_item
        return verify_evidence_item(evidence,self.snapshot,self.root)
    def evidence(self):
        return {'snapshot_id':'snap:one','source_id':'source:one','quote':'中文 quote','span':{'start':4,'end':12},'content_hash':self.snapshot['text_sha256']}
    def test_exact_unicode_quote_and_hashes(self):
        self.assertTrue(self.verify(self.evidence()))
    def test_mutated_original_and_text_are_rejected(self):
        for name in ['original.txt','text.txt']:
            before=(self.root/name).read_bytes();(self.root/name).write_bytes(b'changed')
            with self.assertRaises(ValueError):self.verify(self.evidence())
            (self.root/name).write_bytes(before)
    def test_quote_span_is_exact(self):
        evidence=self.evidence();evidence['span']['end']=11
        with self.assertRaises(ValueError):self.verify(evidence)
    def test_wrong_source_is_rejected(self):
        evidence=self.evidence();evidence['source_id']='source:other'
        with self.assertRaises(ValueError):self.verify(evidence)
    def test_relative_path_cannot_escape_bundle(self):
        self.snapshot['original_path']='../outside.txt'
        with self.assertRaises(ValueError):self.verify(self.evidence())
    def test_content_hash_must_bind_to_extracted_text(self):
        evidence=self.evidence();evidence['content_hash']='a'*64
        with self.assertRaises(ValueError):self.verify(evidence)
if __name__=='__main__':unittest.main()
