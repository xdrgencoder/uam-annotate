# uam-annotate

**UAM CorpusTool 6 标注流水线 —— 完全命令行，绕过 GUI。**

直接读写 CT6 的二进制 `.idx` 与 `sentence.dat`，用 Python 批量落盘。内置两套方案：**及物性**（36 特征 / 5 系统，小句标注）与**评价理论**（UAM 自带 Appraisal_max，75 特征 / 31 系统，态度·介入·级差）。

An agent skill (WorkBuddy / Claude Code) for building, annotating, validating, merging and exporting UAM CorpusTool 6 projects without ever opening the GUI.

## 安装

这是一个**给 AI 智能体用的 skill**，不是 pip 包。装法只有一步：把仓库克隆进技能目录。对任何 Agent 都可以这样说：

> 克隆 https://github.com/xdrgencoder/uam-annotate 到你的技能目录

各端默认位置：

| 端 | 技能目录 |
|---|---|
| WorkBuddy | `~/.workbuddy/skills/uam-annotate` |
| Claude Code | `~/.claude/skills/uam-annotate` |

```bash
git clone https://github.com/xdrgencoder/uam-annotate.git ~/.workbuddy/skills/uam-annotate   # WorkBuddy
git clone https://github.com/xdrgencoder/uam-annotate.git ~/.claude/skills/uam-annotate      # Claude Code
```

已下载到本地的话，`cp -r uam-annotate ~/.workbuddy/skills/` 同样可以。

**装完要新开一轮对话**才会被加载——技能是启动时扫描的，当场不生效不代表没装上。

不想当 skill 用也行：`python scripts/make_project.py --help`，直接当普通脚本跑。

---

## 为什么需要它

UAM CorpusTool 6 只提供 GUI：建项目靠点、标注靠点、多章合并靠手动。一本书十几章、几千句的标注工作量，用鼠标点完基本不可能，而且中途无法版本管理、无法复核、无法批量统计。

这个包把整条链路搬到命令行：项目结构、标注数据、合并、统计全部由脚本生成，产物可以直接用 UAM 打开核对，也可以完全不打开 UAM 就拿到 `StatsResult.html` 口径的频次表。

## 两套方案

| `--scheme` | 层名 | 方案 | 标注单位 | 标注脚本 |
|---|---|---|---|---|
| `transitivity`（默认） | 及物性 | 36 特征 / 5 系统 / 4 层 | 小句 + 成分，**一段一特征** | `run_annotation.py` |
| `appraisal` | 评价 | 75 特征 / 31 系统 | 评价片段，**一段多特征**（每系统各一） | `run_appraisal.py` |

评价方案来自 UAM 自带的 `Resources/Schemes/Appraisal_max.xml`，是 Martin & White 评价理论的标准实现：态度（affect / judgement / appreciation）、介入（mono·hetero-glossic → contract/expand）、级差（force / focus）。

两套共用建项目、切句、二进制写法与复核件机制。差别在 `ANN` 结构与校验规则：

- 及物性「一段一特征」，多个特征靠拆段实现
- 评价「一段多特征」，一个跨度要同时落 `ATTITUDE-TYPE` + `EXPLICITNESS` + `ATTITUDE-POLARITY` 等系统，特征 OR 进同一张位图（75 特征 → 跨 2 个 64 位字）

两层产物都已在 UAM CorpusTool 6 里实机打开验证：及物性项目、评价项目（33 段 / 15 段）均能正常显示标注。

## 五步流程

| 步骤 | 脚本 | 作用 |
|---|---|---|
| 1. 建项目 | `make_project.py` | `.txt` / `.html` / `.doc` / `.docx` / `.rtf` / `.odt` → 标准 CT6 项目结构；`--scheme` 选方案 |
| 2. 写标注 | `ann_skeleton.py` + `run_annotation.py` / `run_appraisal.py` | 生成骨架 → 填 `ANN` → 干跑 → 落盘（带备份） |
| 3. 校验 | 内置于标注脚本 | 及物性六项结构校验；评价层另加四条特征组合校验 |
| 4. 合并成书 | `merge_book.py` + `verify_merge.py` | 多章项目 → 一个 text；再切回逐章零差异比对（`--layer` 切层） |
| 5. 导出统计 | `export_stats.py` / `export_appraisal_stats.py` | 复刻 UAM 的 `StatsResult.html`，可加 `--xlsx` / `--csv` |

