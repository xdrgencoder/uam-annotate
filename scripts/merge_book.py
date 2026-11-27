#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把若干分章 UAM 项目合并成一本完整的书（单 text、单 idx）

    # 及物性层
    python merge_book.py --base "C:/.../斯日古冷UAM项目" \
        --chapters 斯日古冷 第二章 第三章 ... 第十二章 --out 斯日古冷_全书

    # 评价层（层名换成 评价，特征表按方案自动切换）
    python merge_book.py --base ".../评价项目" --chapters 第一章 第二章 \
        --out 评价全书 --layer 评价

合并原理（纯坐标平移，不动任何标签）：
    文本      按章序首尾相接，章末缺换行的补一个 \\n
    sentence  每句 8 字节（起、止）整块搬，start/end 加本章字符偏移
    idx 记录  sid 加本章记录基数；pid==0 保持 0，否则同样加基数；
              start/end 加字符偏移；特征位图与 role 原样搬运
"""
import os, sys, struct, argparse, bisect
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import uamlib

CT3 = """<?xml version='1.0' encoding='utf-8'?>
<project>
  <ctversion>5.0</ctversion>

  <mediatype>text</mediatype>
  <layer version='3'>
    <name>%(layer)s</name>
    <segtype>segment</segtype>
    <segmentation>none</segmentation>
    <autocode>None</autocode>
    <special>None</special>
    <scheme>%(scheme)s</scheme>
  </layer>
