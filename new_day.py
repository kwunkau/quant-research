"""生成新作业目录骨架（需求文档驱动流程的第一步）。

用法：
    python new_day.py 02 "主题名"
    python new_day.py 03            # 主题留空，稍后写进 需求.md

生成内容：kwunkau_dayNN/{需求/需求.md, README.md, .gitignore, run_all.py, src/config.py, src/pipeline.py}
以及空的 data/raw/、output/ 目录。

用户只需：① 填写 需求/需求.md；② 把研报、题目截图、参考代码等资料放进 需求/；
③ 对 Claude 说「执行 dayNN」。之后的全部工作按 CLAUDE.md 第 7 节完成。
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent

TEMPLATES: dict[str, str] = {
    "需求/需求.md": """# __DAY__｜需求文档

> 1. 填写下表（看不懂的字段可以留“待填写”，Claude 会先提问）；
> 2. 把所有资料（研报 PDF、题目截图、老师要求、参考代码、数据文件）直接放进本目录 `需求/`；
> 3. 对 Claude 说「执行 __DAY__」。其余步骤按 `CLAUDE.md` 第 7 节自动完成。
>
> `需求/` 下除本文件外默认**不推送**到公开仓库（第三方资料版权）；需要公开的文件请在「资料清单」里标“公开”。

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

（可自由补充：老师原话、想探索的方向、验收标准、参考作业等）

## 资料清单

（Claude 执行时自动扫描 `需求/` 并补全本表）

| 文件 | 用途 | 是否公开 |
|---|---|---|

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
| 需求文档 | `需求/需求.md` |

## 复现

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt      # Windows: .venv\\Scripts\\pip
python run_all.py
```

## 在线查看

nbviewer：`https://nbviewer.org/urls/raw.githack.com/kwunkau/quant-research/main/__DAY__/output/__DAY___research.ipynb`
""",
    ".gitignore": """data/processed/
output/figures/
output/tables/
__pycache__/
.venv/
.ipynb_checkpoints/

# 需求/ 下的参考资料默认不公开，只提交需求文档；需公开的文件用 !需求/<文件名> 放行
需求/*
!需求/需求.md
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
GITHUB_NB_URL = f"{REPO_URL}/blob/{GITHUB_BRANCH}/{NB_PATH}"
# nbviewer 的 /github/ 路由常因 GitHub API 限流返回 503/404，/urls/ + CDN 更稳定；两条都写进报告
NBVIEWER_CANONICAL = (f"https://nbviewer.org/github/{GITHUB_USER}/{GITHUB_REPO}"
                      f"/blob/{GITHUB_BRANCH}/{NB_PATH}")
NBVIEWER_URL = (f"https://nbviewer.org/urls/raw.githack.com/{GITHUB_USER}/{GITHUB_REPO}"
                f"/{GITHUB_BRANCH}/{NB_PATH}")

# 中文字体：按顺序尝试（Windows / macOS / Colab 的文泉驿 / Noto），直接 addfont 绕过字体缓存
FONT_FILES = [
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/msyh.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]
FONT_NAMES = ["SimHei", "Microsoft YaHei", "PingFang SC", "WenQuanYi Zen Hei",
              "Noto Sans CJK SC"]


def ensure_dirs() -> None:
    for path in (DATA_RAW, DATA_PROCESSED, FIG_DIR, TABLE_DIR):
        path.mkdir(parents=True, exist_ok=True)


def setup_matplotlib() -> None:
    """统一中文字体与绘图风格。"""
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import font_manager, rcParams

    for path in FONT_FILES:
        if Path(path).exists():
            font_manager.fontManager.addfont(path)
    installed = {f.name for f in font_manager.fontManager.ttflist}
    rcParams["font.sans-serif"] = [n for n in FONT_NAMES if n in installed] + ["DejaVu Sans"]
    rcParams["axes.unicode_minus"] = False
    rcParams["savefig.dpi"] = 160
''',
    "src/pipeline.py": '''"""作业主流程：按 需求.md 实现数据抓取 → 特征 → 分析 → 图表 → 报告。"""

from __future__ import annotations


def run() -> dict:
    raise NotImplementedError(
        "本作业尚未实现。请先完善 需求/需求.md，再执行 `执行 __DAY__` 让 Claude 补全。"
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

EMPTY_DIRS = ["data/raw", "output", "需求"]


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
    print(f"下一步：填写 {target.name}/需求/需求.md，把资料放进 {target.name}/需求/，"
          f"然后说「执行 {target.name.removeprefix('kwunkau_')}」")


if __name__ == "__main__":
    main()
