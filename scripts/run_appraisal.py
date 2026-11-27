#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""评价理论（Appraisal）标注：导入 ANN → 校验特征组合 → 写 idx → 导出复核件

    # 看句子
    python run_appraisal.py --project "C:/.../评价项目" --sent 0 20
    # 干跑（不写盘）
    python run_appraisal.py --project ".../评价项目" --ann-prefix ab
    # 校验通过后落盘并导出
    python run_appraisal.py --project ".../评价项目" --ann-prefix ab --write --out ./复核

标注模块放项目目录，命名 <prefix>_a.py …，每个导出 ANN：

    ANN = {
      0: [('a depressing sight',
           ['attitude', 'appreciation', 'reaction', 'quality',
            'negative-attitude', 'inscribed']),
          ('makes me happy',                       # 第二个跨度
           ['attitude', 'affect', 'authorial-evaluation', 'un/happiness',
            'affection', 'positive-attitude', 'inscribed'], 1)],
    }

元组 = (原文片段, [特征…])，可加第 3 位 nth（同片段第几处，0 起）、
第 4 位 [子段…]（同结构，挂在当前段下面）。
"""
import os, sys, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import apprlib

sys.dont_write_bytecode = True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--project', required=True, help='项目目录（含 Corpus/ 与 Annotations/）')
    ap.add_argument('--ann-prefix', help='标注模块前缀，如 ab → ab_a.py ab_b.py …')
    ap.add_argument('--ann-dir', help='标注模块所在目录（默认项目目录）')
    ap.add_argument('--write', action='store_true', help='校验通过后写 评价.idx')
    ap.add_argument('--layer', default='评价', help='层名（决定 idx 文件名，默认 评价）')
    ap.add_argument('--scheme', help='方案 xml（默认项目 Schemes/<层名>.xml）')
    ap.add_argument('--no-export', action='store_true', help='不生成 xlsx/TSV/HTML')
    ap.add_argument('--sent', nargs=2, type=int, metavar=('LO', 'HI'), help='打印句子区间后退出')
    ap.add_argument('--out', help='复核件输出目录（默认当前目录）')
    a = ap.parse_args()

    proj_dir = os.path.abspath(a.project)
    if not os.path.isdir(proj_dir):
        sys.exit('项目目录不存在: %s' % proj_dir)
    sys.path.insert(0, proj_dir)
    if a.ann_dir:
        sys.path.insert(0, os.path.abspath(a.ann_dir))
    p = apprlib.ApprProj(proj_dir, out=os.path.abspath(a.out) if a.out else os.getcwd(),
                         scheme=a.scheme, layer=a.layer)
    sch = p.scheme
    print('方案 %s：%d 系统 / %d 特征' % (os.path.basename(p.scheme_path),
                                        len(sch.systems), len(sch.features) - 1))

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

    recs, errs = p.check(ann)
    print('标注段 %d（含嵌套）' % len(recs))
    if errs:
        print('错误 %d 条：' % len(errs))
        for e in errs[:20]:
            print('  -', e)
        sys.exit('先修好再写盘')

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
