# AGENT_HANDOVER — 课程学习助手

> 目的：把「工程现状 / 三任 agent 做过什么 / 为什么这么做 / 还有哪些坑」一次写清楚，新 agent 读完即可接手。
>
> 最后更新：2026-10-31 15:40（第三任 agent：GUI 可缩放 + 程序运行日志 + 更新日志机制，打包 26.10.31.1537）
> 原始流水账：`.workbuddy-ai/memory/2026-10-25.md`（按事件追加，更细）
> **每次迭代的改动清单：`更新日志.md`（必须维护）**
> 第三位接手者的提示词：`AGENT_ONBOARDING_PROMPT.md`
> **Linux 服务器部署已放弃，不再考虑。**

---

## 0. TL;DR 当前状态

- Windows 桌面程序：`customtkinter` 界面（`start.py`）+ Selenium 课程学习内核（`main.py` + `task/*`）+ 签到子系统（`gui/sign_window.py` + `task/xxt/*`）。
- 可用：多账号并发、7 套主题皮肤、单文件分发、**图片题多模态作答**、题目元素失效重定位、
  浏览器驱动多级兜底、旧数据自动迁移、测验/考试不依赖任务点、卡页自动推进。
- 当前产物：`dist/start.exe`（单文件，版本 **26.10.31.2313**，63,521,549 字节，2026-10-31 23:16:11）；
  备份 `start-26.10.31.2253.exe` / `start-26.10.31.2219.exe` / `start-26.10.31.1844.exe` /
  `start-26.10.31.1817.exe` / `start-26.10.31.1741.exe` / `start-26.10.31.1711.exe` /
  `start-26.10.31.1659.exe` / `start-26.10.31.1644.exe` / `start-26.10.31.1618.exe` /
  `start-26.10.31.1608.exe` / `start-26.10.31.1558.exe` / `start-26.10.31.1537.exe` /
  `start-26.10.31.1526.exe` / `start-26.10.31.1250.exe` / `start-26.10.31.1228.exe` /
  `start-26.10.30.2256.exe` / `start-26.10.30.2125.exe`。
- 运行期数据：`%LOCALAPPDATA%\XuexitongShuake`（源码模式回落到项目 `task/`）；
  **主日志** `logs/程序日志.log`（启动信息+界面操作+全部子进程输出），
  单账号明细 `run/<账号>/运行日志.log`。
- 源码全量编译 0 错；十一个测试套件全绿：图片题 28、测验选择器 5、取答案链路 24、图片题逻辑 22、
  图片点击 13（真实 Edge）、翻页/日志 20、测验跳过 20、课程入口 11、程序日志 19、视频题 18、
  版本比较 9；打包版 `--selftest` RESULT=PASS，GUI 启动冒烟通过（标题 `课程学习助手 26.10.31.1537`）。
- 版本号：**26.10.31.2313**（`task/tool/version_info` 与 `start_version.txt` 已同步）。
- 未做：作业多课程、直播时长、签到首跑、明文密码（见第 7 节）。
- 工程**没有 git**，改动直接落盘，靠本文件 + memory 追溯。

---

## 1. 项目速览

```
start.py（界面，唯一入口）
  ├─ ConfigManager            accounts.json（global + accounts[]）
  ├─ Runner（core/runner）     每个账号一个子进程：sys.executable --core（打包后）/ main.py（源码）
  └─ 界面页面                  主页 / 设置 / 帮助 / 学习记录 / 测试成绩 / 题库查询 / 报错日志 / 赞助作者

子进程 main.py
  ├─ login_study             账号密码登录，Cookie 复用与缓存（task/tool/face.py）
  ├─ choice_course / find_mission   进入课程与章节
  └─ run() 循环：page_message() 识别内容类型 → dispatch_page()
       ├─ 视频   task/watch_vido.py
       ├─ 课件   task/watch_ppt.py
       ├─ 直播   task/watch_live.py
       ├─ 音频   task/play_audio.py
       ├─ 讨论   task/finish_dicussion.py
       ├─ 阅读   task/reading.py
       ├─ 测验   task/quiz_ai.py（Answer / Quiz）
       └─ 作业   task/do_work.py（继承 Answer）

答题链路
  DecodeSecret（task/tool/no_secret.py，字体解析）
  题库多源并发 + 本地缓存（task/tool/ai_wen_da.py）→ DeepSeek 兜底（DeepSeekAsk.py）
  → 选项匹配 → 点击 → 保存/提交

签到子系统（纯 requests，跑在主进程里）
  gui/sign_window.py → task/xxt/{login,client,courses,activity,sign,geocode,storage,crypto,monitor}
  支持普通签到与位置签到（位置坐标用爬山法修正）
```

要点：

- 学习内核（`main.py` 的导入链）**不依赖 tkinter/customtkinter**，可以无界面运行；界面只在 `start.py` / `gui/*`。
- 一个账号一个进程，数据用环境变量 `XXT_HOME` 隔离（`core/paths.py`）。
- 所有路径都走 `core/paths.py`，不要再手写 `task/...` 相对字符串。

---

## 2. 运行方式与数据位置

### 源码运行

```powershell
cd "E:\xuexi\Xuexitong_shuake-master (1)\Xuexitong_shuake-master"
C:\Python315\python.exe start.py
```

- 必须用系统 Python 3.15.1（托管 Python 3.13 没装 customtkinter）。
- 必须在项目根目录执行。
- 数据目录 = 项目 `task/`（开发/测试不受打包版数据目录影响）。

### 单文件 exe

```powershell
C:\Python315\python.exe -m PyInstaller start.spec --clean --noconfirm
```

- 双击即可；**不在 exe 旁边产生文件**，可放只读目录。
- 数据目录：`%LOCALAPPDATA%\XuexitongShuake`
  - `tool/accounts.json`、`tool/cookies.pkl`、`record/`（学习记录、图片题截图）、
    `run/<账号id>/`、`输出记录.log`、`error.log`、`selftest.log`、`drivers/`（可选，离线驱动）。
- 首次运行若 exe 同级有旧版 `task/`，会把 `tool/record/run/data` 与日志复制到数据目录，
  并写 `.migrated` 标记；原目录不动。
- 自检：`start.exe --selftest`，结果在 `<数据目录>\selftest.log`。
- 未签名，首次运行 SmartScreen 可能提示；安全软件可能误报，需加白名单。

### 本机环境（事实）

