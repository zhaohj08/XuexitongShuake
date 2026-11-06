# 逐文件差异明细（自动生成）

上游文本文件行数 ≈ 37152；本地 ≈ 44502（含本地独有文档/测试）


## A. 同名但内容不同的 28 个文件

| 文件 | 上游→本地行数 | 相似度 | 本地新增函数/类（节选） | 依据（交接 / 版本） |
|---|---:|---:|---|---|
| `main.py` | 681→1757 | 0.384 | _click_course_tab, _click_text_keyword, _close_course_tab, _collect_course_cards, _content_signature… | 0. TL;DR 当前状态, 1. 项目速览, 3.1, 3.5 / 26.11.05.1911, 26.11.05.1832, 26.11.05.1726, 26.10.31.2253 |
| `task/quiz_ai.py` | 416→1333 | 0.313 | _as_answer_list, _ask_image_question, _ask_one, _can_answer_by_options, _click_option… | 1. 项目速览, 3.1, 4.2, 4.7 / 26.10.31.1844, 26.10.31.1817, 26.10.31.1644 |
| `start.py` | 775→1094 | 0.541 | _account_label, _box_height, _ensure_log_box, _format_runtime_status, _on_account_finish… | 0. TL;DR 当前状态, 1. 项目速览, 2. 运行方式与数据位置, 3.4 / 26.11.05.1911, 26.11.05.1832, 26.11.05.1726, 26.10.31.2313 |
| `core/config_manager.py` | 98→382 | 0.163 | _blank_account, _migrate_legacy, _read_json, _write_json, accounts_path… | 3.7 / — |
| `gui/setting_panel.py` | 551→676 | 0.787 | _add_account, _collect_form, _persist_form, _remove_account, _reset_form… | 3.7, 4.8, 5. 代码地图（当前 age / — |
| `gui/sign_window.py` | 138→281 | 0.444 | _build_parser, _check_all, _label, _log, _log_now… | 0. TL;DR 当前状态, 1. 项目速览, 7. 已知未修问题（按优先级 / 26.11.05.1832 |
| `task/watch_vido.py` | 363→320 | 0.817 | — | 1. 项目速览, 3.7, 4.7, 4.8 / — |
| `task/tool/common.py` | 109→151 | 0.685 | save_diagnostic_screenshot | 4.10, 4.23, 5. 代码地图（当前 age / 26.10.31.1711 |
| `task/tool/Help.txt` | 65→70 | 0.4 | — | 5. 代码地图（当前 age / — |
| `gui/user_notice.py` | 79→85 | 0.537 | — | 5. 代码地图（当前 age / — |
| `task/do_work.py` | 127→157 | 0.754 | _register_unanswerable | 1. 项目速览, 3.1, 4.2, 5. 代码地图（当前 age / — |
| `task/tool/no_secret.py` | 134→144 | 0.755 | — | 1. 项目速览, 4.2, 5. 代码地图（当前 age / — |
| `gui/update_checker.py` | 248→269 | 0.87 | _is_latest, parse_version | 4.8, 5. 代码地图（当前 age / — |
| `task/tool/DeepSeekAsk.py` | 67→126 | 0.674 | DeepSeekAskImage, _image_mime | 1. 项目速览, 3.2, 4.10, 5. 代码地图（当前 age / — |
| `gui/sponsor_panel.py` | 81→89 | 0.741 | — | — / — |
| `task/xxt/monitor.py` | 110→132 | 0.86 | — | 4.31, 5. 代码地图（当前 age / 26.11.05.1832 |
| `task/tool/ai_wen_da.py` | 740→757 | 0.978 | — | 1. 项目速览, 4.9, 5. 代码地图（当前 age / — |
| `task/tool/send_wx.py` | 22→34 | 0.5 | — | 4.4, 5. 代码地图（当前 age / — |
| `task/tool/face.py` | 603→605 | 0.982 | ChaoxingFaceHelper | 1. 项目速览, 4.4, 5. 代码地图（当前 age / — |
| `gui/tooltip.py` | 30→37 | 0.716 | — | — / — |
| `task/xxt/constants.py` | 51→57 | 0.87 | — | 4.31 / 26.11.05.1832 |
| `task/xxt/storage.py` | 176→182 | 0.966 | — | 4.4, 4.29, 5. 代码地图（当前 age / 26.11.05.1832, 26.10.31.2313 |
| `requirements.txt` | 11→16 | 0.667 | — | 3.1, 3.5, 5. 代码地图（当前 age / — |
| `gui/timer_window.py` | 65→65 | 0.969 | — | — / — |
| `task/tool/version_info` | 1→1 | 0.0 | — | 0. TL;DR 当前状态, 4.8, 4.11, 4.14 / 26.11.05.1911, 26.11.05.1832, 26.11.05.1726 |
| `task/xxt/__init__.py` | 3→3 | 0.667 | — | — / — |
| `task/tool/course_name.json` | 1→1 | 1.0 | — | 3.1, 4.18 / 26.10.31.1558 |
| `task/tool/course_process.json` | 1→1 | 1.0 | — | — / — |

