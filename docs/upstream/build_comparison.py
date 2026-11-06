# -*- coding: utf-8 -*-
"""生成「本地定制版 vs 上游源码」逐文件差异明细（只读，输出 markdown 片段）。

数据来源：diff_report.json + 两份上游源码 + 工作日志（更新日志.md / AGENT_HANDOVER.md）。
"""
import json
import os
import re

BASE = r'E:\xuexi\005\_upstream'
ROOT = r'E:\xuexi\005\Xuexitong_shuake-master (1)\Xuexitong_shuake-master'
UP = os.path.join(BASE, 'master_src', 'Xuexitong_shuake-master')
OUT = os.path.join(BASE, 'comparison_data.md')


def read(path):
    for enc in ('utf-8-sig', 'gbk'):
        try:
            with open(path, encoding=enc, errors='replace') as f:
                return f.read()
        except OSError:
            return ''
    return ''


def sections(text, pattern):
    out, title, buf = [], '(开头)', []
    for line in text.splitlines():
        if re.match(pattern, line):
            out.append((title, '\n'.join(buf)))
            title, buf = line.strip().strip('#').strip(), []
        else:
            buf.append(line)
    out.append((title, '\n'.join(buf)))
    return out


handover = read(os.path.join(ROOT, 'AGENT_HANDOVER.md'))
changelog = read(os.path.join(ROOT, '更新日志.md'))
hd_secs = sections(handover, r'^### 4\.\d+|^### 3\.\d+|^## \d+\. ')
cl_secs = sections(changelog, r'^## 26\.')

rep = json.load(open(os.path.join(BASE, 'diff_report.json'), encoding='utf-8'))


def short(title):
    m = re.match(r'(26\.\d+\.\d+\.\d+|\d+\.\d+)', title)
    return m.group(1) if m else title[:14]


def refs(rel):
    """这个文件在工作日志的哪些章节/版本被提到。"""
    base = os.path.basename(rel)
    keys = [rel.lower()]
    if len(base) >= 7:
        keys.append(base.lower())
    hits_h, hits_c = [], []
    for title, body in hd_secs:
        low = body.lower()
        if any(k in low for k in keys):
            hits_h.append(short(title))
    for title, body in cl_secs:
        low = body.lower()
        if any(k in low for k in keys):
            hits_c.append(short(title))
    return hits_h[:4], hits_c[:4]


def defs(text):
    found = re.findall(r'^\s*(?:async\s+)?def\s+(\w+)|^\s*class\s+(\w+)', text, re.M)
    return set(a or b for a, b in found)


lines = []
lines.append('# 逐文件差异明细（自动生成）\n')

# 统计
up_lines = lo_lines = 0
for rel in rep['same'] + list(rep['diff'].keys()) + rep['only_up']:
    t = read(os.path.join(UP, rel))
    if rel.endswith(('.py', '.txt', '.md')):
        up_lines += len(t.splitlines())
for rel in rep['same'] + list(rep['diff'].keys()) + rep['only_local']:
    t = read(os.path.join(ROOT, rel))
    if rel.endswith(('.py', '.txt', '.md')):
        lo_lines += len(t.splitlines())
lines.append('上游文本文件行数 ≈ %d；本地 ≈ %d（含本地独有文档/测试）\n'
             % (up_lines, lo_lines))

lines.append('\n## A. 同名但内容不同的 28 个文件\n')
lines.append('| 文件 | 上游→本地行数 | 相似度 | 本地新增函数/类（节选） | 依据（交接 / 版本） |')
lines.append('|---|---:|---:|---|---|')
for rel, d in sorted(rep['diff'].items(),
                     key=lambda x: -(x[1].get('up_only_lines', 0) + x[1].get('local_only_lines', 0))):
    a = read(os.path.join(UP, rel))
    b = read(os.path.join(ROOT, rel))
    added = sorted(defs(b) - defs(a))
    brief = ', '.join(added[:5]) + ('…' if len(added) > 5 else '') if added else '—'
    hh, cc = refs(rel)
    lines.append('| `%s` | %s→%s | %s | %s | %s / %s |'
                 % (rel, d.get('up_lines', d.get('up_size')),
                    d.get('local_lines', d.get('local_size')),
                    d['similarity'], brief,
                    ', '.join(hh) or '—', ', '.join(cc) or '—'))

lines.append('\n## B. 仅本地有的 15 个文件\n')
lines.append('| 文件 | 行数 | 顶层函数/类（节选） | 依据 |')
lines.append('|---|---:|---|---|')
for rel in rep['only_local']:
    t = read(os.path.join(ROOT, rel))
    ds = sorted(defs(t))
    hh, cc = refs(rel)
    lines.append('| `%s` | %d | %s | %s / %s |'
                 % (rel, len(t.splitlines()), ', '.join(ds[:6]) or '—',
                    ', '.join(hh) or '—', ', '.join(cc) or '—'))

lines.append('\n## C. 仅上游有的文件\n')
for rel in rep['only_up']:
    lines.append('- `%s`' % rel)

lines.append('\n## D. 字节级一致的 42 个文件（按目录分组）\n')
groups = {}
for rel in rep['same']:
    groups.setdefault(rel.split('/')[0] if '/' in rel else '(根目录)', []).append(rel)
for k in sorted(groups):
    lines.append('- **%s**（%d）：%s' % (k, len(groups[k]), ', '.join('`%s`' % x for x in groups[k])))

lines.append('\n## E. 更新日志版本节索引\n')
lines.append('| 版本 | 主题 |')
lines.append('|---|---|')
for title, body in cl_secs:
    if not title.startswith('26.'):
        continue
    heads = re.findall(r'^### (.+)$', body, re.M)
    lines.append('| %s | %s |' % (short(title), '；'.join(heads[:4]) or '—'))

with open(OUT, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines) + '\n')
print('WROTE', OUT)
print('UP_LINES=%d LOCAL_LINES=%d' % (up_lines, lo_lines))
print('DIFF=%d ONLY_LOCAL=%d ONLY_UP=%d SAME=%d'
      % (len(rep['diff']), len(rep['only_local']), len(rep['only_up']), len(rep['same'])))