配套：`doc_to_html.py`（Word/WPS → HTML，LibreOffice → pandoc → python-docx 三级降级）、`uamlib.py` / `annlib.py` / `apprlib.py`（`.idx` 二进制读写、定位核心、评价方案解析）、`selfcheck.py`（全链路自检）。

## 依赖

- Python 3.8+（开发与验证环境：3.13.14）
- `openpyxl`（仅 `--xlsx` 导出与复核表需要）
- 可选：LibreOffice 或 pandoc（仅 `--doc` 系列需要，两者有其一即可）

```bash
pip install openpyxl
```

## 快速开始

```bash
# 1. 建项目
python scripts/make_project.py --text 第三章.txt --out ./项目/第三章 --name 第三章

# 2. 生成标注骨架（第 0–40 句）
python scripts/ann_skeleton.py --project "./项目/第三章" --sent 0 40 --prefix c3_a --write

# 3. 干跑校验，再落盘
python scripts/run_annotation.py --project "./项目/第三章" --ann-prefix c3
python scripts/run_annotation.py --project "./项目/第三章" --ann-prefix c3 --write --out ./复核

# 4. 多章合并成书
python scripts/merge_book.py --base ./项目 --chapters 第一章 第二章 第三章 --out 全书
python scripts/verify_merge.py --base ./项目 --book 全书 --chapters 第一章 第二章 第三章

# 5. 导出统计
python scripts/export_stats.py --project "./项目/全书" --out . --xlsx
```

评价理论方案：

```bash
# 建项目 → 标注
python scripts/make_project.py --text 语料.txt --out ./项目/评价章 --name 评价章 --scheme appraisal
python scripts/run_appraisal.py --project "./项目/评价章" --ann-prefix ap --write --out ./复核

# 多章合并（--layer 切层）
python scripts/merge_book.py --base ./项目 --chapters 第一章 第二章 --out 评价全书 --layer 评价
python scripts/verify_merge.py --base ./项目 --book 评价全书 --chapters 第一章 第二章 --layer 评价

# 统计（31 张表，系统来自方案 xml）
python scripts/export_appraisal_stats.py --project "./项目/评价全书" --out . --xlsx --csv
```

## 标注数据格式

标注是纯数据文件，命名 `<prefix>_a.py`、`<prefix>_b.py`…，放在项目目录，每个导出 `ANN`：

```python
ANN = {
    0: [                                    # 句子下标，对应 sentence.dat，0 起
        ('The large, heavy flakes gathered high up in the sky', 'material',
         [('Actor', 'The large, heavy flakes'),
          ('location_place', 'high up in the sky')],
         [('each flake trying to deprive the earth of its first smatterings of green',
           'material', [('Actor', 'each flake'), ('Goal', 'the earth')])]),
    ],
}
```

- 小句元组 = `(原文片段, 过程类型, [成分…], [嵌套子句…])`
- 成分 = `(角色, 片段[, nth])`，`nth` 用于句内同片段多次出现
- 片段按空白归一匹配（换行、多空格不影响），但必须与原文同字

评价理论层换成特征列表，一段落多个系统的特征：

```python
ANN = {
    0: [('utterly boring',
         ['attitude', 'appreciation', 'reaction', 'quality',
          'negative-attitude', 'inscribed'])],
    1: [('Sadly',
         ['attitude', 'affect', 'authorial-evaluation', 'un/happiness',
          'misery/cheer', 'negative-attitude', 'inscribed'])],
}
```

写盘前会校验**入口条件是否闭合**：选了 `quality` 就必须同时给 `reaction`、`appreciation`、`attitude`；`attitude` 一旦出现，极性（`ATTITUDE-POLARITY`）与显性度（`EXPLICITNESS`）也各要一个。完整 31 系统树见 `references/appraisal.md`。

## 关键事实（跳过会踩坑）

