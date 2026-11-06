# -*- coding: utf-8 -*-
"""单日「完整日志」导出：把一天里所有日志、诊断截图、学习记录与配置
收进**一个** zip 文件，并在包内额外生成一份把所有文本合并到一起的汇总 txt。

为什么要单独做这个模块（而不是直接调工程根目录的 export_logs.ps1）：
- GUI 里点一下就要出结果，不能依赖 PowerShell / 执行策略 / 外部脚本；
- 需求是「导出单日即可」，ps1 是全量打包，这里按天过滤；
- 纯标准库 + core.paths，纯桩测试可用临时目录跑，不需要浏览器 / 界面 / 联网。

规则
- 带行首时间戳的日志：逐行按日期过滤，无时间戳的续行（异常堆栈、子进程输出、
  分隔线）跟着上一行保留，不会被拦腰截断；
- 没有行首时间戳的文件：按文件修改时间判断是否属于当天；
- 学习记录 / 配置属于「当前快照」，不受单日过滤，全量纳入（README 里写明）；
- 所有文本统一脱敏：密码 / API Key / Cookie / token 字段抹掉，手机号只留后 4 位；
- 包内文件名一律 ASCII（沿用 export_logs.ps1 约定），避免换机器解压乱码；
- 单个文件出错只记 warning，不影响整包生成。
"""
from __future__ import annotations

import os
import platform
import re
import time
import zipfile
from datetime import date, datetime, timedelta

from core import paths

ZIP_PREFIX = '课程学习助手_完整日志_'
README_NAME = '00_README.txt'

# 行首时间戳：2026-11-05 18:27:43 / [2026-11-05 18:27:43] / 启动 2026-11-05 ...
_TS_LINE_RE = re.compile(r'^\s*(?:\[|\(|启动\s+)?(20\d{2})[-/](\d{1,2})[-/](\d{1,2})')
_DAY_RE = re.compile(r'(?<!\d)(20\d{2})[-/](\d{1,2})[-/](\d{1,2})(?!\d)')
_COMPACT_DAY_RE = re.compile(r'(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)')

# 脱敏：JSON 里的敏感字段、明文手机号、sk- 开头的 API Key
_SECRET_FIELD_RE = re.compile(
    r'"(?P<k>password|passwd|pwd|api[_-]?key|apikey|api|token|secret|cookie|cookies|authorization)"'
    r'\s*:\s*"(?:[^"\\]|\\.)*"', re.I)
_PHONE_FIELD_RE = re.compile(
    r'"(?P<k>phone|phone_number|mobile|tel)"\s*:\s*"(?P<v>[^"]{6,})"', re.I)
_PHONE_RE = re.compile(r'(?<!\d)1[3-9]\d{9}(?!\d)')
_API_KEY_RE = re.compile(r'(?<![\w-])(sk-[A-Za-z0-9_\-]{12,})')

_SHOT_TAG_MAP = {
    '未识别页面': 'unknown_page',
    '页面卡住': 'stuck_page',
    '视频出错': 'video_error',
    '测验出错': 'quiz_error',
    '找不到元素': 'no_element',
    '浏览器会话异常': 'browser_session_error',
    '程序异常': 'program_error',
}

# 包内文本文件条目：(包名, 绝对路径, 说明, 是否快照)
_TEXT_PLAN = [
    ('logs/main.log', ('logs', '程序日志.log'), 'logs/程序日志.log', False),
    ('logs/main.log.1', ('logs', '程序日志.log.1'), 'logs/程序日志.log.1（轮转备份）', False),
    ('logs/error.log', ('error.log',), 'error.log（异常堆栈）', False),
    ('logs/gui.log', ('输出记录.log',), '输出记录.log（logging 记录）', False),
    ('logs/selftest.log', ('selftest.log',), 'selftest.log（自检结果）', False),
    ('logs/sign.log', ('data', 'sign.log'), 'data/sign.log（签到）', False),
]


# ---------------------------------------------------------------- 基础工具

def parse_day(value=None) -> date:
    """接受 None / date / datetime / 'YYYY-MM-DD'（也容忍 'YYYY/MM/DD'）。"""
    if value is None or value == '':
        return date.today()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    m = _DAY_RE.search(str(value).strip())
    if not m:
        raise ValueError('日期格式应为 YYYY-MM-DD：%r' % (value,))
    return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))


