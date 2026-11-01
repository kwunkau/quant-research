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
    get_ipython().system("pip -q install baostock==0.9.1 statsmodels")
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
from src.config import KEY_DATES

for d in KEY_DATES:
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
    s = ic_stats(fac, mask, feats["adj"])  # 复权价格，避免份额折算日的假跳空
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
facts = res["review_2026"]["facts"]
print("2026-06-30 综合因子前 5：", "、".join(x["name"] for x in facts["top5_composite_0630"]))
print("2026-06-30 5000 万实际持仓：", "、".join(x["name"] for x in facts["holdings_net_0630"]))
monthly = pd.DataFrame({"5000万综合因子": facts["strategy_monthly"],
                        "等权基准": facts["benchmark_monthly"]})
(monthly * 100).round(1)
'''

INDUSTRY = r'''
ind = res["industry"]
rows = [{"组合": k, "本地年化": ind["avg"][k]["cagr"], "本地回撤": ind["avg"][k]["mdd"],
         "研报年化": res["report_ref"][k]["cagr"], "研报回撤": res["report_ref"][k]["mdd"]}
        for k in ["base", "composite"]]
rows.append({"组合": "benchmark", "本地年化": ind["benchmark"]["cagr"], "本地回撤": ind["benchmark"]["mdd"],
             "研报年化": res["report_ref"]["benchmark"]["cagr"], "研报回撤": res["report_ref"]["benchmark"]["mdd"]})
print(f"新浪 {ind['n_boards']} 个行业板块资金流，{ind['start']} ~ {ind['end']}，W=20–24 平均")
pd.DataFrame(rows).round(4)
'''

CHARTS = r'''
from src.charts import build_all
from IPython.display import Image, display

build_all()
for name in ["fig1_nav.png", "fig2_flowmap.png", "fig3_review2026.png", "fig4_capacity.png"]:
    display(Image(filename=f"output/figures/{name}"))
'''

TAKEAWAYS = r'''
p, ic, rv = res["performance"], res["ic"], res["review_2026"]
gb, gc, nc, bm = (p["gross_base"], p["gross_composite"],
                  p["net_composite_50m"], p["benchmark_gross"])
ref = res["report_ref"]
key = pd.DataFrame(rv["key_dates"])
pct = lambda x: f"{x * 100:.1f}%"

lines = [
    f"1. 绝对收益未复现：理论组合年化 基础 {pct(gb['cagr'])} / 综合 {pct(gc['cagr'])} / "
    f"基准 {pct(bm['cagr'])}，研报为 {pct(ref['base']['cagr'])} / {pct(ref['composite']['cagr'])} / "
    f"{pct(ref['benchmark']['cagr'])}。",
    f"2. 改进方向复现：综合较基础收益 {(gc['cagr'] - gb['cagr']) * 100:+.1f} pct，最大回撤 "
    f"{pct(gb['mdd'])} → {pct(gc['mdd'])}；Rank IC {ic['base']['mean_ic']:.3f} → "
    f"{ic['composite']['mean_ic']:.3f}（t={ic['composite']['ic_t']:.2f}）。",
    f"3. 5000 万可执行性：净年化 {pct(nc['cagr'])}、最大回撤 {pct(nc['mdd'])}、"
    f"成本拖累 {pct(nc['cost_drag_annual'])}，相对基准 {nc['excess_vs_benchmark'] * 100:+.1f} pct；"
    f"bootstrap 95% 区间 [{res['bootstrap_excess']['annualized_ci_low'] * 100:+.1f}, "
    f"{res['bootstrap_excess']['annualized_ci_high'] * 100:+.1f}] pct/年，不显著。",
    f"4. 广度拐点未复现：本地半导体广度 "
    + " / ".join(f"{v * 100:.0f}%" for v in key["semi_breadth"])
    + f"，研报为 {ref['semi_breadth_path']}。",
    f"5. 识别问题：N={res['meta']['problem_size']['n_industries']} 时 "
    f"{res['meta']['problem_size']['n_params']} 个参数对 "
    f"{res['meta']['problem_size']['n_equations']} 个方程，拟合误差小不能当作模型有效的证据。",
    f"6. 行业口径（新浪 {res['industry']['n_boards']} 个行业主动买卖资金流，{res['industry']['start']}–{res['industry']['end']}）："
    f"原始 {pct(res['industry']['avg']['base']['cagr'])} / 综合 {pct(res['industry']['avg']['composite']['cagr'])} / "
    f"基准 {pct(res['industry']['benchmark']['cagr'])}，换回主动买卖数据仍未复现。",
]
for line in lines:
    print(line)
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
        nbf.v4.new_markdown_cell(
            "## 5b. 行业口径复现（补数据）\n\n"
            "用新浪行业板块的逐笔主动买卖资金流，在研报同区间、同规则下重做"
            "（流向图逐日求解快照随仓库提交，见 `data/raw/ind_flow_micro_snapshot.csv`）。"),
        nbf.v4.new_code_cell(INDUSTRY),
        nbf.v4.new_markdown_cell("## 6. 图表"),
        nbf.v4.new_code_cell(CHARTS),
        nbf.v4.new_markdown_cell("## 7. 结论（由 results.json 渲染，与报告一致）"),
        nbf.v4.new_code_cell(TAKEAWAYS),
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
