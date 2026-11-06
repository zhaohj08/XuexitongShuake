# -*- coding: utf-8 -*-
"""「导出完整日志」回归测试（纯桩：临时目录 + zipfile，不联网、不开界面/浏览器）。

覆盖需求：一个单独文件、包含所有数据、只导单日、敏感信息不外泄。
"""
import os
import shutil
import sys
import tempfile
import time
import zipfile
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

from core import log_export  # noqa: E402

FAILS = []
DAY = '2026-11-05'
YDAY = '2026-11-04'


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (('  -> ' + str(detail)) if detail else ''))
    if not ok:
        FAILS.append(name)


def put(root, rel, text, mtime=None):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def put_bin(root, rel, data, mtime=None):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        f.write(data)
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def ts_of(day, hour=9):
    return time.mktime(time.strptime('%s %02d:00:00' % (day, hour), '%Y-%m-%d %H:%M:%S'))


def build_fixture(root):
    # 固定成目标日期当天，避免跨天运行时 mtime 落在另一天，
    # 导致「无逐行时间戳、按文件修改时间判断」的账号明细日志被排除。
    today_ts = ts_of(DAY, 23)
    yesterday_ts = ts_of(YDAY)

    put(root, 'logs/程序日志.log', '\n'.join([
        '',
        '=' * 78,
        '启动 2026-11-05 08:59:00   版本 26.11.05.1832',
        'pid=123  python=3.13  frozen=True',
        '=' * 78,
        '2026-11-05 09:00:00.123 [INFO ] 当天启动完成',
        '2026-11-05 09:00:01.123 [UI   ] 点击「开始学习」',
        '2026-11-04 09:00:00.000 [INFO ] 前一天的记录不该出现',
        '2026-11-05 09:00:02.123 [CHILD] acc_A | 正在学习',
    ]) + '\n', mtime=today_ts)

    put(root, 'error.log', '\n'.join([
        '2026-11-05 10:00:00 ERROR 出错了',
        'Traceback (most recent call last):',
        '  File "main.py", line 1, in <module>',
        'ValueError: boom',
        '2026-11-04 10:00:00 ERROR 昨天的错不该出现',
    ]) + '\n', mtime=today_ts)

    put(root, '输出记录.log', '\n'.join([
        '2026-11-05 09:00:00,100 - INFO - 界面启动',
        '2026-11-04 09:00:00,100 - INFO - 昨天的界面日志',
    ]) + '\n', mtime=today_ts)

    put(root, 'data/sign.log', '\n'.join([
        '[2026-11-05 09:00:00] 签到检测已启动: 每 30 秒检查一次',
        '[2026-11-05 09:00:01] 课程列表: 24 门',
        '[2026-11-04 09:00:00] 昨天的签到日志',
    ]) + '\n', mtime=today_ts)

    # 账号明细日志只有 HH:MM:SS，没有日期 → 按文件修改时间判断
    put(root, 'run/acc_A/运行日志.log', '\n'.join([
        '09:01:00 === 子进程启动 pid=999 ===',
        '09:01:05 正在登录中...',
        '09:01:10 登录成功',
    ]) + '\n', mtime=today_ts)

    # 昨天修改的无日期日志，不该混进来
    put(root, 'run/acc_B/运行日志.log', '09:00:00 昨天的账号日志\n', mtime=yesterday_ts)

    put(root, 'tool/accounts.json',
        '{"phone_number": "13800001475", "password": "abc123", '
        '"api_key": "sk-abcdefghijklmnop", "token": "xyz"}', mtime=today_ts)
    put(root, 'run/acc_A/tool/course_process.json',
        '{"《形势与政策》": [3, 10]}', mtime=today_ts)
    put(root, 'run/acc_A/record/《形势与政策》的学习记录.txt',
        '第一章 已完成\n第二章 学习中\n', mtime=today_ts)

    png = (b'\x89PNG\r\n\x1a\n' + b'fake' * 8)
    put_bin(root, 'run/acc_A/record/诊断截图/未识别页面_20261105_120000.png', png,
            mtime=ts_of(DAY, 12))
    put_bin(root, 'run/acc_A/record/诊断截图/页面卡住_20261104_120000.png', png,
            mtime=ts_of(YDAY, 12))
    put_bin(root, 'run/acc_A/record/图片题/题目_20261105_130000.png', png,
            mtime=ts_of(DAY, 13))
    # 非日志二进制不该被收进来
    put_bin(root, 'run/acc_A/record/cache_ques1.pkl', b'pkl-data', mtime=today_ts)


def read_zip(zf, name):
    return zf.read(name).decode('utf-8', errors='replace')


# ---------------------------------------------------------------- 单元

