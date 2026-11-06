# 贡献与迭代约定

这个工程长期没有 git 历史，改动靠文档追溯。提交前请遵守以下约定。

## 1. 每次迭代必须维护的文档

1. `docs/更新日志.md`：**在顶部新增一节**，按文件末尾的条目模板写，只写实际发生的改动。
   至少包含：类型、产物（字节 / 时间 / 版本 / `--selftest` 结果）、改动文件与函数、
   验证结果、已知风险 / 未做。
2. `CHANGELOG.md`：重大版本同步更新摘要。
3. `docs/AGENT_HANDOVER.md`：架构或历史坑有变化时，更新第 4 节（新增 `4.x`）与第 5 节代码地图。

## 2. 版本号

- 格式 `YY.MM.DD.HHMM`，取**打包时刻**。
- 必须同时更新 `start_version.txt` 与 `task/tool/version_info`，并与 exe 文件属性一致。
- 打包前先备份上一版 exe 为 `dist/start-<上一版本>.exe`。

## 3. 验证顺序

```powershell
python -m compileall -q core gui task main.py start.py
python tests\run_stub_tests.py
# 确认没有正在运行的 start.exe 后：
python -m PyInstaller start.spec --clean --noconfirm
.\dist\start.exe --selftest
```

- 改动页面循环 / 内容指纹，必须补 `tests/test_page_loop.py` 断言。
- 改动签到频率 / 退出机制，必须补 `tests/test_sign_monitor.py` 断言。
- 改动日志导出，必须补 `tests/test_log_export.py` 断言。
- 3 个真实 Edge 套件需要本机匹配驱动，失败时先确认
  `Edge 版本 == msedgedriver 版本`，不要把它当成代码回归。

## 4. 绝对不要提交的内容

- `accounts.json` / `account_info.json` 及任何含真实手机号、密码、API Key、Cookie 的文件；
  仓库只提供 `*.example.json` 空模板。
- `task/run/`、`task/record/`、`task/data/`、`task/logs/` 等运行数据，
  诊断截图与图片题截图、`*.pkl` 缓存、各种 `.log`。
- `build/`、`dist/`、`*.exe`、IDE 配置、`.workbuddy-ai/` 本地记忆与预览图。

导出日志功能会对文本做脱敏（密码 / API Key 抹除、手机号只留后 4 位），
但**源配置本身仍是明文**，提交前请再检查一次 `git status`。

## 5. 不要改回去的既定决策

以下项是用户明确确认过的，见 `docs/AGENT_HANDOVER.md` 第 7.1 节：

- 视频内弹题固定随机作答，不调用 AI；
- 「答题率」= 搜到 / 点到的提交阈值，不是正确率；
- 只缓存题库命中的答案，AI 兜底答案不写缓存，也不加 TTL；
- 已完成的测验 / 考试要跳过。

## 6. 日志导出实现上的坑

- 只认**行首时间戳**：日志正文里的 URL 也可能含 `YYYY-MM-DD`。
- 无时间戳的续行（traceback、子进程输出、启动块）必须跟随上一条带日期的行。
- 账号明细日志只有 `HH:MM:SS`，按文件修改时间判断是否属于当天。
- 所有入包文本都要脱敏，不只是配置文件。

## 7. 提交信息

建议格式：`类型(范围): 简述`，例如
`fix(page-loop): 页面身份指纹加入 chapterId 避免整门课误结束`。
若改动来自真机日志排查，在信息里注明日期与日志证据。