| 项 | 值 |
|---|---|
| OS | Windows 11 (10.0.26300) |
| Python | `C:\Python315\python.exe` → 3.15.1 |
| customtkinter | 6.0.0 |
| selenium | 4.51.0 |
| PyInstaller | 6.22.3 |
| numpy | 2.5.4 |
| 浏览器 | Edge 156.0.4314.42（未安装 Chrome） |
| 驱动缓存 | `C:\Users\popca\.cache\selenium\msedgedriver\win64\156.0.4314.42\` |
| 工作区 | `E:\xuexi\Xuexitong_shuake-master (1)\Xuexitong_shuake-master`（路径含空格/括号，命令要加引号） |

---

## 3. 第一任 agent（workbuddy）做了什么

> 时间：2026-10-25 白天，版本基线 26.10.13。以下内容来自 `memory/2026-10-25.md`，已核实与代码一致。

### 3.1 工程解析与缺陷清单

- 通读约 5900 行、43 个 `.py`，确认「学习子系统 + 签到子系统」双架构。
- 列出主要缺陷：`requirements.txt` 缺 numpy/pycryptodome；`main.py` 两处 URL/XPath 错误；
  `do_work.py` 异常分支引用未定义属性；`quiz_ai.py` 使用 `eval()`；
  `set_speed` 的全局开关只生效一次；`course_name.json` 含真实手机号。

### 3.2 答题链路专项

- 定位 DeepSeek 调用出口（`task/tool/DeepSeekAsk.py`）与四个调用点，梳理出批量答案按位置回填、
  多源答案未投票、判断题子串误判、视频题随机答案覆盖 AI、答题率语义偏差、
  答案缓存无有效期等问题（部分至今未修，见第 7 节）。

### 3.3 固定模型

- 去掉模型随机选择，固定为 `MODEL = 'deepseek-v4-flash'`，删除无用 `import random`。

### 3.4 界面视觉层重构（低风险皮肤层）

- 新增 `gui/theme.py`：7 套语义色板 + 间距/圆角/字体常量 + `palette()/legacy_colors()/font()`。
- `start.py`：接入主题；去掉硬编码颜色；导航选中态改为浅底 + 主色文字；文本框统一描边；
  窗口自适应尺寸后居中；日志框高度按屏幕自适应；内容区加权重填满。
- 修启动即崩：`anchor="ns"` 在 customtkinter 6.0 下非法。
- 设置页放进 `CTkScrollableFrame`，小屏不截断；两列卡片撑满宽度。
- 赞助面板、提示气泡、用户须知、定时窗口、签到窗口、更新弹窗全部去硬编码颜色。
- 用系统 Python 3.15 + ctk 6.0 验证 7 主题 × 8 页面，截图存 `.workbuddy-ai/preview/`。

### 3.5 让工程可运行

- `requirements.txt` 补 `numpy`、`pycryptodome`（人脸模块顶层 import numpy；签到加密依赖 Crypto）。
- 修 `main.py` 登录页 URL 少斜杠、一个非法 XPath。
- 确认必须在项目根目录用 `C:\Python315\python.exe start.py` 启动。

### 3.6 单文件打包（第一版）

- 重写 `start.spec`：把 `task/` 作为数据打进去、`collect_all('customtkinter')`、
  `hiddenimports += ['main']`、图标、关闭 UPX、排除 pandas/matplotlib/scipy。
- `start.py` 增加 `app_dir()/ensure_data_dir()/prepare_runtime()`：打包后把资源释放到 exe 同级，
  并切换工作目录；日志路径改到程序目录。
- 打包后没有系统 Python：`file_name` 改为 `[sys.executable, '--core']`，`__main__` 增加 `--core` 分支。
- 产物约 64.6 MB，临时目录试运行正常。

### 3.7 多账号并发（计划 → 实施）

硬阻塞（已核实）：账号配置、Cookie、记录、进度都是单份；全局章节锁；按键发到前台窗口。

方案与实施：

- 数据层 `task/tool/accounts.json`：global（浏览器/驱动/API/字体/并发数/定时）+ accounts[]。
- 路径抽象 `core/paths.py`：ASSETS 只读资源、HOME 可写数据、子进程用 `XXT_HOME` 隔离。
- `core/browser.py`：按键改走 CDP（不受窗口焦点影响），防锁屏改系统 API。
- `core/runner.py`：每账号一个子进程 + 信号量限流 + 输出回调 + 进程树终止。
- `core/config_manager.py` 重写：旧 `account_info.json` 自动迁移、扁平接口兼容、运行时配置写入账号目录。
- 全工程约 20 处 `task/...` 硬编码路径改 paths。
- `main.py`：去掉 pyautogui 与 ActionChains；`set_speed` 改 CDP；未知页面重试 3 次；各类内容单独兜底。
- `task/watch_vido.py`：按键改 CDP、防锁屏改系统 API、滚动改 JS。
- `start.py`：接入 Runner；日志改为每账号一个文本框 + 顶部下拉切换；并发启动/停止。
- `gui/setting_panel.py`：账号下拉 + 新增/删除，并发数配置，切换账号静默保存。
- `start.spec`：只打资源，不打 `.py` 源码与用户数据。
- 验证：全量编译、界面冒烟（7 主题 × 8 页面、账号增删切换）、Runner 假命令并发、运行时配置生成。

### 3.8 打包与启动问题系列

1. 打包后启动浏览器即失败：缺 `selenium.webdriver.edge.webdriver` → `collect_submodules('selenium')`。
2. 报错日志不生成：`logging.basicConfig` 二次调用失效 → `send_error` 直接追加写文件，界面读同一路径。
3. `AttributeError: 'str' object has no attribute 'press_combo'`：形参 `browser` 遮蔽模块 → 改 `browser_ext`。
4. 登录后答题 `no such element`：答题前缓存的 WebElement 在 AI 等待期间失效 → `_relocate()` 重新定位 +
   `_click_option()` 失败重试；作业页与测验页选择器分别登记。
5. 图片题：实测模型不接受图片输入，本机也无 OCR → 识别图片题并跳过，整块截图存
   `record/图片题/`，同时保证题目相关结构按题号对齐。

### 3.9 交接时状态与遗留

- 16:30 真机测试：两个账号跑通（一个账号完成 1 个视频并写记录，另一个账号缓存了 4 道单选答案）；
  16:34 用户手动关闭。
- 遗留：批量答案回填、`eval()`、真实手机号、版本号、旧 `dist/task` 残留等（见第 7 节）。

---

## 4. 第二任 agent（当前）做了什么

### 4.1 接手与环境修复

- 接手时所有命令失败：`SetNamedSecurityInfoW failed (Win32 5): grantWrite(工作区)`。
  用 ACL 诊断工具修工作区根目录（缺 WRITE_OWNER），补当前用户 FullControl。
- 随后发现受限进程是 Low 完整性，工作区子目录是 Medium → 子目录写不进。
  当时把整个工程标成 Low（**后来证明是错的**，见 4.3）。
- 全量核查：源码内存编译 0 错；依赖可用；界面 8 页面切换正常；确认 exe 与源码一致。

### 4.2 修复：图片题全屏遮罩与元素失效

用户反馈「题目是图片时，图片会全屏显示，然后程序不动了」。

根因：图片选项里有 `<img>`，Selenium 原生点击落在图片上，页面弹出全屏预览遮罩，
遮罩吃掉后续所有点击；另有两种变体：点到图片链接后内容帧被导航成图片；
查询答案期间 iframe 重新加载导致元素句柄全部失效。
还有一个独立崩溃：保存/提交按钮在模块页而不是题目帧里。

改动：

- `task/quiz_ai.py`
  - 新增遮罩检测与关闭：Esc（CDP）+ 移除已知全屏容器与「fixed + 铺满 + 含图片」的浮层，
    跳过人脸/弹窗类容器。
  - 图片选项改 JS 点击 `<li>`（事件目标是 li，不会命中图片的点击处理），点完兜底收遮罩；
    被遮罩拦截时先收遮罩、重定位、再试。
  - 新增上下文进入：每道题作答前从顶层重新走「外层帧 → 模块帧 → 题目帧」，
    模块帧失效按选择器重找，题目帧名称变化按「能否读到题目」兜底。
  - 内容帧被导航成图片时，按当前地址或帧地址判定并后退。
  - 题目解析兼容图片题干/图片选项；截图留存；填空/简答等结构按题号对齐。
  - 保存/提交按钮跨帧查找；「仅自动保存」分支补失败兜底；答题率除零保护。
- `main.py`：每轮先检测并关闭图片遮罩；章节标记改为中性文案并兼容旧记录。
- `task/do_work.py`：作业页使用窗口上下文；未识别题型改为占位登记后跳过（避免题号错位）；
  修异常分支引用未定义属性；无答案集合排除图片题。
- `task/tool/no_secret.py`：字体解析临时文件改为唯一文件名 + 及时清理（多账号并发会互相覆盖）。
- `core/browser.py`：新增 `press_escape()`（CDP）。

验证：新增 `.workbuddy-ai/tests/test_quiz_image.py`，用真实 Edge 驱动本地仿真页
（多层 iframe、图片点击弹遮罩、iframe 重新加载、帧内导航到图片），28 项断言全过。

### 4.3 事故与修复：双击 exe 报「Could not create temporary directory!」

- 真因是 4.1 的处置：整棵工程被标成 Low 完整性后，Windows 会按可执行文件自身的标签决定进程级别，
  exe 以 Low 运行，无法在 `%TEMP%`（Medium）创建单文件解压目录。
- 判据：同一份 exe 复制到 `%TEMP%` 能启动，留在工程内 0 进程立即失败；`icacls` 可见 Low 标签。
- 修复：全工程恢复 Medium；验证 exe 双击可启动、解压目录正常生成。
- 教训：不要为了沙箱写入把工程目录整体降级；必须降时只降非可执行的数据目录。

### 4.4 单文件深度封装

- `core/paths.py` 重写：
  - ASSETS：打包版 = `sys._MEIPASS/task`（只读、退出即删）；源码版 = 项目 `task/`。
  - DATA_ROOT：打包版 = `%LOCALAPPDATA%\XuexitongShuake`；源码版 = 项目 `task/`；支持 `XXT_DATA` 覆盖。
  - HOME = `XXT_HOME` 或 DATA_ROOT；账号目录 = `DATA_ROOT/run/<id>`。
  - 新增 `root_data()`、`data_or_asset()`、`prepare()`、`migrate_portable_install()`。
- `start.py`：去掉「把资源解压到 exe 旁边」；日志与报错页改数据目录；新增 `--selftest`
  （导入 54 个模块 + 校验 9 个资源，结果写数据目录，退出码表示成败）。
- `send_wx.py`、`face.py`、`task/xxt/storage.py` 的写盘点全部迁到数据目录。
- `start.spec` 增加文件版本资源；`start_version.txt` 提供版本信息。
- 验证：纯净目录自检 PASS、界面启动、旧数据自动迁移、`--core` 子进程路径完整。

### 4.5 修复：新电脑首次运行 `NoSuchDriverException`

- 根因：新电脑没有驱动缓存，Selenium Manager 需要联网下载；国内网络、缺代理、
  或浏览器刚更新时失败。单文件 exe 在别的机器上第一次运行必踩。
- 新增 `core/driver.py`：
  - 探测本机浏览器版本（Windows 读注册表 BLBeacon 与更新器客户端信息；Linux 读 `--version`）。
  - 候选顺序：配置路径 → exe 同级 `drivers/` → 数据目录 `drivers/` → Selenium 缓存（按大版本匹配）。
  - 自动下载：Edge 走微软官方 CDN，Chrome 走 Chrome for Testing；解压到数据目录并直接使用。
  - 失败时输出中文、可照做的说明（下载页、drivers 目录、设置驱动地址、换浏览器）。
- `main.start_browser()`：先本地解析；只有抛 `NoSuchDriverException` 才下载重试；仍失败抛带提示的异常。
- 验证：缓存驱动启动 headless Edge 成功；模拟「离线 + 空缓存」自动下载成功；
  打包版自检能识别 exe 同级 `drivers/`。

### 4.6 记录与配置兼容

- 启动时把历史记录文件名统一为「学习记录」、章节标记同步改写（`paths.migrate_legacy_names()`）。
- 旧记录名与旧配置值在代码里用转义常量兼容，老用户数据不需要手工处理。

### 4.7 修复：题库搜索 main() 参数错误 + 视频被暂停跳过（20:10–20:25）

- 用户运行日志报 `第N题搜索失败：main() takes 4 positional arguments but 5 were given`，且视频经常出现
  "视频处理出错: 视频播放异常"后跳页（只看一半/跳过）。
- 修复 1（`task/quiz_ai.py` 330/339 行）：`ai_wen_da.main(...)` 调用多传了 `self.driver`（5 参 vs 定义 4 参），
  导致每次题库搜索必抛 TypeError、全部走 DeepSeek 兜底。删掉多余参数即可。
- 修复 2（`task/watch_vido.py` `check_vido_play`）：① 恢复播放先 JS `video.play()` 再点按钮兜底，
  播放按钮选择器从精确 `[class="..."]` 放宽为 `class*=` 包含匹配；② 放弃阈值从 `b==3`（约 3–6 秒就 raise）
  放宽到 `b>=8`（约 16 秒以上），期间持续恢复；③ `b==6` 且倍速>=2 时先降倍速再试。
- 测试基建：`test_quiz_image.py` 不再裸用 `webdriver.Edge()`（Selenium Manager 联网解析易 NoSuchDriverException），
  复用 `core.driver.resolve('edge')` 显式传入 `Service`。
- 验证：`compileall` 0 错；回归 28 项 ALL PASS。**20:23 已重新打包** `dist/start.exe`
  （63,466,507 字节），`--selftest` RESULT=PASS。

### 4.8 视频题固定随机作答 + 版本号同步（21:10–21:28，第三任 agent）

用户口径（**这是产品决策，不要再按「缺陷」去改**）：

- 视频播放中弹出的题目**就是随机作答**的，不要调用 AI：平台对视频题没有错题校验，
  选错只会提示，继续选下一个选项总能试到正确。
- 答题率统计没问题：它统计的是「搜索到几道题 / 点了几道题」，达到阈值就提交，
  不是正确率。界面「搜到 N% 自动提交」的语义是对的。

改动：

1. `task/watch_vido.py`
   - 删除 `get_answer()`、`finish_video_question()` 与 `check_video_question()` 里的 AI 分支
     （原来 AI 提交后仍会继续跑随机分支，把答案覆盖掉）；同时删掉 `DeepSeekAsk` / `ast` / `random` 导入。
   - `check_video_question(driver)` 只保留随机穷举：单选/判断题逐个选项点一次并提交，
     多选题按「全选 + 两两组合」穷举，每次只点与上一次的对称差集；每次提交后 `time.sleep(0.5)`，
     给平台留出弹「答错」提示的时间。
   - 连带收敛签名：`study_page(driver, course_name, lock_screen, pass_vido, speed, pass_face)`、
     `check_vido_finish(..., lock_screen, speed, pass_face)` 不再接收 `API` / `video_title_choice`；
     `main.dispatch_page` 的调用同步更新（`run()`/`main()` 里的配置参数保留，不影响旧配置）。
2. `gui/setting_panel.py`
   - 「视频题目」由下拉选择改成固定值 `随机答题`（readonly + 单选项 + ToolTip 说明），
     旧配置里的 `DeepSeek AI` 在 `load_data()` 里一律 coerce 成 `随机答题`；
     `_reset_form()` 也会还原该值，否则保存校验会报「请完成视频题目设置」。
   - `shua_ti_choice()` 去掉已无意义的「视频题目用 DeepSeek」提示，API 显隐只由章节测验/讨论决定。
3. 版本号（用户要求：按实际日期和时间）
   - `task/tool/version_info` → `26.10.30.2125`；`start_version.txt` → `filevers/prodvers(26,10,30,2125)`
     与 `FileVersion/ProductVersion` 同步。
   - `gui/update_checker.py`：新增 `parse_version()` + `UpdateChecker._is_latest()`，按
     「年.月.日.构建号」数值比较，本地版本比发布包新时不再误报「有新版本」；
     只有确实存在新版本才弹窗（原来「已是最新」也会把窗口开出来再立刻销毁，表现为闪一下）。
     解析不出时退回原来的子串判断。
4. 新增回归测试
   - `.workbuddy-ai/tests/test_video_question.py`（纯桩、无浏览器，18 项断言）：
     断言 AI 分支已删除、签名收敛、单选/判断/多选的点击与提交次数、提交后留白、无弹题时不误点。
   - `.workbuddy-ai/tests/test_update_version.py`（9 项断言）：版本解析与「本地新/发布包新/解析不出」三种比较。

验证：

- `compileall` 0 错；`test_quiz_image.py` 28 项 ALL PASS；`test_video_question.py` ALL PASS；
  `test_update_version.py` ALL PASS。
- GUI 冒烟：8 页面切换 OK；设置页 `视频题目` 取值为 `随机答题`，`_collect_form()` 落盘
  `video_title_choice='随机答题'`；空表单校验仍报「请填写手机号」，填齐必填项后校验通过
  （证明视频题不会成为保存阻塞）。
- **21:27:55 重新打包** `dist/start.exe`（63,464,258 字节），文件属性
  `课程学习助手 / 26.10.30.2125`，`--selftest` RESULT=PASS。

### 4.9 第 0/1 批修复：测验页识别去硬编码 + 取答案链路加固（21:40–22:05，第三任 agent）

用户授权范围：只做「第 0 批 + 第 1 批」，其余（作业多课程、关窗残留、签到首跑等）**未动**。
用户口径：视频题保持随机穷举；缓存策略选 **(b) 只缓存题库结果、AI 答案不缓存**。

1. **A7 测验页识别去硬编码（`main.py:349`、`task/quiz_ai.py:789`）**
   - 旧写法精确匹配整条 `src`（含平台构建号 `?v=2025-1028-1629`），平台一发版就认不出测验页、
     整章测验被静默跳过。
   - 改为 `iframe[src^="/ananas/modules/work/index.html"]` 前缀匹配（`By.CSS_SELECTOR`）。
2. **A1 批量答案加段数校验（`quiz_ai.Answer.use_deepseek`）**
   - 旧写法 `re.split('/', answers)` 后按下标回填：少一段 `parts[num]` 越界（后面全不答），
     多一段静默错位（第 N 题答案填给第 N+1 题，日志完全正常）。
   - 现在：`_split_batch_answer()` 校验段数；只容忍「末尾多一个 `/`」；单题时整段即答案；
     其余数量不符 → 打印提示并**逐题提问**（`_ask_one`），不再猜位置。
3. **A2 `eval()` 换成字面量解析（`quiz_ai._as_answer_list`）**
   - 新增模块级 `_as_answer_list()`：`ast.literal_eval` 优先；失败只做纯文本切分（不执行任何东西）；
     解析不出按「无答案」交给下一级兜底。`use_ai_wen_da` 走 `_search_bank()`，删掉两处 `eval()`。
4. **A3 缓存只存题库结果（`task/tool/ai_wen_da.py`）**
   - `AnswerResult` 新增 `cacheable: bool = True`；`AutoAnswer.use_deepseek()` 返回
     `cacheable=False`；`auto_answer_question()` 写缓存前过滤 `cacheable`。
   - `quiz_ai.use_deepseek()` 里原来「AI 答案写缓存」的代码删除（`AnswerAPI`/`Question` 不再导入）。
   - 效果：AI 猜错一次不会被永久固化；题库命中依旧写缓存（二次遇到仍然秒出）。
5. 新增回归测试
   - `.workbuddy-ai/tests/test_quiz_answer_backfill.py`（24 项断言）：字面量解析 / 恶意字符串不执行 /
     段数校验 / 少数与多数都改走逐题 / 单题不多问一次 / 题库答案写缓存而 AI 答案不写。
   - `.workbuddy-ai/tests/test_quiz_selector.py`（5 项断言，真实 Edge）：用「未来构建号」的 iframe
     验证新选择器能命中、旧精确选择器命中不了，并检查 `main.py` 已无旧版本号。

验证：

- `compileall` 0 错；`task/quiz_ai.py` 内已无 `eval(`。
- 五个测试全绿：`test_quiz_image`（28）、`test_quiz_answer_backfill`（24）、`test_quiz_selector`（5）、
  `test_video_question`（18）、`test_update_version`（9）。
- GUI + `import main` 冒烟 OK，窗口标题仍是 `课程学习助手 26.10.30.2125`。
- **未重新打包**：`dist/start.exe` 仍是 21:27 那版，不含本次 4.9 的改动；下一次打包要同步升版本号。

### 4.10 图片题多模态作答 + 考试不再要求任务点 + 卡页循环修复（22:00–22:45，第三任 agent）

> 用户授权范围：图片题走多模态、考试也做、`find_mission` 无任务点时按 **方案 A**（从头扫描）、
> 允许一次真实 API 验证。以下改动均已落地。

**更正一条错误结论（重要）**：`.workbuddy-ai/memory/2026-10-25.md:135` 曾记录
「v4-flash/pro 接受 image_url 但返回空字符串，接口不支持视觉」。本次用**合成图片**实测：
`deepseek-v4-flash` 图片输入可用，单选题返回 `'B'`、多选题返回 `'BD'`。
以后不要再引用那条旧结论。验证脚本：`.workbuddy-ai/tests/manual_vision_probe.py`（手工运行，不入自动测试）。

1. **图片题：截图 → 多模态 → 点选项**（`task/tool/DeepSeekAsk.py`、`task/quiz_ai.py`）
   - 新增 `DeepSeekAskImage(API_KEY, prompt, image_paths)`：base64 data URL + OpenAI 兼容
     `image_url`，模型仍是 `MODEL = 'deepseek-v4-flash'`；无 key / `sk-open_deepseek` 哨兵直接返回空
     （不联网）；异常捕获后返回空串。
   - 提示词 `_IMAGE_QUESTION_PROMPT`：**只返回字母**；单选/判断一个字母，多选多个字母，
     选项超过 4 个继续用 E、F…；完全看不到字母时按顺序返回序号。
   - `_save_image_question()` 改为返回路径，并用 `_shrink_image()` 把长边压到 1600px（控请求体大小）。
   - 新增 `_mark_image_question()`：登记图片题时同时加入 `image_unanswered`（保证「没答出来」统计准确）。
   - 新增 `_parse_choice_letters()`：字母优先、序号兜底、越界/重复丢弃、英文句子不误判。
   - 新增 `_ask_image_question()` / `_finish_image_title()`：`_relocate` 重新定位 → 截图 → 问模型
     → 按字母点选项；**选项数一律以页面 `<li>` 为准**（整题图片时 `num_option_dit` 只有 `['']` 占位，
     用它算数量会把 B/C/D 全判越界）。答不出来时：随机答题模式随机点一个，否则跳过并记录。
   - `finish_title()` 的图片题分支改为调用 `_finish_image_title()`（作业页继承 `Answer`，一并生效）。
   - 收尾提示改为「图片题：N 道已由多模态模型作答 / M 道未能作答」。
2. **点击必须落在 ABCD 上，绝不能点到图片**（`_click_option` + `_LABEL_JS`）
   - 含 `<img>` 的选项**一律 JSON 点击**；先用 JS 点选项内的字母/文字节点
     （`i/em/b/span/.num_option/.option-label/.answer_p/p`，跳过含 img 的节点），
     再校验 `aria-checked`；没选中就再点 `<li>` 容器；仍没选中只告警不误判。
   - 点完照旧 `close_image_viewer()` 兜底收遮罩。
3. **考试/测验不再要求任务点**（`task/tool/common.py`、`task/quiz_ai.Quiz`）
   - `Common.__init__` 增加 `require_mission=True`；`main()` 改为
     `if self.require_mission and not self.check_exist_mission(): continue`。
   - `Quiz` 传 `require_mission=False` → 只要页面有测验 iframe 就作答（`Answer.main()` 的
     「已完成」判断保留，已完成的仍跳过）。
4. **整章没有未完成任务点时，改为从头扫描**（`main.py` `find_mission`，方案 A）
   - 新增 `_open_first_chapter()`：依次尝试 `.catalog_tishi120` → `[class*="catalog_tishi"]` →
     `.catalog_jiedian` → `a/li[onclick*="getTeacherAjax"]` → `.catalog_name`，点开后用
     `_landed_on_study_page()` 校验是否真的进了学生学习页，确认成功才返回。
   - 原来打印「所有任务点均已完成」并 `return False` 的分支，改为先尝试从头进入；
     实在进不去才打印「章节列表也点不进去，跳过本课程」。
5. **卡在同一页无限循环的修复**（`main.py`）
   - 未知页面：`UNKNOWN_REFRESH_LIMIT = 3`，先刷新 3 次（用户要求"有时要刷新才出来"），
     第 4 次才跳过该页；刷新后仍回到同一页时由下面的翻页三态兜底。
   - `click_next_page()` 改为返回 `'advanced' / 'finished' / 'stuck'`：新增
     `_wait_page_changed()`（旧 `#iframe` 句柄失效 或 `_page_signature()` 变化才算前进），
     修掉「找不到按钮 → 只 refresh → 仍 return True」导致的假前进；成功后 `error_num = 0`。
   - `run()` 用 `stuck_count` 记连续「没前进」，达到 `STUCK_LIMIT = 2` 就结束本课程并打印原因，
     不再无限刷日志。
   - `dispatch_page` 抛异常时不再 `cond=False` 原地重跑：刷新 + 计数，超过阈值就跳过该页继续推进
     （旧逻辑这条路径**没有任何计数**，处理器每次抛同一个异常就是死循环）。
6. 测试
   - 新增 `test_image_question.py`（22 项，纯桩）：字母解析、AI 给字母就点选项、给不出时跳过/随机、
     定位失败、哨兵 key 不联网、提示词约束。
   - 新增 `test_image_answer.py`（13 项，真实 Edge）：`<li><i>A</i><img></li>` 时点击目标必须是 `I`
     节点、`<li><img></li>` 时退回 `LI`，两种情况都**不能弹全屏遮罩**、且选项确实被选中；
     同时校验截图路径真的传给了多模态接口。
   - `test_quiz_image.py` 同步两处：图片题多模态桩成「答不出」（保持不联网、验证跳过兜底），
     并把「有没有误点」的前后计数改在同一帧内统计（因为 `finish_title` 现在会重进上下文）。

验证：

- `compileall` 0 错；`import main` + GUI 8 页面冒烟 OK。
- 七个套件全绿：`test_quiz_image`(28)、`test_quiz_selector`(5)、`test_quiz_answer_backfill`(24)、
  `test_image_question`(22)、`test_image_answer`(13)、`test_video_question`(18)、`test_update_version`(9)。
- **真实接口验证**：合成单选题返回 `'B'`、合成多选题返回 `'BD'`（`manual_vision_probe.py`，用
  `accounts.json` 里的真实 key，脚本不打印 key）。
- **未重新打包**：`dist/start.exe` 仍是 21:27 那版，不含 4.9 / 4.10 的改动。

### 4.11 重新打包（22:56–23:00）

- 用户授权「检查一遍之后直接打包」。
- 版本号按打包时刻：`task/tool/version_info` 与 `start_version.txt` 同步为 **26.10.30.2256**
  （`filevers/prodvers=(26,10,30,2256)`）。
- 打包前先备份旧包：`dist/start-26.10.30.2125.exe`（63,464,258 字节，21:27 那版），
  方便回退对比。
- `python -m PyInstaller start.spec --clean --noconfirm` → `dist/start.exe`
  63,479,126 字节（比上一版 +14,868 字节，增量来自图片题/翻页逻辑的新代码），22:57:51 完成。
- 验证：
  - `dist/start.exe --selftest` → `RESULT=PASS`（55 个模块导入 + 9 个资源全 OK；
    edge 156.0.4314.50 / 驱动缓存 156.0.4314.42 命中；chrome 无属正常）。
  - 双击启动冒烟：进程存活、窗口标题 `课程学习助手 26.10.30.2256`，随后手动关闭。
  - 文件属性：`课程学习助手 / 26.10.30.2256`。

### 4.12 修复：日志里的「❌ 浏览器启动失败: (No symbol) [0x...]」（23:10–23:25）

现象（用户报）：跑起来后日志出现
`❌ 浏览器启动失败: (No symbol) [0x7ffaa625ee4c]` + 「完整堆栈已写入 error.log」。

**真相：不是浏览器启动失败。** `error.log` 里两条真实异常是：

1. `main.py find_mission` → `NoSuchElementException: li[data-nav-name='章节']`
2. 5 秒后 `turn_page` → `TypeError: argument of type 'NoneType' is not a container or iterable`
   （`driver.window_handles` 已经是 `None`，说明会话已经挂了）

三个原因叠在一起：

- `turn_page()` 只 `sleep(1)` 就去比对窗口标题；新标签页标题还没出来 → 返回 `False`，
  而 `main()` **忽略了返回值**，继续在旧页面上找 `nav_content` → 找不到 → 抛异常。
- `NoSuchElementException` 是 `WebDriverException` 的子类，被 `run_main()` 的
  `except WebDriverException` 兜住，打印成「浏览器启动失败」；`_error_brief()` 取堆栈**最后一行**，
  正好取到驱动附带的 `(No symbol) [0x...]`，于是一条页面问题被伪装成浏览器问题。
- 会话已失效时 `driver.window_handles` 返回 `None`，`for handle in None` 又抛 `TypeError`。

修复：

| 位置 | 改动 |
|---|---|
| `main.turn_page()` | 改成轮询等待（默认 20 秒，0.5 秒一查），`window_handles` 为空/会话失效时不再抛异常，只打印切换失败原因 |
| `main._wait_element()` / `_wait_elements()` | 新增，等元素出现再操作，超时返回 `None`/`[]` |
| `main.find_mission()` | 导航标签先 `_wait_elements(nav_content, 15s)`；没有 `nav_content` 时再等 `li[data-nav-name='章节/作业']`（含 `*=` 兜底）；**都找不到就打印当前页面标题并 `return False` 跳过本课程**，不再把整门课带崩 |
| `main.main()` | `turn_page` 失败只告警「暂未切换…继续等页面加载」，不直接放弃；课程结束时改用 `_close_course_tab()` |
| `main._close_course_tab()` | 只有多于一个窗口时才 `close()`，避免把最后一个窗口关掉导致会话失效 |
| `main._error_brief()` | 优先取含 `selenium.common.exceptions.` / `Error:` / `Exception:` 的那一行，跳过 `(No symbol)`、`File "`、`^` 等堆栈噪声 |
| `main.run_main()` | 新增 `except NoSuchElementException` 分支：提示「页面上找不到预期元素（不是浏览器问题）」；`WebDriverException` 的文案从「浏览器启动失败」改为「浏览器会话异常」 |

验证：`compileall` 0 错；`test_page_loop.py` 扩到 **18 项**（新增异常摘要、等元素超时、会话失效、
单窗口不关闭 6 项）并 ALL PASS；其余 7 个套件全绿；GUI 冒烟 OK。
**源码已修，尚未重新打包**（`dist/start.exe` 仍是 26.10.30.2256）。

### 4.13 修复：遇见章节测验直接跳过（10-31 12:20–12:45）

用户反馈：新包跑起来「遇见章节测验直接跳过」。现场证据：`record/cache_ques1_*.pkl` 没有新增、
没有成绩记录、`error.log` 无新条目 → **测验在进入答题（搜题）之前就被跳过了**。

四个可能「在搜题前拦掉」的点，这次全部处理：

| # | 原问题 | 修复 |
|---|---|---|
| ① | `main.page_message` 用 `iframe[src^="/ananas/..."]` 前缀匹配，平台把 src 写成绝对 URL 就认不出测验 | 改成 `iframe[src*="/ananas/modules/work/index.html"]`（包含匹配），`quiz_ai.Quiz.IFRAME_SELECTOR` 同步 |
| ② | `common.Common.main()` 里 `scrollIntoView(preceding-sibling::div[1])`：模块没有前置 div 时抛 `NoSuchElementException`，被 `safe('测验', ...)` 吞掉 = 整场跳过 | 包 try/except，取不到就不滚动；并把 `self.start()` 也包 try/except，**单场出错打印原因后继续下一场** |
| ③ | `check_audio_finished()` 用 `== 'ans-attach-ct ans-job-finished'` 精确比较，class 顺序/多空格判不出；取父元素失败还会抛异常 | 改成 `'ans-job-finished' in class` 包含匹配，父元素取不到返回 False；跳过时打印原因 |
| ④ | `Answer.main()` 读 iframe 前一个兄弟 div 的 `aria-label`，**只要含「已完成」就整场跳过**——那个 div 常常是同章节里已看完的视频任务点 | 新增 `_quiz_finished_by_status()`：只看测验自己的 `testTit_status`（已完成/已提交/已交/批阅），取不到再退到「本 iframe 父容器」标记；**不再读邻居 label** |

另外：`Quiz.start()` 的异常提示改为带具体原因（`测验处理出错，跳过本场：xxx`）；每个跳过分支都有
明确日志（`第N个测验没有任务点标记，跳过` / `该测验已完成（父容器标记 ans-job-finished），跳过` /
`测试已完成（测验状态=已完成），跳过` / `测验未标记完成（测验状态=未交），开始作答`）。

验证：`compileall` 0 错；新增 `test_quiz_skip.py`（**20 项**：无前置 div 不崩、任务点开关、
class 顺序/空格、单场异常不影响下一场、完成判定只看自己、选择器放宽）ALL PASS；
`test_quiz_selector.py` 同步改为断言 `src*=`；**9 个套件全绿**；GUI 冒烟 OK。
**源码已修，尚未重新打包**。

### 4.14 重新打包（10-31 12:28–12:35）

- 用户授权「打包」，把 4.12（导航/报错文案）+ 4.13（测验被跳过）一起打进包。
- 版本号按打包时刻：`task/tool/version_info` 与 `start_version.txt` 同步为 **26.10.31.1228**
  （`filevers/prodvers=(26,10,31,1228)`）；写入后校验过 UTF-8 无 BOM、中文未乱码。
- 打包前备份旧包：`dist/start-26.10.30.2256.exe`（63,479,126 字节），
  加上更早的 `dist/start-26.10.30.2125.exe`，共两份可回退。
- 打包前确认没有正在运行的 `start.exe`（避免文件占用）。
- `python -m PyInstaller start.spec --clean --noconfirm` → `dist/start.exe`
  **63,483,931 字节**，12:30:56 完成（比上一版 +4,805 字节）。
- 验证：
  - `dist/start.exe --selftest` → **RESULT=PASS**（55 模块 + 9 资源；edge 156.0.4314.50，
    驱动缓存 156.0.4314.42 命中）。
  - 双击启动冒烟：进程存活、窗口标题 `课程学习助手 26.10.31.1228`，随后关闭测试实例。
  - 文件属性：`课程学习助手 / 26.10.31.1228`。

### 4.15 诊断包 26.10.31.1250：为定位「章节测验被跳过」取证（12:36–12:55）

用户复现：程序在看视频 → 用户手动点「下一页」触发视频报错 → 程序也点下一页 → 用户手动切回 →
日志出现「第 1 次点击下一页没有前进」→ 停在测验页时程序无反应、直接跳过。

两个改动方向：

1. **翻页判据换成内容指纹**（4.10 的三态判据作废）
   - 旧：`#iframe` 元素失效 / URL 变化 → 平台换知识点时不重建 iframe，必然误报「没前进」，
     两次就结束整门课（`STUCK_LIMIT` 从 2 改 3）。
   - 新：`_content_signature()` = 章节标题 + 已完成任务点数 + 任务点总数 + 模块 iframe 的 src；
     连续 3 次完全一致才结束，并打印指纹摘要。
   - `click_next_page()` 只返回「点过了 / 课程到底」，不再猜有没有换页。
2. **取证能力**
   - 新增 `describe_page()`：识别不到页面时打印 `title=...; top=[iframe src...]; iframe=[...]`，
     直接看到这一页到底是什么模块。
   - `page_message()` 增加顶层文档兜底：模块不在 `#iframe` 里也能认出来。
   - `core/runner.py`：子进程输出落盘到 `run/<账号>/运行日志.log`（带 `HH:MM:SS`，超 3MB 轮转 `.old`），
     界面日志框关掉也不会丢，排查不用再让人贴日志。

验证：`compileall` 0；`test_page_loop.py` 重写为 **20 项**（指纹变化/相等、`click_next_page` 两态、
`_error_brief`、`_wait_elements`、`turn_page` 兜底、单窗口保护、日志落盘与轮转）ALL PASS；
**9 个套件全绿**；`dist/start.exe` 重建为 **26.10.31.1250**（63,486,282 字节，12:51:38），
`--selftest` PASS，GUI 冒烟 OK；旧包备份 `dist/start-26.10.31.1228.exe`。

### 4.16 课程列表入口关键字兼容 + 打包 26.10.31.1526（15:20–15:30）

用户反馈：登录后进入课程列表时，`choice_course()` 定位「我学的课」标签失败，
导致找不到任何课程卡片（他们的版本 class/文字与旧包不一致）。

原实现（`main.py`）的问题：

```python
element = driver.find_element(By.CLASS_NAME, 'course-tab')   # 写死 class
if element.text == '我学的课': element.click()               # 要求文字完全相等
```

改动：

| 位置 | 改动 |
|---|---|
| 新增 `COURSE_TAB_KEYWORDS = ('我学的课', '我的课程')` | 标签叫法集中管理 |
| 新增 `_click_text_keyword(driver, keywords, timeout, max_text)` | 按 XPath `contains(normalize-space(.), 关键字)` 匹配，**不依赖 class**；跳过文字 >30 字的大容器；`click()` 被遮罩挡住时退回 JS 点击；返回是否点到 |
| `choice_course()` | 先用关键字点「我学的课 / 我的课程」，失败才走原来的 `course-tab` 兜底（文字也改成包含匹配） |
| `choice_course()` 读课程卡片 | 原来只读一次，现在最多轮询 8 秒（16×0.5s），等异步渲染 |

验证：新增 `test_course_entry.py`（**11 项**：完全相等/带角标/换叫法/大容器跳过/遮罩退回 JS/
找不到返回 False/整流程点标签+选课+保存列表）ALL PASS；**10 个套件全绿**；
打包 **26.10.31.1526**（63,485,432 字节，15:27:14），`--selftest` PASS，GUI 冒烟 OK。

### 4.17 窗口可缩放 + 程序运行日志 + 更新日志机制（15:30–15:45）

用户三点要求：①以后每次迭代写完整更新日志（能补的补）②修 GUI 不能缩放 ③从启动开始把完整日志写进单独文件。

1. **新增 `core/applog.py`**（主日志）
   - 文件：`%LOCALAPPDATA%\XuexitongShuake\logs\程序日志.log`（源码模式在 `task/logs/`）。
   - 每次启动写分隔块：时间/版本/pid/python/frozen/平台/app_root/data_root。
   - 行格式 `YYYY-MM-DD HH:MM:SS.mmm [LEVEL] 内容`；等级 `INFO/WARN/ERROR/CHILD/UI`。
   - 8MB 轮转 `.1`；线程锁；写盘异常静默。
2. **接入点**
   - `start.py`：启动块（GUI 与 `--selftest` 都写）、窗口初始化、点击开始/结束学习、
     账号结束、`report_callback_exception`（界面回调异常）、`WM_DELETE_WINDOW`；
   - `core/runner.py`：子进程启动（含 pid）/配置无效/启动失败/退出码 + 全部输出（`CHILD` 行带账号别名）。
   - `_alias_map` 把账号 ID 映射成别名，日志里更好认。
3. **GUI 可缩放**
   - `resizable(True, True)` + `minsize(860, 560)`（逻辑像素，CTk 再乘 DPI）。
   - 原布局权重已具备，放大后日志区/课程列表自动伸展（测试里验证了宽度确实变大）。
4. **关窗停子进程**
   - 新增 `WM_DELETE_WINDOW` 处理：先日志，再 `runner.stop_all()`（`taskkill /F /T`），再销毁窗口。
   - 这顺手解决了第 7 节遗留的「关窗留下孤儿进程」问题（第 1 项）。
5. **新增 `更新日志.md`**：约定+模板+按版本补齐 26.10.30.2125 起的历史；
   更早改动只有主题没有版本号，集中列在「更早的版本」并注明没有确切版本。

验证：新增 `test_applog.py`（**19 项**）ALL PASS；**11 个套件全绿**；`compileall` 0；
打包 **26.10.31.1537**（63,492,281 字节，15:38:26），`--selftest` PASS 且日志里留下启动块；
GUI 冒烟标题 `课程学习助手 26.10.31.1537`，日志出现「窗口初始化完成」。

### 4.18 修复：课程列表点不到「我学的课」、找不到课程（15:50–16:00）

用户反馈：还是定位不到「我学的课」，它不点那个菜单，直接提示找不到课程。

**这次靠主日志一次定位**（`logs/程序日志.log`，4.17 刚加的）：

```
账号2 | 登录成功
账号2 | 正在定位《高等数学》...
账号2 | 获取课程列表失败
账号2 | 未找到《高等数学》这门课程…
```

- 全程**没有**「已点击」→ 标签一次都没点到；也没有卡片 → 0 个课程。
- 根因：①只在固定 iframe `frame_content` 里找，而新版菜单在顶层文档；
  ②卡片只认 3 个 class；③失败后 `.experience` 兜底元素不存在 → 抛异常被外层统一打印成
  「未找到课程」，真实原因被吞。
- 改动（`main.py`）：
  - `_switch_to_frame()`：统一切帧，失败返回 False；
  - `_click_text_keyword()`：Selenium 找不到时用 JS 去掉空白再匹配（`_CLICK_BY_TEXT_JS`）；
  - `_click_course_tab()`：在 `top / frame_content / iframe` 轮询点标签（12 秒）；
  - `_collect_course_cards()`：10 套选择器、title 优先、去重、过滤空/超长；
  - `_locate_course()`：跨帧找卡片 + JS 点击，返回「看到的课程名」；
  - `_save_course_names()`：直接写 `course_name.json`；
  - `describe_course_page()`：失败时打印 url/title/各帧 iframe/课程元素样本；
  - `choice_course()` 重排 + `_retry` 防递归；人工兜底等待改为 **180 秒上限**（原来无限等）。
- 附带修复：主日志里每行重复两遍（runner 与界面各写一次）→ 只保留界面侧（带别名）。
- 验证：`test_course_entry.py` 重写 **18 项** ALL PASS；**11 个套件全绿**；
  打包 **26.10.31.1558**（63,496,681 字节，15:59:48），`--selftest` PASS。

### 4.19 修复：「我学的课」点了但没跳（且谎报已进入）（16:00–16:10）

用户截图：页面停在「我的课表」，程序日志却是
`已点击「我学的课」（JS）` → `已进入「我学的课」列表` → `正在定位《高等数学》…`。

- 根因：①JS 兜底不分标签，点到包住文字的 `div/span`，而跳转绑在 `<a>/<li>` 上；
  ②`_click_course_tab()` 点完不验证就返回 True，上层直接打印「已进入列表」；
  ③菜单文字在 DOM 里被换行拆开，`normalize-space()` 匹配不到，只能走 JS 分支。
- 改动：`_CLICK_BY_TEXT_JS` 重写（取最短命中节点 → `closest('a')` → `closest('li')` →
  自身，并返回 `a=href`）；新增 `_GOTO_BY_TEXT_JS` + `_goto_course_tab()`（按 href 直接跳）；
  新增 `_wait_course_list()`；`_click_course_tab()` 改成「点→验证→换帧→跳转→再验证」，
  只有看到课程卡片才返回 True；日志打印 JS 实际点到的节点。
- 验证：`test_course_entry.py` 增到 **21 项**（点了没反应返回 False、列表出现才算成功、
  成功只点一次）ALL PASS；11 套件全绿；打包 **26.10.31.1608**（63,499,128 字节，16:09:33）。

### 4.20 修复：「我学的课」点到的是 `<li>`，点它没反应（16:10–16:25）

日志（1608 版）关键一行：`已点击「我学的课」（JS：li=我学的课）`。
说明命中的是 `<li>`，且**没有祖先 `<a>`**——1608 的 JS 只查了 `closest('a')`（自己/祖先），
漏了**后代** `<a>`（最常见结构就是 `<li><a href=…>我学的课</a></li>`），`li.click()` 自然没反应。

- 改动：
  1. `_CLICK_BY_TEXT_JS` 命中顺序改为 **祖先 `<a>` → 后代 `a[href]` → `<li>` → 自身**，
     并回传 `li` 的 `class` / `onclick`；
  2. 新增 `_last_click_detail`：点到链接但没跳时，`_click_course_tab()` 直接 `driver.get(href)`；
  3. 新增 `COURSE_LIST_URLS` + `_open_course_list_via_url()`：菜单彻底点不动时
     **直接打开课程列表页**（mooc1 / mooc1-1 / mooc2-ans 三个地址），每个都验证是否出现课程卡片；
  4. `choice_course()` 接入该兜底，失败时立刻打印页面诊断。
- 验证：11 套件全绿；`test_course_entry.py` 21 项 ALL PASS；
  打包 **26.10.31.1618**（63,499,292 字节，16:21:49），`--selftest` PASS。
- 教训：**"点到了" ≠ "点对了"**。点之前要确认点的是可跳转的节点（a/href），
  点之后要验证页面真的变了；两者都缺就会写出"我点过了"但页面没动的代码。

### 4.21 修复：题干「文字+公式图片」不触发多模态；重做测验崩溃（16:30–16:50）

用户实测反馈：整场测验题目是图片，但只答错、没调用图像 API。

- 日志证据（16:36 那场）：题干是 `函数的间断点为()`（文字非空但公式在图里），
  程序走纯文字搜题拿到 `['A0']`、`['B2']`，提交后「未达到及格线，请重做」；
  `record/图片题/` 里无截图 → 根本没被当成图片题。
- 根因：图片题判定只在「题干文字**完全为空**」时触发。题干是「文字 + `<img>` 公式」时文字非空，
  于是当普通题处理。
- 改动（`task/quiz_ai.py`）：
  - `_element_has_meaningful_image()`：≥40×16 的图才算，过滤小图标；
  - `_question_has_stem_image()`：JS 扫描整题元素，**排除选项 `<li>` 的图**，只看题干区域；
  - `get_title_option()`：题干含图 → 记入 `image_questions`，改由多模态作答；
  - 日志文案改为「改由多模态作答」。
- 附带修：自动重做时 `after_finish_question` 已是 float(0.9)，又被 `re.search` 处理 →
  `TypeError` → 整场放弃。新增 `_parse_finish_ratio()`（数字直接返回，字符串才解析 `%`）。
- 验证：新增 `test_image_stem.py` **12 项** ALL PASS；**12 个套件全绿**；
  打包 **26.10.31.1644**（63,501,360 字节，16:45:43），`--selftest` PASS。

### 4.22 修复：点任务点后「页面无法识别」→ 3 次就结束整门课（16:50–17:00）

16:50 那次（用户截图）在 `已检测到未完成点` 之后卡住：
`该页面无法识别` ×3 + 指纹 `|0|0|` ×3 → 「连续 3 次页面内容没有变化，结束本课程」。

- 分析：`已检测到未完成点` → 首次检测间隔约 25 秒 ≈ `turn_page('学生学习页面')` 20 秒超时，
  说明**没有标题为「学生学习页面」的窗口**（学习页开在了新标签页、标题不同）；
  指纹 `|0|0|`（无章节标题/无子 iframe）说明仍停在目录页。
- 另外暴露我 4.15 引入的一个错误：**「无进展计数」把"页面无法识别"也算进去了**，
  于是刷新 3 次就结束整门课，且没打印页面诊断。
- 改动：新增 `_switch_to_newest_window()`（记录点击前窗口，失败后切到新窗口，不看标题）、
  `_window_titles()`（打印所有窗口标题，当前窗口标 `*`）；
  `main()` 里 `turn_page('学生学习页面', timeout=8)` 失败后：切新窗口 → 当前是否已是学习页 →
  打印窗口标题；`run()` 里无进展计数只在**识别成功**时累加，未知页面首次失败即打印 `页面诊断`。
- 验证：`test_page_loop.py` 增到 **24 项** ALL PASS；12 套件全绿；
  打包 **26.10.31.1659**（63,502,128 字节，16:59:52），`--selftest` PASS。

### 4.23 用户要求：认不出的页面「截图 + 直接下一节」；任何错误都留截图（17:05–17:15）

用户明确要求：「以后遇见这种无法识别的页面，直接点击下一节，顺便截个图作为诊断日志输出；
以后遇见任何错误，直接截图作为诊断日志输出。」

- 背景：17:04 停在「不定积分的性质及基本公式」——这是**纯文本知识点**（教学要求），
  页面没有任何模块 iframe，`page_message()` 认不出；旧行为刷新 3 次白等 30 秒。
- 改动：
  1. `run()`：识别不到页面 → 打印 `页面诊断` → **保存截图** → 直接「点下一节」；
     连续 `UNKNOWN_SKIP_LIMIT = 10` 页认不出才结束课程（原来是刷新 3 次就停）。
  2. 新增 `task/tool/common.py: save_diagnostic_screenshot(driver, tag)`，
     截图存 `record/诊断截图/<标签>_YYYYmmdd_HHMMSS.png`，失败静默。
  3. 接入点：未识别页面、页面卡住、`dispatch_page` 各类处理异常（`<类型>出错`）、
     `Quiz.start`（`测验出错`）、`run_main` 三类异常（`找不到元素`/`浏览器会话异常`/`程序异常`）。
  4. `main.py` 增加模块级 `_CURRENT_DRIVER`，让顶层异常也能截图。
- 验证：`test_page_loop.py` 增到 **29 项** ALL PASS；12 套件全绿；
  打包 **26.10.31.1711**（63,502,790 字节，17:12:43），`--selftest` PASS。

### 4.24 额度保护：简答题不再疯狂刷 API（17:30–17:45）

用户实测：一场 10 题全简答的章末测试，每道题都「题库 3 源 → DeepSeek → 未找到」，
几十次请求把额度烧掉。要求：这种题直接跳过，任何时候不许刷爆额度。

- 根因：①简答类只是"没有选项"，仍进搜题队列；②题库空结果时 `_search_bank` 还重试一次；
  ③全链路没有任何调用上限。
- 改动：
  1. 新增 `task/tool/quota.py`：本轮总数 100 / 每分钟 20 / 同题 DeepSeek 2 次，
     超限打印 `⛔ ...` 一次并拒绝，进程级、线程安全；
  2. `DeepSeekAsk`、`DeepSeekAskImage` 联网前过闸门（图片题指纹带图片路径）；
  3. `ai_wen_da` 两个取答案入口加闸门；`auto_answer_question` 对 2/9 题型直接返回；
  4. `quiz_ai` 新增 `UNANSWERABLE_TYPES`（简答/论述/填空/名词解释/未知）→ 搜题与 AI 都跳过；
     去掉题库重试；`use_deepseek` 单次最多 15 道；每场结束打印累计联网次数。
- 验证：新增 `test_quota.py` **16 项** ALL PASS；**13 个套件全绿**；
  打包 **26.10.31.1741**（63,509,115 字节，17:42:42），`--selftest` PASS。

### 4.25 修复：计算题仍被送多模态（特殊题跳过不彻底）（18:05–18:20）

用户截图：4 道计算题，日志写着"题型无法识别…已跳过自动作答"，却仍截图调模型并"答"了 A。

- 根因：`get_title_option()` 的 **else 分支（题型没解析出来）直接把题登记成 `image_questions`**，
  答题时就会调多模态。计算题的题型标签不在题干元素里，正好落进这个分支。
- 改动：
  1. 分型 `question_kind()`：choice / essay / unknown；
  2. unknown 分支按**有没有 `<li>` 选项**区分：无选项 → `skipped_questions` + 只截图、不调 AI；
     有选项 → 仍走多模态（整题图片的选择题保持原行为）；
  3. 新增 `skipped_questions`：`finish_title()` 直接返回、`use_ai_wen_da()` 不查题库、
     `no_answer_dit` 不收录；整场全跳过时直接结束本场（不重做）。
- 验证：`test_quota.py` 扩到 **22 项** ALL PASS；13 套件全绿；
  打包 **26.10.31.1817**（63,509,646 字节，18:19:07），`--selftest` PASS。

### 4.26 修复：计算题里也有 `<li>`，导致仍被送多模态（18:35–18:50）

用户再次实测：5 道计算题仍然 `题型未解析但有选项，按图片题交给多模态`。

- 根因：1817 用「有没有 `<li>`」判断能否点选项，但**计算题的"填写答案"富文本编辑器
  工具栏本身就是 `<li>`**，于是被当成选项题。
- 改动（三重判据）：
  1. `_has_rich_editor()`：出现 `[contenteditable=true]`/`.w-e-text-container`/`textarea`/
     `.edui-body-container`/`iframe.w-e-iframe` → 主观题，直接跳过；
  2. `_count_real_options()`：JS 统计"真正的选项"（排除编辑器区域后，要求 A./B. 标号、
     radio/checkbox、`num_option`/`option` 类、或图片）；
  3. `_can_answer_by_options()`：有编辑器或真实选项 <2 → 不能作答；
  4. 题型兜底：题干元素没有 `【xx题】` 时从整题文本再捞一次（计算题常见）。
- 验证：`test_quota.py` 扩到 **29 项**；13 套件全绿；
  打包 **26.10.31.1844**（63,510,605 字节，18:46:07），`--selftest` PASS。

### 4.27 额度策略改成频率限流（22:09–22:25）

用户要求：「100 次太少了完全不够，改成限制频率」。

- 改动（`task/tool/quota.py`）：
  1. `MAX_TOTAL = None`：**不再有总量上限**（保留显式设置能力作兜底）；
  2. 保留 **每分钟 20 次**，但新增 `acquire()`：达到频率上限时**等待**下一个时间窗
     （最多 90 秒，每次 sleep ≤5 秒），不再直接丢题；
  3. 同题 DeepSeek 最多 2 次的上限保留（防同一题死循环），超限立即返回不等；
  4. `DeepSeekAsk`、`DeepSeekAskImage`、`ai_wen_da` 两个入口改用 `acquire()`；
  5. 提示 `⏳`，每场结束打印累计次数与"最近一分钟 M/20"。
- 验证：`test_quota.py` **35 项** ALL PASS；13 套件全绿；
  打包 **26.10.31.2219**（63,512,353 字节，22:23:54），`--selftest` PASS。

### 4.28 修复：被打回的空壳页空转 + 新版学习页无 id iframe（22:37–23:00）

用户日志：卡在 `mooc1-2.chaoxing.com/visit/courses/study?s=...`，反复"无法识别 → 截图 →
点下一页失败"，最后被刷回首页。用户指出这就是**被平台打回时落的空壳首页**。

- 根因：①`page_message()` 只认 `#iframe`/顶层，新版学习页内容在**无 id 的 iframe** 里；
  ②翻页只认 `#prevNextFocusNext`，该版式没有；③空壳页没专门识别；④`run()` 无法上报"页面丢了"。
- 改动：
  1. `page_message()` **逐帧下钻**（顶层 → 最多 4 个 iframe），结束统一回默认文档；
  2. `_find_next_button()` + `NEXT_PAGE_XPATHS`（id → 文字「下一页/下一节」→ class 含 next），
     `click_next_page()` 先顶层、再逐帧找；
  3. `_looks_like_course_home()`：`/visit/courses/study` 且无 `#iframe` → 空壳页；
  4. `run()` 返回 `'done'/'lost'/'home'`；`main()` 遇 `'lost'` 调 `_reenter_course()`
     （首页→重选课，否则刷新）重新 `find_mission`，最多 3 次。
- 验证：`test_page_loop.py` **35 项** ALL PASS；13 套件全绿；
  打包 **26.10.31.2253**（63,514,662 字节，22:55:27），`--selftest` PASS。

### 4.29 多账号：签到多选 + 并发状态可视化（23:00–23:20）

用户反馈：①自动签到只进一个账号，也没有选账号的选项；②调完并发数不知道哪几个账号在跑/排队。

- 根因：
  1. `SignWindow` 只接收当前账号的 `account_info`，只起一条签到线程；
  2. 签到数据目录是全局 `paths.root_data('data')`，多账号共用同一份 `config.json`
     （cookie 互相覆盖），所以"多开"本身不安全；
  3. `Runner` 不暴露运行/排队集合，GUI 只能说"已启动 N 个"。
- 改动：
  1. `SignWindow` 重写为**多选账号**（默认勾选已启用，含全选/全不选），每个账号一个
     **独立子进程**（`start.py --sign`，各自 `XXT_HOME`），最多同时 3 个，输出带账号前缀；
  2. 新增 `sign_once()` 子进程入口；`bootstrap()` 的 `input()` 加 EOF 保护；
  3. `task/xxt/storage.py` 的 `DATA_DIR` 改为 `paths.data('data')`（跟随 HOME）→ 签到数据隔离；
  4. `Runner` 增加 `entry_args`、`running_ids()`、`pending_ids()`、`_discard_pending()`；
  5. GUI：日志栏状态标签每秒刷新「并发 2/3 ｜ 运行中：… ｜ 排队：…」，
     账号下拉框加 `● 运行中` / `… 排队` 前缀并保持当前选择。
- 验证：新增 `test_multi_account.py` **18 项** ALL PASS；**14 个套件全绿**；
  GUI 冒烟（主窗口 + 签到窗口）通过；打包 **26.10.31.2313**（63,521,549 字节，23:16:11），
  `--selftest` PASS。

### 4.30 修复：课程被「连续 3 次页面内容没有变化」误结束（2026-11-05 17:26，源码，未打包）

用户 11-05 日志（另一台电脑，跑 26.10.31.2253）里 4 次「结束本课程」，两账号几乎同时触发。
页面其实在正常前进（诊断 URL 的 chapterId 每次不同、视频一节节播完），
16:42 的「页面卡住」截图是一张还没开始播放的全新视频页 —— 纯属误判。
完整证据：工作区 `课程被结束_根因分析_2026-11-05.md`。

- 根因三条：
  1. `_content_signature()` 的四元组在新版学习页退化成常量（`.prev_title` 取不到、
     iframe src 只取前 80 字符，所有视频模块都一样），**不含 URL / chapterId / objectId**；
  2. `run()` 只在指纹不同时清零 `no_progress`，未识别页分支不碰计数 → 跨 38 分钟、
     跨多个章节累积到 3；
  3. 上限触发时 `return 'done'`，`main()` 只对 `'lost'` 重进课程 → 整门课被直接关掉。
- 改动（`main.py`）：
  1. 新增 `_page_identity()`：从顶层 URL + 各 iframe src 提取
     `chapterId/courseId/clazzId/knowledgeId/objectId/jobId/cardId`；
     刻意排除 `s=`/`ktoken=` 随机 token；取不到则返回空串退回旧行为；
  2. `run()` 复合指纹 = `身份||内容指纹`，日志带上 chapterId；
  3. 未识别页重置 `no_progress` / `last_sig`；
  4. 达到 `STUCK_LIMIT` 先 `refresh()` 重试一次，刷新后变了就继续学，
     仍卡住才 `return 'lost'`（交给 `_reenter_course()`，最多 3 次）。
- 验证：`compileall` 0 错；`test_page_loop.py` 35 → **43 项 ALL PASS**；
  11 个纯桩套件全绿。3 个需真实 Edge 的套件因本机 Edge `156.0.4314.58` /
  缓存驱动 `156.0.4314.42` 不匹配失败（`unhandled request`，最小脚本复现），与改动无关。
- **未打包**：`dist/start.exe` 仍是 26.10.31.2313；版本号文件未动。
- 未做：P2（把「章节详情/图文作业页」纳入 `CONTENT_TYPES`）需要真机确认判定条件，
  避免静默漏做真有任务点的页面。

### 4.31 修复签到高频轮询 + 复查课程误结束 + 打包 26.11.05.1832（2026-11-05 18:20–18:35）

**封号根因**（用户尾号 1475 账号被封，技术部门称「连续刷 20 万次」）：
不是答题 API（两个账号全部日志联网仅几百次、有 20 次/分钟限流），
而是**自动签到**：`constants.py:36 CHECK_INTERVAL=2`（注释却写 7 秒），
每轮对 24 门课各发一次 `ACTIVE_LIST` ≈ 12 次/秒 ≈ 4.3 万次/小时；
`data/sign.log` 1258 行里 1231 行是空转「课程列表: 24 门」，最后一次启动后无「已停止」。
详见工作区 `1475账号封号_调用量分析_2026-11-05.md`。

- 签到改动：`CHECK_INTERVAL` 2→30 秒；新增空闲退避（10 轮后逐步到 120 秒）、
  最长运行 4 小时自动停止；`storage.log` 加时间戳；`sign_window` 抽出
  `_build_parser()` 改用 `parse_known_args()`（修 `--sign` 被 argparse 拒绝）、
  `sign_once()` 传 `stop_event` + `_watch_parent_exit()` 父进程消失自停。
- 复查 4.30 的课程修复：用 11-05 真实 URL 验证 `_page_identity()` 能提取 chapterId；
  审查全部 `return 'done'/'lost'/'home'` 与 `main()` 的 status 处理，确认只有
  「课程到底 / 连续 8 次找不到下一页」走 `'done'`；再加固 3 处
  （identity 排序拼接、刷新后 identity 为空不误判换页、处理器异常后重置计数），
  `test_page_loop.py` 43→45 项。
- 验证：`compileall` 0 错；新增 `test_sign_monitor.py` 15 项 ALL PASS；
  12 个纯桩套件全绿；3 个需真实 Edge 的套件仍因本机 Edge 156.0.4314.58 /
  驱动 156.0.4314.42 不匹配失败（与改动无关，单列待办）。
- 产物：`dist/start.exe` 63,550,578 字节，18:35:16，文件属性 26.11.05.1832，
  `--selftest` RESULT=PASS；备份 `dist/start-26.10.31.2313.exe`；
  `task/tool/version_info` 与 `start_version.txt` 已同步。
- 未做：位置签到爬山循环无总请求上限；P2 图文页识别；真机关窗后签到子进程残留的观察。

### 4.32 界面新增「导出完整日志」+ 打包 26.11.05.1911（2026-11-05 19:05–19:14）

需求：在界面加导出完整日志功能，导出为**一个单独文件**、包含所有数据、只导单日。

- 为什么不复用根目录 `export_logs.ps1`：它是全量打包、依赖 PowerShell 执行策略、只能外部
  双击；界面点一下就出结果必须走 Python，且要按天过滤。**ps1 保留未改**，继续作为独立工具。
- `core/log_export.py`（新增）：`export_day_logs()` → 一个 zip。包内
  `00_FULL_LOG_<日期>.txt` 是所有文本日志的合并版（可直接发人），
  `00_README.txt` 有规则 + 包内名↔原始位置对照表 + 数据目录完整清单；分类目录沿用
  ps1 的 ASCII 命名：`logs/`、`logs/accounts/<账号>/`、`shots/`、`records/`、
  `config_sanitized/`。
- 三个容易踩的坑，接手时别改回去：
  1. **只认行首时间戳**（`_TS_LINE_RE`）。日志正文里常有带日期的 URL，用「任意位置
     出现 YYYY-MM-DD」判断会把整份日志误判成结构化，导致续行全丢。
  2. **无时间戳续行用状态机跟随**（`filter_text`）：traceback、子进程输出、启动块分隔线
     都跟着上一条带日期行走，不能按行独立丢弃。
  3. **`run/<账号>/运行日志.log` 只有 `HH:MM:SS`、没有日期**，必须按文件 mtime 判断，
     否则永远导不出来。配置 / 记录是「当前快照」，不受单日过滤，但汇总里要标
     「日志 0 份 / 快照 N 份」，免得把快照当成当天运行记录。
- 脱敏是**所有入包文本**统一过 `sanitize()`，不是只处理配置文件：日志正文里也会出现
  手机号。真实数据实测 6 个敏感值 0 泄露。
- `gui/log_export_dialog.py`（新增）：后台线程只写结果变量，主线程 `after` 轮询刷新，
  不要在子线程碰 Tk 控件；导出动作写 `applog.ui()` 便于追溯。
- `start.py`：主页第 4 列按钮、`text_box_frame` columnspan 3→4、按钮纳入换色列表、
  selftest 模块清单补两项。
- 验证：新增 `test_log_export.py` 60 项 ALL PASS；16 套件 13 绿 / 3 个 Edge 驱动失败
  （同 4.31，环境问题）；真实数据导出 2026-10-31 得 1.85 MB / 27 条目；
  GUI 冒烟（Start 实例化 + 弹窗）通过；`--selftest` PASS；
  exe 63,575,643 字节 / 19:13:39 / 26.11.05.1911，备份 `start-26.11.05.1832.exe`。
- 未做：4.31 的旧待办本轮未触碰。

---

## 5. 代码地图（当前 agent 新增/修改）

| 文件 | 性质 | 要点 |
|---|---|---|
| `core/paths.py` | 重写 | ASSETS / DATA_ROOT / HOME、`XXT_DATA`、`root_data`、`data_or_asset`、迁移、`prepare`、旧名称迁移 |
| `core/driver.py` | 新增 | 浏览器版本探测、驱动候选、官方 CDN 下载、中文错误说明 |
| `core/browser.py` | 修改 | `_send_key`、`press_escape`（CDP） |
| `task/quiz_ai.py` | 修改 | 遮罩检测/关闭、跨帧上下文、JS 点图选项、跨帧按钮、除零保护 |
| `task/do_work.py` | 修改 | 作业页窗口上下文、占位登记防错位、异常分支兜底 |
| `task/tool/no_secret.py` | 修改 | 字体解析临时文件唯一化 + 清理 |
| `task/tool/face.py` | 修改 | `face_url.json` 读取走 `data_or_asset`；处理类改名 |
| `task/tool/page_compat.py` | 重命名 | 原 `disable_monitor.py`，类名 `PageCompat` |
| `task/tool/send_wx.py` | 修改 | 错误日志写数据目录 |
| `task/xxt/storage.py` | 修改 | 签到数据目录改 `DATA_ROOT/data` |
| `main.py` | 修改 | 每轮清遮罩；驱动解析与下载重试；文案统一；章节标记兼容 |
| `start.py` | 修改 | 数据目录/日志、`--selftest`、无控制台 stdout 兜底、界面文案、导出日志按钮 |
| `core/log_export.py` | 新增（4.32） | 单日完整日志导出：按日过滤 + 脱敏 + 单 zip + 汇总 txt |
| `gui/log_export_dialog.py` | 新增（4.32） | 导出日期/目录选择弹窗，后台线程导出 |
| `gui/setting_panel.py` | 修改 | 驱动路径占位符不落盘、旧配置值兼容、文案统一 |
| `gui/user_notice.py` | 修改 | 声明文案更新 |
| `task/tool/Help.txt` | 重写 | 驱动/设置/常见问题，按新流程更新 |
| `start.spec` | 修改 | 文件版本资源 + 单文件说明 |
| `start_version.txt` | 新增 | 文件属性（课程学习助手 / 26.10.30.2125） |
| `task/watch_vido.py` | 修改（10-30） | 视频题固定随机作答，删除 AI 分支；签名去掉 `API`/`video_title_choice` |
| `gui/setting_panel.py` | 修改（10-30） | 「视频题目」固定为 `随机答题`；旧配置 coerce；重置表单还原该值 |
| `gui/update_checker.py` | 修改（10-30） | `parse_version()` + `_is_latest()` 数值比较；确实有新版本才弹窗 |
| `task/tool/version_info` | 修改（10-30） | `26.10.30.2125` |
| `task/quiz_ai.py` | 修改（10-30 第 1 批） | `_as_answer_list`（字面量解析）、`_split_batch_answer` 段数校验、`_ask_one` 逐题兜底、删除 AI 答案写缓存；测验选择器改前缀匹配 |
| `task/tool/ai_wen_da.py` | 修改（10-30 第 1 批） | `AnswerResult.cacheable`；DeepSeek 结果不可缓存；写缓存前按 `cacheable` 过滤 |
| `main.py` | 修改（10-30 第 0 批） | 测验识别改 `iframe[src^="/ananas/modules/work/index.html"]` |
| `.workbuddy-ai/tests/test_quiz_answer_backfill.py` | 新增（10-30） | 取答案链路桩测试（24 项断言） |
| `.workbuddy-ai/tests/test_quiz_selector.py` | 新增（10-30） | 测验 iframe 选择器（真实 Edge，5 项断言） |
| `task/tool/DeepSeekAsk.py` | 修改（10-30 第 2 批） | 新增 `DeepSeekAskImage`（base64 多模态，模型仍 v4-flash）；文本入口不变 |
| `task/quiz_ai.py` | 修改（10-30 第 2 批） | 图片题改多模态作答；`_LABEL_JS` 点字母节点；`_parse_choice_letters`；`_mark_image_question`；`require_mission=False` |
| `task/tool/common.py` | 修改（10-30 第 2 批） | `require_mission` 开关；测验不再要求任务点图标 |
| `task/do_work.py` | 修改（10-30 第 2 批） | 图片题登记同步进 `image_unanswered`（作业也能走多模态） |
| `main.py` | 修改（10-30 第 2 批） | `_open_first_chapter`（无任务点从头上扫）；`click_next_page` 三态 + `_wait_page_changed`；`run()` 卡页计数；`UNKNOWN_REFRESH_LIMIT=3` |
| `.workbuddy-ai/tests/test_image_question.py` | 新增（10-30） | 图片题逻辑桩测试（22 项断言） |
| `.workbuddy-ai/tests/test_image_answer.py` | 新增（10-30） | 图片选项点击/遮罩（真实 Edge，13 项断言） |
| `.workbuddy-ai/tests/manual_vision_probe.py` | 新增（10-30） | 手工跑一次真实多模态验证（不入自动测试） |
| `.workbuddy-ai/tests/test_page_loop.py` | 新增（10-30） | 翻页/内容指纹/日志落盘桩测试（20 项断言） |
| `core/applog.py` | 新增（10-31） | 程序运行日志：启动块、五级日志、8MB 轮转、线程锁 |
| `.workbuddy-ai/tests/test_course_entry.py` | 新增（10-31） | 课程列表入口关键字（11 项断言） |
| `.workbuddy-ai/tests/test_applog.py` | 新增（10-31） | 程序日志 + 窗口缩放（19 项断言） |
| `更新日志.md` | 新增（10-31） | **每次迭代必须更新的改动清单**（含条目模板） |
| `main.py` | 修改（10-31） | `turn_page` 轮询等待、`_wait_element(s)`、`find_mission` 等导航标签、`_close_course_tab`、`_error_brief` 取异常行、`run_main` 新增 NoSuchElement 分支 |
| `task/tool/common.py` | 修改（10-31） | `check_audio_finished` 包含匹配+容错；`main()` 滚动容错、单场异常不再中断、跳过打原因 |
| `task/quiz_ai.py` | 修改（10-31） | `_quiz_finished_by_status()` 只认测验自身状态；选择器 `src*=`；`Quiz.start` 错误提示带原因 |
| `.workbuddy-ai/tests/test_quiz_skip.py` | 新增（10-31） | 测验被跳过回归（20 项断言） |
| `main.py` | 修改（10-30 打包前复核） | 卡住时先刷新一次再计数；章节头扫每个选择器最多试 3 个节点 |
| `task/tool/version_info`、`start_version.txt` | 修改（10-30 打包） | `26.10.30.2256` |
| `.workbuddy-ai/tests/test_video_question.py` | 新增（10-30） | 视频题随机作答桩测试（18 项断言） |
| `.workbuddy-ai/tests/test_update_version.py` | 新增（10-30） | 更新检查版本比较（9 项断言） |
| `requirements.txt` | 修改 | 去掉不用的依赖，补打包说明 |
| `.workbuddy-ai/tests/test_quiz_image.py` | 新增 | 图片题/遮罩/重定位回归测试 |
| `.workbuddy-ai/tests/inspect_crx.py` | 新增 | 查看 crx 扩展内容的小工具 |
| `.workbuddy-ai/memory/2026-10-25.md` | 追加 | 原始流水账（含第一任记录） |

---

## 6. 测试与验证

```powershell
# 1) 全量编译
C:\Python315\python.exe -m compileall -q core gui task main.py start.py

# 2) 图片题/遮罩/元素失效回归（真实 Edge + 本地仿真页，28 项断言）
C:\Python315\python.exe .workbuddy-ai\tests\test_quiz_image.py
# 期望最后一行：ALL PASS

# 2b) 视频内弹题（纯桩，无浏览器，18 项断言）：随机穷举、不调 AI、签名收敛
C:\Python315\python.exe .workbuddy-ai\tests\test_video_question.py

# 2c) 更新检查的版本比较（纯逻辑，9 项断言）
C:\Python315\python.exe .workbuddy-ai\tests\test_update_version.py

# 2d) 取答案链路（纯桩，24 项断言）：字面量解析 / 段数校验 / 逐题兜底 / 缓存策略
C:\Python315\python.exe .workbuddy-ai\tests\test_quiz_answer_backfill.py

# 2e) 测验 iframe 选择器（真实 Edge，5 项断言）：新前缀匹配能命中、旧精确匹配命中不了
C:\Python315\python.exe .workbuddy-ai\tests\test_quiz_selector.py

# 2f) 图片题多模态逻辑（纯桩，22 项断言）：字母解析 / 点选项 / 跳过 / 随机 / 哨兵不联网
C:\Python315\python.exe .workbuddy-ai\tests\test_image_question.py

# 2g) 图片选项点击（真实 Edge，13 项断言）：必须点字母节点、不能点 img、不能弹遮罩
C:\Python315\python.exe .workbuddy-ai\tests\test_image_answer.py

# 2h) 手工验证真实多模态链路（用真实 key，画一张合成题目图，只发 1~2 次请求）
C:\Python315\python.exe .workbuddy-ai\tests\manual_vision_probe.py

# 2i) 翻页/日志落盘（纯桩，20 项断言）：内容指纹、点击两态、报错摘要、等元素、单窗口保护、
#     子进程输出落盘与轮转
C:\Python315\python.exe .workbuddy-ai\tests\test_page_loop.py

# 2j) 测验被跳过（纯桩，20 项断言）：无前置 div 不崩、class 包含匹配、完成判定只看测验自己
C:\Python315\python.exe .workbuddy-ai\tests\test_quiz_skip.py

# 2k) 课程列表入口（纯桩，11 项断言）：按关键字点「我学的课」、大容器跳过、遮罩退回 JS、整流程选课
C:\Python315\python.exe .workbuddy-ai\tests\test_course_entry.py

# 2l) 程序日志与窗口缩放（19 项断言）：启动块、五个等级、异常堆栈、毫秒时间戳、轮转、
#     8 线程不丢行、窗口可缩放、最小尺寸、放大后确实变宽
C:\Python315\python.exe .workbuddy-ai\tests\test_applog.py

# 3) 界面构建冒烟（8 个页面）
C:\Python315\python.exe -c "import sys; sys.argv=['start.py']; import start; s=start.Start(); [s.select_frame_by_name(p) for p in ['主页','设置','帮助','学习记录','测试成绩','题库查询','报错日志','赞助作者']]; print('pages OK'); s.root.after(300, s.root.destroy); s.root.mainloop()"

# 4) 打包
C:\Python315\python.exe -m PyInstaller start.spec --clean --noconfirm

# 5) 打包后自检（结果在 %LOCALAPPDATA%\XuexitongShuake\selftest.log）
.\dist\start.exe --selftest
```

注意：

- 测试程序会把 `XXT_HOME` 指到临时目录，不污染项目记录。
- 跑界面/打包前先关掉正在运行的 `start.exe`，否则文件被占用。
- 本机没有 Chrome，自检里 `chrome version=None` 属正常；Edge 应为 156.0.4314.42。

---

## 7. 已知未修问题（按优先级）

1. 驱动获取失败目前只在日志里，界面没有引导。
2. 作业模式只处理第一门课（`main.py` 里 `do_work` 之后直接 `return`）。
3. 作业「自动选择」硬编码第 3 个单选框（`do_work.py:31` 的 `elements[2]`），页面结构一变就 IndexError。
4. ~~主窗口没绑定 `WM_DELETE_WINDOW`：点 X 退出不杀子进程，子进程写 stdout 抛 `OSError [Errno 22]`。~~
   **已修（4.17）**：关闭时先 `runner.stop_all()` 再销毁窗口，并记进程序日志。
5. 直播时长按「秒×60+分」解析（`watch_live.py:35`），1:30 会等 30 分钟、45:00 只等 45 秒。
6. 签到首次使用会调到 `input()`（`sign_window.py:34`），窗口版没有控制台 → `EOFError`。
7. 运行时 `accounts.json` 明文存手机号/密码/API Key，未加密。
8. 旧版 `dist/task` 已删除；若用户仍保留旧安装，需要靠首次运行迁移。

### 7.1 用户明确表示「不是问题」，不要再改

- **视频内弹题固定随机作答**：平台没有错题校验，选错只提示，继续选下一个就能试到正确，
  所以**不调用 AI**（AI 分支已于 2026-10-30 删除，见 4.8）。
- **答题率** = 「搜索到几道 / 点了几道」的提交阈值（界面「搜到 N% 自动提交」），
  不是正确率；语义正确，不要改成「答对率」。
- **缓存策略（用户选定 b）**：只缓存题库/接口命中的答案，AI 兜底答案不写缓存；
  不要给缓存加 TTL，也不要改回「AI 答案也缓存」。
- **已完成的测验/考试要跳过**：不要为了"多做几道"去重复提交已完成测验。

### 7.2 2026-10-30 已修复

- 视频题 AI 作答后仍跑随机分支、覆盖答案 → 整段 AI 分支删除，只留随机穷举。
- 视频题答案不在选项里的索引越界 → 随 AI 分支一并消失（`finish_video_question` 已删）。
- 版本号 26.10.13 → **26.10.30.2125**（`version_info` + `start_version.txt` 同步），
  更新检查改为按版本号数值比较，本地比发布包新时不再误报「有新版本」。
- 批量答案按 `/` 位置回填无校验 → 段数校验 + 对不上就逐题问（见 4.9）。
- 题库返回 `eval()` → `ast.literal_eval`（`_as_answer_list`，见 4.9）。
- AI 答案写缓存导致错一次被永久固化 → `cacheable` 标记，只缓存题库结果（见 4.9）。
- 测验 iframe 精确匹配构建号 → `src^=` 前缀匹配（见 4.9）。
- 图片题只能跳过 → 截图走多模态作答（见 4.10）；点击落在 ABCD 文字节点，不碰图片。
- 测验/考试必须挂在任务点下才答 → `require_mission=False`（见 4.10）。
- 整章没有未完成任务点就整门跳过 → 从头扫描章节（见 4.10）。
- 未知页面/翻页失败导致原地无限循环 → 三态翻页 + 卡页计数（见 4.10）。
- `error_num` 累计不清零 → 翻页成功后清零。
- 日志把页面问题显示成「浏览器启动失败」并只给 `(No symbol)` → 异常分诊 + 摘要取异常行（见 4.12）。
- 切窗口不等标题、`window_handles` 为 None 二次报错 → `turn_page` 轮询 + 兜底（见 4.12）。
- 遇见章节测验直接跳过 → 选择器放宽、滚动容错、class 包含匹配、完成判定只看测验自己（见 4.13）。

---

## 8. 踩坑清单（下一位必看）

1. `switch_to.frame(None)` 不报错也不切换 —— 必须显式判断 `self.frame is not None`。
2. `driver.execute_script` 只认 `return`：立即执行函数要写成 `return (function(){...})()`。
3. 窗口模式 exe 的 `sys.stdout` 是 None：模块级包装 stdout 会崩；`start.py` 已补空流兜底。
4. 单文件 exe 的完整性标签会决定进程级别：exe 被标成 Low 时写不了 `%TEMP%`，
   报「无法创建临时目录」。不要把工程整体降级。
5. 保存/提交按钮在模块页（题目帧的父帧），作答后不切帧直接找会失败。
6. 图片选项的原生点击会弹全屏遮罩：必须用 JS 点 `<li>`，并兜底关闭遮罩。
7. iframe 重新加载后元素全部失效：每道题作答前重新进入上下文、重新定位，不要缓存元素。
8. 多账号并发不能共用临时文件：字体解析已改唯一文件名。
9. `browser` 形参曾遮蔽 `from core import browser` 模块：现在统一用 `browser_ext`。
10. 驱动地址的占位提示不能当路径保存：保存时已过滤。
11. 工作区路径含空格/括号：PowerShell 命令要引号，`cmd /c start "" "路径"` 同理。
12. 多账号不能用前台按键方案：全部改 CDP。
13. 调用 `ai_wen_da.main()`（异步入口）参数必须与签名 `(typ, question, options, api)` 严格一致：
    `quiz_ai.py` 曾多传 `self.driver`，导致每次题库搜索必抛 TypeError、100% 走 DeepSeek 兜底
    （表现为日志大量「第N题搜索失败」）。
14. 视频暂停恢复不要只依赖播放按钮的精确 class：`[class="..."]` 在 class 拼接变化时会点不到。
    改为先 JS `video.play()`、再用 `class*=` 包含匹配点按钮；且不要检测几次暂停（旧逻辑 b==3）
    就 raise 跳整页视频——已放宽到 b>=8 持续重试。
15. customtkinter 6.0 下 `CTkComboBox(state='disabled')` 调 `set()` **不生效**（`get()` 仍返回空串）。
    要显示固定值时用 `state='readonly'` + 单选项；否则保存校验会报「没填」。
16. 改含中文的源文件不要用 `Get-Content -Raw | Set-Content`：PowerShell 会按 ANSI 读写，
    把「课程学习助手」变成乱码（本次 `start_version.txt` 就踩过，已用 UTF-8 重写）。
17. 视频题只走随机作答，不要「优化」成调 AI：平台无错题校验，随机穷举必然试到正确；
    AI 分支历史上会在提交后被随机分支覆盖，属于负收益。
18. 题目/页面识别不要写死平台构建号（如 `?v=2025-1028-1629`）：平台发版必改，一改就静默漏做。
    统一用属性前缀/包含匹配（`src^=`、`class*=`）。
19. 第三方接口返回的内容一律走 `ast.literal_eval` 或显式校验，禁止 `eval`：畸形返回会打断整场测验，
    恶意返回可在本机执行任意代码。
20. **`deepseek-v4-flash` 支持图片输入，不要相信「不支持视觉」这句话**：早期 memory（`2026-10-25.md:135`）
    的那条结论已被实测证伪（合成单选题返回 `B`、多选题返回 `BD`）。图片按 base64 `image_url` 发送即可。
21. 图片选项点击**必须点字母/文字节点**（`_LABEL_JS`），绝对不能原生点 `<img>`：会让平台弹全屏放大，
    遮罩吃掉后续所有点击。没有字母节点时才退回点 `<li>`。
22. 图片题的选项数以**页面 `<li>` 为准**：整题是图片时 `num_option_dit` 只有 `['']` 占位，
    拿它算数量会把 B/C/D 全判成越界（这次踩过）。
23. 翻页必须验证"真的前进了"（`_wait_page_changed`）：只 refresh 就当成功会让 `run()` 在同一页
    无限循环，这也是用户看到的「卡住不动」。
24. **`NoSuchElementException` 是 `WebDriverException` 的子类**：`run_main()` 里必须放在前面单独 catch，
    否则页面元素问题会被打印成「浏览器启动失败」；`_error_brief()` 也不能取堆栈最后一行
    （WebDriver 的堆栈最后一行是 `(No symbol) [0x...]`）。
25. 新开标签页/切窗口后**标题要等**：`turn_page()` 必须轮询等待，不能 `sleep(1)` 就判定；
    它的返回值也不能忽略，否则会在旧页面上继续找元素，连锁报错。
26. `driver.window_handles` 在会话失效时会返回 `None`，遍历前要兜底，否则 `TypeError` 二次伤害。
27. 判断「测验是否已完成」**不能看相邻兄弟 div 的 aria-label**：那个 div 可能是同章节里已看完的视频，
   含「已完成」就把没做的测验也跳过。要看测验自己的 `testTit_status`。
28. `preceding-sibling::div[1]` 不是所有模块都有（考试尤其常见）：滚动/取状态都要能容错，
    否则一个 `NoSuchElementException` 就让整场测验被 `safe()` 吞掉。
29. 完成标记用**包含匹配**（`'ans-job-finished' in class`），不要用 `==` 比整串 class。
30. 判断「翻页有没有成功」**不能用 iframe 元素是否失效**：平台切知识点时不重建 iframe，
    用内容指纹（标题/完成数/模块 src）判断，见 4.15。
31. 用户会手动操作浏览器做测试（手动点下一页/切回），程序必须能容忍：不能因为一次点击没生效
    就结束整门课，也不能把手动切页当成自己的翻页失败。

---

## 9. 常用命令速查

```powershell
# 关掉正在运行的实例
Get-Process start -ErrorAction SilentlyContinue | ForEach-Object { taskkill /F /T /PID $_.Id }

# 源码运行
C:\Python315\python.exe start.py

# 重新打包（先关实例）
C:\Python315\python.exe -m PyInstaller start.spec --clean --noconfirm

# 单文件自检
.\dist\start.exe --selftest
Get-Content "$env:LOCALAPPDATA\XuexitongShuake\selftest.log" -Encoding UTF8

# 看报错
Get-Content "$env:LOCALAPPDATA\XuexitongShuake\error.log" -Tail 60 -Encoding UTF8

# 数据目录（备份/恢复出厂）
explorer "$env:LOCALAPPDATA\XuexitongShuake"

# 清临时解压残留（可选）
Get-ChildItem $env:TEMP -Directory -Filter '_MEI*' | Remove-Item -Recurse -Force
```

---

## 10. 建议的下一步

1. **真机验证新包**（`dist/start.exe` 26.10.31.1537）：单账号单课程跑一段，重点看
   ① 章节测验是否进入作答（日志应有「测验未标记完成（…），开始作答」）；
   ② 图片题是否有「图片题截图已保存」→「AI 答案: X」；
   ③ 翻页是否推进、卡住时是否打印原因；
   ④ **新增**：`logs/程序日志.log` 里是否有完整时间线（启动块 → 点击开始 → CHILD 行 → 退出码）。
   **以后排查先读这个文件**，不再靠界面截图。
   旧包已备份可随时回退。
2. 若测验仍然跳过，把日志中 `跳过`/`已完成`/`没有任务点标记`/`处理出错` 那几行发来：
   4.13 已给每个分支加了原因，一眼能定位。
3. 修第 7 节 2–5（作业多课程 / 单选框索引 / 关窗停子进程 / 直播时长 / 签到首跑），
   这几项都需要真机确认，建议一次一项。
4. 给「驱动获取失败」补界面提示（目前只在日志里）。

---

## 11. 产物与数据（当前机器）

- `dist/start.exe`：2026-10-31 23:16:11，63,521,549 字节（「课程学习助手 / **26.10.31.2313**」），
  `--selftest` PASS；含 4.8–4.29。
- 历史备份：`start-26.10.31.2253.exe`、`start-26.10.31.2219.exe`、`start-26.10.31.1844.exe`、
  `start-26.10.31.1817.exe`、`start-26.10.31.1741.exe`、`start-26.10.31.1711.exe`、
  `start-26.10.31.1659.exe`、`start-26.10.31.1644.exe`、`start-26.10.31.1618.exe`、
  `start-26.10.31.1608.exe`、`start-26.10.31.1558.exe`、`start-26.10.31.1537.exe`、
  `start-26.10.31.1526.exe`、`start-26.10.31.1250.exe`、`start-26.10.31.1228.exe`、
  `start-26.10.30.2256.exe`、`start-26.10.30.2125.exe`。
- `%LOCALAPPDATA%\XuexitongShuake`：2 个账号（`acc_0540745e`、`acc_8ac0c5bc`），含 `.migrated`、
  `selftest.log`、`error.log`、`输出记录.log`；旧记录名会在启动时自动改为新名。
  注意：这里的 `tool/accounts.json` 是**明文**手机号+密码+API Key，不要外发、不要提交。
- 工程内不再保留真实手机号、旧版数据副本、编译缓存与构建中间产物。
- 没有 git 仓库；以文件为准。
