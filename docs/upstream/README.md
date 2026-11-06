# 上游对比数据存档

这里保存 2026-11-06 拉取上游 [Mortal004/Xuexitong_shuake](https://github.com/Mortal004/Xuexitong_shuake)
时得到的**小体积分析依据**，用于支撑本仓库的两份对比文档：

- [../上游对比与合入计划_2026-11-06.md](../上游对比与合入计划_2026-11-06.md)
- [../本地定制版与上游源码对比_2026-11-06.md](../本地定制版与上游源码对比_2026-11-06.md)

| 文件 | 内容 |
|---|---|
| `commits.json` | 上游最近 100 条提交（SHA / 日期 / 说明） |
| `commit_<sha>.json` | 14 个关键提交的逐文件 patch |
| `releases.json` | Release `26.11.04` 元数据 |
| `diff_report.json` | 上游 master 与本地工程的文件级哈希 / 行级相似度报告 |
| `comparison_data.md` | 逐文件差异明细（含本地新增函数/类与日志章节索引） |
| `compare.py` / `build_comparison.py` | 生成上面两份报告的分析脚本（存档用） |

**说明**

- 上游源码包（6.45 MB）、解压副本与 Release 资产包（88 MB）体量太大，未入库；
  需要复核时按 [`../上游对比与合入计划_2026-11-06.md`](../上游对比与合入计划_2026-11-06.md)
  第 8 节的命令重新拉取即可（本机代理 `socks5h://127.0.0.1:10808`）。
- `compare.py` / `build_comparison.py` 里的路径指向当时的 `_upstream/` 目录，
  作为存档保留；若重新运行，请先按实际目录调整常量 `BASE` / `UP` / `OUT`。
- `commits.json` 与 `commit_*.json` 是 GitHub API 原始返回，不含任何账号凭据。
