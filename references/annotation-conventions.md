# 标注口径与写法

## ANN 数据结构

```python
ANN = {
  句号: [ 小句, 小句, … ],
}
```

小句：

```python
(片段, 过程类型, [成分, …], [嵌套子句, …])   # 后两项可省
```

成分：

```python
(角色, 片段)          # 或 (角色, 片段, nth)
```

### 过程类型（第二位）

`material` / `mental` / `relational` / `verbal` / `behavioural` / `existential`，
必要时在后接子类型，用空格分隔：

```python
('he knew the answer', 'mental cognition', [('Senser', 'he'), ('Phenomenon', 'the answer')])
('it was a dog',        'relational identifying',
 [('Identified', 'it'), ('Identifier', 'a dog')])
('the snow was white',  'relational attributive',
 [('Carrier', 'the snow'), ('Attribute', 'white')])
```

### 成分角色（第三位）

参与者 16 个：`Actor` `Goal` `Range` `Beneficiary` `Senser` `Phenomenon` `Carrier`
`Attribute` `Identified` `Identifier` `Sayer` `Verbiage` `Receiver` `Target` `Behaver` `Existent`

环境 8 个：`location_time` `location_place` `manner` `cause` `accompaniment` `matter` `role` `extent`

### 顶层小句的顺序与跨度（最常踩）

`build` 定位顶层小句是**顺序推进**的：第一句从句子起点搜，它的 `end` 就是第二句的搜索起点。
所以第二个并列小句必须落在母句跨度之外——**母句片段不能把后随的非限定小句一起包进去**，
否则报：

```
S1 未找到 'wishing success in his future endeavors'
  区间: '.'
```

（区间只剩一个句号，说明母句已经吃到句末，游标没得可搜。）

正确写法：母句截到非限定小句之前，非限定小句单独成一条顶层记录，这也正好符合口径 4。

```python
 1: [('President U. Khurelsukh commended Ambassador I.K. Azizov … to the strategic partnership',
      'verbal', [('Sayer', 'President U. Khurelsukh'), ('Target', 'Ambassador I.K. Azizov')]),
     ('wishing success in his future endeavors', 'mental emotion',
      [('Phenomenon', 'success in his future endeavors')])],
```

嵌套子句（第 4 位）不受影响，它是在母句跨度内搜的。

### 片段匹配

按**空白归一**比较：原文的换行、连续空格都折算成一个空格，所以片段可以跨行写。
但每一个字符必须与原文一致，包括原文的错字和粘连（`youngmastiff`、`wasstill`、`didn’tdare`）。

同一片段在句内出现多次会报错，用 `nth` 指定：

```python
('he saw what he wanted', 'mental perception',
 [('Senser', 'he', 0), ('Phenomenon', 'what he wanted'), ('Senser', 'he', 1)])
```

## 十条口径

1. **直接引语按独立小句分析**（投影小句），引导句单列 verbal 小句；引语内的句子不并入 Verbiage。
2. **省略的参与者不建段**（没有文本跨度），所以会出现只有 Attribute、或只有 Goal 的段，不是漏标；
   主语本身由从句充当时（"What he saw confirmed X"），该从句按自身过程类型另标，外层不再重复取 Senser 跨度。
3. **目的与原因一律标 `cause`**——方案里 cause 的 GLOSS 就是 "Cause / Purpose"，没有单独的 purpose 特征。
4. **非限定小句单独成段**；只有跨度确实落在母句内部的从属小句才嵌套。
5. **结果/状态成分一律作 `Attribute`**，不另立关系小句：`make/turn + 宾语 + 形容词`（"made him violent"）、
   `wake up / stumble + 形容词`（"woke up furious"）的结果成分直接挂在 material 小句下——这些片段没有谓体，成不了 clause。
6. **`be + 介词短语` 按 circumstantial Attribute 处理**（"he was in the city" → Carrier + Attribute=in the city），
   这是 Halliday 对关系过程的处理，不拆成 location_place。
7. **`be / become + 形容词` 一律 relational attributive**（"were disappointed"、"too scared to get any closer"），
   不标 mental emotion；只有 `feel / want / know / hear` 这类心理动词才建 mental 小句；
   `feel + 形容词`（"felt uncomfortable"）保留 mental，形容词作 Phenomenon；
   **但 `be / become` 后的形容词不能作 Phenomenon**——那是 Attribute。
8. **价格、交易条件的 `for-` 短语作 `Range`**（"go for anything less"、"buy for a shockingly low price"），
   不作 matter；matter 只用于 `about / over` 引出的谈论或争论话题。
9. **被动句的 by- 短语记 `Actor`**，主语记 `Goal`。
10. **片段**（"Nothing." / "What lovely fresh air!"）按最贴近的过程类型标注，不补主语。

## 构建时自动做的三处结构修正

`uamlib.build` 在返回前会修三类树形问题，标注时不必手动处理：

1. **前置环境段并入后随小句**：句首的环境成分（无谓体）后跟逗号、紧接一个小句时，
   把那个小句的起点前移到环境成分，环境段挂为其子段。
2. **关系小句并入前置名词段**：`that / which / who / whose / where / when / whereby` 开头的从属小句，
   挂到紧邻其前、跨度相接的名词性段上，并把名词段的 end 延到关系小句末尾。
   前置段带 `Identified`/`Identifier` 时不并——那是强调句 `it is X that Y`，不是关系小句。
3. **子段被同级兄弟完整包含时改挂**：只允许「小句挂到参与者段下」，反向不允许（防成环）。

## 常见判定争议

| 情形 | 处理 |
|---|---|
| `snow fell more quickly` | material + Range？不——`more quickly` 是 manner |
| `for Tibetan mastiffs`（价格/供应对象） | Range，不是 matter |
| `how big` | extent，不是 matter |
| `feel + 形容词` | mental，形容词作 Phenomenon |
| `be + 形容词` | relational attributive，形容词作 Attribute |
| `it is X that Y` | 强调句：X 记 Identified/Identifier，that-小句独立成段，不并入 |
| 标题（全大写行） | 通常不建段；若并入首句则按该句成分标 |
| 单独成句的呼语 `"Kelsang!"` | 不建段（无过程），覆盖率里体现为未覆盖 |

## 排错

`run_annotation.py` 干跑时报 `S12/Actor 未找到 'the man'` 之类：

1. 看它给出的区间原文（错误信息里带 `区间:`），确认拼写与换行
2. 常见是原文粘连（`theman`）或标点差异（`’` vs `'`）
3. 片段在同一句出现多次 → 加 `nth`
4. 跨句写错句号 → `--sent LO HI` 打印句子核对
5. 报「区间: '.'」+ 句子末尾的片段 → 母句跨度吞了后随小句，按上一节截开
