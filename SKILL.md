---
name: uam-annotate
description: Build, annotate, validate, merge and export UAM CorpusTool 6 projects entirely from the command line, bypassing the GUI by writing the binary .idx format directly. One project holds several layers at once (transitivity + attitude + engagement + graduation), each with its own scheme and idx. Use when a task involves UAM / UAM CorpusTool / .ct3 / 及物性 / transitivity / 评价理论 / appraisal / attitude / engagement / graduation, multi-layer annotation, clause annotation of English corpus texts, converting .doc or .txt chapters into UAM projects, merging chapter projects into one book text, or reproducing UAM's Statistics / StatsResult.html output. Triggered by 语料标注、及物性分析、过程类型、参与者角色、环境成分、评价标注、态度资源、介入、级差、多层标注、UAM 项目、多章合并、统计导出.
agent_created: true
---

# UAM CorpusTool 6 标注流水线

全流程绕过 GUI：直接读写 CT6 的二进制 `.idx` 与 `sentence.dat`，用 Python 批量落盘。
适用英文叙事/新闻语料（单 text），内置五套方案，可在一个项目里叠成多层。

## 一个项目，多个层

**一个项目 = 一段语料 + 多个标注层**（不是「一个项目一个方案」）。各层共用同一份
`Text-1.txt` 与 `sentence.dat`，在 UAM 的 Layer 面板里切换查看，各自标注、各自统计。

```
项目/第三章/
├── 第三章.ct3                       ← 里面并列 4 个 <layer>
├── Schemes/及物性.xml 态度.xml 介入.xml 级差.xml
├── Corpus/Texts/Text-1.txt          ← 一份正文，四层共用
└── Annotations/Texts/Text-1.txt/
    ├── sentence.dat                 ← 一份切句，四层共用
    └── 及物性.idx 态度.idx 介入.idx 级差.idx
```

`make_project.py` 默认就建这四层；每层先写一个 0 条记录的空 idx，UAM 打开即为空层，可直接标。

## 五套方案

| 方案键 | 默认层名 | 规模 | 标注单位 | 脚本 |
|---|---|---|---|---|
| `transitivity` | 及物性 | 36 特征 / 5 系统 | 小句 + 成分，**一段一特征** | `run_annotation.py` |
| `attitude` | 态度 | 36 特征 / 13 系统 | 评价片段，**一段多特征** | `run_appraisal.py` |
| `engagement` | 介入 | 19 特征 / 8 系统 | 同上 | `run_appraisal.py` |
| `graduation` | 级差 | 22 特征 / 10 系统 | 同上 | `run_appraisal.py` |
| `appraisal` | 评价 | 75 特征 / 31 系统（= 上面三支合并，UAM 自带 Appraisal_max） | 同上 | `run_appraisal.py` |

三支拆开还是合并成一支，取决于统计口径：合并版里 `attitude`/`engagement`/`graduation`
是互斥取一支（`APPRAISAL-TYPE`），一个跨度只能进一支；拆开后各层独立计数，百分比互不干扰。
两套都支持，`--scheme appraisal` 就是单层合并版。细节见 `references/appraisal.md`。

## 何时用

- 把 `.doc` / `.txt` / 网页正文做成 UAM 项目，标及物性、态度、介入、级差（任意组合）
- 项目已有，要批量标注、校验、改写某一层
- 多章各自成项目后，合成本书一个 text（多层一起合，`--layer` 可只合指定层）
- 要 UAM Statistics 口径的频次表（`StatsResult.html`、Excel、CSV），按层各出一份

不适用：需要 UAM 的 UD 句法解析、多 text 对照、或改标注方案特征集的场景。

## 五步流程

脚本都在 `scripts/`，只依赖标准库 + openpyxl；只有 `--doc` 需要额外装 LibreOffice 或 pandoc（有其一即可）。
换机器或改过脚本后先跑 `python scripts/selfcheck.py`，它会在临时目录把四条链路走一遍，末尾打印 PASS/FAIL。

