#!/usr/bin/env python3
"""매일 국가법령정보센터 Open API로 법령·고시·훈령 8종의 현행본을 확인하고,
개정됐으면 data.json의 해당 문서 조문을 새 본문으로 바꾼다.

- 개정 없음: status.json의 checked 날짜만 갱신
- 개정 있음: data.json·status.json 갱신, updates에 기록
- 자동 반영이 안전하지 않다고 판단되면(조문 수 급감, 파싱 실패) data.json은 그대로 두고
  updates에 ok:false로 남긴 뒤 종료코드 2 → 워크플로 실패 메일로 담당자에게 알림

환경변수 LAW_OC: open.law.go.kr에서 발급받은 인증키(이메일 ID). 없으면 공개 테스트 키 사용.
"""
import json, os, re, sys, time, datetime
import urllib.request, urllib.parse
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OC = os.environ.get('LAW_OC') or 'test'
BASE = 'https://www.law.go.kr/DRF/'
KST = datetime.timezone(datetime.timedelta(hours=9))
TODAY = datetime.datetime.now(KST).strftime('%Y-%m-%d')


def get_xml(path, **params):
    params = {'OC': OC, 'type': 'XML', **params}
    url = BASE + path + '?' + urllib.parse.urlencode(params)
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'rnd-rules-updater/1.0'})
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
            return ET.fromstring(raw)
        except Exception as e:  # 네트워크·파싱 오류는 잠시 후 재시도
            last = e
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f'조회 실패: {url} ({last})')


def txt(el, tag):
    x = el.find('.//' + tag)
    return (x.text or '').strip() if x is not None and x.text else ''


def current_version(t):
    """lawSearch로 이름이 정확히 같은 현행 항목의 (일련번호, 번호, 시행일자)를 찾는다."""
    root = get_xml('lawSearch.do', target=t['target'], query=t['query'], display='50')
    if t['target'] == 'law':
        items, name_tag, serial_tag, no_tag, cur_tag = root.iter('law'), '법령명한글', '법령일련번호', '공포번호', '현행연혁코드'
    else:
        items, name_tag, serial_tag, no_tag, cur_tag = root.iter('admrul'), '행정규칙명', '행정규칙일련번호', '발령번호', '현행연혁구분'
    pending = None
    for it in items:
        if txt(it, name_tag).replace(' ', '') != t['name'].replace(' ', ''):
            continue
        v = {'serial': txt(it, serial_tag), 'no': txt(it, no_tag), 'eff': txt(it, '시행일자'), 'status': txt(it, cur_tag)}
        if v['status'] == '현행':
            return v, pending
        pending = v
    return None, pending


# ---------- 본문 → 조문 단위 섹션 (build.py의 law_sections와 같은 모양)
ART = re.compile(r'^제(\d+)조(?:의(\d+))?\s*(\([^)]*\)|삭제)?')
CHAP = re.compile(r'^(제\d+장|제\d+절|제\d+관)\s*')


def clean(s):
    return re.sub(r'[ \t]+', ' ', (s or '').replace('\r', '')).strip()


def law_body_sections(root):
    """법률·시행령·시행규칙 XML(lawService target=law)."""
    secs, path = [], {'장': '', '절': ''}
    for u in root.iter('조문단위'):
        kind = txt(u, '조문여부')
        head = clean(txt(u, '조문내용'))
        if kind == '전문' or (CHAP.match(head) and not ART.match(head)):
            m = CHAP.match(head)
            if m:
                if m.group(1).endswith('장'):
                    path['장'], path['절'] = head, ''
                else:
                    path['절'] = head
            continue
        no, br, title = txt(u, '조문번호'), txt(u, '조문가지번호'), txt(u, '조문제목')
        t = f'제{no}조' + (f'의{br}' if br and br != '0' else '')
        m = ART.match(head)
        if m:
            t = head[:m.end()].strip()
            body0 = head[m.end():].strip()
        else:
            t += f'({title})' if title else ''
            body0 = head
        lines = [body0] if body0 else []
        for hang in u.findall('항'):
            hl = clean(txt(hang, '항내용'))
            if hl:
                lines.append(hl)
            for ho in hang.findall('호'):
                l = clean(txt(ho, '호내용'))
                if l:
                    lines.append(l)
                for mok in ho.findall('목'):
                    for ml in (txt(mok, '목내용') or '').split('\n'):
                        if clean(ml):
                            lines.append(clean(ml))
        secs.append({'t': t, 'p': ' › '.join(x for x in (path['장'], path['절']) if x), 'x': '\n'.join(lines)})
    return secs