## B. 仅本地有的 15 个文件

| 文件 | 行数 | 顶层函数/类（节选） | 依据 |
|---|---:|---|---|
| `AGENT_HANDOVER.md` | 1200 | 顺序 | — / (开头) |
| `AGENT_ONBOARDING_PROMPT.md` | 132 | — | (开头) / — |
| `core/applog.py` | 140 | _log, _rotate, _stamp, _write, child, error | 4.17, 5. 代码地图（当前 age, 6. 测试与验证 / 26.10.31.1537 |
| `core/browser.py` | 126 | _send_key, keep_awake, press_combo, press_escape, press_key, scroll_page | 3.7, 4.2, 5. 代码地图（当前 age / — |
| `core/driver.py` | 300 | _download_bytes, _exe, _extract_driver, _is_windows, _major, _reg_value | 4.5, 5. 代码地图（当前 age / — |
| `core/log_export.py` | 523 | _app_version, _build_full_log, _build_readme, _collect, _extract_day, _file_day | 4.32, 5. 代码地图（当前 age / 26.11.05.1911 |
| `core/paths.py` | 226 | _assets_root, _copy_tree_if_missing, _data_root, _record_dirs, account_home, app_root | 1. 项目速览, 3.7, 4.4, 5. 代码地图（当前 age / — |
| `core/runner.py` | 251 | AccountProcess, Runner, __init__, _apply_color, _command, _decode | 3.7, 4.15, 4.17 / 26.10.31.2313, 26.10.31.1558, 26.10.31.1537, 26.10.31.1250 |
| `gui/log_export_dialog.py` | 203 | LogExportDialog, __init__, _finish, _on_close, _pick_dir, _poll | 4.32, 5. 代码地图（当前 age / 26.11.05.1911 |
| `gui/theme.py` | 99 | current_name, font, legacy_colors, legacy_dict, palette, set_current | 3.4 / — |
| `start.spec` | 85 | — | 2. 运行方式与数据位置, 3.6, 3.7, 4.4 / — |
| `start_version.txt` | 28 | — | 0. TL;DR 当前状态, 4.4, 4.8, 4.11 / 26.11.05.1911, 26.11.05.1832, 26.11.05.1726 |
| `task/tool/page_compat.py` | 130 | PageCompat, __init__, disable, enable, is_enabled | 5. 代码地图（当前 age / — |
| `task/tool/quota.py` | 142 | ApiQuota, __init__, _warn, acquire, allow, question_key | 4.24, 4.25, 4.26, 4.27 / 26.10.31.2219, 26.10.31.1844, 26.10.31.1817, 26.10.31.1741 |
| `更新日志.md` | 1015 | — | (开头), 4.17, 5. 代码地图（当前 age / — |

## C. 仅上游有的文件

- `README.md`
- `task/tool/disable_monitor.py`

## D. 字节级一致的 42 个文件（按目录分组）

