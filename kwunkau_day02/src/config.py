"""kwunkau_day02 全局配置：路径、区间、分享链接。"""

from pathlib import Path

PROJECT_ID = "kwunkau_day02"

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
