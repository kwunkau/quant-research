"""数据抓取：baostock 行业 ETF 日线 + 新浪单只 ETF 资金流。

设计要点：
1. 全部落盘缓存，`force=True` 才重新抓取，保证离线可复现；
2. 每个数据源都做行数、日期、字段校验，失败给出明确提示；
3. baostock 连接会超时/断开，查询失败时重新登录并退避重试；
4. 新浪资金流仅 2025-02 起有数据，用于代理校验与 2026 案例，不用于长样本。
"""

from __future__ import annotations

import json
import time
from datetime import datetime

import pandas as pd
import requests

from .config import (
    DATA_RAW,
    END_DATE,
    ETF_UNIVERSE,
    FETCH_START,
    FLOW_START,
    MIN_HISTORY_DAYS,
    ensure_dirs,
)

BAOSTOCK_FIELDS = "date,open,high,low,close,volume,amount,turn,pctChg"
DAILY_COLS = ["code", "name", "industry", "date", "open", "high", "low",
              "close", "volume", "amount", "turn", "pctChg"]

SINA_URL = ("https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
            + "Money" + "Flow" + ".ssl_qsfx_zjlrqs")
SINA_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Referer": "https://finance.sina.com.cn/",
}


# ---------------------------------------------------------------- baostock 日线

def _query_one(code: str, start: str, end: str, retries: int = 4) -> pd.DataFrame:
    """查询单只 ETF 日线；失败时重新登录并退避重试。"""
    import baostock as bs

    last_err: Exception | None = None
    for attempt in range(retries):
        logged_in = False
        try:
            lg = bs.login()
            logged_in = lg.error_code == "0"
            rs = bs.query_history_k_data_plus(
                code, BAOSTOCK_FIELDS, start_date=start, end_date=end,
                frequency="d", adjustflag="3",
            )
            if rs.error_code != "0":
                raise RuntimeError(f"{code} 查询失败：{rs.error_msg}")
            rows = []
            while rs.error_code == "0" and rs.next():
                rows.append(rs.get_row_data())
            if len(rows) < 20:
                raise RuntimeError(f"{code} 返回记录过少：{len(rows)}")
            return pd.DataFrame(rows, columns=BAOSTOCK_FIELDS.split(","))
        except Exception as exc:  # noqa: BLE001 - 网络异常种类多，统一重试
            last_err = exc
            time.sleep(1.5 * (attempt + 1))
        finally:
            if logged_in:
                try:
                    bs.logout()
                except Exception:  # noqa: BLE001
                    pass
    raise RuntimeError(f"{code} 抓取失败（重试 {retries} 次）") from last_err


