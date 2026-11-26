#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""自检：在临时目录跑一遍全链路（建项目 → 骨架 → 标注落盘 → 合并 → 回比 → 统计）

    python scripts/selfcheck.py            # 跑完删临时目录
    python scripts/selfcheck.py --keep     # 保留临时目录，方便查看产物

用途：换机器、换 Python、改了脚本之后，先跑这个确认不是环境问题。
全部通过时最后一行打印 PASS。
"""
import os, sys, subprocess, tempfile, shutil, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
FAILS = []


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

        run('make_project.py', '--text', os.path.join(tmp, 'ch1.txt'),
            '--out', os.path.join(b, '第一章'), '--name', '第一章', label='建项目 ch1')
        run('make_project.py', '--text', os.path.join(tmp, 'ch2.txt'),
            '--out', os.path.join(b, '第二章'), '--name', '第二章', label='建项目 ch2')

        run('ann_skeleton.py', '--project', os.path.join(b, '第一章'),
            '--sent', '0', '3', '--prefix', 'skel', '--write', label='生成骨架')

        write(os.path.join(b, '第一章', 'c1_a.py'), ANN1)
        write(os.path.join(b, '第二章', 'c2_a.py'), ANN2)
        run('run_annotation.py', '--project', os.path.join(b, '第一章'),
            '--ann-prefix', 'c1', label='干跑 ch1')
        run('run_annotation.py', '--project', os.path.join(b, '第一章'),
            '--ann-prefix', 'c1', '--write', '--out', os.path.join(tmp, '复核'), label='写盘 ch1')
        run('run_annotation.py', '--project', os.path.join(b, '第二章'),
            '--ann-prefix', 'c2', '--write', '--out', os.path.join(tmp, '复核'), label='写盘 ch2')

        for ch in ('第一章', '第二章'):
            idx = os.path.join(b, ch, 'Annotations/Texts/Text-1.txt/及物性.idx')
            if os.path.exists(idx) and os.path.getsize(idx) > 40:
                print('  ✓ %s 及物性.idx 已生成' % ch)
            else:
                print('  ✗ %s 及物性.idx 缺失' % ch)
                FAILS.append('%s idx' % ch)

        run('merge_book.py', '--base', b, '--chapters', '第一章', '第二章',
            '--out', '全书', label='合并全书')

        r = run('verify_merge.py', '--base', b, '--book', '全书',
                '--chapters', '第一章', '第二章', label='回比校验')
        if '全部一致' not in r.stdout:
            print('  ✗ verify_merge 未报「全部一致」')
            FAILS.append('verify 结论')

        run('export_stats.py', '--project', os.path.join(b, '全书'),
            '--out', os.path.join(tmp, '统计'), '--xlsx', label='统计导出')
        for f in ('StatsResult.html', 'StatsResult.xlsx'):
            p = os.path.join(tmp, '统计', f)
            if not (os.path.exists(p) and os.path.getsize(p) > 0):
                print('  ✗ 缺 %s' % f)
                FAILS.append(f)

        print('\n%s' % ('PASS' if not FAILS else 'FAIL: ' + ', '.join(FAILS)))
        return 0 if not FAILS else 1
    finally:
        if a.keep:
            print('保留目录:', tmp)
        else:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
