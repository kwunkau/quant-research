"""kwunkau_day02 一键复现入口（需在已安装依赖的虚拟环境中运行）。"""

from __future__ import annotations

import sys
import time

MIN_PYTHON = (3, 12)


def check_env() -> None:
    if sys.version_info < MIN_PYTHON:
        sys.exit(f"[错误] 需要 Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+，当前为 {sys.version.split()[0]}")
    if sys.prefix == sys.base_prefix:
        sys.exit(
            "[错误] 当前解释器不在虚拟环境中，依赖可能缺失。\n"
            "       请先创建并激活虚拟环境：python -m venv .venv\n"
            "       再运行：.venv/bin/python run_all.py"
            "（Windows: .venv\\Scripts\\python run_all.py）"
        )


def main() -> None:
    check_env()
    from src.pipeline import run

    t0 = time.time()
    run()
    print(f"[done] 全流程完成  {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
