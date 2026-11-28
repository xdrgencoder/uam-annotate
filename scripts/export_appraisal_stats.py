#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""按 UAM Statistics 口径导出评价层（或任意方案层）统计

    python export_appraisal_stats.py --project "C:/.../评价全书" --out .
    python export_appraisal_stats.py --project ".../评价全书" --out . --xlsx --csv
    python export_appraisal_stats.py --project ".../评价章" --layer 评价
    python export_appraisal_stats.py --project ".../评价全书" --out . --exclude 4200:8400 --suffix _dedup

口径与 UAM 一致：
    N = 带该特征的标注段数
    % = N ÷ 全部标注段数（global，不是 system 内占比）
系统与特征全部来自方案 xml，不做任何硬编码，所以换方案不用改脚本。

和 export_stats.py 的区别：那个是及物性专用（PROCESS-TYPE 三套的互斥关系要特殊处理）；
这个只认方案里的系统表，适用于 31 个系统的评价层。
"""
import os, sys, struct, argparse, datetime
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import uamlib
import apprlib

CSS = """table.statstable{border-collapse:collapse;margin:6px 0;font-size:12.5px;
font-family:Arial,Helvetica,"Microsoft YaHei",sans-serif}
table.statstable th{background:#e9e9e9;border:1px solid #b8b8b8;padding:3px 8px;
text-align:left;font-weight:normal}
table.statstable th:nth-child(3),table.statstable th:nth-child(4){text-align:right}
table.statstable td{border:1px solid #d6d6d6;padding:2px 8px}
td.statscol1{padding-left:12px;white-space:nowrap}
td.tableinset{width:6px;padding:0;border-left:0;border-right:0}
td.bluecol{color:#00009c;text-align:right;cursor:pointer;font-variant-numeric:tabular-nums}
table.statstable td:nth-child(4){text-align:right;font-variant-numeric:tabular-nums;width:66px}
p.minheight{margin:0;line-height:10px}"""
JS = ('<script>if(typeof showStatsHits==="undefined")'
      '{window.showStatsHits=function(){}};</script>')


def stats_html(recs, sch, layer, note, path):
    n = len(recs)
    c = Counter(f for x in recs for f in x['feats'])
    o = ["<html><meta charset='utf-8'><style>%s</style>%s</head>" % (CSS, JS),
         "<body style='overflow: scroll; margin: 10px; background-color: white;'>",
         "<p><b>User</b>: $Standalone",
         "<p><b>Unit of Interest</b>: &lt;%s feature=\"%s\"/&gt;" % (layer, sch.root),
         "<p><b>Aspect</b>: feature",
         "<p><b>Counting</b>: global"]
    for name, (ec, feats) in sch.systems.items():
        tot = sum(c[f] for f in feats)
        o.append('<p class="minheight">&nbsp;')
        o.append('<table class="statstable">')
        o.append('<tbody><tr><th><b>%s</b></th><th class="tableinset"></th><th>N</th>'
                 '<th>%%\n  </th></tr>' % name)
        for f in feats:
            o.append('<tr><td class="statscol1"> - %s</td><td class="tableinset"></td>'
                     '<td class="bluecol" onclick="showStatsHits(&quot;%s&quot;, 0);">%d</td>'
                     '<td>%.1f\n  </td></tr>' % (f, f, c[f], 100.0 * c[f] / n if n else 0))
        o.append('<tr><td class="statscol1"><b>TOTAL</b>:</td><td class="tableinset"></td>'
                 '<td><b>%d</b></td><td><b>%.1f%%</b>\n</td></tr></tbody></table>'
                 % (tot, 100.0 * tot / n if n else 0))
    o.append('</p>')
    o.append('<p style="color:#666;font-size:11.5px;margin-top:26px">'
             '标注段 %s · %s 系统 · %s</p></body></html>'
             % (format(n, ','), len(sch.systems), note))
    open(path, 'w', encoding='utf-8', newline='\n').write('\n'.join(o))
    return path


def write_xlsx(recs, sch, path):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    THIN = Side(style='thin', color='D0D7DE')
    BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
    H_FILL = PatternFill('solid', fgColor='1F3A5F')
    H_FONT = Font(color='FFFFFF', bold=True, size=10.5)
    CEN = Alignment(horizontal='center', vertical='center')
    RIG = Alignment(horizontal='right', vertical='center')
    MONO = Font(name='Consolas', size=10)

    n = len(recs)
    c = Counter(f for x in recs for f in x['feats'])
    wb = Workbook()
    ws = wb.active
    ws.title = 'Feature statistics'
    ws.cell(row=1, column=1, value='Feature statistics · Global').font = Font(bold=True, size=13)
    ws.cell(row=2, column=1, value='Percent = N ÷ 段总数 %s（与 UAM Statistics 一致）'
            % format(n, ',')).font = Font(size=10, color='666666')
    for col, h in enumerate(['System', 'Feature', 'N', 'Percent'], 1):
        cc = ws.cell(row=4, column=col, value=h)
        cc.fill, cc.font, cc.alignment, cc.border = H_FILL, H_FONT, CEN, BOX
    r = 5
    for name, (ec, feats) in sch.systems.items():
        for f in feats:
            ws.cell(row=r, column=2, value=f).font = MONO
            ws.cell(row=r, column=3, value=c[f]).alignment = RIG
            ws.cell(row=r, column=4, value='%.1f%%' % (100.0 * c[f] / n if n else 0)).alignment = RIG
            for col in range(1, 5):
                ws.cell(row=r, column=col).border = BOX
            if r == 5 or ws.cell(row=r - 1, column=1).value != name:
                ws.cell(row=r, column=1, value=name).font = Font(size=9.5, color='555555')
            r += 1
        tot = sum(c[f] for f in feats)
        ws.cell(row=r, column=2, value='Total').font = Font(bold=True)
        ws.cell(row=r, column=3, value=tot).font = Font(bold=True)
        ws.cell(row=r, column=4, value='%.1f%%' % (100.0 * tot / n if n else 0)) \
            .font = Font(bold=True)
        for col in range(1, 5):
            ws.cell(row=r, column=col).border = BOX
        r += 2
    for col, w in zip('ABCD', [24, 26, 8, 11]):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = 'A5'

    ws2 = wb.create_sheet('System summary')
    ws2.append(['System', 'EC', 'Features', 'N(有标注的特征数)', 'TOTAL(段次)', '占段比'])
    for name, (ec, feats) in sch.systems.items():
        used = [f for f in feats if c[f]]
        tot = sum(c[f] for f in feats)
        ws2.append([name, ec, len(feats), len(used), tot,
                    '%.1f%%' % (100.0 * tot / n if n else 0)])
    for col, w in zip('ABCDEF', [26, 20, 20, 20, 14, 10]):
        ws2.column_dimensions[col].width = w
    wb.save(path)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--project', required=True, help='项目目录（含 Annotations/）')
    ap.add_argument('--layer', default='评价',
                    help='层名（决定 idx 文件名，默认 评价；多层项目里可给 态度 / 介入 / 级差 / 及物性）')
    ap.add_argument('--scheme', help='方案 xml（默认 <项目>/Schemes/<层名>.xml）')
    ap.add_argument('--out', default='.', help='输出目录（默认当前目录）')
    ap.add_argument('--xlsx', action='store_true', help='同时导出 Excel')
    ap.add_argument('--csv', action='store_true', help='同时导出 CSV')
    ap.add_argument('--exclude', help='丢弃起点落在 START:END 的段（去重用）')
    ap.add_argument('--suffix', default='', help='输出文件名后缀')
    a = ap.parse_args()

    proj = os.path.abspath(a.project)
    idx = os.path.join(proj, 'Annotations/Texts/Text-1.txt', a.layer + '.idx')
    if not os.path.exists(idx):
        sys.exit('没有 %s，先跑标注脚本落盘' % idx)
    scheme_path = a.scheme or os.path.join(proj, 'Schemes', a.layer + '.xml')
    if not os.path.exists(scheme_path):
        fn = apprlib.scheme_file(a.layer)
        if not fn:
            sys.exit('找不到 Schemes/%s.xml，也认不出层名 %r（用 --scheme 指定方案）'
                     % (a.layer, a.layer))
        scheme_path = os.path.join(apprlib.ASSETS, fn)
    sch = apprlib.Scheme(scheme_path)

    recs, ftab = uamlib.read_idx(idx)
    if ftab != sch.features:
        sys.exit('idx 的特征表与方案不符（%d vs %d 项）' % (len(ftab), len(sch.features)))

    if a.exclude:
        try:
            x, y = a.exclude.split(':')
            lo, hi = int(x), int(y)
        except ValueError:
            sys.exit('--exclude 要写成 START:END，例如 15599:31198')
        keep = [r for r in recs if not (lo <= r['start'] < hi)]
        print('排除起点落在 %d–%d 的段 %d 条' % (lo, hi, len(recs) - len(keep)))
        recs = keep

    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    note = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    stem = os.path.basename(proj.rstrip('/\\'))
    p_html = stats_html(recs, sch, a.layer, note,
                        os.path.join(out, 'StatsResult%s.html' % a.suffix))
    print('导出', p_html)

    if a.xlsx:
        print('导出', write_xlsx(recs, sch, os.path.join(out, 'StatsResult%s.xlsx' % a.suffix)))
    if a.csv:
        c = Counter(f for r in recs for f in r['feats'])
        lines = ['system,feature,N,percent']
        for name, (ec, feats) in sch.systems.items():
            for f in feats:
                lines.append('%s,%s,%d,%.1f' % (name, f, c[f],
                                                100.0 * c[f] / len(recs) if recs else 0))
        pc = os.path.join(out, '%s%s.csv' % (stem, a.suffix))
        open(pc, 'w', encoding='utf-8-sig', newline='\n').write('\n'.join(lines))
        print('导出', pc)

    print('段 %d · 系统 %d · 特征 %d' % (len(recs), len(sch.systems), len(sch.features) - 1))


if __name__ == '__main__':
    main()
