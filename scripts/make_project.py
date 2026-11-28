#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""从纯文本或 HTML 建一个 UAM CorpusTool 6 项目骨架（可多层 + 切句）

    # 默认建四层：及物性 / 态度 / 介入 / 级差
    python make_project.py --text "第三章.txt" --out "C:/.../项目/第三章" --name 第三章

    # 只建一层（旧用法）
    python make_project.py --text "第三章.txt" --out ".../第三章" --scheme transitivity
    python make_project.py --text "第三章.txt" --out ".../第三章" --scheme appraisal

    # 自选组合：--layer 层名:方案，可重复；只给层名时方案按名推断
    python make_project.py --text "第三章.txt" --out ".../第三章" \
        --layer 及物性:transitivity --layer 态度 --layer 介入

产出：
    Corpus/Texts/Text-1.txt              正文（每段一行）
    Schemes/<层名>.xml                    每层一份标注方案（从 assets/ 复制）
    <name>.ct3                            项目描述，内含多个 <layer>
    Annotations/Texts/Text-1.txt/Metadata.idx
    Annotations/Texts/Text-1.txt/<层名>.idx      空 idx（0 条记录，特征表与方案一致）
    Annotations/Texts/Text-1.txt/sentence.dat   每句 8 字节（起、止）

一个项目 = 一段语料 + 多层，共用同一份 Text-1.txt 与 sentence.dat；
在 UAM 的 Layer 面板里切层查看，各层独立标注、独立统计。

--html 适合 WPS/Word 导出的正文，会做视觉行→段落的还原；
--doc 直接吃 .doc/.docx/.rtf/.odt（内部调 doc_to_html.py，需 LibreOffice 或 pandoc）；
--text 适合已经清洗好的纯文本，一行一段。
"""
import os, re, sys, html, struct, shutil, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import apprlib                     # 方案表 + 空 idx 用的特征表
import uamlib
ASSETS = apprlib.ASSETS
ABBR = {'mr', 'mrs', 'ms', 'dr', 'st', 'jr', 'sr', 'prof', 'etc', 'e.g', 'i.e', 'vs', 'no'}


def lines_from_html(path):
    s = open(path, encoding='utf-8').read()
    s = re.sub(r'<head.*?</head>', '', s, flags=re.S | re.I)
    s = re.sub(r'<style.*?</style>', '', s, flags=re.S | re.I)
    s = re.sub(r'<script.*?</script>', '', s, flags=re.S | re.I)
    # LibreOffice/Word 的 HTML 标签是大写（<P CLASS="...">），必须忽略大小写
    blocks = re.findall(r'<(p|h[1-6]|li)\b[^>]*>(.*?)</\1>', s, flags=re.S | re.I)
    out = []
    for tag, inner in blocks:
        t = re.sub(r'<br\s*/?>', ' ', inner)
        t = re.sub(r'<[^>]+>', '', t)
        t = re.sub(r'\s+', ' ', html.unescape(t)).strip()
        if t:
            out.append(t)
    return out


def build_paragraphs(lines):
    """把 doc 导出的一行一视觉行还原成段落；开头连续全大写行作标题并入首段"""
    lines = list(lines)
    while lines and re.fullmatch(r'\d{1,3}', lines[0]):
        lines.pop(0)
    tl = []
    while lines:
        letters = [c for c in lines[0] if c.isalpha()]
        if len(letters) > 3 and all(c.isupper() for c in letters):
            tl.append(lines.pop(0))
        else:
            break
    paras, cur = [], ''
    for ln in lines:
        if not cur:
            cur = ln
            continue
        prev_end = cur.rstrip().endswith(('.', '!', '?', '.”', '…', '."', '!"'))
        starts = bool(re.match(r'^[A-Z“"‘’\'\-—]', ln))
        if prev_end and starts:
            paras.append(cur)
            cur = ln
        else:
            cur = cur + ' ' + ln
    if cur:
        paras.append(cur)
    if tl:
        paras.insert(0, ' '.join(tl))
    return paras


def strip_heading(lines):
    """去掉开头标题/小标题：连续全大写行，或首行短且无句末标点"""
    lines = list(lines)
    while lines and re.fullmatch(r'\d{1,3}', lines[0]):
        lines.pop(0)
    n = 0
    while n < len(lines):
        L = lines[n]
        letters = [c for c in L if c.isalpha()]
        if letters and len(L) <= 120 and all(c.isupper() for c in letters):
            n += 1
        else:
            break
    if n:
        return lines[n:]
    if len(lines) >= 2 and len(lines[0]) <= 80 \
            and not lines[0].rstrip().endswith(('.', '!', '?', '”', '…', '."', '!"', '?')):
        return lines[1:]
    return lines


def split_sentences(text):
    bounds, start, i, L = [], 0, 0, len(text)
    while i < L:
        c = text[i]
        if c in '.!?':
            j = i + 1
            while j < L and text[j] in '.!?':
                j += 1
            k = j
            while k < L and text[k] in '”’"\')]':
                k += 1
            if c == '.':
                w = re.search(r'([A-Za-z.]+)$', text[max(0, i - 12):i])
                if w:
                    tok = w.group(1)
                    if tok.lower().rstrip('.') in ABBR:
                        i += 1
                        continue
                    # 人名首字母：U. / I.K. / J. R. —— 不切句
                    if re.fullmatch(r'(?:[A-Z]\.)*[A-Z]', tok):
                        i += 1
                        continue
            n = k
            while n < L and text[n] in ' \n\t':
                n += 1
            if n >= L:
                bounds.append((start, L))
                start = L
                break
            nxt = text[n]
            if nxt.isupper() or nxt in '“”"‘’\'—–-(' or nxt.isdigit():
                bounds.append((start, k))
                start = k
                while start < L and text[start] in ' \n\t':
                    start += 1
                i = start
                continue
        i += 1
    if start < L:
        s = start
        while s < L and text[s] in ' \n\t':
            s += 1
        if s < L:
            bounds.append((s, L))
    return [(s, e) for s, e in bounds if text[s:e].strip()]


CT3_LAYER = """  <layer version='3'>
    <name>%(layer)s</name>
    <segtype>segment</segtype>
    <segmentation>none</segmentation>
    <autocode>None</autocode>
    <special>None</special>
    <scheme>%(scheme)s</scheme>
  </layer>
