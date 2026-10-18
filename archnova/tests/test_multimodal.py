import sys, tempfile, unittest, hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))

class MultimodalIngestTests(unittest.TestCase):
    def test_image_material_has_hash_and_visual_task(self):
        from multimodal_ingest import ingest_image, make_vision_task
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'figure.png'; p.write_bytes(b'fake-image')
            item=ingest_image(p,Path(tmp),'source:paper',page=3,region={'x':1,'y':2,'width':10,'height':20})
            self.assertEqual(item['kind'],'image'); self.assertEqual(item['page'],3); self.assertEqual(len(item['sha256']),64)
            task=make_vision_task(item,'Extract block graph and interface arrows')
            self.assertEqual(task['executor'],'host'); self.assertEqual(task['role'],'visual_architecture_reviewer')
            self.assertEqual(task['content'][1]['type'],'image'); self.assertEqual(task['input_hash'],hashlib.sha256(__import__('json').dumps(task['content'],sort_keys=True,separators=(',',':')).encode()).hexdigest())
    def test_pdf_backend_unavailable_is_structured(self):
        from multimodal_ingest import render_pdf_pages
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'x.pdf'; p.write_bytes(b'not-pdf')
            result=render_pdf_pages(p,Path(tmp)/'out')
            self.assertIn(result['status'],('unavailable','failed'))
            self.assertIn('backend',result)
    def test_manifest_rejects_path_escape(self):
        from multimodal_ingest import ingest_image
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'x.png'; p.write_bytes(b'x')
            with self.assertRaises(ValueError): ingest_image(p,Path(tmp)/'nested','s',region={'x':-1,'y':0,'width':1,'height':1})
if __name__=='__main__': unittest.main()

import sys,tempfile,unittest,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
class ProjectMaterialTests(unittest.TestCase):
 def test_index_project_covers_code_config_docs_and_images(self):
  from multimodal_ingest import index_project, make_project_tasks
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)/'proj'; root.mkdir(); (root/'src').mkdir(); (root/'src'/'main.py').write_text('print(1)',encoding='utf8'); (root/'analysis.ipynb').write_text('{}',encoding='utf8'); (root/'Dockerfile').write_text('FROM python',encoding='utf8'); (root/'README.md').write_text('# demo',encoding='utf8'); (root/'config.yaml').write_text('x: 1',encoding='utf8'); (root/'data.csv').write_text('a,b\n1,2',encoding='utf8'); (root/'fig.png').write_bytes(b'PNG')
   result=index_project(root,Path(tmp)/'bundle','source:repo')
   kinds={x['kind'] for x in result['materials']}; self.assertTrue({'source_code','notebook','documentation','configuration','table','image'}<=kinds); self.assertEqual(result['status'],'completed')
   tasks=make_project_tasks(result['materials']); self.assertTrue(any(t['role']=='code_architecture_reviewer' for t in tasks)); self.assertTrue(any(t['role']=='visual_architecture_reviewer' for t in tasks))
 def test_project_index_skips_secrets_and_binaries(self):
  from multimodal_ingest import index_project
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)/'p';root.mkdir(); (root/'.env').write_text('TOKEN=secret',encoding='utf8'); (root/'x.exe').write_bytes(b'\0'*20); (root/'ok.py').write_text('x=1',encoding='utf8')
   result=index_project(root,Path(tmp)/'b','s'); paths={x['source_path'] for x in result['materials']}; self.assertNotIn('.env',paths); self.assertNotIn('x.exe',paths); self.assertIn('ok.py',paths)

 def test_index_excludes_bundle_inside_project(self):
  from multimodal_ingest import index_project
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)/'p';root.mkdir(); bundle=root/'bundle'; bundle.mkdir(); (root/'ok.py').write_text('x=1',encoding='utf8'); (bundle/'old.py').write_text('old',encoding='utf8')
   result=index_project(root,bundle,'s'); self.assertEqual([x['source_path'] for x in result['materials']],['ok.py'])

 def test_budget_is_explicit(self):
  from multimodal_ingest import index_project
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)/'p';root.mkdir(); (root/'a.py').write_text('a',encoding='utf8'); r=index_project(root,Path(tmp)/'b','s',max_files=0); self.assertEqual(r['status'],'blocked'); self.assertIn('budget',r['errors'][0])
if __name__=='__main__':unittest.main()
