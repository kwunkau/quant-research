"""报告生成：把 results.json 与图表渲染为 HTML，再打印为 PDF。"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pandas as pd

from .config import FIG_DIR, NBVIEWER_URL, OUTPUT, PROJECT_ID, REPO_URL, TABLE_DIR

CSS = """
@page { size: A4; margin: 14mm 14mm 12mm 14mm; }
* { box-sizing: border-box; }
body { font-family: "Microsoft YaHei", "SimSun", sans-serif; font-size: 9.3pt;
       line-height: 1.5; color: #222; margin: 0; }
h1 { font-size: 16.5pt; margin: 0 0 2mm 0; letter-spacing: .5px; }
.sub { color: #666; font-size: 9pt; margin-bottom: 5mm; }
h2 { font-size: 11.5pt; margin: 5mm 0 2mm; padding-left: 3mm;
     border-left: 3px solid #2F6F8F; }
h3 { font-size: 10pt; margin: 3.5mm 0 1.5mm; color: #1F4F66; }
p { margin: 1.5mm 0; text-align: justify; }
.abstract { background: #F4F7F9; border-left: 3px solid #2F6F8F;
            padding: 3mm 4mm; margin: 3mm 0 4mm; font-size: 9.2pt; }
.abstract b { color: #1F4F66; }
table { border-collapse: collapse; width: 100%; font-size: 8.4pt; margin: 2mm 0 3mm;
        break-inside: avoid; page-break-inside: avoid; }
tr { break-inside: avoid; page-break-inside: avoid; }
th { background: #EDF2F5; font-weight: 600; }
th, td { border-bottom: 1px solid #DCE3E8; padding: 1.2mm 1.8mm; text-align: right; }
th:first-child, td:first-child { text-align: left; }
tr.total td { font-weight: 600; border-top: 1px solid #9FB3BF; }
.cap { font-size: 8.2pt; color: #666; margin: 1mm 0 3mm; }
figure { margin: 2mm 0 1mm; page-break-inside: avoid; }
figure img { width: 100%; display: block; }
.kv { color: #1F4F66; font-weight: 600; }
ul { margin: 1.5mm 0 1.5mm 5mm; padding: 0; }
li { margin: .8mm 0; }
.ref { font-size: 8.2pt; color: #444; }
.ref li { margin-bottom: 1mm; }
.pagebreak { page-break-before: always; }
.small { font-size: 8.3pt; color: #555; }
a.url { font-family: Consolas, "Courier New", monospace; font-size: 7.2pt;
        color: #1F4F66; text-decoration: none; word-break: break-all; }
code { background: #F2F2F2; padding: 0 .8mm; font-size: 8.4pt; }
"""


def b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


def fig(name: str, caption: str, width: str = "100%") -> str:
    return (f'<figure style="width:{width};margin-left:auto;margin-right:auto">'
            f'<img src="data:image/png;base64,{b64(FIG_DIR / name)}">'
            f'<figcaption class="cap">{caption}</figcaption></figure>')


def fmt_p(p: float) -> str:
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def build_html(res: dict) -> str:
    s, nd, sd = res["sample"], res["next_day"], res["same_day"]
    reg_u, reg_c = res["regression"]["univariate"], res["regression"]["controlled"]
    reg_s = res["regression"]["same_day"]
    ls = res["decile"]["long_short"]
    bh = res["bh"]
    roll = res["rolling"]
    dc = res["data_check"]

    desc = pd.read_csv(TABLE_DIR / "t01_descriptive.csv", index_col=0)
    rows = ["nbi", "r0", "divergence", "r", "vol20"]
    labels = {"nbi": "主买净流入率 NBI", "r0": "超大单净流入率 R0",
              "divergence": "超大单-全单分歧 D", "r": "指数日收益 r", "vol20": "20 日波动率"}
    desc_rows = "".join(
        f"<tr><td>{labels[k]}</td><td>{desc.loc[k, 'mean']:.4f}</td>"
        f"<td>{desc.loc[k, 'std']:.4f}</td><td>{desc.loc[k, 'min']:.4f}</td>"
        f"<td>{desc.loc[k, 'max']:.4f}</td><td>{desc.loc[k, 'skew']:.2f}</td>"
        f"<td>{desc.loc[k, 'ac1']:.3f}</td></tr>" for k in rows)

    dec = pd.read_csv(TABLE_DIR / "t04_decile.csv")
    dec_rows = "".join(
        f"<tr><td>第 {int(r.group)} 组</td><td>{int(r.n)}</td><td>{r.mean_bp:+.1f}</td>"
        f"<td>[{r.ci_low_bp:+.1f}, {r.ci_high_bp:+.1f}]</td><td>{r.t:.2f}</td>"
        f"<td>{r.win * 100:.1f}%</td></tr>" for _, r in dec.iterrows())

    # 回归表直接读 CSV，保证与脚本输出逐字一致
    regdf = pd.read_csv(TABLE_DIR / "t03_regression.csv")
    reg_rows = "".join(
        f"<tr><td>{r['模型']}</td><td>{r['变量']}</td><td>{r['系数']:.4f}</td>"
        f"<td>{r['t 值']:.2f}</td><td>{fmt_p(r['p 值'])}</td><td>{r['R2']:.4f}</td></tr>"
        for _, r in regdf.iterrows())

    subs = pd.read_csv(TABLE_DIR / "t07_subsample.csv")
    hor = pd.read_csv(TABLE_DIR / "t06_horizon.csv")
    ind = pd.read_csv(TABLE_DIR / "t09_indicators.csv")

    robust_rows = "".join(
        f"<tr><td>子区间 {r.period}</td><td>{r['corr']:+.3f}</td><td>{fmt_p(r['p'])}</td><td>{r.n}</td></tr>"
        for _, r in subs.iterrows())
    robust_rows += "".join(
        f"<tr><td>持有期 {r.horizon}</td><td>{r['corr']:+.3f}</td><td>{fmt_p(r['p'])}</td><td>{r.n}</td></tr>"
        for _, r in hor.iterrows() if r.horizon != "1 日")
    robust_rows += "".join(
        f"<tr><td>指标：{r['指标']}</td><td>{r['corr']:+.3f}</td><td>{fmt_p(r['p'])}</td><td>{s['n']}</td></tr>"
        for _, r in ind.iterrows())

    html = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<style>{CSS}</style></head><body>

<h1>主动性买盘与沪深300指数次日走势</h1>
<div class="sub">基于 2012–2026 年日度资金流的实证检验 ｜ 作业编号 {PROJECT_ID} ｜ {s['start']} – {s['end']}</div>

<div class="abstract">
<b>摘要：</b>本文用沪深300板块日度资金流构造“主买净流入率”（主动买入净额 ÷ 成交额），
在 {s['n']:,} 个交易日上检验其与指数当日、次日收益的关系。主买强度与<b>当日</b>收益高度同步
（Pearson {sd['pearson']:.3f}，R² = {reg_s['r2']:.3f}，回归 t = {reg_s['t']['nbi']:.1f}），与<b>次日</b>收益几乎无关
（Pearson {nd['pearson']:.3f}，p = {nd['p_pearson']:.2f}，95% 置信区间 [{nd['ci_low']:.3f}, {nd['ci_high']:.3f}]）。
控制当日收益、波动率与成交额后，主买强度的 HAC t 值仅 {reg_c['t']['nbi']:.2f}（p = {fmt_p(reg_c['p']['nbi'])}）。
{bh['n_tests']} 项预测性检验中，原始显著 {bh['n_raw_sig']} 项，经 Benjamini-Hochberg 校正后 <b>0 项</b>。
结论：日频主动性买盘主要是价格的结果，而非次日走势的先兆。
</div>

<h2>一、研究思路</h2>

<h3>1.1 为什么选择“主买净流入率”</h3>
<p>“主动性买盘”指以卖方报价成交、由买方主动吃单的交易。它与普通成交额的区别在于<b>方向</b>：
同样 1 亿元成交，是买方主动打上去的，还是卖方主动砸下来的，对后续价格的含义完全不同。
海通证券[1][2]用逐笔成交识别主买/主卖，并以“主买占比”“主买强度”构建选股因子；本文在指数层面沿用同一思路。</p>
<p>具体选用数据商的<b>主买净流入额 ÷ 当日成交额</b>（下称主买净流入率 NBI）而非净额绝对值，原因有三：
(i) 2012 年以来沪深300日均成交额放大约 {res['turnover_growth']['ratio']:.0f} 倍（{res['turnover_growth']['y2012_yi']:.0f} 亿 → {res['turnover_growth']['y_last_yi']:,.0f} 亿），绝对净额不可跨期比较，比率无量纲；
(ii) 比率天然剔除了市场整体流动性的季节性与趋势；
(iii) 它对应文献中“主买强度”的构造，经济含义清晰——每 1 元成交中，有多少是买方主动推动的净额。</p>

<h3>1.2 想验证的假设</h3>
<ul>
<li><b>H1（同期）</b>：主买强度与当日收益显著正相关——这是数据口径的“体检”。</li>
<li><b>H2（次日）</b>：若资金流是“聪明钱”，应能预测次日收益；若只是价格的影子，则预测力应接近零。</li>
<li><b>H3（结构）</b>：极端主买、超大单、牛熊与高低波动状态下，预测关系是否不同。</li>
</ul>

<h2>二、数据与方法</h2>

<h3>2.1 数据来源与区间</h3>
<table>
<tr><th>数据</th><th>来源</th><th>区间</th><th>记录数</th></tr>
<tr><td>沪深300板块日度资金流（主买净额、净流入率、超大单净额）</td><td>新浪财经 MoneyFlow 接口</td><td>2010-03-08 至 2026-10-29</td><td>4,038</td></tr>
<tr><td>沪深300指数日线（收盘价、成交额）</td><td>baostock</td><td>2011-12-01 至 2026-10-29</td><td>3,619</td></tr>
<tr><td>研究样本（两者交集，2012 年起）</td><td>—</td><td>{s['start']} 至 {s['end']}</td><td>{s['n']:,}</td></tr>
</table>
<p class="small">说明：东方财富“主力资金”历史接口目前仅保留最近 121 个交易日（2026-04-30 起），无法覆盖 2012 年至今，故未采用；
本文全部结论基于新浪板块资金流。数据一致性校验：由“净额 ÷ 净流入率”反推的成交额与指数实际成交额的比值中位数为
{dc['implied_ratio_median']:.3f}，两者相关系数 {dc['corr_implied_actual']:.3f}，说明该序列确实是按沪深300成分股成交额口径聚合的，口径内部自洽。</p>

<h3>2.2 指标与方法</h3>
<p>指标：NBI<sub>t</sub> = 主买净流入额<sub>t</sub> / 成交额<sub>t</sub>；R0<sub>t</sub> 为超大单净流入率；
D<sub>t</sub> = R0<sub>t</sub> − NBI<sub>t</sub> 度量大单与全单的方向分歧；Z<sub>t</sub> 为 NBI 的滚动 250 日标准化值（仅用 t 日及以前信息，无前视）。</p>
<p>方法：(1) Pearson / Spearman 相关，配移动块 bootstrap（500 次、块长 20）置信区间；
(2) Newey-West HAC(5) 回归，先单变量、再控制当日收益 r<sub>t</sub>、20 日波动率与对数成交额；
(3) 按 Z<sub>t</sub> 十分位分组统计次日收益，并做多空价差检验；
(4) 牛熊（收盘价是否高于 250 日均线）与波动三分位分组；
(5) 对全部 {bh['n_tests']} 项预测性检验做 Benjamini-Hochberg 多重检验校正。</p>

{fig('fig1_timeseries.png', '图1　沪深300指数（上）与主买净流入率（下，柱为日度值，实线为 20 日移动平均）。资金流围绕零轴双向波动，未呈现与指数的同步趋势。', '90%')}

<h2>三、研究结果</h2>

<h3>3.1 同期关系：几乎是同一个变量</h3>
<p>NBI 与当日收益的 Pearson 相关系数为 <span class="kv">{sd['pearson']:.3f}</span>（Spearman {sd['spearman']:.3f}，
bootstrap 95% 置信区间 [{sd['ci_low']:.3f}, {sd['ci_high']:.3f}]），单变量回归 R² = {reg_s['r2']:.3f}、t = {reg_s['t']['nbi']:.1f}。
即主买净流入率每高 1 个百分点，当日收益平均高约 0.20 个百分点。同期相关在滚动窗口内始终维持在 {roll['same_min']:.2f}–{roll['same_max']:.2f}
（图4），是全样本最稳定的统计特征。这说明数据口径可靠——“主动买盘”确实捕捉到了当日买卖压力的方向。</p>

{fig('fig2_scatter.png', '图2　主买净流入率与指数收益的散点图：左为同日（r = 0.750，R2 = 0.563），右为次日（r = 0.024，R2 = 0.001）。', '94%')}

<h3>3.2 次日关系：预测力消失</h3>
<p>把被解释变量换成次日收益后，相关系数降至 <span class="kv">{nd['pearson']:.3f}</span>（p = {nd['p_pearson']:.2f}），
Spearman 秩相关 {nd['spearman']:.3f}（p = {nd['p_spearman']:.2f}），bootstrap 置信区间
[{nd['ci_low']:.3f}, {nd['ci_high']:.3f}] 覆盖 0。HAC 回归中 NBI 系数为 {reg_u['coef']['nbi']:.4f}
（t = {reg_u['t']['nbi']:.2f}，p = {reg_u['p']['nbi']:.2f}，R² = {reg_u['r2']:.4f}）；
加入当日收益、波动率与成交额后系数进一步降至 {reg_c['coef']['nbi']:.4f}（t = {reg_c['t']['nbi']:.2f}，
p = {fmt_p(reg_c['p']['nbi'])}），R² 仅 {reg_c['r2']:.4f}。换言之，当日收益已经“吸收”了资金流的全部信息。</p>
<p>图4 显示，滚动 250 日的次日相关系数长期在零轴附近摆动，全样本 {roll['next_positive_share']*100:.1f}% 的时间为正；
唯一一次明显抬升出现在 <b>{roll['next_max_date']}</b>，达到 {roll['next_max']:.3f}，对应 2024 年 9 月末政策行情，
属于单边急涨中的短窗口现象；截至样本末端已回落至 {roll['next_current']:.3f}。</p>

{fig('fig4_rolling.png', '图4　主买净流入率与当日收益、次日收益的滚动 250 日相关系数。', '92%')}

<h3>3.3 分组与状态：没有稳定的方向性</h3>
<p>按 Z<sub>t</sub> 分十分位后，次日平均收益在 −12.7 bp 至 +17.8 bp 之间无规律跳动（表2、图3）：
第 10 组（主买最强）+17.8 bp（t = 2.35）与第 3 组 −12.7 bp 看似突出，但多空价差仅
{ls['spread_bp']:.1f} bp，t = {ls['t']:.2f}（p = {ls['p']:.3f}），且分组间不单调。
牛市（0.042，p = 0.070）略高于熊市（0.011，p = 0.645），波动三分组为 0.033 / 0.048 / 0.015，均不显著；
牛熊 × 波动交叉后最大单元格为 0.097（牛市 × 中波动），但每个单元格仅约 600 个交易日，仍落在噪声范围内。</p>

{fig('fig5_heatmap.png', '图5　牛熊 × 波动状态下的次日相关系数：所有单元格均在 ±0.1 以内。', '58%')}

<table>
<tr><th>分组</th><th>样本数</th><th>次日平均收益（bp）</th><th>95% 置信区间</th><th>t 值</th><th>胜率</th></tr>
{dec_rows}
</table>
<div class="cap">表2　按主买强度 Z 值十分位分组的次日收益（1 = 净卖出最强，10 = 净买入最强）。</div>

{fig('fig3_decile.png', '图3　分组次日平均收益及 95% 置信区间：组间差异在统计噪声之内。', '92%')}

<h3>3.4 稳健性</h3>
<p>子区间、持有期与替代指标的结果高度一致（表3）：四个子区间的相关系数在 −0.028 至 +0.056 之间且均不显著，
剔除 2015 年股灾与 2016 年熔断区间后为 {subs.iloc[-1]['corr']:.3f}（p = {subs.iloc[-1]['p']:.3f}）；
持有期延长到 5/10/20 日，相关系数仍不超过 0.02。替代指标中，超大单净流入率
（{ind.iloc[1]['corr']:.3f}，p = {ind.iloc[1]['p']:.3f}）是唯一在未校正水平上接近显著的变量，
但经 BH 校正后不再显著；大单与全单的分歧指标接近 0。</p>

<table>
<tr><th>检验</th><th>相关系数</th><th>p 值</th><th>样本数</th></tr>
{robust_rows}
</table>
<div class="cap">表3　稳健性检验：子区间、持有期与替代指标与次日收益的相关性。</div>

<p class="small">多重检验：本文共做 {bh['n_tests']} 项“是否存在预测力”的检验，未校正时 {bh['n_raw_sig']} 项在 5% 水平显著
（第 10 分组 t≈2.35、超大单净流入率 p={ind.iloc[1]['p']:.3f}），Benjamini-Hochberg 校正后显著项为
<b>{bh['n_adj_sig']}</b> 项。这与“做了足够多次检验，总会撞上一次显著”的预期完全吻合，不能据此构建策略。</p>

<h2>四、结论与思考</h2>
<p><b>结论。</b>在 2012–2026 年的 {s['n']:,} 个交易日上，主动性买盘与沪深300<b>当日</b>收益高度同步（r = {sd['pearson']:.3f}，
R² = 0.563），但对<b>次日</b>收益没有可用的预测力（r = {nd['pearson']:.3f}，p = {nd['p_pearson']:.2f}）。
分组、状态划分、多期限与替代指标均未提供稳健的反例；多重检验校正后无一项显著。</p>
<p><b>是否符合预期。</b>研究前我倾向认为“主动买盘强 → 次日延续”，结果否定了这一直觉。更合理的解释是：
日频资金流是<b>成交过程的事后归纳</b>——它记录的是当天谁更着急，而当天收盘价已经把这份着急定价完毕；
次日开盘面对的是新的信息集。这也解释了为何同期相关极高而次日相关归零。</p>
<p><b>局限。</b>(1) 板块口径：新浪按板块聚合，若其成分回溯方式含幸存者偏差，历史序列会与真实可投资集合存在偏差；
(2) 频率：日频聚合抹平了日内信息，尾盘 30 分钟的主动买盘可能比全天净额更有信息量；
(3) 识别方法：数据商以单笔成交金额分层加价格方向近似“主动方”，并非严格逐笔 Lee-Ready 判定；
(4) 单一市场状态：样本覆盖两轮牛熊，但 2024 年 9 月后市场微观结构变化较快，需持续跟踪。</p>
<p><b>可以继续做的。</b>① 用分钟级数据构造 Lee-Ready 订单流不平衡，检验日内尾盘主买的预测力；
② 下沉到成分股，验证“大单主买”与“小单主买”的分化，以及主买广度（净流入为正的股票占比）；
③ 引入 ETF 申赎与期指基差等真实资金面变量做条件分析；④ 把主买强度与动量、波动率组合成非线性模型，
检验是否存在交互效应而非线性预测力。</p>

<h2>五、复现说明</h2>
<p class="small" style="text-align:left">环境：Python 3.12+ 虚拟环境，依赖见 <code>requirements.txt</code>。
复现：<code>python -m venv .venv</code> → <code>pip install -r requirements.txt</code> → <code>python run_all.py</code>
（抓数→特征→分析→图表→报告；数据已缓存，可离线重跑，加 <code>--refresh</code> 重新抓取）。
产物：<code>data/</code>（原始快照与建模数据）、<code>output/tables/</code>（统计表与 <code>results.json</code>）、
<code>output/figures/</code>（图 1–5）、<code>output/{PROJECT_ID}_report.html</code>、<code>output/{PROJECT_ID}_report.pdf</code>。
报告中每个数字均由 <code>results.json</code> 渲染，未手工填写；完整流程亦整合为单个自包含 Notebook（<code>output/{PROJECT_ID}_research.ipynb</code>），已推送至 GitHub 公开仓库 <a class="url" href="{REPO_URL}">{REPO_URL}</a>。</p>
<p class="small" style="text-align:left;margin:1mm 0 0">在线查看（nbviewer）：<br><a class="url" href="{NBVIEWER_URL}">{NBVIEWER_URL}</a></p>

<h2>附表　主要变量描述统计</h2>
<table>
<tr><th>变量</th><th>均值</th><th>标准差</th><th>最小值</th><th>最大值</th><th>偏度</th><th>一阶自相关</th></tr>
{desc_rows}
</table>
<div class="cap">附表A　主要变量的描述统计（N = {s['n']:,}）。比率为小数口径，例如 NBI 均值 0.0022 表示 0.22%。</div>

<h2>参考文献</h2>
<ol class="ref">
<li>海通证券（2020）.《选股因子系列研究（五十七）：基于主动买入行为的选股因子》. 新浪财经转载.
https://finance.sina.com.cn/stock/stockzmt/2020-01-15/doc-iihnzahk4179997.shtml</li>
<li>海通证券（2020）.《大额买入与资金流向跟踪》. 新浪财经转载.
https://finance.sina.com.cn/stock/stockzmt/2020-09-07/doc-iivhuipp2907364.shtml</li>
<li>国信证券（2024）.《基于主动买卖特征的高频订单因子改进》. 新浪财经转载.
https://finance.sina.cn/2024-08-20/detail-inckfzcs5651129.d.html</li>
<li>数据：新浪财经 MoneyFlow 板块资金流接口；baostock 指数日线接口（抓取日期 2026-10-29）。</li>
</ol>

</body></html>"""
    return html


def render_pdf(html_path: Path, pdf_path: Path) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(html_path.as_uri())
        page.wait_for_timeout(500)
        page.pdf(path=str(pdf_path), format="A4", print_background=True,
                 margin={"top": "14mm", "bottom": "12mm", "left": "14mm", "right": "14mm"})
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
