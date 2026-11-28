# -*- coding: utf-8 -*-
"""章节标注库：读项目、建记录、校验、写 idx + xlsx + TSV + HTML

用法：
    from annlib import Proj
    p = Proj('第四章', base=r'C:/.../斯日古冷UAM项目')
    ann = {0: [('原文小句', 'material', [('Actor', 'X'), ('Goal', 'Y')])]}
    recs, tab, errs = p.check(ann)      # 先干跑，看错误
    print(p.validate(recs))
    p.write(recs); p.excel(recs); p.tsv(recs); p.html(recs)
"""
import os, sys, re, struct, importlib
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import uamlib

# 十条例行口径（页面「口径」面板与 references/annotation-conventions.md 同源）
POLICY = [
    '直接引语按独立小句分析（投影小句），引导句单列 verbal 小句；引语内的句子不并入 Verbiage。',
    '省略的参与者不建段（没有文本跨度），所以会出现只有 Attribute、或只有 Goal 的段，不是漏标；'
    '主语本身由从句充当时（"What he saw confirmed X"），该从句按自身过程类型另标，外层不再重复取 Senser 跨度。',
    '目的与原因一律标 <code>cause</code>——本方案里 cause 的 GLOSS 就是 "Cause / Purpose"，没有单独的 purpose 特征。',
    '非限定小句单独成段；只有跨度确实落在母句内部的从属小句才嵌套。',
    '父子关系记在 xlsx「父段」列与 TSV 的 pid 列，本页不显示。',
    '片段（"Nothing." / "What lovely fresh air!"）按最贴近的过程类型标注，不补主语。',
    '<b>结果/状态成分一律作 <code>Attribute</code></b>，不另立关系小句：<code>make/turn + 宾语 + 形容词</code>'
    '（"made him violent"）、<code>wake up / stumble + 形容词</code>（"woke up furious"）的结果成分都直接挂在 '
    'material 小句下——这些片段没有谓体，成不了 clause。',
    '<b><code>be + 介词短语</code> 按 circumstantial Attribute 处理</b>（"he was in the city" → Carrier + '
    'Attribute=in the city），这是 Halliday 对关系过程的处理，不拆成 location_place。',
    '<b><code>be / become + 形容词</code> 一律 relational attributive</b>（"were disappointed"、"too scared to '
    'get any closer"），不标 mental emotion；只有 <code>feel / want / know / hear</code> 这类心理动词才建 mental '
    '小句；<code>feel + 形容词</code>（"felt uncomfortable"）保留 mental，该形容词作 Phenomenon；'
    '<b>但 <code>be / become</code> 后的形容词不能作 Phenomenon</b>——那是 Attribute。',
    '<b>价格、交易条件的 <code>for-</code> 短语作 <code>Range</code></b>（"go for anything less"、'
    '"buy for a shockingly low price"），不作 matter；matter 只用于 <code>about / over</code> 引出的谈论或争论话题。',
]


