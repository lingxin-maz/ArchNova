# -*- coding: utf-8 -*-
"""Build an installable .codex/skills archive with SKILL.md at its skill root."""
import argparse, hashlib, json, shutil, zipfile
from pathlib import Path

def build(source, output_dir, zip_path):
    source=Path(source).resolve(); output_dir=Path(output_dir).resolve(); zip_path=Path(zip_path).resolve()
    if not (source/'SKILL.md').is_file(): raise ValueError('Source must contain SKILL.md')
    if output_dir.exists(): shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    excluded={'__pycache__','.pytest_cache','.git'}
    files=[]
    for path in sorted(source.rglob('*')):
        if not path.is_file() or any(part in excluded for part in path.parts) or path.suffix=='.pyc': continue
        rel=path.relative_to(source); target=output_dir/rel; target.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(path,target); files.append(rel.as_posix())
    if zip_path.exists(): zip_path.unlink()
    manifest={}
    with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED) as z:
        for rel in files:
            body=(output_dir/rel).read_bytes(); name='arch-anatomy/'+rel
            info=zipfile.ZipInfo(name,date_time=(2026,1,1,0,0,0)); info.compress_type=zipfile.ZIP_DEFLATED; info.external_attr=0o644<<16; z.writestr(info,body); manifest[name]=hashlib.sha256(body).hexdigest()
    archive_hash=hashlib.sha256(zip_path.read_bytes()).hexdigest()
    result={'format':'codex-skill','install_root':'.codex/skills','skill_name':'arch-anatomy','files':manifest,'archive_sha256':archive_hash}
    (output_dir/'skill-manifest.json').write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    return result

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--source',default=str(Path(__file__).resolve().parents[1])); ap.add_argument('--output-dir',default=None); ap.add_argument('--zip',dest='zip_path',default=None); a=ap.parse_args(); source=Path(a.source).resolve(); root=source.parent/'dist'; out=Path(a.output_dir or root/'arch-anatomy'); zip_path=Path(a.zip_path or root/'arch-anatomy-codex-skill.zip'); print(json.dumps(build(source,out,zip_path),ensure_ascii=False,indent=2))
if __name__=='__main__': main()