def admrul_body_sections(root):
    """고시·훈령 XML(lawService target=admrul): 조문내용이 조 단위 덩어리로 온다."""
    secs, path = [], {'장': '', '절': ''}
    for el in root.iter('조문내용'):
        block = (el.text or '').replace('\r', '').strip()
        if not block:
            continue
        first, *rest = [clean(l) for l in block.split('\n') if clean(l)]
        m = CHAP.match(first)
        if m and not ART.match(first):
            if m.group(1).endswith('장'):
                path['장'], path['절'] = first, ''
            else:
                path['절'] = first
            continue
        m = ART.match(first)
        if not m:
            if secs:
                secs[-1]['x'] += '\n' + '\n'.join([first] + rest)
            continue
        t = first[:m.end()].strip()
        body0 = first[m.end():].strip()
        secs.append({'t': t, 'p': ' › '.join(x for x in (path['장'], path['절']) if x),
                     'x': '\n'.join(([body0] if body0 else []) + rest)})
    return secs


def addenda(root):
    out = []
    for u in root.iter('부칙단위'):
        no, date = txt(u, '부칙공포번호'), txt(u, '부칙공포일자')
        body = (u.findtext('부칙내용') or '').replace('\r', '')
        out.append((no, date, body))
    if not out:  # 행정규칙: <부칙><부칙내용>…
        for el in root.iter('부칙내용'):
            out.append(('', '', (el.text or '').replace('\r', '')))
    if not out:
        return []
    no, date, body = out[0]  # 최신 부칙만 둔다(기존 데이터와 같은 방식)
    lines = [clean(l) for l in body.split('\n') if clean(l)]
    secs, head = [], None
    for l in lines:
        if l.startswith('부칙') and len(l) < 40:
            head = l
            continue
        m = ART.match(l)
        if m:
            secs.append({'t': '부칙 ' + l[:m.end()].strip(), 'p': '부칙', 'x': l[m.end():].strip()})
        elif secs:
            secs[-1]['x'] += '\n' + l
        else:
            secs.append({'t': head or '부칙', 'p': '부칙', 'x': l})
    title = head or (f'부칙 <제{no}호,{date[:4]}. {int(date[4:6])}. {int(date[6:])}.>' if len(date) == 8 else '부칙')
    if not secs or secs[0]['t'] != title:
        secs.insert(0, {'t': title, 'p': '부칙', 'x': ''})
    return secs


def fmt_date(d):
    return f'{d[:4]}. {int(d[4:6])}. {int(d[6:8])}.' if len(d) == 8 else d


KIND_LABEL = {'act': '법률', 'decree': '대통령령', 'rule': '과학기술정보통신부령'}


def fetch_document(doc, v):
    t = doc['track']
    if t['target'] == 'law':
        root = get_xml('lawService.do', target='law', MST=v['serial'])
        body = law_body_sections(root)
        kind = KIND_LABEL.get(doc['id'], '법령')
    else:
        root = get_xml('lawService.do', target='admrul', ID=v['serial'])
        body = admrul_body_sections(root)
        kind = txt(root, '행정규칙종류') or ('훈령' if doc['org'] == 'rda' else '고시')
    rev = txt(root, '제개정구분') or txt(root, '제개정구분명')
    pub = txt(root, '공포일자') or txt(root, '발령일자')
    info = {'t': '시행 정보', 'p': '', 'x': f'[시행 {fmt_date(v["eff"])}] [{kind} 제{v["no"]}호, {fmt_date(pub)}, {rev}]'.replace(', ]', ']')}
    org_kind = {'고시': '과기정통부 고시', '훈령': '농촌진흥청 훈령'}.get(kind, kind)
    meta = f'{org_kind} 제{v["no"].lstrip("0") or v["no"]}호 · 시행 {fmt_date(v["eff"])}'
    return [info] + body + addenda(root), meta


