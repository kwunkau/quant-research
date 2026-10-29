"""一键复现：抓数 → 特征 → 分析 → 图表 → 报告。

用法（需在已安装依赖的虚拟环境中运行）：
    python run_all.py            # 使用本地缓存，离线可跑
    python run_all.py --refresh  # 重新抓取全部原始数据
"""

from __future__ import annotations

import argparse
import sys
import time

MIN_PYTHON = (3, 12)


def check_env() -> None:
    """确认运行在具备依赖的虚拟环境中，避免误用全局解释器。"""
    if sys.version_info < MIN_PYTHON:
        sys.exit(f"[错误] 需要 Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+，当前为 {sys.version.split()[0]}")
    if sys.prefix == sys.base_prefix:
        sys.exit(
            "[错误] 当前解释器不在虚拟环境中，依赖可能缺失。\n"
            "       请先创建并激活虚拟环境：python -m venv .venv\n"
            "       再运行：.venv/bin/python run_all.py"
            "（Windows: .venv\\Scripts\\python run_all.py）"
        )
    print(f"[env] Python {sys.version.split()[0]}（虚拟环境）")


def main() -> None:
    parser = argparse.ArgumentParser(description="主动性买盘与沪深300次日收益研究：一键复现")
    parser.add_argument("--refresh", action="store_true", help="重新抓取原始数据（默认使用缓存）")
    args = parser.parse_args()

    check_env()

    from src.analysis import run as run_analysis
    from src.build_features import build_dataset
    from src.charts import build_all
    from src.make_report import build as build_report

    t0 = time.time()

    from src.fetch_data import build_raw

    if args.refresh:
        build_raw(force=True)
        print(f"[1/5] 数据重新抓取完成  {time.time() - t0:.1f}s")
    else:
        print("[1/5] 使用本地缓存数据（--refresh 可重新抓取）")

    data = build_dataset(force=True)
    print(f"[2/5] 特征构建完成  {data.shape[0]:,} 个交易日  {time.time() - t0:.1f}s")

    res = run_analysis()
    print(f"[3/5] 统计分析完成  共 {res['bh']['n_tests']} 项检验  {time.time() - t0:.1f}s")

    from src.analysis import decile_analysis

    grid = build_all(data, decile_analysis(data), res["decile"]["long_short"])
    print(f"[4/5] 图表生成完成  {grid.shape[0]}×{grid.shape[1]} 热力图  {time.time() - t0:.1f}s")

    pdf = build_report()
    print(f"[5/5] 报告生成完成  {pdf}  总耗时 {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
