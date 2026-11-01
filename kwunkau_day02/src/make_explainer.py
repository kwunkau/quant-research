"""生成一页看懂版 HTML：大白话解释研报公式 + 本地回测结果。

用法：python -m src.make_explainer（run_all.py 第 7 步自动调用）
产物：output/kwunkau_day02_explainer.html（自包含，图片内嵌，可直接浏览器打开/打印）
所有数字从 results.json / 数据缓存读取，禁止手填。
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .config import (DATA_PROCESSED, DATA_RAW, FIG_DIR, GITHUB_NB_URL, KEY_DATES,
                     NBVIEWER_URL, OUTPUT, PROJECT_ID, REPO_URL, GITHUB_BRANCH)

# ---------------------------------------------------------------- 数据

res = json.loads((OUTPUT / "results.json").read_text(encoding="utf-8"))
p = res["performance"]
cap = pd.DataFrame(res["capacity"])
ic = res["ic"]
rv = res["review_2026"]
key = pd.DataFrame(rv["key_dates"])
monthly = pd.DataFrame(rv["monthly"])
ytd = pd.DataFrame(rv["ytd"]).set_index("code")
nav = pd.read_csv(OUTPUT / "nav_curves.csv", index_col=0, parse_dates=True)
micro = pd.read_csv(DATA_PROCESSED / "flow_micro.csv", parse_dates=["date"])
flow = pd.read_csv(DATA_RAW / "sina_etf_flow.csv", parse_dates=["date"])
meta = res["meta"]
ref = res["report_ref"]
facts = rv["facts"]
ps = meta["problem_size"]
semi_b = [f"{v * 100:.0f}%" for v in key["semi_breadth"]]


def pct(x: float, d: int = 1) -> str:
    return f"{x * 100:.{d}f}%"


def pp(x: float, d: int = 1) -> str:
    return f"{x * 100:+.{d}f} pct"


def b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


# ---------------------------------------------------------------- 小工具

def sparkline(series: pd.Series, w: int = 150, h: int = 36, color: str = "#2a78d6") -> str:
    s = series.dropna().to_numpy(float)
    if len(s) < 2:
        return ""
    s = s[:: max(1, len(s) // 80)]
    x = np.linspace(2, w - 2, len(s))
    lo, hi = s.min(), s.max()
    y = h - 4 - (s - lo) / (hi - lo + 1e-12) * (h - 8)
    pts = " ".join(f"{a:.1f},{b:.1f}" for a, b in zip(x, y))
    return (f'<svg class="spark" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'aria-label="净值走势"><polyline points="{pts}" fill="none" '
            f'stroke="{color}" stroke-width="2" stroke-linejoin="round" '
            f'stroke-linecap="round"/></svg>')


def hbar(label: str, value: float, vmax: float, color: str,
         suffix: str = "%", note: str = "") -> str:
    width = max(0.0, min(100.0, value / vmax * 100))
    return (f'<div class="hbar-row"><div class="hbar-label">{label}</div>'
            f'<div class="hbar-track"><div class="hbar-fill" style="width:{width:.1f}%;'
            f'background:{color}"></div></div>'
            f'<div class="hbar-value">{value:.1f}{suffix}</div>'
            f'<div class="hbar-note">{note}</div></div>')


# ---------------------------------------------------------------- 图：瀑布

def waterfall_svg() -> str:
    gross = p["gross_composite"]["cagr"] * 100
    capped = p["cap_only_composite_50m"]["cagr"] * 100
    net = p["net_composite_50m"]["cagr"] * 100
    rows = [("理论组合", gross, 0, gross, "#2a78d6"),
            ("容量/执行", capped - gross, gross, capped, "#eb6834"),
            ("交易成本", net - capped, capped, net, "#eb6834"),
            ("5000 万净结果", net, 0, net, "#2a78d6")]
    w, h = 720, 230
    left, right, top, bottom = 58, 18, 18, 38
    plot_w, plot_h = w - left - right, h - top - bottom
    ymax = max(10.0, np.ceil(gross / 2) * 2)
    def sy(v): return top + plot_h - v / ymax * plot_h
    bw = plot_w / (len(rows) * 1.55)
    parts = []
    for i, (label, val, y0, y1, color) in enumerate(rows):
        x = left + (i + 0.5) * plot_w / len(rows)
        top_y, bot_y = sy(max(y0, y1)), sy(min(y0, y1))
        hh = max(2, bot_y - top_y)
        parts.append(f'<rect x="{x - bw/2:.1f}" y="{top_y:.1f}" width="{bw:.1f}" '
                     f'height="{hh:.1f}" rx="3" fill="{color}" opacity="0.92"/>')
        sign = "+" if val > 0 else ""
        parts.append(f'<text x="{x:.1f}" y="{top_y - 6:.1f}" text-anchor="middle" '
                     f'class="svg-val">{sign}{val:.1f}%</text>')
        parts.append(f'<text x="{x:.1f}" y="{h - 14}" text-anchor="middle" '
                     f'class="svg-lab">{label}</text>')
        if i < len(rows) - 1:
            nx = left + (i + 1.5) * plot_w / len(rows)
            parts.append(f'<line x1="{x + bw/2:.1f}" y1="{sy(y1):.1f}" '
                         f'x2="{nx - bw/2:.1f}" y2="{sy(y1):.1f}" '
                         f'stroke="#c3c2b7" stroke-width="1"/>')
    grid = "".join(
        f'<line x1="{left}" y1="{sy(v):.1f}" x2="{w-right}" y2="{sy(v):.1f}" '
        f'stroke="#e1e0d9" stroke-width="1"/>'
        f'<text x="{left-8}" y="{sy(v)+4:.1f}" text-anchor="end" class="svg-tick">{v:.0f}%</text>'
        for v in range(0, int(ymax) + 1, 2))
    return (f'<svg viewBox="0 0 {w} {h}" class="chart" role="img" '
            f'aria-label="从理论组合到 5000 万净结果的瀑布图">{grid}{"".join(parts)}</svg>')


# ---------------------------------------------------------------- 图：容量

def capacity_svg() -> str:
    df = cap.copy()
    x = np.log10(df["资金规模(万元)"].to_numpy(float))
    y = df["年化收益"].to_numpy(float) * 100
    w, h = 720, 250
    left, right, top, bottom = 56, 16, 22, 42
    plot_w, plot_h = w - left - right, h - top - bottom
    xmin, xmax = 2.9, 4.8
    ymin = min(y.min(), p["benchmark_gross"]["cagr"] * 100) - 0.4
    ymax = max(y.max(), p["benchmark_gross"]["cagr"] * 100) + 0.6
    def sx(v): return left + (v - xmin) / (xmax - xmin) * plot_w
    def sy(v): return top + plot_h - (v - ymin) / (ymax - ymin) * plot_h
    grid = []
    for v in range(int(np.ceil(ymin)), int(np.floor(ymax)) + 1):
        grid.append(f'<line x1="{left}" y1="{sy(v):.1f}" x2="{w-right}" y2="{sy(v):.1f}" '
                    f'stroke="#e1e0d9" stroke-width="1"/>'
                    f'<text x="{left-8}" y="{sy(v)+4:.1f}" text-anchor="end" class="svg-tick">{v}%</text>')
    ticks = [(3.0, "1000万"), (3.7, "5000万"), (4.0, "1亿"), (4.7, "5亿")]
    for v, label in ticks:
        grid.append(f'<text x="{sx(v):.1f}" y="{h-16}" text-anchor="middle" class="svg-tick">{label}</text>')
    # 基准线
    bench = p["benchmark_gross"]["cagr"] * 100
    grid.append(f'<line x1="{left}" y1="{sy(bench):.1f}" x2="{w-right}" y2="{sy(bench):.1f}" '
                f'stroke="#898781" stroke-width="1"/>'
                f'<text x="{w-right-2}" y="{sy(bench)-6:.1f}" text-anchor="end" class="svg-lab">'
                f'等权基准 {bench:.1f}%</text>')
    pts = " ".join(f"{sx(a):.1f},{sy(b):.1f}" for a, b in zip(x, y))
    dots = []
    for i, (a, b) in enumerate(zip(x, y)):
        color = "#eb6834" if int(df.iloc[i]["资金规模(万元)"]) == 5000 else "#2a78d6"
        r = 5 if color == "#eb6834" else 4
        dots.append(f'<circle cx="{sx(a):.1f}" cy="{sy(b):.1f}" r="{r}" fill="{color}" '
                    f'stroke="#fcfcfb" stroke-width="2"><title>{int(df.iloc[i]["资金规模(万元)"]):,} 万元：'
                    f'{b:.2f}%</title></circle>')
        if int(df.iloc[i]["资金规模(万元)"]) in (1000, 5000, 50000):
            dots.append(f'<text x="{sx(a):.1f}" y="{sy(b)-11:.1f}" text-anchor="middle" '
                        f'class="svg-val">{b:.1f}%</text>')
    return (f'<svg viewBox="0 0 {w} {h}" class="chart" role="img" '
            f'aria-label="容量曲线：不同资金规模下的净年化收益">{"".join(grid)}'
            f'<polyline points="{pts}" fill="none" stroke="#2a78d6" stroke-width="2"/>'
            f'{"".join(dots)}</svg>')


# ---------------------------------------------------------------- 图：2026 广度

def breadth_svg() -> str:
    b = micro[micro.code == "sh.512480"].set_index("date").breadth
    b = b.rolling(5, min_periods=1).mean().loc["2026-05-01":"2026-10-30"] * 100
    w, h = 720, 230
    left, right, top, bottom = 52, 16, 18, 36
    plot_w, plot_h = w - left - right, h - top - bottom
    x0, x1 = b.index.min(), b.index.max()
    def sx(t): return left + (t - x0) / (x1 - x0) * plot_w
    def sy(v): return top + plot_h - v / 100 * plot_h
    grid = []
    for v in [0, 25, 50, 75, 100]:
        grid.append(f'<line x1="{left}" y1="{sy(v):.1f}" x2="{w-right}" y2="{sy(v):.1f}" '
                    f'stroke="#e1e0d9" stroke-width="1"/>'
                    f'<text x="{left-8}" y="{sy(v)+4:.1f}" text-anchor="end" class="svg-tick">{v}%</text>')
    pts = " ".join(f"{sx(t):.1f},{sy(v):.1f}" for t, v in b.items())
    marks = []
    t0, t1 = pd.Timestamp(KEY_DATES[0]), pd.Timestamp(KEY_DATES[-1])
    marks.append(f'<rect x="{sx(t0):.1f}" y="{top}" width="{sx(t1)-sx(t0):.1f}" '
                 f'height="{plot_h}" fill="#2a78d6" opacity="0.08"/>')
    for t in (t0, t1):
        marks.append(f'<line x1="{sx(t):.1f}" y1="{top}" x2="{sx(t):.1f}" y2="{top+plot_h}" '
                     f'stroke="#c3c2b7" stroke-width="1"/>')
    marks.append(f'<text x="{(sx(t0)+sx(t1))/2:.1f}" y="{top+13}" text-anchor="middle" '
                 f'class="svg-lab">6/24–7/6 研报示例</text>')
    for t in pd.date_range(b.index.min().replace(day=1), b.index.max(), freq="MS"):
        marks.append(f'<text x="{sx(t):.1f}" y="{h-14}" text-anchor="middle" '
                     f'class="svg-tick">{t.month}月</text>')
    return (f'<svg viewBox="0 0 {w} {h}" class="chart" role="img" '
            f'aria-label="半导体净流入为正比例（5日均）">{"".join(grid)}'
            f'<polyline points="{pts}" fill="none" stroke="#2a78d6" stroke-width="2"/>'
            f'{"".join(marks)}</svg>')


# ---------------------------------------------------------------- 图：散点

def scatter_svg() -> str:
    b = micro.pivot(index="date", columns="code", values="breadth")
    f = flow.pivot(index="date", columns="code", values="ratioamount")
    dates = list(zip(KEY_DATES, ["#2a78d6", "#eb6834", "#1baf7a"]))
    rows = []
    for d, color in dates:
        t = pd.Timestamp(d)
        for code in b.columns:
            if code in f.columns and t in b.index and t in f.index:
                bv, fv = b.at[t, code], f.at[t, code]
                if pd.notna(bv) and pd.notna(fv):
                    rows.append((d, code, bv * 100, fv * 100, color))
    df = pd.DataFrame(rows, columns=["date", "code", "x", "y", "color"])
    w, h = 720, 260
    left, right, top, bottom = 56, 18, 18, 40
    plot_w, plot_h = w - left - right, h - top - bottom
    xmin, xmax = 0, 100
    ymin, ymax = -12, 16
    def sx(v): return left + (v - xmin) / (xmax - xmin) * plot_w
    def sy(v): return top + plot_h - (v - ymin) / (ymax - ymin) * plot_h
    grid = []
    for v in [0, 25, 50, 75, 100]:
        grid.append(f'<line x1="{sx(v):.1f}" y1="{top}" x2="{sx(v):.1f}" y2="{top+plot_h}" '
                    f'stroke="#e1e0d9" stroke-width="1"/>'
                    f'<text x="{sx(v):.1f}" y="{h-16}" text-anchor="middle" class="svg-tick">{v}%</text>')
    for v in [-10, -5, 0, 5, 10, 15]:
        grid.append(f'<line x1="{left}" y1="{sy(v):.1f}" x2="{w-right}" y2="{sy(v):.1f}" '
                    f'stroke="#e1e0d9" stroke-width="1"/>'
                    f'<text x="{left-8}" y="{sy(v)+4:.1f}" text-anchor="end" class="svg-tick">{v}%</text>')
    grid.append(f'<line x1="{left}" y1="{sy(0):.1f}" x2="{w-right}" y2="{sy(0):.1f}" '
                f'stroke="#898781" stroke-width="1.2"/>')
    dots = []
    for _, r in df.iterrows():
        dots.append(f'<circle cx="{sx(r.x):.1f}" cy="{sy(r.y):.1f}" r="4" fill="{r.color}" '
                    f'stroke="#fcfcfb" stroke-width="2" opacity="0.9">'
                    f'<title>{r.date} · {r.code} · 广度 {r.x:.0f}% · 真实净流入 {r.y:+.1f}%</title></circle>')
    corr = {d: key[key.date == d]["corr_breadth_flow"].iloc[0] for d, _ in dates}
    labels = "".join(
        f'<text x="{left+10}" y="{top+18+i*16}" class="svg-lab">'
        f'<tspan fill="{color}">●</tspan> {d}  r = {corr[d]:+.2f}</text>'
        for i, (d, color) in enumerate(dates))
    return (f'<svg viewBox="0 0 {w} {h}" class="chart" role="img" '
            f'aria-label="本地广度与真实 ETF 净流入的散点图">{"".join(grid)}{"".join(dots)}{labels}</svg>'), df


# ---------------------------------------------------------------- 热力图

def heatmap_html() -> str:
    codes = ["sh.515220", "sh.512800", "sz.159611", "sh.512480",
             "sh.515880", "sh.512660", "sh.515790", "sh.515030", "sz.159869"]
    names = {"sh.515220": "煤炭", "sh.512800": "银行", "sz.159611": "电力",
             "sh.512480": "半导体", "sh.515880": "通信", "sh.512660": "军工",
             "sh.515790": "光伏", "sh.515030": "新能源车", "sz.159869": "游戏"}
    months = [f"2026-{m:02d}" for m in range(1, 11)]
    m = monthly.set_index("code")
    head = "".join(f"<div class='hm-m'>{int(x[-2:])}月</div>" for x in months)
    body = []
    for code in codes:
        cells = []
        for month in months:
            v = m.loc[code, month] * 100
            # 红涨蓝跌，中性灰；深色单元格用白字
            if v >= 0:
                alpha = min(0.92, 0.12 + abs(v) / 45)
                bg = f"rgba(227,73,72,{alpha:.2f})"
            else:
                alpha = min(0.92, 0.12 + abs(v) / 45)
                bg = f"rgba(42,120,214,{alpha:.2f})"
            fg = "#ffffff" if abs(v) > 18 else "#0b0b0b"
            txt = f"{v:+.0f}"
            if txt in ("+0", "-0"):
                txt = "0"
            cells.append(f"<div class='hm-c' style='background:{bg};color:{fg}' "
                         f"title='{names[code]} {month}：{v:+.1f}%'>{txt}</div>")
        body.append(f"<div class='hm-name'>{names[code]}</div>{''.join(cells)}")
    return (f"<div class='heat' style='grid-template-columns: 74px repeat(10, 1fr)'>"
            f"<div></div>{head}{''.join(body)}</div>")


# ---------------------------------------------------------------- 组装

CSS = """
:root{
  --page:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e;
  --muted:#898781; --grid:#e1e0d9; --border:rgba(11,11,11,.10);
  --blue:#2a78d6; --orange:#eb6834; --aqua:#1baf7a; --red:#e34948;
  --blue-wash:rgba(42,120,214,.10); --orange-wash:rgba(235,104,52,.10);
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--page);color:var(--ink);
  font-family:"PingFang SC","Microsoft YaHei","Noto Sans CJK SC",system-ui,-apple-system,"Segoe UI",sans-serif;
  font-size:15px;line-height:1.72;-webkit-font-smoothing:antialiased}
