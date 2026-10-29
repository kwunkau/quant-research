"""全局配置：路径、研究区间、数据源与绘图样式。"""

from pathlib import Path

PROJECT_ID = "kwunkau_day01"

ROOT = Path(__file__).resolve().parents[1]
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
OUTPUT = ROOT / "output"
FIG_DIR = OUTPUT / "figures"
TABLE_DIR = OUTPUT / "tables"

# 研究区间：2012 年至今。抓取时向前多留一天用于计算首日收益。
START_DATE = "2012-01-01"
END_DATE = "2026-10-29"
FETCH_START = "2011-12-01"

BAOSTOCK_CODE = "sh.000300"
SINA_API_BASE = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
SINA_FLOW_URL = SINA_API_BASE + "Money" + "Flow" + ".ssl_bkzj_zjlrqs"

FONT_PATH = "C:/Windows/Fonts/simhei.ttf"
DPI = 160
SEED = 20261029

# 在线分享：GitHub 公开仓库 + nbviewer（报告「复现说明」自动引用这些链接）
GITHUB_USER = "kwunkau"
GITHUB_REPO = "quant-research"
GITHUB_BRANCH = "main"

# 仓库根 = 项目根，作业目录名即 PROJECT_ID
NB_PATH = f"{PROJECT_ID}/output/{PROJECT_ID}_research.ipynb"
REPO_URL = f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}"
NBVIEWER_URL = (f"https://nbviewer.org/github/{GITHUB_USER}/{GITHUB_REPO}"
                f"/blob/{GITHUB_BRANCH}/{NB_PATH}")

# 主检验族：BH 多重检验校正覆盖的 p 值
BOOTSTRAP_N = 500
BOOTSTRAP_BLOCK = 20


def ensure_dirs() -> None:
    """创建全部输出目录（幂等）。"""
    for path in (DATA_RAW, DATA_PROCESSED, FIG_DIR, TABLE_DIR):
        path.mkdir(parents=True, exist_ok=True)


def setup_matplotlib() -> None:
    """统一中文字体与绘图风格。"""
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import font_manager, rcParams

    if Path(FONT_PATH).exists():
        font_manager.fontManager.addfont(FONT_PATH)
    else:
        # 非 Windows 环境按可用字体回退
        for name in ["SimHei", "Microsoft YaHei", "WenQuanYi Zen Hei",
                     "Noto Sans CJK SC", "AR PL UMing CN"]:
            if any(f.name == name for f in font_manager.fontManager.ttflist):
                rcParams["font.sans-serif"] = [name]
                break
    rcParams["axes.unicode_minus"] = False
    rcParams["figure.dpi"] = 110
    rcParams["savefig.dpi"] = DPI
    rcParams["axes.grid"] = True
    rcParams["grid.alpha"] = 0.25
    rcParams["axes.spines.top"] = False
    rcParams["axes.spines.right"] = False
