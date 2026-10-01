# -*- coding: utf-8 -*-
r"""오버레이·실행 파일 문자열 추출 (2026-10-01) — 메뉴·시스템 메시지·도움말·시나리오 설명
  대상: 0.BIN · CS.BIN · LOAD.BIN · HELP.BIN · OPAOPA.BIN · NAMEENT.BIN · BOSS00‥04.BIN (압축 없음, 문자열이 데이터 안에 평문)
  문법(메뉴·메시지 쪽): 글자(0x20↑, 0x18‥0x1D 2바이트) · 03/04 + 1바이트 · **05 = 줄바꿈 1바이트**(대사 스크립트와 다름) · 06‥0A 1바이트
        → 바로 뒤가 00|01|02 인 덩어리만.
  거르기: 가나·한자 2자↑ + 대사 말뭉치(work/extract.json)로 만든 글자 2-그램 점수 > −4.2 (진짜 대사 하위 5% ≈ −4.5).
  ⛔포인터를 못 찾았으므로 넣을 때는 «제자리·원래 바이트 이하»(남는 곳은 00 채움 — 끝 표시와 같음) → «구분» 열에 예산 바이트.
  토큰: \n = 05 · {06}‥{0A} · {03:nn} {04:nn} · {c:XXX}
  python tools/ovl_extract.py → work/text/ovl_001‥.tsv (+ my files/tsv 사본) · work/ovl.json
"""
import collections, glob, json, math, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import tbl

FILES = ['0.BIN', 'CS.BIN', 'LOAD.BIN', 'HELP.BIN', 'OPAOPA.BIN', 'NAMEENT.BIN'] + ['BOSS%02d.BIN' % i for i in range(5)]
TH = -4.2
CHUNK = 29 * 1024


def model():
    occ = json.load(open(os.path.join(ROOT, 'work', 'extract.json'), encoding='utf-8'))
    big, uni, seen = collections.Counter(), collections.Counter(), set()
    for o in occ:
        t = re.sub(r'\{[^}]*\}|\\n', '', o['text'])
        if t in seen:
            continue
        seen.add(t); t = '^' + t + '$'
        for a, b in zip(t, t[1:]):
            big[a + b] += 1; uni[a] += 1
    V = len(uni) + 1

    def score(s):
        t = '^' + s + '$'
        lp = [math.log((big[a + b] + 0.1) / (uni[a] + 0.1 * V)) for a, b in zip(t, t[1:])]
        return sum(lp) / len(lp)
    return score


def runs(b):
    i, n = 0, len(b)
    while i < n:
        j, cs = i, []
        while j < n:
            c = b[j]
            if 0x18 <= c <= 0x1D and j + 1 < n and ((c - 0x17) << 8 | b[j + 1]) <= tbl.LAST:
                cs.append((c - 0x17) << 8 | b[j + 1]); j += 2
            elif c >= 0x20:
                cs.append(c); j += 1
            elif c in (3, 4) and j + 1 < n:
                j += 2
            elif c in (5, 6, 7, 8, 9, 10):
                j += 1
            else:
                break
        if len(cs) >= 2 and j < n and b[j] in (0, 1, 2):
            yield i, j, cs
        i = max(j, i + 1)


def decode(b, i, e):
    out = []
    while i < e:
        c = b[i]
        if 0x18 <= c <= 0x1D:
            v = (c - 0x17) << 8 | b[i + 1]; out.append(tbl.DEC.get(v, '{c:%03X}' % v)); i += 2
        elif c >= 0x20:
            out.append(tbl.DEC.get(c, '{c:%03X}' % c)); i += 1
        elif c in (3, 4):
            out.append('{%02X:%02X}' % (c, b[i + 1])); i += 2
        elif c == 5:
            out.append('\\n'); i += 1
        else:
            out.append('{%02X}' % c); i += 1
    return ''.join(out)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    score = model()
    occ = []
    for f in FILES:
        p = os.path.join(ROOT, 'work', 'disc', f)
        if not os.path.exists(p):
            continue
        b = open(p, 'rb').read()
        for i, e, cs in runs(b):
            s = ''.join(tbl.DEC.get(c, '?') for c in cs)
            real = sum(1 for c in cs if 0x6E <= c <= tbl.LAST and c != 0x2FF)
            if real >= 2 and score(s) > TH:
                occ.append({'file': f, 'start': i, 'end': e, 'term': b[e], 'text': decode(b, i, e), 'n': len(cs)})
    uniq, order = {}, []
    for o in occ:
        if o['text'] not in uniq:
            uniq[o['text']] = []; order.append(o['text'])
        uniq[o['text']].append(o)
    rows = []
    for k, t in enumerate(order, 1):
        os_ = uniq[t]; rid = 'V%05d' % k
        for x in os_:
            x['id'] = rid
        budget = min(x['end'] - x['start'] for x in os_)
        kind = '메뉴:%dB' % budget
        if t.count(' ') >= 8 and len(t.replace(' ', '')) <= 8:
            kind = '번역금지'                                   # 이름 입력판 한자 표(LOAD.BIN) — 자판은 따로
        elif len(t) <= 3:
            kind = '잡음?:%dB' % budget                          # 2~3자 조각(대개 데이터) — 뜻이 안 되면 비워 둘 것
        rows.append('\t'.join([rid, '%s:%X' % (os_[0]['file'], os_[0]['start']), kind, str(len(os_)), t, '']))
    json.dump(occ, open(os.path.join(ROOT, 'work', 'ovl.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    head = 'ID\t위치\t구분\t공유\t원문\t번역\n'
    parts, cur, size = [], [], 0
    for r in rows:
        s = len((r + '\n').encode('utf-8'))
        if cur and size + s > CHUNK:
            parts.append(cur); cur, size = [], 0
        cur.append(r); size += s
    if cur:
        parts.append(cur)
    for out in (os.path.join(ROOT, 'work', 'text'), os.path.join(ROOT, 'my files', 'tsv')):
        os.makedirs(out, exist_ok=True)
        for p in glob.glob(os.path.join(out, 'ovl_*.tsv')):
            os.remove(p)
        for n, p in enumerate(parts, 1):
            open(os.path.join(out, 'ovl_%03d.tsv' % n), 'w', encoding='utf-8', newline='\n').write(head + '\n'.join(p) + '\n')
    per = collections.Counter(o['file'] for o in occ)
    print('출현 %d · 고유 %d · 글자 %d · 파일별 %s' % (len(occ), len(order), sum(uniq[t][0]['n'] for t in order), dict(per)))


if __name__ == '__main__':
    main()