### 1. 建项目

```bash
# 默认四层：及物性 / 态度 / 介入 / 级差
python scripts/make_project.py --text 第三章.txt --out ./项目/第三章 --name 第三章

# 自选层（--layer 层名:方案，可重复；只给层名时方案按名推断）
python scripts/make_project.py --text 第三章.txt --out ".../第三章" \
  --layer 及物性:transitivity --layer 态度 --layer 介入 --layer 级差
python scripts/make_project.py --text 语料.txt --out ".../态度章" --layer 态度

# 只要一层时仍可用 --scheme（旧用法）
python scripts/make_project.py --text 语料.txt --out ".../评价章" --scheme appraisal
```

正文来源三种：`--text`（一行一段）、`--html`（WPS/Word 导出，会做视觉行→段落还原）、
`--doc`（`.doc/.docx/.rtf/.odt` 直通，内部转 HTML，需 soffice 或 pandoc）。
Word 导出的 txt 若是硬折行加 `--wrap`；开头标题行不属于正文时加 `--no-title`。

```bash
python scripts/doc_to_html.py 第三章.doc --out-dir ./tmp     # 只转 HTML，不建项目
```

终端报字符/段/句/词与三个质量指标（裸数字、断词、双空格）——后两者应为 0，否则原文有粘连。

### 2. 写标注

标注是数据文件，命名 `<prefix>_a.py`、`<prefix>_b.py`…，放在项目目录。**每层一套 prefix**，
互不干扰（如 `c1_*` 及物性、`at_*` 态度、`en_*` 介入、`gr_*` 级差）。

及物性层：

```python
ANN = {
  0: [                                          # 句号，即 sentence.dat 的下标（0 起）
    ('It was snowing for the second time that spring', 'material',
     [('Actor', 'It'), ('location_time', 'for the second time that spring')]),
  ],
  1: [
    ('The large, heavy flakes gathered high up in the sky', 'material',
     [('Actor', 'The large, heavy flakes'), ('location_place', 'high up in the sky')],
     [('each flake trying to deprive the earth of its first smatterings of green',
       'material', [('Actor', 'each flake'), ('Goal', 'the earth')])]),   # 第 4 位是嵌套子句
  ],
}
```

小句元组 = `(原文片段, 过程类型, [成分…], [嵌套子句…])`；成分 = `(角色, 片段[, nth])`。
片段按**空白归一**匹配（换行、多空格不影响），但必须与原文同字，差一个字母就报定位错误。

评价三支（态度 / 介入 / 级差）的 ANN 是**一段多特征**，元组 = `(片段, [特征…][, nth][, [子段…]])`：

```python
# 态度层：给齐 类型 + 显性度 + 极性，可选 评价者/被评价者
ANN = {
  0: [('utterly boring',
       ['attitude', 'appreciation', 'reaction', 'quality',
        'negative-attitude', 'inscribed', 'writer-appraiser'])],
  1: [('disappointed',
       ['attitude', 'affect', 'dis/satisfaction', 'dis/pleasure',
        'negative-attitude', 'inscribed', 'other-appraiser'])],
}

# 介入层
ANN = {1: [('Sadly', ['engagement', 'hetero-glossic', 'expand', 'entertain'])]}

# 级差层
ANN = {0: [('utterly', ['graduation', 'force', 'intensification', 'degree', 'upscale'])]}
```

```bash
# 及物性层
python scripts/ann_skeleton.py --project "./项目/第四章" --sent 0 40 --prefix c4_a --write
python scripts/run_annotation.py --project "./项目/第四章" --ann-prefix c4            # 干跑
python scripts/run_annotation.py --project "./项目/第四章" --ann-prefix c4 --write --out ./复核

# 态度 / 介入 / 级差：--layer 指明哪一层，方案随层自动取 Schemes/<层名>.xml
python scripts/run_appraisal.py --project "./项目/第四章" --layer 态度 --ann-prefix at
python scripts/run_appraisal.py --project "./项目/第四章" --layer 态度 --ann-prefix at --write --out ./复核
python scripts/run_appraisal.py --project "./项目/第四章" --layer 介入 --ann-prefix en --write
python scripts/run_appraisal.py --project "./项目/第四章" --layer 级差 --ann-prefix gr --write
```

