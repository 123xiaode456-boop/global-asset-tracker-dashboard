# 全球资产判断系统跟踪总结

本项目用于归档知识星球数据总表，解析每日 PDF/XLSX，写入 SQLite，生成观察日报，并通过本地仪表盘和 GitHub Pages 公网版查看资产指标曲线。

## 当前状态

- 已归档说明书和补充 PDF：`data/raw/source_docs`
- 最新核心数据集：2026-08-28，235 行
- 最新内地主连：2026-08-28，28 行
- 最新押注工具（ETF 独立板块）：2026-08-19，1037 行
- 数据库：`data/processed/signals.sqlite`
- 日报：`data/reports/2026-06-09_core.md`、`data/reports/2026-06-09_betting.md`

## 每日流程

1. 把当天 PDF/XLSX 放到固定收件箱的日期子目录，或直接传给 Codex 后让我保存：

```text
data/inbox/YYYY-MM-DD/
```

例如：

```text
data/inbox/2026-06-22/
```

2. 运行导入脚本：

```powershell
.\scripts\import_daily.ps1 -Path "D:\Workspace\project-027-全球资产判断系统跟踪总结\工程内容\data\inbox\2026-06-22\*.xlsx"
```

归档、导入、行情更新、静态数据导出和公网发布也可以一次完成：

```powershell
.\scripts\update_daily_site.ps1 -Path <当天文件列表> -Publish
```

文件名包含“押注工具”时会自动识别为 ETF 数据集并更新“ETF 押注工具”分页；核心数据和内地主连仍只进入原商品板块。

3. 同步能自动匹配的免费行情：

```powershell
.\scripts\fetch_prices.ps1
```

也可以只同步一个标的：

```powershell
.\scripts\fetch_prices.ps1 -Asset "SPY|SPDR S&P 500 ETF Trust"
```

如果某个标的出现在“待映射”页，可以先手工绑定行情 symbol：

```powershell
.\scripts\map_symbol.ps1 -Asset "GC1!|Gold Futures" -Symbol "GC=F" -Source "yfinance"
.\scripts\fetch_prices.ps1 -Asset "GC1!|Gold Futures"
```

4. 打开或刷新仪表盘：

```powershell
.\scripts\start_dashboard.ps1
```

默认仪表盘地址：`http://localhost:8507`

## 公开网站部署

如需把仪表盘部署成可发给别人访问的公网网站，查看：

```text
docs/公开部署说明.md
```

部署版本默认上传处理后的 `data/processed/signals.sqlite`，不上传 `data/raw/` 和 `data/inbox/` 原始 Excel/PDF。若需要限制访问，在云平台设置环境变量：

```text
ASSET_TRACKER_PASSWORD=你的密码
```

## GitHub Pages 静态版

如果要像“国内商品期货波动率网页”一样通过 GitHub Pages 发公网链接，使用静态版：

公网 v2 地址：

```text
https://123xiaode456-boop.github.io/global-asset-tracker-dashboard/v2/
```

```powershell
$env:PYTHONPATH="D:\Workspace\project-027-全球资产判断系统跟踪总结\工程内容\src"
.\.venv\Scripts\python.exe .\src\export_static_site.py
.\.venv\Scripts\python.exe .\scripts\publish_static_pages.py
```

输出目录：

```text
site/
```

静态版包含商品总览、机会排名、早期转折、期货品种四象限分图、三级别趋势、动量状态和独立 ETF 押注工具分页。数据按日期和页面拆分，首屏只加载清单、当前快照和当前期货数据；趋势、动量、ETF 与价格历史在进入对应页面时按需加载。全部历史数据仍保留，公网不再下载旧的 82MB 单体文件。发布脚本会同步完整分片目录并清理过期分片，公网网址保持不变。

### 动能跟踪板块（2026-08-30）

导航新增“动能跟踪”，集中展示四个源表字段：当前动能状态、动能数值、当前动能状态持续时间（bar）、当前动能状态累积涨跌幅（%）。覆盖核心表和内地主连全部标的，支持数据来源、状态、名称/代码及 bar=1 筛选；原“动量状态”与 ETF 分页保留。

查看历史时才加载近 30 天的动能分片，显示动能数值、持续 bar、累计涨跌幅三张共享日期轴的图及历史明细。数据按“数据集类型＋标的键”匹配，避免同代码串线；使用完整动能日期（含内地主连独有日期），缺记录保留空值，真实零值显示 0，百分数沿用源表口径。切换日期加载失败时清空旧日期值并提示重试。

## 手动命令

```powershell
$env:PYTHONPATH="D:\Workspace\project-027-全球资产判断系统跟踪总结\工程内容\src"
$py="C:\Users\janzh\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
& $py -m asset_tracker import "data\raw\2026-06-09"
& $py -m pytest
```

## 数据边界

- 本项目只做数据整理、状态观察和复盘记录，不构成投资建议。
- Excel 是首选源；PDF 可作为兜底源。
- 行情源第一版采用免费源映射，无法自动映射的标的会进入待映射队列。

## 单资产页

- 顶部“当天结论”按日级别趋势给出：上行趋势 = 可做多，下行趋势 = 可做空，无趋势 = 不做/观望。
- 中部展示行情价格和星球指标曲线；没有行情映射时仍展示星球指标。
- 底部展示四象限轨迹：横轴为 `相对强度 - 100`，纵轴为 `强度动量 - 100`，并附带日期横轴的象限坐标变化曲线。
