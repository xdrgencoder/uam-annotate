#!/usr/bin/env python
# -*- coding: utf-8 -*-
""".doc / .docx / .rtf / .odt → HTML（替代 workbuddy 的 doc_convert_to_html）

    python doc_to_html.py 第三章.docx                    # 转出 第三章.html（同目录）
    python doc_to_html.py 第三章.doc --out-dir /tmp
    python doc_to_html.py 第三章.docx --out 第三章.html

后端优先级：LibreOffice(soffice) → pandoc → python-docx(仅 .docx)。
LibreOffice 用独立 profile 目录，避免与桌面端 soffice 抢锁。

只做格式转换，不做排版清洗：视觉行还原成段落交给 make_project.py 的 build_paragraphs()。
"""
import os, sys, subprocess, shutil, tempfile, argparse, uuid

SOFFICE_NAMES = ('soffice', 'libreoffice')


def which_soffice():
    for n in SOFFICE_NAMES:
        p = shutil.which(n)
        if p:
            return p
    return None


def convert_soffice(src, out_dir):
    exe = which_soffice()
    if not exe:
        return None
    prof = 'file://' + os.path.join(tempfile.gettempdir(), 'lo_uam_%s' % uuid.uuid4().hex[:8])
    cmd = [exe, '-env:UserInstallation=%s' % prof, '--headless',
           '--convert-to', 'html:HTML (StarWriter)', '--outdir', out_dir, src]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180,
                       env=dict(os.environ, HOME=tempfile.gettempdir()))
    cand = os.path.join(out_dir, os.path.splitext(os.path.basename(src))[0] + '.html')
    if r.returncode == 0 and os.path.exists(cand) and os.path.getsize(cand) > 0:
        return cand
    sys.stderr.write('[soffice] rc=%s %s\n' % (r.returncode, (r.stderr or '').strip()[:300]))
    return None


def convert_pandoc(src, out_dir):
    exe = shutil.which('pandoc')
    if not exe:
        return None
    cand = os.path.join(out_dir, os.path.splitext(os.path.basename(src))[0] + '.html')
    r = subprocess.run([exe, src, '-t', 'html', '-o', cand], capture_output=True, text=True, timeout=180)
    if r.returncode == 0 and os.path.exists(cand) and os.path.getsize(cand) > 0:
        return cand
    sys.stderr.write('[pandoc] rc=%s %s\n' % (r.returncode, (r.stderr or '').strip()[:300]))
    return None


def convert_docx(src, out_dir):
    try:
        import docx
        from xml.sax.saxutils import escape
    except ImportError:
        return None
    cand = os.path.join(out_dir, os.path.splitext(os.path.basename(src))[0] + '.html')
    d = docx.Document(src)
    parts = ['<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>']
    for p in d.paragraphs:
        t = p.text.strip()
        if t:
            parts.append('<p style="%s">%s</p>' % ('text-align:center' if p.alignment else '',
                                                   escape(t)))
    for tb in d.tables:
        for row in tb.rows:
            for cell in row.cells:
                t = cell.text.strip()
                if t:
                    parts.append('<p>%s</p>' % escape(t))
    parts.append('</body></html>')
    open(cand, 'w', encoding='utf-8', newline='\n').write('\n'.join(parts))
    return cand


BACKENDS = [('soffice', convert_soffice), ('pandoc', convert_pandoc), ('python-docx', convert_docx)]


def doc_to_html(src, out_dir=None, out_path=None):
    """返回生成的 html 路径；失败抛 RuntimeError。"""
    src = os.path.abspath(src)
    if not os.path.exists(src):
        raise RuntimeError('找不到输入文件: %s' % src)
    tmp = tempfile.mkdtemp(prefix='uam_doc_')
    try:
        got = None
        for tag, fn in BACKENDS:
            if tag == 'pandoc' and src.lower().endswith('.doc'):
                continue  # pandoc 不支持老式 .doc
            got = fn(src, tmp)
            if got:
                print('[doc] 后端 %s → %s' % (tag, os.path.basename(got)))
                break
        if not got:
            raise RuntimeError('三种后端都失败：装 LibreOffice 或 pandoc 后重试')
        out_path = os.path.abspath(out_path) if out_path else os.path.join(
            out_dir or os.path.dirname(src),
            os.path.splitext(os.path.basename(src))[0] + '.html')
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        shutil.copyfile(got, out_path)
        return out_path
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src', help='.doc / .docx / .rtf / .odt')
    ap.add_argument('--out', help='输出 html 路径')
    ap.add_argument('--out-dir', help='输出目录（默认与源文件同目录）')
    a = ap.parse_args()
    dst = doc_to_html(a.src, a.out_dir, a.out)
    print('HTML →', dst)


if __name__ == '__main__':
    main()