check('parse_day 默认取今天',
      log_export.parse_day() == date.today(), log_export.parse_day())
check('parse_day 接受 YYYY-MM-DD',
      log_export.parse_day(DAY) == date(2026, 11, 5))
check('parse_day 接受 YYYY/MM/DD',
      log_export.parse_day('2026/11/05') == date(2026, 11, 5))
try:
    log_export.parse_day('不是日期')
    check('parse_day 拒绝非法日期', False)
except ValueError:
    check('parse_day 拒绝非法日期', True)

days = log_export.recent_days(7, today=date(2026, 11, 5))
check('recent_days 今天排第一且共 7 天',
      days[0] == DAY and len(days) == 7 and days[-1] == '2026-10-30', days)

sample = '\n'.join([
    '', '=' * 40,
    '启动 2026-11-05 08:59:00   版本 x',
    '2026-11-05 09:00:00 [INFO] 当天',
    '  这是没有时间戳的续行（堆栈/子进程输出）',
    '2026-11-04 09:00:00 [INFO] 前一天',
    '  前一天的续行也不该出现',
    '2026-11-05 09:01:00 [INFO] 又回到当天',
])
filtered = log_export.filter_text(sample, DAY)
check('按日过滤：保留当天行', '当天' in filtered and '又回到当天' in filtered)
check('按日过滤：剔除前一天行', '前一天' not in filtered and '前一天的续行' not in filtered)
check('按日过滤：续行跟着保留', '这是没有时间戳的续行' in filtered)
check('按日过滤：文件头的启动块保留', '启动 2026-11-05' in filtered and '=' * 40 in filtered)

masked = log_export.sanitize(
    '{"password": "abc123", "api_key": "sk-abcdefghijklmnop", '
    '"phone_number": "13800001475"} 手机 13800001475')
check('脱敏：密码字段抹除', 'abc123' not in masked and '"***"' in masked)
check('脱敏：API Key 打码', 'sk-abcdefghijklmnop' not in masked)
check('脱敏：手机号只留后 4 位', '13800001475' not in masked and '1475' in masked, masked)

check('default_out_dir 返回可写目录',
      isinstance(log_export.default_out_dir(), str) and log_export.default_out_dir() != '')

# ---------------------------------------------------------------- 主流程

