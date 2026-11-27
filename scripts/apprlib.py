# -*- coding: utf-8 -*-
"""评价理论（Appraisal）标注库：解析方案 → 校验特征组合 → 写 .idx → 复核件

方案取 UAM CT6 自带的 Appraisal_max.xml（31 系统 / 75 特征 + 根特征 appraisal）。
与及物性层最大的结构差异：一个跨度要同时落多个系统的特征，例如

    'a depressing sight'  →  attitude + appreciation + reaction + quality
                             + negative-attitude + inscribed

所以 .idx 的记录是「特征集合」（位图），不是单特征；同一跨度只写一条记录，
多个系统的特征按位或进同一张位图。

用法：
    from apprlib import ApprProj
    p = ApprProj('评价项目')
    ann = {0: [('a depressing sight', ['attitude', 'appreciation', 'reaction',
                                      'quality', 'negative-attitude', 'inscribed'])]}
    recs, tab, errs = p.check(ann)
    print(p.validate(recs))
    p.write(recs); p.excel(recs); p.tsv(recs); p.html(recs)
"""
import os, re, sys, struct, importlib
from collections import Counter, defaultdict, OrderedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import uamlib


# ---------------------------------------------------------------- 方案解析
class Scheme:
    """.xml → 特征表 + 系统表 + 入口条件（EC）链"""

    def __init__(self, path):
        raw = open(path, encoding='utf-8').read()
        root = re.search(r'<ROOT>(.*?)</ROOT>', raw, re.S)
        self.root = (re.search(r'<NAME>(.*?)</NAME>', root.group(1), re.S)
                     .group(1).strip() if root else 'appraisal')
        self.systems = OrderedDict()      # 系统名 -> (EC, [特征…])
        self.feat2sys, self.feat2ec, self.gloss = {}, {}, {}
        order = [self.root]
        for s in re.findall(r'<SYSTEM>(.*?)</SYSTEM>', raw, re.S):
            nm = re.search(r'<NAME>(.*?)</NAME>', s, re.S).group(1).strip()
            ec = re.search(r'<EC>(.*?)</EC>', s, re.S)
            ec = re.sub(r'\s+', ' ', ec.group(1)).strip() if ec else self.root
            feats = []
            for f in re.findall(r'<FEATURE>(.*?)</FEATURE>', s, re.S):
                fn = re.search(r'<NAME>(.*?)</NAME>', f, re.S).group(1).strip()
                if fn in self.feat2sys and self.feat2sys[fn] != nm:
                    raise ValueError('特征 %r 同时出现在 %s 与 %s'
                                     % (fn, self.feat2sys[fn], nm))
                gl = re.search(r'<GLOSS>(.*?)</GLOSS>', f, re.S)
                feats.append(fn)
                self.feat2sys[fn] = nm
                self.feat2ec[fn] = ec
                if gl:
                    self.gloss[fn] = re.sub(r'\s+', ' ', gl.group(1)).strip()
                if fn not in order:
                    order.append(fn)
            self.systems[nm] = (ec, feats)
        self.features = order
        self.fset = set(order)
        self.of = {f: i for i, f in enumerate(order)}
        self._depth = {}

    # 特征到根的层数，用于挑盒子标签
    def depth(self, f):
        if f in self._depth:
            return self._depth[f]
        d, cur, seen = 1, f, {f}
        while True:
            ec = self.feat2ec.get(cur)
            if not ec or ec == self.root or ec in seen:
                break
            seen.add(ec)
            d += 1
            cur = ec
        self._depth[f] = d
        return d

    def spine(self, feats):
        """最深那条链（根之外），作 UAM 盒子标签，如 appreciation·reaction·quality"""
        cand = [f for f in feats if f != self.root]
        if not cand:
            return self.root
        cand.sort(key=lambda f: (-self.depth(f), self.of.get(f, 0)))
        leaf, chain = cand[0], []
        cur = leaf
        while cur and cur != self.root:
            chain.append(cur)
            cur = self.feat2ec.get(cur)
        return '·'.join(reversed(chain))

    # 一段特征组合是否合法
    def diagnose(self, feats):
        bad = []
        unknown = [f for f in feats if f not in self.fset]
        if unknown:
            return ['未知特征 %s（该方案没有这些特征）' % ', '.join(unknown)]
        sel = set(feats)
        bysys = defaultdict(list)
        for f in sel:
            bysys[self.feat2sys.get(f, '')].append(f)
        for sysname, fs in bysys.items():
            if sysname and len(fs) > 1:
                bad.append('系统 %s 只能取一个特征，却给了 %s'
                           % (sysname, ' / '.join(sorted(fs))))
        for f in sorted(sel):
            if f == self.root:
                continue
            ec = self.feat2ec.get(f)
            if ec and ec != self.root and ec not in sel:
                bad.append('%s 的入口条件是 %s，必须同时选中' % (f, ec))
        return bad


