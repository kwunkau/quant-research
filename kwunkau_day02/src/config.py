"""kwunkau_day02 全局配置：路径、ETF 池、区间、回测与成本参数。"""

import subprocess
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

# 研报 2026 案例的三个示例日（流向图、广度对照、复盘图共用）
KEY_DATES = ["2026-06-24", "2026-06-30", "2026-07-06"]

# 行业口径复现（新浪行业板块资金流，补 Wind 主动买卖金额的缺口）
IND_START = "2018-12-31"          # 与研报回测起点一致
IND_FETCH_START = "2018-06-01"    # 多留半年做 W 日平滑预热
IND_REPORT_END = "2026-07-31"     # 研报回测终点，用于同区间对照
IND_W_GRID = [20, 21, 22, 23, 24]  # 研报“W 取 20 至 24”的 5 组回测
IND_SEMI = "电子器件"              # 与研报“电子”最接近的新浪行业
IND_TELECOM = "电子信息"           # 新浪口径无独立“通信设备”，用电子信息对照

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
GITHUB_NB_URL = f"{REPO_URL}/blob/{GITHUB_BRANCH}/{NB_PATH}"



NB_REL = f"output/{PROJECT_ID}_research.ipynb"  # 相对作业目录


def _git(*args: str) -> subprocess.CompletedProcess | None:
    """在作业目录执行 git；无 git 或不在仓库中（如 Colab 直接上传）时返回 None。"""
    try:
        out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                             text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return None if "not a git repository" in out.stderr else out


def _nb_commit() -> str | None:
    """最近一次提交 Notebook 的 commit SHA；无 git / 未提交时返回 None（回退到分支链接）。"""
    out = _git("log", "-1", "--format=%H", "--", NB_REL)
    return (out.stdout.strip() or None) if out else None


def nb_link_problem() -> str | None:
    """锁定链接是否指向本地这版 Notebook 且已推送；有问题返回原因，没问题或无法校验返回 None。"""
    if _git("rev-parse", "--git-dir") is None:
        return None
    if NB_COMMIT is None:
        return "Notebook 尚未提交"
    if _git("diff", "--quiet", NB_COMMIT, "--", NB_REL).returncode != 0:
        return f"本地 Notebook 与提交 {NB_COMMIT[:7]} 不一致（重跑后尚未提交）"
    if _git("merge-base", "--is-ancestor", NB_COMMIT,
            f"origin/{GITHUB_BRANCH}").returncode != 0:
        return f"提交 {NB_COMMIT[:7]} 尚未推送到 origin/{GITHUB_BRANCH}"
    return None


# nbviewer 的 /github/ 路由依赖 GitHub API：分支目录会被服务端旧缓存卡住（404 “not found
# among N files”），API 限流时返回 503。主链接走 /urls/ + rawcdn.githack（不经 GitHub API），
# 并锁定到 Notebook 所在提交，内容不随后续推送变化；/github/ 直连与 GitHub 原生视图作备选。
NB_COMMIT = _nb_commit()
NBVIEWER_BRANCH_URL = (f"https://nbviewer.org/urls/raw.githack.com/{GITHUB_USER}/{GITHUB_REPO}"
                       f"/{GITHUB_BRANCH}/{NB_PATH}")
NBVIEWER_URL = (f"https://nbviewer.org/urls/rawcdn.githack.com/{GITHUB_USER}/{GITHUB_REPO}"
                f"/{NB_COMMIT}/{NB_PATH}" if NB_COMMIT else NBVIEWER_BRANCH_URL)
NBVIEWER_CANONICAL = (f"https://nbviewer.org/github/{GITHUB_USER}/{GITHUB_REPO}"
                      f"/blob/HEAD/{NB_PATH}")
COLAB_URL = (f"https://colab.research.google.com/github/{GITHUB_USER}/{GITHUB_REPO}"
             f"/blob/{GITHUB_BRANCH}/{NB_PATH}")

# 中文字体：按顺序尝试（Windows / macOS / Colab 安装的文泉驿 / Noto），都不存在时按字体名回退
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
    """统一中文字体与绘图风格。

    直接 addfont 字体文件，不依赖 matplotlib 字体缓存
    （Colab 上 apt 新装的字体不会出现在已有缓存里，否则会出现方框字）。
    """
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import font_manager, rcParams

    for path in FONT_FILES:
        if Path(path).exists():
            font_manager.fontManager.addfont(path)
    installed = {f.name for f in font_manager.fontManager.ttflist}
    rcParams["font.sans-serif"] = [n for n in FONT_NAMES if n in installed] + ["DejaVu Sans"]
    rcParams["axes.unicode_minus"] = False
    rcParams["figure.dpi"] = 110
    rcParams["savefig.dpi"] = 160
    rcParams["axes.grid"] = True
    rcParams["grid.alpha"] = 0.25
    rcParams["axes.spines.top"] = False
    rcParams["axes.spines.right"] = False
