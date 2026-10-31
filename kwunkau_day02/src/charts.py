"""图表：净值、资金流向图、2026 复盘、容量曲线。

配色约定：红 = 净流入/上涨，蓝 = 净流出/下跌，灰 = 基准/中性。
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.dates as mdates
import matplotlib.patheffects as pe

from .config import FIG_DIR, OUTPUT, TABLE_DIR, ensure_dirs, setup_matplotlib
from .fetch_data import fetch_etf_daily
from .build_features import build_dataset, cross_section
from .flowmap import solve_day

RED = "#C0504D"
BLUE = "#2F6F8F"
GRAY = "#8A8A8A"
INK = "#333333"
DIVERGING = LinearSegmentedColormap.from_list(
    "div", ["#2F6F8F", "#E8EFF3", "#F2F2F2", "#F3E3E2", "#C0504D"]
)
SEQUENTIAL = LinearSegmentedColormap.from_list("seq", ["#DCE8EF", "#1F4F66"])


def _save(fig, name: str) -> None:
    path = FIG_DIR / name
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"[charts] {path.name}")


def fig_nav() -> None:
    nav = pd.read_csv(OUTPUT / "nav_curves.csv", index_col=0, parse_dates=True)
    res = json.loads((OUTPUT / "results.json").read_text(encoding="utf-8"))
    fig, axes = plt.subplots(2, 1, figsize=(9.4, 5.6), sharex=True,
                             gridspec_kw={"hspace": 0.28})

    ax = axes[0]
    for col, label, color, lw in [
        ("gross_base", "基础因子（W=20）", GRAY, 1.1),
        ("gross_composite", "资金流向综合因子（W=20）", RED, 1.5),
        ("benchmark", "行业等权基准", BLUE, 1.3),
    ]:
        ax.plot(nav.index, nav[col] / nav[col].iloc[0], label=label, color=color, lw=lw)
    ax.set_ylabel("累计净值（起点=1）")
    ax.set_title("A　理论组合（未计成本与容量）", loc="left", fontsize=10, color=INK)
    ax.legend(frameon=False, fontsize=8, loc="upper left")

    ax = axes[1]
    for col, label, color, lw in [
        ("net_base", "5000 万 · 基础因子", GRAY, 1.1),
        ("net_composite", "5000 万 · 综合因子", RED, 1.5),
        ("benchmark", "等权基准", BLUE, 1.3),
    ]:
        ax.plot(nav.index, nav[col] / nav[col].iloc[0], label=label, color=color, lw=lw)
    ax.set_ylabel("累计净值（起点=1）")
    ax.set_title("B　5000 万元模拟（佣金+价差+冲击，参与率≤5% ADV）",
                 loc="left", fontsize=10, color=INK)
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    fig.suptitle("图1　ETF 行业轮动：信号、成本与容量的三层对照", x=0.01, ha="left",
                 fontsize=11.5, color=INK)
    _save(fig, "fig1_nav.png")


SHORT_NAMES = {
    "半导体ETF": "半导体", "证券ETF": "证券", "银行ETF": "银行", "酒ETF": "酒",
    "消费ETF": "消费", "医疗ETF": "医疗", "医药ETF": "医药", "军工ETF": "军工",
    "有色金属ETF": "有色", "通信ETF": "通信", "传媒ETF": "传媒", "房地产ETF": "地产",
    "煤炭ETF": "煤炭", "光伏ETF": "光伏", "新能源车ETF": "新能车", "游戏ETF": "游戏",
    "新能源ETF": "新能源", "电力ETF": "电力",
}


def _draw_flow_map(ax, q, pairs, codes, names, title, top_edges=26):
    n = len(codes)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False)
    pos = {i + 1: (np.cos(a), np.sin(a)) for i, a in enumerate(angles)}
    pos[0] = (0.0, 0.0)

    order = np.argsort(-np.abs(q))[:top_edges]
    qmax = np.max(np.abs(q)) if len(q) else 1.0
    for k in order:
        i, j = pairs[k]
        if abs(q[k]) < 1e-12:
            continue
        color = RED if q[k] > 0 else BLUE
        lw = 0.4 + 2.6 * abs(q[k]) / qmax
        ax.annotate(
            "", xy=pos[i], xytext=pos[j],
            arrowprops=dict(arrowstyle="-|>", color=color, lw=lw, alpha=0.55,
                            shrinkA=4, shrinkB=4),
        )

    for i in range(n + 1):
        x, y = pos[i]
        is_ext = i == 0
        ax.scatter([x], [y], s=210 if is_ext else 70,
                   color="#E8EDF0" if is_ext else "#F4F7F9",
                   edgecolor=INK, linewidth=0.6, zorder=3)
        full = "外部" if is_ext else names[codes[i - 1]]
        label = "外部" if is_ext else SHORT_NAMES.get(full, full.replace("ETF", ""))
        if is_ext:
            lx, ly, ha, va = x, y, "center", "center"
        else:
            lx, ly = x * 1.14, y * 1.14
            ha = "left" if x > 0.12 else ("right" if x < -0.12 else "center")
            va = "bottom" if y > 0.12 else ("top" if y < -0.12 else "center")
        ax.text(lx, ly, label, ha=ha, va=va,
                fontsize=6.6 if not is_ext else 7.0, color=INK, zorder=4,
                path_effects=[pe.withStroke(linewidth=1.6, foreground="white")])
    ax.set_xlim(-1.38, 1.38)
    ax.set_ylim(-1.38, 1.38)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(title, fontsize=9, color=INK)


def fig_flowmap() -> None:
    feats = build_dataset(fetch_etf_daily())
    names = feats["meta"]["name"].to_dict()
    dates = ["2026-06-24", "2026-06-30", "2026-07-06"]
    fig, axes = plt.subplots(1, 3, figsize=(9.6, 3.45))
    for ax, d in zip(axes, dates):
        cs = cross_section(feats, pd.Timestamp(d))
        sol = solve_day(cs["Q"], cs["H"], cs["V"], cs["S"], n_random=5)
        _draw_flow_map(ax, sol["q"], sol["pairs"], cs["codes"], names,
                       f"{d}\n最大误差 {sol['max_abs_err'] * 1000:.1f}‰")
    fig.suptitle("图3　行业资金流向图：2026 年三个示例日"
                 "（红=净流入，蓝=净流出，仅画前 26 条边）",
                 x=0.01, ha="left", fontsize=11, color=INK)
    fig.tight_layout()
    _save(fig, "fig2_flowmap.png")


def fig_review_2026() -> None:
    res = json.loads((OUTPUT / "results.json").read_text(encoding="utf-8"))
    monthly = pd.DataFrame(res["review_2026"]["monthly"])
    feats = build_dataset(fetch_etf_daily())
    micro = pd.read_csv(Path(OUTPUT).parent / "data" / "processed" / "flow_micro.csv",
                        parse_dates=["date"])

    fig, axes = plt.subplots(1, 2, figsize=(9.6, 4.1),
                             gridspec_kw={"width_ratios": [1.35, 1]})
    ax = axes[0]
    months = [c for c in monthly.columns if c.startswith("2026-")]
    mat = monthly.set_index("name")[months].to_numpy(float) * 100
    order = np.nanmean(mat, axis=1).argsort()[::-1]
    mat = mat[order]
    labels = monthly.set_index("name").index[order]
    im = ax.imshow(mat, aspect="auto", cmap=DIVERGING, vmin=-40, vmax=40)
    ax.set_xticks(range(len(months)), [m[-2:] for m in months], fontsize=7)
    ax.set_yticks(range(len(labels)), labels, fontsize=7)
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            if np.isfinite(mat[i, j]):
                ax.text(j, i, f"{mat[i, j]:.0f}", ha="center", va="center",
                        fontsize=5.8, color=INK)
    ax.set_title("A　2026 年行业 ETF 月度收益（%）", loc="left", fontsize=9.5, color=INK)
    ax.grid(False)
    fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)

    ax = axes[1]
    raw = feats["close"]["sh.512480"].loc["2026-05-01":"2026-10-30"].ffill()
    pct_s = feats["pct"]["sh.512480"].loc[raw.index].fillna(0.0)
    price = (1.0 + pct_s).cumprod() * raw.iloc[0]  # 复权，消除 2026-07 份额折算的假跳空
    b = micro[micro.code == "sh.512480"].set_index("date").breadth
    b = b.loc[raw.index]
    b_ma = b.rolling(5, min_periods=1).mean()

    ax.plot(price.index, price, color=INK, lw=1.15, label="半导体 ETF（复权）")
    ax.set_ylabel("复权价格（元）")
    ax2 = ax.twinx()
    ax2.plot(b.index, b * 100, color=RED, lw=0.7, alpha=0.22)
    ax2.plot(b_ma.index, b_ma * 100, color=RED, lw=1.2, label="净流入为正比例（5日均）")
    ax2.set_ylabel("净流入为正比例（%）", color=RED)
    ax2.set_ylim(0, 100)
    ax2.tick_params(axis="y", colors=RED)
    for d in ["2026-06-24", "2026-06-30", "2026-07-06"]:
        ax.axvline(pd.Timestamp(d), color=GRAY, ls="--", lw=0.7)
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m月"))
    ax.set_title("B　半导体的“抱团温度计”与复权价格", loc="left", fontsize=9.5, color=INK)
    lines = ax.get_lines()[:1] + ax2.get_lines()[1:2]
    ax.legend(lines, [l.get_label() for l in lines], frameon=False,
              fontsize=7.2, loc="lower left")
    fig.suptitle("图4　2026 年复盘：AI 硬件主线的一致与松动", x=0.01, ha="left",
                 fontsize=11, color=INK)
    fig.tight_layout()
    _save(fig, "fig3_review2026.png")


def fig_capacity() -> None:
    res = json.loads((OUTPUT / "results.json").read_text(encoding="utf-8"))
    cap = pd.DataFrame(res["capacity"])
    fig, ax = plt.subplots(figsize=(9.2, 2.9))
    x = cap["资金规模(万元)"]
    ax.plot(x, cap["年化收益"] * 100, marker="o", color=RED, lw=1.5,
            label="净年化收益")
    ax.axhline(res["benchmark_excess_line"] if "benchmark_excess_line" in res else
               res["performance"]["benchmark_gross"]["cagr"] * 100,
               color=BLUE, ls="--", lw=1.0, label="等权基准")
    ax.set_xscale("log")
    ax.set_xlabel("资金规模（万元，对数轴）")
    ax.set_ylabel("年化收益（%）")
    ax.grid(alpha=0.25)
    ax2 = ax.twinx()
    ax2.plot(x, cap["最大参与率"] * 100, marker="s", color=GRAY, lw=1.0,
             label="最大参与率")
    ax2.axhline(5, color=GRAY, ls=":", lw=0.8)
    ax2.set_ylabel("最大参与率（% of ADV）", color=GRAY)
    ax2.tick_params(axis="y", colors=GRAY)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, frameon=False, fontsize=7.8, loc="lower right")
    ax.axvline(5000, color=GRAY, ls=":", lw=0.9)
    ax.text(5200, 4.55, "5000 万", fontsize=7, color=GRAY,
            bbox=dict(facecolor="white", edgecolor="none", pad=1.0))
    ax.set_title("图2　容量曲线：5000 万附近触顶，更大规模下策略被截断为低换手组合",
                 loc="left", fontsize=10, color=INK)
    _save(fig, "fig4_capacity.png")


def build_all() -> None:
    ensure_dirs()
    setup_matplotlib()
    fig_nav()
    fig_flowmap()
    fig_review_2026()
    fig_capacity()


if __name__ == "__main__":
    build_all()
