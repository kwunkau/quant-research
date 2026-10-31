"""生成并执行自包含 Notebook（Colab / 本地均可运行）。

Notebook 通过公开仓库的 src/ 包复现全流程；首个代码单元自适应安装依赖与中文字体，
数据优先读 data/raw/ 快照，缺失时联网抓取，失败则提示上传 CSV。
"""

from __future__ import annotations

import os
from pathlib import Path

import nbformat as nbf
from nbclient import NotebookClient

from .config import OUTPUT, PROJECT_ID

SETUP = r'''
import os, sys
from pathlib import Path

IN_COLAB = "google.colab" in sys.modules

if IN_COLAB:
    get_ipython().system("pip -q install baostock statsmodels")
    get_ipython().system("apt-get -qq install -y fonts-wqy-zenhei > /dev/null")
    repo = Path("/content/quant-research")
    if not repo.exists():
        get_ipython().system("git clone -q https://github.com/kwunkau/quant-research /content/quant-research")
    os.chdir(repo / "kwunkau_day02")
else:
    if Path("src").exists():
        pass
    elif Path("kwunkau_day02/src").exists():
        os.chdir("kwunkau_day02")

if not Path("src").exists():
    raise RuntimeError(
        "未找到项目目录。请把 kwunkau_day02 整个目录（含 src/ 与 data/raw/）上传后，"
        "在 kwunkau_day02 目录下重新运行；或使用 Google Colab 直接运行本 Notebook。"
    )

import warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

pd.set_option("display.width", 140)
pd.set_option("display.max_columns", 30)
print("环境就绪：", "Colab" if IN_COLAB else "本地")
'''

DATA = r'''
from src.fetch_data import fetch_etf_daily, fetch_sina_flow

try:
    daily = fetch_etf_daily()
except Exception as exc:
    raise RuntimeError(
        "ETF 日线不可用。请把 data/raw/etf_daily.csv 上传到同路径后重跑；"
        "或在可访问 baostock 的网络环境执行 python run_all.py --refresh。"
    ) from exc

meta = daily.groupby(["code", "name"]).agg(
    上市日=("date", "min"), 最新=("date", "max"), 行数=("date", "size")
)
print(f"ETF 日线：{len(daily):,} 行，{daily.code.nunique()} 只，"
      f"{daily.date.min():%Y-%m-%d} ~ {daily.date.max():%Y-%m-%d}")
meta.tail(6)
'''

FEATURES = r'''
from src.build_features import build_dataset, cross_section
from src.config import START_DATE, END_DATE

feats = build_dataset(daily)
mask = feats["mask"]
sub = mask.loc[START_DATE:END_DATE]
print(f"样本：{sub.index.min():%Y-%m-%d} ~ {sub.index.max():%Y-%m-%d}，"
      f"{len(sub):,} 个交易日")
print("每年平均可投 ETF 数：")
sub.sum(axis=1).groupby(sub.index.year).mean().round(1)
'''

FLOWMAP = r'''
from src.flowmap import run as run_flowmap, solve_day

fm = run_flowmap()          # 有缓存则直接读取；无缓存则逐日求解（约 10–15 分钟）
err = fm["errors"]
med = err.max_abs_err.median() * 1000
print(f"资金流向图：{len(err)} 个交易日，最大误差中位数 "
      f"{'<0.01‰' if med < 0.01 else f'{med:.2f}‰'}，"
      f"95 分位 {err.max_abs_err.quantile(.95)*1000:.2f}‰")

key = []
for d in ["2026-06-24", "2026-06-30", "2026-07-06"]:
    cs = cross_section(feats, pd.Timestamp(d))
    sol = solve_day(cs["Q"], cs["H"], cs["V"], cs["S"], n_random=5)
    b = fm["micro"].query("date == @d").set_index("code").breadth
    key.append({
        "日期": d, "标的数": len(cs["codes"]),
        "半导体广度": b.get("sh.512480"), "通信广度": b.get("sh.515880"),
        "最大误差(‰)": sol["max_abs_err"] * 1000,
    })
pd.DataFrame(key).round(4)
'''

BACKTEST = r'''
from src.backtest import build_factor_panels, run_engine
from src.analysis import perf_metrics, ic_stats

panels = build_factor_panels(feats, fm["micro"])
base, comp = panels["base_w20"], panels["composite_w20"]

gross_base = run_engine(feats, base, cost=False, cap=False)
gross_comp = run_engine(feats, comp, cost=False, cap=False)
bench = run_engine(feats, base, cost=False, cap=False, benchmark=True)
net_comp = run_engine(feats, comp, capital=50_000_000, cost=True, cap=True)

rows = []
for label, res in [("基础因子（毛）", gross_base), ("综合因子（毛）", gross_comp),
                   ("等权基准（毛）", bench), ("综合因子（5000万净）", net_comp)]:
    m = perf_metrics(res["nav"])
    rows.append({"组合": label, "年化": m["cagr"], "波动": m["vol"],
                 "夏普": m["sharpe"], "最大回撤": m["mdd"],
                 "期末(万元)": m["final_value"] / 1e4})
pd.DataFrame(rows).round(4)
'''