a{color:var(--blue);text-decoration:none}
a:hover{text-decoration:underline}
.wrap{max-width:1080px;margin:0 auto;padding:0 24px}
header.hero{padding:56px 0 26px;background:linear-gradient(180deg,#f4f7fb 0%,var(--page) 100%);
  border-bottom:1px solid var(--border)}
.eyebrow{font-size:12px;letter-spacing:.14em;color:var(--muted);text-transform:uppercase}
h1{font-size:38px;line-height:1.24;margin:12px 0 10px;font-weight:700;letter-spacing:-.01em}
.lede{font-size:17px;color:var(--ink2);max-width:760px;margin:0 0 26px}
.hero-grid{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:36px;align-items:end}
.hero-figure{background:var(--surface);border:1px solid var(--border);border-radius:14px;
  padding:20px 22px;box-shadow:0 1px 0 rgba(11,11,11,.03)}
.hero-label{font-size:12px;color:var(--muted);letter-spacing:.06em}
.hero-value{font-size:58px;font-weight:700;line-height:1.05;margin:2px 0 4px}
.hero-value span{font-size:28px;font-weight:600;color:var(--ink2)}
.hero-delta{font-size:13px;color:var(--ink2)}
nav.toc{display:flex;flex-wrap:wrap;gap:8px 18px;padding:20px 0 2px;font-size:13px;color:var(--ink2)}
nav.toc a{color:var(--ink2)}
nav.toc a:hover{color:var(--blue)}
main{padding:34px 0 60px}
section{margin:0 0 54px;scroll-margin-top:20px}
h2{font-size:24px;margin:0 0 6px;letter-spacing:-.01em}
.sub{color:var(--ink2);font-size:14px;margin:0 0 20px}
h3{font-size:17px;margin:0 0 8px}
p{margin:0 0 12px}
.card{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:20px 22px}
.grid2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
.grid3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}
.grid4{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}
.kpi .v{font-size:30px;font-weight:700;line-height:1.15}
.kpi .l{font-size:12px;color:var(--muted);letter-spacing:.04em}
.kpi .d{font-size:12px;color:var(--ink2);margin-top:2px}
.chain{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;align-items:stretch}
.step{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:14px 14px 12px;position:relative}
.step:not(:last-child):after{content:"";position:absolute;right:-9px;top:50%;width:8px;height:1px;background:var(--muted)}
.step .n{font-size:11px;color:var(--muted);letter-spacing:.08em}
.step b{display:block;font-size:14px;margin:3px 0 4px}
.step span{font-size:12.5px;color:var(--ink2)}
.formula-card{display:grid;grid-template-columns:178px minmax(0,1fr);gap:18px;align-items:start;
  background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:18px 20px;margin:0 0 14px}
