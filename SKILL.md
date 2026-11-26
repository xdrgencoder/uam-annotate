---
name: uam-transitivity
description: Build, annotate, validate, merge and export UAM CorpusTool 6 transitivity projects entirely from the command line, bypassing the GUI by writing the binary .idx format directly. Use when a task involves UAM / UAM CorpusTool / .ct3 / 及物性 / transitivity analysis, clause annotation of English corpus texts, converting .doc or .txt chapters into UAM projects, merging chapter projects into one book text, or reproducing UAM's Statistics / StatsResult.html output. Triggered by 语料标注、及物性分析、过程类型、参与者角色、环境成分、UAM 项目、多章合并、统计导出.
agent_created: true
---

# UAM CorpusTool 6 及物性标注流水线

全流程绕过 GUI：直接读写 CT6 的二进制 `.idx` 与 `sentence.dat`，用 Python 批量落盘。
适用英文叙事语料（单 text），方案固定为及物性（36 特征 / 5 系统 / 4 层）。

## 何时用

- 把 `.doc` / `.txt` / 网页正文做成 UAM 项目并标及物性
- 项目已有，要批量标注、校验、改写
- 多章各自成项目后，合成本书一个 text
- 要 UAM Statistics 口径的频次表（`StatsResult.html`、Excel、CSV）

不适用：需要 UAM 的 UD 句法解析、多 text 对照、或改标注方案特征集的场景。

## 五步流程

脚本都在 `scripts/`，只依赖标准库 + openpyxl；只有 `--doc` 需要额外装 LibreOffice 或 pandoc（二者有其一即可）。
换机器或改过脚本后先跑 `python scripts/selfcheck.py`，它会在临时目录把五步走一遍，末尾打印 PASS/FAIL。
示例路径写成相对形式，Windows 下把 `./项目` 换成实际目录；Windows 的 soffice 在 `LibreOffice\program\soffice.exe`，不在 PATH 时装 pandoc 兜底。

### 1. 建项目

```bash
# 纯文本（一行一段）
python scripts/make_project.py --text 第三章.txt --out ./项目/第三章 --name 第三章
# WPS/Word 导出的 HTML（会做视觉行→段落还原）
python scripts/make_project.py --html 第三章.html --out ".../第三章" --name 第三章
# Word/WPS 文件直通（.doc/.docx/.rtf/.odt），内部自动转 HTML
python scripts/make_project.py --doc 第三章.docx --out ".../第三章" --name 第三章
# Word 导出的 txt：一行只是视觉行时加 --wrap 还原段落；标题行不属于正文时加 --no-title
python scripts/make_project.py --text 第三章.txt --wrap --no-title --out ".../第三章" --name 第三章
```

产出 `Corpus/Texts/Text-1.txt`、`Schemes/及物性.xml`、`<name>.ct3`、`Metadata.idx`、`sentence.dat`。
终端报字符/段/句/词与三个质量指标（裸数字、断词、双空格）——后两者应为 0，否则原文有粘连。

`--doc` 由 `scripts/doc_to_html.py` 转换，后端按 LibreOffice(soffice) → pandoc → python-docx 自动降级，
全都没有时报错退出；LibreOffice 用独立 profile，不影响桌面端已打开的文档。也可单独转换：

```bash
python scripts/doc_to_html.py 第三章.doc --out-dir ./tmp     # 只出 HTML，不建项目
```

### 2. 写标注

标注是数据文件，命名 `<prefix>_a.py`、`<prefix>_b.py`…，放在项目目录，每个导出 `ANN`：

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
`nth` 在句内同片段出现多次时指定第几处（0 起）。

一次标 30–60 句一批，先干跑再落盘：

```bash
python scripts/ann_skeleton.py --project "./项目/第四章" --sent 0 40 --prefix c4_a --write  # 出骨架
python scripts/run_annotation.py --project "./项目/第四章" --sent 0 40         # 看句子
python scripts/run_annotation.py --project "./项目/第四章" --ann-prefix c4     # 干跑
python scripts/run_annotation.py --project "./项目/第四章" --ann-prefix c4 --write --out ./复核
```

`--write` 先备份旧 idx、回读自检，再出 `_标注复核表.xlsx`、`_标注明细.tsv`、`_标注复核.html`。

### 3. 校验

`run_annotation.py` 内置六项结构校验：越界 / 父段无效 / 子段未包住 / 同层重叠 / 不属任何句 / 覆盖率。
任何一项非 0 就退出不写盘。覆盖率落 95–97% 属正常（标题、单独成句的呼语、句间空白未标）。

### 4. 合并成书

```bash
python scripts/merge_book.py --base ./项目 \
  --chapters 斯日古冷 第二章 第三章 第四章 第五章 第六章 第七章 第八章 第九章 第十章 第十一章 第十二章 \
  --out 斯日古冷_全书
python scripts/verify_merge.py --base ".../项目" --book 斯日古冷_全书 --chapters 斯日古冷 第二章 ...
```

合并不是拼字符串：`sid` 加记录基数、`pid` 同步平移、`start/end` 加字符偏移。
脚本自动校验「三系统之和 = 段总数」并逐条报越界/父段问题；`verify_merge.py` 再把书按章切回，
与分章项目全字段比对，确认零差异。

### 5. 导出统计

```bash
python scripts/export_stats.py --project ".../斯日古冷_全书" --out .
python scripts/export_stats.py --project ".../全书" --out . --exclude 15599:31198 --suffix _dedup
python scripts/export_stats.py --project ".../全书" --out . --xlsx --chapters 斯日古冷 第二章 ...
```

默认输出复刻 UAM 导出的 `StatsResult.html`（五张表 + `Counting: global`）。
口径与 UAM 完全一致：**% = N ÷ 段总数，不是 system 内占比**；MENTAL-TYPE / RELATIONAL-TYPE
是 PROCESS-TYPE 的子集，不参与 100% 相加。详见 `references/statistics.md`。

## 关键事实（跳过会踩坑）

| 事实 | 说明 |
|---|---|
| `.idx` 是二进制 | 6×uint32 头 + `;` 分隔特征表 + 每条 24 字节记录，见 `references/idx-format.md` |
| `sid` / `pid` 是 u16 | 单 text 上限 65,535 条记录，超了必须先拆 |
| 盒子标签只显示 `Clause` | 参与者/环境段必须写 `role` 字段，否则 UAM 只显示过程类型 |
| 一句可有多条 `pid=0` | 并列、非限定、从属小句都平铺，不是错误 |
| 每段只带一个特征 | 按成分分段（过程段/参与者段/环境段），故 feature pattern 退化为单特征 |
| `sentence.dat` 每句 8 字节 | 两个 uint32 起止；切句器若末句不推进 `start` 会重复末句，务必校验 |
| 顶层小句按顺序定位 | 前一小句的 `end` 就是下一句搜索的 `start`；母句跨度若吞掉后随非限定小句，后一句就报「未找到」 |
| 人名首字母不切句 | `U. Khurelsukh` / `I.K. Azizov` 已在切句器里排除，否则一句话会被切成碎句 |
| 复核件默认写到 cwd | 想放到项目里就加 `--out ./复核`，脚本会自动建目录 |

## 参考

- `references/idx-format.md` — `.idx` / `sentence.dat` / `.ct3` 二进制细节
- `references/annotation-conventions.md` — 十条标注口径、ANN 写法、常见判定争议
- `references/statistics.md` — UAM Statistics 的 N / % 定义与三种视图
- `assets/scheme-transitivity.xml` — 及物性方案（36 特征 / 5 系统）
- `scripts/selfcheck.py` — 全链路自检，末尾打印 PASS/FAIL
