"""特征构建：把资金流与指数日线合并成研究数据集。"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import DATA_PROCESSED, START_DATE, ensure_dirs
from .fetch_data import build_raw

Z_WINDOW = 250
Z_MIN_PERIODS = 120


def build_dataset(force: bool = False) -> pd.DataFrame:
    """返回建模用日频数据集（日期为索引，含全部指标）。"""
    ensure_dirs()
    cache = DATA_PROCESSED / "dataset.csv"
    if cache.exists() and not force:
        return pd.read_csv(cache, parse_dates=["date"])

    flow, index = build_raw(force=False)
    df = index.merge(flow, on="date", how="inner").sort_values("date").reset_index(drop=True)
    df = df.loc[df["date"] >= pd.Timestamp(START_DATE)].reset_index(drop=True)

    # 收益：t 日实现收益、t+1 待预测收益、多周期远期收益
    df["r"] = df["close"].pct_change()
    df["r_next"] = df["r"].shift(-1)
    for k in (5, 10, 20):
        df[f"r_fwd{k}"] = df["close"].shift(-k) / df["close"] - 1

    # 状态变量
    df["vol20"] = df["r"].rolling(20).std()
    df["ma250"] = df["close"].rolling(250).mean()
    df["bull"] = df["close"] > df["ma250"]
    df["log_amount"] = np.log(df["amount"].replace(0, np.nan))

    # 主买指标
    df["nbi"] = df["ratioamount"]                 # 主动买入净额 / 成交额
    df["r0"] = df["r0_ratio"]                     # 超大单净流入率
    df["divergence"] = df["r0"] - df["nbi"]       # 大单与全单的方向分歧
    df["nbi_s5"] = df["nbi"].rolling(5).sum()     # 5 日累计主买强度
    roll = df["nbi"].rolling(Z_WINDOW, min_periods=Z_MIN_PERIODS)
    df["nbi_z"] = (df["nbi"] - roll.mean()) / roll.std()

    df = df.dropna(subset=["r_next"]).reset_index(drop=True)
    df.to_csv(cache, index=False, encoding="utf-8-sig")
    return df


def describe(df: pd.DataFrame) -> pd.DataFrame:
    """描述统计表。"""
    cols = ["nbi", "r0", "divergence", "nbi_s5", "r", "vol20", "turnover", "amount"]
    out = df[cols].describe().T
    out["skew"] = df[cols].skew()
    out["kurt"] = df[cols].kurt()
    out["ac1"] = [df[c].autocorr(1) for c in cols]
    return out.round(4)


if __name__ == "__main__":
    data = build_dataset(force=True)
    print(data.shape, data.date.min().date(), data.date.max().date())
    print(describe(data).to_string())
