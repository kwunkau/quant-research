"""kwunkau_day02 一键复现：抓数 → 特征 → 流向图 → 回测 → 图表 → 报告 → Notebook。

用法（需在已安装依赖的虚拟环境中运行）：
    python run_all.py                 # 使用本地缓存，离线可跑
    python run_all.py --refresh       # 重新抓取原始数据并重算流向图
    python run_all.py --skip-notebook # 跳过 Notebook 生成与执行
"""

from __future__ import annotations

import argparse
import sys
import time

MIN_PYTHON = (3, 12)


def check_env() -> None:
    if sys.version_info < MIN_PYTHON:
        sys.exit(f"[错误] 需要 Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+，"
                 f"当前为 {sys.version.split()[0]}")
    if sys.prefix == sys.base_prefix:
        sys.exit(
            "[错误] 当前解释器不在虚拟环境中，依赖可能缺失。\n"
            "       请先创建并激活虚拟环境：python -m venv .venv\n"
            "       再运行：.venv/bin/python run_all.py"
            "（Windows: .venv\\Scripts\\python run_all.py）"
        )
    print(f"[env] Python {sys.version.split()[0]}（虚拟环境）")


def main() -> None:
    parser = argparse.ArgumentParser(description="行业资金流向图 ETF 复现与 5000 万模拟")
    parser.add_argument("--refresh", action="store_true", help="重新抓数并重算流向图")
    parser.add_argument("--skip-notebook", action="store_true", help="跳过 Notebook")
    args = parser.parse_args()

    check_env()
    t0 = time.time()

    from src.fetch_data import build_raw, fetch_etf_daily

    if args.refresh:
        daily, _ = build_raw(force=True)
        print(f"[1/7] 数据重新抓取完成  {time.time() - t0:.1f}s")
    else:
        daily = fetch_etf_daily()
        print(f"[1/7] 使用本地缓存  {len(daily):,} 行  {time.time() - t0:.1f}s")

    from src.build_features import build_dataset

    build_dataset(daily)
    print(f"[2/7] 特征构建完成  {time.time() - t0:.1f}s")

    from src.flowmap import run as run_flowmap

    fm = run_flowmap(force=args.refresh)
    print(f"[3/7] 资金流向图完成  {len(fm['errors'])} 日  {time.time() - t0:.1f}s")

    from src.analysis import run as run_analysis

    res = run_analysis()
    print(f"[4/7] 回测与统计完成  {time.time() - t0:.1f}s")

    from src.charts import build_all

    build_all()
    print(f"[5/7] 图表生成完成  {time.time() - t0:.1f}s")

    from src.make_report import build as build_report

    pdf = build_report()
    print(f"[6/7] 报告生成完成  {pdf}  {time.time() - t0:.1f}s")

    if not args.skip_notebook:
        from src.make_notebook import build as build_notebook

        nb = build_notebook()
        print(f"[7/7] Notebook 完成  {nb}  {time.time() - t0:.1f}s")
    else:
        print("[7/7] 跳过 Notebook")

    perf = res["performance"]["net_composite_50m"]
    print(f"[done] 5000 万综合因子：年化 {perf['cagr']*100:.1f}%，"
          f"最大回撤 {perf['mdd']*100:.1f}%，"
          f"期末 {perf['final_value']/1e4:,.0f} 万元  "
          f"总耗时 {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