写盘前自动查四条：特征是否存在 / **入口条件是否闭合**（选了 `quality` 就必须同时给 `reaction`、
`appreciation`、`attitude`）/ 同一系统是否只取一个 / 同一跨度是否标了两次。
同一跨度的多个特征 OR 进同一条记录的位图，不拆成多条。
根特征（`attitude` / `engagement` / `graduation` / `clause`）由脚本自动补，**不要写进特征表**，
否则会重复写入同一段。

`--write` 先备份旧 idx、回读自检，再出 `<章>_<层>标注复核表.xlsx`、`_<层>标注明细.tsv`、`_<层>标注复核.html`。

### 3. 校验

结构校验六项：越界 / 父段无效 / 子段未包住 / 同层重叠 / 不属任何句 / 覆盖率。
任何一项非 0 就退出不写盘。及物性覆盖率落 95–97% 属正常（标题、单独成句的呼语、句间空白未标）；
评价层天然稀疏（5–25%），覆盖率只作参考，不设阈值。

### 4. 合并成书

```bash
# 默认合并首章 .ct3 里声明的全部层
python scripts/merge_book.py --base ./项目 \
  --chapters 斯日古冷 第二章 第三章 ... 第十二章 --out 斯日古冷_全书
python scripts/verify_merge.py --base ".../项目" --book 斯日古冷_全书 \
  --chapters 斯日古冷 第二章 ...

# 只合指定层
python scripts/merge_book.py --base ./项目 --chapters 第一章 第二章 \
  --out 评价全书 --layer 态度 介入 级差
python scripts/verify_merge.py --base ./项目 --book 评价全书 \
  --chapters 第一章 第二章 --layer 态度
```

合并不是拼字符串：文本与切句只拼一次，各层记录各自 `sid` 加基数、`pid` 同步平移、`start/end` 加字符偏移。
合并前核对各章该层 idx 的特征表与方案是否一致，不一致拒绝合并；及物性层还校验「三系统之和 = 段总数」。
某层在全部章节都没 idx 时输出空层，保证 `.ct3` 声明的层都有文件。
`verify_merge.py` 把书按章切回逐层全字段比对，确认零差异。

### 5. 导出统计

```bash
# 及物性层
python scripts/export_stats.py --project ".../全书" --out . --layer 及物性
python scripts/export_stats.py --project ".../全书" --out . --exclude 15599:31198 --suffix _dedup
python scripts/export_stats.py --project ".../全书" --out . --xlsx --chapters 斯日古冷 第二章 ...

# 评价三支 / 合并版（系统与特征全部来自方案 xml，不做硬编码）
python scripts/export_appraisal_stats.py --project ".../全书" --layer 态度 --out ./统计_态度 --xlsx
python scripts/export_appraisal_stats.py --project ".../全书" --layer 介入 --out ./统计_介入
python scripts/export_appraisal_stats.py --project ".../全书" --layer 级差 --out ./统计_级差
python scripts/export_appraisal_stats.py --project ".../评价全书" --out . --xlsx --csv
```

默认输出复刻 UAM 导出的 `StatsResult.html`（`Counting: global`）。
口径与 UAM 完全一致：**% = N ÷ 段总数，不是 system 内占比**；MENTAL-TYPE / RELATIONAL-TYPE
是 PROCESS-TYPE 的子集，不参与 100% 相加。详见 `references/statistics.md`。
评价层同一段会在多个系统表里各计一次，这是多维标注的正常结果，不是重复计数；
拆层之后各层百分比也**不能跨层相加**（同一个片段可能既是态度又带级差）。

## 关键事实（跳过会踩坑）

