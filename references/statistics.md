# UAM Statistics 口径

从 UAM 真实导出的 `StatsResult.html` 反推并用试点数据验证过，`export_stats.py` 严格照此实现。

## 导出文件长什么样

```html
<p><b>User</b>: $Standalone
<p><b>Unit of Interest</b>: &lt;及物性 feature="clause"/&gt;
<p><b>Aspect</b>: feature
<p><b>Counting</b>: global

<table class="statstable">
  <tr><th><b>PROCESS-TYPE</b></th><th class="tableinset"></th><th>N</th><th>%</th></tr>
  <tr><td class="statscol1"> - material</td><td class="tableinset"></td>
      <td class="bluecol">414</td><td>19.3</td></tr>
  …
  <tr><td class="statscol1"><b>TOTAL</b>:</td><td></td><td><b>692</b></td><td><b>32.3%</b></td></tr>
</table>
```

五个 system 各一张表，顺序固定：PROCESS-TYPE、MENTAL-TYPE、RELATIONAL-TYPE、PARTICIPANT-ROLE、CIRCUMSTANCE。

## N 与 % 的定义

- **N** — 带该特征的**标注段数**（coded segments）。一个段可以同时带 process type 和若干成分？不会：
  本方案按成分分段，每段只带一个特征（外加恒真的 `clause`）。
- **%** — `N ÷ 全部标注段数`。**不是** system 内占比。

验证：试点第一章 2142 段，material 414 → 414/2142 = 19.3% ✓；PROCESS-TYPE TOTAL 692 → 692/2142 = 32.3% ✓。
如果按 system 内算，414/692 = 59.8%，与导出值不符——这是最容易搞错的地方。

## 三系统恒等式

```
PROCESS-TYPE 的 N 之和  +  PARTICIPANT-ROLE 的 N 之和  +  CIRCUMSTANCE 的 N 之和  =  段总数
```

因为每个段恰好落在这三个并列系统之一。全书例：7,646 + 11,493 + 3,969 = 23,108。
`merge_book.py` 会断言这条恒等式，不成立说明有段漏标或重复归类。

MENTAL-TYPE 与 RELATIONAL-TYPE 不是并列系统，是 PROCESS-TYPE 的子集：
MENTAL 的 N 之和 = mental 的 N，RELATIONAL 的 N 之和 = relational 的 N。它们参与不了 100%。

## 三种统计视图

| 视图 | 含义 | 在这个方案里的表现 |
|---|---|---|
| **Feature statistics** | 单特征频次，按 system 分块 | 主表，就是 `StatsResult.html` |
| **Feature pattern** | 一个 segment 上被激活的全部特征组合 | 因按成分分段，退化为「clause+特征名」，全书仅 33 种 |
| **Clause pattern**（小句模式） | 小句自身 + 全部直接子段的特征集合 | 解释力最强，全书 6,670 顶层小句 / 433 种组合 |

`export_stats.py --xlsx` 会把三者都写进工作簿。小句模式的 top 通常是
`relational+attributive+Carrier+Attribute`、`material+Actor+location_place`、`material+Actor+Goal`。

## 去重

若原文正文重复（如正文两遍都保留），UAM 的 Global 会把两遍都算进去——GUI 里没法只统计一半。
用 `--exclude START:END` 剔除起点落在该区间的段，分母随之减小：

```bash
python scripts/export_stats.py --project ".../全书" --out . --exclude 15599:31198 --suffix _dedup
```

注意同时要排除该区间的句子（`export_stats.py` 的分母用剩下的段数，句子数不参与百分比）。

## 与论文口径的对照

| 指标 | 全量（两遍） | 去重（第一章取前半） |
|---|---:|---:|
| 句 | 4,042 | 3,875 |
| 词 | 61,921 | 59,160 |
| 小句（PROCESS 段） | 7,646 | 7,300 |
| 标注段 | 23,108 | 22,038 |

两者的百分比几乎不变（33.1% vs 33.1%），因为重复的恰恰是同一段文本。
论文里报去重口径，附录材料可以给全量。
