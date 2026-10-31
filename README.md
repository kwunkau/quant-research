# 量化研究作业集

本仓库按作业编号存放 `kwunkau_dayNN/` 目录，每次作业包含研究报告、Notebook 与可复现代码。

| 作业 | 主题 | 交付物 |
|---|---|---|
| [kwunkau_day01](./kwunkau_day01/) | 主动性买盘与沪深300指数次日走势（2012–2026） | [报告 PDF](./kwunkau_day01/output/kwunkau_day01_report.pdf) ｜ [Notebook](./kwunkau_day01/output/kwunkau_day01_research.ipynb) |
| [kwunkau_day02](./kwunkau_day02/) | 行业资金流向图：ETF 复现与 5000 万元模拟（2020–2026） | [报告 PDF](./kwunkau_day02/output/kwunkau_day02_report.pdf) ｜ [Notebook](./kwunkau_day02/output/kwunkau_day02_research.ipynb) |

## 在线查看 Notebook

- day01：`https://nbviewer.org/github/kwunkau/quant-research/blob/main/kwunkau_day01/output/kwunkau_day01_research.ipynb`
- day02：`https://nbviewer.org/urls/raw.githack.com/kwunkau/quant-research/main/kwunkau_day02/output/kwunkau_day02_research.ipynb`

## 复现

```bash
cd kwunkau_day01
python -m venv .venv
.venv/bin/pip install -r requirements.txt      # Windows: .venv\Scripts\pip
python run_all.py
```
