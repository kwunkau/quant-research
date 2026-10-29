"""数据抓取：新浪沪深300板块资金流 + baostock 沪深300指数日线。

设计要点：
1. 全部落盘缓存，`force=True` 才重新抓取，保证离线可复现。
2. 每个数据源都有断言校验（行数、日期区间、关键字段非空）。
3. baostock 的 ResultData.get_data() 在 pandas 2.x 下不可用（内部调用 df.append），
   这里统一用 while + get_row_data() 逐行读取。
"""

from __future__ import annotations

import json
import time
from datetime import datetime

import pandas as pd
import requests

from .config import (
    BAOSTOCK_CODE,
    DATA_RAW,
    END_DATE,
    FETCH_START,
    SINA_FLOW_URL,
    ensure_dirs,
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Referer": "https://finance.sina.com.cn/",
}

FLOW_COLUMNS = [
    "date",
    "netamount",
    "ratioamount",
    "r0_net",
    "r0_ratio",
    "turnover",
    "avg_changeratio",
]


def _get_json(url: str, params: dict, retries: int = 3, timeout: int = 40):
    """带重试与退避的 JSON GET，返回解析后的对象。"""
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
            resp.raise_for_status()
            return json.loads(resp.text)
        except Exception as exc:  # noqa: BLE001 - 网络异常种类多，统一重试
            last_err = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"请求失败（重试 {retries} 次）：{url}") from last_err


def fetch_sina_flow(force: bool = False) -> pd.DataFrame:
    """沪深300板块日度资金流（2010-03 至今）。"""
    ensure_dirs()
    cache = DATA_RAW / "sina_hs300_flow.csv"
    if cache.exists() and not force:
        return pd.read_csv(cache, parse_dates=["date"])

    raw = _get_json(
        SINA_FLOW_URL,
        {"page": 1, "num": 5000, "sort": "opendate", "asc": 1, "bankuai": "hs300"},
    )
    if not isinstance(raw, list) or len(raw) < 3000:
        raise ValueError(f"新浪资金流返回异常，记录数={len(raw) if raw else 0}")

    df = pd.DataFrame(raw)
    df["date"] = pd.to_datetime(df["opendate"])
    numeric = ["netamount", "ratioamount", "r0_net", "r0_ratio", "turnover", "avg_changeratio"]
    df[numeric] = df[numeric].apply(pd.to_numeric, errors="coerce")
    df = df[FLOW_COLUMNS].sort_values("date").reset_index(drop=True)

    assert df["ratioamount"].notna().all(), "资金流净流入率存在缺失"
    assert (df["date"].diff().dropna().dt.days > 0).all(), "资金流日期未严格递增"
    df.to_csv(cache, index=False, encoding="utf-8-sig")

    meta = {"source": "新浪财经 MoneyFlow 板块资金流", "fetched_at": datetime.now().isoformat()}
    (DATA_RAW / "sina_hs300_flow.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return df


def fetch_index_daily(force: bool = False) -> pd.DataFrame:
    """沪深300指数日线（baostock，前复权口径对指数无影响）。"""
    ensure_dirs()
    cache = DATA_RAW / "hs300_daily.csv"
    if cache.exists() and not force:
        return pd.read_csv(cache, parse_dates=["date"])

    import baostock as bs

    lg = bs.login()
    if lg.error_code != "0":
        raise RuntimeError(f"baostock 登录失败：{lg.error_msg}")

    try:
        rs = bs.query_history_k_data_plus(
            BAOSTOCK_CODE,
            "date,open,high,low,close,volume,amount",
            start_date=FETCH_START,
            end_date=END_DATE,
            frequency="d",
            adjustflag="3",
        )
        rows = []
        while rs.error_code == "0" and rs.next():
            rows.append(rs.get_row_data())
    finally:
        bs.logout()

    if len(rows) < 3000:
        raise ValueError(f"baostock 指数日线返回异常，记录数={len(rows)}")

    df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume", "amount"])
    df["date"] = pd.to_datetime(df["date"])
    for col in ["open", "high", "low", "close", "volume", "amount"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)

    assert (df["close"] > 0).all(), "指数收盘价存在非正值"
    df.to_csv(cache, index=False, encoding="utf-8-sig")
    return df


def build_raw(force: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    flow = fetch_sina_flow(force=force)
    index = fetch_index_daily(force=force)
    print(f"[fetch] 新浪资金流 {len(flow)} 行 {flow.date.min():%Y-%m-%d}~{flow.date.max():%Y-%m-%d}")
    print(f"[fetch] 指数日线   {len(index)} 行 {index.date.min():%Y-%m-%d}~{index.date.max():%Y-%m-%d}")
    return flow, index


if __name__ == "__main__":
    build_raw(force=True)