"""

CT3 = """<?xml version='1.0' encoding='utf-8'?>
<project>
  <ctversion>5.0</ctversion>

  <mediatype>text</mediatype>
%(layers)s</project>
"""


def resolve_layers(a):
    """--layer 名称:方案… > --scheme 单选 > 默认四层；返回 [(层名, 方案文件名)…]"""
    specs = a.layer or []
    if specs:
        out = []
        for sp in specs:
            if ':' in sp:
                nm, key = [x.strip() for x in sp.split(':', 1)]
                fn = apprlib.scheme_file(key)
                if not fn:
                    sys.exit('未知方案 %r（可选: %s）' % (key, ', '.join(apprlib.FAMILY)))
            else:
                nm = sp.strip()
                fn = apprlib.scheme_file(nm)
                if not fn:
                    sys.exit('认不出层名 %r（已知层名: %s；也可写 层名:方案）'
                             % (nm, ', '.join(apprlib.LAYER2SCHEME)))
            if not nm:
                sys.exit('层名不能为空：%r' % sp)
            out.append((nm, fn))
    elif a.scheme:
        fn = apprlib.scheme_file(a.scheme)
        out = [(apprlib.FAMILY[a.scheme][1], fn)]
    else:
        out = [(apprlib.FAMILY[k][1], apprlib.FAMILY[k][0])
               for k in apprlib.DEFAULT_LAYERS]
    names = [n for n, _ in out]
    dup = sorted({n for n in names if names.count(n) > 1})
    if dup:
        sys.exit('层名重复：%s（同一项目里层名必须唯一）' % '、'.join(dup))
    return out


def write_empty_idx(path, scheme_path):
    """空 idx：头部 + 特征表 + 0 条记录。UAM 打开即为空层，可直接开始标注。"""
    sch = apprlib.Scheme(scheme_path)
    old = list(uamlib.FEATURES)
    uamlib.set_features(sch.features)
    try:
        uamlib.write_idx(path, [])
    finally:
        uamlib.set_features(old)
    return len(sch.features)


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--text', help='纯文本（一行一段）')
    g.add_argument('--html', help='WPS/Word 导出的 HTML')
    g.add_argument('--doc', help='.doc/.docx/.rtf/.odt（先转 HTML，需 soffice 或 pandoc）')
    ap.add_argument('--out', required=True, help='项目目录')
    ap.add_argument('--name', help='项目名（默认取目录名），决定 .ct3 文件名')
    ap.add_argument('--wrap', action='store_true',
                    help='--text 时把视觉行（Word 导出的硬折行）还原成段落；一行一段的清洗稿不要加')
    ap.add_argument('--no-title', action='store_true',
                    help='丢掉开头标题/小标题行（新闻标题、编号，不属于正文）')
    ap.add_argument('--scheme', choices=list(apprlib.FAMILY),
                    help='只建一层时用：transitivity / appraisal / attitude / engagement / graduation')
    ap.add_argument('--layer', action='append', metavar='层名[:方案]',
                    help='要建的层，可重复；只给层名时方案按名推断。'
                         '默认四层：及物性 态度 介入 级差')
    a = ap.parse_args()
    layers = resolve_layers(a)

    if a.doc:
        import doc_to_html
        print('[doc]', a.doc, '→ HTML')
        a.html = doc_to_html.doc_to_html(a.doc)   # html 落在 doc 同目录

    if a.text:
        raw = open(a.text, encoding='utf-8').read().replace('\r\n', '\n').replace('\r', '\n')
        lines = [re.sub(r'\s+', ' ', x).strip() for x in raw.split('\n') if x.strip()]
        if a.no_title:
            lines = strip_heading(lines)
        paras = build_paragraphs(lines) if a.wrap else lines
    else:
        lines = lines_from_html(a.html)
        if a.no_title:
            lines = strip_heading(lines)
        paras = build_paragraphs(lines)

    text = '\n'.join(paras)
    out = os.path.abspath(a.out)
    name = a.name or os.path.basename(out.rstrip('/\\'))

    for sub in ['Corpus/Texts', 'Schemes', 'Annotations/Texts/Text-1.txt']:
        os.makedirs(os.path.join(out, sub), exist_ok=True)
    open(os.path.join(out, 'Corpus/Texts/Text-1.txt'), 'w', encoding='utf-8', newline='\n').write(text)
    open(os.path.join(out, 'Annotations/Texts/Text-1.txt/Metadata.idx'), 'wb').write(
        b'english\tutf-8\tArial\t14')

    blocks, nfeat = [], []
    for layer, fn in layers:
        src = os.path.join(ASSETS, fn)
        dst = os.path.join(out, 'Schemes', layer + '.xml')
        shutil.copy2(src, dst)
        n = write_empty_idx(os.path.join(out, 'Annotations/Texts/Text-1.txt', layer + '.idx'), dst)
        blocks.append(CT3_LAYER % dict(layer=layer, scheme=layer + '.xml'))
        nfeat.append((layer, fn, n))
    open(os.path.join(out, name + '.ct3'), 'w', encoding='utf-8', newline='\n').write(
        CT3 % dict(layers=''.join(blocks)))

    b = split_sentences(text)
    with open(os.path.join(out, 'Annotations/Texts/Text-1.txt/sentence.dat'), 'wb') as f:
        for s, e in b:
            f.write(struct.pack('2I', s, e))

    nums = re.findall(r'(?<![\w.,])\d{1,3}(?![\w.,])', text)
    hy = re.findall(r'\b[a-zA-Z]+-\s+[a-z][a-zA-Z]*', text)
    print('%-10s 字符 %6d 段 %4d 句 %4d 词 %5d | 裸数字 %d 断词 %d 双空格 %d'
          % (name, len(text), len(paras), len(b), len(text.split()),
             len(nums), len(hy), len(re.findall(r'  ', text))))
    print('  层 %d 个：%s' % (len(nfeat), ' / '.join('%s(%d 特征)' % (l, n) for l, _, n in nfeat)))
    for layer, fn, n in nfeat:
        print('    %-6s ← %-24s → Schemes/%s.xml + %s.idx（空）' % (layer, fn, layer, layer))
    print('  标题:', repr(paras[0][:60]))
    print('  首段:', repr(paras[1][:70]) if len(paras) > 1 else '')
    print('  末段:', repr(paras[-1][-70:]))
    if nums:
        print('  裸数字上下文:', [text[max(0, text.find(n) - 20):text.find(n) + 20].replace('\n', ' ')
                             for n in nums[:3]])
    print('项目 →', out)


if __name__ == '__main__':
    main()
