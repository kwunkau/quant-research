"""统计分析：相关性、HAC 回归、分组、状态划分与稳健性检验。

所有结果同时写入 output/tables/*.csv 与 output/results.json，
报告正文中的每个数字都从 results.json 读取，避免手写数字与结果不一致。
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.api as sm

from .build_features import build_dataset, describe
from .config import BOOTSTRAP_BLOCK, BOOTSTRAP_N, SEED, TABLE_DIR, ensure_dirs

HAC_LAGS = 5
CRASH_START, CRASH_END = "2015-06-12", "2016-02-29"


# ---------------------------------------------------------------- 基础工具

def corr_stats(x: pd.Series, y: pd.Series, n_boot: int = BOOTSTRAP_N,
               block: int = BOOTSTRAP_BLOCK, seed: int = SEED) -> dict:
    """Pearson/Spearman 相关及移动块 bootstrap 置信区间。"""
    mask = x.notna() & y.notna()
    xv, yv = x[mask].to_numpy(), y[mask].to_numpy()
    pearson, p_pearson = stats.pearsonr(xv, yv)
    spearman, p_spearman = stats.spearmanr(xv, yv)

    rng = np.random.default_rng(seed)
    n = len(xv)
    n_blocks = int(np.ceil(n / block))
    boots = np.empty(n_boot)
    for i in range(n_boot):
        starts = rng.integers(0, n - block, n_blocks)
        idx = np.concatenate([np.arange(s, s + block) for s in starts])[:n]
        boots[i] = np.corrcoef(xv[idx], yv[idx])[0, 1]

    return {
        "n": int(n),
        "pearson": float(pearson),
        "p_pearson": float(p_pearson),
        "spearman": float(spearman),
        "p_spearman": float(p_spearman),
        "ci_low": float(np.percentile(boots, 2.5)),
        "ci_high": float(np.percentile(boots, 97.5)),
    }


def hac_regression(df: pd.DataFrame, y: str, xs: list[str], lags: int = HAC_LAGS) -> dict:
    """OLS + Newey-West HAC 标准误。"""
    cols = [y] + xs
    sub = df[cols].dropna()
    X = sm.add_constant(sub[xs], has_constant="add")
    res = sm.OLS(sub[y], X).fit(cov_type="HAC", cov_kwds={"maxlags": lags})
    return {
        "n": int(res.nobs),
        "r2": float(res.rsquared),
        "coef": {k: float(v) for k, v in res.params.items()},
        "t": {k: float(v) for k, v in res.tvalues.items()},
        "p": {k: float(v) for k, v in res.pvalues.items()},
    }


def _group_stats(x: pd.Series) -> dict:
    """单组的均值、t 值、胜率、95% 置信区间（单位 bp）。"""
    x = x.dropna()
    n = len(x)
    mean = x.mean()
    se = x.std(ddof=1) / np.sqrt(n)
    return {
        "n": int(n),
        "mean_bp": float(mean * 1e4),
        "t": float(mean / se),
        "win": float((x > 0).mean()),
        "ci_low_bp": float((mean - 1.96 * se) * 1e4),
        "ci_high_bp": float((mean + 1.96 * se) * 1e4),
    }


# ---------------------------------------------------------------- 各项检验

def decile_analysis(df: pd.DataFrame, x: str = "nbi_z", y: str = "r_next",
                    q: int = 10) -> pd.DataFrame:
    """按主买强度十分位分组，统计次日收益。"""
    sub = df[[x, y]].dropna().copy()
    sub["grp"] = pd.qcut(sub[x], q, labels=False, duplicates="drop")
    rows = []
    for g, part in sub.groupby("grp"):
        row = {"group": int(g) + 1, "x_mask": float(part[x].mean()), **_group_stats(part[y])}
        rows.append(row)
    out = pd.DataFrame(rows)

    top, bottom = sub[sub.grp == sub.grp.max()][y], sub[sub.grp == sub.grp.min()][y]
    t_ls = stats.ttest_ind(top, bottom, equal_var=False)
    out.attrs["long_short"] = {
        "spread_bp": float((top.mean() - bottom.mean()) * 1e4),
        "t": float(t_ls.statistic),
        "p": float(t_ls.pvalue),
        "n_top": int(len(top)),
        "n_bottom": int(len(bottom)),
    }
    return out


def regime_analysis(df: pd.DataFrame, x: str = "nbi", y: str = "r_next") -> pd.DataFrame:
    """牛熊（250 日均线）与波动三分位下的预测关系。"""
    d = df[[x, y, "bull", "vol20"]].dropna().copy()
    d["vol_grp"] = pd.qcut(d["vol20"], 3, labels=["低波动", "中波动", "高波动"], duplicates="drop")
    rows = []
    for name, part in [("熊市", d[~d["bull"]]), ("牛市", d[d["bull"]])]:
        st = corr_stats(part[x], part[y], n_boot=200)
        rows.append({"regime": name, "corr": st["pearson"], "p": st["p_pearson"], "n": st["n"]})
    for name, part in d.groupby("vol_grp", observed=True):
        st = corr_stats(part[x], part[y], n_boot=200)
        rows.append({"regime": str(name), "corr": st["pearson"], "p": st["p_pearson"], "n": st["n"]})
    return pd.DataFrame(rows)


def horizon_analysis(df: pd.DataFrame, x: str = "nbi") -> pd.DataFrame:
    """不同期限的预测力。"""
    rows = []
    for y, label in [("r_next", "1 日"), ("r_fwd5", "5 日"), ("r_fwd10", "10 日"), ("r_fwd20", "20 日")]:
        st = corr_stats(df[x], df[y], n_boot=200)
        rows.append({"horizon": label, "corr": st["pearson"], "p": st["p_pearson"],
                     "spearman": st["spearman"], "n": st["n"]})
    return pd.DataFrame(rows)


def subsample_analysis(df: pd.DataFrame, x: str = "nbi", y: str = "r_next") -> pd.DataFrame:
    """四个子区间 + 剔除股灾区间。"""
    periods = [
        ("2012-2015", "2012-01-01", "2015-12-31"),
        ("2016-2019", "2016-01-01", "2019-12-31"),
        ("2020-2022", "2020-01-01", "2022-12-31"),
        ("2023-2026", "2023-01-01", "2026-12-31"),
    ]
    rows = []
    for name, start, end in periods:
        part = df[(df.date >= start) & (df.date <= end)]
        st = corr_stats(part[x], part[y], n_boot=200)
        rows.append({"period": name, "corr": st["pearson"], "p": st["p_pearson"], "n": st["n"]})
    ex_crash = df[~df.date.between(CRASH_START, CRASH_END)]
    st = corr_stats(ex_crash[x], ex_crash[y], n_boot=200)
    rows.append({"period": "剔除股灾", "corr": st["pearson"], "p": st["p_pearson"], "n": st["n"]})
    return pd.DataFrame(rows)


def bh_adjust(pvals: list[float]) -> list[float]:
    """Benjamini-Hochberg FDR 校正。"""
    p = np.asarray(pvals, dtype=float)
    order = np.argsort(p)
    ranked = p[order]
    m = len(p)
    adj = ranked * m / (np.arange(m) + 1)
    adj = np.minimum.accumulate(adj[::-1])[::-1]
    out = np.empty(m)
    out[order] = np.clip(adj, 0, 1)
    return out.tolist()


# ---------------------------------------------------------------- 主流程

def run() -> dict:
    ensure_dirs()
    df = build_dataset(force=False)

    desc = describe(df)
    desc.to_csv(TABLE_DIR / "t01_descriptive.csv", encoding="utf-8-sig")

    # H1 同期 / H2 次日
    same = corr_stats(df["nbi"], df["r"])
    nxt = corr_stats(df["nbi"], df["r_next"])
    corr_table = pd.DataFrame([
        {"关系": "主买强度 vs 当日收益", "Pearson": same["pearson"], "p 值": same["p_pearson"],
         "Spearman": same["spearman"], "95%CI 下界": same["ci_low"], "95%CI 上界": same["ci_high"], "n": same["n"]},
        {"关系": "主买强度 vs 次日收益", "Pearson": nxt["pearson"], "p 值": nxt["p_pearson"],
         "Spearman": nxt["spearman"], "95%CI 下界": nxt["ci_low"], "95%CI 上界": nxt["ci_high"], "n": nxt["n"]},
    ]).round(4)
    corr_table.to_csv(TABLE_DIR / "t02_correlation.csv", index=False, encoding="utf-8-sig")

    # 回归
    reg_uni = hac_regression(df, "r_next", ["nbi"])
    reg_ctrl = hac_regression(df, "r_next", ["nbi", "r", "vol20", "log_amount"])
    reg_large = hac_regression(df, "r_next", ["r0", "divergence", "r", "vol20", "log_amount"])
    reg_same = hac_regression(df, "r", ["nbi"])
    reg_rows = []
    for name, res, keys in [
        ("同日: r ~ NBI", reg_same, ["nbi"]),
        ("次日: r_next ~ NBI", reg_uni, ["nbi"]),
        ("次日: + 控制变量", reg_ctrl, ["nbi", "r", "vol20", "log_amount"]),
        ("次日: 超大单/分歧 + 控制", reg_large, ["r0", "divergence", "r", "vol20", "log_amount"]),
    ]:
        for k in keys:
            reg_rows.append({
                "模型": name, "变量": k,
                "系数": res["coef"].get(k, np.nan), "t 值": res["t"].get(k, np.nan),
                "p 值": res["p"].get(k, np.nan), "R2": res["r2"], "n": res["n"],
            })
    pd.DataFrame(reg_rows).round(5).to_csv(
        TABLE_DIR / "t03_regression.csv", index=False, encoding="utf-8-sig")

    # 十分位
    dec = decile_analysis(df)
    dec.to_csv(TABLE_DIR / "t04_decile.csv", index=False, encoding="utf-8-sig")
    dec_raw = decile_analysis(df, x="nbi")

    # 状态
    regime = regime_analysis(df)
    regime.round(4).to_csv(TABLE_DIR / "t05_regime.csv", index=False, encoding="utf-8-sig")

    # 期限
    horizon = horizon_analysis(df)
    horizon.round(4).to_csv(TABLE_DIR / "t06_horizon.csv", index=False, encoding="utf-8-sig")

    # 子样本
    sub = subsample_analysis(df)
    sub.round(4).to_csv(TABLE_DIR / "t07_subsample.csv", index=False, encoding="utf-8-sig")

    # 其他指标稳健性
    alt_rows = []
    for col, label in [("nbi", "主买净流入率"), ("r0", "超大单净流入率"),
                       ("divergence", "超大单-全单分歧"), ("nbi_s5", "5 日累计主买")]:
        st = corr_stats(df[col], df["r_next"], n_boot=200)
        alt_rows.append({"指标": label, "corr": st["pearson"], "p": st["p_pearson"],
                         "spearman": st["spearman"], "ci_low": st["ci_low"], "ci_high": st["ci_high"]})
    alt = pd.DataFrame(alt_rows)

    # 多重检验校正（预测性检验族）
    family = [
        ("次日相关 Pearson", nxt["p_pearson"]),
        ("次日相关 Spearman", nxt["p_spearman"]),
        ("回归 NBI 系数", reg_uni["p"]["nbi"]),
        ("回归 NBI 系数(控制)", reg_ctrl["p"]["nbi"]),
    ]
    family += [(f"指标:{r['指标']}", r["p"]) for _, r in alt.iterrows() if r["指标"] != "主买净流入率"]
    family += [(f"期限:{r['horizon']}", r["p"]) for _, r in horizon.iterrows() if r["horizon"] != "1 日"]
    family += [(f"状态:{r['regime']}", r["p"]) for _, r in regime.iterrows()]

    labels = [f[0] for f in family]
    raw_p = [f[1] for f in family]
    adj_p = bh_adjust(raw_p)
    bh = pd.DataFrame({"检验": labels, "原始 p": raw_p, "BH 校正 p": adj_p,
                       "校正后显著": ["是" if p < 0.05 else "否" for p in adj_p]}).round(4)
    bh.to_csv(TABLE_DIR / "t08_bh.csv", index=False, encoding="utf-8-sig")

    alt.round(4).to_csv(TABLE_DIR / "t09_indicators.csv", index=False, encoding="utf-8-sig")

    # 滚动相关：取次日相关最大值及对应日期，供报告引用
    roll_next = df["nbi"].rolling(250).corr(df["r_next"])
    roll_same = df["nbi"].rolling(250).corr(df["r"])
    peak_idx = roll_next.idxmax()
    rolling = {
        "same_min": float(roll_same.min()),
        "same_max": float(roll_same.max()),
        "next_min": float(roll_next.min()),
        "next_max": float(roll_next.max()),
        "next_max_date": str(df.loc[peak_idx, "date"].date()),
        "next_current": float(roll_next.iloc[-1]),
        "same_current": float(roll_same.iloc[-1]),
        "next_positive_share": float((roll_next.dropna() > 0).mean()),
    }

    # 数据一致性校验：净额/净流入率 反推的成交额应与指数成交额一致
    implied = df["netamount"] / df["ratioamount"].replace(0, np.nan)
    ratio = (implied / df["amount"]).replace([np.inf, -np.inf], np.nan).dropna()
    data_check = {
        "implied_ratio_median": float(ratio.median()),
        "corr_implied_actual": float(implied.corr(df["amount"])),
    }

    # 成交额量级变化（用于说明为何采用比率而非绝对净额）
    amt_2012 = df.loc[df.date.dt.year == 2012, "amount"].mean()
    amt_last = df.loc[df.date.dt.year == df.date.dt.year.max(), "amount"].mean()
    turnover_growth = {
        "y2012_yi": float(amt_2012 / 1e8),
        "y_last_yi": float(amt_last / 1e8),
        "ratio": float(amt_last / amt_2012),
        "last_year": int(df.date.dt.year.max()),
    }

    results = {
        "sample": {"start": str(df.date.min().date()), "end": str(df.date.max().date()),
                   "n": int(len(df))},
        "data_check": data_check,
        "turnover_growth": turnover_growth,
        "rolling": rolling,
        "same_day": same,
        "next_day": nxt,
        "regression": {"univariate": reg_uni, "controlled": reg_ctrl,
                       "same_day": reg_same},
        "decile": {"z": dec.drop(columns=[]).to_dict(orient="records"),
                   "long_short": dec.attrs["long_short"],
                   "raw_long_short": dec_raw.attrs["long_short"]},
        "regime": regime.to_dict(orient="records"),
        "horizon": horizon.to_dict(orient="records"),
        "subsample": sub.to_dict(orient="records"),
        "indicators": alt.to_dict(orient="records"),
        "bh": {"n_tests": len(labels), "n_raw_sig": int(sum(p < 0.05 for p in raw_p)),
               "n_adj_sig": int(sum(p < 0.05 for p in adj_p))},
        "descriptive": desc.to_dict(orient="index"),
    }
    (TABLE_DIR.parent / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
    return results


if __name__ == "__main__":
    res = run()
    print(json.dumps({k: res[k] for k in ["sample", "same_day", "next_day", "bh"]},
                     ensure_ascii=False, indent=2, default=float))
