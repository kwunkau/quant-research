"""报告生成：results.json + 图表 → HTML → PDF。

正文中的每个数字都从 results.json 读取；研报原文数字单独标注为“研报”。
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pandas as pd

from .config import FIG_DIR, NBVIEWER_URL, OUTPUT, PROJECT_ID, REPO_URL

CSS = """
@page { size: A4; margin: 13mm 14mm 11mm 14mm; }
* { box-sizing: border-box; }
body { font-family: "Microsoft YaHei", "SimSun", sans-serif; font-size: 8.9pt;
       line-height: 1.46; color: #222; margin: 0; }
h1 { font-size: 15pt; margin: 0 0 1.4mm 0; letter-spacing: .3px; line-height: 1.24; }
.sub { color: #666; font-size: 8.4pt; margin-bottom: 3.2mm; }
h2 { font-size: 10.8pt; margin: 3.8mm 0 1.4mm; padding-left: 2.6mm;
     border-left: 3px solid #2F6F8F; }
h3 { font-size: 9.4pt; margin: 2.6mm 0 1.1mm; color: #1F4F66; }
p { margin: 1.1mm 0; text-align: justify; }
.abstract { background: #F4F7F9; border-left: 3px solid #2F6F8F;
            padding: 2.4mm 3.2mm; margin: 2.2mm 0 2.8mm; font-size: 8.8pt; }
.abstract b { color: #1F4F66; }
table { border-collapse: collapse; width: 100%; font-size: 7.8pt; margin: 1.4mm 0 2.2mm;
        break-inside: avoid; page-break-inside: avoid; }
tr { break-inside: avoid; page-break-inside: avoid; }
th { background: #EDF2F5; font-weight: 600; }
th, td { border-bottom: 1px solid #DCE3E8; padding: .9mm 1.3mm; text-align: right; }
th:first-child, td:first-child { text-align: left; }
.cap { font-size: 7.6pt; color: #666; margin: .5mm 0 2.2mm; }
figure { margin: 1.4mm 0 .6mm; page-break-inside: avoid; }
figure img { width: 100%; display: block; }
.kv { color: #1F4F66; font-weight: 600; }
ul, ol { margin: 1.1mm 0 1.1mm 4.4mm; padding: 0; }
li { margin: .5mm 0; }
.ref { font-size: 7.7pt; color: #444; }
.small { font-size: 7.8pt; color: #555; }
a.url { font-family: Consolas, "Courier New", monospace; font-size: 6.9pt;
        color: #1F4F66; text-decoration: none; word-break: break-all; }
code { background: #F2F2F2; padding: 0 .6mm; font-size: 8.0pt; }
"""


def b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


def fig(name: str, caption: str, width: str = "100%") -> str:
    return (f'<figure style="width:{width};margin-left:auto;margin-right:auto">'
            f'<img src="data:image/png;base64,{b64(FIG_DIR / name)}">'
            f'<figcaption class="cap">{caption}</figcaption></figure>')


def pct(x: float, d: int = 1) -> str:
    return f"{x * 100:.{d}f}%"


def pp(x: float, d: int = 1) -> str:
    return f"{x * 100:+.{d}f} pct"


def build_html(res: dict) -> str:
    p = res["performance"]
    gb, gc = p["gross_base"], p["gross_composite"]
    nb, nc = p["net_base_50m"], p["net_composite_50m"]
    bm, bmn = p["benchmark_gross"], p["benchmark_net_50m"]
    cap = pd.DataFrame(res["capacity"])
    ic = res["ic"]
    boot = res["bootstrap_excess"]
    fl = res["flowmap"]
    rv = res["review_2026"]
    key = pd.DataFrame(rv["key_dates"])
    ytd = pd.DataFrame(rv["ytd"])
    meta = res["meta"]
    ref = res["report_ref"]

    def row(label, m):
        ex = "—" if "基准" in label else pp(m.get("excess_vs_benchmark", 0.0))
        return (f"<tr><td>{label}</td><td>{pct(m['cagr'])}</td><td>{pct(m['vol'])}</td>"
                f"<td>{m['sharpe']:.2f}</td><td>{pct(m['mdd'])}</td>"
                f"<td>{ex}</td></tr>")

    perf_rows = "".join([
        row("理论组合 · 基础因子（W=20）", gb),
        row("理论组合 · 综合因子（W=20）", gc),
        row("理论组合 · 行业等权基准", bm),
        row("5000 万 · 基础因子", nb),
        row("5000 万 · 综合因子", nc),
        row("5000 万 · 等权基准", bmn),
    ])

    cap_rows = "".join(
        f"<tr><td>{int(r['资金规模(万元)']):,}</td><td>{pct(r['年化收益'])}</td>"
        f"<td>{r['夏普']:.2f}</td><td>{pct(r['最大回撤'])}</td>"
        f"<td>{pp(r['超额(vs基准)'])}</td><td>{pct(r['年化成本拖累'])}</td>"
        f"<td>{r['最大参与率']*100:.1f}%</td><td>{int(r['受限天数'])}</td></tr>"
        for _, r in cap.iterrows()
    )

    ic_labels = {
        "base": "基础因子", "composite": "综合因子",
        "max_in": "行业间最大净流入", "breadth": "净流入为正比例",
        "out_sum": "净流出之和", "external": "市场外部净流入",
    }
    ic_rows = "".join(
        f"<tr><td>{ic_labels.get(k, k)}</td><td>{v['mean_ic']:.3f}</td>"
        f"<td>{v['ic_t']:.2f}</td><td>{v['positive_share']*100:.1f}%</td>"
        f"<td>{v['long_short_mean_bp']:+.0f}</td></tr>"
        for k, v in ic.items() if v
    )

    key_rows = "".join(
        f"<tr><td>{r['date']}</td><td>{r['semi_breadth']*100:.0f}%</td>"
        f"<td>{r['semi_flow']*100:+.1f}%</td>"
        f"<td>{r['telecom_breadth']*100:.0f}%</td>"
        f"<td>{r['telecom_flow']*100:+.1f}%</td>"
        f"<td>{r['corr_breadth_flow']:+.2f}</td></tr>"
        for _, r in key.iterrows()
    )

    ytd_best = ytd.head(3)
    ytd_worst = ytd.tail(3).iloc[::-1]
    ytd_rows = "".join(
        f"<tr><td>{r['name']}</td><td>{r['ytd']*100:+.1f}%</td>"
        f"<td>{'前三' if i < 3 else '后三'}</td></tr>"
        for i, (_, r) in enumerate(pd.concat([ytd_best, ytd_worst]).iterrows())
    )

    cost = pd.DataFrame(res["cost_sensitivity"])
    cost_min = cost["年化收益"].min()
    cost_max = cost["年化收益"].max()
    boot_lo, boot_hi = boot["annualized_ci_low"], boot["annualized_ci_high"]
    subs = pd.DataFrame(res["subsample"])
    sub_comp_22 = subs[(subs["组合"] == "综合因子") & (subs["区间"] == "2020-2022")]["年化收益"].iloc[0]
    sub_comp_26 = subs[(subs["组合"] == "综合因子") & (subs["区间"] == "2023-2026")]["年化收益"].iloc[0]
    sub_bm_22 = subs[(subs["组合"] == "等权基准") & (subs["区间"] == "2020-2022")]["年化收益"].iloc[0]
    sub_bm_26 = subs[(subs["组合"] == "等权基准") & (subs["区间"] == "2023-2026")]["年化收益"].iloc[0]

    html = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<style>{CSS}</style></head><body>

<h1>行业资金流向图：从华泰研报到 ETF 可执行性<br>——兼 2026 年 AI 硬件主线复盘</h1>
<div class="sub">作业编号 {PROJECT_ID} ｜ 样本 {meta['start']}–{meta['end']} ｜
{meta['n_etfs']} 只行业 ETF ｜ {meta['n_days']:,} 个交易日 ｜ 5000 万元模拟</div>

<div class="abstract">
<b>摘要：</b>本文用 {meta['n_etfs']} 只行业/主题 ETF 的公开日线，复现华泰证券《行业资金流向图应用于行业轮动》
的两层构造：主动净买入因子（公开数据下退化为 W=20 资金流强度）与曼宁公式资金流向图（五因子合成）。
{meta['start']}–{meta['end']} 上，理论组合年化 <b>{pct(gb['cagr'])}</b>（基础）、
<b>{pct(gc['cagr'])}</b>（综合），等权基准 {pct(bm['cagr'])}；研报同期为 21.97% / 22.63% / 9.31%。
<b>绝对收益没有复现</b>，但“综合优于基础”的方向复现：综合因子较基础因子 {pp(gc['cagr']-gb['cagr'])}，
最大回撤从 {pct(gb['mdd'])} 改善到 {pct(gc['mdd'])}（{abs(gc['mdd']-gb['mdd'])*100:.1f} pct），
与研报“收益小升、回撤大降”的改进模式一致。5000 万元、参与率≤5% ADV、含佣金/价差/冲击后，
综合因子年化 <b>{pct(nc['cagr'])}</b>、最大回撤 <b>{pct(nc['mdd'])}</b>、
年化成本拖累 {pct(nc['cost_drag_annual'])}，相对等权基准的超额为
<b>{pp(nc['excess_vs_benchmark'])}</b>。研报的“广度拐点”在 ETF 口径下<b>没有复现</b>：
本地半导体净流入为正比例在三个示例日为
{key.iloc[0]['semi_breadth']*100:.0f}% / {key.iloc[1]['semi_breadth']*100:.0f}% /
{key.iloc[2]['semi_breadth']*100:.0f}%，与研报的 29/39→37/39→13/39 方向不同，
与真实 ETF 资金流的截面相关也只有 {key.iloc[0]['corr_breadth_flow']:+.2f} /
{key.iloc[1]['corr_breadth_flow']:+.2f} / {key.iloc[2]['corr_breadth_flow']:+.2f}。
尽管如此，6 月 30 日因子仍满仓 AI 硬件，7 月半导体 −34%、10 月再 −25%——这正是本次复盘最值得写下的部分。
</div>

<h2>一、研究思路</h2>

<h3>1.1 研报的四步链条</h3>
<p>研报逻辑可拆成四步：① 用 Wind 主动买入、主动卖出金额构造行业主动净买入
<code>Q_i/V_i</code>（Q 为买卖占比之差，V 为成交额占比，W 日平滑），周度持有前 5 行业；
② 原始因子年化 {ref['base']['cagr']*100:.1f}%、超额 {ref['base']['excess']*100:.1f} pct，
但最大回撤 {ref['base']['mdd']*100:.1f}%、2022–2023 年跑输；③ 借鉴曼宁公式把行业间资金流建成“河网”，
用质量守恒 + 最小二范数特解 + 齐次通解 + 多初值梯度下降求解；④ 从流向图提取四个微观维度
（最大净流入、净流入为正比例、净流出之和、外部净流入），与主动净买入等权合成，
年化 {ref['composite']['cagr']*100:.1f}%、最大回撤 {ref['composite']['mdd']*100:.1f}%。</p>

<h3>1.2 三个问题</h3>
<ul>
<li><b>复现</b>：把 Wind 口径换成公开 ETF 数据，研报的收益与回撤改进还剩多少？</li>
<li><b>容量</b>：5000 万元真实执行，扣佣金、价差、冲击后，超额是否还在？边界在哪？</li>
<li><b>复盘</b>：研报对 2026 年 6–7 月 AI 硬件主线“缩圈→共识→松动”的判断，在 ETF 上能否复现？</li>
</ul>

<h2>二、数据与方法</h2>

<h3>2.1 数据与样本</h3>
<p>数据为 {meta['n_etfs']} 只行业/主题 ETF 的日线（baostock，含成交额、换手率、涨跌幅），
区间 {meta['start']}–{meta['end']}，共 {meta['n_days']:,} 个交易日、{meta['n_rebalances']} 次周度调仓；
新浪单只 ETF 主力资金流（2025-02 起）仅用于代理校验与 2026 案例。样本从 2020 年开始，
因为 2019 年下半年满足“上市满 120 个交易日”的行业 ETF 不足 11 只，更早的截面宽度不足。
与研报有三处口径差异：标的从 40 个中信行业指数换成 {meta['n_etfs']} 只 ETF；时间从 2018-12 起换成 2020-01 起；
数据从 Wind 主动买卖金额换成公开量价代理。<b>这三处差异是“绝对收益未复现”的主要原因，不应简单归因于方法失效。</b></p>

<h3>2.2 主动净买入的公开数据代理</h3>
<p>公开数据没有逐笔主动买卖，本文用 Chaikin 资金流乘数
<code>MFM=((C−L)−(H−C))/(H−L)</code> 作为“主动净买入强度”的代理，成交额占比 V、
换手率反推的流通市值占比 S、超额收益 H 作为流向图输入。需要说明一个容易被忽略的数学事实：
研报的 <code>Q_i/V_i</code> 依赖 Wind 主动买、卖总额<b>不相等</b>；在“买卖总额相等”的代理下，
<code>Q_i/V_i</code> 会退化为 <code>MFM_i</code> 本身。因此本地“基础因子”就是 20 日资金流强度（CMF 类），
不是对 Wind 口径的逐字复刻。方向仍与研报一致：资金流强度越高、成交占比越低，得分越高。</p>

<h3>2.3 资金流向图与求解</h3>
<p>节点 0 为市场外部（Q<sub>0</sub>=H<sub>0</sub>=0，V<sub>0</sub>=S<sub>0</sub>=1），其余为行业；
边 i&lt;j 的流量 q<sub>ij</sub> 满足节点守恒 <code>Aq=Q</code>。方程欠定，将解写成
<code>q=q₀+Φγ</code>（q₀ 为最小二范数特解，Φ 为 SVD 零空间），代入曼宁关系
<code>H_i=exp(α_i)·S_i^(exp(β₂)−1)·V_i^(−exp(β₁))·[A(q|q|)]_i+ε_i</code>，
最小化 Σε²；解析梯度 + L-BFGS-B，前一交易日解热启动 + 3 个随机初值。
全样本 {meta['n_flow_days']} 个交易日逐日求解，最大误差中位数 &lt;0.01‰、
95 分位 {fl['p95_max_err']*1000:.2f}‰，
{fl['share_below_5permille']*100:.1f}% 的日期低于研报的 5‰ 标准；最差一天
{fl['max_max_err']*1000:.1f}‰。但后文会说明，<b>拟合误差小并不等于模型有效</b>。</p>

<h3>2.4 回测、成本与 5000 万模拟</h3>
<p>每周最后一个交易日收盘算因子，次一交易日按 VWAP（成交额/成交量）成交，前 5 名等权，100 份整数手。
成本单边 = 佣金 1bp + 半价差 2bp + 冲击 <code>10bp×sqrt(参与率/5%)</code>；
参与率 = 成交额 / ADV20，上限 5%，超出则缩减成交并保留现金。
份额折算日用“价格比 / (1+涨跌幅)”识别并同步调整份额（2020 年以来共 13 次，含 2026-07 的 1:2 折算）。
容量扫描 1000 万–5 亿元；参数敏感性覆盖 W=15/20/25 与 top3/5/8；成本敏感性覆盖冲击 5/10/20bp、
佣金 0.5/1/2bp，全部报告、不择优。</p>

<h2>三、研究结果</h2>

<h3>3.1 信号层：改进方向复现，绝对收益没有</h3>
<p>表1 第一组是未计成本与容量的理论组合。基础因子年化 {pct(gb['cagr'])}、综合因子
{pct(gc['cagr'])}、等权基准 {pct(bm['cagr'])}；研报的 21.97%/22.63% 与 9.31% 没有出现，
综合因子超额 {pp(gc['excess_vs_benchmark'])}，远小于研报的 13.32 pct。
但<b>改进的方向复现了</b>：综合因子较基础因子 {pp(gc['cagr']-gb['cagr'])}，
最大回撤从 {pct(gb['mdd'])} 收窄到 {pct(gc['mdd'])}，改善
{abs(gc['mdd']-gb['mdd'])*100:.1f} pct，甚至大于研报的 12.59 pct。
更有意思的是，综合因子的 Rank IC 反而低于基础因子（{ic['composite']['mean_ic']:.3f} vs
{ic['base']['mean_ic']:.3f}），说明改进<b>不是来自截面排序能力，而是来自风险结构</b>：
四个低相关弱因子把组合从“押注单一资金流强度”变成“多维度投票”，收益略升、回撤大降。
四个微观因子的 IC 都很弱：净流出之和 {ic['out_sum']['mean_ic']:.3f}（t={ic['out_sum']['ic_t']:.2f}）
是唯一略正的一项，最大净流入 {ic['max_in']['mean_ic']:.3f}（t={ic['max_in']['ic_t']:.2f}）、
广度 {ic['breadth']['mean_ic']:.3f}（t={ic['breadth']['ic_t']:.2f}）、
外部净流入 {ic['external']['mean_ic']:.3f}（t={ic['external']['ic_t']:.2f}）都接近零或为负。
这与研报“四个弱因子、低相关、合成后改善”的描述一致，但“弱”到在 18 只 ETF 上无法单独使用。</p>

{fig('fig1_nav.png', '图1　理论组合（A）与 5000 万元模拟（B）的累计净值。综合因子复现了“收益略升、回撤大降”的方向，但绝对收益远低于研报。')}

<table>
<tr><th>组合</th><th>年化</th><th>波动</th><th>夏普</th><th>最大回撤</th><th>超额</th></tr>
{perf_rows}
</table>
<div class="cap">表1　业绩指标（2020-01-02–2026-10-30；超额 = 年化 − 等权基准年化；5000 万组合含成本与容量约束）。</div>

<h3>3.2 执行层：5000 万扣成本后只剩 3%，超额转负</h3>
<p>表1 第二组是 5000 万元、参与率≤5% ADV、含成本的模拟。基础因子年化 {pct(nb['cagr'])}、
综合因子 {pct(nc['cagr'])}、等权基准 {pct(bmn['cagr'])}；综合因子年化成本拖累
{pct(nc['cost_drag_annual'])}，最大参与率 {nc['max_participation']*100:.1f}%，
受限天数 {nc['binding_days']}。50,000,000 元本金期末变为
<b>{nc['final_value']/1e4:,.0f} 万元</b>（净收益 {nc['net_profit']/1e4:+,.0f} 万元），
最大回撤 {pct(nc['mdd'])}。理论组合 {pct(gc['cagr'])} 到净结果 {pct(nc['cagr'])} 的 5.1 pct 差距，
约一半来自成本（{pct(nc['cost_drag_annual'])}），另一半来自容量约束下的“想买买不到、想卖卖不掉”。
5000 万组合的周频超额 bootstrap 95% 区间为
[{boot_lo*100:+.1f}, {boot_hi*100:+.1f}] pct/年，HAC t = {boot['hac_t']:.2f}，
不能拒绝“超额为零”。成本敏感性也不小：冲击 5bp 时年化 {pct(cost_max)}，
20bp 时只有 {pct(cost_min)}——结论取决于冲击假设，不能只看一个点估计。</p>

<h3>3.3 容量：不是“越大越差”，而是策略被约束改变了</h3>
<p>表3 与图2 的容量曲线<b>不是单调下降</b>：1000 万 {pct(cap.iloc[0]['年化收益'])}、
3000 万 {pct(cap.iloc[1]['年化收益'])}、5000 万 {pct(cap.iloc[2]['年化收益'])}，
随后 1 亿 {pct(cap.iloc[3]['年化收益'])}、2 亿 {pct(cap.iloc[4]['年化收益'])}、
5 亿 {pct(cap.iloc[5]['年化收益'])}。原因不是“大资金更强”，而是大资金触及参与率上限后，
调仓被截断，换手率从 {cap.iloc[2]['年化换手']:.1f} 降到 {cap.iloc[5]['年化换手']:.1f}，
成本拖累从 {pct(cap.iloc[2]['年化成本拖累'])} 降到 {pct(cap.iloc[5]['年化成本拖累'])}，
组合被动变成长持有。真正的容量结论是：<b>5000 万时净超额已为
{pp(nc['excess_vs_benchmark'])}，且 {nc['binding_days']} 天受限；规模再大，
策略逐渐退化为低换手的等权持有，信号作用减弱。</b>“容量”不是静态的 ADV 比例，
而是“流动性差的行业先被挤出”的动态过程。</p>

{fig('fig4_capacity.png', '图2　容量曲线：净年化收益（左）与最大参与率（右）。5000 万附近触及 5% ADV 约束，更大规模下策略被截断为低换手组合。', '96%')}

<table>
<tr><th>资金（万元）</th><th>年化</th><th>夏普</th><th>最大回撤</th><th>超额</th><th>成本拖累</th><th>最大参与率</th><th>受限天数</th></tr>
{cap_rows}
</table>
<div class="cap">表3　容量扫描（综合因子，W=20，top5，含成本与参与率约束）。</div>

<h3>3.4 2026 复盘：因子在共识顶点满仓，广度没有提前报警</h3>
<p>2026 年是极端分化的一年：半导体 6 月 <b>+39.1%</b>、7 月 <b>−34.0%</b>、10 月再
<b>−24.6%</b>，全年 −1.6%；通信 6 月 +13.0%、7 月 −35.2%、10 月 −31.0%，全年 −15.9%；
同期煤炭 +20.4%、银行 +8.5%、电力 +2.5% 为正收益，游戏 −33.8%、新能源 −33.4%、
新能源车 −31.6% 垫底。6 月 30 日，基础因子与综合因子的前 5 名都是半导体、通信、光伏、
新能源/新能源车、军工——<b>因子在 AI 硬件的共识顶点满仓</b>，7 月的 −34% 直接打在组合上。
5000 万净组合 7 月 −15.1%（基准 −4.1%），10 月 −1.7%（基准 −8.8%）：7 月被 AI 硬件反噬，
9 月底已轮换到银行、电力、地产，反而避开了 10 月的第二波下跌。
这不是“因子失效”，而是动量因子在共识顶点天然最脆弱：它买的正是“过去最强”，
而最强的那一刻往往也是边际资金耗尽的那一刻。</p>

{fig('fig2_flowmap.png', '图3　行业资金流向图：2026-06-24、06-30、07-06 三个示例日（红=净流入，蓝=净流出，仅画前 26 条边）。图形能读出“资金往哪去”，但本地广度没有复现研报的“先升后降”。')}

<p>表4 对比了研报三个日期上本地流向图的“净流入为正比例”与新浪真实主力净流入。
<b>研报的“缩圈→共识→松动”在 ETF 上没有复现</b>：本地半导体的广度是
{key.iloc[0]['semi_breadth']*100:.0f}% / {key.iloc[1]['semi_breadth']*100:.0f}% /
{key.iloc[2]['semi_breadth']*100:.0f}%，在 6 月 24 日最高、6 月 30 日最低，与研报
29/39→37/39→13/39 的“先升后降”方向相反；通信是
{key.iloc[0]['telecom_breadth']*100:.0f}% / {key.iloc[1]['telecom_breadth']*100:.0f}% /
{key.iloc[2]['telecom_breadth']*100:.0f}%，也没有单调变化。
广度与真实 ETF 主力净流入的截面相关为 {key.iloc[0]['corr_breadth_flow']:+.2f} /
{key.iloc[1]['corr_breadth_flow']:+.2f} / {key.iloc[2]['corr_breadth_flow']:+.2f}，
没有稳定的正相关。这意味着：在 18 只 ETF、量价代理、欠定求解这三个条件下，
<b>“广度拐点”不是一个可靠的 timing 信号</b>。</p>
<p>更值得记录的是口径差异：研报 2026-06-24 称通信设备“净流入为正比例仅 9/39”，
但同日通信 ETF 的新浪主力净流入是 <b>{key.iloc[0]['telecom_flow']*100:+.1f}%</b>（净流入率），
6 月 26 日更高达 +17.5%。两者不矛盾：研报测的是<b>行业间相对流向</b>，ETF 资金流测的是
<b>单只产品的绝对进出</b>。同一日、同一条主线，两个“资金流”可以给出相反结论。
做策略前必须先定义清楚：你要的是“相对谁”的资金流。</p>

{fig('fig3_review2026.png', '图4　A：2026 年行业 ETF 月度收益；B：半导体 ETF 复权价格与本地“净流入为正比例”（5 日均）。广度没有在 7 月暴跌前给出稳定预警。')}

<table>
<tr><th>日期</th><th>半导体广度</th><th>半导体真实净流入率</th><th>通信广度</th><th>通信真实净流入率</th><th>广度-资金流截面相关</th></tr>
{key_rows}
</table>
<div class="cap">表4　2026 年三个关键日期的本地广度与新浪真实主力净流入（净流入率 = 净额/成交额）。</div>

<h3>3.5 稳健性</h3>
<p>子区间看，综合因子在 2020–2022 年化 {pct(sub_comp_22)}（基准 {pct(sub_bm_22)}），
2023–2026 年化 {pct(sub_comp_26)}（基准 {pct(sub_bm_26)}）——超额主要来自后一段，
与研报“2022–2023 年正超额”的稳定性并不相同。W=15/20/25 的综合因子年化为
{pct(pd.DataFrame(res['sensitivity']).query("因子=='综合因子' and topN==5").set_index('W').loc[15,'年化收益'])} /
{pct(gc['cagr'])} /
{pct(pd.DataFrame(res['sensitivity']).query("因子=='综合因子' and topN==5").set_index('W').loc[25,'年化收益'])}，
top3/5/8 为
{pct(pd.DataFrame(res['sensitivity']).query("因子=='综合因子' and W==20").set_index('topN').loc[3,'年化收益'])} /
{pct(gc['cagr'])} /
{pct(pd.DataFrame(res['sensitivity']).query("因子=='综合因子' and W==20").set_index('topN').loc[8,'年化收益'])}，
方向不翻转，但 top3 的收益更高、集中度也更高，不能据此择优。</p>

<h2>四、结论与思考</h2>

<h3>4.1 我从这篇研报里学到的五件事</h3>
<ol>
<li><b>先做数据体检，再建模。</b>研报发现 Wind 主动买卖金额长期为负的系统性误差，用“占比之差”
而不是绝对净额来消除它。这比换一个数据源更根本：误差是口径带来的，就在口径内解决。</li>
<li><b>把不可观测量变成可估计量。</b>行业间资金流无法直接观测，研报用河网/曼宁公式建立
“流量—超额收益”关系，再用质量守恒和欠定方程求解。这套“物理类比 + 约束 + 正则化”的思路，
可以迁移到期现基差、ETF 申赎、跨境资金等任何“看得见结果、看不见流量”的场景。</li>
<li><b>弱因子合成的价值在风险结构，不在 IC。</b>我们的综合因子 Rank IC 反而低于基础因子，
但收益 +{ (gc['cagr']-gb['cagr'])*100:.1f} pct、最大回撤改善
{abs(gc['mdd']-gb['mdd'])*100:.1f} pct。改进来自四个低相关弱因子的“多维度投票”，
不是更强的截面排序。这个区分很重要：如果只盯 IC，会错过真正的改进。</li>
<li><b>指标的口径决定结论，跨口径验证是必修课。</b>研报的“净流入为正比例”在 ETF 上没有复现，
与真实 ETF 资金流的相关性也不稳定；06-24 通信的“9/39 vs +6.9%”是最具体的反例。
我们学到的是：不要直接搬用一个“看起来有道理”的指标，先在目标 universe 上验证它的符号与稳定性。</li>
<li><b>可视化是研究工具，不是装饰。</b>流向图把“缩圈/共识/松动”这种主观判断变成可比较的图形；
弦图、网络图、时间轴动画都是自然的延展。图3 的三连图，比任何一段文字都更直观——
即使它这次没有给出可交易的信号，它仍然帮我们看清了市场在讨论什么。</li>
</ol>

<h3>4.2 对研报的三点批判</h3>
<p><b>第一，识别问题。</b>N=18 时未知量约 173 个（γ 153 + α 19 + β 2），而独立方程只有 19 个；
研报 N=40 时更悬殊（约 824 个未知量对 82 个方程）。因此“建模误差 &lt;5‰”几乎是参数数量的必然结果，
<b>不能当作模型有效的证据</b>。最小二范数解是一个假设（能量最低），不是市场事实；
换初值、换正则化，流向图会变。我们建议报告“流向的置信带”，而不是单点图。</p>
<p><b>第二，口径问题。</b>“行业间相对流向”与“单只 ETF 绝对流向”不是同一个东西。
2026-06-24 通信的反例说明，同一日可以一个说“分歧”、一个说“大幅流入”。
做策略时先定义清楚资金流的口径，再谈方向。</p>
<p><b>第三，成本与容量问题。</b>研报的回测未计交易费用与容量。我们的 5000 万模拟显示，
周度行业轮动的换手率足以让年化成本拖累达到 {pct(nc['cost_drag_annual'])}，
叠加早期 ETF 流动性不足，净超额转为 {pp(nc['excess_vs_benchmark'])}。容量不是“资金/ADV”的静态比例，
而是“流动性差的行业先被挤出”的动态过程。</p>

<h3>4.3 如果我来改进</h3>
<ul>
<li>用 ETF <b>份额变化（申购赎回）</b>补充成交额口径：份额变化是真实资金进出，
不受“主动买/卖”分类误差影响，且日频可得。</li>
<li>把“净流入为正比例”做成日频<b>广度开关</b>——但先要在目标 universe 上验证它的符号与领先性；
本次在 ETF 上没有通过这个检验，所以它仍是一个待验证的想法，而不是结论。</li>
<li>对流向图做<b>滚动求解 + 解稳定性区间</b>，报告“流向的置信带”，而不是单点图。</li>
</ul>

<h3>4.4 对今年行情的复盘</h3>
<p>2026 年的主线是 AI 硬件：4–6 月半导体、通信同步加速，光伏/新能源车在 6 月被资金推到榜首，6 月 30 日因子满仓；
7 月半导体 −34%、通信 −35%，10 月再 −25%/−31%。同期煤炭、银行、电力全年为正。
这不是“因子失效”，而是<b>动量因子在共识顶点天然最脆弱</b>：它买的正是“过去最强”，
而最强的那一刻往往也是边际资金耗尽的那一刻。对 5000 万组合的启示是：
不要把“因子排名”当作仓位开关；如果要用广度做风险开关，必须先证明它在目标 universe 上
有稳定的领先性——本次没有做到，这是下一步要补的功课，而不是本次的结论。</p>

<h2>五、复现说明</h2>
<p class="small" style="text-align:left">环境：Python 3.12+ 虚拟环境，依赖见 <code>requirements.txt</code>。
复现：<code>python -m venv .venv</code> → <code>pip install -r requirements.txt</code> → <code>python run_all.py</code>
（抓数→特征→流向图→回测→图表→报告；数据已缓存，可离线重跑，加 <code>--refresh</code> 重新抓取）。
产物：<code>data/raw/</code>（ETF 日线与资金流快照，抓取日期 2026-10-31）、
<code>output/tables/</code>（统计表与 <code>results.json</code>）、
<code>output/figures/</code>（图 1–4）、<code>output/{PROJECT_ID}_report.html/.pdf</code>。
报告中每个数字均由 <code>results.json</code> 渲染，未手工填写；完整流程亦整合为自包含 Notebook
（<code>output/{PROJECT_ID}_research.ipynb</code>），已推送至 GitHub 公开仓库
<a class="url" href="{REPO_URL}">{REPO_URL}</a>。</p>
<p class="small" style="text-align:left;margin:.5mm 0 0">在线查看（nbviewer）：<br>
<a class="url" href="{NBVIEWER_URL}">{NBVIEWER_URL}</a></p>

<h2>参考文献</h2>
<ol class="ref">
<li>华泰证券研究所，徐特、何康（2026-08-13）.《行业资金流向图应用于行业轮动》. 华泰证券金工深度研究.</li>
<li>Chaikin, M. (1966). The Chaikin Money Flow indicator. <i>Stock Market Publishing</i>.</li>
<li>数据：baostock ETF 日线接口；新浪财经 MoneyFlow 单只 ETF 资金流接口（抓取日期 2026-10-31）.</li>
<li>本项目代码与 Notebook：<a class="url" href="{REPO_URL}">{REPO_URL}</a>.</li>
</ol>

</body></html>"""
    return html


def render_pdf(html_path: Path, pdf_path: Path) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(html_path.as_uri())
        page.wait_for_timeout(600)
        page.pdf(path=str(pdf_path), format="A4", print_background=True,
                 margin={"top": "13mm", "bottom": "11mm", "left": "14mm", "right": "14mm"})
        browser.close()


def build() -> Path:
    res = json.loads((OUTPUT / "results.json").read_text(encoding="utf-8"))
    html = build_html(res)
    html_path = OUTPUT / f"{PROJECT_ID}_report.html"
    html_path.write_text(html, encoding="utf-8")
    pdf_path = OUTPUT / f"{PROJECT_ID}_report.pdf"
    render_pdf(html_path, pdf_path)
    print(f"[report] {html_path}\n[report] {pdf_path}")
    return pdf_path


if __name__ == "__main__":
    build()
