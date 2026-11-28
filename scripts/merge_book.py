#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把若干分章 UAM 项目合并成一本完整的书（单 text，每层一个 idx）

    # 多层项目：默认合并首章 .ct3 里声明的全部层
    python merge_book.py --base "C:/.../项目" \
        --chapters 第一章 第二章 ... --out 全书

    # 只合并指定层
    python merge_book.py --base ".../项目" --chapters 第一章 第二章 \
        --out 全书 --layer 及物性 态度 介入 级差

合并原理（纯坐标平移，不动任何标签）：
    文本      按章序首尾相接，章末缺换行的补一个 \\n
    sentence  每句 8 字节（起、止）整块搬，start/end 加本章字符偏移
    idx 记录  逐层合并：sid 加本章记录基数；pid==0 保持 0，否则同样加基数；
              start/end 加字符偏移；特征位图与 role 原样搬运
层        文字的映射只做一次（文本与切句各层共用），记录按层各自平移。
某层在全部章节里都没有 idx 时，输出空 idx，保证 .ct3 声明的层都有文件。
"""
import os, re, sys, struct, shutil, argparse, bisect
from collections import Counter, OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import uamlib
import apprlib

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


def layers_of(proj):
    """读 .ct3 里声明的层，返回 [(层名, 方案文件名)…]（按文档顺序）"""
    ct3 = [f for f in sorted(os.listdir(proj)) if f.endswith('.ct3')]
    if not ct3:
        return []
    s = open(os.path.join(proj, ct3[0]), encoding='utf-8').read()
    out = []
    for blk in re.findall(r'<layer\b[^>]*>(.*?)</layer>', s, re.S):
        nm = re.search(r'<name>(.*?)</name>', blk, re.S)
        sc = re.search(r'<scheme>(.*?)</scheme>', blk, re.S)
        if nm:
            name = nm.group(1).strip()
            out.append((name, sc.group(1).strip() if sc else name + '.xml'))
    return out


def layer_features(layer, scheme_path):
    """及物性优先用内置特征表（历史 idx 就是按它写的）；其他层按 Schemes/<层名>.xml 解析"""
    if layer == '及物性' and not (scheme_path and os.path.exists(scheme_path)):
        return list(uamlib.FEATURES), None
    if not scheme_path or not os.path.exists(scheme_path):
        sys.exit('找不到方案文件：%s（用 --scheme 指定，或先跑 make_project 建层）' % scheme_path)
    sch = apprlib.Scheme(scheme_path)
    return sch.features, sch


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', required=True, help='放各章项目的目录')
    ap.add_argument('--chapters', nargs='+', required=True, help='按合并顺序排列的章目录名')
    ap.add_argument('--out', required=True, help='输出项目目录（相对 --base 或绝对路径）')
    ap.add_argument('--layer', nargs='+',
                    help='要合并的层（可多个）；默认取首章 .ct3 里声明的全部层')
    ap.add_argument('--scheme-from', help='从哪个章项目取方案 xml（默认第一个章）')
    ap.add_argument('--force', action='store_true', help='输出目录已存在时先删掉')
    a = ap.parse_args()

    base = os.path.abspath(a.base)
    out = a.out if os.path.isabs(a.out) else os.path.join(base, a.out)
    name = os.path.basename(out.rstrip('/\\'))
    src_ch = a.scheme_from or a.chapters[0]
    src = os.path.join(base, src_ch)

    declared = layers_of(src)
    if a.layer:
        layers = [(n, dict(declared).get(n, n + '.xml')) for n in a.layer]
    elif declared:
        layers = declared
    else:
        layers = [('及物性', '及物性.xml')]
    if not layers:
        sys.exit('没有可合并的层')

    # ---------------------------------------------------------------- 文本与切句
    texts, sents, info = [], [], []
    off = 0
    for i, ch in enumerate(a.chapters):
        p = os.path.join(base, ch)
        t = open(os.path.join(p, 'Corpus/Texts/Text-1.txt'), encoding='utf-8').read()
        if i < len(a.chapters) - 1 and not t.endswith('\n'):
            t += '\n'
        d = open(os.path.join(p, 'Annotations/Texts/Text-1.txt/sentence.dat'), 'rb').read()
        b = [struct.unpack('2I', d[k * 8:(k + 1) * 8]) for k in range(len(d) // 8)]
        texts.append(t)
        sents.append([(s + off, e + off) for s, e in b])
        info.append((ch, off, off + len(t), len(b)))
        off += len(t)
    book = ''.join(texts)
    assert len(book) == off
    allb = [b for x in sents for b in x]

    # ---------------------------------------------------------------- 逐层合并记录
    merged = OrderedDict()
    for layer, scheme_name in layers:
        scheme_path = os.path.join(src, 'Schemes', scheme_name)
        if not os.path.exists(scheme_path):
            scheme_path = os.path.join(src, 'Schemes', layer + '.xml')
        feats, sch = layer_features(layer, scheme_path)
        recs, base_rec, have, detail = [], 0, 0, []
        for ch, lo, hi, nseg in info:
            idx = os.path.join(base, ch, 'Annotations/Texts/Text-1.txt', layer + '.idx')
            if not os.path.exists(idx):
                detail.append((ch, 0, 0))
                continue
            r, f0 = uamlib.read_idx(idx)
            if f0 != list(feats):
                sys.exit('%s 的 %s 特征表与方案不符（%d vs %d 项），不能混方案合并'
                         % (ch, layer, len(f0), len(feats)))
            for x in r:
                y = dict(x)
                y['start'] += lo
                y['end'] += lo
                y['sid'] += base_rec
                if y['pid']:
                    y['pid'] += base_rec
                recs.append(y)
            detail.append((ch, len(r), base_rec))
            base_rec += len(r)
            have += 1
        merged[layer] = dict(feats=feats, sch=sch, recs=recs,
                             scheme=scheme_name, have=have, detail=detail)

    # ---------------------------------------------------------------- 写盘
    if os.path.isdir(out) and os.listdir(out):
        if not a.force:
            sys.exit('输出目录非空：%s（加 --force 覆盖）' % out)
        shutil.rmtree(out)
    for sub in ['Corpus/Texts', 'Schemes', 'Annotations/Texts/Text-1.txt']:
        os.makedirs(os.path.join(out, sub), exist_ok=True)

    open(os.path.join(out, 'Corpus/Texts/Text-1.txt'), 'w', encoding='utf-8', newline='\n').write(book)
    open(os.path.join(out, 'Annotations/Texts/Text-1.txt/Metadata.idx'), 'wb').write(
        b'english\tutf-8\tArial\t14')
    with open(os.path.join(out, 'Annotations/Texts/Text-1.txt/sentence.dat'), 'wb') as f:
        for s, e in allb:
            f.write(struct.pack('2I', s, e))

    blocks = []
    for layer, m in merged.items():
        sp = os.path.join(src, 'Schemes', m['scheme'])
        if not os.path.exists(sp):
            sp = os.path.join(src, 'Schemes', layer + '.xml')
        if os.path.exists(sp):
            shutil.copy2(sp, os.path.join(out, 'Schemes', layer + '.xml'))
            m['scheme'] = layer + '.xml'
        blocks.append(CT3_LAYER % dict(layer=layer, scheme=m['scheme']))
        old = list(uamlib.FEATURES)
        uamlib.set_features(m['feats'])
        try:
            uamlib.write_idx(os.path.join(out, 'Annotations/Texts/Text-1.txt', layer + '.idx'),
                             m['recs'])
            back, _ = uamlib.read_idx(
                os.path.join(out, 'Annotations/Texts/Text-1.txt', layer + '.idx'))
        finally:
            uamlib.set_features(old)
        assert len(back) == len(m['recs']), '回读条数不符（%s）' % layer
    open(os.path.join(out, name + '.ct3'), 'w', encoding='utf-8', newline='\n').write(
        CT3 % dict(layers=''.join(blocks)))

    # ---------------------------------------------------------------- 校验
    print('章        起        止    句')
    for ch, x, y, k in info:
        print('  %-8s %8d %8d %5d' % (ch, x, y, k))
    print('全书 字符 %d · 句 %d · 层 %d' % (len(book), len(allb), len(merged)))

    sstarts = [s for s, _ in allb]

    def sent_of(x):
        k = bisect.bisect_right(sstarts, x) - 1
        if k < 0:
            return -1
        s, e = allb[k]
        return k if s <= x < e else -1

    print('\n层      记录   方案           结构校验')
    bad_total = 0
    for layer, m in merged.items():
        recs = m['recs']
        assert len(recs) < 65535, '%s 的 sid 是 u16，记录数超上限 65535' % layer
        byid = {r['sid']: r for r in recs}
        assert len(byid) == len(recs), '%s 的 sid 重复' % layer
        bad_span = [r for r in recs if not (0 <= r['start'] < r['end'] <= len(book))]
        bad_par = [r for r in recs if r['pid'] and r['pid'] not in byid]
        bad_nest = [r for r in recs if r['pid'] in byid and
                    not (byid[r['pid']]['start'] <= r['start'] and r['end'] <= byid[r['pid']]['end'])]
        bad_sent = [r for r in recs if sent_of(r['start']) < 0]
        nbad = len(bad_span) + len(bad_par) + len(bad_nest) + len(bad_sent)
        bad_total += nbad
        sch = m['sch']
        nf = '%d 特征' % (len(m['feats']))
        if sch:
            nf += ' / %d 系统' % len(sch.systems)
        tag = ('越界 %d · 父段失效 %d · 父段未包住 %d · 不属任何句 %d'
               % (len(bad_span), len(bad_par), len(bad_nest), len(bad_sent)))
        print('  %-6s %6d   %-14s %s' % (layer, len(recs), nf, tag if nbad else '✓'))
        if not m['have']:
            print('        （各章都没有 %s.idx，输出空层）' % layer)

    for layer, m in merged.items():
        recs = m['recs']
        if not recs:
            continue
        cov = sum(r['end'] - r['start'] for r in recs if r['pid'] == 0)
        print('\n[%s] 顶层覆盖 %.1f%%' % (layer, 100.0 * cov / len(book)))
        if layer == '及物性':
            tops = Counter(sent_of(r['start']) for r in recs if r['pid'] == 0)
            no_clause = [k for k in range(len(allb)) if tops.get(k, 0) == 0]
            multi = sum(1 for v in tops.values() if v != 1)
            nproc = sum(1 for r in recs if any(f in uamlib.PROC_FEATS for f in r['feats']))
            nrole = sum(1 for r in recs if any(f in uamlib.ROLE_FEATS for f in r['feats']))
            ncirc = sum(1 for r in recs if any(f in uamlib.CIRC_FEATS for f in r['feats']))
            print('  无 clause 的句 %d（标题/呼语属正常）· 多 clause 的句 %d'
                  % (len(no_clause), multi))
            print('  系统互斥：过程 %d + 参与者 %d + 环境 %d = %d（段 %d）%s'
                  % (nproc, nrole, ncirc, nproc + nrole + ncirc, len(recs),
                     '✓' if nproc + nrole + ncirc == len(recs) else '✗'))
            assert nproc + nrole + ncirc == len(recs), '三系统之和与段数不符'
        elif m['sch']:
            hit = Counter(f for r in recs for f in r['feats'])
            empty = [nm for nm, (ec, fs) in m['sch'].systems.items()
                     if not any(hit.get(f) for f in fs)]
            print('  未出现的系统 %d / %d%s'
                  % (len(empty), len(m['sch'].systems),
                     ('：' + '、'.join(empty[:6])) if empty else ''))

    assert bad_total == 0, '结构校验未通过'
    print('\n输出 →', out)


if __name__ == '__main__':
    main()
