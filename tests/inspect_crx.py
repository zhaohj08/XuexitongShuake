# -*- coding: utf-8 -*-
"""看 crx 里到底是什么扩展（服务器上要不要带）。"""
import json
import os
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for name in ('chrome-extension.crx', 'speed.crx', 'zyb-227372.crx'):
    path = os.path.join(ROOT, 'task', 'tool', name)
    with open(path, 'rb') as f:
        data = f.read()
    pos = data.find(b'PK\x03\x04')
    print('===', name, 'size=%d' % len(data), 'zip_at=%d' % pos)
    if pos < 0:
        continue
    try:
        zf = zipfile.ZipFile(__import__('io').BytesIO(data[pos:]))
        names = zf.namelist()
        manifest = None
        for n in names:
            if n.endswith('manifest.json'):
                manifest = json.loads(zf.read(n).decode('utf-8-sig'))
                break
        if manifest:
            print('  name:', manifest.get('name'))
            print('  desc:', (manifest.get('description') or '')[:120])
            print('  version:', manifest.get('manifest_version'), manifest.get('version'))
            print('  permissions:', manifest.get('permissions'))
            print('  host_permissions:', manifest.get('host_permissions'))
            print('  content_scripts:', [c.get('matches') for c in manifest.get('content_scripts', [])])
            print('  web_accessible:', (manifest.get('web_accessible_resources') or [])[:2])
        print('  files:', len(names), names[:8])
    except Exception as e:
        print('  ERR', repr(e))