</project>
"""


def layer_features(layer, scheme_path):
    """及物性用内置特征表（历史 idx 就是按它写的）；其他层按 Schemes/<层名>.xml 解析"""
    if layer == '及物性':
        return list(uamlib.FEATURES), None
    if not scheme_path or not os.path.exists(scheme_path):
        sys.exit('找不到方案文件：%s（用 --scheme 指定）' % scheme_path)
    import apprlib
    sch = apprlib.Scheme(scheme_path)
    return sch.features, sch


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', required=True, help='放各章项目的目录')
    ap.add_argument('--chapters', nargs='+', required=True, help='按合并顺序排列的章目录名')
    ap.add_argument('--out', required=True, help='输出项目目录（相对 --base 或绝对路径）')
    ap.add_argument('--layer', default='及物性', help='层名（决定 idx 文件名，默认 及物性）')
    ap.add_argument('--scheme-from', help='从哪个章项目取方案 xml（默认第一个章）')
    ap.add_argument('--scheme', help='方案 xml 路径（默认取 <scheme-from>/Schemes/<层名>.xml）')
    ap.add_argument('--force', action='store_true', help='输出目录已存在时先删掉')
    a = ap.parse_args()

    base = os.path.abspath(a.base)
    out = a.out if os.path.isabs(a.out) else os.path.join(base, a.out)
    name = os.path.basename(out.rstrip('/\\'))
    src_ch = a.scheme_from or a.chapters[0]
    scheme_path = a.scheme or os.path.join(base, src_ch, 'Schemes', a.layer + '.xml')
    feats, sch = layer_features(a.layer, scheme_path)
    idx_name = a.layer + '.idx'

    texts, sents, recs, info = [], [], [], []
    off = base_rec = 0
    for i, ch in enumerate(a.chapters):
        p = os.path.join(base, ch)
        t = open(os.path.join(p, 'Corpus/Texts/Text-1.txt'), encoding='utf-8').read()
        if i < len(a.chapters) - 1 and not t.endswith('\n'):
            t += '\n'
        d = open(os.path.join(p, 'Annotations/Texts/Text-1.txt/sentence.dat'), 'rb').read()
        b = [struct.unpack('2I', d[k * 8:(k + 1) * 8]) for k in range(len(d) // 8)]
        r, f0 = uamlib.read_idx(os.path.join(p, 'Annotations/Texts/Text-1.txt', idx_name))
        if f0 != list(feats):
            sys.exit('%s 的特征表与方案不符（%d vs %d 项），不能混方案合并'
                     % (ch, len(f0), len(feats)))

        texts.append(t)
        sents.append([(s + off, e + off) for s, e in b])
        for x in r:
            y = dict(x)
            y['start'] += off
            y['end'] += off
            y['sid'] += base_rec
            if y['pid']:
                y['pid'] += base_rec
            recs.append(y)
        info.append((ch, off, off + len(t), len(r), len(b)))
        off += len(t)
        base_rec += len(r)

    book = ''.join(texts)
    assert len(book) == off

    if os.path.isdir(out) and os.listdir(out):
        if not a.force:
            sys.exit('输出目录非空：%s（加 --force 覆盖）' % out)
        import shutil
        shutil.rmtree(out)
    for sub in ['Corpus/Texts', 'Schemes', 'Annotations/Texts/Text-1.txt']:
        os.makedirs(os.path.join(out, sub), exist_ok=True)

    import shutil
    open(os.path.join(out, 'Corpus/Texts/Text-1.txt'), 'w', encoding='utf-8', newline='\n').write(book)
    shutil.copy2(scheme_path, os.path.join(out, 'Schemes', a.layer + '.xml'))
    open(os.path.join(out, name + '.ct3'), 'w', encoding='utf-8', newline='\n').write(
        CT3 % dict(layer=a.layer, scheme=a.layer + '.xml'))
    open(os.path.join(out, 'Annotations/Texts/Text-1.txt/Metadata.idx'), 'wb').write(
        b'english\tutf-8\tArial\t14')

    allb = [b for x in sents for b in x]
    with open(os.path.join(out, 'Annotations/Texts/Text-1.txt/sentence.dat'), 'wb') as f:
        for s, e in allb:
            f.write(struct.pack('2I', s, e))
    old = list(uamlib.FEATURES)
    uamlib.set_features(feats)
    try:
        uamlib.write_idx(os.path.join(out, 'Annotations/Texts/Text-1.txt', idx_name), recs)
        back, _ = uamlib.read_idx(os.path.join(out, 'Annotations/Texts/Text-1.txt', idx_name))
    finally:
        uamlib.set_features(old)
    assert len(back) == len(recs), '回读条数不符'

    # ---------------------------------------------------------------- 校验
    print('章        起        止    记录   句')
    for ch, x, y, n, k in info:
        print('  %-8s %8d %8d %6d %5d' % (ch, x, y, n, k))
    print('全书 字符 %d · 句 %d · 段 %d · 层 %s' % (len(book), len(allb), len(recs), a.layer))
    assert len(recs) < 65535, 'sid 是 u16，记录数超上限 65535'

    byid = {r['sid']: r for r in recs}
    assert len(byid) == len(recs), 'sid 重复'
    bad_span = [r for r in recs if not (0 <= r['start'] < r['end'] <= len(book))]
    bad_par = [r for r in recs if r['pid'] and r['pid'] not in byid]
    bad_nest = [r for r in recs if r['pid'] in byid and
                not (byid[r['pid']]['start'] <= r['start'] and r['end'] <= byid[r['pid']]['end'])]
    sstarts = [s for s, _ in allb]

    def sent_of(x):
        k = bisect.bisect_right(sstarts, x) - 1
        if k < 0:
            return -1
        s, e = allb[k]
        return k if s <= x < e else -1

    bad_sent = [r for r in recs if sent_of(r['start']) < 0]
    cov = sum(r['end'] - r['start'] for r in recs if r['pid'] == 0)
    print('越界 %d · 父段失效 %d · 父段未包住 %d · 不属任何句 %d'
          % (len(bad_span), len(bad_par), len(bad_nest), len(bad_sent)))
    print('顶层覆盖 %.1f%%' % (100.0 * cov / len(book)))

    if a.layer == '及物性':
        tops = Counter(sent_of(r['start']) for r in recs if r['pid'] == 0)
        no_clause = [k for k in range(len(allb)) if tops.get(k, 0) == 0]
        multi = sum(1 for v in tops.values() if v != 1)
        nproc = sum(1 for r in recs if any(f in uamlib.PROC_FEATS for f in r['feats']))
        nrole = sum(1 for r in recs if any(f in uamlib.ROLE_FEATS for f in r['feats']))
        ncirc = sum(1 for r in recs if any(f in uamlib.CIRC_FEATS for f in r['feats']))
        print('无 clause 的句 %d（标题/呼语属正常）· 多 clause 的句 %d' % (len(no_clause), multi))
        print('系统互斥：过程 %d + 参与者 %d + 环境 %d = %d（段 %d）%s'
              % (nproc, nrole, ncirc, nproc + nrole + ncirc, len(recs),
                 '✓' if nproc + nrole + ncirc == len(recs) else '✗'))
        assert nproc + nrole + ncirc == len(recs), '三系统之和与段数不符'
    else:
        hit = Counter(f for r in recs for f in r['feats'])
        empty = [nm for nm, (ec, fs) in sch.systems.items() if not any(hit.get(f) for f in fs)]
        print('方案 %d 系统 · 全书未出现的系统 %d 个%s'
              % (len(sch.systems), len(empty), ('：' + '、'.join(empty[:6])) if empty else ''))

    assert not bad_span and not bad_par and not bad_nest and not bad_sent, '结构校验未通过'
    print('输出 →', out)


if __name__ == '__main__':
    main()
