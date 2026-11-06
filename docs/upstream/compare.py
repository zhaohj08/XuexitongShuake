# -*- coding: utf-8 -*-
"""只读对比：上游 master 源码 vs 本地定制工程，输出 diff_report.json。

排除：构建产物、缓存、本地文档之外的运行数据（源码模式下 task/ 兼作数据目录）、
以及含明文账号密码的配置文件。
"""
import difflib
import json
import os

UP = r'E:\xuexi\005\_upstream\master_src\Xuexitong_shuake-master'
LOCAL = r'E:\xuexi\005\Xuexitong_shuake-master (1)\Xuexitong_shuake-master'
OUT = r'E:\xuexi\005\_upstream\diff_report.json'

SKIP_DIRS = {'.git', '__pycache__', '.idea', '.workbuddy-ai', 'build', 'dist', '.pytest_cache'}
SKIP_PREFIX = (
    'task/run/', 'task/record/', 'task/data/', 'task/logs/',
    'run/', 'record/', 'data/', 'logs/',
)
SKIP_FILES = {
    'accounts.json', 'account_info.json', 'cookies.pkl',
    '输出记录.log', 'error.log', 'selftest.log', 'sign.log',
    'signed.json',
}
SKIP_EXTS = {'.pyc', '.pyo', '.pkl', '.exe', '.zip', '.dll', '.so'}


def walk(root):
    out = {}
    for base, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in names:
            path = os.path.join(base, name)
            rel = os.path.relpath(path, root).replace('\\', '/')
            if any(rel.startswith(p) for p in SKIP_PREFIX):
                continue
            if name in SKIP_FILES or os.path.splitext(name)[1].lower() in SKIP_EXTS:
                continue
            try:
                with open(path, 'rb') as f:
                    out[rel] = f.read()
            except OSError:
                pass
    return out


def as_lines(data):
    try:
        return data.decode('utf-8-sig').splitlines()
    except UnicodeDecodeError:
        return None


def main():
    up, local = walk(UP), walk(LOCAL)
    common = sorted(set(up) & set(local))
    only_up = sorted(set(up) - set(local))
    only_local = sorted(set(local) - set(up))
    same = [r for r in common if up[r] == local[r]]
    diff = [r for r in common if up[r] != local[r]]

    details = {}
    for rel in diff:
        a, b = as_lines(up[rel]), as_lines(local[rel])
        if a is None or b is None:
            details[rel] = {'kind': 'binary', 'up_size': len(up[rel]),
                            'local_size': len(local[rel]), 'similarity': 0.0}
        else:
            sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
            delta = list(difflib.unified_diff(a, b, n=0))
            details[rel] = {
                'kind': 'text',
                'up_lines': len(a), 'local_lines': len(b),
                'similarity': round(sm.ratio(), 3),
                'up_only_lines': sum(1 for x in delta if x.startswith('-') and not x.startswith('---')),
                'local_only_lines': sum(1 for x in delta if x.startswith('+') and not x.startswith('+++')),
            }

    report = {
        'up_root': UP, 'local_root': LOCAL,
        'up_count': len(up), 'local_count': len(local),
        'same': same, 'diff': details,
        'only_up': only_up, 'only_local': only_local,
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print('UP=%d LOCAL=%d SAME=%d DIFF=%d ONLY_UP=%d ONLY_LOCAL=%d'
          % (len(up), len(local), len(same), len(diff), len(only_up), len(only_local)))
    print('\n--- 两边都有但内容不同（按差异行数排序）---')
    for rel, d in sorted(details.items(),
                         key=lambda x: -(x[1].get('up_only_lines', 0) + x[1].get('local_only_lines', 0))):
        print('%-56s sim=%-6s up=%-6s local=%-6s -%d/+%d'
              % (rel, d['similarity'], d.get('up_lines', d.get('up_size')),
                 d.get('local_lines', d.get('local_size')),
                 d.get('up_only_lines', 0), d.get('local_only_lines', 0)))
    print('\n--- 仅上游有 ---')
    for rel in only_up:
        print('  ', rel)
    print('\n--- 仅本地有（节选前 60）---')
    for rel in only_local[:60]:
        print('  ', rel)
    print('  ... 共 %d 个' % len(only_local))
    print('\nREPORT=%s' % OUT)


if __name__ == '__main__':
    main()
