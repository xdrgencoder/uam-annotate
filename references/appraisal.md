# 评价理论层（Appraisal）

方案取自 UAM CorpusTool 6 自带的 `Resources/Schemes/Appraisal_max.xml`，本包 `assets/scheme-appraisal.xml` 是原样副本。

**规模**：根特征 `appraisal`，31 个系统，75 个特征，50 条 GLOSS，**0 条 REALISATION**（纯手工标注，没有任何自动识别规则，所以不受「自动标注器」影响，也不会被 UAM 重新计算覆盖）。

选它建项目：

```bash
python scripts/make_project.py --text 语料.txt --out ./项目/评价章 --name 评价章 --scheme appraisal
```

产出的层名是 `评价`，方案落 `Schemes/评价.xml`，标注写 `Annotations/Texts/Text-1.txt/评价.idx`。

## 与及物性层的三个结构差异

| | 及物性 | 评价理论 |
|---|---|---|
| 标注单位 | 小句 + 成分，**一段一特征** | 评价片段，**一段多特征**（每个系统各出一个） |
| 段层级 | 母子树（小句 > 参与者 > 从句） | 一般扁平，只有「整段态度 > 局部强化」才嵌套 |
| 覆盖率 | 95–97%（几乎覆盖全文） | 通常 5–25%（只标有评价的地方），低不是漏标 |

「一段多特征」是关键：UAM 的 `.idx` 每条记录带一张 u64 位图，一个跨度把若干系统的特征**按位或**进同一张位图，正好对上这种标注方式。所以本包 `apprlib.py` 写记录时是一段一条，不拆成多条。

## 完整系统树

| 系统 | 入口条件（EC） | 特征 |
|---|---|---|
| `APPRAISAL-TYPE` | appraisal | attitude / engagement / graduation |
| `ATTITUDE-TYPE` | attitude | affect / judgement / appreciation |
| `AFFECT-TYPE` | affect | authorial-evaluation / non-authorial-evaluation |
| `AFFECT-TYPE2` | affect | un/happiness / dis/satisfaction / in/security / dis/inclination |
| `UN/HAPPINESS-TYPE` | un/happiness | misery/cheer / antipathy/affection |
| `DIS/SATISFACTION-TYPE` | dis/satisfaction | ennui/interest / dis/pleasure |
| `IN/SECURITY-TYPE` | in/security | dis/quiet / dis/trust |
| `JUDGEMENT-TYPE` | judgement | normality / capacity / tenacity / propriety / veracity / unclear |
| `APPRECIATION-TYPE` | appreciation | reaction / composition / social-valuation |
| `REACTION-TYPE` | reaction | impact / quality |
| `COMPOSITION-TYPE` | composition | balance / complexity |
| `EXPLICITNESS` | attitude | inscribed / invoked |
| `ATTITUDE-POLARITY` | attitude | positive-attitude / negative-attitude / ambiguous |
| `ENGAGEMENT-TYPE` | engagement | mono-glossic / hetero-glossic |
| `HETERO-GLOSSIC-TYPE` | hetero-glossic | contract / expand |
| `CONTRACT-TYPE` | contract | disclaim / proclaim |
| `DISCLAIM-TYPE` | disclaim | deny / counter |
| `PROCLAIM-TYPE` | proclaim | concur / pronounce / endorse / justify |
| `CONCUR-TYPE` | concur | affirm / concede |
| `EXPAND-TYPE` | expand | entertain / attribute |
| `ATTRIBUTE-GATE` | attribute | acknowledge / distance |
| `GRADUATION-TYPE` | graduation | force / focus |
| `FORCE-TYPE` | force | intensification / quantification |
| `INTENSIFICATION-TYPE` | intensification | degree / vigour |
| `QUANTIFICATION-TYPE` | quantification | number / mass / extent |
| `EXTENT-GATE` | extent | proximity / distribution |
| `PROXIMITY-TYPE` | proximity | time / space |
| `DISTRIBUTION-TYPE` | distribution | distrib-time / distrib-space |
| `SCALE` | force | upscale / downscale |
| `LEXICAL-FUSION` | force | isolating / infusing |
| `FOCUS-TYPE` | focus | soften / sharpen |

三处容易看漏的设计：