.formula-card .fig{background:var(--page);border-radius:10px;padding:6px}
.formula-card h3{margin:0 0 4px}
.formula-card .plain{color:var(--ink2);font-size:14px;margin:0 0 8px}
.formula-card code{display:inline-block;background:#eef3fa;color:#184f95;border-radius:6px;
  padding:2px 7px;font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:12.5px}
.formula-card .note{font-size:12.5px;color:var(--muted);margin-top:6px}
.chart{width:100%;height:auto;display:block}
.svg-tick{font-size:10px;fill:var(--muted);font-family:inherit}
.svg-lab{font-size:11px;fill:var(--ink2);font-family:inherit}
.svg-val{font-size:11px;fill:var(--ink);font-family:inherit;font-weight:600}
.hbar-row{display:grid;grid-template-columns:110px minmax(0,1fr) 64px 150px;gap:10px;align-items:center;
  padding:7px 0;border-bottom:1px solid var(--grid)}
.hbar-row:last-child{border-bottom:none}
.hbar-label{font-size:13px;color:var(--ink2)}
.hbar-track{height:12px;background:#eef0f2;border-radius:999px;overflow:hidden}
.hbar-fill{height:12px;border-radius:999px}
.hbar-value{font-size:13px;font-weight:600;text-align:right;font-variant-numeric:tabular-nums}
.hbar-note{font-size:11.5px;color:var(--muted)}
.small-multiples{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.sm-head{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:6px}
.sm-head b{font-size:15px}
.sm-head span{font-size:12px;color:var(--muted)}
.sm-scale{font-size:11px;color:var(--muted);margin-top:8px}
.heat{display:grid;gap:2px;font-size:11px}
.hm-m{color:var(--muted);text-align:center;padding:2px 0}
.hm-name{color:var(--ink2);padding:6px 4px;font-size:12px;display:flex;align-items:center}
.hm-c{display:flex;align-items:center;justify-content:center;height:30px;border-radius:3px;
  font-variant-numeric:tabular-nums}
.legend{display:flex;align-items:center;gap:8px;font-size:11.5px;color:var(--muted);margin-top:8px}
.legend .sw{width:22px;height:10px;border-radius:2px}
.timeline{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:0;margin-top:8px}
.tl-item{position:relative;padding:16px 10px 0;border-top:1px solid var(--grid)}
.tl-item:before{content:"";position:absolute;top:-4px;left:0;width:7px;height:7px;border-radius:50%;
  background:var(--blue)}
.tl-item b{display:block;font-size:13px;margin-bottom:2px}
.tl-item span{font-size:12px;color:var(--ink2)}
.take{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px}
.take .card{padding:16px}
.take .n{font-size:11px;color:var(--muted);letter-spacing:.1em}
.take b{display:block;font-size:14px;margin:4px 0 6px}
.take p{font-size:12.5px;color:var(--ink2);margin:0}
.callout{border-left:3px solid var(--blue);background:var(--blue-wash);border-radius:0 10px 10px 0;
  padding:12px 16px;color:var(--ink2);font-size:13.5px;margin:14px 0}
.callout.warn{border-left-color:var(--orange);background:var(--orange-wash)}
.table{width:100%;border-collapse:collapse;font-size:12.5px}
.table th{text-align:left;color:var(--muted);font-weight:500;padding:6px 8px;border-bottom:1px solid var(--grid)}
.table td{padding:6px 8px;border-bottom:1px solid var(--grid);font-variant-numeric:tabular-nums}
.table td:first-child,.table th:first-child{text-align:left}
details{margin-top:10px}
summary{cursor:pointer;color:var(--blue);font-size:12.5px}
footer{border-top:1px solid var(--border);padding:20px 0 40px;color:var(--muted);font-size:12px}
@media (max-width:860px){
  h1{font-size:30px}.hero-grid{grid-template-columns:1fr}.grid4{grid-template-columns:repeat(2,1fr)}
  .grid3,.grid2,.small-multiples{grid-template-columns:1fr}.chain{grid-template-columns:1fr}
  .step:not(:last-child):after{display:none}.take{grid-template-columns:1fr}
  .formula-card{grid-template-columns:1fr}.timeline{grid-template-columns:1fr}
  .tl-item{border-top:none;border-left:1px solid var(--grid);padding:0 0 14px 16px}
  .tl-item:before{left:-4px;top:4px}
  .hbar-row{grid-template-columns:84px minmax(0,1fr) 54px}
  .hbar-note{display:none}
}
@media print{
  body{background:#fff;font-size:10.5pt}
  header.hero{background:#fff}
  nav.toc{display:none}
  h2,h3{break-after:avoid}
  p{orphans:2;widows:2}
  section{break-inside:auto;margin-bottom:22px}
  .card,.formula-card,.step{box-shadow:none;break-inside:avoid}
}
"""


def build_html() -> str:
    per = p
    hero_spark = sparkline(nav["net_composite"])
    flowmap_png = b64(FIG_DIR / "fig2_flowmap.png")

    # 小多图
    local = [("基础因子", per["gross_base"]["cagr"] * 100),
             ("综合因子", per["gross_composite"]["cagr"] * 100),
             ("等权基准", per["benchmark_gross"]["cagr"] * 100)]
    report = [("基础因子", ref["base"]["cagr"] * 100), ("综合因子", ref["composite"]["cagr"] * 100),
              ("等权基准", ref["benchmark"]["cagr"] * 100)]
    local_html = "".join(hbar(n, v, 10, "#2a78d6",
                              note="本地 ETF 复现") for n, v in local)
    report_html = "".join(hbar(n, v, 25, "#898781",
                               note=f"研报原文（{ref['n_industries']} 个行业指数）") for n, v in report)

    # 容量表
    cap_rows = "".join(
        f"<tr><td>{int(r['资金规模(万元)']):,}</td><td>{r['年化收益']*100:.2f}%</td>"
        f"<td>{r['最大回撤']*100:.1f}%</td><td>{r['年化成本拖累']*100:.2f}%</td>"
        f"<td>{r['最大参与率']*100:.1f}%</td><td>{int(r['受限天数'])}</td></tr>"
        for _, r in cap.iterrows())

    # 关键日期表
    key_rows = "".join(
        f"<tr><td>{r['date']}</td><td>{r['semi_breadth']*100:.0f}%</td>"
        f"<td>{r['semi_flow']*100:+.1f}%</td><td>{r['telecom_breadth']*100:.0f}%</td>"
        f"<td>{r['telecom_flow']*100:+.1f}%</td><td>{r['corr_breadth_flow']:+.2f}</td></tr>"
        for _, r in key.iterrows())

    # 散点 + 表格
    scatter, sdf = scatter_svg()
    sdf = sdf.merge(monthly[["code", "name"]], on="code", how="left")
    scatter_rows = "".join(
        f"<tr><td>{r.date}</td><td>{r['name']}</td><td>{r.x:.0f}%</td><td>{r.y:+.1f}%</td></tr>"
        for _, r in sdf.sort_values(["date", "x"], ascending=[True, False]).iterrows())

    # 瀑布
    wf = waterfall_svg()

    # 2026 热力图的完整数据表（9 个行业 × 10 个月）
    hm_codes = ["sh.515220", "sh.512800", "sz.159611", "sh.512480",
                "sh.515880", "sh.512660", "sh.515790", "sh.515030", "sz.159869"]
    hm_names = {"sh.515220": "煤炭", "sh.512800": "银行", "sz.159611": "电力",
                "sh.512480": "半导体", "sh.515880": "通信", "sh.512660": "军工",
                "sh.515790": "光伏", "sh.515030": "新能源车", "sz.159869": "游戏"}
    m_idx = monthly.set_index("code")
    hm_head = "<th>行业</th>" + "".join(f"<th>{m}月</th>" for m in range(1, 11))
    hm_rows = "".join(
        f"<tr><td>{hm_names[c]}</td>"
        + "".join(f"<td>{m_idx.loc[c, f'2026-{m:02d}']*100:+.1f}%</td>" for m in range(1, 11))
        + "</tr>" for c in hm_codes)

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>一页看懂：行业资金流向图与 5000 万模拟（{PROJECT_ID}）</title>
<style>{CSS}</style>
</head>
<body>

<header class="hero">
  <div class="wrap">
    <div class="eyebrow">{PROJECT_ID} · 研读心得 · {meta["snapshot_date"]}</div>
    <div class="hero-grid">
      <div>
        <h1>一页看懂：<br>行业资金流向图，到底在做什么？</h1>
        <p class="lede">先把华泰研报的公式翻译成大白话，再用 {meta['n_etfs']} 只行业 ETF、5000 万元，
        看看它能不能真的落地。结论先说：<b>方法的方向对了，但绝对收益没有复现；
        而在 5000 万这个量级，钱主要是被成本和容量吃掉的。</b></p>
      </div>
      <div class="hero-figure">
        <div class="hero-label">5000 万元模拟 · 净年化</div>
        <div class="hero-value">{p['net_composite_50m']['cagr']*100:.1f}<span>%</span></div>
        <div class="hero-delta">理论组合 {pct(p['gross_composite']['cagr'])} → 扣容量与成本后 {pct(p['net_composite_50m']['cagr'])}</div>
        {hero_spark}
        <div class="hero-label" style="margin-top:2px">净值走势（{meta['start'][:4]}–{meta['end'][:4]}）</div>
      </div>
    </div>
    <nav class="toc">
      <a href="#story">01 研报在做什么</a>
      <a href="#formulas">02 公式翻译</a>
      <a href="#results">03 成绩单</a>
      <a href="#money">04 钱去哪了</a>
      <a href="#capacity">05 容量</a>
      <a href="#y2026">06 2026 复盘</a>
      <a href="#takeaways">07 我学到了什么</a>
    </nav>
  </div>
</header>

<main class="wrap">

<section id="story">
  <h2>01　研报在做什么：一条五步链条</h2>
  <p class="sub">不用先看公式，先看它想把什么事情变成可计算的东西。</p>
  <div class="chain">
    <div class="step"><div class="n">STEP 1</div><b>主动买卖</b><span>谁在主动买、谁在主动卖。研报认为“真金白银的押注”比口头观点更可信。</span></div>
    <div class="step"><div class="n">STEP 2</div><b>行业净买入</b><span>把主动买、主动卖相减，再除以成交额，得到每个行业的“资金流强度”。</span></div>
    <div class="step"><div class="n">STEP 3</div><b>资金流向图</b><span>把行业间的钱想成河网：用“曼宁公式”把看不见的行业间流量，变成可求解的方程。</span></div>
    <div class="step"><div class="n">STEP 4</div><b>四个微观因子</b><span>从流向图里提炼：最大净流入、流入广度、流出之和、场外净流入。</span></div>
    <div class="step"><div class="n">STEP 5</div><b>五因子合成</b><span>五个“弱因子”各投一票，合成“资金流向综合因子”，周度买前 5 个行业。</span></div>
  </div>
  <div class="callout">一句话：<b>研报不是想预测“哪只股票涨”，而是想回答“钱在行业之间怎么流”。</b>
  流向图是它的“显微镜”，因子是它的“投票器”。</div>
</section>

<section id="formulas">
  <h2>02　公式翻译：把符号换成生活里的东西</h2>
  <p class="sub">下面每个公式都配一句大白话。公式本身不重要，重要的是它在量什么。</p>

  <div class="formula-card">
    <div class="fig">
      <svg viewBox="0 0 160 110" width="160" height="110" role="img" aria-label="买卖占比示意">
        <text x="4" y="16" class="svg-lab">主动买</text>
        <rect x="4" y="24" width="112" height="10" rx="3" fill="#e34948" opacity=".85"/>
        <text x="4" y="52" class="svg-lab">主动卖</text>
        <rect x="4" y="60" width="80" height="10" rx="3" fill="#2a78d6" opacity=".85"/>
        <text x="4" y="88" class="svg-lab">差值 ÷ 成交额占比</text>
        <text x="4" y="104" class="svg-val">= 资金流强度</text>
      </svg>
    </div>
    <div>
      <h3>① 主动净买入因子：Q / V</h3>
      <p class="plain">把每个行业想成一个班级：<b>Q</b> 是“主动找它搭话的人占比”减去“主动离开的人占比”；
      <b>V</b> 是它的“发言量占比”。Q/V 就是：<b>在同样发言量下，谁被更主动地追捧。</b></p>
      <code>Q_i = 主动买占比 − 主动卖占比；因子 = Q_i / V_i</code>
      <div class="note">研报还发现数据商的主动买卖金额长期为负，所以用“占比之差”而不是绝对金额来消除误差。</div>
    </div>
  </div>

  <div class="formula-card">
    <div class="fig">
      <svg viewBox="0 0 160 110" width="160" height="110" role="img" aria-label="收盘价位置示意">
        <rect x="80" y="10" width="10" height="92" rx="3" fill="#cde2fb"/>
        <line x1="85" y1="10" x2="85" y2="102" stroke="#898781" stroke-width="1"/>
        <text x="98" y="16" class="svg-lab">最高 H</text>
        <text x="98" y="106" class="svg-lab">最低 L</text>
        <circle cx="85" cy="28" r="5" fill="#eb6834" stroke="#fcfcfb" stroke-width="2"/>
        <text x="98" y="32" class="svg-lab">收盘 C</text>
        <text x="4" y="54" class="svg-lab">收得越高</text>
        <text x="4" y="68" class="svg-lab">买盘越强</text>
      </svg>
    </div>
    <div>
      <h3>② 没有逐笔数据时，用 MFM 代理</h3>
      <p class="plain">看收盘价站在当天最高价和最低价的什么位置。<b>收在最高附近，说明买方把价格顶住了；
      收在最低附近，说明卖方砸下来了。</b>这就是我们能拿到的“主动净买入强度”的替身。</p>
      <code>MFM = ((C − L) − (H − C)) / (H − L)</code>
      <div class="note">公开数据没有 Wind 的主动买卖金额，所以长样本只能用这个量价代理；报告里已明确说明，不冒充 Wind 口径。</div>
    </div>
  </div>

  <div class="formula-card">
    <div class="fig">
      <svg viewBox="0 0 160 110" width="160" height="110" role="img" aria-label="河网示意">
        <path d="M6 78 C 36 78, 44 36, 80 36 S 124 58, 154 58" fill="none"
              stroke="#2a78d6" stroke-width="8" stroke-linecap="round" opacity=".30"/>
        <path d="M6 78 C 36 78, 44 36, 80 36 S 124 58, 154 58" fill="none"
              stroke="#2a78d6" stroke-width="2" stroke-linecap="round"/>
        <line x1="26" y1="50" x2="26" y2="88" stroke="#898781" stroke-width="1"/>
        <text x="30" y="88" class="svg-lab">水深</text>
        <text x="82" y="22" class="svg-lab">坡度</text>
        <text x="116" y="46" class="svg-lab">河宽</text>
      </svg>
    </div>
    <div>
      <h3>③ 曼宁公式：把行业间的钱想成河水</h3>
      <p class="plain"><b>河道越宽（市值）、水越深（成交额）、坡度越陡（涨跌幅），水流越大</b>，再乘一个“摩擦系数”。
      研报借用这个物理公式，把“行业间的资金流”和“行业涨跌幅”绑在一起。</p>
      <code>Q = A × R^(2/3) × H^(1/2) → H_i = e^α × S^(…) × V^(…) × Q|Q|</code>
      <div class="note">这不是说市场真的像河流；它是给“看不见的流量”找一个可计算的形状。</div>
    </div>
  </div>

  <div class="formula-card">
    <div class="fig">
      <svg viewBox="0 0 160 110" width="160" height="110" role="img" aria-label="水库与水管示意">
        <circle cx="26" cy="58" r="14" fill="#eef3fa" stroke="#2a78d6" stroke-width="1.5"/>
        <text x="26" y="62" text-anchor="middle" class="svg-lab">A</text>
        <circle cx="80" cy="58" r="14" fill="#eef3fa" stroke="#2a78d6" stroke-width="1.5"/>
        <text x="80" y="62" text-anchor="middle" class="svg-lab">B</text>
        <circle cx="134" cy="58" r="14" fill="#fdf0eb" stroke="#eb6834" stroke-width="1.5"/>
        <text x="134" y="62" text-anchor="middle" class="svg-lab">场外</text>
        <line x1="40" y1="58" x2="66" y2="58" stroke="#2a78d6" stroke-width="2"/>
        <line x1="94" y1="58" x2="120" y2="58" stroke="#eb6834" stroke-width="2"/>
        <text x="4" y="16" class="svg-lab">流入 − 流出 = 净流入</text>
        <text x="4" y="102" class="svg-lab">水管多、水位计少 → 解不唯一</text>
      </svg>
    </div>
    <div>
      <h3>④ 质量守恒 + 欠定：{ps['n_equations']} 个水位计，猜 {ps['n_edges']} 条水管</h3>
      <p class="plain">每个行业是一个水库：<b>流进来的减去流出去的 = 净流入</b>；场外也是一个水库。
      问题是：我们只有 {ps['n_equations']} 个“水位计”（每个行业的净流入和涨跌幅），却要猜 {ps['n_edges']} 条“水管”的流量。
      满足守恒的答案有无数个。</p>
      <p class="plain">研报的做法：先选<b>“总流量最小”</b>的那个解（最小二范数），再用它去拟合涨跌幅；
      拟合不好就调参数。<b>所以“拟合误差小”不等于“模型是真的”</b>——未知量比方程多得多。</p>
      <code>q = q₀ + Φγ；min Σ ε²</code>
      <div class="note">这条是我们最想提醒的：流向图很好看，但它是“一个可能的解”，不是“唯一真相”。</div>
    </div>
  </div>

  <div class="formula-card">
    <div class="fig">
      <svg viewBox="0 0 160 110" width="160" height="110" role="img" aria-label="五因子投票示意">
        <circle cx="20" cy="14" r="6" fill="#2a78d6"/><circle cx="20" cy="34" r="6" fill="#2a78d6"/>
        <circle cx="20" cy="54" r="6" fill="#2a78d6"/><circle cx="20" cy="74" r="6" fill="#2a78d6"/>
        <circle cx="20" cy="94" r="6" fill="#2a78d6" opacity=".5"/>
        <line x1="26" y1="14" x2="64" y2="54" stroke="#c3c2b7" stroke-width="1"/>
        <line x1="26" y1="34" x2="64" y2="54" stroke="#c3c2b7" stroke-width="1"/>
        <line x1="26" y1="54" x2="64" y2="54" stroke="#c3c2b7" stroke-width="1"/>
        <line x1="26" y1="74" x2="64" y2="54" stroke="#c3c2b7" stroke-width="1"/>
        <line x1="26" y1="94" x2="64" y2="54" stroke="#c3c2b7" stroke-width="1" opacity=".5"/>
        <rect x="64" y="38" width="88" height="32" rx="8" fill="#eef3fa" stroke="#2a78d6" stroke-width="1.5"/>
        <text x="108" y="58" text-anchor="middle" class="svg-lab">综合因子</text>
        <text x="4" y="108" class="svg-lab">5 个弱评委</text>
      </svg>
    </div>
    <div>
      <h3>⑤ 四个微观因子 + 五因子投票</h3>
      <div class="grid2" style="gap:8px;margin:6px 0 8px">
        <div><b>最大净流入</b><div class="note">最粗的一根进水管——谁最被看好。</div></div>
        <div><b>净流入为正比例</b><div class="note">多少个邻居愿意给你送水——抱团广度。</div></div>
        <div><b>净流出之和</b><div class="note">同时有多少水在往外漏——分歧程度。</div></div>
        <div><b>场外净流入</b><div class="note">有没有新钱从市场外面进来。</div></div>
      </div>
      <p class="plain">五个评委各投一票，单个都不准，合起来更稳。研报说，改进来自<b>“低相关的弱因子”</b>，
      而不是找到一个更强的主因子。</p>
      <code>综合 = mean(z(基础), z(最大), z(广度), z(流出), z(场外))</code>
    </div>
  </div>
</section>

<section id="results">
  <h2>03　成绩单：方向对了，绝对收益没有</h2>
  <p class="sub">同一套方法，左边是我们用 {meta['n_etfs']} 只行业 ETF 的复现，右边是研报原文。两边口径不同，不能直接比高低，但能看出差距。</p>
  <div class="small-multiples">
    <div class="card">
      <div class="sm-head"><b>本地复现</b><span>{meta['n_etfs']} 只行业 ETF · {meta['start'][:4]}–{meta['end'][:4]}</span></div>
      {local_html}
      <div class="sm-scale">横轴 0–10%</div>
    </div>
    <div class="card">
      <div class="sm-head"><b>研报原文</b><span>{ref['n_industries']} 个中信行业指数 · {ref['period'][:4]}–{ref['period'][-10:-6]}</span></div>
      {report_html}
      <div class="sm-scale">横轴 0–25%</div>
    </div>
  </div>
  <div class="callout">为什么差这么多？三处口径不同：<b>{ref['n_industries']} 个行业指数 vs {meta['n_etfs']} 只 ETF、{ref['period'][:4]} 年起 vs {meta['start'][:4]} 年起、
  Wind 主动买卖 vs 量价代理。</b>所以这不是“研报错了”，而是“换了一套材料，做不出同样的菜”。</div>
  <div class="grid3" style="margin-top:14px">
    <div class="card kpi"><div class="l">基础因子</div><div class="v">{pct(per['gross_base']['cagr'])}</div><div class="d">最大回撤 {pct(per['gross_base']['mdd'])}</div></div>
    <div class="card kpi"><div class="l">综合因子</div><div class="v">{pct(per['gross_composite']['cagr'])}</div><div class="d">最大回撤 {pct(per['gross_composite']['mdd'])}</div></div>
    <div class="card kpi"><div class="l">等权基准</div><div class="v">{pct(per['benchmark_gross']['cagr'])}</div><div class="d">最大回撤 {pct(per['benchmark_gross']['mdd'])}</div></div>
  </div>
  <div class="callout"><b>但改进的方向复现了：</b>综合因子比基础因子多赚
  {pp(per['gross_composite']['cagr']-per['gross_base']['cagr'])}，最大回撤从
  {pct(per['gross_base']['mdd'])} 收窄到 {pct(per['gross_composite']['mdd'])}（改善
  {abs(per['gross_composite']['mdd']-per['gross_base']['mdd'])*100:.1f} pct）。
  排序能力也同步改善：Rank IC 从 {ic['base']['mean_ic']:.3f} 升到 {ic['composite']['mean_ic']:.3f}
  （t = {ic['composite']['ic_t']:.2f}）。但“净流出之和”在 ETF 上方向与研报相反
  （IC {ic['out_sum']['mean_ic']:.3f}），<b>合成前要先逐个检验符号。</b></div>
</section>

<section id="money">
  <h2>04　钱去哪了：{pct(p['gross_composite']['cagr'])} 怎么变成 {pct(p['net_composite_50m']['cagr'])}</h2>
  <p class="sub">5000 万元真金白银，按周调仓、100 份整数手、参与率不超过 ADV 的 5%。</p>
  <div class="card">
    {wf}
    <div class="callout" style="margin-bottom:0">成本不是“手续费”三个字这么简单：佣金 1bp + 半价差 2bp +
    冲击 10bp×√(参与率/5%)。理论 {pct(p['gross_composite']['cagr'])} → 只加 5% ADV 约束 {pct(p['cap_only_composite_50m']['cagr'])} → 再扣成本 {pct(p['net_composite_50m']['cagr'])}。
    <b>{abs(p['net_composite_50m']['cagr']-p['gross_composite']['cagr'])*100:.1f} 个百分点的差距里，
    “想买买不到、想卖卖不掉”占 {abs(p['cap_only_composite_50m']['cagr']-p['gross_composite']['cagr'])*100:.1f}，
    交易成本占 {abs(p['net_composite_50m']['cagr']-p['cap_only_composite_50m']['cagr'])*100:.1f}。</b></div>
  </div>
  <div class="grid3" style="margin-top:14px">
    <div class="card kpi"><div class="l">5000 万期末</div><div class="v">{per['net_composite_50m']['final_value']/1e4:,.0f}<span style="font-size:15px"> 万</span></div><div class="d">净收益 {per['net_composite_50m']['net_profit']/1e4:+,.0f} 万</div></div>
    <div class="card kpi"><div class="l">年化成本拖累</div><div class="v">{pct(per['net_composite_50m']['cost_drag_annual'])}</div><div class="d">每年被交易吃掉</div></div>
    <div class="card kpi"><div class="l">最大回撤</div><div class="v">{pct(per['net_composite_50m']['mdd'])}</div><div class="d">{per['net_composite_50m']['binding_days']} 天触及 5% ADV 上限</div></div>
  </div>
</section>

<section id="capacity">
  <h2>05　容量：不是“越大越差”，而是策略被约束改变了</h2>
  <p class="sub">5000 万不是终点。把资金从 1000 万加到 5 亿，看净年化怎么变。</p>
  <div class="card">
    {capacity_svg()}
    <div class="legend"><span><b style="color:#2a78d6">●</b> 净年化收益</span>
      <span><b style="color:#eb6834">●</b> 5000 万</span>
      <span><b style="color:#898781">—</b> 等权基准</span></div>
    <details><summary>看数据表（含参与率与受限天数）</summary>
      <table class="table"><thead><tr><th>资金（万元）</th><th>净年化</th><th>最大回撤</th>
      <th>成本拖累</th><th>最大参与率</th><th>受限天数</th></tr></thead><tbody>{cap_rows}</tbody></table>
    </details>
  </div>
  <div class="callout warn"><b>怎么读这张图：</b>1000 万 → 5000 万，收益从
  {pct(cap.iloc[0]['年化收益'])} 降到 {pct(cap.iloc[2]['年化收益'])}，因为成本与参与率上来了；
  但 1 亿以上又回升，不是因为“大资金更强”，而是因为调仓被截断、换手从
  {cap.iloc[2]['年化换手']:.1f} 降到 {cap.iloc[5]['年化换手']:.1f}，组合被动变成长持有。
  <b>5000 万时净超额已经是 {pp(per['net_composite_50m']['excess_vs_benchmark'])}，
  再多钱，策略就慢慢不是原来那个策略了。</b></div>
</section>

<section id="y2026">
  <h2>06　2026 复盘：因子在共识顶点满仓</h2>
  <p class="sub">这一年 AI 硬件先加速、再崩塌。6 月 30 日综合因子前 5 名：{'、'.join(x['name'].replace('ETF', '') for x in facts['top5_composite_0630'])}。</p>

  <div class="card">
    <div class="sm-head"><b>2026 年行业 ETF 月度收益</b><span>红=涨，蓝=跌；数字为 %</span></div>
    {heatmap_html()}
    <div class="legend"><span>−40%</span><span class="sw" style="background:#2a78d6"></span>
      <span class="sw" style="background:#9ec5f4"></span><span class="sw" style="background:#f0efec"></span>
      <span class="sw" style="background:#f2b3b3"></span><span class="sw" style="background:#e34948"></span>
      <span>+40%</span></div>
    <details><summary>看数据表（9 个行业 × 10 个月）</summary>
      <div style="overflow-x:auto"><table class="table"><thead><tr>{hm_head}</tr></thead><tbody>{hm_rows}</tbody></table></div>
    </details>
  </div>

  <div class="timeline" style="margin-top:18px">
    <div class="tl-item"><b>6/24</b><span>研报说电子“缩圈”；本地半导体广度 {semi_b[0]}。</span></div>
    <div class="tl-item"><b>6/30</b><span>研报说“共识高度一致”；本地广度 {semi_b[1]}。因子满仓 AI 硬件。</span></div>
    <div class="tl-item"><b>7/6</b><span>研报说“抱团松动”；本地广度 {semi_b[2]}。</span></div>
    <div class="tl-item"><b>7 月</b><span>半导体 {pct(monthly.set_index('code').loc['sh.512480','2026-07'])}，通信 {pct(monthly.set_index('code').loc['sh.515880','2026-07'])}。</span></div>
    <div class="tl-item"><b>10 月</b><span>半导体再 {pct(monthly.set_index('code').loc['sh.512480','2026-10'])}，通信 {pct(monthly.set_index('code').loc['sh.515880','2026-10'])}。</span></div>
  </div>

  <div class="card" style="margin-top:16px">
    <div class="sm-head"><b>真实的行业资金流向图</b><span>2026-06-24 / 06-30 / 07-06</span></div>
    <a href="data:image/png;base64,{flowmap_png}" target="_blank">
      <img src="data:image/png;base64,{flowmap_png}" alt="行业资金流向图：三个示例日"
           style="width:100%;height:auto;border-radius:8px;display:block">
    </a>
    <div class="note" style="margin-top:6px">红=净流入，蓝=净流出；箭头越粗，流量越大。点图可放大。</div>
  </div>

  <div class="card" style="margin-top:18px">
    <div class="sm-head"><b>半导体的“抱团温度计”</b><span>净流入为正比例，5 日均</span></div>
    {breadth_svg()}
    <div class="callout" style="margin-bottom:0"><b>关键结论：</b>研报的“缩圈→共识→松动”在 ETF 上没有复现。
    本地广度是 {' / '.join(semi_b)}，与研报的 {ref['semi_breadth_path']} 方向不同。
    <b>所以“广度开关”这次没有通过检验，不能直接拿来用。</b></div>
  </div>

  <div class="card" style="margin-top:16px">
    <div class="sm-head"><b>广度 vs 真实 ETF 资金流</b><span>每个点 = 一只 ETF；横轴广度，纵轴真实净流入率</span></div>
    {scatter}
    <div class="callout" style="margin-bottom:0">三天的一致性都不高（r = {key.iloc[0]['corr_breadth_flow']:+.2f} /
    {key.iloc[1]['corr_breadth_flow']:+.2f} / {key.iloc[2]['corr_breadth_flow']:+.2f}）。
    最具体的反例：研报说 6/24 通信“净流入为正比例仅 {ref['telecom_breadth_0624']}”，但同日通信 ETF 的真实主力净流入是
    <b>{key.iloc[0]['telecom_flow']*100:+.1f}%</b>。一个说“相对分歧”，一个说“绝对流入”——
    <b>“资金流”三个字，先定义口径，再谈方向。</b></div>
    <details><summary>看数据表（{len(sdf)} 个点）</summary>
      <table class="table"><thead><tr><th>日期</th><th>ETF</th><th>广度</th><th>真实净流入率</th></tr></thead><tbody>{scatter_rows}</tbody></table>
    </details>
  </div>
</section>

<section id="takeaways">
  <h2>07　我学到了什么（以及不要误读什么）</h2>
  <div class="take">
    <div class="card"><div class="n">01</div><b>先体检，再建模</b><p>研报用“占比之差”消除数据商长期为负的系统性误差。误差是口径带来的，就在口径内解决。</p></div>
    <div class="card"><div class="n">02</div><b>把看不见的变成可估计的</b><p>河网/曼宁公式 + 质量守恒 + 欠定方程，是处理“看得见结果、看不见流量”的通用套路。</p></div>
    <div class="card"><div class="n">03</div><b>弱因子合成，先验符号</b><p>综合因子收益更高、回撤更小、IC 也更高；但其中“净流出之和”在 ETF 上方向相反，合成前要逐个检验。</p></div>
    <div class="card"><div class="n">04</div><b>口径决定结论</b><p>“行业间相对流向”和“单只 ETF 绝对流向”不是一回事。06-24 通信的 {ref['telecom_breadth_0624']} vs {key.iloc[0]['telecom_flow']*100:+.1f}% 是最具体的反例。</p></div>
    <div class="card"><div class="n">05</div><b>可视化是研究工具</b><p>流向图把“缩圈/共识/松动”变成可比较的图形。即使这次没给出可交易信号，它也帮我们看清了市场在讨论什么。</p></div>
  </div>

  <div class="grid2" style="margin-top:16px">
    <div class="card"><h3>不要误读</h3>
      <p><b>不是“研报错了”：</b>口径不同。{ref['n_industries']} 个行业指数、{ref['period'][:4]} 年起、Wind 主动买卖，和 {meta['n_etfs']} 只 ETF、{meta['start'][:4]} 年起、量价代理，本来就不该有一样的收益。</p>
      <p><b>不是“因子完全没用”：</b>综合因子确实把回撤从 {pct(per['gross_base']['mdd'])} 降到
      {pct(per['gross_composite']['mdd'])}，只是绝对收益不够。</p>
      <p><b>不是“5000 万一定亏”：</b>冲击假设 5/10/20bp 下，净年化在
      {pct(pd.DataFrame(res['cost_sensitivity'])['年化收益'].min())}–
      {pct(pd.DataFrame(res['cost_sensitivity'])['年化收益'].max())} 之间，取决于成本和执行。</p>
    </div>
    <div class="card"><h3>下一步</h3>
      <p><b>① 用 ETF 份额变化（申购赎回）</b>补充成交额口径：份额变化是真实资金进出，不受“主动买/卖”分类误差影响。</p>
      <p><b>② 先验证广度，再做开关：</b>本次在 ETF 上没有通过；下一步要在目标 universe 上检验符号与领先性。</p>
      <p><b>③ 给流向图加“置信带”：</b>未知量远多于方程，单点图会骗人；滚动求解 + 解稳定性区间更诚实。</p>
    </div>
  </div>

  <div class="callout" style="margin-top:16px"><b>一句话总结：</b>研报最值钱的不是“21.97%”这个数字，
  而是<b>“把行业间的钱变成可观察的图”</b>这件事；我们复现了图和改进方向，但没有复现收益，
  也验证出“广度拐点”在 ETF 口径下不成立。<b>知道什么不能用，和知道什么能用，一样重要。</b></div>
</section>

<section id="repro">
  <h2>08　复现与原文</h2>
  <div class="card">
    <p>报告 PDF：<a href="{REPO_URL}/blob/{GITHUB_BRANCH}/{PROJECT_ID}/output/{PROJECT_ID}_report.pdf">{PROJECT_ID}_report.pdf</a><br>
    Notebook：<a href="{NBVIEWER_URL}">nbviewer</a> ·
    <a href="{GITHUB_NB_URL}">GitHub 原生视图</a><br>
    代码与数据：<a href="{REPO_URL}/tree/{GITHUB_BRANCH}/{PROJECT_ID}">{REPO_URL.removeprefix("https://")}/{PROJECT_ID}</a></p>
    <p class="note">本地复现：<code>python run_all.py</code>；数据快照抓取日期 {meta["snapshot_date"]}。
    本页所有数字来自 <code>output/results.json</code>，由 <code>src/make_explainer.py</code> 生成。</p>
  </div>
</section>

</main>
<footer><div class="wrap">{PROJECT_ID} · 行业资金流向图 ETF 复现与 5000 万模拟 · {meta["snapshot_date"]}</div></footer>
</body></html>"""
    return html


def build() -> Path:
    """写出 HTML 并打印为 PDF（复用报告的渲染器）。"""
    from .make_report import render_pdf

    html_path = OUTPUT / f"{PROJECT_ID}_explainer.html"
    html_path.write_text(build_html(), encoding="utf-8")
    pdf_path = html_path.with_suffix(".pdf")
    render_pdf(html_path, pdf_path)
    print(f"[explainer] {html_path.name}  {pdf_path.name}")
    return pdf_path


if __name__ == "__main__":
    build()
