# -*- coding: utf-8 -*-
"""更新检查的版本比较测试（纯逻辑，不联网、不弹窗）。

背景：本地版本号改为「年.月.日.构建号」（如 26.10.30.2116），发布包名里通常只有日期
（如 26.10.25）。旧逻辑用 `version in file_name` 判断，本地日期比发布包新时会误报
「有新版本可用」，并且每次都会把弹窗开出来再立刻销毁（窗口一闪）。

用法：C:/Python315/python.exe tests/test_update_version.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from gui.update_checker import UpdateChecker, parse_version

FAILS = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (('  -> ' + str(detail)) if detail else ''))
    if not ok:
        FAILS.append(name)


def main():
    check('解析四段版本号', parse_version('26.10.30.2116') == (26, 10, 30, 2116),
          parse_version('26.10.30.2116'))
    check('解析文件名里的三段版本号',
          parse_version('CourseStudyHelper-26.10.25.exe') == (26, 10, 25, 0),
          parse_version('CourseStudyHelper-26.10.25.exe'))
    check('无版本号时返回 None', parse_version('release-asset.exe') is None)

    local = '26.10.30.2116'
    check('本地比发布包新 -> 无需更新',
          UpdateChecker._is_latest(local, 'CourseStudyHelper-26.10.25.exe') is True)
    check('同一天的不同构建 -> 仍算最新',
          UpdateChecker._is_latest(local, 'CourseStudyHelper-26.10.30.exe') is True)
    check('发布包更新 -> 提示更新',
          UpdateChecker._is_latest(local, 'CourseStudyHelper-26.11.01.exe') is False)
    check('发布包只有日期且更晚 -> 提示更新',
          UpdateChecker._is_latest('26.10.30.2116', '课程学习助手 26.12.01.exe') is False)
    check('解析不出时退回子串判断（命中即最新）',
          UpdateChecker._is_latest('26.10.30.2116', 'start-26.10.30.2116.exe') is True)
    check('解析不出时退回子串判断（不命中则提示）',
          UpdateChecker._is_latest('26.10.30.2116', 'release-asset.exe') is False)

    print('---')
    if FAILS:
        print('FAILED: %d' % len(FAILS), FAILS)
        return 1
    print('ALL PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
