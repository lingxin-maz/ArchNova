import hashlib,json,sys,tempfile,unittest,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build_codex_skill import build

class ArchNovaPackagingTests(unittest.TestCase):
 def test_install_archive_and_manifest_use_archnova(self):
  source=Path(__file__).resolve().parents[1]
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);target=root/'.codex'/'skills'/'archnova';archive=root/'archnova-codex-skill.zip'
   manifest=build(source,target,archive)
   self.assertEqual(manifest['skill_name'],'archnova')
   self.assertEqual(manifest['install_root'],'.codex/skills')
   self.assertIn('name: archnova',(target/'SKILL.md').read_text(encoding='utf8'))
   with zipfile.ZipFile(str(archive)) as package:
    self.assertIsNone(package.testzip())
    self.assertEqual(set(package.namelist()),set(manifest['files']))
    self.assertTrue(all(name.startswith('archnova/') for name in package.namelist()))
    for name,expected in manifest['files'].items():self.assertEqual(hashlib.sha256(package.read(name)).hexdigest(),expected)
   self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(),manifest['archive_sha256'])

if __name__=='__main__':unittest.main()
