"""图表生成：5 张图，统一配色与版式。

配色约定（按数据承担的"任务"选色，而非按好看）：
- 极性（正/负净流入）→ 发散色：蓝(正) / 红(负) + 中性灰零点
- 有序分组（十分位）→ 单色相顺序色阶
- 两个序列（同日/次日相关）→ 固定顺序的分类色，且带图例
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from scipy import stats

from .config import FIG_DIR, ensure_dirs, setup_matplotlib

BLUE = "#2F6F8F"
RED = "#C0504D"
GRAY = "#8A8A8A"
INK = "#333333"
LIGHT = "#D9E2E8"

DIVERGING = LinearSegmentedColormap.from_list(
    "div", ["#B3544F", "#E8D6D5", "#F2F2F2", "#D3E0E8", "#2F6F8F"]
)
SEQUENTIAL = LinearSegmentedColormap.from_list("seq", ["#DCE8EF", "#1F4F66"])


def _save(fig, name: str) -> None:
    path = FIG_DIR / name
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"[charts] {path.name}")


def fig_timeseries(df: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(9.6, 5.4), sharex=True,
                             gridspec_kw={"height_ratios": [1, 1], "hspace": 0.12})
    ax1, ax2 = axes

    ax1.plot(df.date, df.close, color=BLUE, lw=1.2)
    ax1.set_ylabel("沪深300收盘")
    ax1.set_title("图1  沪深300指数与主动买盘净流入率（2012-01 至 2026-10）",
                  loc="left", fontsize=11, color=INK)

    colors = np.where(df.nbi >= 0, BLUE, RED)
    ax2.bar(df.date, df.nbi * 100, width=1.0, color=colors, alpha=0.35, linewidth=0)
    ax2.plot(df.date, df.nbi.rolling(20).mean() * 100, color=INK, lw=1.2,
             label="20 日移动平均")
    ax2.axhline(0, color=GRAY, lw=0.8)
    ax2.set_ylabel("主买净流入率（%）")
    ax2.legend(frameon=False, loc="lower left", fontsize=8)
    _save(fig, "fig1_timeseries.png")


def fig_scatter(df: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 4.0))
    for ax, ycol, title in [
        (axes[0], "r", "同日（t 日收益）"),
        (axes[1], "r_next", "次日（t+1 日收益）"),
    ]:
        sub = df[["nbi", ycol]].dropna()
        x, y = sub.nbi * 100, sub[ycol] * 100
        ax.scatter(x, y, s=6, color=BLUE, alpha=0.25, linewidth=0)
        coef = np.polyfit(x, y, 1)
        xs = np.linspace(x.min(), x.max(), 100)
        ax.plot(xs, np.polyval(coef, xs), color=RED, lw=1.6)
        r = np.corrcoef(x, y)[0, 1]
        ax.set_title(f"{title}  r = {r:.3f}   R2 = {r ** 2:.3f}", fontsize=10, loc="left")
        ax.set_xlabel("主买净流入率（%）")
        ax.set_ylabel("指数收益（%）")
        ax.axhline(0, color=GRAY, lw=0.6)
        ax.axvline(0, color=GRAY, lw=0.6)
    fig.suptitle("图2  主买净流入率与指数收益：同日强相关，次日消失", x=0.01,
                 ha="left", fontsize=11, color=INK)
    fig.tight_layout()
    _save(fig, "fig2_scatter.png")


def fig_decile(dec: pd.DataFrame, long_short: dict) -> None:
    fig, ax = plt.subplots(figsize=(9.0, 3.1))
    mean = dec["mean_bp"].to_numpy()
    lo = mean - dec["ci_low_bp"].to_numpy()
    hi = dec["ci_high_bp"].to_numpy() - mean
    colors = [SEQUENTIAL(v) for v in np.linspace(0.15, 0.95, len(dec))]

    ax.bar(dec["group"], mean, color=colors, width=0.68, linewidth=0)
    ax.errorbar(dec["group"], mean, yerr=[lo, hi], fmt="none",
                ecolor=GRAY, elinewidth=1, capsize=3)
    ax.axhline(0, color=INK, lw=0.8)
    ax.set_xticks(dec["group"])
    ax.set_xlabel("主买强度十分位（1 = 净卖出最强，10 = 净买入最强）")
    ax.set_ylabel("次日平均收益（bp）")
    ax.set_title(
        f"图3  按主买强度分组的次日收益（误差线为 95% 置信区间；"
        f"多空价差 {long_short['spread_bp']:.1f} bp，t = {long_short['t']:.2f}）",
        loc="left", fontsize=10, color=INK,
    )
    _save(fig, "fig3_decile.png")


def fig_rolling(df: pd.DataFrame, window: int = 250) -> None:
    same = df.nbi.rolling(window).corr(df.r)
    nxt = df.nbi.rolling(window).corr(df.r_next)
    fig, ax = plt.subplots(figsize=(9.6, 3.6))
    ax.plot(df.date, same, color=BLUE, lw=1.3, label="与当日收益")
    ax.plot(df.date, nxt, color=RED, lw=1.3, label="与次日收益")
    ax.axhline(0, color=GRAY, lw=0.8)
    ax.set_ylabel(f"滚动 {window} 日相关系数")
    ax.set_title("图4  主买净流入率的滚动相关系数：同期稳定高相关，次日长期贴零",
                 loc="left", fontsize=10, color=INK)
    ax.legend(frameon=False, loc="center left", fontsize=9)
    ax.text(df.date.iloc[-1], same.iloc[-1], "  同日", color=BLUE, va="center", fontsize=9)
    ax.text(df.date.iloc[-1], nxt.iloc[-1], "  次日", color=RED, va="center", fontsize=9)
    _save(fig, "fig4_rolling.png")


def fig_heatmap(df: pd.DataFrame) -> pd.DataFrame:
    d = df[["nbi", "r_next", "bull", "vol20"]].dropna().copy()
    d["vol_grp"] = pd.qcut(d["vol20"], 3, labels=["低波动", "中波动", "高波动"])
    d["regime"] = np.where(d["bull"], "牛市", "熊市")

    grid = pd.DataFrame(index=["熊市", "牛市"], columns=["低波动", "中波动", "高波动"], dtype=float)
    for (reg, vol), part in d.groupby(["regime", "vol_grp"], observed=True):
        grid.loc[reg, str(vol)] = np.corrcoef(part.nbi, part.r_next)[0, 1]

    fig, ax = plt.subplots(figsize=(5.6, 2.9))
    im = ax.imshow(grid.to_numpy(dtype=float), cmap=DIVERGING, vmin=-0.1, vmax=0.1, aspect="auto")
    ax.set_xticks(range(grid.shape[1]), grid.columns)
    ax.set_yticks(range(grid.shape[0]), grid.index)
    for i in range(grid.shape[0]):
        for j in range(grid.shape[1]):
            ax.text(j, i, f"{grid.iloc[i, j]:.3f}", ha="center", va="center",
                    fontsize=9.5, color=INK)
    ax.set_title("图5  牛熊 × 波动状态下的次日相关系数", loc="left", fontsize=10, color=INK)
    ax.grid(False)
    fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
    _save(fig, "fig5_heatmap.png")
    return grid


def build_all(df: pd.DataFrame, dec: pd.DataFrame, long_short: dict) -> pd.DataFrame:
    ensure_dirs()
    setup_matplotlib()
    fig_timeseries(df)
    fig_scatter(df)
    fig_decile(dec, long_short)
    fig_rolling(df)
    return fig_heatmap(df)


if __name__ == "__main__":
    import json

    from .analysis import decile_analysis
    from .build_features import build_dataset
    from .config import OUTPUT

    data = build_dataset()
    table = decile_analysis(data)
    res = json.loads((OUTPUT / "results.json").read_text(encoding="utf-8"))
    build_all(data, table, res["decile"]["long_short"])