def fetch_etf_daily(force: bool = False) -> pd.DataFrame:
    """全部行业 ETF 日线（不复权价格 + 成交额 + 换手率 + 涨跌幅）。"""
    ensure_dirs()
    cache = DATA_RAW / "etf_daily.csv"
    if cache.exists() and not force:
        return pd.read_csv(cache, parse_dates=["date"])

    frames = []
    for code, name, industry in ETF_UNIVERSE:
        raw = _query_one(code, FETCH_START, END_DATE)
        raw.insert(0, "industry", industry)
        raw.insert(0, "name", name)
        raw.insert(0, "code", code)
        frames.append(raw)
        print(f"[fetch] {code} {name} {len(raw)} 行 "
              f"{raw.date.min()}~{raw.date.max()}")

    df = pd.concat(frames, ignore_index=True)
    df["date"] = pd.to_datetime(df["date"])
    for col in ["open", "high", "low", "close", "volume", "amount", "turn", "pctChg"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df[DAILY_COLS].sort_values(["code", "date"]).reset_index(drop=True)

    # 校验
    assert not df.duplicated(["code", "date"]).any(), "存在重复的 code+date"
    assert (df["close"] > 0).all(), "收盘价存在非正值"
    counts = df.groupby("code").size()
    short = counts[counts < MIN_HISTORY_DAYS]
    assert short.empty, f"以下 ETF 历史不足 {MIN_HISTORY_DAYS} 日：{short.to_dict()}"

    df.to_csv(cache, index=False, encoding="utf-8-sig")
    meta = {
        "source": "baostock query_history_k_data_plus（ETF 日线，不复权）",
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "start": str(df.date.min().date()),
        "end": str(df.date.max().date()),
        "n_rows": int(len(df)),
        "n_codes": int(df.code.nunique()),
    }
    (DATA_RAW / "etf_daily.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return df


# ---------------------------------------------------------------- 新浪资金流

def _sina_one(code: str, retries: int = 6) -> pd.DataFrame | None:
    """单只 ETF 资金流；接口偶发限流，重试后仍失败则返回 None。"""
    daima = code.replace(".", "")
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            resp = requests.get(
                SINA_URL,
                params={"page": 1, "num": 3000, "sort": "opendate",
                        "asc": 1, "daima": daima},
                headers=SINA_HEADERS, timeout=30,
            )
            resp.raise_for_status()
            raw = json.loads(resp.text)
            if not isinstance(raw, list) or not raw:
                raise ValueError(f"返回为空或格式异常（{len(raw) if isinstance(raw, list) else '?'}）")
            df = pd.DataFrame(raw)
            df["date"] = pd.to_datetime(df["opendate"])
            for col in ["netamount", "ratioamount", "r0_net", "turnover"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            df = df[["date", "netamount", "ratioamount", "r0_net", "turnover"]]
            return df
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(1.5 * (attempt + 1))
    print(f"[fetch] 警告：{code} 资金流抓取失败：{last_err}")
    return None


def fetch_sina_flow(force: bool = False) -> pd.DataFrame:
    """单只 ETF 主力资金流（新浪，2025-02 起）。"""
    ensure_dirs()
    cache = DATA_RAW / "sina_etf_flow.csv"
    if cache.exists() and not force:
        return pd.read_csv(cache, parse_dates=["date"])

    frames = []
    for code, name, industry in ETF_UNIVERSE:
        df = _sina_one(code)
        if df is None:
            continue
        df = df[df["date"] >= pd.Timestamp(FLOW_START)].copy()
        df = df[df["turnover"].fillna(0) > 0]
        df.insert(0, "industry", industry)
        df.insert(0, "name", name)
        df.insert(0, "code", code)
        frames.append(df)
        print(f"[fetch] {code} {name} 资金流 {len(df)} 行")
        time.sleep(0.4)

    if not frames:
        raise RuntimeError(
            "新浪 ETF 资金流全部抓取失败。请检查网络后重试；"
            "若接口不可用，可跳过 2026 案例对照，但长样本回测不受影响。"
        )

    out = pd.concat(frames, ignore_index=True)
    out = out.sort_values(["code", "date"]).reset_index(drop=True)
    out.to_csv(cache, index=False, encoding="utf-8-sig")
    meta = {
        "source": "新浪财经 MoneyFlow 单只 ETF 资金流接口",
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "start": str(out.date.min().date()),
        "end": str(out.date.max().date()),
        "n_rows": int(len(out)),
        "n_codes": int(out.code.nunique()),
    }
    (DATA_RAW / "sina_etf_flow.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return out


def build_raw(force: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    daily = fetch_etf_daily(force=force)
    flow = fetch_sina_flow(force=force)
    print(f"[fetch] ETF 日线 {len(daily):,} 行，{daily.code.nunique()} 只，"
          f"{daily.date.min():%Y-%m-%d}~{daily.date.max():%Y-%m-%d}")
    print(f"[fetch] 资金流   {len(flow):,} 行，{flow.code.nunique()} 只，"
          f"{flow.date.min():%Y-%m-%d}~{flow.date.max():%Y-%m-%d}")
    return daily, flow


if __name__ == "__main__":
    build_raw(force=True)
