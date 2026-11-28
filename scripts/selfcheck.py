#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""自检：在临时目录跑一遍全链路

    python scripts/selfcheck.py            # 跑完删临时目录
    python scripts/selfcheck.py --keep     # 保留临时目录，方便查看产物

覆盖四条链路：
    1. 多层项目骨架      四层 .ct3 + 四套方案 + 四个空 idx
    2. 及物性层          骨架 → 标注 → 落盘 → 合并 → 回比 → 统计
    3. 评价三支子层      态度 / 介入 / 级差 各自落盘，多层合并与逐层回比
    4. 合并评价方案      单层 appraisal（76 特征，两位图），合并与统计

用途：换机器、换 Python、改了脚本之后，先跑这个确认不是环境问题。
全部通过时最后一行打印 PASS。
"""
import os, sys, re, subprocess, tempfile, shutil, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
FAILS = []
sys.path.insert(0, HERE)


def run(script, *args, expect=0, label=None):
    cmd = [PY, os.path.join(HERE, script)] + list(args)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    ok = r.returncode == expect
    tag = label or script
    print('  %s %s' % ('✓' if ok else '✗', tag))
    if not ok:
        FAILS.append(tag)
        sys.stdout.write('    ' + (r.stdout + r.stderr).strip().replace('\n', '\n    ')[:800] + '\n')
    return r


def check(cond, ok_msg, bad_msg):
    print('  %s %s' % ('✓' if cond else '✗', ok_msg if cond else bad_msg))
    if not cond:
        FAILS.append(bad_msg)
    return cond


def write(p, s):
    os.makedirs(os.path.dirname(p) or '.', exist_ok=True)
    open(p, 'w', encoding='utf-8', newline='\n').write(s)


CH1 = """The snow fell all night.
The children ran out into the yard.
She folded the paper carefully.
"""

CH2 = """The road was clear.
They walked to the station.
"""

# 评价理论：一段要落多个系统的特征（这是与及物性最大的结构差异）
CH3 = """The film was utterly boring.
Sadly, the children were disappointed by it.
"""

ANN3 = """ANN = {
  0: [('utterly boring',
       ['attitude', 'appreciation', 'reaction', 'quality',
        'negative-attitude', 'inscribed'])],
  1: [('Sadly',
       ['attitude', 'affect', 'authorial-evaluation', 'un/happiness',
        'misery/cheer', 'negative-attitude', 'inscribed']),
      ('disappointed',
       ['attitude', 'affect', 'non-authorial-evaluation', 'dis/satisfaction',
        'dis/pleasure', 'negative-attitude', 'inscribed'])],
}
"""

CH4 = """What a marvellous performance it was.
Perhaps the critics will disagree.
"""

ANN4 = """ANN = {
  0: [('marvellous',
       ['attitude', 'appreciation', 'reaction', 'quality',
        'positive-attitude', 'inscribed'])],
  1: [('Perhaps', ['engagement', 'hetero-glossic', 'expand', 'entertain'])],
}
"""

ANN1 = """ANN = {
 0: [('The snow fell all night', 'material',
      [('Actor', 'The snow'), ('location_time', 'all night')])],
 1: [('The children ran out into the yard', 'material',
      [('Actor', 'The children'), ('location_place', 'into the yard')])],
 2: [('She folded the paper carefully', 'material',
      [('Actor', 'She'), ('Goal', 'the paper'), ('manner', 'carefully')])],
}
"""

ANN2 = """ANN = {
 0: [('The road was clear', 'relational attributive',
      [('Carrier', 'The road'), ('Attribute', 'clear')])],
 1: [('They walked to the station', 'material',
      [('Actor', 'They'), ('location_place', 'to the station')])],
}
"""

# 态度 / 介入 / 级差：同一项目里各自成层，各写各的 idx
ATT1 = """ANN = {
 0: [('all night', ['attitude', 'appreciation', 'composition', 'complexity',
                    'positive-attitude', 'inscribed', 'writer-appraiser'])],
 2: [('carefully', ['attitude', 'judgement', 'capacity',
                    'positive-attitude', 'inscribed', 'writer-appraiser'])],
}
"""

ATT2 = """ANN = {
 0: [('clear', ['attitude', 'appreciation', 'reaction', 'quality',
                'positive-attitude', 'inscribed', 'writer-appraiser'])],
}
"""

ENG1 = """ANN = {
 1: [('The children ran out into the yard',
      ['engagement', 'mono-glossic'])],
}
"""

ENG2 = """ANN = {
 1: [('They walked to the station', ['engagement', 'mono-glossic'])],
}
"""

GRD1 = """ANN = {
 0: [('all night', ['graduation', 'force', 'quantification', 'extent'])],
}
"""

LAYERS = ('及物性', '态度', '介入', '级差')


def read_layers(proj):
    import merge_book
    return [n for n, _ in merge_book.layers_of(proj)]


def nrec(idx):
    import uamlib
    return len(uamlib.read_idx(idx)[0])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--keep', action='store_true', help='保留临时目录')
    a = ap.parse_args()

    print('selfcheck · Python %s' % sys.version.split()[0])
    try:
        import openpyxl  # noqa: F401
        print('  ✓ openpyxl %s' % openpyxl.__version__)
    except ImportError:
        print('  ✗ 缺 openpyxl（xlsx 导出会失败）：pip install openpyxl')
        FAILS.append('openpyxl')

    tmp = tempfile.mkdtemp(prefix='uam_selfcheck_')
    try:
        b = os.path.join(tmp, '项目')
        write(os.path.join(tmp, 'ch1.txt'), CH1)
        write(os.path.join(tmp, 'ch2.txt'), CH2)

        # ---------------- 1. 多层骨架 ----------------
        run('make_project.py', '--text', os.path.join(tmp, 'ch1.txt'),
            '--out', os.path.join(b, '第一章'), '--name', '第一章', label='建项目 ch1（四层）')
        run('make_project.py', '--text', os.path.join(tmp, 'ch2.txt'),
            '--out', os.path.join(b, '第二章'), '--name', '第二章', label='建项目 ch2（四层）')
        p1 = os.path.join(b, '第一章')
        lay = read_layers(p1)
        check(lay == list(LAYERS), '四层已写入 .ct3：%s' % ' / '.join(lay),
              '.ct3 层不符：%r' % lay)
        sch = os.path.join(p1, 'Schemes')
        have = sorted(f for f in os.listdir(sch) if f.endswith('.xml'))
        check(have == sorted(x + '.xml' for x in LAYERS),
              'Schemes 四份：%s' % ', '.join(have), 'Schemes 不全：%r' % have)
        ann_dir = os.path.join(p1, 'Annotations/Texts/Text-1.txt')
        empties = [x for x in LAYERS if os.path.exists(os.path.join(ann_dir, x + '.idx'))]
        check(empties == list(LAYERS), '四个空 idx 已生成', '空 idx 缺失：%r' % empties)
        check(all(nrec(os.path.join(ann_dir, x + '.idx')) == 0 for x in LAYERS),
              '空 idx 均为 0 条记录', '空 idx 记录数不为 0')

        # ---------------- 2. 及物性层 ----------------
        run('ann_skeleton.py', '--project', p1,
            '--sent', '0', '3', '--prefix', 'skel', '--write', label='生成骨架')
        write(os.path.join(p1, 'c1_a.py'), ANN1)
        write(os.path.join(b, '第二章', 'c2_a.py'), ANN2)
        run('run_annotation.py', '--project', p1, '--ann-prefix', 'c1', label='干跑 ch1')
        run('run_annotation.py', '--project', p1, '--ann-prefix', 'c1', '--write',
            '--out', os.path.join(tmp, '复核'), label='写盘 ch1 及物性')
        run('run_annotation.py', '--project', os.path.join(b, '第二章'),
            '--ann-prefix', 'c2', '--write', '--out', os.path.join(tmp, '复核'),
            label='写盘 ch2 及物性')
        for ch in ('第一章', '第二章'):
            idx = os.path.join(b, ch, 'Annotations/Texts/Text-1.txt/及物性.idx')
            n = nrec(idx) if os.path.exists(idx) else 0
            check(n > 0, '%s 及物性.idx %d 条' % (ch, n), '%s 及物性.idx 缺失' % ch)

        # ---------------- 3. 态度 / 介入 / 级差 ----------------
        for ch, pre, body in (('第一章', 'at', ATT1), ('第一章', 'en', ENG1),
                              ('第一章', 'gr', GRD1), ('第二章', 'at', ATT2),
                              ('第二章', 'en', ENG2)):
            write(os.path.join(b, ch, '%s_a.py' % pre), body)
        for ch in ('第一章', '第二章'):
            for layer, pre in (('态度', 'at'), ('介入', 'en')):
                run('run_appraisal.py', '--project', os.path.join(b, ch),
                    '--layer', layer, '--ann-prefix', pre, '--write', '--no-export',
                    label='%s %s 落盘' % (ch, layer))
        run('run_appraisal.py', '--project', p1, '--layer', '级差', '--ann-prefix', 'gr',
            '--write', '--out', os.path.join(tmp, '复核'), label='第一章 级差 落盘')
        for layer in ('态度', '介入', '级差'):
            idx = os.path.join(ann_dir, layer + '.idx')
            n = nrec(idx) if os.path.exists(idx) else 0
            check(n > 0, '第一章 %s.idx %d 条（与及物性同项目）' % (layer, n),
                  '第一章 %s.idx 没写进去' % layer)

        # ---------------- 4. 多层合并与逐层回比 ----------------
        run('merge_book.py', '--base', b, '--chapters', '第一章', '第二章',
            '--out', '全书', label='合并全书（四层）')
        bk = os.path.join(b, '全书')
        check(read_layers(bk) == list(LAYERS), '全书 .ct3 四层齐备',
              '全书 .ct3 层不符：%r' % read_layers(bk))
        r = run('verify_merge.py', '--base', b, '--book', '全书',
                '--chapters', '第一章', '第二章', label='逐层回比')
        check('全部一致' in r.stdout, '回比结论：全部一致', 'verify_merge 未报「全部一致」')

        run('export_stats.py', '--project', bk, '--out', os.path.join(tmp, '统计'),
            '--xlsx', label='统计导出 及物性')
        for layer, script in (('态度', 'export_appraisal_stats.py'),
                              ('介入', 'export_appraisal_stats.py'),
                              ('级差', 'export_appraisal_stats.py')):
            run(script, '--project', bk, '--layer', layer,
                '--out', os.path.join(tmp, '统计' + layer), label='统计导出 %s' % layer)
            p = os.path.join(tmp, '统计' + layer, 'StatsResult.html')
            check(os.path.exists(p) and os.path.getsize(p) > 0,
                  '%s 统计已出' % layer, '%s 统计缺失' % layer)
        for f in ('StatsResult.html', 'StatsResult.xlsx'):
            p = os.path.join(tmp, '统计', f)
            check(os.path.exists(p) and os.path.getsize(p) > 0, f + ' 已生成', '缺 ' + f)

        # ---------------- 5. 合并评价方案（单层 76 特征） ----------------
        write(os.path.join(tmp, 'ch3.txt'), CH3)
        run('make_project.py', '--text', os.path.join(tmp, 'ch3.txt'),
            '--out', os.path.join(b, '评价章'), '--name', '评价章',
            '--scheme', 'appraisal', label='建项目 评价章（单层）')
        check(read_layers(os.path.join(b, '评价章')) == ['评价'], '单层 appraisal 仍可用',
              '单层 appraisal 层名不符')
        write(os.path.join(b, '评价章', 'ap_a.py'), ANN3)
        r = run('run_appraisal.py', '--project', os.path.join(b, '评价章'),
                '--ann-prefix', 'ap', '--write',
                '--out', os.path.join(tmp, '复核'), label='评价落盘')
        idx3 = os.path.join(b, '评价章', 'Annotations/Texts/Text-1.txt/评价.idx')
        check(os.path.exists(idx3) and nrec(idx3) == 3, '评价.idx 3 段',
              '评价.idx 缺失或段数不符')
        check('标注段 3' in r.stdout, '评价段数 3 与预期一致', '评价段数不符')
        try:
            import uamlib, apprlib
            schs = apprlib.Scheme(os.path.join(apprlib.ASSETS, 'scheme-appraisal.xml'))
            back, ftab = uamlib.read_idx(idx3)
            ok = (len(ftab) == len(schs.features)
                  and all(len(x['feats']) >= 4 for x in back))
            check(ok, '评价 idx 回读（%d 特征 / %d 段，两位图）' % (len(ftab), len(back)),
                  '评价 idx 回读不符')
        except Exception as ex:
            check(False, '', '评价 idx 回读失败: %s' % ex)

        write(os.path.join(tmp, 'ch4.txt'), CH4)
        run('make_project.py', '--text', os.path.join(tmp, 'ch4.txt'),
            '--out', os.path.join(b, '评价章2'), '--name', '评价章2',
            '--scheme', 'appraisal', label='建项目 评价章2（单层）')
        write(os.path.join(b, '评价章2', 'ap_a.py'), ANN4)
        run('run_appraisal.py', '--project', os.path.join(b, '评价章2'),
            '--ann-prefix', 'ap', '--write', '--no-export', label='评价章2 落盘')
        run('merge_book.py', '--base', b, '--chapters', '评价章', '评价章2',
            '--out', '评价全书', label='合并评价全书')
        r = run('verify_merge.py', '--base', b, '--book', '评价全书',
                '--chapters', '评价章', '评价章2', label='评价回比')
        check('全部一致' in r.stdout, '评价回比：全部一致', '评价 verify_merge 未报「全部一致」')
        run('export_appraisal_stats.py', '--project', os.path.join(b, '评价全书'),
            '--out', os.path.join(tmp, '统计评价'), '--xlsx', '--csv',
            label='评价统计导出')
        for f in ('StatsResult.html', 'StatsResult.xlsx'):
            p = os.path.join(tmp, '统计评价', f)
            check(os.path.exists(p) and os.path.getsize(p) > 0,
                  '评价 ' + f + ' 已生成', '缺评价 ' + f)

        print('\n%s' % ('PASS' if not FAILS else 'FAIL: ' + ', '.join(FAILS)))
        return 0 if not FAILS else 1
    finally:
        if a.keep:
            print('保留目录:', tmp)
        else:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
