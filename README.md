# 全球资产判断系统跟踪总结

本项目用于归档知识星球数据总表，解析每日 PDF/XLSX，写入 SQLite，生成观察日报，并用 Streamlit 仪表盘查看资产指标曲线。

## 当前状态

- 已归档说明书和补充 PDF：`data/raw/source_docs`
- 已导入 2026-06-09 样本：
  - 核心数据集：235 行
  - 押注工具：959 行
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

公网地址：

```text
https://123xiaode456-boop.github.io/global-asset-tracker-dashboard/
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

静态版包含总览、机会排名、资产表、期货品种四象限分图。每日导入新 Excel 后，需要重新运行导出脚本并发布 `site/`。

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
