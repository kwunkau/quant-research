"""生成新作业目录骨架（需求文档驱动流程的第一步）。

用法：
    python new_day.py 02 "主题名"
    python new_day.py 03            # 主题留空，稍后写进 需求.md

生成内容：kwunkau_dayNN/{需求.md, README.md, .gitignore, run_all.py, src/config.py, src/pipeline.py}
以及空的 data/raw/、output/ 目录。之后的全部工作由 Claude 读取 需求.md 后完成。
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent

TEMPLATES: dict[str, str] = {
    "需求.md": """# __DAY__｜需求文档

> 把本次作业的完整要求写在下面。写完后告诉 Claude「执行 __DAY__」，
> 其余步骤按其项目约束（`CLAUDE.md` 第 7 节）自动完成。

| 字段 | 内容 |
|---|---|
| 研究主题 | __TOPIC__ |
| 研究问题 | 待填写（要验证的假设 / 要回答的问题） |
| 数据要求 | 待填写（数据源、区间、频率、口径） |
| 指标与方法 | 待填写（可留空，由 Claude 选型并说明理由） |
| 交付要求 | 报告 2–5 页；Notebook 自包含；图表 ≥ 3 张（默认值，可改） |
| 特殊约束 | 待填写（命名、风格、必须包含或排除的内容） |
| 状态 | 待执行 |
| 交付链接 | 待生成 |
| 更新时间 | __TODAY__ |

## 详细说明

（可自由补充：参考文献、想探索的方向、验收标准、参考作业等）

## 变更记录

- __TODAY__ 初始化需求文档
""",
    "README.md": """# __DAY__

__TOPIC__

## 交付物

| 对象 | 路径 |
|---|---|
| 报告 | `output/__DAY___report.pdf` |
| Notebook | `output/__DAY___research.ipynb` |
| 需求文档 | `需求.md` |

## 复现

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt      # Windows: .venv\\Scripts\\pip
python run_all.py
```

## 在线查看

nbviewer：`https://nbviewer.org/github/kwunkau/quant-research/blob/main/__DAY__/output/__DAY___research.ipynb`
""",
    ".gitignore": """data/processed/
output/figures/
output/tables/
__pycache__/
.venv/
""",
    "src/__init__.py": '"""__DAY__ 源码包。"""\n',
    "src/config.py": '''"""__DAY__ 全局配置：路径、区间、分享链接。"""

from pathlib import Path

PROJECT_ID = "__DAY__"

ROOT = Path(__file__).resolve().parents[1]
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
OUTPUT = ROOT / "output"
FIG_DIR = OUTPUT / "figures"
TABLE_DIR = OUTPUT / "tables"

# 研究区间（按需求文档填写）
START_DATE = "2012-01-01"
END_DATE = "2026-10-29"

# 在线分享：仓库固定，路径由 PROJECT_ID 推导
GITHUB_USER = "kwunkau"
GITHUB_REPO = "quant-research"
GITHUB_BRANCH = "main"

NB_PATH = f"{PROJECT_ID}/output/{PROJECT_ID}_research.ipynb"
REPO_URL = f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}"
NBVIEWER_URL = (f"https://nbviewer.org/github/{GITHUB_USER}/{GITHUB_REPO}"
                f"/blob/{GITHUB_BRANCH}/{NB_PATH}")

FONT_PATH = "C:/Windows/Fonts/simhei.ttf"


def ensure_dirs() -> None:
    for path in (DATA_RAW, DATA_PROCESSED, FIG_DIR, TABLE_DIR):
        path.mkdir(parents=True, exist_ok=True)


def setup_matplotlib() -> None:
    """统一中文字体与绘图风格。"""
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import font_manager, rcParams

    if Path(FONT_PATH).exists():
        font_manager.fontManager.addfont(FONT_PATH)
        rcParams["font.sans-serif"] = ["SimHei"]
    else:
        for name in ["Microsoft YaHei", "WenQuanYi Zen Hei", "Noto Sans CJK SC"]:
            if any(f.name == name for f in font_manager.fontManager.ttflist):
                rcParams["font.sans-serif"] = [name]
                break
    rcParams["axes.unicode_minus"] = False
    rcParams["savefig.dpi"] = 160
''',
    "src/pipeline.py": '''"""作业主流程：按 需求.md 实现数据抓取 → 特征 → 分析 → 图表 → 报告。"""

from __future__ import annotations


def run() -> dict:
    raise NotImplementedError(
        "本作业尚未实现。请先完善 需求.md，再执行 `执行 __DAY__` 让 Claude 补全。"
    )
''',
    "run_all.py": '''"""__DAY__ 一键复现入口（需在已安装依赖的虚拟环境中运行）。"""

from __future__ import annotations

import sys
import time

MIN_PYTHON = (3, 12)


def check_env() -> None:
    if sys.version_info < MIN_PYTHON:
        sys.exit(f"[错误] 需要 Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+，当前为 {sys.version.split()[0]}")
    if sys.prefix == sys.base_prefix:
        sys.exit(
            "[错误] 当前解释器不在虚拟环境中，依赖可能缺失。\\n"
            "       请先创建并激活虚拟环境：python -m venv .venv\\n"
            "       再运行：.venv/bin/python run_all.py"
            "（Windows: .venv\\\\Scripts\\\\python run_all.py）"
        )


def main() -> None:
    check_env()
    from src.pipeline import run

    t0 = time.time()
    run()
    print(f"[done] 全流程完成  {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
''',
}

EMPTY_DIRS = ["data/raw", "output"]


def scaffold(day: str, topic: str) -> Path:
    name = f"kwunkau_day{day}"
    target = ROOT / name
    if target.exists():
        raise SystemExit(f"[错误] 目录已存在：{target}")

    today = date.today().isoformat()
    for rel, text in TEMPLATES.items():
        path = target / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            text.replace("__DAY__", name).replace("__TOPIC__", topic).replace("__TODAY__", today),
            encoding="utf-8",
        )
    for rel in EMPTY_DIRS:
        (target / rel).mkdir(parents=True, exist_ok=True)

    (target / "requirements.txt").write_text(
        "pandas>=2.2\nnumpy>=2.0\nmatplotlib>=3.8\nscipy>=1.16\nstatsmodels>=0.14\n"
        "requests>=2.32\n",
        encoding="utf-8",
    )
    return target


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit('用法：python new_day.py <编号，如 02> ["主题"]')
    day = sys.argv[1].zfill(2)
    topic = sys.argv[2] if len(sys.argv) > 2 else "待填写"
    target = scaffold(day, topic)
    print(f"[created] {target}")
    print("下一步：在 需求.md 中填写要求，然后说「执行 " + target.name + "」")


if __name__ == "__main__":
    main()
