# 课程学习助手（定制分支）

Windows 桌面程序：`customtkinter` 图形界面 + Selenium 课程学习内核 + 自动签到子系统。
本仓库是基于上游 [Mortal004/Xuexitong_shuake](https://github.com/Mortal004/Xuexitong_shuake) 的**深度定制分支**。

> **免责声明**：本项目仅供学习与研究使用。使用者应遵守所在学校的相关规定，合理安排学习时间，
> 不得用于 24 小时高强度挂机或替他人刷课。平台风控日益严格，已有账号被封禁的案例；
> 因使用本程序导致的账号、成绩或法律风险由使用者自行承担。详见 [LICENSE](LICENSE)。

## 与上游的关系

| | 上游 master 源码 | 本仓库 |
|---|---|---|
| 基线 | `26.10.13`（2026-10-14 大版本） | 同基线，之后独立演进 |
| 版本串 | `26.10.13` | 打包时刻 `YY.MM.DD.HHMM` |
| 形态 | 源码 | 源码 + PyInstaller 单文件 exe |
| 测试 | 无 | 18 个测试脚本（16 个套件） |
| 日志 | 界面输出 | 主日志 + 单账号明细 + 单日一键导出 |

本地新增了统一路径 / 数据目录、主日志系统、浏览器驱动探测、多账号子进程隔离、
课程误结束修复、签到降频（避免高频请求）、一键导出完整日志、单文件打包与自检等能力。
**上游 Release `26.11.04` 的复习模式、问卷随机答题、邮箱提醒只发布了二进制，源码未同步，
因此本仓库不包含这些功能。**

详细差异见 [docs/本地定制版与上游源码对比_2026-11-06.md](docs/本地定制版与上游源码对比_2026-11-06.md)，
上游更新与合入评估见 [docs/上游对比与合入计划_2026-11-06.md](docs/上游对比与合入计划_2026-11-06.md)。

## 主要功能

- 自动完成视频 / PPT / 音频 / 阅读 / 讨论 / 直播 / 作业 / 章节测验
- 答题优先查免费题库，DeepSeek AI 兜底；图片题走多模态；特殊题与简答题有频率限流
- 自动签到（普通签到 / 位置签到），30 秒基础间隔 + 空闲退避 + 4 小时自动停止
- 多账号并发，每个账号独立子进程与独立数据目录
- 7 套主题皮肤、定时刷课、课程进度查看
- 主日志记录完整时间线；界面「⇩ 导出完整日志」一键导出单日 zip（自动脱敏）

## 环境要求

- Windows（本机验证环境：Windows 11 / Python 3.15.1）
- Python 3.x + 与浏览器版本匹配的 Edge / Chrome 驱动
- 依赖见 [requirements.txt](requirements.txt)

```powershell
pip install -r requirements.txt
```

## 快速开始

配置模板以 `*.example.json` 提供。首次运行前先复制成真实文件名（**这些文件会被 `.gitignore` 排除，
填写真实账号后切勿提交**）：

```powershell
Get-ChildItem task\tool\*.example.json | ForEach-Object {
    Copy-Item $_.FullName ($_.FullName -replace '\.example\.json$', '.json')
}
python start.py
```

打包版的数据目录是 `%LOCALAPPDATA%\XuexitongShuake`，exe 旁边不写任何文件，
可以放在只读目录、桌面或 U 盘直接运行。

## 打包与自检

```powershell
python -m PyInstaller start.spec --clean --noconfirm
.\dist\start.exe --selftest
```

`dist/` 与 `build/` 不入库，发布请用 GitHub Release。

## 测试

```powershell
python tests\run_stub_tests.py
```

`run_stub_tests.py` 跑全部纯桩套件（不联网、不开浏览器）。
`test_image_answer.py` / `test_quiz_image.py` / `test_quiz_selector.py` 需要真实 Edge 与匹配驱动，
默认跳过；本机驱动版本不匹配时它们会报 `unhandled request`，属环境问题。

## 目录结构

```
├── main.py / start.py        学习内核 / 图形界面入口
├── core/                    路径、日志、驱动、多账号、日志导出
├── gui/                     界面页面与主题
├── task/                    各内容处理器、答题链路、签到子系统、资源
├── tests/                   回归测试
├── docs/                    交接文档、更新日志历次记录、诊断与对比报告
├── scripts/                 独立日志导出脚本
├── start.spec               单文件打包配置
├── requirements.txt
└── CHANGELOG.md / CONTRIBUTING.md / LICENSE
```

## 文档

- [更新日志（完整 21 个版本）](docs/更新日志.md) · [CHANGELOG 摘要](CHANGELOG.md)
- [工程交接文档（架构 / 历史 / 踩坑 / 未修问题）](docs/AGENT_HANDOVER.md)
- [贡献与迭代约定](CONTRIBUTING.md)
- [本地定制版与上游源码对比](docs/本地定制版与上游源码对比_2026-11-06.md) ·
  [上游对比与合入计划](docs/上游对比与合入计划_2026-11-06.md)
- [上游对比数据存档](docs/upstream/README.md)

## 许可

见 [LICENSE](LICENSE)。上游项目为非商业使用许可，本分支沿用。
