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
| 需求与资料 | `需求/需求.md` + `需求/` 下参考资料（资料默认不公开） |

- Colab 上的文件名与本地保持一致（上传后重命名）。
- 报告标题页、README、Notebook 首行统一标注作业编号（如 `kwunkau_day01`）。
- 新增作业按已有最大编号顺延，不复用、不跳号。
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

## 6. 作业提交（GitHub 公开仓库 + nbviewer）

提交三件套：

1. `output/kwunkau_dayNN_report.pdf`
2. **nbviewer 链接**（渲染已执行 Notebook，只读在线查看）
3. `src/` 工程代码（权威实现，可命令行复现）

### 6.1 仓库约定

- 所有作业共用一个**公开**仓库：`github.com/kwunkau/quant-research`，主分支 `main`。
  私有仓库 nbviewer 读不到，必须 public。
- 仓库根目录 = 项目根 `021量化研究/`，各次作业放在 `kwunkau_dayNN/` 子目录下。
- 链接只在 `src/config.py` 维护 `GITHUB_USER` / `GITHUB_REPO` / `GITHUB_BRANCH` 三项，
  其余（仓库地址、nbviewer 地址）由 `PROJECT_ID` 自动推导，报告里禁止手写 URL。

### 6.2 推送流程（gh CLI 已登录，可整套脚本化）

1. 项目根执行 `git init -b main`（仅首次）。
2. `.gitignore`：忽略 `.venv/`、`__pycache__/`、`data/processed/`、`output/figures/`、`output/tables/`、`需求/*`（放行 `需求/需求.md`）；
   **保留** `data/raw/`、报告 PDF/HTML、Notebook、`results.json`。
3. `git add -A && git commit`。
4. 首次建仓：`gh repo create quant-research --public --source=. --remote=origin --push`；后续：`git push`。
5. 链接推导：
   - nbviewer：`https://nbviewer.org/github/<user>/<repo>/blob/<branch>/<PROJECT_ID>/output/<PROJECT_ID>_research.ipynb`
   - raw 校验：`https://raw.githubusercontent.com/<user>/<repo>/<branch>/<同上路径>`
6. 重新生成报告（链接写入 PDF「复现说明」），再提交推送一次，保证仓库内容与 PDF 一致。

### 6.3 链接验收标准

- `raw.githubusercontent.com` 返回 200，且文件体积与本机 `.ipynb` 一致。
- nbviewer 返回 200，页面能看到标题与图表（空输出 = 没推执行结果，重跑后再推）。
- nbviewer `/github/` 路由常因 GitHub API 限流返回 503/404：主链接用 `/urls/raw.githack.com/...`，
  `/github/` 直连与 GitHub 原生视图作为备选一并写入报告（`config.py` 已推导三条）。
- **推送前必须执行过 Notebook**，图表、表格、数字已内嵌；空输出直接推送视为不合格。

### 6.4 Notebook 要求

- **首个代码单元自适应环境**：检测是否在云端运行时，按需安装依赖与中文字体；本地运行直接跳过。
- **不依赖本机资源**：无绝对路径、无本地缓存假设、无 token/密钥、无本机代理。
- **数据获取有降级**：优先读 `data/raw/` 快照 → 无快照则联网抓取 → 失败时抛出带
  「上传 CSV 后重跑」提示的明确异常。
- **输出干净**：单元格输出中不得出现本机路径、用户名、内网地址；图片内嵌在 `.ipynb` 中。
- **与报告一致**：关键数字必须与 `results.json` 一致。

### 6.5 备选方式

Gitee 镜像（国内访问更快）、Kaggle Notebooks 可作为备选，需在 README 注明。

## 7. 多日作业流程（需求文件夹驱动）

### 7.1 用户只做三件事

```bash
python new_day.py 03 "主题名"      # ① 生成 kwunkau_day03/（含空的 需求/ 文件夹）
```

