#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生成 ANN 骨架：把句子编号和原文先排好，标注时只填过程类型与角色

    python scripts/ann_skeleton.py --project ./项目/第四章 --sent 0 40
    python scripts/ann_skeleton.py --project ./项目/第四章 --sent 0 40 --prefix c4_a --write

--write 会写 <project>/<prefix>_a.py；不写则只打印到屏幕。
骨架里每句是空列表，注释是该句原文（截 96 字符），照抄片段可避免定位错误。
"""
import os, sys, argparse, re

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import annlib

sys.dont_write_bytecode = True   # 不往项目目录里落 __pycache__


def skeleton(p, lo, hi, width=96):
    lines = ['# -*- coding: utf-8 -*-',
             '# 由 ann_skeleton.py 生成：把每句的 [] 换成小句元组列表',
             'ANN = {']
    for i in range(lo, min(hi, len(p.bounds))):
        s = p.sent(i)
        cm = s if len(s) <= width else s[:width - 1] + '…'
        cm = re.sub(r'\s+', ' ', cm)
        lines.append('    %d: [],   # %s' % (i, cm))
    lines.append('}')
    return '\n'.join(lines) + '\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--project', required=True, help='项目目录')
    ap.add_argument('--sent', nargs=2, type=int, metavar=('LO', 'HI'), required=True,
                    help='句子区间 [LO, HI)')
    ap.add_argument('--prefix', help='写出文件名前缀，如 c4_a（配 --write）')
    ap.add_argument('--write', action='store_true', help='写到项目目录而不是只打印')
    a = ap.parse_args()

    proj = os.path.abspath(a.project)
    if not os.path.isdir(proj):
        sys.exit('项目目录不存在: %s' % proj)
    p = annlib.Proj(proj)
    if a.sent[0] < 0 or a.sent[0] >= a.sent[1]:
        sys.exit('--sent 区间不合法（需 LO < HI）')
    code = skeleton(p, *a.sent)

    if a.write:
        if not a.prefix:
            sys.exit('--write 需要同时给 --prefix（如 c4_a）')
        dst = os.path.join(proj, a.prefix + '.py')
        open(dst, 'w', encoding='utf-8', newline='\n').write(code)
        print('写出', dst)
    else:
        sys.stdout.write(code)


if __name__ == '__main__':
    main()
