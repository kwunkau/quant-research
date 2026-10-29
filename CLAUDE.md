# 021 量化研究 — 项目级约束

本目录下的每次作业放在 `kwunkau_dayNN/` 子目录（kwunkau_day01、kwunkau_day02…），
共享同一套运行环境与交付规范。以下约束对所有作业生效，优先级高于临时口头约定。

## 0. 交付物命名（强制）

所有产出统一以 `kwunkau_dayNN` 为标识，禁止出现 `report.pdf`、`research.ipynb` 这类无标识文件名：

| 对象 | 路径 |
|---|---|
| 作业目录 | `kwunkau_dayNN/`（NN 为两位数字） |
| 研究报告 | `output/kwunkau_dayNN_report.pdf`（同名 `.html`） |
| Notebook | `output/kwunkau_dayNN_research.ipynb`（统一生成在 output/ 下） |

- Colab 上的文件名与本地保持一致（上传后重命名）。
- 报告标题页、README、Notebook 首行统一标注作业编号（如 `kwunkau_day01`）。
- 新增作业从 `kwunkau_day02` 起顺延编号，不复用、不跳号。
- **不打包 zip**：代码随目录直接提交，或以仓库 / Colab 链接形式给出。
- Notebook 一律生成在 `output/` 下，不在项目根目录或其它子目录另建 .ipynb。

## 1. 交付物中不得出现本机环境信息

研究报告、README、Notebook、图表标题与复现说明中，**禁止**出现：

- 本机绝对路径（如 `E:\00Code\021量化研究\.venv`、`C:\Users\...`）
- 用户名、主机名、本地 venv 路径、代理地址
- 抓取时依赖本机网络环境的说明（可写"如接口不可用，使用随附数据快照"）

复现说明一律使用**通用命令**，假定读者自己的机器：

```bash
python -m venv .venv            # Python 3.12+
.venv/bin/pip install -r requirements.txt      # Windows: .venv\Scripts\pip
.venv/bin/python run_all.py
```

需要说明"共享环境"时，只写"项目使用 Python 3.12+ 虚拟环境隔离依赖"，不写具体盘符路径。

## 2. 运行环境

- 本地统一使用 Python 3.12+ 的项目级虚拟环境，依赖只装进 venv，不污染全局解释器。
- 代码需兼容 Python 3.10+，以保证在 **Google Colab 默认运行时**可直接运行。
- 每次作业的 `requirements.txt` 锁定**该作业实际使用的版本**；新增依赖追加安装并记录。
- 入口脚本可校验"当前解释器是否在虚拟环境中"（`sys.prefix != sys.base_prefix`）与版本号，
  但校验失败时给出**通用**提示，不打印本机路径。

## 3. 数据与可复现性

- 原始数据抓取后落盘缓存（`data/raw/`），支持离线重跑；`--refresh` 才重新抓取。
- 报告中每个数字必须来自脚本实际计算并写入的结果文件（如 `results.json`），**禁止手填**。
- 若数据源历史长度不足，必须在报告中如实说明原因与实际研究区间。
- 抓取失败要有重试与降级方案，并在 README 注明数据快照的抓取日期。
- **Colab 场景**：运行时没有本地缓存，抓取逻辑必须能直接联网取数；若目标网络不可达
  （如海外机器连不上国内行情端口），必须给出明确提示——"把 `data/raw/*.csv` 上传到同路径后重跑"，
  禁止静默失败或返回空表继续计算。

## 4. 代码结构

- `src/` 按职责拆分（config / fetch / features / analysis / charts / report），单一职责，禁止重复逻辑。
- `run_all.py` 为唯一入口，一条命令跑完全流程：抓数 → 特征 → 分析 → 图表 → 报告。
- 第三方库缺失时的替代实现（如手写 HAC 标准误）优先于新增重量级依赖。

## 5. 报告规范

- PDF 页数 2–5 页（A4），中文不出现方框字，图表不跨页断裂。
- 结构固定：研究思路 → 数据与方法 → 研究结果 → 结论与思考 → 复现说明 → 参考文献。
- 结论必须与统计输出一致；不显著就写不显著，不做选择性汇报。

## 6. 作业提交（Google Colab 为标准方式）

提交三件套：

1. `report.pdf`
2. **Google Colab Notebook 链接**（自包含单文件，`notebooks/*.ipynb`）
3. `src/` 工程代码（权威实现，可维护、可命令行复现）

### 6.1 Colab 链接的交付标准

- 链接必须来自 colab.research.google.com，分享权限设为「**任何拥有链接的人可查看**」；
  需要评审直接运行时给「编辑者」，并确认他人打开后「全部运行」可跑通。
- 链接写入 `README.md` 与报告「复现说明」一节，格式：
  `Notebook（Colab）：https://colab.research.google.com/drive/<fileId>`

### 6.2 Notebook 必须满足的 Colab 要求

- **首个代码单元识别环境**：`IN_COLAB = "google.colab" in sys.modules`，为真时自动
  `!pip -q install <依赖>` 与 `!apt-get -qq install -y fonts-wqy-zenhei`，并用
  `font_manager.fontManager.addfont(...)` 注册中文字体（否则图中中文是方框）。
- **不依赖本机资源**：无绝对路径、无本地缓存假设、无 token/密钥、无本机代理。
- **数据获取有降级**：优先读 `data/raw/` 快照 → 无快照则联网抓取 → 抓取失败时抛出带
  「上传 CSV 后重跑」提示的明确异常。
- **输出干净**：单元格输出中不得出现本机路径、用户名、内网地址；图片内嵌在 `.ipynb` 中。
- **与报告一致**：Notebook 的关键数字必须与 `results.json` 一致（可在末尾加一致性校验单元）。
- 提交前在 **全新 Colab 运行时**（不是复用已有会话）完整跑一遍，确认无报错、无警告性缺字。

### 6.3 备选方式

GitHub + nbviewer、Kaggle Notebooks 仅作为备选，不作为提交标准；若使用需在 README 注明原因。
