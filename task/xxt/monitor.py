# -*- coding: utf-8 -*-
"""检测循环: 拉取全部课程 -> 查找进行中的 普通/位置 签到 -> 自动签到。

默认每 30 秒一轮；连续多轮没有签到会逐步降频（最多 120 秒）；
最长连续运行 4 小时自动停止，避免忘了关窗口时对平台持续高频请求。
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, Tuple

from . import constants, courses, sign, storage
from .client import XXTClient

DEFAULT_WORKERS = 5
CLIENT_FACTORY = XXTClient      # 便于测试替换


def _fetch_activities(client: XXTClient, course) -> Tuple[object, List]:
    """单个课程的活动查询(用独立会话, 保证并发安全)"""
    worker = CLIENT_FACTORY(uid=getattr(client, "uid", ""),
                            fid=getattr(client, "fid", ""),
                            name=getattr(client, "name", ""),
                            cookies=getattr(client, "cookies", ""))
    try:
        return course, courses.get_ongoing_activities(worker, course)
    except Exception as e:
        storage.log("课程 %s 活动查询异常: %s" % (course.title, e),sign_text=sign_txt)
        return course, []


def collect_ongoing(client: XXTClient, course_cache: List,
                    workers: int = DEFAULT_WORKERS) -> List:
    """并发收集所有课程里需要处理的签到活动"""
    if not course_cache:
        return []
    if workers and workers > 1 and len(course_cache) > 1:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(lambda c: _fetch_activities(client, c),
                                    course_cache))
    else:
        results = [_fetch_activities(client, c) for c in course_cache]

    pending = []
    for _course, acts in results:
        for act in acts:
            if not storage.is_signed(act.aid):     # 已处理过的不再提交
                pending.append(act)
    return pending


def scan_and_sign_once(client: XXTClient, course_cache: Optional[List] = None,
                       workers: int = DEFAULT_WORKERS) -> List[object]:
    """一轮检查: 返回本轮处理过的活动列表"""
    all_courses = course_cache or courses.get_courses(client)
    if not all_courses:
        storage.log("未获取到课程列表(登录可能已失效)",sign_text=sign_txt)
        return []

    handled = []
    pending = collect_ongoing(client, all_courses, workers)
    if pending:
        storage.log("本轮发现 %d 个待处理签到" % len(pending),sign_text=sign_txt)
    for act in pending:
        try:
            result = sign.sign_activity(client, act,sign_text=sign_txt)
        except Exception as e:
            storage.log("  签到异常 %s: %s" % (act.aid, e),sign_text=sign_txt)
            continue
        storage.log("  结果: %s" % result.text,sign_text=sign_txt)
        if result.is_ok() or result.locked or result.auth_error \
                or result.need_captcha or result.need_face or result.need_photo:
            if result.need_captcha or result.need_face or result.need_photo:
                storage.log("  该签到需要额外验证(滑块/人脸/拍照), 本次跳过",sign_text=sign_txt)
            storage.mark_signed(act.aid, result.text, act.name, act.course.title)
            handled.append(act)
    return handled

sign_txt=None
def monitor(client: XXTClient, interval: Optional[int] = None,
            course_refresh_cycles: int = constants.COURSE_REFRESH_CYCLES,
            workers: int = DEFAULT_WORKERS,
            stop_event=None,sign_text=None) -> None:
    global sign_txt
    sign_txt=sign_text
    base_interval = max(1, int(interval or constants.CHECK_INTERVAL))
    max_interval = max(base_interval, int(constants.MAX_CHECK_INTERVAL))
    max_runtime = int(constants.MAX_RUNTIME or 0)
    idle_rounds = 0
    started = time.time()
    storage.log("签到检测已启动: 每 %d 秒检查一次 (并发 %d, 最长 %d 分钟, Ctrl+C 退出)"
                % (base_interval, workers, max_runtime // 60),sign_text=sign_text)
    all_courses: List = []
    cycle = 0
    while True:
        if stop_event and stop_event.is_set():
            storage.log("签到检测已停止",sign_text=sign_text)
            break
        if max_runtime and time.time() - started >= max_runtime:
            storage.log("自动签到已连续运行 %d 分钟，自动停止（避免长时间高频请求）"
                        % (max_runtime // 60),sign_text=sign_text)
            break
        cycle += 1
        if not all_courses or cycle % course_refresh_cycles == 1:
            all_courses = courses.get_courses(client)
            storage.log("课程列表: %d 门" % len(all_courses),sign_text=sign_text)
            if not all_courses:
                from . import login as login_mod
                new_client = login_mod.restore_client(sign_text=sign_text)
                if new_client is not None:
                    client.__dict__.update(new_client.__dict__)
                    all_courses = courses.get_courses(client)
                    storage.log("重新登录后课程列表: %d 门" % len(all_courses),sign_text=sign_text)
        try:
            handled = scan_and_sign_once(client, all_courses, workers)
            if handled:
                idle_rounds = 0
                storage.log("本轮完成 %d 个签到" % len(handled),sign_text=sign_txt)
            else:
                idle_rounds += 1
        except KeyboardInterrupt:
            raise
        except Exception as e:
            storage.log("本轮检查异常: %s" % e,sign_text=sign_txt)
            idle_rounds += 1
        # 一直没人发起签到就没必要每 30 秒全量扫一遍所有课程
        cur_interval = base_interval
        if idle_rounds >= constants.IDLE_BACKOFF_AFTER:
            factor = 2 ** min(3, idle_rounds // constants.IDLE_BACKOFF_AFTER)
            cur_interval = min(max_interval, base_interval * factor)
        time.sleep(cur_interval)