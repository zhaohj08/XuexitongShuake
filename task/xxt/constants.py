# -*- coding: utf-8 -*-
"""
常量 / 接口地址 / 密钥
唯一保留的两种签到: 普通签到(otherId=0) 与 位置签到(otherId=4)
"""
from __future__ import annotations

# ---------------- 签到类型 ----------------
SIGN_NORMAL = "0"
SIGN_LOCATION = "4"

# ---------------- 用户代理 ----------------
UA_IOS = ("Mozilla/5.0 (iPhone; CPU iPhone OS 14_2_1 like Mac OS X) "
          "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
          "com.ssreader.ChaoXingStudy/ChaoXingStudy_3_4.8_ios_phone_202012052220_56 "
          "(@Kalimdor)_12787186548451577248")
UA_IOS_SIMPLE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 14_2_1 like Mac OS X) "
                 "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148")
UA_DESKTOP = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36 Edg/117.0.2045.60")
REFERER_MOOC = ("https://mooc1-2.chaoxing.com/visit/interaction"
                "?s=a5913ee5215774a303a05e9c9358f603")
ACCEPT_LANG = "zh-Hans-CN;q=1, zh-Hant-CN;q=0.9"

# ---------------- 登录 ----------------
LOGIN_REGISTER = "https://passport2-api.chaoxing.com/v11/loginregister"
FANYALOGIN_URL = "https://passport2.chaoxing.com/fanyalogin"
GET_PUID = "https://sso.chaoxing.com/apis/login/userLogin4Uname.do"

# ---------------- 课程 / 活动 ----------------
COURSE_LIST = "http://mooc1-api.chaoxing.com/mycourse/backclazzdata"
ACTIVE_LIST = ("https://mobilelearn.chaoxing.com/v2/apis/active/student/activelist")
ACTIVE_TASK_LIST = "https://mobilelearn.chaoxing.com/ppt/activeAPI/taskactivelist"
ACTIVE_INFO = "https://mobilelearn.chaoxing.com/v2/apis/active/getPPTActiveInfo"
SIGN_DETAIL = "https://mobilelearn.chaoxing.com/newsign/signDetail"

# ---------------- 签到 ----------------
SIGN_AJAX = "https://mobilelearn.chaoxing.com/pptSign/stuSignajax"
PRE_SIGN = "https://mobilelearn.chaoxing.com/newsign/preSign"
ANALYSIS = "https://mobilelearn.chaoxing.com/pptSign/analysis"
ANALYSIS2 = "https://mobilelearn.chaoxing.com/pptSign/analysis2"

# ---------------- 加解密 / 其他 ----------------
AES_KEY = "u2oh6Vu^HWe4_AES"          # 本地保存密码 & fanyalogin 传输
DEFAULT_AMAP_KEY = "cf7120783770ef244dc54f203487bbea"   # 地址->坐标(可用 config 覆盖)
AMAP_GEOCODE_URL = "https://restapi.amap.com/v3/geocode/geo"

# ---------------- 运行参数 ----------------
# 2026-11-05：这里原本写成 2 秒（注释却写着 7 秒），每轮会对全部课程各发一次
# ACTIVE_LIST 请求，24 门课约 12 次/秒，挂机几小时就能刷出几十万次平台请求，
# 用户账号因此被封。现改为 30 秒基础间隔 + 空闲退避 + 最长运行 4 小时。
CHECK_INTERVAL = 30             # 基础检查间隔（秒）
IDLE_BACKOFF_AFTER = 10         # 连续多少轮没有待处理签到后开始降频
MAX_CHECK_INTERVAL = 120        # 空闲退避的上限（秒）
MAX_RUNTIME = 4 * 3600          # 最长连续运行时间（秒），到点自动停止
COURSE_REFRESH_CYCLES = 30      # 每 30 轮刷新一次课程列表（按 30 秒间隔约 15 分钟）
REQUEST_INTERVAL = 0.25         # 位置签到坐标修正时的请求间隔