class Proj:
    def __init__(self, chapter, base=None, out=None, layer='及物性'):
        """chapter: 项目目录名（相对 base）或绝对路径；base 默认取环境变量 UAM_BASE 或当前目录；
        layer: 层名，决定 idx 文件名与复核件名（一个项目可有多层，各写各的 idx）"""
        base = base or os.environ.get('UAM_BASE') or os.getcwd()
        self.root = chapter if os.path.isabs(chapter) else os.path.join(base, chapter)
        self.ch = os.path.basename(self.root.rstrip('/\\'))
        self.out = out or base
        self.layer = layer
        os.makedirs(self.out, exist_ok=True)   # 复核件目录不存在时自动建
        self.text = open(os.path.join(self.root, 'Corpus/Texts/Text-1.txt'), encoding='utf-8').read()
        d = open(os.path.join(self.root, 'Annotations/Texts/Text-1.txt/sentence.dat'), 'rb').read()
        self.bounds = [struct.unpack('2I', d[i * 8:(i + 1) * 8]) for i in range(len(d) // 8)]

    # ---------------------------------------------------------------- 读取
    def norm(self, s):
        return re.sub(r'\s+', ' ', s).strip()

    def sent(self, i):
        s, e = self.bounds[i]
        return self.norm(self.text[s:e])

    def load_ann(self, prefix, letters='abcdefghijklmn'):
        """按 prefix_a / prefix_b ... 依次导入，合并各模块的 ANN 字典"""
        ann, mods = {}, []
        for c in letters:
            m = '%s_%s' % (prefix, c)
            try:
                mod = importlib.import_module(m)
            except ModuleNotFoundError:
                break
            mods.append(m)
            ann.update(mod.ANN)
        return ann, mods

    # ---------------------------------------------------------------- 构建与校验
    def build(self, ann, collect=True):
        uamlib.ERRORS.clear()
        return uamlib.build(ann, self.bounds, self.text, collect=collect)

    def check(self, ann):
        recs, tab = self.build(ann)
        return recs, tab, list(uamlib.ERRORS)

    def validate(self, recs):
        by = {r['sid']: r for r in recs}
        out = {}
        out['越界'] = sum(1 for r in recs if r['end'] > len(self.text) or r['start'] < 0)
        out['父段无效'] = sum(1 for r in recs if r['pid'] and r['pid'] not in by)
        out['子段越界'] = sum(1 for r in recs if r['pid'] and r['pid'] in by and
                              not (by[r['pid']]['start'] <= r['start'] and r['end'] <= by[r['pid']]['end']))
        kids = defaultdict(list)
        for r in recs:
            kids[r['pid']].append(r)
        ov = 0
        for p, ks in kids.items():
            ks.sort(key=lambda x: x['start'])
            for a, b in zip(ks, ks[1:]):
                if b['start'] < a['end']:
                    ov += 1
        out['同层重叠'] = ov
        cov = [0] * len(self.text)
        for r in recs:
            for i in range(r['start'], r['end']):
                cov[i] = 1
        out['覆盖率'] = 100.0 * sum(cov) / len(self.text)
        # 句子归属
        bad = 0
        for r in recs:
            if self.sent_of(r['start']) < 0:
                bad += 1
        out['不属任何句'] = bad
        return out

    def sent_of(self, pos):
        for i, (s, e) in enumerate(self.bounds):
            if s <= pos < e:
                return i
        return -1

    # ---------------------------------------------------------------- 写盘与导出
    def idx_path(self):
        return os.path.join(self.root, 'Annotations/Texts/Text-1.txt', self.layer + '.idx')

    def write(self, recs):
        p = self.idx_path()
        if os.path.exists(p):
            import shutil, datetime
            shutil.copy2(p, p + '.bak-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
        uamlib.write_idx(p, recs)
        back, feats = uamlib.read_idx(p)
        assert len(back) == len(recs), '回读条数不符'
        assert feats == uamlib.FEATURES, '回读特征表不符'
        return p, os.path.getsize(p)

    def excel(self, recs, name=None):
        import openpyxl
        from openpyxl.styles import Font
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = '标注明细'
        ws.append(['段号', '句号', '父段', '层级', '起始', '结束', '原文片段', '特征', '盒子标签'])
        for i, r in enumerate(recs, start=2):
            lvl = '小句' if any(f in uamlib.PROC_FEATS for f in r['feats']) else '参与者/环境'
            ws.cell(i, 1, r['sid']).font = Font(name='Consolas', size=9)
            ws.cell(i, 2, self.sent_of(r['start']))
            ws.cell(i, 3, r['pid'] or '')
            ws.cell(i, 4, lvl)
            ws.cell(i, 5, r['start']).font = Font(name='Consolas', size=9)
            ws.cell(i, 6, r['end']).font = Font(name='Consolas', size=9)
            ws.cell(i, 7, self.text[r['start']:r['end']].replace('\n', ' '))
            ws.cell(i, 8, '+'.join(f for f in r['feats'] if f != 'clause')).font = Font(name='Consolas', size=9)
            ws.cell(i, 9, r.get('role') or ''.join(
                f for f in r['feats'] if f in uamlib.PROC_FEATS).capitalize())
        for col, w in zip('ABCDEFGHI', [7, 7, 7, 13, 8, 8, 70, 26, 16]):
            ws.column_dimensions[col].width = w
        ws.freeze_panes = 'A2'
        ws.auto_filter.ref = ws.dimensions
        ws2 = wb.create_sheet('统计')
        ws2.append(['特征', '类别', '次数'])
        cnt = Counter(f for r in recs for f in r['feats'] if f != 'clause')
        for k, v in cnt.most_common():
            cat = ('过程类型' if k in uamlib.PROC_FEATS else
                   '参与者角色' if k in uamlib.ROLE_FEATS else '环境成分')
            ws2.append([k, cat, v])
        for col, w in zip('ABC', [22, 14, 10]):
            ws2.column_dimensions[col].width = w
        p = os.path.join(self.out, name or '%s_%s标注复核表.xlsx' % (self.ch, self.layer))
        wb.save(p)
        return p

    def tsv(self, recs, name=None):
        rows = ['sid\tpid\tstart\tend\tfeatures\ttext']
        for r in sorted(recs, key=lambda x: (x['start'], -x['end'])):
            rows.append('%d\t%s\t%d\t%d\t%s\t%s' % (
                r['sid'], r['pid'] or '', r['start'], r['end'],
                '+'.join(r['feats']), self.norm(self.text[r['start']:r['end']])))
        p = os.path.join(self.out, name or '%s_%s标注明细.tsv' % (self.ch, self.layer))
        open(p, 'w', encoding='utf-8', newline='\n').write('\n'.join(rows))
        return p

    def html(self, recs, name=None):
        COLOR = {'material': '#58a6ff', 'mental': '#d2a8ff', 'relational': '#7ee787',
                 'verbal': '#ffa657', 'behavioural': '#79c0ff', 'existential': '#56d4dd'}
        ROLE, CIRC = '#e3b341', '#3fb950'
        text = self.text

        def render(s, e, kids):
            out, pos = [], s
            for k in kids:
                if k['start'] > pos:
                    out.append(html_escape(text[pos:k['start']]))
                lab = [f for f in k['feats'] if f != 'clause']
                if any(f in uamlib.PROC_FEATS for f in lab):
                    c = next((COLOR[f] for f in lab if f in COLOR), '#8b949e')
                    sub = render(k['start'], k['end'], k.get('kids', []))
                    out.append('<span class="cl" style="--c:%s"><i class="lab">%s</i>%s</span>'
                               % (c, '·'.join(lab), sub))
                else:
                    c = ROLE if any(f in uamlib.ROLE_FEATS for f in lab) else CIRC
                    inner = render(k['start'], k['end'], k.get('kids', [])) if k.get('kids') \
                        else html_escape(text[k['start']:k['end']])
                    out.append('<span class="pt" style="--c:%s"><i class="lab">%s</i>%s</span>'
                               % (c, '·'.join(lab), inner))
                pos = k['end']
            if pos < e:
                out.append(html_escape(text[pos:e]))
            return ''.join(out)

        blocks = []
        for sno in range(len(self.bounds)):
            s, e = self.bounds[sno]
            mine = [dict(r) for r in recs if s <= r['start'] and r['end'] <= e]
            if not mine:
                continue
            for r in mine:
                r['kids'] = sorted([k for k in mine if k['pid'] == r['sid']], key=lambda x: x['start'])
            tops = sorted([r for r in mine if r['pid'] == 0], key=lambda x: x['start'])
            blocks.append((sno, render(s, e, tops)))

        ncl = sum(1 for r in recs if any(f in uamlib.PROC_FEATS for f in r['feats']))
        pc = Counter(f for r in recs for f in r['feats'] if f in uamlib.PROC_FEATS)
        bars = ''.join('<span class="bar"><b>%s</b> %d</span>' % (k, pc[k])
                       for k in ['material', 'relational', 'mental', 'behavioural',
                                 'existential', 'verbal'])
        rc = Counter(f for r in recs for f in r['feats'] if f in uamlib.ROLE_FEATS)
        cc = Counter(f for r in recs for f in r['feats'] if f in uamlib.CIRC_FEATS)
        rbars = ' · '.join('%s <b>%d</b>' % (k, v) for k, v in rc.most_common())
        cbars = ' · '.join('%s <b>%d</b>' % (k, v) for k, v in cc.most_common())
        pol = '<br>\n'.join('%d. %s' % (i + 1, x) for i, x in enumerate(POLICY))
        H = ["""<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<title>%(ch)s %(layer)s标注复核</title><style>
:root{color-scheme:dark}
body{background:#0d1117;color:#c9d1d9;margin:0;padding:28px 36px 80px;
font-family:-apple-system,"Segoe UI",system-ui,"Microsoft YaHei",sans-serif;line-height:2.05;font-size:15px}
h1{font-size:19px;margin:0 0 4px;color:#e6edf3;font-weight:600}
.meta{color:#8b949e;font-size:13px;margin-bottom:16px}
.panel{background:#161b22;border:1px solid #21262d;border-radius:8px;padding:12px 16px;margin-bottom:22px;font-size:12.5px;color:#8b949e}
.bar{margin-right:16px;white-space:nowrap}.bar b{color:#c9d1d9;font-weight:600}
.sent{margin:0 0 22px;padding:12px 15px;background:#161b22;border:1px solid #21262d;border-radius:8px}
.sn{color:#484f58;font-family:ui-monospace,Consolas,monospace;font-size:11px;display:block;margin-bottom:1px}
.cl{border-bottom:2px solid var(--c);background:color-mix(in srgb,var(--c) 8%%,transparent);border-radius:2px;padding:0 1px}
.pt{background:color-mix(in srgb,var(--c) 15%%,transparent);border-radius:2px;padding:0 1px}
.lab{font-style:normal;font-size:10px;color:var(--c);font-family:ui-monospace,Consolas,monospace;vertical-align:super;margin-right:2px}
.cl>.lab{font-weight:700}
</style></head><body>
<h1>%(ch)s · %(layer)s标注复核</h1>
<div class="meta">%(ns)d 句 · %(ncl)d 个小句 · %(nseg)d 个标注段</div>
<div class="panel">过程类型：%(bars)s</div>
<div class="panel"><div>参与者角色：%(rbars)s</div>
<div style="margin-top:4px">环境成分：%(cbars)s</div></div>
<div class="panel"><b>口径</b>（外部核验请配合 xlsx / TSV 的「父段」列）<br>
%(pol)s
<br>
</div>
""" % dict(ch=self.ch, layer=self.layer, ns=len(blocks), ncl=ncl, nseg=len(recs), bars=bars,
           rbars=rbars, cbars=cbars, pol=pol)]
        for sno, body in blocks:
            H.append('<div class="sent"><span class="sn">S%d</span>%s</div>' % (sno, body))
        H.append('</body></html>')
        p = os.path.join(self.out, name or '%s_%s标注复核.html' % (self.ch, self.layer))
        open(p, 'w', encoding='utf-8', newline='\n').write('\n'.join(H))
        return p


def html_escape(s):
    import html as H
    return H.escape(s, quote=False)


def dump(chapter, lo, hi, base=None):
    p = Proj(chapter, base)
    for i in range(lo, min(hi, len(p.bounds))):
        print('%d|%s' % (i, p.sent(i)))
