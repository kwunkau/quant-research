# kwunkau_day02

华泰证券《行业资金流向图应用于行业轮动》的 ETF 复现、5000 万元资金模拟与研读心得。

## 研究问题

1. 用公开 ETF 数据能否复现研报的主动净买入因子及“资金流向图”改进？
2. 5000 万元资金扣除佣金、价差与冲击后是否仍有超额？容量边界在哪？
3. 研报对 2026 年 6–7 月 AI 硬件主线“缩圈→共识→松动”的判断，在 ETF 层面是否成立？

## 数据

- 18 只行业/主题 ETF 日线（baostock，2020-01-02 至 2026-10-30，含成交额、换手率、涨跌幅）。
- 新浪单只 ETF 主力资金流（2025-02-06 起），用于代理校验与 2026 案例。
- 原始数据快照抓取日期：2026-10-31；`data/raw/*.csv` 已随仓库提交，可离线重跑。
- `data/raw/flow_micro_snapshot.csv` 与 `flow_errors_snapshot.csv` 是资金流向图的求解快照，
  无本地缓存时 Notebook 直接读取，避免在 Colab 重跑 10–15 分钟；`--refresh` 会重新求解。

## 交付物

| 对象 | 路径 |
|---|---|
| 报告 | `output/kwunkau_day02_report.pdf` |
| Notebook | `output/kwunkau_day02_research.ipynb` |
| 需求文档 | `需求.md` |
| 结果文件 | `output/results.json` |

## 复现

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt      # Windows: .venv\Scripts\pip
python run_all.py
```

- 默认读取 `data/raw/` 快照，离线可跑。
- `python run_all.py --refresh` 重新抓取；若新浪资金流接口不可用，长样本回测不受影响，
  但 2026 案例对照会跳过并在日志中提示。
- 全样本资金流向图逐日求解约 10–15 分钟；缓存位于 `data/processed/flow_micro.csv`。

## 在线查看

nbviewer：`https://nbviewer.org/github/kwunkau/quant-research/blob/main/kwunkau_day02/output/kwunkau_day02_research.ipynb`

## 说明

华泰研报 PDF 为第三方付费研究，未随仓库分发；报告仅引用其标题、日期与公开结论。
