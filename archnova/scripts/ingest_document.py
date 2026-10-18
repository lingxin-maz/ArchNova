# -*- coding: utf-8 -*-
"""Copy a source document into a portable anatomy bundle and create an evidence receipt."""
import argparse, shutil
from pathlib import Path
from evidence_snapshots import snapshot_receipt

def ingest(original, bundle, source_id, snapshot_id, source_version, tool='PyPDF2', tool_version='2.12.1', text=None, retrieved_at=None):
    bundle=Path(bundle).resolve(); docs=bundle/'documents'; docs.mkdir(parents=True,exist_ok=True)
    original=Path(original).resolve()
    if not original.is_file(): raise ValueError('Original document does not exist: '+str(original))
    target=docs/original.name; shutil.copyfile(original,target)
    if text is None:
        if original.suffix.lower()=='.pdf':
            try:
                from PyPDF2 import PdfReader
                text='\\n'.join((page.extract_text() or '') for page in PdfReader(str(original)).pages)
            except ImportError: raise ValueError('PDF extraction needs PyPDF2 or pass --text-file')
        else: text=original.read_text(encoding='utf-8')
    text_path=docs/(original.stem+'.extracted.txt'); text_path.write_text(text,encoding='utf-8')
    if retrieved_at is None: raise ValueError('retrieved_at is required for reproducible receipts')
    return snapshot_receipt(target,text_path,bundle,source_id,snapshot_id,source_version,tool,tool_version,retrieved_at)

def main():
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--original',required=True); ap.add_argument('--bundle',required=True); ap.add_argument('--source-id',required=True); ap.add_argument('--snapshot-id',required=True); ap.add_argument('--source-version',required=True); ap.add_argument('--retrieved-at',required=True); ap.add_argument('--text-file'); ap.add_argument('--output',required=True); a=ap.parse_args()
    try:
        text=Path(a.text_file).read_text(encoding='utf-8') if a.text_file else None
        receipt=ingest(a.original,a.bundle,a.source_id,a.snapshot_id,a.source_version,text=text,retrieved_at=a.retrieved_at)
    except (ValueError,OSError) as exc: ap.error(str(exc))
    Path(a.output).write_text(__import__('json').dumps(receipt,ensure_ascii=False,indent=2)+'\\n',encoding='utf-8'); print(a.output)
if __name__=='__main__': main()
