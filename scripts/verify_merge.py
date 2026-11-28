#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""合并校验：把合并后的书按章切回，与各分章项目逐条比对（可多层）

    python verify_merge.py --base "C:/.../项目" \\
        --book 全书 --chapters 第一章 第二章 ... 第十二章

    只比对某几层：
    python verify_merge.py --base ".../项目" --book 全书 \\
        --chapters 第一章 第二章 --layer 及物性 态度

比对项：整章文本、句子边界；每层各自比对条数、sid、pid、start、end、特征集合、role。
"""
import os, sys, struct, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import uamlib
from merge_book import layers_of


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', required=True)
    ap.add_argument('--book', required=True, help='合并后的项目目录名或绝对路径')
    ap.add_argument('--chapters', nargs='+', required=True)
    ap.add_argument('--layer', nargs='+',
                    help='要比对的层（可多个）；默认取书 .ct3 里声明的全部层')
    a = ap.parse_args()

    base = os.path.abspath(a.base)
    bk = a.book if os.path.isabs(a.book) else os.path.join(base, a.book)
    book = open(os.path.join(bk, 'Corpus/Texts/Text-1.txt'), encoding='utf-8').read()
    d = open(os.path.join(bk, 'Annotations/Texts/Text-1.txt/sentence.dat'), 'rb').read()
    b1_all = [struct.unpack('2I', d[k * 8:(k + 1) * 8]) for k in range(len(d) // 8)]

    layers = a.layer or [nm for nm, _ in layers_of(bk)] or ['及物性']
    print('层：%s' % ' / '.join(layers))

    ok = True
    # ---------------------------------------------------------------- 文本与句子
    pos, spans = 0, []
    for ch in a.chapters:
        p = os.path.join(base, ch)
        t = open(os.path.join(p, 'Corpus/Texts/Text-1.txt'), encoding='utf-8').read()
        if book[pos:pos + len(t)] != t:
            print('[文本] %s 不一致（偏移 %d）' % (ch, pos))
            ok = False
        d0 = open(os.path.join(p, 'Annotations/Texts/Text-1.txt/sentence.dat'), 'rb').read()
        b0 = [struct.unpack('2I', d0[k * 8:(k + 1) * 8]) for k in range(len(d0) // 8)]
        mine = [(s, e) for s, e in b1_all if pos <= s < pos + len(t)]
        if [(s - pos, e - pos) for s, e in mine] != b0:
            print('[句子] %s 不一致（%d vs %d）' % (ch, len(mine), len(b0)))
            ok = False
        spans.append((ch, pos, len(t), len(b0)))
        pos += len(t) + (1 if not t.endswith('\n') else 0)

    # ---------------------------------------------------------------- 逐层比对记录
    for layer in layers:
        idx_name = layer + '.idx'
        bp = os.path.join(bk, 'Annotations/Texts/Text-1.txt', idx_name)
        if not os.path.exists(bp):
            print('[缺文件] 书里没有 %s' % idx_name)
            ok = False
            continue
        recs, _ = uamlib.read_idx(bp)
        print('\n层 %s（书 %d 条）' % (layer, len(recs)))
        base_rec = 0
        for ch, pos, tlen, nseg in spans:
            p = os.path.join(base, ch, 'Annotations/Texts/Text-1.txt', idx_name)
            if not os.path.exists(p):
                print('  %-8s 无 %s（空层）' % (ch, idx_name))
                continue
            r0, _ = uamlib.read_idx(p)
            mine = [x for x in recs if pos <= x['start'] < pos + tlen]
            bad = 0
            if len(mine) != len(r0):
                print('  [条数] %s %d vs %d' % (ch, len(mine), len(r0)))
                bad += 1
            for a_, b_ in zip(r0, mine):
                good = (b_['sid'] - base_rec == a_['sid']
                        and (b_['pid'] == 0 if a_['pid'] == 0 else b_['pid'] - base_rec == a_['pid'])
                        and b_['start'] - pos == a_['start'] and b_['end'] - pos == a_['end']
                        and sorted(b_['feats']) == sorted(a_['feats'])
                        and b_['role'] == a_['role'])
                if not good:
                    bad += 1
                    if bad <= 2:
                        print('    [差异] sid%d %r → %r' % (a_['sid'], a_, b_))
            if bad:
                ok = False
            print('  %-8s 字符 %6d 条 %4d 句 %4d  %s'
                  % (ch, tlen, len(mine), nseg, '✓' if not bad else '✗'))
            base_rec += len(r0)

    print('\n结论：', '全部一致' if ok else '存在差异')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
