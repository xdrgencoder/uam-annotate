#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""跑一个章节的标注：导入 ANN 模块 → 构建 → 校验 → 写 idx → 导出 xlsx/TSV/HTML

    # 先看句子
    python run_annotation.py --project "C:/.../斯日古冷UAM项目/第四章" --sent 0 20
    # 干跑（不写盘）
    python run_annotation.py --project ".../第四章" --ann-prefix c4
    # 校验通过后落盘并导出三种复核件
    python run_annotation.py --project ".../第四章" --ann-prefix c4 --write
    # 只写 idx，不出 xlsx/html
    python run_annotation.py --project ".../第四章" --ann-prefix c4 --write --no-export

标注模块放在项目目录里（或 PYTHONPATH 上），命名 <prefix>_a.py、<prefix>_b.py …，
每个模块导出 ANN = {句号: [小句, 小句, …]}，小句结构见 references/annotation-conventions.md。
"""
import os, sys, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import annlib

sys.dont_write_bytecode = True   # 不往项目目录里落 __pycache__


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--project', required=True, help='项目目录（含 Corpus/ 与 Annotations/）')
    ap.add_argument('--ann-prefix', help='标注模块前缀，如 c4 → c4_a.py c4_b.py …')
    ap.add_argument('--ann-dir', help='标注模块所在目录（默认项目目录）')
    ap.add_argument('--layer', default='及物性',
                    help='层名（决定 idx 与复核件名，默认 及物性）')
    ap.add_argument('--write', action='store_true', help='校验通过后写入 <层名>.idx')
    ap.add_argument('--no-export', action='store_true', help='不生成 xlsx/TSV/HTML')
    ap.add_argument('--sent', nargs=2, type=int, metavar=('LO', 'HI'), help='打印句子区间后退出')
    ap.add_argument('--allow-errors', action='store_true', help='有定位错误也继续（仅打印）')
    ap.add_argument('--out', help='复核件输出目录（默认当前目录）')
    a = ap.parse_args()

    proj_dir = os.path.abspath(a.project)
    if not os.path.isdir(proj_dir):
        sys.exit('项目目录不存在: %s' % proj_dir)
    sys.path.insert(0, proj_dir)
    if a.ann_dir:
        sys.path.insert(0, os.path.abspath(a.ann_dir))
    p = annlib.Proj(proj_dir, out=os.path.abspath(a.out) if a.out else os.getcwd(),
                    layer=a.layer)

    if a.sent:
        lo, hi = a.sent
        for i in range(lo, min(hi, len(p.bounds))):
            print('%d|%s' % (i, p.sent(i)))
        return

    if not a.ann_prefix:
        sys.exit('需要 --ann-prefix（或只用 --sent 看句子）')

    ann, mods = p.load_ann(a.ann_prefix)
    if not ann:
        sys.exit('没找到 %s_*.py，确认模块在 %s 里' % (a.ann_prefix, proj_dir))
    missing = [i for i in range(len(p.bounds)) if i not in ann]
    print('模块 %s' % ' '.join(mods))
    print('已标 %d 句 / 共 %d 句%s'
          % (len(ann), len(p.bounds), ('，未标: %s' % missing[:20]) if missing else ''))

    recs, tab, errs = p.check(ann)
    print('段 %d · 小句 %d' % (len(recs), sum(1 for r in recs
                                              if any(f in annlib.uamlib.PROC_FEATS for f in r['feats']))))
    if errs:
        print('定位错误 %d 条：' % len(errs))
        for e in errs[:20]:
            print('  -', e)
        if not a.allow_errors:
            sys.exit('先修好定位错误再写盘（或加 --allow-errors 仅查看）')

    v = p.validate(recs)
    print('校验：' + ' · '.join('%s %s' % (k, ('%.1f%%' % x) if k == '覆盖率' else x)
                              for k, x in v.items()))
    bad = {k: x for k, x in v.items() if k != '覆盖率' and x}
    if bad:
        sys.exit('结构校验未通过：%s' % bad)

    if a.write:
        path, size = p.write(recs)
        print('写入 %s（%d 字节）' % (path, size))
        if not a.no_export:
            for f in (p.excel(recs), p.tsv(recs), p.html(recs)):
                print('导出', f)
    else:
        print('（干跑，未写盘；确认无误后加 --write）')


if __name__ == '__main__':
    main()
