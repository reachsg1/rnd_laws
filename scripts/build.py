import re, json

T = 'txt/'
DOCS = [
  # id, file, name, short, org, kind, meta, track(target, query, serial, no, eff)
  ('act','act','국가연구개발혁신법','혁신법','nat','law','법률 제21421호 · 시행 2026. 9. 11.',('law','국가연구개발혁신법','283849','21421','20260911')),
  ('decree','decree','국가연구개발혁신법 시행령','혁신법 시행령','nat','law','대통령령 제36525호 · 시행 2026. 9. 11.',('law','국가연구개발혁신법 시행령','288335','36525','20260911')),
  ('rule','rule','국가연구개발혁신법 시행규칙','혁신법 시행규칙','nat','law','과학기술정보통신부령 제173호 · 시행 2026. 8. 20.',('law','국가연구개발혁신법 시행규칙','289003','00173','20260820')),
  ('cost','rnd_cost_std','국가연구개발사업 연구개발비 사용 기준','연구개발비 사용 기준','nat','law','과기정통부 고시 제2026-38호 · 시행 2026. 5. 6.',('admrul','국가연구개발사업 연구개발비 사용 기준','2100000278740','2026-38','20260506')),
  ('dist','msit_dist','연구성과 관리·유통 전담기관 지정 고시','성과 전담기관 고시','nat','law','과기정통부 고시 제2022-41호 · 시행 2022. 6. 29.',('admrul','연구성과 관리·유통 전담기관 지정 고시','2100000212539','2022-41','20220629')),
  ('bio','bio','생명연구자원법 제8조 책임기관 및 기탁등록보존기관','생명자원 기탁기관','nat','plain','전담기관 지정 고시 붙임 1',None),
  ('rda','rda_rule','농촌진흥청 농업과학기술 연구개발사업 운영규정','농진청 운영규정','rda','law','농촌진흥청 훈령 제1501호 · 시행 2025. 11. 28.',('admrul','농촌진흥청 농업과학기술 연구개발사업 운영규정','2100000268930','1501','20251128')),
  ('rcost','rda_cost','농촌진흥청 농업과학기술 연구개발사업 연구개발비 관리지침','농진청 연구비 관리지침','rda','hwpx','2026. 6. 개정',None),
  ('pub','rda_publish','농촌진흥청 연구결과 대외발표 규정','농진청 대외발표 규정','rda','law','농촌진흥청 훈령 제1520호 · 시행 2026. 5. 1.',('admrul','농촌진흥청 연구결과 대외발표 규정','2100000278044','1520','20260501')),
  ('note','rda_note','농촌진흥청 연구노트 관리지침','농진청 연구노트 지침','rda','law','농촌진흥청 훈령 제1488호 · 시행 2025. 6. 16.',('admrul','농촌진흥청 연구노트 관리지침','2100000260338','1488','20250616')),
  ('man','manual','농촌진흥청 농업과학기술 연구개발사업 운영 매뉴얼(본문)','농진청 운영매뉴얼','rda','hwpx','2025. 12. 개정',None),
  ('form','forms','농촌진흥청 농업과학기술 연구개발사업 운영 매뉴얼(별표·서식)','농진청 매뉴얼 서식','rda','forms','2025. 12. 개정',None),
  ('ind','indicator','농촌진흥청 연구성과지표 지표정의서','농진청 성과지표 정의서','rda','indicator','2025. 12. 수정',None),
]

CIRC = '①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳'
NEWLINE_MARK = re.compile(r'^([' + CIRC + r']|\d+\.|\d+\)|[가-하]\.|[가-하]\)|\(\d+\)|\([가-하]\)|제\d+조|※|-|ㅇ|○|□|■|◦|•|\[|부칙|o\s)')
ART = re.compile(r'^제(\d+)조(?:의(\d+))?(\(([^)]*)\)|\s*삭제)')
CHAP = re.compile(r'^(제\d+장|제\d+절)\s*(.*)$')