def recent_days(n: int = 7, today=None) -> list:
    """最近 n 天，今天排第一个，字符串 YYYY-MM-DD。"""
    base = today or date.today()
    if isinstance(base, datetime):
        base = base.date()
    return [(base - timedelta(days=i)).strftime('%Y-%m-%d')
            for i in range(max(1, int(n)))]


def _safe(name: str) -> str:
    return re.sub(r'[^0-9A-Za-z_.-]', '_', str(name)) or 'default'


def _extract_day(line: str):
    m = _DAY_RE.search(line or '')
    if not m:
        return None
    return '%04d-%02d-%02d' % (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def _ts_day(line: str):
    """只认行首时间戳，避免把 URL 里的日期当成一条日志的开始。"""
    m = _TS_LINE_RE.match(line or '')
    if not m:
        return None
    return '%04d-%02d-%02d' % (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def _file_day(path: str) -> str:
    try:
        return time.strftime('%Y-%m-%d', time.localtime(os.path.getmtime(path)))
    except OSError:
        return ''


def _shot_day(name: str, path: str) -> str:
    """优先取截图文件名里的日期，取不到就退回文件修改时间。"""
    m = _DAY_RE.search(name)
    if m:
        return '%04d-%02d-%02d' % (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = _COMPACT_DAY_RE.search(name)
    if m:
        return '%04d-%02d-%02d' % (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return _file_day(path)


def sanitize(text: str) -> str:
    """所有入包文本的统一脱敏出口。"""
    if not text:
        return text or ''
    text = _SECRET_FIELD_RE.sub(lambda m: '"%s": "***"' % m.group('k'), text)
    text = _PHONE_FIELD_RE.sub(
        lambda m: '"%s": "%s"' % (m.group('k'), '*' * (len(m.group('v')) - 4) + m.group('v')[-4:]),
        text)
    text = _PHONE_RE.sub(lambda m: '*******' + m.group(0)[-4:], text)
    text = _API_KEY_RE.sub(lambda m: m.group(1)[:3] + '***', text)
    return text


def filter_text(text: str, day_str: str) -> str:
    """按行首时间戳过滤到指定日期。

    状态机：
    - None：还没遇到任何行首时间戳（文件头），先攒着；
    - True / False：当前处于 / 不处于目标日，无时间戳的行全部算上一行的续行。
    这样 traceback、子进程多行输出、启动分隔块都不会被截断。
    """
    out, pending = [], []
    state = None
    for line in (text or '').splitlines():
        d = _ts_day(line)
        if d is not None:
            state = (d == day_str)
            if state:
                if pending:
                    out.extend(pending)
                    pending = []
                out.append(line)
            else:
                pending = []
        else:
            if state is True:
                out.append(line)
            elif state is None:
                pending.append(line)
    return '\n'.join(out)


def _is_structured_log(text: str) -> bool:
    """只有确实带逐行时间戳的日志才逐行过滤，其余整份按修改时间判断。"""
    lines = (text or '').splitlines()
    if not lines:
        return False
    dated = sum(1 for line in lines if _ts_day(line) is not None)
    return dated >= 2


def _read_text(path: str) -> str:
    try:
        with open(path, 'r', encoding='utf-8-sig', errors='replace') as f:
            return f.read()
    except (OSError, ValueError):
        return ''


def _rel(path: str, root: str) -> str:
    try:
        return os.path.relpath(path, root).replace('\\', '/')
    except ValueError:
        return path.replace('\\', '/')


def default_out_dir() -> str:
    desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
    if os.path.isdir(desktop):
        return desktop
    return paths.app_root()


def _app_version() -> str:
    try:
        with open(paths.asset('tool', 'version_info'), 'r', encoding='utf-8') as f:
            return f.read().strip()
    except (OSError, ValueError):
        return '未知'


# ---------------------------------------------------------------- 收集

def _collect(data_root: str, day_str: str, with_question_shots: bool):
    """返回 (entries, sections, warnings)。

    entries  : [(包名, bytes, 原始相对路径, 说明, 类型)]
    sections : [(包名, 说明, 文本)]  —— 用于生成包内唯一汇总 txt
    """
    entries, sections, warnings = [], [], []
    used = set()

    def add(packed, content, src, note, kind):
        if packed in used:                       # 同名不同源时加序号，避免 zip 里出现重复项
            base, ext = os.path.splitext(packed)
            i = 2
            while '%s_%d%s' % (base, i, ext) in used:
                i += 1
            packed = '%s_%d%s' % (base, i, ext)
        used.add(packed)
        entries.append((packed, content, _rel(src, data_root) if src else '-', note, kind))

    def add_text(src, packed, note, snapshot=False):
        if not os.path.isfile(src):
            return
        try:
            raw = _read_text(src)
        except Exception as e:                   # 单文件失败不影响整包
            warnings.append('读取失败 %s：%r' % (_rel(src, data_root), e))
            return
        if not raw:
            return
        if snapshot:
            body, label = raw, '当前快照（不受单日过滤）'
        elif _is_structured_log(raw):
            body = filter_text(raw, day_str)
            if not body.strip():
                return
            label = '仅 %s 的行' % day_str
        else:
            if _file_day(src) != day_str and day_str not in raw:
                return
            body, label = raw, '全文（无逐行时间戳，按文件日期判断）'
        body = sanitize(body)
        note_full = '%s｜%s' % (note, label)
        add(packed, body.encode('utf-8'), src, note_full, 'text')
        sections.append((packed, note_full, body))

    # 1) 根目录下的主日志 / 报错 / 自检 / 签到
    for packed, parts, note, snapshot in _TEXT_PLAN:
        add_text(os.path.join(data_root, *parts), packed, note, snapshot)

    # 2) 各账号的明细日志（含轮转备份）
    run_root = os.path.join(data_root, 'run')
    if os.path.isdir(run_root):
        try:
            accounts = sorted(n for n in os.listdir(run_root)
                              if os.path.isdir(os.path.join(run_root, n)))
        except OSError:
            accounts = []
        for acc in accounts:
            safe = _safe(acc)
            acc_dir = os.path.join(run_root, acc)
            for src_name, packed_name, suffix in (
                    ('运行日志.log', 'account.log', ''),
                    ('运行日志.log.old', 'account.log.old', '（轮转备份）')):
                add_text(os.path.join(acc_dir, src_name),
                         'logs/accounts/%s/%s' % (safe, packed_name),
                         'run/%s/%s%s' % (acc, src_name, suffix))

    # 3) 全部 JSON 配置 / 状态：当前快照，脱敏后纳入
    for folder, _dirs, files in os.walk(data_root):
        if '__pycache__' in folder or os.path.basename(folder).startswith('.'):
            continue
        for name in files:
            if not name.lower().endswith('.json'):
                continue
            src = os.path.join(folder, name)
            rel = _rel(src, data_root)
            add_text(src, 'config_sanitized/%s.json' % _safe(rel[:-5]),
                     '%s（已脱敏）' % rel, snapshot=True)

    # 4) 学习 / 成绩记录 txt：当前快照，全量纳入。
    #    原始文件名是中文课程名，包内改成 <账号>/study_01.txt / score_01.txt，
    #    原名与包内名的对应关系写在 README 对照表里。
    record_files = []
    for folder, _dirs, files in os.walk(data_root):
        if '__pycache__' in folder or os.path.basename(folder).startswith('.'):
            continue
        for name in files:
            if not name.lower().endswith('.txt') or name.endswith('.log'):
                continue
            src = os.path.join(folder, name)
            rel = _rel(src, data_root)
            if '记录' not in name and 'record' not in rel.lower():
                continue
            record_files.append((src, rel))
    record_counters = {}
    for src, rel in sorted(record_files, key=lambda x: x[1]):
        parts = rel.split('/')
        scope = _safe(parts[1]) if len(parts) > 2 and parts[0] == 'run' else 'root'
        kind = 'score' if '成绩' in os.path.basename(rel) else 'study'
        key = (scope, kind)
        record_counters[key] = record_counters.get(key, 0) + 1
        packed = 'records/%s/%s_%02d.txt' % (scope, kind, record_counters[key])
        add_text(src, packed, rel, snapshot=True)

    # 5) 诊断截图 / 图片题截图：按日期（文件名优先，其次修改时间）
    for folder, _dirs, files in os.walk(data_root):
        base = os.path.basename(folder)
        if base not in ('诊断截图', '图片题'):
            continue
        if base == '图片题' and not with_question_shots:
            continue
        scope = _safe(_rel(os.path.dirname(folder), data_root))
        for name in sorted(files):
            if not name.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                continue
            src = os.path.join(folder, name)
            if _shot_day(name, src) != day_str:
                continue
            stem, ext = os.path.splitext(name)
            m = re.match(r'^(?P<tag>.+?)_(?P<d>\d{8})_(?P<t>\d{6})$', stem)
            if m:
                ascii_name = _SHOT_TAG_MAP.get(m.group('tag'), 'shot')
                packed_name = '%s_%s_%s%s' % (ascii_name, m.group('d'), m.group('t'), ext)
            else:
                packed_name = _safe(name)
            try:
                with open(src, 'rb') as f:
                    content = f.read()
            except OSError as e:
                warnings.append('截图读取失败 %s：%r' % (_rel(src, data_root), e))
                continue
            add('shots/%s/%s' % (scope, packed_name), content, src,
                '%s｜%s 当日截图' % (_rel(src, data_root), day_str), 'binary')

    return entries, sections, warnings


def _build_readme(data_root: str, day_str: str, entries, warnings,
                  with_question_shots: bool) -> str:
    lines = [
        '课程学习助手 - 单日完整日志包',
        '=' * 78,
        '导出日期     : %s' % day_str,
        '导出时间     : %s' % time.strftime('%Y-%m-%d %H:%M:%S'),
        '程序版本     : %s' % _app_version(),
        '计算机 / 用户: %s / %s' % (os.environ.get('COMPUTERNAME', '-'),
                                    os.environ.get('USERNAME', '-')),
        '系统         : %s' % platform.platform(),
        '数据目录     : %s' % data_root,
        '',
        '【这个文件是什么】',
        '  一个 zip，就是本次导出的全部结果。里面另外放了一份',
        '  00_FULL_LOG_%s.txt：所有文本日志按来源合并成一份，' % day_str,
        '  不用一个个翻文件，直接把那份 txt（或整个 zip）发给开发者即可。',
        '',
        '【范围与规则】',
        '  · 日志：只保留 %s 的行；带行首时间戳的逐行过滤，' % day_str,
        '    无时间戳的续行（异常堆栈、子进程输出、分隔线）跟着上一行保留。',
        '  · 无逐行时间戳的文件：按文件修改时间判断是否属于当天。',
        '  · 学习记录 / 配置 JSON：属于「当前快照」，不受单日过滤，全量纳入。',
        '  · 诊断截图：按文件名里的日期或文件修改时间筛选当天。',
        '  · 图片题截图：%s' % ('已包含' if with_question_shots else '默认不含（体积大）'),
        '  · 未纳入：*.pkl 题库缓存、*.pyc、浏览器 Cookie 二进制等非日志数据。',
        '',
        '【脱敏】',
        '  password / pwd / api_key / token / secret / cookie 等字段已抹成 ***；',
        '  明文手机号只保留后 4 位；sk- 开头的 API Key 已打码。',
        '  包内文件名一律 ASCII，避免换机器解压乱码；原名见下面的对照表。',
        '',
    ]
    if warnings:
        lines.append('【跳过 / 警告】')
        lines.extend('  ! ' + w for w in warnings)
        lines.append('')
    lines.append('【包内文件清单】')
    lines.append('%-52s %10s  %s' % ('包内文件', '字节', '原始位置｜说明'))
    lines.append('-' * 78)
    for packed, content, src, note, _kind in entries:
        lines.append('%-52s %10d  %s｜%s' % (packed, len(content), src, note))
    lines.append('')
    lines.append('【数据目录完整清单（字节 / 修改时间 / 相对路径）】')
    lines.append('-' * 78)
    try:
        all_files = []
        for folder, _dirs, files in os.walk(data_root):
            for name in files:
                p = os.path.join(folder, name)
                try:
                    st = os.stat(p)
                except OSError:
                    continue
                all_files.append((st.st_size,
                                  time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(st.st_mtime)),
                                  _rel(p, data_root)))
        for size, mtime, rel in sorted(all_files, key=lambda x: x[2]):
            lines.append('%10d  %s  %s' % (size, mtime, rel))
    except OSError as e:
        lines.append('  清单生成失败：%r' % (e,))
    lines.append('')
    return '\n'.join(lines) + '\n'


def _build_full_log(day_str: str, sections) -> str:
    log_sections = [s for s in sections if '当前快照' not in s[1]]
    head = [
        '课程学习助手 完整日志汇总（单日）',
        '=' * 78,
        '日期      : %s' % day_str,
        '导出时间  : %s' % time.strftime('%Y-%m-%d %H:%M:%S'),
        '文本来源  : 日志 %d 份 / 配置与记录快照 %d 份'
        % (len(log_sections), len(sections) - len(log_sections)),
        '说明      : 日志按来源分节，只含 %s 的内容；' % day_str,
        '            配置为当前快照，不受单日过滤；密码 / API Key 已抹除，手机号只留后 4 位。',
        '=' * 78,
        '',
    ]
    out = list(head)
    if not sections:
        out.append('（当天没有收集到任何文本日志，也没有可用配置 / 记录）')
        out.append('')
    elif not log_sections:
        out.append('注意：没有找到 %s 的日志；以下内容均为当前快照（配置 / 学习记录），'
                   '不代表该日运行记录。' % day_str)
        out.append('')
    for idx, (packed, note, body) in enumerate(sections, 1):
        out.append('')
        out.append('#' * 78)
        out.append('【%d/%d】%s' % (idx, len(sections), packed))
        out.append('    原始位置｜说明：%s' % note)
        out.append('#' * 78)
        out.append(body.rstrip('\n'))
        out.append('')
    return '\n'.join(out) + '\n'


# ---------------------------------------------------------------- 对外入口

def export_day_logs(day=None, out_dir=None, data_root=None,
                    with_question_shots: bool = False) -> dict:
    """导出某一天的完整日志，返回单个 zip 文件的路径。

    参数
      day        : None=今天，或 'YYYY-MM-DD' / date / datetime
      out_dir    : 输出目录，默认桌面
      data_root  : 数据目录，默认 paths.DATA_ROOT（测试可传临时目录）
      with_question_shots : 是否连图片题截图一起打包

    返回 dict：ok / zip_path / day / entries / warnings / error / size
    无论数据目录是否存在都会产出一个 zip（里面写清情况），不会抛异常打断 GUI。
    """
    result = {'ok': False, 'zip_path': '', 'day': '', 'entries': [],
              'warnings': [], 'error': '', 'size': 0}
    try:
        day_obj = parse_day(day)
    except ValueError as e:
        result['error'] = str(e)
        return result
    day_str = day_obj.strftime('%Y-%m-%d')
    result['day'] = day_str
    root = os.path.abspath(data_root or paths.DATA_ROOT)
    target_dir = os.path.abspath(out_dir or default_out_dir())
    try:
        os.makedirs(target_dir, exist_ok=True)
    except OSError:
        target_dir = os.path.abspath(default_out_dir())
        try:
            os.makedirs(target_dir, exist_ok=True)
        except OSError:
            pass

    warnings = []
    if not os.path.isdir(root):
        warnings.append('没找到数据目录：%s（程序可能还没在这台电脑上运行过）' % root)

    try:
        entries, sections, collect_warnings = _collect(root, day_str, with_question_shots)
    except Exception as e:                       # 兜底：收集阶段任何意外都不该让界面崩
        entries, sections, collect_warnings = [], [], ['收集阶段异常：%r' % (e,)]
    warnings.extend(collect_warnings)

    readme = _build_readme(root, day_str, entries, warnings, with_question_shots)
    full_log = _build_full_log(day_str, sections)
    stamp = time.strftime('%H%M%S')
    zip_name = '%s%s_%s.zip' % (ZIP_PREFIX, day_str.replace('-', ''), stamp)
    zip_path = os.path.join(target_dir, zip_name)
    seq = 2
    while os.path.exists(zip_path):              # 同一秒连点两次也不覆盖上一次
        zip_path = os.path.join(target_dir, '%s%s_%s_%d.zip'
                                % (ZIP_PREFIX, day_str.replace('-', ''), stamp, seq))
        seq += 1

    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(README_NAME, sanitize(readme).encode('utf-8'))
            zf.writestr('00_FULL_LOG_%s.txt' % day_str, sanitize(full_log).encode('utf-8'))
            for packed, content, _src, _note, _kind in entries:
                zf.writestr(packed, content)
    except (OSError, ValueError, zipfile.BadZipFile) as e:
        result['error'] = '写 zip 失败：%r' % (e,)
        result['warnings'] = warnings
        return result

    result['ok'] = True
    result['zip_path'] = zip_path
    result['entries'] = [p for p, _c, _s, _n, _k in entries]
    result['warnings'] = warnings
    try:
        result['size'] = os.path.getsize(zip_path)
    except OSError:
        pass
    return result
