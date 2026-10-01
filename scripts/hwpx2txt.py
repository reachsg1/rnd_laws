import sys, zipfile, re
from lxml import etree

HP = '{http://www.hancom.co.kr/hwpml/2011/paragraph}'

def run_text(p):
    """Text of a paragraph from its own runs only (tables handled separately)."""
    out = []
    for run in p.findall(HP + 'run'):
        for ch in run:
            if ch.tag == HP + 't':
                out.append(''.join(ch.itertext()))
            elif ch.tag == HP + 'tab':
                out.append(' ')
    return ''.join(out)

def cell_text(tc):
    parts = []
    for p in tc.iter(HP + 'p'):
        # only paragraphs whose nearest tbl ancestor is this cell's table
        t = run_text(p).strip()
        if t:
            parts.append(t)
    return ' '.join(parts)

def walk(el, lines):
    for p in el.iter(HP + 'p'):
        # skip paragraphs inside tables; tables emitted from their anchor paragraph
        anc = p.getparent()
        inside_tbl = False
        while anc is not None:
            if anc.tag == HP + 'tbl':
                inside_tbl = True; break
            anc = anc.getparent()
        if inside_tbl:
            continue
        t = run_text(p).strip()
        if t:
            lines.append(t)
        for tbl in p.iter(HP + 'tbl'):
            # only top-level tables of this paragraph
            a = tbl.getparent(); nested = False
            while a is not None and a is not p:
                if a.tag == HP + 'tbl': nested = True; break
                a = a.getparent()
            if nested: continue
            lines.append('[표]')
            for tr in tbl.findall(HP + 'tr'):
                cells = [cell_text(tc) for tc in tr.findall(HP + 'tc')]
                cells = [c for c in cells if c]
                if cells:
                    lines.append(' | '.join(cells))
            lines.append('[/표]')

def main(src, dst):
    z = zipfile.ZipFile(src)
    names = sorted(n for n in z.namelist() if re.match(r'Contents/section\d+\.xml', n))
    lines = []
    for n in names:
        parser = etree.XMLParser(huge_tree=True)
        root = etree.fromstring(z.read(n), parser)
        walk(root, lines)
    open(dst, 'w').write('\n'.join(lines))

main(sys.argv[1], sys.argv[2])