1. **一个入口条件可以挂多个系统**。`attitude` 同时是 `ATTITUDE-TYPE`、`EXPLICITNESS`、`ATTITUDE-POLARITY` 三套的入口 —— 所以一个态度段必须同时给出「哪一类 + 显性/隐性 + 正/负/模糊」三个特征，缺一个就不完整。`affect` 同理（`AFFECT-TYPE` + `AFFECT-TYPE2`），`force` 挂了三套（`FORCE-TYPE` + `SCALE` + `LEXICAL-FUSION`）。
2. **`GRADUATION-TYPE` 的入口是 `graduation` 而不是 `attitude`** —— 级差可以脱离态度单独标，不必先有态度段。
3. **`mono-glossic` 到此为止**，没有下级系统；`hetero-glossic` 才继续分 contract / expand。

## ANN 写法

一段 = `(原文片段, [特征…])`，可选第 3 位 `nth`（同片段第几处，0 起）、第 4 位 `[子段…]`。

```python
ANN = {
  0: [('utterly boring',
       ['attitude', 'appreciation', 'reaction', 'quality',
        'negative-attitude', 'inscribed'])],
  1: [('Sadly',
       ['attitude', 'affect', 'authorial-evaluation', 'un/happiness',
        'misery/cheer', 'negative-attitude', 'inscribed']),
      ('disappointed',
       ['attitude', 'affect', 'non-authorial-evaluation', 'dis/satisfaction',
        'dis/pleasure', 'negative-attitude', 'inscribed'])],
}
```

跑：

```bash
python scripts/run_appraisal.py --project "./项目/评价章" --sent 0 20      # 看句子
python scripts/run_appraisal.py --project "./项目/评价章" --ann-prefix ap   # 干跑
python scripts/run_appraisal.py --project "./项目/评价章" --ann-prefix ap --write --out ./复核
```

落盘后出 `_评价标注复核表.xlsx`（明细 / 统计 / 系统覆盖三张表）、`_评价标注明细.tsv`、`_评价标注复核.html`。

## 自动校验的四条

写入前 `apprlib.Scheme.diagnose()` 逐段检查，任何一条不过就拒绝写盘：

1. 特征必须在方案里（拼错直接报「未知特征」）。
2. **入口条件闭合**：选了 `quality` 就必须同时有 `reaction`、`appreciation`、`attitude`；链断在哪一层就报哪一层。
3. **同一系统只能取一个特征**：同时给 `positive-attitude` 和 `negative-attitude` 会报错（要模糊就用 `ambiguous`）。
4. **同一跨度不能标两次**：重叠的重复标注会提示合并特征，因为一段只能是位图里的一条记录。

另有结构校验：越界、父段无效、子段越界、跨句、同层重叠。覆盖率只报数不设阈值。

## 标注口径（据方案自带 GLOSS 归纳）

- **`A BORING building` 是 `appreciation:reaction`，不是 `affect`** —— 方案在 `affect` 的 gloss 里明确点了这条：情绪脱离人的感受者、挂到事物属性上，就归 appreciation。
- **评价人的外观用 `appreciation`，评价行为对错用 `judgement`** —— gloss 原文：对人的 appreciation 是「不针对行为正确与否，而是外观」。
- **`judgement:unclear`** 只用于「六个子类都不适用」的情况，与「歧义需双标」不是一回事。
- **`invoked`** 指标的是暗示出来的评价（靠信息本身让人得出判断），不是词汇里明写的。
- **`ambiguous`** 用于态度明显存在但正负难定，常见于有修辞目的的反讽。
- `SCALE`（upscale / downscale）与 `LEXICAL-FUSION`（isolating / infusing）是 `force` 下两个**并列**系统，不是上下级。

## 已知边界

- `merge_book.py` / `verify_merge.py` / `export_stats.py` 目前只认及物性层（`及物性.idx` 与 PROCESS-TYPE 口径）。评价层的多章合并与 UAM 式 `StatsResult.html` 还没做；单章统计用复核表里的「统计」「系统覆盖」两张 sheet。
- 覆盖率天然偏低，`run_appraisal.py` 不会因为覆盖率低而拦截。
- `.idx` 的写法与已验证的及物性层同一个 writer（`uamlib.write_idx`），记录格式一致；但**首次用 UAM 打开评价项目时，建议看一眼盒子标签**——标签取「最深那条特征链」（如 `attitude·affect·un/happiness·misery/cheer`），存在 `role` 字段里，和及物性层同一套机制。
