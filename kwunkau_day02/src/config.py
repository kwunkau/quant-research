"""kwunkau_day02 全局配置：路径、ETF 池、区间、回测与成本参数。"""

from pathlib import Path

PROJECT_ID = "kwunkau_day02"

ROOT = Path(__file__).resolve().parents[1]
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
OUTPUT = ROOT / "output"
FIG_DIR = OUTPUT / "figures"
TABLE_DIR = OUTPUT / "tables"

# 研究区间：2020 年起（2019 年下半年满足 120 个交易日的行业 ETF 不足 11 只）
START_DATE = "2020-01-02"
END_DATE = "2026-10-30"
FETCH_START = "2019-01-01"  # 多留一年用于上市天数与 ADV 预热

# 信号池：纯行业/主题 ETF（宽基与红利不进选股域）
ETF_UNIVERSE = [
    ("sh.512480", "半导体ETF", "半导体"),
    ("sh.512880", "证券ETF", "证券"),
    ("sh.512800", "银行ETF", "银行"),
    ("sh.512690", "酒ETF", "食品饮料"),
    ("sz.159928", "消费ETF", "消费"),
    ("sh.512170", "医疗ETF", "医疗"),
    ("sh.512010", "医药ETF", "医药"),
    ("sh.512660", "军工ETF", "军工"),
    ("sh.512400", "有色金属ETF", "有色金属"),
    ("sh.515880", "通信ETF", "通信"),
    ("sh.512980", "传媒ETF", "传媒"),
    ("sh.512200", "房地产ETF", "房地产"),
    ("sh.515220", "煤炭ETF", "煤炭"),
    ("sh.515790", "光伏ETF", "光伏"),
    ("sh.515030", "新能源车ETF", "新能源车"),
    ("sz.159869", "游戏ETF", "游戏"),
    ("sh.516160", "新能源ETF", "新能源"),
    ("sz.159611", "电力ETF", "电力"),
]

# 仅作对照/防御参照，不参与排名
REFERENCE_ETFS = [
    ("sh.510880", "红利ETF"),
    ("sz.159949", "创业板50ETF"),
]

MIN_HISTORY_DAYS = 120
ADV_WINDOW = 20
ADV_MIN_YI = 2.0  # 可执行池门槛：ADV20 ≥ 2 亿元

# 因子与组合
W_MAIN = 20
W_GRID = [15, 20, 25]
TOP_N = 5
TOP_N_GRID = [3, 5, 8]

# 5000 万模拟与容量
CAPITAL = 50_000_000
AUM_GRID = [10_000_000, 30_000_000, 50_000_000, 100_000_000, 200_000_000, 500_000_000]
LOT_SIZE = 100

# 交易成本（单边）
COMMISSION_BPS = 1.0
HALF_SPREAD_BPS = 2.0
IMPACT_BPS_AT_5PCT = 10.0  # 参与率 5% 时的冲击成本
MAX_PARTICIPATION = 0.05
IMPACT_GRID = [5.0, 10.0, 20.0]
COMMISSION_GRID = [0.5, 1.0, 2.0]

# 新浪单只 ETF 资金流覆盖起点
FLOW_START = "2025-02-06"

# 统计
BOOTSTRAP_N = 5000
BOOTSTRAP_BLOCK = 8  # 周收益，块长 8 周
SEED = 20261031

# 在线分享：仓库固定，路径由 PROJECT_ID 推导
GITHUB_USER = "kwunkau"
GITHUB_REPO = "quant-research"
GITHUB_BRANCH = "main"

NB_PATH = f"{PROJECT_ID}/output/{PROJECT_ID}_research.ipynb"
REPO_URL = f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}"
NBVIEWER_URL = (f"https://nbviewer.org/github/{GITHUB_USER}/{GITHUB_REPO}"
                f"/blob/{GITHUB_BRANCH}/{NB_PATH}")
GITHUB_NB_URL = f"{REPO_URL}/blob/{GITHUB_BRANCH}/{NB_PATH}"

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
    rcParams["figure.dpi"] = 110
    rcParams["savefig.dpi"] = 160
    rcParams["axes.grid"] = True
    rcParams["grid.alpha"] = 0.25
    rcParams["axes.spines.top"] = False
    rcParams["axes.spines.right"] = False