IC = r'''
ic_rows = []
for label, fac in [("基础因子", base), ("综合因子", comp)]:
    s = ic_stats(fac, mask, feats["close"].ffill())
    ic_rows.append({"因子": label, "RankIC": s["mean_ic"], "t值": s["ic_t"],
                    "IC>0占比": s["positive_share"]})
pd.DataFrame(ic_rows).round(4)
'''

CAPACITY = r'''
cap_rows = []
for aum in [10_000_000, 30_000_000, 50_000_000, 100_000_000, 200_000_000, 500_000_000]:
    r = run_engine(feats, comp, capital=aum, cost=True, cap=True)
    m = perf_metrics(r["nav"])
    cap_rows.append({"资金(万元)": aum / 1e4, "年化": m["cagr"],
                     "最大回撤": m["mdd"], "成本拖累": m["cost_drag_annual"],
                     "最大参与率": m["max_participation"], "受限天数": m["binding_days"]})
pd.DataFrame(cap_rows).round(4)
'''

REVIEW = r'''
import json
from src.config import OUTPUT

res = json.loads((OUTPUT / "results.json").read_text(encoding="utf-8"))
ytd = pd.DataFrame(res["review_2026"]["ytd"])
ytd["ytd"] = (ytd["ytd"] * 100).round(1)
ytd.head(8)
'''

CHARTS = r'''
from src.charts import build_all
from IPython.display import Image, display

build_all()
for name in ["fig1_nav.png", "fig2_flowmap.png", "fig3_review2026.png", "fig4_capacity.png"]:
    display(Image(filename=f"output/figures/{name}"))
'''

TAKEAWAYS = r'''
# 结论（与 results.json 一致）

- 公开 ETF 数据下，基础因子与综合因子都**没有复现**研报的 21.97% / 22.63% 年化与双位数超额；
  样本区间、标的池与数据口径（Wind 主动买卖 vs 量价代理）是主要差异来源。
- 5000 万元、参与率 ≤5% ADV、含佣金/价差/冲击后，收益进一步被成本与容量侵蚀；
  容量不是静态比例，而是“流动性差的行业先被挤出”的动态过程。
- 研报最可复用的不是五因子合成，而是**净流入为正比例**这一广度指标：
  2026-06-30 见顶、07-06 骤降，随后半导体 7 月 −34%。广度比强度更早反映分歧。
- 方法层面最大的警示是**识别问题**：流向图未知量远多于方程，
  “拟合误差 <5‰”不能当作模型有效的证据；最小二范数解是假设，不是事实。
'''


def build() -> Path:
    nb = nbf.v4.new_notebook()
    nb.cells = [
        nbf.v4.new_markdown_cell(
            "# 行业资金流向图：ETF 复现与 5000 万元模拟（kwunkau_day02）\n\n"
            "**问题**：用 18 只行业 ETF 的公开数据，复现华泰证券《行业资金流向图应用于行业轮动》"
            "的两层构造，并在 5000 万元、参与率 ≤5% ADV 的约束下检验可执行性。\n\n"
            "**数据**：baostock 行业 ETF 日线（2020-01-02–2026-10-30）+ 新浪单只 ETF 资金流"
            "（2025-02 起，用于代理校验与 2026 案例）。\n\n"
            "**说明**：本 Notebook 通过公开仓库的 `src/` 包运行；若在 Colab 打开，"
            "首个代码单元会自动安装依赖、克隆仓库并切换目录。"
        ),
        nbf.v4.new_markdown_cell("## 0. 环境与路径（Colab 自适应）"),
        nbf.v4.new_code_cell(SETUP),
        nbf.v4.new_markdown_cell("## 1. 数据"),
        nbf.v4.new_code_cell(DATA),
        nbf.v4.new_markdown_cell("## 2. 特征与可投域"),
        nbf.v4.new_code_cell(FEATURES),
        nbf.v4.new_markdown_cell(
            "## 3. 行业资金流向图\n\n"
            "流向图逐日求解；若 `data/processed/flow_micro.csv` 不存在，会重新求解"
            "（约 10–15 分钟，取决于机器）。下表是研报三个示例日期的本地结果。"
        ),
        nbf.v4.new_code_cell(FLOWMAP),
        nbf.v4.new_markdown_cell("## 4. 回测与 5000 万元模拟"),
        nbf.v4.new_code_cell(BACKTEST),
        nbf.v4.new_code_cell(IC),
        nbf.v4.new_code_cell(CAPACITY),
        nbf.v4.new_markdown_cell("## 5. 2026 年复盘"),
        nbf.v4.new_code_cell(REVIEW),
        nbf.v4.new_markdown_cell("## 6. 图表"),
        nbf.v4.new_code_cell(CHARTS),
        nbf.v4.new_markdown_cell(TAKEAWAYS),
    ]
    nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3",
                                 "language": "python"}
    nb.metadata["language_info"] = {"name": "python"}

    out = OUTPUT / f"{PROJECT_ID}_research.ipynb"
    nbf.write(nb, str(out))
    print(f"[notebook] 写入 {out}，开始执行…")
    client = NotebookClient(nb, timeout=1800, kernel_name="python3",
                            resources={"metadata": {"path": str(out.parent.parent)}})
    client.execute()
    nbf.write(nb, str(out))
    print(f"[notebook] 执行完成 {out}")
    return out


if __name__ == "__main__":
    build()
