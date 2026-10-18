# -*- coding: utf-8 -*-
"""Build a deterministic skill archive and SHA-256 manifest."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def build(root, target):
    root, target = Path(root), Path(target)
    manifest = {}
    with zipfile.ZipFile(str(target), 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob('*')):
            if not path.is_file() or '__pycache__' in path.parts or path.suffix == '.pyc':
                continue
            rel = root.name + '/' + path.relative_to(root).as_posix()
            body = path.read_bytes()
            info = zipfile.ZipInfo(rel, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, body)
            manifest[rel] = hashlib.sha256(body).hexdigest()
    result = {'archive_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
              'files': manifest}
    target.with_suffix(target.suffix + '.manifest.json').write_text(
        json.dumps(result, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', default=None)
    a = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    result = build(root, a.output or root.with_suffix('.skill'))
    print(json.dumps({'files': len(result['files']), 'archive_sha256': result['archive_sha256']}))


if __name__ == '__main__':
    main()
