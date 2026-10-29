# 主动性买盘与沪深300指数次日走势（kwunkau_day01）

量化研究作业 `kwunkau_day01`。研究 2012-01-04 至 2026-10-28 共 3,591 个交易日，
检验"主动性买盘"与沪深300指数次日涨跌之间是否存在显著统计关联。

## 结论摘要

| 检验 | 结果 |
|---|---|
| 主买净流入率 vs **当日**收益 | Pearson 0.750，R² = 0.563，t = 36.0（高度同步） |
| 主买净流入率 vs **次日**收益 | Pearson 0.024，p = 0.156，95% CI [-0.015, 0.064]（不显著） |
| 控制当日收益/波动/成交额后 | 系数 t = 0.49，p = 0.623 |
| 十分位多空价差 | 15.5 bp，t = 1.39，p = 0.166 |
| 15 项预测性检验（BH 校正） | 原始显著 1 项 → 校正后 **0 项** |

日频主动性买盘主要是**价格的结果**（当日成交过程的归纳），而非次日走势的先兆。
详见 `output/kwunkau_day01_report.pdf`。

## 目录结构

```
kwunkau_day01/
├── run_all.py            # 一键复现入口（抓数→特征→分析→图表→报告）
├── requirements.txt
├── src/
│   ├── config.py         # 路径、区间、字体、常量
│   ├── fetch_data.py     # 新浪板块资金流 + baostock 指数日线（带回重试与缓存）
│   ├── build_features.py # 收益、NBI、超大单、分歧、滚动标准化、牛熊标记
│   ├── analysis.py       # 相关、HAC 回归、十分位、状态划分、BH 校正
│   ├── charts.py         # 图 1–5
│   └── make_report.py    # HTML 模板 → Playwright 打印 PDF
├── data/
│   ├── raw/              # 原始快照（CSV，含抓取元信息）
│   └── processed/        # dataset.csv（建模用）
└── output/
    ├── figures/          # 图 1–5（PNG）
    ├── tables/           # t01–t09 统计表
    ├── results.json      # 报告引用的全部统计结果
    ├── kwunkau_day01_research.ipynb  # 自包含 Notebook（Colab 打开）
    ├── kwunkau_day01_report.html  # 报告源码
    └── kwunkau_day01_report.pdf   # 交付报告（5 页）
```

## 环境与复现

需要 Python 3.12+。依赖隔离在虚拟环境中，首次安装一次即可：

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt      # Windows: .venv\Scripts\pip

python run_all.py            # 用缓存，约 15 秒
python run_all.py --refresh  # 重新抓取全部原始数据，约 1 分钟
```

`run_all.py` 会校验当前解释器是否在虚拟环境中、Python 是否 ≥ 3.12，不满足时给出命令提示并退出。
完整流程也可作为单个 Notebook 打开：`output/kwunkau_day01_research.ipynb`。

**Notebook 在线查看（nbviewer）**：`https://nbviewer.org/github/kwunkau/quant-research/blob/main/kwunkau_day01/output/kwunkau_day01_research.ipynb`

**Notebook 在线运行（Colab）**：`https://colab.research.google.com/github/kwunkau/quant-research/blob/main/kwunkau_day01/output/kwunkau_day01_research.ipynb`

**仓库**：`https://github.com/kwunkau/quant-research`

## 数据来源与口径

| 数据 | 接口 | 区间 | 记录数 |
|---|---|---|---|
| 沪深300板块日度资金流 | 新浪财经 `MoneyFlow.ssl_bkzj_zjlrqs?bankuai=hs300` | 2010-03-08 ~ 2026-10-29 | 4,038 |
| 沪深300指数日线 | baostock `sh.000300` | 2011-12-01 ~ 2026-10-29 | 3,619 |

- 东方财富"主力资金"历史接口目前仅保留最近 121 个交易日，无法覆盖 2012 年至今，故未采用。
- 数据一致性校验：`净额 ÷ 净流入率` 反推成交额 / 指数实际成交额，中位数 0.992，相关系数 0.993。
- baostock 的 `ResultData.get_data()` 在 pandas 2.x 下会因 `df.append` 报错，本项目改为逐行读取。

## 指标定义

- **NBI（主买净流入率）** = 主动买入净额 ÷ 成交额，无量纲，可跨期比较。
- **R0** = 超大单净流入率；**D** = R0 − NBI，度量大单与全单的方向分歧。
- **Z** = NBI 的滚动 250 日标准化值（仅用 t 日及以前数据，无前视）。

## 方法

Pearson/Spearman + 移动块 bootstrap（500 次、块长 20）置信区间；Newey-West HAC(5) 回归；
按 Z 十分位分组与多空价差检验；牛熊（250 日均线）× 波动三分位划分；
对 15 项预测性检验做 Benjamini-Hochberg 校正。

## 局限

1. 板块口径为数据商聚合，若成分回溯方式含幸存者偏差，历史序列与真实可投资集合存在差异。
2. 日频聚合抹平日内信息，尾盘主动买盘的信息含量未被检验。
3. 数据商以单笔金额分层 + 价格方向近似"主动方"，非严格逐笔 Lee-Ready 判定。

## 说明

本研究为课程作业，不构成任何投资建议。所有数字均由 `src/analysis.py` 实际计算并写入
`output/results.json`，报告正文从该文件读取，未手工填写。