def law_sections(docid, text, title):
    lines = text.split('\n')
    out = []  # list of dict(t, p, lines)
    chap = {'장': '', '절': ''}
    cur = {'t': '시행 정보', 'p': '', 'lines': []}
    last = (0, 0)
    in_bu = False
    for raw in lines:
        if re.match(r'^\s*법제처\s+\d+\s+국가법령정보센터\s*$', raw):
            continue
        s = raw.strip()
        if not s:
            continue
        if s == title:
            continue
        indent = len(raw) - len(raw.lstrip(' '))
        m = ART.match(s) if indent <= 1 else None
        if m and not in_bu:
            key = (int(m.group(1)), int(m.group(2) or 0))
            if key <= last:
                m = None
        if m and in_bu:
            key = (int(m.group(1)), int(m.group(2) or 0))
        c = CHAP.match(s)
        if c and len(s) < 60:
            if c.group(1).endswith('장'):
                chap['장'] = s; chap['절'] = ''
            else:
                chap['절'] = s
            continue
        if s.startswith('부칙') and len(s) < 40:
            out.append(cur)
            cur = {'t': s, 'p': '부칙', 'lines': []}
            in_bu = True
            continue
        if m:
            out.append(cur)
            last = key
            t = s[:m.end()]
            rest = s[m.end():].strip()
            p = ' › '.join(x for x in (chap['장'], chap['절']) if x) if not in_bu else cur['p'] if cur['p'] == '부칙' else '부칙'
            if in_bu:
                t = '부칙 ' + t
            cur = {'t': t, 'p': p, 'lines': [rest] if rest else []}
            continue
        # continuation or new line
        if cur['lines'] and not NEWLINE_MARK.match(s):
            prev = cur['lines'][-1]
            sep = ' ' if (prev[-1:] in '.,)>」』:;' or s[:1] in '<(「') else ''
            cur['lines'][-1] = prev + sep + s
        else:
            cur['lines'].append(s)
    out.append(cur)
    res = []
    for c in out:
        body = '\n'.join(c['lines']).strip()
        if not body and c['t'] == '시행 정보':
            continue
        res.append({'t': c['t'], 'p': c['p'], 'x': body})
    if not any(r['t'].startswith('제') for r in res) and res and res[0]['t'] == '시행 정보':
        res[0]['t'] = '본문'
    return res

ROMAN = 'ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫ'
H1 = re.compile(r'^([' + ROMAN + r'])\s*\.\s*(.+)$')
H2 = re.compile(r'^(\d{1,2})\.\s*(.+)$')
H3 = re.compile(r'^([가-하])\.\s*(.+)$')
H4 = re.compile(r'^(\(\d{1,2}\)|\d{1,2}\))\s*\S.*$')

def is_heading_text(s):
    return len(s) <= 45 and not re.search(r'(다|음|함|임|것)\.?$', s) and not s.endswith('.') and '|' not in s

def hwpx_sections(text, split_h3=True):
    lines = text.split('\n')
    # skip table of contents: find first H1 after 목차, strip page nums, find its 2nd occurrence
    start = 0
    for i, l in enumerate(lines[:400]):
        m = H1.match(l)
        if m:
            key = re.sub(r'\s*\d+$', '', l).strip()
            for j in range(i + 1, len(lines)):
                if re.sub(r'\s+', '', lines[j]) == re.sub(r'\s+', '', key):
                    start = j; break
            break
    ctx = ['', '', '']
    out = []
    cur = {'t': '개요', 'p': '', 'lines': []}
    depth = 0
    for l in lines[start:]:
        s = l.strip()
        if not s:
            continue
        if s in ('[표]', '[/표]'):
            cur['lines'].append(s); continue
        lvl = None
        if H1.match(s) and is_heading_text(s):
            lvl = 0
        elif H2.match(s) and is_heading_text(s) and len(s) <= 35:
            lvl = 1
        elif split_h3 and H3.match(s) and is_heading_text(s) and len(s) <= 30:
            lvl = 2
        m = re.match(r'^【\s*별표\s*\d+\s*】.*', s)
        if m and len(s) < 60:
            lvl = 0
        if lvl is not None:
            if cur['lines'] or cur['t'] != '개요':
                out.append(cur)
            ctx[lvl] = s
            for k in range(lvl + 1, 3):
                ctx[k] = ''
            path = ' › '.join(x for x in ctx[:lvl] if x)
            cur = {'t': s, 'p': path, 'lines': []}
        else:
            cur['lines'].append(s)
    out.append(cur)
    res = []
    for c in out:
        if not c['lines']: continue
        if sum(len(x) for x in c['lines']) > 3500:
            parts = [{'t': c['t'], 'p': c['p'], 'lines': []}]
            intbl = False
            for x in c['lines']:
                if x == '[표]': intbl = True
                if x == '[/표]': intbl = False
                if not intbl and H4.match(x) and is_heading_text(x) and len(x) <= 30 and sum(len(y) for y in parts[-1]['lines']) > 150:
                    parts.append({'t': x, 'p': (c['p'] + ' › ' if c['p'] else '') + c['t'], 'lines': []})
                else:
                    parts[-1]['lines'].append(x)
            res += parts
        else:
            res.append(c)
    return [{'t': c['t'], 'p': c['p'], 'x': clean_tables('\n'.join(c['lines']))} for c in res if c['lines']]

