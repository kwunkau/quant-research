"""统计与回测汇总：业绩指标、IC、容量、敏感性、2026 复盘。

所有报告数字写入 output/results.json 与 output/tables/*.csv，
报告正文只从 results.json 渲染，避免手填数字。
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.api as sm

from .backtest import (
    build_factor_panels,
    run_engine,
    weekly_signal_dates,
)
from .build_features import build_dataset
from .config import (
    ADV_MIN_YI,
    AUM_GRID,
    BOOTSTRAP_BLOCK,
    BOOTSTRAP_N,
    CAPITAL,
    COMMISSION_GRID,
    END_DATE,
    IMPACT_GRID,
    OUTPUT,
    SEED,
    START_DATE,
    TABLE_DIR,
    TOP_N,
    TOP_N_GRID,
    W_GRID,
    ensure_dirs,
)
from .fetch_data import fetch_etf_daily, fetch_sina_flow
from .flowmap import run as run_flowmap

# 研报原文数字（仅用于对照，不参与本地计算）
REPORT_REF = {
    "base": {"cagr": 0.2197, "excess": 0.1266, "mdd": -0.3486},
    "composite": {"cagr": 0.2263, "excess": 0.1332, "mdd": -0.2227},
    "benchmark": {"cagr": 0.0931, "mdd": -0.2877},
    "period": "2018-12-31~2026-07-31",
    "n_industries": 40,
}
KEY_DATES = ["2026-06-24", "2026-06-30", "2026-07-06"]


# ---------------------------------------------------------------- 指标

def _json_default(obj):
    """把 numpy 标量转成 Python 标量，保证 results.json 可序列化。"""
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    raise TypeError(f"不可序列化类型：{type(obj)}")


def perf_metrics(nav: pd.DataFrame) -> dict:
    """年化、波动、夏普、最大回撤、卡玛、换手与成本拖累。"""
    nav = nav.dropna(subset=["value"])
    if len(nav) < 2:
        return {}
    days = (nav.index[-1] - nav.index[0]).days
    years = max(days / 365.25, 1 / 365.25)
    total = nav.value.iloc[-1] / nav.value.iloc[0] - 1.0
    cagr = (1.0 + total) ** (1.0 / years) - 1.0
    r = nav.value.pct_change(fill_method=None).dropna()
    vol = float(r.std(ddof=1) * np.sqrt(252))
    sharpe = float(r.mean() * 252 / vol) if vol > 0 else np.nan
    mdd = float((nav.value / nav.value.cummax() - 1.0).min())
    calmar = float(cagr / abs(mdd)) if mdd < 0 else np.nan
    turnover = float(nav.turnover.sum() / nav.value.mean() / years) if "turnover" in nav else np.nan
    cost = float(nav.cost.sum() / nav.value.mean() / years) if "cost" in nav else np.nan
    return {
        "start": str(nav.index[0].date()), "end": str(nav.index[-1].date()),
        "years": float(years), "total": float(total), "cagr": float(cagr),
        "vol": vol, "sharpe": sharpe, "mdd": mdd, "calmar": calmar,
        "final_value": float(nav.value.iloc[-1]),
        "net_profit": float(nav.value.iloc[-1] - nav.value.iloc[0]),
        "turnover_annual": turnover, "cost_drag_annual": cost,
        "avg_participation": float(nav.max_participation[~nav.binding].mean())
        if "max_participation" in nav and (~nav.binding).any() else np.nan,
        "max_participation": float(nav.max_participation.max())
        if "max_participation" in nav else np.nan,
        "binding_days": int(nav.binding.sum()) if "binding" in nav else 0,
        "n_days": int(len(nav)),
    }


def slice_nav(nav: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    out = nav.loc[start:end].copy()
    if len(out):
        out["value"] = out["value"] / out["value"].iloc[0] * nav.value.iloc[0]
    return out


def ic_stats(factor: pd.DataFrame, mask: pd.DataFrame, close: pd.DataFrame,
             horizon: int = 5) -> dict:
    """周度截面 Spearman IC + 多空组合。"""
    dates = close.index
    dates = dates[(dates >= pd.Timestamp(START_DATE)) & (dates <= pd.Timestamp(END_DATE))]
    sigs = weekly_signal_dates(dates)
    ics, longs, shorts = [], [], []
    for sd in sigs:
        pos = dates.get_loc(sd)
        if pos + horizon >= len(dates):
            continue
        fwd = close.iloc[pos + horizon] / close.iloc[pos] - 1.0
        x = factor.loc[sd].where(mask.loc[sd])
        y = fwd.where(mask.loc[sd])
        both = x.notna() & y.notna()
        if both.sum() < 6:
            continue
        ics.append(float(stats.spearmanr(x[both], y[both]).statistic))
        ranked = x[both].sort_values(ascending=False)
        longs.append(float(y[ranked.index[:TOP_N]].mean()))
        shorts.append(float(y[ranked.index[-TOP_N:]].mean()))
    ics = pd.Series(ics, dtype=float)
    if len(ics) == 0:
        return {}
    return {
        "n_weeks": int(len(ics)), "mean_ic": float(ics.mean()),
        "ic_std": float(ics.std(ddof=1)), "icir": float(ics.mean() / ics.std(ddof=1)),
        "ic_t": float(ics.mean() / ics.std(ddof=1) * np.sqrt(len(ics))),
        "positive_share": float((ics > 0).mean()),
        "long_short_mean_bp": float((np.mean(longs) - np.mean(shorts)) * 1e4),
    }


def block_bootstrap(x: np.ndarray, n_boot: int = BOOTSTRAP_N,
                    block: int = BOOTSTRAP_BLOCK, seed: int = SEED) -> dict:
    """移动块 bootstrap 的均值置信区间（周频）。"""
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < block * 2:
        return {"mean": float(np.mean(x)), "ci_low": np.nan, "ci_high": np.nan, "n": n}
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(n / block))
    draws = np.empty(n_boot)
    for i in range(n_boot):
        starts = rng.integers(0, n - block, n_blocks)
        idx = np.concatenate([np.arange(s, s + block) for s in starts])[:n]
        draws[i] = x[idx].mean()
    return {
        "mean": float(np.mean(x)), "ci_low": float(np.percentile(draws, 2.5)),
        "ci_high": float(np.percentile(draws, 97.5)), "n": int(n),
    }


def weekly_returns(nav: pd.DataFrame) -> pd.Series:
    return nav.value.resample("W-FRI").last().pct_change(fill_method=None).dropna()


def hac_t(x: np.ndarray, lags: int = 4) -> float:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < 10:
        return np.nan
    res = sm.OLS(x, np.ones(len(x))).fit(cov_type="HAC", cov_kwds={"maxlags": lags})
    return float(res.tvalues[0])


# ---------------------------------------------------------------- 主流程

def run() -> dict:
    ensure_dirs()
    daily = fetch_etf_daily()
    feats = build_dataset(daily)
    flow = run_flowmap()
    panels = build_factor_panels(feats, flow["micro"])

    # 主回测：W=20，top-5
    base = panels["base_w20"]
    comp = panels["composite_w20"]
    gross_base = run_engine(feats, base, cost=False, cap=False)
    gross_comp = run_engine(feats, comp, cost=False, cap=False)
    net_base = run_engine(feats, base, capital=CAPITAL, cost=True, cap=True)
    net_comp = run_engine(feats, comp, capital=CAPITAL, cost=True, cap=True)
    bench = run_engine(feats, base, capital=CAPITAL, cost=False, cap=False, benchmark=True)
    bench_net = run_engine(feats, base, capital=CAPITAL, cost=True, cap=True, benchmark=True)

    perf = {
        "gross_base": perf_metrics(gross_base["nav"]),
        "gross_composite": perf_metrics(gross_comp["nav"]),
        "net_base_50m": perf_metrics(net_base["nav"]),
        "net_composite_50m": perf_metrics(net_comp["nav"]),
        "benchmark_gross": perf_metrics(bench["nav"]),
        "benchmark_net_50m": perf_metrics(bench_net["nav"]),
    }
    for key in ["gross_base", "gross_composite", "net_base_50m", "net_composite_50m"]:
        perf[key]["excess_vs_benchmark"] = (
            perf[key]["cagr"] - perf["benchmark_gross"]["cagr"]
        )

    # 容量扫描
    cap_rows = []
    comp_name = comp
    for aum in AUM_GRID:
        r = run_engine(feats, comp_name, capital=aum, cost=True, cap=True)
        m = perf_metrics(r["nav"])
        cap_rows.append({
            "资金规模(万元)": round(aum / 1e4),
            "年化收益": m["cagr"], "年化波动": m["vol"], "夏普": m["sharpe"],
            "最大回撤": m["mdd"], "净收益(万元)": m["net_profit"] / 1e4,
            "超额(vs基准)": m["cagr"] - perf["benchmark_gross"]["cagr"],
            "年化换手": m["turnover_annual"], "年化成本拖累": m["cost_drag_annual"],
            "最大参与率": m["max_participation"], "受限天数": m["binding_days"],
        })
    cap_df = pd.DataFrame(cap_rows)

    # 参数敏感性（未扣成本，考察信号本身）
    sens_rows = []
    for w in W_GRID:
        for kind, col in [("基础因子", f"base_w{w}"), ("综合因子", f"composite_w{w}")]:
            r = run_engine(feats, panels[col], cost=False, cap=False)
            m = perf_metrics(r["nav"])
            sens_rows.append({"因子": kind, "W": w, "topN": TOP_N,
                              "年化收益": m["cagr"], "最大回撤": m["mdd"],
                              "夏普": m["sharpe"]})
    for n in TOP_N_GRID:
        r = run_engine(feats, comp, top_n=n, cost=False, cap=False)
        m = perf_metrics(r["nav"])
        sens_rows.append({"因子": "综合因子", "W": 20, "topN": n,
                          "年化收益": m["cagr"], "最大回撤": m["mdd"],
                          "夏普": m["sharpe"]})
    sens_df = pd.DataFrame(sens_rows)

    # 成本敏感性
    cost_rows = []
    for impact in IMPACT_GRID:
        for comm in COMMISSION_GRID:
            r = run_engine(feats, comp, capital=CAPITAL, cost=True, cap=True,
                           impact_bps_at_5pct=impact, commission_bps=comm)
            m = perf_metrics(r["nav"])
            cost_rows.append({"冲击成本@5%": impact, "佣金(bp)": comm,
                              "年化收益": m["cagr"], "最大回撤": m["mdd"],
                              "净收益(万元)": m["net_profit"] / 1e4})
    cost_df = pd.DataFrame(cost_rows)

    # IC：统一用 W=20 的标准化分量，保证与综合因子口径一致
    comps20 = panels["components"][20]
    ic = {}
    for key, label in [("base", "基础因子"), ("composite", "综合因子"),
                       ("max_in", "行业间最大净流入"), ("breadth", "净流入为正比例"),
                       ("out_sum", "净流出之和"), ("external", "外部净流入")]:
        ic[key] = ic_stats(comps20[key], feats["mask"], feats["close"].ffill())

    # 子区间
    subs = []
    for label, s, e in [("2020-2022", "2020-01-01", "2022-12-31"),
                        ("2023-2026", "2023-01-01", "2026-12-31")]:
        for name, res in [("基础因子", gross_base), ("综合因子", gross_comp),
                          ("等权基准", bench)]:
            m = perf_metrics(slice_nav(res["nav"], s, e))
            subs.append({"区间": label, "组合": name, "年化收益": m["cagr"],
                         "最大回撤": m["mdd"], "夏普": m["sharpe"]})
    subs_df = pd.DataFrame(subs)

    # 周频超额与 bootstrap
    wr_s = weekly_returns(net_comp["nav"])
    wr_b = weekly_returns(bench["nav"])
    excess = (wr_s - wr_b).dropna()
    boot = block_bootstrap(excess.to_numpy())
    boot["annualized"] = boot["mean"] * 52
    boot["annualized_ci_low"] = boot["ci_low"] * 52
    boot["annualized_ci_high"] = boot["ci_high"] * 52
    boot["hac_t"] = hac_t(excess.to_numpy())

    # 2026 复盘
    pct = feats["pct"]
    m2026 = pct.loc["2026-01-01":"2026-12-31"]
    monthly = ((1 + m2026).resample("ME").prod() - 1).T
    monthly.columns = [c.strftime("%Y-%m") for c in monthly.columns]
    ytd = ((1 + m2026).prod() - 1).sort_values(ascending=False)
    name_map = feats["meta"]["name"]
    ytd_df = pd.DataFrame({"code": ytd.index, "name": [name_map.get(c, c) for c in ytd.index],
                           "ytd": ytd.to_numpy()})
    monthly.insert(0, "name", [name_map.get(c, c) for c in monthly.index])
    monthly.insert(0, "code", monthly.index)

    # 关键日期：本地广度 vs 新浪真实资金流
    breadth = flow["micro"].pivot(index="date", columns="code", values="breadth")
    sina = fetch_sina_flow()
    sina_p = sina.pivot(index="date", columns="code", values="ratioamount")
    key_rows = []
    for d in KEY_DATES:
        dd = pd.Timestamp(d)
        if dd not in breadth.index:
            continue
        b = breadth.loc[dd]
        a = sina_p.loc[dd] if dd in sina_p.index else pd.Series(dtype=float)
        common = b.dropna().index.intersection(a.dropna().index)
        corr = (float(stats.spearmanr(b[common], a[common]).statistic)
                if len(common) >= 5 else np.nan)
        key_rows.append({
            "date": d, "n": int(len(common)), "corr_breadth_flow": corr,
            "semi_breadth": float(b.get("sh.512480", np.nan)),
            "semi_flow": float(a.get("sh.512480", np.nan)),
            "telecom_breadth": float(b.get("sh.515880", np.nan)),
            "telecom_flow": float(a.get("sh.515880", np.nan)),
        })
    key_df = pd.DataFrame(key_rows)

    # 流向图误差
    errs = flow["errors"].copy()
    errs["year"] = errs.date.dt.year
    err_by_year = errs.groupby("year").max_abs_err.agg(["count", "median", "max"]).reset_index()
    err_by_year.columns = ["年份", "天数", "中位最大误差", "最大误差"]

    results = {
        "meta": {
            "project": "kwunkau_day02",
            "start": START_DATE, "end": END_DATE,
            "n_days": int(len(feats["pct"].loc[START_DATE:END_DATE])),
            "n_etfs": int(feats["pct"].shape[1]),
            "n_rebalances": int(len(weekly_signal_dates(
                feats["pct"].loc[START_DATE:END_DATE].index))),
            "adv_min_yi": ADV_MIN_YI,
            "capital": CAPITAL,
            "n_flow_days": int(len(flow["errors"])),
        },
        "report_ref": REPORT_REF,
        "performance": perf,
        "capacity": cap_df.to_dict("records"),
        "sensitivity": sens_df.to_dict("records"),
        "cost_sensitivity": cost_df.to_dict("records"),
        "ic": ic,
        "subsample": subs_df.to_dict("records"),
        "bootstrap_excess": boot,
        "flowmap": {
            "median_max_err": float(errs.max_abs_err.median()),
            "p95_max_err": float(errs.max_abs_err.quantile(0.95)),
            "max_max_err": float(errs.max_abs_err.max()),
            "share_below_5permille": float((errs.max_abs_err < 0.005).mean()),
            "by_year": err_by_year.to_dict("records"),
        },
        "review_2026": {
            "ytd": ytd_df.to_dict("records"),
            "monthly": monthly.to_dict("records"),
            "key_dates": key_df.to_dict("records"),
        },
    }

    (OUTPUT / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )

    perf_df = pd.DataFrame([
        {"组合": k, **{kk: vv for kk, vv in v.items()
                       if kk in ("cagr", "vol", "sharpe", "mdd", "calmar",
                                 "excess_vs_benchmark", "turnover_annual",
                                 "cost_drag_annual", "binding_days")}}
        for k, v in perf.items()
    ])
    perf_df.to_csv(TABLE_DIR / "t01_performance.csv", index=False, encoding="utf-8-sig")
    cap_df.to_csv(TABLE_DIR / "t02_capacity.csv", index=False, encoding="utf-8-sig")
    sens_df.to_csv(TABLE_DIR / "t03_sensitivity.csv", index=False, encoding="utf-8-sig")
    cost_df.to_csv(TABLE_DIR / "t04_cost.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(ic).T.to_csv(TABLE_DIR / "t05_ic.csv", encoding="utf-8-sig")
    subs_df.to_csv(TABLE_DIR / "t06_subsample.csv", index=False, encoding="utf-8-sig")
    ytd_df.to_csv(TABLE_DIR / "t07_ytd_2026.csv", index=False, encoding="utf-8-sig")
    monthly.to_csv(TABLE_DIR / "t08_monthly_2026.csv", index=False, encoding="utf-8-sig")
    key_df.to_csv(TABLE_DIR / "t09_key_dates.csv", index=False, encoding="utf-8-sig")
    err_by_year.to_csv(TABLE_DIR / "t10_flowmap_errors.csv", index=False, encoding="utf-8-sig")

    # 保存净值曲线供图表使用
    navs = {
        "gross_base": gross_base["nav"], "gross_composite": gross_comp["nav"],
        "net_base": net_base["nav"], "net_composite": net_comp["nav"],
        "benchmark": bench["nav"],
    }
    pd.concat({k: v.value for k, v in navs.items()}, axis=1).to_csv(
        OUTPUT / "nav_curves.csv", encoding="utf-8-sig"
    )
    print(f"[analysis] 结果写入 {OUTPUT / 'results.json'}")
    return results
