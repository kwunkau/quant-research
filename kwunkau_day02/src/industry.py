"""行业口径复现：用新浪行业板块资金流补 Wind 主动买卖金额的缺口。

与研报对齐的部分：行业层面（48 个新浪行业，研报为 40 个中信行业）、回测区间 2018-12-31~2026-07-31、
W=20~24 五组回测取平均、周度 top-5 等权、次一交易日调仓（以“当日半仓新、半仓旧”近似均价成交）、
不计交易费用。
口径差异：新浪“净流入”按逐笔主动买卖划分，与 Wind 主动买卖金额同源但算法不同；
板块没有流通市值字段，流向图中 S_i 用成交额占比代替（会与 V_i 项合并，报告中说明）。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .backtest import winsor_cs, weekly_signal_dates
from .build_features import zscore_cs
from .config import (DATA_RAW, IND_REPORT_END, IND_SEMI, IND_START,
                     IND_TELECOM, IND_W_GRID, KEY_DATES, TOP_N)
from .fetch_data import fetch_sina_boards
from .flowmap import extract_micro, solve_day

# 非行业板块（地域/杂项）不进截面
EXCLUDE_BOARDS = ["开发区", "其它行业"]
MICRO_KEYS = ["max_in", "breadth", "out_sum", "external"]


def build_panels(boards: pd.DataFrame | None = None) -> dict:
    """date × board 面板：Q（买入占比−卖出占比）、V（成交额占比）、H（超额收益）。"""
    if boards is None:
        boards = fetch_sina_boards()
    b = boards[~boards.board.isin(EXCLUDE_BOARDS)]
    pct = b.pivot(index="date", columns="board", values="pct").sort_index()
    amt = b.pivot(index="date", columns="board", values="amount").reindex_like(pct)
    net = b.pivot(index="date", columns="board", values="netamount").reindex_like(pct)
    mask = pct.notna() & amt.notna() & (amt > 0) & net.notna()
    amt, net, pct_m = amt.where(mask), net.where(mask), pct.where(mask)
    buy, sell = (amt + net) / 2, (amt - net) / 2
    q = buy.div(buy.sum(axis=1), axis=0) - sell.div(sell.sum(axis=1), axis=0)
    v = amt.div(amt.sum(axis=1), axis=0)
    h = pct_m.sub(pct_m.mean(axis=1), axis=0)
    return {"pct": pct, "mask": mask, "q": q, "v": v, "h": h,
            "adj": (1.0 + pct.fillna(0.0)).cumprod()}


def _solve_one(p: dict, date: pd.Timestamp, n_random: int, warm=None):
    m = p["mask"].loc[date]
    sel = list(m[m].index)
    q, h, v = (p[k].loc[date, sel].to_numpy(float) for k in ("q", "h", "v"))
    if len(sel) < 6 or not all(np.all(np.isfinite(a)) for a in (q, h, v)):
        return None, sel
    return solve_day(q, h, v, v, n_random=n_random, warm=warm), sel


def solve_micro(p: dict, force: bool = False, n_random: int = 1) -> pd.DataFrame:
    """逐日求解行业资金流向图并提取四个微观维度；结果以快照随仓库提交（全量约 20 分钟）。"""
    snap = DATA_RAW / "ind_flow_micro_snapshot.csv"
    if snap.exists() and not force:
        return pd.read_csv(snap, parse_dates=["date"])

    dates = p["pct"].loc["2018-10-01":IND_REPORT_END].index  # 预留 W 日平滑预热
    rows, last = [], {}
    for k, d in enumerate(dates):
        sel_key = tuple(p["mask"].loc[d][p["mask"].loc[d]].index)
        sol, sel = _solve_one(p, d, n_random, warm=last.get(sel_key))
        if sol is None:
            continue
        last[sel_key] = sol["x"]
        micro = extract_micro(sol["q"], sol["pairs"], len(sel), p["v"].loc[d, sel].to_numpy(float))
        for j, board in enumerate(sel):
            rows.append({"date": d, "board": board, "max_abs_err": sol["max_abs_err"],
                         **{key: micro[key][j] for key in MICRO_KEYS}})
        if (k + 1) % 200 == 0:
            print(f"[industry] 流向图 {k + 1}/{len(dates)}")
    out = pd.DataFrame(rows)
    out.to_csv(snap, index=False, encoding="utf-8-sig", float_format="%.6g")
    return out


def factor_panels(p: dict, micro: pd.DataFrame, w: int) -> dict[str, pd.DataFrame]:
    mask = p["mask"]
    mp = lambda w_: max(5, int(w_ * 0.8))  # noqa: E731
    comps = {"base": zscore_cs(winsor_cs((p["q"] / p["v"]).rolling(w, min_periods=mp(w)).mean(),
                                         mask), mask)}
    for key in MICRO_KEYS:
        panel = (micro.pivot(index="date", columns="board", values=key)
                 .reindex(index=mask.index, columns=mask.columns)
                 .replace([np.inf, -np.inf], np.nan))
        comps[key] = zscore_cs(winsor_cs(panel.rolling(w, min_periods=mp(w)).mean(), mask), mask)
    comp = pd.concat([comps[k] for k in ["base", *MICRO_KEYS]]).groupby(level=0).mean()
    comps["composite"] = zscore_cs(comp.where(mask), mask)
    return comps


def backtest(p: dict, factor: pd.DataFrame | None, top_n: int = TOP_N) -> pd.Series:
    """周度 top-N 等权（factor=None 为行业等权基准）；返回日收益。"""
    pct = p["pct"].fillna(0.0)
    idx = pct.index
    dates = idx[(idx >= pd.Timestamp(IND_START)) & (idx <= pd.Timestamp(IND_REPORT_END))]
    if factor is None:
        return pct.where(p["mask"]).mean(axis=1).loc[dates]
    target = pd.DataFrame(np.nan, index=idx, columns=pct.columns)
    for sd in weekly_signal_dates(dates):
        top = factor.loc[sd].where(p["mask"].loc[sd]).dropna().nlargest(top_n).index
        target.loc[sd] = 0.0
        target.loc[sd, top] = 1.0 / len(top) if len(top) else 0.0
    target = target.ffill().fillna(0.0)
    new, old = target.shift(1), target.shift(2)          # 信号日收盘 → 次日调仓
    held = new.where(new.eq(old).all(axis=1), 0.5 * new + 0.5 * old, axis=0)
    return (held * pct).sum(axis=1).loc[dates]


def metrics(r: pd.Series) -> dict:
    nav = (1.0 + r).cumprod()
    years = (nav.index[-1] - nav.index[0]).days / 365.25
    return {"cagr": float(nav.iloc[-1] ** (1 / years) - 1),
            "mdd": float((nav / nav.cummax() - 1).min())}


def weekly_ic(p: dict, factor: pd.DataFrame, horizon: int = 5) -> dict:
    """周度 Rank IC：信号日收盘 → 次日起持有 horizon 日（完整索引定位）。"""
    from scipy import stats

    idx, adj = p["adj"].index, p["adj"]
    dates = idx[(idx >= pd.Timestamp(IND_START)) & (idx <= pd.Timestamp(IND_REPORT_END))]
    ics = []
    for sd in weekly_signal_dates(dates):
        pos = idx.get_loc(sd)
        if pos + 1 + horizon >= len(idx):
            continue
        fwd = adj.iloc[pos + 1 + horizon] / adj.iloc[pos + 1] - 1.0
        x = factor.loc[sd].where(p["mask"].loc[sd])
        ok = x.notna() & fwd.notna()
        if ok.sum() >= 10:
            ics.append(stats.spearmanr(x[ok], fwd[ok]).statistic)
    s = pd.Series(ics, dtype=float)
    return {"mean_ic": float(s.mean()), "ic_t": float(s.mean() / s.std(ddof=1) * np.sqrt(len(s))),
            "n_weeks": int(len(s))}


def key_date_breadth(p: dict) -> list[dict]:
    """研报三个示例日：电子/通信对应行业的“净流入为正个数/其他行业数”（多初值求解）。"""
    out = []
    for d in KEY_DATES:
        sol, sel = _solve_one(p, pd.Timestamp(d), n_random=5)
        if sol is None:
            continue
        micro = extract_micro(sol["q"], sol["pairs"], len(sel),
                              p["v"].loc[pd.Timestamp(d), sel].to_numpy(float))
        n_other = len(sel) - 1
        row = {"date": d, "n_other": n_other, "max_abs_err": sol["max_abs_err"]}
        for tag, board in [("semi", IND_SEMI), ("telecom", IND_TELECOM)]:
            j = sel.index(board)
            row[f"{tag}_board"] = board
            row[f"{tag}_pos"] = int(round(micro["breadth"][j] * n_other))
            row[f"{tag}_external"] = float(micro["external"][j])
        out.append(row)
    return out


def run(force: bool = False) -> dict:
    p = build_panels()
    micro = solve_micro(p, force=force)
    bench = metrics(backtest(p, None))
    per_w = []
    for w in IND_W_GRID:
        comps = factor_panels(p, micro, w)
        per_w.append({"W": w,
                      "base": metrics(backtest(p, comps["base"])),
                      "composite": metrics(backtest(p, comps["composite"]))})
    avg = {k: {m: float(np.mean([r[k][m] for r in per_w])) for m in ("cagr", "mdd")}
           for k in ("base", "composite")}
    comps20 = factor_panels(p, micro, 20)
    errs = micro.drop_duplicates("date").set_index("date").max_abs_err.loc[IND_START:]
    return {
        "source": "新浪行业板块资金流（逐笔主动买卖口径）",
        "n_boards": int(p["mask"].loc[IND_START:].sum(axis=1).median()),
        "start": IND_START, "end": IND_REPORT_END,
        "benchmark": bench, "avg": avg, "by_w": per_w,
        "ic": {k: weekly_ic(p, comps20[k]) for k in ["base", "composite", *MICRO_KEYS]},
        "flowmap_median_err": float(errs.median()),
        "flowmap_share_below_5permille": float((errs < 0.005).mean()),
        "key_dates": key_date_breadth(p),
    }


if __name__ == "__main__":
    import json

    print(json.dumps(run(), ensure_ascii=False, indent=2, default=float))
