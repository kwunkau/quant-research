"""周度行业 ETF 轮动回测与 5000 万资金模拟。

关键口径：
- 信号：每周最后一个交易日收盘计算，次一交易日按 VWAP（成交额/成交量）成交；
- 组合：因子前 N 名等权，100 份整数手，剩余现金留存；
- 成本：佣金 + 半价差 + 平方根冲击；参与率 = 成交额 / ADV20，上限 5%；
- 份额折算：用“价格比 / (1+涨跌幅)”识别，折算日同步调整份额；
- 所有价格只用于成交与估值，收益路径以不复权收盘价 + 份额折算调整计。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import (
    ADV_MIN_YI,
    CAPITAL,
    COMMISSION_BPS,
    END_DATE,
    HALF_SPREAD_BPS,
    IMPACT_BPS_AT_5PCT,
    LOT_SIZE,
    MAX_PARTICIPATION,
    START_DATE,
    TOP_N,
)


# ---------------------------------------------------------------- 因子面板

def winsor_cs(df: pd.DataFrame, mask: pd.DataFrame | None = None,
              lo: float = 0.01, hi: float = 0.99) -> pd.DataFrame:
    """逐日截面 1%/99% 缩尾，避免极端值主导 z 分数。"""
    x = df.where(mask) if mask is not None else df
    q = x.quantile([lo, hi], axis=1).T
    return x.clip(lower=q[lo], upper=q[hi], axis=0)


def zscore_cs(df: pd.DataFrame, mask: pd.DataFrame | None = None) -> pd.DataFrame:
    x = df.where(mask) if mask is not None else df
    mu = x.mean(axis=1)
    sd = x.std(axis=1, ddof=0).replace(0, np.nan)
    return x.sub(mu, axis=0).div(sd, axis=0)


def build_factor_panels(feats: dict, micro: pd.DataFrame) -> dict:
    """构造基础因子、四个微观因子与综合因子（W=15/20/25）。"""
    mask = feats["mask"]
    micro_p = {
        col: micro.pivot(index="date", columns="code", values=col).reindex(
            index=mask.index, columns=mask.columns
        ).replace([np.inf, -np.inf], np.nan)
        for col in ["max_in", "breadth", "out_sum", "external"]
    }

    out = {"components": {}}
    for w in (15, 20, 25):
        comps = {}
        base = feats[f"base_w{w}"]
        comps["base"] = zscore_cs(winsor_cs(base, mask), mask)
        for name, panel in micro_p.items():
            ma = panel.rolling(w, min_periods=max(5, int(w * 0.8))).mean()
            comps[name] = zscore_cs(winsor_cs(ma, mask), mask)
        keys = ["base", "max_in", "breadth", "out_sum", "external"]
        composite = pd.concat([comps[k] for k in keys]).groupby(level=0).mean()
        comps["composite"] = zscore_cs(composite.where(mask), mask)
        out["components"][w] = comps
        out[f"base_w{w}"] = comps["base"]
        out[f"composite_w{w}"] = comps["composite"]
    return out


# ---------------------------------------------------------------- 工具

def split_factors(feats: dict) -> pd.DataFrame:
    """份额折算因子：shares /= factor；正常日 =1。"""
    close, pct = feats["close"], feats["pct"]
    ratio = close / close.shift(1)
    implied = 1.0 + pct
    factor = (ratio / implied).replace([np.inf, -np.inf], np.nan)
    factor = factor.where((factor - 1).abs() > 0.1, 1.0).fillna(1.0)
    return factor


def weekly_signal_dates(index: pd.DatetimeIndex) -> list[pd.Timestamp]:
    """每个 ISO 周最后一个交易日。"""
    s = pd.Series(index, index=index)
    week = pd.Series(index.strftime("%G-%V"), index=index)
    return list(s.groupby(week).max().sort_values())


def _cost_bps(participation: float, commission_bps: float,
              half_spread_bps: float, impact_bps_at_5pct: float) -> float:
    if participation <= 0:
        return 0.0
    impact = impact_bps_at_5pct * np.sqrt(participation / MAX_PARTICIPATION)
    return commission_bps + half_spread_bps + impact


# ---------------------------------------------------------------- 回测引擎

def run_engine(feats: dict, factor: pd.DataFrame, top_n: int = TOP_N,
               capital: float = CAPITAL, cost: bool = True, cap: bool = True,
               benchmark: bool = False,
               commission_bps: float = COMMISSION_BPS,
               half_spread_bps: float = HALF_SPREAD_BPS,
               impact_bps_at_5pct: float = IMPACT_BPS_AT_5PCT,
               adv_min: float = ADV_MIN_YI * 1e8) -> dict:
    """按周调仓的日频资金曲线引擎。

    benchmark=True 时持有全部可投标的等权（行业等权基准）。
    """
    dates = feats["pct"].index
    dates = dates[(dates >= pd.Timestamp(START_DATE)) & (dates <= pd.Timestamp(END_DATE))]
    closes = feats["close"].ffill()
    pct = feats["pct"].fillna(0.0)
    vwap = (feats["amount"] / feats["volume"]).replace([np.inf, -np.inf], np.nan)
    vwap = vwap.where(vwap > 0).fillna(closes)
    adv = feats["adv"].ffill()
    mask = feats["mask"]
    splits = split_factors(feats)

    signal_dates = weekly_signal_dates(dates)
    exec_map = {}
    for sd in signal_dates:
        pos = dates.get_loc(sd)
        if pos + 1 < len(dates):
            exec_map[dates[pos + 1]] = sd

    shares: dict[str, float] = {}
    cash = float(capital)
    records = []
    trades = []

    for d in dates:
        # 1) 份额折算
        for code in list(shares):
            f = splits.at[d, code] if code in splits.columns else 1.0
            if np.isfinite(f) and f > 0 and abs(f - 1) > 1e-9:
                shares[code] = shares[code] / f

        close_d = closes.loc[d]
        value_pre = cash + sum(sh * close_d.get(c, np.nan) for c, sh in shares.items()
                               if np.isfinite(close_d.get(c, np.nan)))

        if d in exec_map:
            sd = exec_map[d]
            row = factor.loc[sd]
            eligible = mask.loc[sd]
            if benchmark:
                candidates = list(eligible[eligible].index)
            else:
                liquid = adv.loc[sd] >= adv_min if cap else pd.Series(True, index=adv.columns)
                candidates = list((eligible & liquid & row.notna()).loc[lambda s: s].index)
            ranked = row[candidates].dropna().sort_values(ascending=False)
            targets = list(ranked.index[:top_n]) if not benchmark else candidates

            price_d = vwap.loc[d]
            if targets:
                target_value = value_pre * 0.998 / max(len(targets), 1)
            else:
                target_value = 0.0

            def _plan(code: str, delta: float, price: float) -> dict | None:
                adv_t = adv.at[sd, code] if code in adv.columns else np.nan
                trade_value = abs(delta) * price
                participation = (trade_value / adv_t
                                 if (np.isfinite(adv_t) and adv_t > 0) else np.inf)
                binding = False
                if cap and (not np.isfinite(participation)
                            or participation > MAX_PARTICIPATION):
                    max_value = (MAX_PARTICIPATION * adv_t
                                 if (np.isfinite(adv_t) and adv_t > 0) else 0.0)
                    max_shares = np.floor(max_value / price / LOT_SIZE) * LOT_SIZE
                    delta = np.sign(delta) * min(abs(delta), max_shares)
                    if delta == 0:
                        return None
                    trade_value = abs(delta) * price
                    participation = trade_value / adv_t if adv_t > 0 else np.nan
                    binding = True
                bps = (_cost_bps(participation, commission_bps, half_spread_bps,
                                 impact_bps_at_5pct) if cost else 0.0)
                return {"code": code, "delta": float(delta), "price": price,
                        "value": trade_value, "participation": participation,
                        "cost_bps": bps, "cost": trade_value * bps / 1e4,
                        "binding": binding}

            sells, buys = [], []
            for code in set(list(shares) + targets):
                cur = shares.get(code, 0.0)
                price = price_d.get(code, np.nan)
                if not np.isfinite(price) or price <= 0:
                    continue
                desired = (np.floor(target_value / price / LOT_SIZE) * LOT_SIZE
                           if code in targets else 0.0)
                delta = desired - cur
                if delta < 0:
                    plan = _plan(code, delta, price)
                    if plan is not None:
                        sells.append(plan)
                elif delta > 0:
                    plan = _plan(code, delta, price)
                    if plan is not None:
                        buys.append(plan)

            # 先卖
            for p in sells:
                code = p["code"]
                shares[code] = shares.get(code, 0.0) + p["delta"]
                cash -= p["delta"] * p["price"] + p["cost"]
                trades.append({"date": d, "signal_date": sd, "code": code,
                               "side": "sell", "shares": abs(p["delta"]),
                               "price": p["price"], "value": p["value"],
                               "participation": p["participation"],
                               "cost_bps": p["cost_bps"], "cost": p["cost"],
                               "binding": p["binding"]})
                if shares[code] <= 0:
                    shares.pop(code, None)

            # 再买；现金不足时按比例缩减（只影响未成交部分，保留现金）
            total_buy = sum(p["delta"] * p["price"] + p["cost"] for p in buys)
            if total_buy > cash and total_buy > 0:
                scale = max(cash, 0.0) / total_buy
                for p in buys:
                    new_delta = np.floor(p["delta"] * scale / LOT_SIZE) * LOT_SIZE
                    p["delta"] = float(new_delta) if new_delta > 0 else 0.0
                    p["value"] = p["delta"] * p["price"]
                    p["cost"] = p["value"] * p["cost_bps"] / 1e4

            for p in buys:
                if p["delta"] == 0:
                    continue
                code = p["code"]
                shares[code] = shares.get(code, 0.0) + p["delta"]
                cash -= p["delta"] * p["price"] + p["cost"]
                trades.append({"date": d, "signal_date": sd, "code": code,
                               "side": "buy", "shares": abs(p["delta"]),
                               "price": p["price"], "value": p["value"],
                               "participation": p["participation"],
                               "cost_bps": p["cost_bps"], "cost": p["cost"],
                               "binding": p["binding"]})

        close_post = closes.loc[d]
        value = cash + sum(sh * close_post.get(c, np.nan) for c, sh in shares.items()
                           if np.isfinite(close_post.get(c, np.nan)))
        records.append({"date": d, "value": value, "cash": cash,
                        "n_pos": len(shares)})

    nav = pd.DataFrame(records).set_index("date")
    nav["ret"] = nav["value"].pct_change(fill_method=None).fillna(0.0)
    trade_df = pd.DataFrame(trades)
    if not trade_df.empty:
        nav["turnover"] = trade_df.groupby("date").value.sum().reindex(nav.index).fillna(0.0)
        nav["cost"] = trade_df.groupby("date").cost.sum().reindex(nav.index).fillna(0.0)
        nav["max_participation"] = (trade_df.groupby("date").participation.max()
                                    .reindex(nav.index).fillna(0.0))
        binding = trade_df.groupby("date").binding.max().reindex(nav.index)
        nav["binding"] = binding.astype(float).fillna(0.0).astype(bool)
    else:
        nav["turnover"] = 0.0
        nav["cost"] = 0.0
        nav["max_participation"] = 0.0
        nav["binding"] = False
    return {"nav": nav, "trades": trade_df}
