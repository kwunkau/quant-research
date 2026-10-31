"""特征构建：面板、超额收益、成交额/市值占比、资金流强度代理。

口径说明（报告第 2 节会原样解释）：
- 公开数据没有 Wind 的主动买/卖金额，用 Chaikin 资金流乘数 MFM 作代理：
  MFM = ((C-L) - (H-C)) / (H-L)，取值 [-1, 1]；
- 研报的 Q_i / V_i 在“买卖总额相等”的代理下会退化为 MFM_i，因此基础因子就是
  W 日资金流强度（CMF 类），不是对 Wind 口径的逐字复刻；
- 资金流向图的输入仍按研报定义：Q_i 为净流入占比（截面和为 0），
  V_i 为成交额占比，S_i 为由换手率反推的流通市值占比，H_i 为超额收益。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import ADV_WINDOW, DATA_PROCESSED, MIN_HISTORY_DAYS, ensure_dirs

PANEL_KEYS = ["open", "high", "low", "close", "volume", "amount", "turn", "pct"]


def build_panel(daily: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """把长表转成 date × code 的宽面板。"""
    daily = daily.copy()
    daily["pct"] = daily["pctChg"] / 100.0
    panels = {}
    for key in PANEL_KEYS:
        panels[key] = daily.pivot(index="date", columns="code", values=key).sort_index()
    panels["meta"] = (
        daily[["code", "name", "industry"]].drop_duplicates("code")
        .set_index("code")
    )
    return panels


def money_flow_multiplier(high: pd.DataFrame, low: pd.DataFrame,
                          close: pd.DataFrame) -> pd.DataFrame:
    """Chaikin 资金流乘数；H=L 或缺失时记 0。"""
    rng = (high - low).replace(0, np.nan)
    mfm = ((close - low) - (high - close)) / rng
    return mfm.clip(-1, 1).fillna(0.0)


def build_features(daily: pd.DataFrame) -> dict:
    """计算全部日频特征，返回面板字典。"""
    p = build_panel(daily)
    pct, amount, turn = p["pct"], p["amount"], p["turn"]

    # 可投域：上市满 120 个交易日、当日有成交与收益
    n_obs = pct.notna().cumsum()
    mask = (n_obs >= MIN_HISTORY_DAYS) & pct.notna() & amount.notna() & (amount > 0)

    pct_m = pct.where(mask)
    excess = pct_m.sub(pct_m.mean(axis=1), axis=0)

    amt_m = amount.where(mask)
    v_share = amt_m.div(amt_m.sum(axis=1), axis=0)

    # 流通市值代理：成交额 / 换手率（换手率为百分数）
    cap = (amount / (turn / 100.0)).where(mask)
    s_share = cap.div(cap.sum(axis=1), axis=0)

    mfm = money_flow_multiplier(p["high"], p["low"], p["close"]).where(mask)
    # 净流入占比 = MFM × 成交额占比；截面去均值保证 ΣQ = 0
    q_share = (mfm * v_share)
    q_share = q_share.sub(q_share.where(mask).mean(axis=1), axis=0)

    adv = amount.rolling(ADV_WINDOW, min_periods=max(5, ADV_WINDOW // 2)).mean()

    p.update({
        "mask": mask,
        "excess": excess,
        "v_share": v_share,
        "s_share": s_share,
        "mfm": mfm,
        "q_share": q_share,
        "adv": adv,
        "n_obs": n_obs,
    })
    return p


def add_rolling_factors(feats: dict, w: int) -> dict:
    """对基础因子与（稍后求解出的）微观因子做 W 日移动平均 + 截面标准化。"""
    mfm = feats["mfm"]
    mask = feats["mask"]
    base = mfm.rolling(w, min_periods=max(5, int(w * 0.8))).mean()
    base = base.where(mask)
    feats[f"base_w{w}"] = zscore_cs(base, mask)
    feats[f"base_raw_w{w}"] = base
    return feats


def zscore_cs(df: pd.DataFrame, mask: pd.DataFrame | None = None) -> pd.DataFrame:
    """逐日截面标准化；缺失值保持缺失。"""
    x = df.where(mask) if mask is not None else df
    mu = x.mean(axis=1)
    sd = x.std(axis=1, ddof=0).replace(0, np.nan)
    return x.sub(mu, axis=0).div(sd, axis=0)


def cross_section(feats: dict, date: pd.Timestamp) -> dict | None:
    """取某日的截面输入；不足 6 只标的返回 None。"""
    mask = feats["mask"].loc[date]
    codes = mask[mask].index
    if len(codes) < 6:
        return None
    return {
        "date": date,
        "codes": list(codes),
        "Q": feats["q_share"].loc[date, codes].to_numpy(float),
        "H": feats["excess"].loc[date, codes].to_numpy(float),
        "V": feats["v_share"].loc[date, codes].to_numpy(float),
        "S": feats["s_share"].loc[date, codes].to_numpy(float),
        "mfm": feats["mfm"].loc[date, codes].to_numpy(float),
    }


def build_dataset(daily: pd.DataFrame | None = None) -> dict:
    """读取/构建特征并缓存基础面板（宽表，parquet 不便离线时用 pickle）。"""
    ensure_dirs()
    if daily is None:
        from .fetch_data import fetch_etf_daily

        daily = fetch_etf_daily()
    feats = build_features(daily)
    for w in (15, 20, 25):
        feats = add_rolling_factors(feats, w)
    return feats
