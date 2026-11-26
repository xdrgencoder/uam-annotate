# UAM CorpusTool 6 文件格式

逆向自 CT6 的 `Server/Common/Project/Codings.py`，并用「空标注写出的文件与 CT 原生文件字节一致」验证过。

## 项目结构

```
项目名/
├── 项目名.ct3                              # XML，层定义
├── Schemes/及物性.xml                       # 标注方案
├── Corpus/Texts/Text-1.txt                 # 正文（UTF-8）
└── Annotations/Texts/Text-1.txt/
    ├── Metadata.idx                        # english\tutf-8\tArial\t14
    ├── sentence.dat                        # 每句 8 字节
    └── 及物性.idx                           # 标注记录
```

### `<项目名>.ct3`

```xml
<?xml version='1.0' encoding='utf-8'?>
<project>
  <ctversion>5.0</ctversion>
  <mediatype>text</mediatype>
  <layer version='3'>
    <name>及物性</name>
    <segtype>segment</segtype>
    <segmentation>none</segmentation>
    <autocode>None</autocode>
    <special>None</special>
    <scheme>及物性.xml</scheme>
  </layer>
</project>
```

`<segmentation>none</segmentation>` 表示不做句内自动切段，全部手工标注——这是本流水线要的。

### `Metadata.idx`

一行，Tab 分隔：`english\tutf-8\tArial\t14`。

### `sentence.dat`

每句 8 字节，两个 little-endian `uint32`：`(start, end)`，**字符偏移**（不是字节偏移）。
句子按顺序排列，第 i 条就是句号 i。UAM 用它把标注段归到句子上。

## `及物性.idx`

### 头部 24 字节

```c
struct Header { uint32 intsNeeded; uint32 featLen; uint32 codLen;
                uint32 fieldLen;  uint32 roleLen;  uint32 commentLen; };
```

- `intsNeeded` — 位图需要几个 64 位整数；36 个特征 → 1
- `featLen` — 特征表字节长度
- `codLen` — 记录区字节长度（= 记录数 × 24）
- `fieldLen` — 恒为 0
- `roleLen` / `commentLen` — 角色区 / 注释区字节长度，0 表示没有

### 特征表

紧接头部，`;` 分隔的 UTF-8 特征名，顺序即位图的下标：

```
clause;material;mental;relational;verbal;behavioural;existential;perception;emotion;cognition;attributive;identifying;Actor;Goal;…
```

**这个顺序必须与 `Schemes/及物性.xml` 的声明顺序一致**，否则 UAM 打开会错位。

### 记录区（每条 24 字节）

```c
struct Coding {
  uint16 sid;      // 记录序号，1 起，全文唯一
  uint16 pid;      // 父记录 sid；0 = 句子级（顶层）
  uint32 start;    // 字符偏移
  uint32 end;
  uint8  flags;    // bit0 = 有 comment，bit1 常置 1
  uint8  pad[3];
  uint64 bitmap;   // 特征位图，bit i ↔ 特征表第 i 项
};
```

写入时必须先把前 13 字节 pack 出来、补 3 字节到 16，再接 8 字节位图——
`struct.pack('2H2IB', ...)` 天然只产生 13 字节，直接补 `b'\x00'*3` 即可。

`pid` 指向父段，构成树：句子级小句（pid=0）→ 参与者/环境段（pid=小句 sid）→ 嵌套子句（pid=成分 sid）→ …

### 角色区

若有 `roleLen`，是若干行 `sid\t角色标签`：

```
12	Actor
15	Location: Time
```

### 注释区

若有 `commentLen`，是若干行 `sid\t注释`，换行写作 `%NL`。

## 为什么必须写 role

CT 的盒子标签逻辑：`WrappedViewDraw → Codings.getBestLabel → Scheme.getBestLabel`，
后者只沿每个特征的**第一个子系统**下探，于是只有 PROCESS-TYPE 的特征能成为标签，
参与者段全显示成 `Clause`。

`getBestLabel` 第一行是：

```java
if (seg.role != null && !seg.role.isEmpty() && !seg.role.equals("Constituent"))
    return seg.role;
```

所以给参与者/环境段写 role（`Actor`、`Goal`、`Location: Time`…）就能正确显示。
副作用：这些图层被识别为「带 role 的层」，在 GUI 里新建片段默认填 `???`，需手改。

## 常见崩溃

| 现象 | 原因 |
|---|---|
| 打开项目报错 / 标注全错位 | 特征表顺序与 scheme 不一致 |
| 段挂错句子 | `sentence.dat` 与 `Text-1.txt` 偏移不匹配（换行被吞/多加） |
| 末句重复 | 切句器在「句末即文末」分支里 `bounds.append((start, L))` 后没推进 `start` |
| 只显示 Clause | 缺 role 字段（见上） |
| 记录数超 65,535 后乱码 | sid/pid 是 u16，溢出 |
