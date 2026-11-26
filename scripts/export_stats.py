#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""按 UAM CorpusTool 6 的 Statistics 口径导出统计

    # 复刻 UAM 导出的 StatsResult.html（Counting: global）
    python export_stats.py --project "C:/.../斯日古冷_全书" --out .
    # 去掉正文重复的那一遍（段起点落在 15599–31198 的段不计）
    python export_stats.py --project ".../斯日古冷_全书" --out . --exclude 15599:31198 --suffix _dedup
    # 附带 Excel 工作簿与按章表
    python export_stats.py --project ".../斯日古冷_全书" --out . --xlsx \
        --chapters 斯日古冷 第二章 ... 第十二章 --base "C:/.../斯日古冷UAM项目"

口径（从 UAM 真实导出反推并验证）：
    N = 带该特征的标注段数
    % = N ÷ 全部标注段数（不是 system 内占比）
    MENTAL-TYPE / RELATIONAL-TYPE 是 PROCESS-TYPE 的子集，不参与 100% 相加
    PROCESS-TYPE + PARTICIPANT-ROLE + CIRCUMSTANCE 三者之和 = 段总数
"""
import os, sys, struct, argparse, datetime
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import uamlib

SYSTEMS = [
    ('PROCESS-TYPE', ['material', 'mental', 'relational', 'verbal', 'behavioural', 'existential']),
    ('MENTAL-TYPE', ['perception', 'emotion', 'cognition']),
    ('RELATIONAL-TYPE', ['attributive', 'identifying']),
    ('PARTICIPANT-ROLE', ['Actor', 'Goal', 'Range', 'Beneficiary', 'Senser', 'Phenomenon',
                          'Carrier', 'Attribute', 'Identified', 'Identifier', 'Sayer',
                          'Verbiage', 'Receiver', 'Target', 'Behaver', 'Existent']),
    ('CIRCUMSTANCE', ['location_time', 'location_place', 'manner', 'cause',
                      'accompaniment', 'matter', 'role', 'extent']),
]
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


def stats_html(recs, note, path):
    n = len(recs)
    c = Counter(f for x in recs for f in x['feats'])
    o = ["<html><meta charset='utf-8'><style>%s</style>%s</head>" % (CSS, JS),
         "<body style='overflow: scroll; margin: 10px; background-color: white;'>",
         "<p><b>User</b>: $Standalone",
         "<p><b>Unit of Interest</b>: &lt;及物性 feature=\"clause\"/&gt;",
         "<p><b>Aspect</b>: feature",
         "<p><b>Counting</b>: global"]
    for name, feats in SYSTEMS:
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
    o.append('<p style="color:#666;font-size:11.5px;margin-top:26px">标注段 %s · %s</p>'
             '</body></html>' % (format(n, ','), note))
    open(path, 'w', encoding='utf-8', newline='\n').write('\n'.join(o))
    return path


def write_xlsx(recs, path, ch_spans=None):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    THIN = Side(style='thin', color='D0D7DE')
    BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
    H_FILL = PatternFill('solid', fgColor='1F3A5F')
    H_FONT = Font(color='FFFFFF', bold=True, size=10.5)
    S_FILL = PatternFill('solid', fgColor='DCE6F1')
    T_FILL = PatternFill('solid', fgColor='F2F2F2')
    CEN = Alignment(horizontal='center', vertical='center')
    RIG = Alignment(horizontal='right', vertical='center')
    MONO = Font(name='Consolas', size=10)

    wb = Workbook()
    n = len(recs)
    c = Counter(f for x in recs for f in x['feats'])

    # 1 Feature statistics
    ws = wb.active
    ws.title = 'Feature statistics'
    ws.cell(row=1, column=1, value='Feature statistics · Global').font = Font(bold=True, size=13)
    ws.cell(row=2, column=1, value='Percent = N ÷ 段总数 %s（与 UAM Statistics 一致）'
            % format(n, ',')).font = Font(size=10, color='666666')
    for col, h in enumerate(['System', 'Feature', 'N', 'Percent'], 1):
        cc = ws.cell(row=4, column=col, value=h)
        cc.fill, cc.font, cc.alignment, cc.border = H_FILL, H_FONT, CEN, BOX
    r = 5
    for name, feats in SYSTEMS:
        r0 = r
        for f in feats:
            ws.cell(row=r, column=2, value=f).font = MONO
            ws.cell(row=r, column=3, value=c[f]).alignment = RIG
            ws.cell(row=r, column=4, value='%.1f%%' % (100.0 * c[f] / n)).alignment = RIG
            for col in range(1, 5):
                ws.cell(row=r, column=col).border = BOX
            r += 1
        tot = sum(c[f] for f in feats)
        ws.cell(row=r, column=2, value='Total').font = Font(bold=True)
        ws.cell(row=r, column=3, value=tot).font = Font(bold=True)
        ws.cell(row=r, column=3).alignment = RIG
        ws.cell(row=r, column=4, value='%.1f%%' % (100.0 * tot / n)).alignment = RIG
        for col in range(1, 5):
            cc = ws.cell(row=r, column=col)
            cc.border, cc.fill = BOX, T_FILL
        ws.merge_cells(start_row=r0, start_column=1, end_row=r, end_column=1)
        sc = ws.cell(row=r0, column=1, value=name)
        sc.font, sc.fill = Font(bold=True, size=10), S_FILL
        sc.alignment = Alignment(horizontal='center', vertical='center', text_rotation=90)
        for rr in range(r0, r + 1):
            ws.cell(row=rr, column=1).border = BOX
        r += 2
    for col, w in [('A', 20), ('B', 18), ('C', 9), ('D', 10)]:
        ws.column_dimensions[col].width = w

    # 2 段级 pattern
    ws = wb.create_sheet('Feature pattern')
    ws.cell(row=1, column=1, value='Feature pattern · Global').font = Font(bold=True, size=13)
    ws.cell(row=2, column=1, value='每段一个 pattern；因按成分分段，通常等于「特征名 + clause」'
            ).font = Font(size=10, color='666666')
    for col, h in enumerate(['Pattern', 'N', 'Percent'], 1):
        cc = ws.cell(row=4, column=col, value=h)
        cc.fill, cc.font, cc.alignment, cc.border = H_FILL, H_FONT, CEN, BOX
    r = 5
    for p_, k in Counter('+'.join(f for f in uamlib.FEATURES if f in x['feats'])
                         for x in recs).most_common():
        ws.cell(row=r, column=1, value=p_).font = MONO
        ws.cell(row=r, column=2, value=k).alignment = RIG
        ws.cell(row=r, column=3, value='%.2f%%' % (100.0 * k / n)).alignment = RIG
        for col in range(1, 4):
            ws.cell(row=r, column=col).border = BOX
        r += 1
    ws.column_dimensions['A'].width = 60

    # 3 小句模式
    kids = defaultdict(list)
    for x in recs:
        if x['pid']:
            kids[x['pid']].append(x)
    tops = [x for x in recs if x['pid'] == 0]
    cp = Counter()
    for t in tops:
        fs = set(f for f in t['feats'] if f != 'clause')
        for k in kids[t['sid']]:
            fs |= set(f for f in k['feats'] if f != 'clause')
        cp['+'.join(f for f in uamlib.FEATURES if f in fs and f != 'clause')] += 1
    ws = wb.create_sheet('小句模式')
    ws.cell(row=1, column=1, value='小句模式 · Global').font = Font(bold=True, size=13)
    ws.cell(row=2, column=1, value='顶层小句 %d 条、%d 种组合' % (len(tops), len(cp))
            ).font = Font(size=10, color='666666')
    for col, h in enumerate(['Pattern', 'N', 'Percent'], 1):
        cc = ws.cell(row=4, column=col, value=h)
        cc.fill, cc.font, cc.alignment, cc.border = H_FILL, H_FONT, CEN, BOX
    r = 5
    for p_, k in cp.most_common():
        ws.cell(row=r, column=1, value=p_).font = MONO
        ws.cell(row=r, column=2, value=k).alignment = RIG
        ws.cell(row=r, column=3, value='%.2f%%' % (100.0 * k / len(tops))).alignment = RIG
        for col in range(1, 4):
            ws.cell(row=r, column=col).border = BOX
        r += 1
    ws.column_dimensions['A'].width = 60

    # 4 按章
    if ch_spans:
        hdr = ['Feature'] + [x[0] for x in ch_spans] + ['全书']
        ws = wb.create_sheet('按章统计')
        ws.cell(row=1, column=1, value='各特征在每章中的频次').font = Font(bold=True, size=13)
        for col, h in enumerate(hdr, 1):
            cc = ws.cell(row=3, column=col, value=h)
            cc.fill, cc.font, cc.alignment, cc.border = H_FILL, H_FONT, CEN, BOX
        r = 4
        for name, feats in SYSTEMS:
            for f in feats:
                ws.cell(row=r, column=1, value=f).font = MONO
                for j, (ch, lo, hi) in enumerate(ch_spans):
                    v = sum(1 for x in recs if lo <= x['start'] < hi and f in x['feats'])
                    ws.cell(row=r, column=2 + j, value=v).alignment = RIG
                ws.cell(row=r, column=2 + len(ch_spans), value=c[f]).alignment = RIG
                for col in range(1, len(hdr) + 1):
                    ws.cell(row=r, column=col).border = BOX
                r += 1
        ws.column_dimensions['A'].width = 20
        for j in range(len(ch_spans) + 1):
            ws.column_dimensions[get_column_letter(2 + j)].width = 9

    wb.save(path)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--project', required=True, help='项目目录')
    ap.add_argument('--out', default='.', help='输出目录')
    ap.add_argument('--exclude', action='append', default=[],
                    metavar='START:END', help='段起点落在此区间则不计（可重复），用于剔除重复正文')
    ap.add_argument('--suffix', default='', help='输出文件名后缀，如 _dedup')
    ap.add_argument('--xlsx', action='store_true', help='同时导出 Excel 工作簿')
    ap.add_argument('--chapters', nargs='+', help='按章统计用：章目录名，按序')
    ap.add_argument('--base', help='各章项目所在目录（默认取 --project 的上级）')
    a = ap.parse_args()

    proj = os.path.abspath(a.project)
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    recs, _ = uamlib.read_idx(os.path.join(proj, 'Annotations/Texts/Text-1.txt/及物性.idx'))

    ex = []
    for e in a.exclude:
        lo, hi = [int(x) for x in e.split(':')]
        ex.append((lo, hi))
    if ex:
        recs = [r for r in recs if not any(lo <= r['start'] < hi for lo, hi in ex)]

    note = os.path.basename(proj.rstrip('/\\'))
    if ex:
        note += ' · 已剔除 ' + ', '.join('%d–%d' % e for e in ex)
    note += ' · ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    p = stats_html(recs, note, os.path.join(out, 'StatsResult%s.html' % a.suffix))
    print('写出', p, '| 段', len(recs))

    n = len(recs)
    c = Counter(f for x in recs for f in x['feats'])
    for name, feats in SYSTEMS:
        tot = sum(c[f] for f in feats)
        print('  %-16s TOTAL %5d  %5.1f%%' % (name, tot, 100.0 * tot / n))

    if a.xlsx:
        ch_spans = None
        if a.chapters:
            base = os.path.abspath(a.base) if a.base else os.path.dirname(proj)
            ch_spans, pos = [], 0
            book = open(os.path.join(proj, 'Corpus/Texts/Text-1.txt'), encoding='utf-8').read()
            for ch in a.chapters:
                t = open(os.path.join(base, ch, 'Corpus/Texts/Text-1.txt'), encoding='utf-8').read()
                ch_spans.append((ch, pos, pos + len(t)))
                pos += len(t) + (1 if not t.endswith('\n') else 0)
            assert pos <= len(book) + 1, '章文本与书文本长度对不上'
        xp = write_xlsx(recs, os.path.join(out, 'StatsResult%s.xlsx' % a.suffix), ch_spans)
        print('写出', xp)


if __name__ == '__main__':
    main()