② 填写 `kwunkau_day03/需求/需求.md`，并把**全部资料**（研报 PDF、题目截图、老师原话、参考代码、数据文件）
直接丢进 `kwunkau_day03/需求/`；③ 对 Claude 说「执行 day03」。之后不再需要逐项确认。

脚手架生成：`需求/需求.md`、`README.md`、`.gitignore`、`run_all.py`、`src/config.py`（PROJECT_ID、链接、
跨平台中文字体已配好）、`src/pipeline.py`，以及空的 `data/raw/`、`output/`。

### 7.2 唯一输入：`需求/` 文件夹

| 位置 | 说明 |
|---|---|
| `需求/需求.md` | 字段表（见下），随仓库公开 |
| `需求/*` 其它文件 | 参考资料；**默认不推送**（`.gitignore` 已排除），需公开的在「资料清单」标“公开”并在 `.gitignore` 放行 |

`需求.md` 字段固定：研究主题 / 研究问题 / 数据要求 / 指标与方法（可留空） / 交付要求 / 特殊约束 /
状态（`待执行`→`执行中`→`已完成`）/ 交付链接 / 更新时间 / 详细说明 / **资料清单** / 变更记录（追加式）。

### 7.3 执行契约（「执行 dayNN」后按顺序推进）

1. **读需求**：读 `需求/需求.md` 与 `需求/` 下全部资料（PDF 抽文本、图片直接看），补全「资料清单」；
   字段有歧义时提出不超过 3 个问题，其余按本文件默认规范处理；状态改为 `执行中`。
2. **抽取对照基准**：资料里的原文数字（研报收益、回撤、示例日期与取值）写进代码常量
   （如 `REPORT_REF`）并进入 `results.json`，报告只引用常量，不在正文手抄。
3. **数据探针**：先验证接口能取到所需历史长度与字段，再动手；不足则如实写入需求与报告。
4. **实现**：`src/` 按职责拆分；`run_all.py` 一条命令跑完 抓数 → 特征 → 分析 → 图表 → 报告 → Notebook。
5. **自检**（见 7.4，全部通过才进入下一步）。
6. **推送**：按第 6 节提交推送，验证链接后回填 `需求.md`、README、报告，再生成并推送一次。
7. **收尾**：状态改为 `已完成`，变更记录追加一条，回报：链接、核心结论（3–5 条）、未复现/不显著项。

### 7.4 交付前自检清单

- [ ] `run_all.py` 从缓存全流程跑通，Notebook 已执行、无报错单元、图片已内嵌。
- [ ] 报告 / Notebook / 附加页面中的数字全部由 `results.json` 渲染；`grep` 正文模板无手写百分比。
- [ ] 结论段的每个判断（“高于/低于”“领先”“复现/未复现”）都能在 `results.json` 中找到对应数字且方向一致；
      Notebook 结论单元由代码生成，不写死 markdown。
- [ ] 时间序列计算用**完整日期索引**定位（先过滤再 `get_loc` 后 `iloc` 原表会错位）；
      收益类计算用复权价格或涨跌幅累乘，不用不复权收盘价（ETF 份额折算会产生假跳空）。
- [ ] 回测“持仓”“实际成交”与“信号排名”分开表述，持仓以引擎记录为准。
- [ ] PDF 页数符合要求、无方框字；交付物无本机路径/用户名/代理（`grep -iE "Users|Administrator|:\\"`）。
- [ ] `requirements.txt` 版本与 venv 中实际安装版本一致（`pip freeze` 对照）。
- [ ] `需求/` 下第三方资料未被 `git add`（`git status` 确认）。

### 7.5 约束

- 一次只执行一个作业目录，避免交叉污染数据与缓存。
- 需求变更只追加到「变更记录」，不改写历史条目。
- 附加产物（如一页图解）也必须放在 `src/` 并由 `run_all.py` 生成，不在作业根目录放临时脚本。
- 未在 `需求.md` 中明确的内容，按本文件其它章节的默认规范处理。