- **(根目录)**（1）：`LICENSE`
- **task**（41）：`task/__init__.py`, `task/finish_dicussion.py`, `task/img/add.png`, `task/img/error.png`, `task/img/find.png`, `task/img/fold.png`, `task/img/give_money.png`, `task/img/help.png`, `task/img/helping.png`, `task/img/home_dark.png`, `task/img/menu.png`, `task/img/money.jpg`, `task/img/money.png`, `task/img/money_img.png`, `task/img/open.png`, `task/img/score.png`, `task/img/set.png`, `task/img/show.png`, `task/img/vido.png`, `task/img/xuexitong1 .ico`, `task/play_audio.py`, `task/reading.py`, `task/tool/Match.py`, `task/tool/__init__.py`, `task/tool/chrome-extension.crx`, `task/tool/color.py`, `task/tool/face_url.json`, `task/tool/file.py`, `task/tool/font_dict.txt`, `task/tool/getanswer.py`, `task/tool/speed.crx`, `task/tool/zyb-227372.crx`, `task/watch_live.py`, `task/watch_ppt.py`, `task/xxt/activity.py`, `task/xxt/client.py`, `task/xxt/courses.py`, `task/xxt/crypto.py`, `task/xxt/geocode.py`, `task/xxt/login.py`, `task/xxt/sign.py`

## E. 更新日志版本节索引

| 版本 | 主题 |
|---|---|
| 26.11.05.1911 | 新增：界面「导出完整日志」（单日 / 单文件 / 全数据）；验证；已知风险 / 未做 |
| 26.11.05.1832 | 修复 A：自动签到每 2 秒全量轮询（用户账号被封的根因）；修复 B：复查「课程被结束」修复（用户特别要求再查一遍）；验证；已知风险 / 未做 |
| 26.11.05.1726 | 现象；根因；改动（`main.py`，只动这一处逻辑）；验证 |
| 26.10.31.2313 | 修复：自动签到只签一个账号、没法选账号；修复：调完并发数不知道哪几个账号在跑；已知风险 |
| 26.10.31.2253 | 修复：卡在「被打回的课程空壳页」里空转；已知风险 |
| 26.10.31.2219 | 变更：去掉「本轮最多 100 次」的总量上限，改为按频率限流；已知风险 |
| 26.10.31.1844 | 修复：计算题里也有 `<li>`，导致"有选项"判断失灵；已知风险 |
| 26.10.31.1817 | 修复：计算题被当成图片题送多模态，仍然在烧额度；已知风险 |
| 26.10.31.1741 | 修复：简答题疯狂消耗 API 额度；已知风险 |
| 26.10.31.1711 | 改动：认不出的页面不再反复刷新，改为「截图 + 直接下一节」；新增：任何错误都留一张诊断截图；验证；已知风险 |
| 26.10.31.1659 | 修复：点开任务点后「该页面无法识别」，3 次就结束整门课；已知风险 |
| 26.10.31.1644 | 修复：题干是「文字+公式图片」时没走图像 API，答案全错；修复：自动重做测验时崩溃 `expected string or bytes-like object, got 'float'`；验证；已知风险 |
| 26.10.31.1618 | 修复：「我学的课」点到的是 `<li>`，点它没有任何反应；已知风险 |
| 26.10.31.1608 | 修复：「我学的课」点了但页面没跳（还会谎报已进入）；已知风险 |
| 26.10.31.1558 | 修复：课程列表找不到课程（「我学的课」点不进）；修复：程序日志里每行重复两遍；验证；已知风险 |
| 26.10.31.1537 | 新增：程序运行日志（单独文件，从启动开始）；修复：主窗口不能调整大小；修复：关闭窗口后子进程残留；新增：本文件《更新日志》 |
| 26.10.31.1526 | 修复：登录后进课程列表找不到课程 |
| 26.10.31.1250 | 修复：翻页判据（原来的「三态」会误判）；新增：诊断输出；新增：子进程输出落盘；验证 |
| 26.10.31.1228 | 修复：日志显示「❌ 浏览器启动失败: (No symbol) [0x...]」其实是页面问题；修复：章节测验被跳过（四个拦截点） |
| 26.10.30.2256 | 新增：图片题多模态作答；变更：考试/章节测验不再要求「任务点」；修复：卡页循环；变更：视频题固定随机作答 |
| 26.10.30.2125 | 新增：<标题>；验证；已知风险 / 未做 |