def clean_tables(x):
    # drop empty table wrappers
    x = re.sub(r'\[표\]\n\[/표\]\n?', '', x)
    return x.strip()

def form_sections(text):
    lines = [l.strip() for l in text.split('\n')]
    pat = re.compile(r'^【\s*(별표\s*\d+|별지\s*제?\s*[\d-]+\s*호\s*서식|부표\s*\d+|소속기관 추가 서식\s*\d+)\s*】')
    names = {}; part = 'main'; start = 0
    for i, l in enumerate(lines[:400]):
        if l == '소속기관 규정 서식 목록': part = 'inst'
        m = pat.match(l)
        if m and re.search(r'\d$', l):
            nm = re.sub(r'\s*\d+$', '', l[m.end():]).strip()
            names[(part, re.sub(r'\s', '', m.group(1)))] = nm
        elif m:
            start = i; break
    out = []; cur = None; part = 'main'; lastno = 0; seen_bupyo = False
    for l in lines[start:]:
        if not l: continue
        m = pat.match(l)
        if m and len(l) < 80:
            lab = re.sub(r'\s', '', m.group(1))
            if lab.startswith('부표'): seen_bupyo = True
            if lab.startswith('소속기관'): part = 'inst'
            if lab.startswith('별지'):
                no = int(re.search(r'\d+', lab).group())
                if seen_bupyo and no < lastno: part = 'inst'
                lastno = no
            if cur: out.append(cur)
            if '삭제' in l[m.end():]:
                cur = None; continue
            nm = names.get((part, lab), '')
            grp = '별표' if lab.startswith('별표') else '부표' if lab.startswith('부표') else ('소속기관 규정 서식' if part == 'inst' else '서식')
            cur = {'t': m.group(0) + (' ' + nm if nm else ''), 'p': grp, 'lines': []}
        elif cur is not None:
            cur['lines'].append(l)
    if cur: out.append(cur)
    return [{'t': c['t'], 'p': c['p'], 'x': clean_tables('\n'.join(c['lines']))} for c in out if c['lines']]

def indicator_sections(text):
    lines = text.split('\n')
    out = []
    cur = {'t': '연구성과지표 현황(총괄표)', 'p': '', 'lines': []}
    for l in lines:
        s = l.strip()
        if not s: continue
        if s.startswith('관리번호 |'):
            out.append(cur)
            cur = {'t': '', 'p': '지표별 세부내역', 'lines': []}
        if s.startswith('지 표 명 |') and not cur['t']:
            cur['t'] = s.split('|', 1)[1].strip()
        cur['lines'].append(s)
    out.append(cur)
    res = []
    for c in out:
        # tidy wrapper table markers
        body = clean_tables('\n'.join(c['lines']))
        body = re.sub(r'\n?\[표\]\n지표별 세부내역\n\[/표\]', '', body)
        res.append({'t': c['t'] or '지표', 'p': c['p'], 'x': body})
    return res

docs, secs = [], []
for did, fn, name, short, org, kind, meta, track in DOCS:
    text = open(T + fn + '.txt').read()
    if kind == 'law':
        ss = law_sections(did, text, next(l.strip() for l in text.split('\n') if l.strip()))
        # page header lines are the doc title as printed; strip any exact title-only lines
    elif kind == 'hwpx':
        ss = hwpx_sections(text)
    elif kind == 'forms':
        ss = form_sections(text)
    elif kind == 'indicator':
        ss = indicator_sections(text)
    else:
        ss = [{'t': name, 'p': '', 'x': text.strip()}]
    d = {'id': did, 'name': name, 'short': short, 'org': org, 'meta': meta, 'n': len(ss)}
    if track: d['track'] = dict(zip(['target','query','serial','no','eff'], track))
    docs.append(d)
    for s in ss:
        s['d'] = did
        secs.append(s)
    print(did, len(ss))

json.dump({'docs': docs, 'secs': secs, 'checked': '2026-10-01', 'updates': []}, open('data.json', 'w'), ensure_ascii=False, separators=(',', ':'))
import os; print('bytes', os.path.getsize('data.json'))