| 事实 | 说明 |
|---|---|
| 一个项目可有多层 | `.ct3` 里并列多个 `<layer version='3'>`，每层一个 `Schemes/<层名>.xml` + `Annotations/.../<层名>.idx` |
| `.idx` 是二进制 | 6×uint32 头 + `;` 分隔特征表 + 每条 `16 + 8×intsNeeded` 字节记录，见 `references/idx-format.md` |
| 空 idx 合法 | 只有头和特征表、0 条记录，UAM 能正常打开（新建项目的空层就是这么写的） |
| `sid` / `pid` 是 u16 | 单 text 上限 65,535 条记录，超了必须先拆 |
| 盒子标签只显示 `Clause` | 参与者/环境段必须写 `role` 字段，否则 UAM 只显示过程类型 |
| 一句可有多条 `pid=0` | 并列、非限定、从属小句都平铺，不是错误 |
| 及物性一段一特征 | 按成分分段（过程段/参与者段/环境段），feature pattern 退化为单特征 |
| 评价一段多特征 | 一个跨度同时落 类型 / 显性度 / 极性… 每系统一特征，OR 进同一张位图 |
| 换方案的位图会错乱 | 位图下标就是特征表顺序，`uamlib.set_features()` 必须在写/读时成对切换，写完立刻还原 |
| 位图不是固定 8 字节 | 按 64 位字存，`intsNeeded = ceil(特征数/64)`：及物性/态度 36 特征 → 1 字/24 字节，合并评价 75 特征 → 2 字/32 字节 |
| `sentence.dat` 每句 8 字节 | 两个 uint32 起止；切句器若末句不推进 `start` 会重复末句，务必校验 |
| 顶层小句按顺序定位 | 前一小句的 `end` 就是下一句搜索的 `start`；母句跨度若吞掉后随非限定小句，后一句就报「未找到」 |
| 人名首字母不切句 | `U. Khurelsukh` / `I.K. Azizov` 已在切句器里排除，否则一句话会被切成碎句 |
| 复核件默认写到 cwd | 想放到项目里就加 `--out ./复核`，脚本会自动建目录 |

## 已验证的坑：位图字序

`.idx` 记录的位图按 64 位字存，**高位字在前**（`bits = word[0] << 64 | word[1]`）。
写成低位字在前时 UAM 不报格式错，只在打开项目时抛
`Error: some problem with getData: list index out of range` —— 它按错误偏移取位，下标越界。

- 1 个字的方案（≤64 特征：及物性、态度、介入、级差）两种字序字节完全相同，所以这个坑只在 >64 特征的方案（合并评价 75 特征 → 2 字 / 32 字节记录）暴露
- 定位方式：让 UAM 自己在评价层标 3 条并保存，读它的 `.idx` 对照，一眼看出 word[0] 全是 0、特征全在 word[1]
- 修复：`uamlib.write_idx` / `read_idx` 按 `nw-1-w` 取字

## 参考

- `references/idx-format.md` — `.idx` / `sentence.dat` / `.ct3` 二进制细节（含多层 .ct3 写法）
- `references/multilayer.md` — 多层项目布局、层间取舍、迁移已有单层项目、四层示范数据
- `references/annotation-conventions.md` — 及物性十条标注口径、ANN 写法、常见判定争议
- `references/appraisal.md` — 评价理论 31 系统完整树、三支拆分对照、入口条件链、口径要点
- `references/statistics.md` — UAM Statistics 的 N / % 定义与三种视图
- `assets/scheme-transitivity.xml` — 及物性（36 特征 / 5 系统）
- `assets/scheme-attitude.xml` / `scheme-engagement.xml` / `scheme-graduation.xml` — 评价三支（UAM 自带）
- `assets/scheme-appraisal.xml` — 合并版 Appraisal_max（75 特征 / 31 系统）
- `scripts/selfcheck.py` — 全链路自检（多层骨架 + 及物性 + 三支子层 + 合并评价，47 项），末尾打印 PASS/FAIL
