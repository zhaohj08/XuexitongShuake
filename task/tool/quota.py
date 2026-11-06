# -*- coding: utf-8 -*-
"""联网答题的**频率限制**：不限制总量，但保证任何时候都不会把额度瞬间刷爆。

用户要求（2026-10-31）：「100 次太少，改成限制频率」。

现在的规则：
1. **每分钟最多 20 次**（默认）——超了就**等**到下一个时间窗再继续，不丢题；
2. **同一道题最多问 DeepSeek 2 次**（按题目文本指纹）——防止同一道题反复重试；
3. 没有总量上限：一场测验题多就多花点时间，不会因为到顶而拒绝作答。

使用方式：
- 题库接口：`quota.acquire('', '题库')`（只受频率限制）；
- DeepSeek：`quota.acquire(quota.question_key(题目), 'deepseek')`（频率 + 同题次数）。

计数是进程级的（一个账号一个子进程），线程安全；`reset()` 可在新一轮学习开始时清零。
"""
from __future__ import annotations

import hashlib
import threading
import time

from task.tool import color

MAX_TOTAL = None       # 不设总量上限（保留参数只为兼容旧调用/测试）
MAX_PER_MINUTE = 20    # 每分钟最多联网 20 次，超了就等下一个时间窗
MAX_PER_QUESTION = 2   # 同一道题最多问 DeepSeek 2 次


def question_key(text: str) -> str:
    """题目文本 -> 短指纹，用于统计"同一道题问了几次"。"""
    raw = (text or '').strip()
    if not raw:
        return ''
    return hashlib.md5(raw.encode('utf-8', 'ignore')).hexdigest()[:16]


class ApiQuota:
    def __init__(self, max_total=MAX_TOTAL, max_per_minute=MAX_PER_MINUTE,
                 max_per_question=MAX_PER_QUESTION):
        self.max_total = max_total
        self.max_per_minute = max_per_minute
        self.max_per_question = max_per_question
        self.total = 0
        self.window_start = time.time()
        self.window_count = 0
        self.per_question = {}
        self.stopped = False
        self.last_reason = ''
        self._lock = threading.Lock()
        self._warned = set()

    # ---------------------------------------------------------------- 计数
    def allow(self, key: str = '', tag: str = '搜题') -> bool:
        """问能不能马上发一次请求；被拒时 `last_reason` 说明原因。"""
        with self._lock:
            now = time.time()
            if now - self.window_start >= 60:
                self.window_start = now
                self.window_count = 0
            if self.stopped:
                self.last_reason = 'stopped'
                return False
            if self.max_total and self.total >= self.max_total:
                self.stopped = True
                self.last_reason = 'total'
                self._warn('total', '联网次数已达上限 %d 次，剩下的题不再联网' % self.max_total)
                return False
            if self.window_count >= self.max_per_minute:
                self.last_reason = 'minute'
                self._warn('minute', '每分钟最多联网 %d 次，达到后会自动等待下一个时间窗'
                           % self.max_per_minute)
                return False
            if key and self.per_question.get(key, 0) >= self.max_per_question:
                self.last_reason = 'question'
                self._warn('q:' + key, '同一道题已重试 %d 次，直接跳过（不重复消耗）'
                           % self.max_per_question)
                return False
            self.total += 1
            self.window_count += 1
            if key:
                self.per_question[key] = self.per_question.get(key, 0) + 1
            self.last_reason = ''
            return True

    def acquire(self, key: str = '', tag: str = '搜题', wait: bool = True,
                max_wait: float = 90) -> bool:
        """要一次调用许可：频率超了就**等**到下一个窗口，同题超限则直接返回 False。

        `max_wait` 是单次最多等待的秒数（默认 90，比一个时间窗略长）。
        """
        deadline = time.time() + max(0, max_wait)
        while True:
            if self.allow(key, tag):
                return True
            if not wait or self.stopped or self.last_reason != 'minute':
                return False
            if time.time() >= deadline:
                return False
            pause = max(0.5, 60 - (time.time() - self.window_start))
            time.sleep(min(pause, 5.0))

    def _warn(self, key: str, message: str) -> None:
        if key in self._warned:
            return
        self._warned.add(key)
        print(color.yellow('⏳ ' + message), flush=True)

    def stats(self) -> dict:
        with self._lock:
            return {'total': self.total, 'per_minute': self.window_count,
                    'questions': len(self.per_question), 'stopped': self.stopped,
                    'max_total': self.max_total, 'max_per_minute': self.max_per_minute}


_QUOTA = ApiQuota()


def allow(key: str = '', tag: str = '搜题') -> bool:
    return _QUOTA.allow(key, tag)


def acquire(key: str = '', tag: str = '搜题', wait: bool = True, max_wait: float = 90) -> bool:
    return _QUOTA.acquire(key, tag, wait=wait, max_wait=max_wait)


def stats() -> dict:
    return _QUOTA.stats()


def reset(max_total: int = None) -> None:
    """新一轮学习开始时调用：清零计数。"""
    with _QUOTA._lock:
        _QUOTA.total = 0
        _QUOTA.window_start = time.time()
        _QUOTA.window_count = 0
        _QUOTA.per_question.clear()
        _QUOTA.stopped = False
        _QUOTA.last_reason = ''
        _QUOTA._warned.clear()
        if max_total is not None:
            _QUOTA.max_total = max_total
