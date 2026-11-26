# uam-transitivity

**UAM CorpusTool 6 及物性标注流水线 —— 完全命令行，绕过 GUI。**

直接读写 CT6 的二进制 `.idx` 与 `sentence.dat`，用 Python 批量落盘。适用于英文叙事语料（单 text）的及物性分析，标注方案固定为 36 特征 / 5 系统 / 4 层。

An agent skill (WorkBuddy / Claude Code) for building, annotating, validating, merging and exporting UAM CorpusTool 6 transitivity projects without ever opening the GUI.

---

## 为什么需要它

UAM CorpusTool 6 只提供 GUI：建项目靠点、标注靠点、多章合并靠手动。一本书十几章、几千句的标注工作量，用鼠标点完基本不可能，而且中途无法版本管理、无法复核、无法批量统计。

这个包把整条链路搬到命令行：项目结构、标注数据、合并、统计全部由脚本生成，产物可以直接用 UAM 打开核对，也可以完全不打开 UAM 就拿到 `StatsResult.html` 口径的频次表。

## 五步流程

| 步骤 | 脚本 | 作用 |
|---|---|---|
| 1. 建项目 | `make_project.py` | `.txt` / `.html` / `.doc` / `.docx` / `.rtf` / `.odt` → 标准 CT6 项目结构 |
| 2. 写标注 | `ann_skeleton.py` + `run_annotation.py` | 生成骨架 → 填 `ANN` → 干跑 → 落盘（带备份） |
| 3. 校验 | 内置于 `run_annotation.py` | 六项结构校验，非 0 即拒绝写盘 |
| 4. 合并成书 | `merge_book.py` + `verify_merge.py` | 多章项目 → 一个 text；再切回逐章零差异比对 |
| 5. 导出统计 | `export_stats.py` | 复刻 UAM 的 `StatsResult.html`，可加 `--xlsx` / `--csv` |

配套：`doc_to_html.py`（Word/WPS → HTML，LibreOffice → pandoc → python-docx 三级降级）、`uamlib.py` / `annlib.py`（`.idx` 二进制读写与定位核心）、`selfcheck.py`（全链路自检）。

## 安装

把整个目录放进技能目录即可：

```bash
# WorkBuddy
cp -r uam-transitivity ~/.workbuddy/skills/

# Claude Code
cp -r uam-transitivity ~/.claude/skills/
```

也可以只当普通 Python 脚本用，直接 `python scripts/make_project.py --help`。

### 依赖

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

## 关键事实（跳过会踩坑）

| 事实 | 说明 |
|---|---|
| `.idx` 是二进制 | 6×uint32 头 + `;` 分隔特征表 + 每条 24 字节记录 |
| `sid` / `pid` 是 u16 | 单 text 上限 65,535 条记录，超了必须先拆 |
| 盒子标签只显示 `Clause` | 参与者/环境段必须写 `role` 字段，否则 UAM 只显示过程类型 |
| 一句可有多条 `pid=0` | 并列、非限定、从属小句都平铺，不是错误 |
| 每段只带一个特征 | 按成分分段，feature pattern 退化为单特征 |
| `sentence.dat` 每句 8 字节 | 两个 uint32 起止；末句不推进 `start` 会重复末句 |
| 顶层小句按顺序定位 | 前一小句的 `end` 是下一句的搜索 `start` |
| 人名首字母不切句 | `U. Khurelsukh` / `I.K. Azizov` 已在切句器排除 |
| 覆盖率 95–97% 正常 | 标题、独立呼语、句间空白本就不标 |

## 统计口径

与 UAM 完全一致：**% = N ÷ 段总数，不是 system 内占比**。`MENTAL-TYPE` / `RELATIONAL-TYPE` 是 `PROCESS-TYPE` 的子集，不参与 100% 相加。详见 `references/statistics.md`。

## 自检

换机器、换 Python、改过脚本之后先跑：

```bash
python scripts/selfcheck.py          # 跑完删临时目录
python scripts/selfcheck.py --keep   # 保留产物以便查看
```

会在临时目录把五步完整走一遍（建项目 → 骨架 → 标注落盘 → 合并 → 回比 → 统计），末尾打印 `PASS` 或失败项。

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
PASS
```

## 目录结构

```
uam-transitivity/
├── SKILL.md                          # 技能说明（五步流程 + 关键事实）
├── scripts/
│   ├── make_project.py               # 建项目
│   ├── doc_to_html.py                # Word/WPS → HTML
│   ├── ann_skeleton.py               # 生成 ANN 骨架
│   ├── run_annotation.py             # 校验 + 落盘 + 复核件
│   ├── merge_book.py                 # 多章合并
│   ├── verify_merge.py               # 合并结果回比
│   ├── export_stats.py               # 统计导出
│   ├── uamlib.py                     # .idx / sentence.dat 读写
│   ├── annlib.py                     # 片段定位与段落构建
│   └── selfcheck.py                  # 全链路自检
├── references/
│   ├── idx-format.md                 # 二进制格式细节
│   ├── annotation-conventions.md     # 十条标注口径与争议判定
│   └── statistics.md                 # N / % 定义与三种视图
└── assets/
    └── scheme-transitivity.xml       # 及物性方案（36 特征 / 5 系统 / 4 层）
```

## 不适用

- UAM 的 UD 句法解析
- 多 text 对照
- 修改标注方案的特征集（方案是固定的）

## 许可

未指定许可。如需复用或再分发，请先联系作者。