# ---------------------------------------------------------------- 项目
class ApprProj:
    def __init__(self, chapter, base=None, out=None, scheme=None, layer='评价'):
        base = base or os.environ.get('UAM_BASE') or os.getcwd()
        self.root = chapter if os.path.isabs(chapter) else os.path.join(base, chapter)
        self.ch = os.path.basename(self.root.rstrip('/\\'))
        self.out = out or base
        self.layer = layer
        os.makedirs(self.out, exist_ok=True)
        self.text = open(os.path.join(self.root, 'Corpus/Texts/Text-1.txt'),
                         encoding='utf-8').read()
        d = open(os.path.join(self.root, 'Annotations/Texts/Text-1.txt/sentence.dat'),
                 'rb').read()
        self.bounds = [struct.unpack('2I', d[i * 8:(i + 1) * 8])
                       for i in range(len(d) // 8)]
        path = scheme or os.path.join(self.root, 'Schemes', layer + '.xml')
        if not os.path.exists(path):
            path = os.path.join(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))), 'assets', 'scheme-appraisal.xml')
        self.scheme = Scheme(path)
        self.scheme_path = path

    def norm(self, s):
        return re.sub(r'\s+', ' ', s).strip()

    def sent(self, i):
        s, e = self.bounds[i]
        return self.norm(self.text[s:e])

    def sent_of(self, pos):
        for i, (s, e) in enumerate(self.bounds):
            if s <= pos < e:
                return i
        return -1

    def load_ann(self, prefix, letters='abcdefghijklmn'):
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

    # ------------------------------------------------------------ 构建
    def check(self, ann):
        recs, errs, sid = [], [], 0
        sch = self.scheme
        for sno in sorted(ann):
            if not 0 <= sno < len(self.bounds):
                errs.append('句号 %d 越界（共 %d 句）' % (sno, len(self.bounds)))
                continue
            st, en = self.bounds[sno]
            S = uamlib.Sent(self.text, st, en)

            def emit(item, pid, lo, hi):
                nonlocal sid
                quote, feats, nth, kids = _item(item)
                probs = sch.diagnose(feats)
                if probs:
                    errs.extend('S%d %r: %s' % (sno, quote[:40], p) for p in probs)
                    return
                label = 'S%d %r' % (sno, quote[:30])
                try:
                    a, b = S.find(quote, lo, hi, label, nth)
                except Exception as ex:
                    errs.append(str(ex))
                    return
                sid += 1
                this = sid
                full = [sch.root] + [f for f in sorted(feats, key=lambda x: sch.of[x])]
                recs.append(dict(sid=this, pid=pid, start=a, end=b, feats=full,
                                 role=sch.spine(feats)))
                for kid in kids:
                    emit(kid, this, a, b)

            for item in ann[sno]:
                emit(item, 0, st, en)

        # 同一跨度重复标注 → 应合并到一条记录
        seen = {}
        for r in recs:
            k = (r['start'], r['end'], r['pid'])
            if k in seen:
                errs.append('跨度 %d-%d 被标了两次（sid %d / %d），请合并特征'
                            % (r['start'], r['end'], seen[k], r['sid']))
            seen[k] = r['sid']
        return recs, errs

    # ------------------------------------------------------------ 校验
    def validate(self, recs):
        by = {r['sid']: r for r in recs}
        out = {}
        out['越界'] = sum(1 for r in recs if r['end'] > len(self.text) or r['start'] < 0)
        out['父段无效'] = sum(1 for r in recs if r['pid'] and r['pid'] not in by)
        out['子段越界'] = sum(1 for r in recs if r['pid'] in by and
                              not (by[r['pid']]['start'] <= r['start']
                                   and r['end'] <= by[r['pid']]['end']))
        out['跨句'] = sum(1 for r in recs
                          if self.sent_of(r['start']) != self.sent_of(r['end'] - 1))
        kids = defaultdict(list)
        for r in recs:
            kids[r['pid']].append(r)
        ov = 0
        for ks in kids.values():
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
        # 评价标注天然稀疏，覆盖率只作参考，不设阈值
        return out

    # ------------------------------------------------------------ 写盘
    def idx_path(self):
        return os.path.join(self.root, 'Annotations/Texts/Text-1.txt',
                            self.layer + '.idx')

    def write(self, recs):
        p = self.idx_path()
        old = list(uamlib.FEATURES)
        if os.path.exists(p):
            import shutil, datetime
            shutil.copy2(p, p + '.bak-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
        uamlib.set_features(self.scheme.features)
        try:
            uamlib.write_idx(p, recs)
            back, feats = uamlib.read_idx(p)
        finally:
            uamlib.set_features(old)
        assert len(back) == len(recs), '回读条数不符'
        assert feats == self.scheme.features, '回读特征表不符'
        for a, b in zip(sorted(recs, key=lambda r: r['sid']), back):
            assert set(a['feats']) == set(b['feats']), 'sid %d 特征不符' % a['sid']
        return p, os.path.getsize(p)

    # ------------------------------------------------------------ 复核件
    def excel(self, recs, name=None):
        import openpyxl
        from openpyxl.styles import Font
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = '标注明细'
        ws.append(['段号', '句号', '父段', '起始', '结束', '原文片段', '特征', '盒子标签'])
        sch = self.scheme
        for i, r in enumerate(sorted(recs, key=lambda x: (x['start'], -x['end'])), start=2):
            ws.cell(i, 1, r['sid']).font = Font(name='Consolas', size=9)
            ws.cell(i, 2, self.sent_of(r['start']))
            ws.cell(i, 3, r['pid'] or '')
            ws.cell(i, 4, r['start']).font = Font(name='Consolas', size=9)
            ws.cell(i, 5, r['end']).font = Font(name='Consolas', size=9)
            ws.cell(i, 6, self.norm(self.text[r['start']:r['end']]))
            ws.cell(i, 7, '+'.join(f for f in r['feats'] if f != sch.root)) \
                .font = Font(name='Consolas', size=9)
            ws.cell(i, 8, r.get('role') or '')
        for col, w in zip('ABCDEFGH', [7, 7, 7, 8, 8, 62, 46, 30]):
            ws.column_dimensions[col].width = w
        ws.freeze_panes = 'A2'
        ws.auto_filter.ref = ws.dimensions

        ws2 = wb.create_sheet('统计')
        ws2.append(['系统', '特征', '次数', '占标注段'])
        n = len(recs) or 1
        hit = Counter(f for r in recs for f in r['feats'] if f != sch.root)
        for sysname, (ec, feats) in sch.systems.items():
            for f in feats:
                c = hit.get(f, 0)
                if c:
                    ws2.append([sysname, f, c, round(100.0 * c / n, 1)])
        for col, w in zip('ABCD', [26, 22, 8, 12]):
            ws2.column_dimensions[col].width = w

        ws3 = wb.create_sheet('系统覆盖')
        ws3.append(['系统', '入口条件', '可选特征', '本层用到'])
        for sysname, (ec, feats) in sch.systems.items():
            used = [f for f in feats if hit.get(f)]
            ws3.append([sysname, ec, ' / '.join(feats), ' / '.join(used)])
        for col, w in zip('ABCD', [26, 18, 60, 40]):
            ws3.column_dimensions[col].width = w

        p = os.path.join(self.out, name or '%s_评价标注复核表.xlsx' % self.ch)
        wb.save(p)
        return p

    def tsv(self, recs, name=None):
        rows = ['sid\tpid\tstart\tend\tfeatures\tlabel\ttext']
        sch = self.scheme
        for r in sorted(recs, key=lambda x: (x['start'], -x['end'])):
            rows.append('%d\t%s\t%d\t%d\t%s\t%s\t%s' % (
                r['sid'], r['pid'] or '', r['start'], r['end'],
                '+'.join(r['feats']), r.get('role', ''),
                self.norm(self.text[r['start']:r['end']])))
        p = os.path.join(self.out, name or '%s_评价标注明细.tsv' % self.ch)
        open(p, 'w', encoding='utf-8', newline='\n').write('\n'.join(rows))
        return p

    def html(self, recs, name=None):
        sch = self.scheme
        n = len(recs)
        hit = Counter(f for r in recs for f in r['feats'] if f != sch.root)
        fam = {'attitude': '#58a6ff', 'engagement': '#d2a8ff', 'graduation': '#7ee787'}
        rows = []
        for sysname, (ec, feats) in sch.systems.items():
            used = ' · '.join('%s <b>%d</b>' % (f, hit[f]) for f in feats if hit.get(f))
            if used:
                rows.append('<tr><td>%s</td><td class="ec">%s</td><td>%s</td></tr>'
                            % (sysname, ec, used))
        blocks = []
        for sno in range(len(self.bounds)):
            s, e = self.bounds[sno]
            mine = sorted([r for r in recs if s <= r['start'] and r['end'] <= e],
                          key=lambda x: (x['start'], -x['end']))
            if not mine:
                continue
            out, pos = [], s
            for r in mine:
                if r['start'] < pos:
                    continue
                if r['start'] > pos:
                    out.append(_esc(self.text[pos:r['start']]))
                top = next((f for f in r['feats'] if f in fam), '#8b949e')
                lab = r.get('role') or ''
                out.append('<span class="sp" style="--c:%s"><i class="lab">%s</i>%s</span>'
                           % (top, _esc(lab), _esc(self.text[r['start']:r['end']])))
                pos = r['end']
            if pos < e:
                out.append(_esc(self.text[pos:e]))
            blocks.append('<div class="sent"><span class="sn">S%d</span>%s</div>'
                          % (sno, ''.join(out)))
        H = ["""<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<title>%(ch)s 评价标注复核</title><style>
:root{color-scheme:dark}
body{background:#0d1117;color:#c9d1d9;margin:0;padding:28px 36px 80px;
font-family:-apple-system,"Segoe UI",system-ui,"Microsoft YaHei",sans-serif;line-height:2.05;font-size:15px}
h1{font-size:19px;margin:0 0 4px;color:#e6edf3;font-weight:600}
.meta{color:#8b949e;font-size:13px;margin-bottom:16px}
.panel{background:#161b22;border:1px solid #21262d;border-radius:8px;padding:12px 16px;margin-bottom:22px;font-size:12.5px;color:#8b949e}
table{border-collapse:collapse;width:100%%;font-size:12.5px}
td{padding:3px 10px 3px 0;vertical-align:top;border-bottom:1px solid #21262d}
td.ec{color:#6e7681;font-family:ui-monospace,Consolas,monospace}
.sent{margin:0 0 22px;padding:12px 15px;background:#161b22;border:1px solid #21262d;border-radius:8px}
.sn{color:#484f58;font-family:ui-monospace,Consolas,monospace;font-size:11px;display:block;margin-bottom:1px}
.sp{background:color-mix(in srgb,var(--c) 14%%,transparent);border-bottom:2px solid var(--c);border-radius:2px;padding:0 1px}
.lab{font-style:normal;font-size:10px;color:var(--c);font-family:ui-monospace,Consolas,monospace;vertical-align:super;margin-right:2px}
</style></head><body>
<h1>%(ch)s · 评价标注复核</h1>
<div class="meta">%(ns)d 句有标注 · %(n)d 个标注段 · 方案 %(np)d 系统 / %(nf)d 特征</div>
<div class="panel"><table>%(rows)s</table></div>
""" % dict(ch=self.ch, ns=len(blocks), n=n, np=len(sch.systems),
           nf=len(sch.features) - 1, rows=''.join(rows))]
        H.extend(blocks)
        H.append('</body></html>')
        p = os.path.join(self.out, name or '%s_评价标注复核.html' % self.ch)
        open(p, 'w', encoding='utf-8', newline='\n').write('\n'.join(H))
        return p


def _item(item):
    """(片段, [特征…]) | (片段, [特征…], nth) | (片段, [特征…], nth, [子段…])"""
    quote, feats = item[0], list(item[1])
    nth = item[2] if len(item) > 2 else None
    kids = item[3] if len(item) > 3 else []
    return quote, feats, nth, kids


def _esc(s):
    import html as H
    return H.escape(s, quote=False)


def dump(chapter, lo, hi, base=None, layer='评价'):
    p = ApprProj(chapter, base, layer=layer)
    for i in range(lo, min(hi, len(p.bounds))):
        print('%d|%s' % (i, p.sent(i)))