tmp = tempfile.mkdtemp(prefix='xt_log_export_')
try:
    data_root = os.path.join(tmp, 'data')
    out_dir = os.path.join(tmp, 'out')
    os.makedirs(out_dir, exist_ok=True)
    build_fixture(data_root)

    result = log_export.export_day_logs(day=DAY, out_dir=out_dir, data_root=data_root)
    check('导出成功', result['ok'] is True, result.get('error'))
    zip_path = result.get('zip_path', '')
    check('生成的是单个文件', os.path.isfile(zip_path) and zip_path.endswith('.zip'), zip_path)
    check('输出目录里只有这一个导出文件', len(os.listdir(out_dir)) == 1, os.listdir(out_dir))
    check('文件名带目标日期', '20261105' in os.path.basename(zip_path), os.path.basename(zip_path))
    check('返回字节数 > 0', result.get('size', 0) > 0, result.get('size'))

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        check('包内文件名一律 ASCII',
              all(ord(c) < 128 for n in names for c in n), names[:5])
        check('包含 README', log_export.README_NAME in names)
        full_name = '00_FULL_LOG_%s.txt' % DAY
        check('包含所有文本合并的汇总 txt', full_name in names)
        full = read_zip(zf, full_name)
        check('汇总含当天主日志行', '当天启动完成' in full)
        check('汇总不含前一天主日志行', '前一天的记录不该出现' not in full)
        check('汇总含签到日志', '课程列表: 24 门' in full)
        check('汇总含异常堆栈续行', 'ValueError: boom' in full)
        check('汇总不含昨天的错', '昨天的错不该出现' not in full)
        check('汇总不含明文手机号', '13800001475' not in full)

        check('包含主日志', 'logs/main.log' in names)
        main_text = read_zip(zf, 'logs/main.log')
        check('主日志按日过滤', '当天启动完成' in main_text and '前一天的记录' not in main_text)
        check('包含报错日志', 'logs/error.log' in names)
        check('包含签到日志', 'logs/sign.log' in names)
        check('包含 logging 记录', 'logs/gui.log' in names)

        check('包含当日账号明细日志', 'logs/accounts/acc_A/account.log' in names)
        check('不含昨天修改的账号日志', 'logs/accounts/acc_B/account.log' not in names)

        shots = [n for n in names if n.startswith('shots/')]
        check('只收当日诊断截图', any('20261105' in n for n in shots)
              and not any('20261104' in n for n in shots), shots)
        check('默认不含图片题截图', not any('图片题' in n or 'question' in n for n in shots), shots)
        check('不收 pkl 缓存', not any(n.endswith('.pkl') for n in names))

        cfgs = [n for n in names if n.startswith('config_sanitized/')]
        check('包含脱敏配置', len(cfgs) >= 2, cfgs)
        cfg_all = '\n'.join(read_zip(zf, n) for n in cfgs)
        check('配置里密码已抹除', 'abc123' not in cfg_all and '"***"' in cfg_all)
        check('配置里 API Key 已打码', 'sk-abcdefghijklmnop' not in cfg_all)
        check('配置里手机号只留后 4 位', '13800001475' not in cfg_all and '1475' in cfg_all)
        check('包含课程进度 JSON', any('course_process' in n for n in cfgs), cfgs)

        records = [n for n in names if n.startswith('records/')]
        check('包含学习记录（当前快照，不过滤日期）', len(records) >= 1, records)
        check('学习记录内容完整', '第一章 已完成' in read_zip(zf, records[0]))

        readme = read_zip(zf, log_export.README_NAME)
        check('README 写明单日范围', DAY in readme and '00_FULL_LOG' in readme)
        check('README 含数据目录完整清单', '数据目录完整清单' in readme and 'cache_ques1.pkl' in readme)
        check('README 已脱敏', '13800001475' not in readme)

    # 带图片题截图
    result2 = log_export.export_day_logs(day=DAY, out_dir=out_dir, data_root=data_root,
                                         with_question_shots=True)
    with zipfile.ZipFile(result2['zip_path']) as zf2:
        shots2 = [n for n in zf2.namelist() if n.startswith('shots/')]
    check('勾选后包含图片题截图', len(shots2) > len(shots), (len(shots), len(shots2)))

    # 另一天：仍然生成单文件，但不含本日日志
    out2 = os.path.join(tmp, 'out2')
    r3 = log_export.export_day_logs(day='2026-01-01', out_dir=out2, data_root=data_root)
    check('导出其它日期不崩溃且仍是单文件', r3['ok'] and os.path.isfile(r3['zip_path']))
    with zipfile.ZipFile(r3['zip_path']) as zf3:
        check('其它日期不含 11-05 主日志', 'logs/main.log' not in zf3.namelist())
        other_full = read_zip(zf3, '00_FULL_LOG_2026-01-01.txt')
        check('其它日期汇总明确注明「没有找到该日日志」',
              '没有找到 2026-01-01 的日志' in other_full, other_full[:300])
        check('其它日期汇总标明配置/记录为快照',
              '当前快照' in other_full and '日志 0 份' in other_full)

    # 数据目录不存在 / 非法日期
    out3 = os.path.join(tmp, 'out3')
    r4 = log_export.export_day_logs(day=DAY, out_dir=out3,
                                    data_root=os.path.join(tmp, 'does_not_exist'))
    check('数据目录不存在也生成 zip 且带提示',
          r4['ok'] and r4['warnings'] and os.path.isfile(r4['zip_path']), r4['warnings'])
    r5 = log_export.export_day_logs(day='乱码', out_dir=out3, data_root=data_root)
    check('非法日期返回 ok=False 且不抛异常', r5['ok'] is False and r5['error'] != '', r5['error'])

    # 无行首时间戳、且修改日是昨天的纯文本不该混入
    out4 = os.path.join(tmp, 'out4')
    r6 = log_export.export_day_logs(day=DAY, out_dir=out4, data_root=data_root)
    with zipfile.ZipFile(r6['zip_path']) as zf6:
        check('无时间戳且非当天的账号日志被排除',
              'logs/accounts/acc_B/account.log' not in zf6.namelist())
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# ---------------------------------------------------------------- GUI 集成（静态锁，防回退）
start_py = open(os.path.join(ROOT, 'start.py'), encoding='utf-8').read()
check('start.py 顶层导入导出弹窗',
      'from gui.log_export_dialog import open_export_dialog' in start_py)
check('start.py 有导出按钮且绑定到弹窗',
      'export_log_button' in start_py and 'open_export_dialog(self.root)' in start_py)
check('主页日志区已扩到 4 列', 'columnspan=4' in start_py)
check('导出按钮纳入主题换色列表', 'self.export_log_button,' in start_py)
check('selftest 覆盖两个新模块',
      "'core.log_export'" in start_py and "'gui.log_export_dialog'" in start_py)

print('')
if FAILS:
    print('FAILED %d: %s' % (len(FAILS), ', '.join(FAILS)))
    sys.exit(1)
print('ALL PASS')
sys.exit(0)
