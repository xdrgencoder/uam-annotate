#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""合并校验：把合并后的书按章切回，与各分章项目逐条比对

    python verify_merge.py --base "C:/.../斯日古冷UAM项目" \
        --book 斯日古冷_全书 --chapters 斯日古冷 第二章 ... 第十二章

比对项：整章文本、条数、sid、pid、start、end、特征集合、role、句子边界。
"""
import os, sys, struct, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import uamlib


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', required=True)
    ap.add_argument('--book', required=True, help='合并后的项目目录名或绝对路径')
    ap.add_argument('--chapters', nargs='+', required=True)
    a = ap.parse_args()

    base = os.path.abspath(a.base)
    bk = a.book if os.path.isabs(a.book) else os.path.join(base, a.book)
    book = open(os.path.join(bk, 'Corpus/Texts/Text-1.txt'), encoding='utf-8').read()
    d = open(os.path.join(bk, 'Annotations/Texts/Text-1.txt/sentence.dat'), 'rb').read()
    recs, _ = uamlib.read_idx(os.path.join(bk, 'Annotations/Texts/Text-1.txt/及物性.idx'))

    ok = True
    pos = base_rec = 0
    for ch in a.chapters:
        p = os.path.join(base, ch)
        t = open(os.path.join(p, 'Corpus/Texts/Text-1.txt'), encoding='utf-8').read()
        if book[pos:pos + len(t)] != t:
            print('[文本] %s 不一致' % ch)
            ok = False

        r0, _ = uamlib.read_idx(os.path.join(p, 'Annotations/Texts/Text-1.txt/及物性.idx'))
        mine = [x for x in recs if pos <= x['start'] < pos + len(t)]
        # 章末补的换行会让最后一字符落在 seg 外，这里按 start 归属即可
        if len(mine) != len(r0):
            print('[条数] %s %d vs %d' % (ch, len(mine), len(r0)))
            ok = False
        diff = 0
        for a_, b_ in zip(r0, mine):
            good = (b_['sid'] - base_rec == a_['sid']
                    and (b_['pid'] == 0 if a_['pid'] == 0 else b_['pid'] - base_rec == a_['pid'])
                    and b_['start'] - pos == a_['start'] and b_['end'] - pos == a_['end']
                    and sorted(b_['feats']) == sorted(a_['feats'])
                    and b_['role'] == a_['role'])
            if not good:
                diff += 1
                if diff <= 2:
                    print('  [差异] %s sid%d %r → %r' % (ch, a_['sid'], a_, b_))
        if diff:
            print('[记录] %s 差异 %d 条' % (ch, diff))
            ok = False

        d0 = open(os.path.join(p, 'Annotations/Texts/Text-1.txt/sentence.dat'), 'rb').read()
        b0 = [struct.unpack('2I', d0[k * 8:(k + 1) * 8]) for k in range(len(d0) // 8)]
        b1 = [struct.unpack('2I', d[k * 8:(k + 1) * 8]) for k in range(len(d) // 8)]
        b1 = [(s, e) for s, e in b1 if pos <= s < pos + len(t)]
        if [(s - pos, e - pos) for s, e in b1] != b0:
            print('[句子] %s 不一致（%d vs %d）' % (ch, len(b1), len(b0)))
            ok = False

        print('%-8s %6d 字符 %6d 条 %4d 句  %s'
              % (ch, len(t), len(mine), len(b0), '✓' if ok else '✗'))
        pos += len(t) + (1 if not t.endswith('\n') else 0)
        base_rec += len(r0)

    print('\n结论：', '全部一致' if ok else '存在差异')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