| 事实 | 说明 |
|---|---|
| `.idx` 是二进制 | 6×uint32 头（含 `intsNeeded`）+ `;` 分隔特征表 + 每条 `16 + 8 × intsNeeded` 字节记录 |
| `sid` / `pid` 是 u16 | 单 text 上限 65,535 条记录，超了必须先拆 |
| 盒子标签只显示 `Clause` | 参与者/环境段必须写 `role` 字段，否则 UAM 只显示过程类型 |
| 一句可有多条 `pid=0` | 并列、非限定、从属小句都平铺，不是错误 |
| 每段只带一个特征 | 及物性按成分分段，feature pattern 退化为单特征 |
| 评价层一段多特征 | 一个跨度同时落多系统特征，OR 进同一张位图（可能跨多个 64 位字） |
| **位图高位字在前** | `bits = word[0] << 64 \| word[1]`。写反了 UAM 不报格式错，只在打开项目时抛 `list index out of range`；≤64 特征的方案两种顺序字节相同，看不出差别 |
| 换方案要换特征表 | 位图下标 = 特征表顺序，`uamlib.set_features()` 写读成对、用完还原 |
| `sentence.dat` 每句 8 字节 | 两个 uint32 起止；末句不推进 `start` 会重复末句 |
| 顶层小句按顺序定位 | 前一小句的 `end` 是下一句的搜索 `start` |
| 人名首字母不切句 | `U. Khurelsukh` / `I.K. Azizov` 已在切句器排除 |
| 覆盖率 95–97% 正常 | 及物性层；评价层天然只有 5–25%，低不是漏标 |

## 统计口径

及物性层与 UAM 完全一致：**% = N ÷ 段总数，不是 system 内占比**。`MENTAL-TYPE` / `RELATIONAL-TYPE` 是 `PROCESS-TYPE` 的子集，不参与 100% 相加。详见 `references/statistics.md`。

评价层的复核表按系统分组出频次与「占标注段」比例，不做 UAM 式 `StatsResult.html`。

## 自检

换机器、换 Python、改过脚本之后先跑：

```bash
python scripts/selfcheck.py          # 跑完删临时目录
python scripts/selfcheck.py --keep   # 保留产物以便查看
```

会在临时目录把两条链路都走一遍（及物性：建项目 → 骨架 → 标注落盘 → 合并 → 回比 → 统计；评价：建项目 → 多特征标注落盘 → 位图回读 → 合并 → 回比 → 统计），末尾打印 `PASS` 或失败项，共 21 项。

```
selfcheck · Python 3.13.14
  ✓ openpyxl 3.1.5
  ✓ 建项目 ch1 / ch2
  ✓ 生成骨架
  ✓ 干跑 ch1 / 写盘 ch1 / 写盘 ch2
  ✓ 两章 及物性.idx 已生成
  ✓ 合并全书
  ✓ 回比校验
  ✓ 统计导出
  ✓ 建项目 评价章 / 评价章2
  ✓ 评价落盘 / 评价章2 落盘
  ✓ 评价章 评价.idx 已生成
  ✓ 评价 idx 回读（76 特征 / 3 段，多特征位图）
  ✓ 合并评价全书
  ✓ 评价回比
  ✓ 评价统计导出
PASS
```

## 目录结构

```
uam-annotate/
├── SKILL.md                          # 技能说明（方案对照 + 五步流程 + 关键事实）
├── scripts/
│   ├── make_project.py               # 建项目（--scheme 选及物性/评价）
│   ├── doc_to_html.py                # Word/WPS → HTML
│   ├── ann_skeleton.py               # 生成 ANN 骨架（及物性）
│   ├── run_annotation.py             # 及物性：校验 + 落盘 + 复核件
│   ├── run_appraisal.py              # 评价：校验 + 落盘 + 复核件
│   ├── merge_book.py                 # 多章合并（--layer 切层）
│   ├── verify_merge.py               # 合并结果回比（--layer 切层）
│   ├── export_stats.py               # 统计导出（及物性 5 套系统）
│   ├── export_appraisal_stats.py     # 统计导出（方案驱动，评价 31 系统）
│   ├── uamlib.py                     # .idx / sentence.dat 读写 + 换特征表
│   ├── annlib.py                     # 及物性：片段定位与段落构建
│   ├── apprlib.py                    # 评价：方案解析、特征组合校验、位图落盘
│   └── selfcheck.py                  # 全链路自检（两条链路）
├── references/
│   ├── idx-format.md                 # 二进制格式细节
│   ├── annotation-conventions.md     # 及物性十条标注口径与争议判定
│   ├── appraisal.md                  # 评价 31 系统树、入口条件、四条校验、口径
│   └── statistics.md                 # N / % 定义与三种视图
└── assets/
    ├── scheme-transitivity.xml       # 及物性方案（36 特征 / 5 系统 / 4 层）
    └── scheme-appraisal.xml          # 评价方案（75 特征 / 31 系统，UAM Appraisal_max）
```

## 不适用

- UAM 的 UD 句法解析
- 多 text 对照
- 修改标注方案的特征集（方案按原样使用）

## 许可

未指定许可。如需复用或再分发，请先联系作者。