def article_ok(old, new):
    o = [s for s in old if ART.match(s['t'])]
    n = [s for s in new if ART.match(s['t'])]
    if not n or len(n) < 0.7 * len(o):
        return False, f'조문 수 {len(o)} → {len(n)}'
    keys = [(int(ART.match(s['t']).group(1)), int(ART.match(s['t']).group(2) or 0)) for s in n]
    if any(b <= a for a, b in zip(keys, keys[1:])):
        return False, '조 번호 순서가 맞지 않음'
    return True, f'조문 {len(o)} → {len(n)}'


def main():
    dpath, spath = os.path.join(ROOT, 'data.json'), os.path.join(ROOT, 'status.json')
    data = json.load(open(dpath, encoding='utf-8'))
    status = json.load(open(spath, encoding='utf-8'))
    docs = {d['id']: d for d in data['docs']}
    changed, manual, notes = False, [], []

    for t in status['tracked']:
        doc = docs[t['id']]
        try:
            v, pending = current_version(t)
        except Exception as e:
            notes.append(f'- {doc["short"]}: 조회 실패({e}) — 다음 회차에 다시 확인')
            continue
        if pending and (not v or pending['eff'] > v['eff']):
            notes.append(f'- {doc["short"]}: 시행 예정 개정 있음 (제{pending["no"]}호, 시행 {fmt_date(pending["eff"])})')
        if not v:
            notes.append(f'- {doc["short"]}: 현행 항목을 찾지 못함')
            continue
        if (v['serial'], v['no'], v['eff']) == (t['serial'], t['no'], t['eff']):
            continue
        try:
            new_secs, meta = fetch_document(doc, v)
        except Exception as e:
            manual.append(doc['short'])
            notes.append(f'- {doc["short"]}: 개정 확인(제{v["no"]}호) — 본문 조회 실패({e})')
            status['updates'].insert(0, {'date': TODAY, 'doc': doc['short'], 'from': t['no'], 'to': f'제{v["no"]}호 · 시행 {fmt_date(v["eff"])}', 'ok': False})
            continue
        old = [s for s in data['secs'] if s['d'] == doc['id']]
        ok, why = article_ok(old, new_secs)
        if not ok:
            manual.append(doc['short'])
            notes.append(f'- {doc["short"]}: 개정 확인(제{v["no"]}호) — 자동 반영 보류({why}), 개정 원문으로 수동 반영 필요')
            status['updates'].insert(0, {'date': TODAY, 'doc': doc['short'], 'from': t['no'], 'to': f'제{v["no"]}호 · 시행 {fmt_date(v["eff"])}', 'ok': False})
            continue
        # 같은 위치에 교체
        first = next(i for i, s in enumerate(data['secs']) if s['d'] == doc['id'])
        rest = [s for s in data['secs'] if s['d'] != doc['id']]
        for s in new_secs:
            s['d'] = doc['id']
        data['secs'] = rest[:first] + new_secs + rest[first:]
        doc['meta'], doc['n'] = meta, len(new_secs)
        doc['track'].update(serial=v['serial'], no=v['no'], eff=v['eff'])
        status['updates'].insert(0, {'date': TODAY, 'doc': doc['short'], 'from': t['no'], 'to': f'제{v["no"]}호 · 시행 {fmt_date(v["eff"])}', 'ok': True})
        t.update(serial=v['serial'], no=v['no'], eff=v['eff'])
        notes.append(f'- {doc["short"]}: 제{t["no"]}호로 반영 ({why})')
        changed = True

    status['updates'] = status['updates'][:20]
    status['checked'] = TODAY
    data['checked'] = TODAY
    if changed:
        json.dump(data, open(dpath, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    json.dump(status, open(spath, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    report = f'## 규정 개정 점검 {TODAY}\n' + ('\n'.join(notes) if notes else '- 8종 모두 현행본과 같음')
    print(report)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8').write(report + '\n')
    if manual:
        print('수동 반영 필요: ' + ', '.join(manual), file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    main()
