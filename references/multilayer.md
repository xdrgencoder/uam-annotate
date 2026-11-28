# 一个项目，多个层

UAM 的项目模型是「**一段语料 + 若干标注层**」，不是「一个项目一个方案」。
本流水线默认给新项目建四层：及物性 / 态度 / 介入 / 级差。

## 布局

```
项目/Sharpie_四层/
├── Sharpie.ct3                       4 个并列 <layer>
├── Schemes/
│   ├── 及物性.xml                     ← scheme-transitivity.xml
│   ├── 态度.xml                       ← scheme-attitude.xml
│   ├── 介入.xml                       ← scheme-engagement.xml
│   └── 级差.xml                       ← scheme-graduation.xml
├── Corpus/Texts/Text-1.txt            一份正文，四层共用
└── Annotations/Texts/Text-1.txt/
    ├── sentence.dat                   一份切句，四层共用
    ├── 及物性.idx                     各层独立记录
    ├── 态度.idx
    ├── 介入.idx
    └── 级差.idx
```

层名同时决定三件事，所以**同一项目里层名必须唯一**：`.ct3` 的 `<name>`、
`Schemes/<层名>.xml`、`Annotations/.../<层名>.idx`。

## 建项目

```bash
# 默认四层
python scripts/make_project.py --text 语料.txt --out ./项目/Sharpie --name Sharpie

# 自选组合（--layer 层名:方案，可重复）
python scripts/make_project.py --text 语料.txt --out ./项目/Sharpie --name Sharpie \
  --layer 及物性:transitivity --layer 态度 --layer 介入 --layer 级差

# 只要一层，两种写法都行
python scripts/make_project.py --text 语料.txt --out ./项目/态度章 --layer 态度
python scripts/make_project.py --text 语料.txt --out ./项目/评价章 --scheme appraisal
```

新项目会给每层写一个**空 idx**（头部 + 特征表 + 0 条记录），UAM 打开就是空层，
不进 GUI 建层也能直接开始标注。空 idx 是合法的：UAM 读它只得到「0 段」。

## 合并还是拆分

评价理论在 UAM 里有两套现成方案，取舍在于统计口径：

| | 合并版（`--scheme appraisal`） | 三支拆分（默认） |
|---|---|---|
| 层数 | 1 层（评价） | 3 层（态度 / 介入 / 级差） |
| 特征 | 75 / 31 系统 | 36 + 19 + 22 |
| 一个跨度 | 只能落在 `attitude` / `engagement` / `graduation` **一支**（`APPRAISAL-TYPE` 互斥） | 各层独立，同一个片段可以在三层里各有一条 |
| 统计 | 31 张表，同一段在多表各计一次 | 每层各出一套表，分母是**该层的段数** |
| 适合 | 想看「整体评价资源分布」 | 想看三支各自的内部构型 |

拆开的好处是分母干净：态度层的 100% 是「态度段」的 100%，不会被介入段稀释。
代价是同一个片段可能在三层各标一次（真实语料里「级差嵌在态度里」很常见），
所以**跨层百分比不能相加**，也不能拿三层的段数之和当总段数。

拆分层的入口条件是各自方案的根：态度层必须给 `attitude`，介入层 `engagement`，级差 `graduation`。
根特征由脚本自动补，ANN 里**不要再写**（写了会重复进位图）。

## 标注

每层一套 prefix，避免模块名撞车：

```bash
python scripts/run_annotation.py --project ./项目/Sharpie --layer 及物性 --ann-prefix c --write
python scripts/run_appraisal.py --project ./项目/Sharpie --layer 态度 --ann-prefix at --write --out ./复核
python scripts/run_appraisal.py --project ./项目/Sharpie --layer 介入 --ann-prefix en --write --out ./复核
python scripts/run_appraisal.py --project ./项目/Sharpie --layer 级差 --ann-prefix gr --write --out ./复核
```

复核件名带层名（`Sharpie_四层_态度标注复核.html`），三层各一套，不会互相覆盖。
`--layer` 只决定写哪个 idx，其余文件（正文、切句）不动。

## 合并与统计

```bash
# 合并：默认把首章 .ct3 声明的层全部合掉
python scripts/merge_book.py --base ./项目 --chapters 第一章 第二章 --out 全书
python scripts/verify_merge.py --base ./项目 --book 全书 --chapters 第一章 第二章

# 只合某几层
python scripts/merge_book.py --base ./项目 --chapters 第一章 第二章 \
  --out 全书_评价 --layer 态度 介入 级差

# 统计：按层各出一份
python scripts/export_stats.py --project ./项目/全书 --out ./统计 --layer 及物性 --xlsx
python scripts/export_appraisal_stats.py --project ./项目/全书 --layer 态度 --out ./统计_态度
python scripts/export_appraisal_stats.py --project ./项目/全书 --layer 介入 --out ./统计_介入
python scripts/export_appraisal_stats.py --project ./项目/全书 --layer 级差 --out ./统计_级差
```

合并时文本与切句只拼一次，各层记录各自平移；某层在某章没有 idx 就跳过，
全书也没有就写空 idx，保证 `.ct3` 声明的层都有对应文件（否则 UAM 打开会缺层）。

## 把已有单层评价项目迁到三支

老项目是合并版 `评价.idx`（75 特征）。迁法：按记录的首个特征（即 `APPRAISAL-TYPE` 的取值）
分流到三层，再按目标层方案过滤特征。

两处必须处理：

1. **根特征去掉**——目标层根是 `attitude`/`engagement`/`graduation`，脚本会补，留着会重复。
2. **特征名映射**——合并版把评价者放在 `AFFECT-TYPE`（`authorial-evaluation` /
   `non-authorial-evaluation`），拆分版放在 `APPRAISER`（`writer-appraiser` / `other-appraiser`）：

   ```python
   MAP = {'authorial-evaluation': 'writer-appraiser',
          'non-authorial-evaluation': 'other-appraiser'}
   ```

其余 43 个特征名两套方案一致，直接搬。子段（`ANN` 元组第 4 位）若与父段同支就保留嵌套，
不同支就提升为该层的顶层段——比如「a much better pen」里的 `much`（级差）挂在态度段下，
拆开后 `much` 成为级差层的独立段。

迁移后必须回读核对：三层条数之和 = 原段数 + 跨支提升的子段数。

## 示范数据

`Sharpie_四层`（AP 政治新闻，4131 字符 / 35 句 / 22 段）由合并版评价项目迁来：

| 层 | 方案 | 段数 | 覆盖率 |
|---|---|---|---|
| 及物性 | 36 特征 / 5 系统 | 0（未标，空层） | — |
| 态度 | 36 特征 / 13 系统 | 23 | 12.5% |
| 介入 | 19 特征 / 8 系统 | 4 | 3.0% |
| 级差 | 22 特征 / 10 系统 | 5 | 1.4% |

23 + 4 + 5 = 32，与原评价层 32 个顶层段一致（原第 33 条是挂在态度段下的 `much`，拆后进级差层）。

## 校验清单

打开 UAM 前先过一遍：

- [ ] `.ct3` 的 `<layer>` 数量 = 期望层数，`<name>` 与 `<scheme>` 一致
- [ ] `Schemes/` 里每个层名都有 `.xml`
- [ ] `Annotations/.../` 里每个层名都有 `.idx`（可以是空层）
- [ ] 每个 idx 的特征表顺序 = 该层方案 xml 的顺序（`read_idx` 会回读比对）
- [ ] 及物性层「三系统之和 = 段数」；其它层「每段特征都过 EC 闭合」
- [ ] `python scripts/selfcheck.py` 末尾是 PASS
