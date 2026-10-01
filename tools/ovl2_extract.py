# -*- coding: utf-8 -*-
r"""오버레이 문자열 보충 추출 (2026-10-02, 실기 «미번역» 화면 대응) → work/text/ovl2.tsv · work/ovl2.json (ID W…)
  ovl_extract.py 가 놓친 것:
    ① 점수 필터(2-그램)에 떨어진 이름·설명(아이템·무기·선수·적 이름, 杞人之憂·封印の門, 시나리오 설명 등)
    ② 메뉴 문자열 안의 제어 바이트 0B‥17(07·0D·0E·0F·10·11·13·15 …) — 05 말고는 몰라서 덩어리째 버렸음.
       ★0D·10 은 뒤 «2바이트» 인자(10 xx yy = 글 위치 — 「10 11 13 はい」), 나머지는 1바이트
       → 토큰 {0D:xx:yy} {10:xx:yy} {0B}‥{17} 로 보존(인자를 1바이트로 보면 yy 가 글자로 읽혀 번역에 먹힌다).
  방식: 후보는 넉넉히(가나·한자 2자 이상 이어진 덩어리, 0xFF(ゾ)·모르는 코드 없음) — ★잡음은 «번역을 비워» 두면 안 건드린다
        (번역은 사람이 줄마다 보고 채움). 제외: 기존 V 문자열(work/ovl.json)과 겹침 · 이름판 행(nameent) · 이름판 문구
        · 0.BIN 아이템 설명 표(따로 — tools/itemdesc.py).
  넣기는 V 와 같은 «제자리·원래 바이트 이하»(insert.py).
  python tools/ovl2_extract.py
"""
import collections, json, os, re, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import tbl, ovl_extract as ox, nameent

FILES = ox.FILES
ARG1 = (3, 4, 0x17)                         # 17 xx = 글 색으로 보임(17 04 綜生産量)
ARG2 = (0x07, 0x0D, 0x10, 0x11)   # 10 xx yy = 글 위치 · 11 xx yy = 숫자 표시 · 07 xx yy = 링크·값 · 0D xx yy
KJ = re.compile(r'[぀-ヿ一-鿿]')
# 글 구역(기존 V 문자열이 몰린 곳 + 실기에서 확인한 표) — 이 밖은 그림·코드라 안 본다
REGIONS = {'0.BIN': [(0x749F0, 0x752B0), (0x775D0, 0x77F40)],
           'CS.BIN': [(0x7B000, 0x7FB00)],
           'LOAD.BIN': [(0xEB00, 0xF100), (0x10500, 0x12B00)],
           'HELP.BIN': [(0x12E00, 0x19900)],
           'NAMEENT.BIN': [(0x2B9F, 0x2EE0)]}
SKIP = {'0.BIN': [(0x72BE6, 0x749F0)],                      # 아이템 설명 표(u16 BE 오프셋 256 + 앞 글 재사용 코드)
        'LOAD.BIN': [(0x10DF0, 0x10E7F), (0x10FF0, 0x11074), (0xEB00, 0xF100)],   # …· 탁점 변환 가나 표 · 잡음                   # 이름판 탭·버튼·제목(nameent.patch_load 가 씀)
        'NAMEENT.BIN': [(0x2AC8, 0x2B0D)]}


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
            elif c in ARG1 and j + 1 < n:
                j += 2
            elif c in ARG2 and j + 2 < n:
                j += 3
            elif 5 <= c <= 0x17:
                j += 1
            else:
                break
        if cs and j < n and b[j] in (0, 1, 2):
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
        elif c in ARG1:
            out.append('{%02X:%02X}' % (c, b[i + 1])); i += 2
        elif c in ARG2:
            out.append('{%02X:%02X:%02X}' % (c, b[i + 1], b[i + 2])); i += 3
        elif c == 5:
            out.append('\\n'); i += 1
        else:
            out.append('{%02X}' % c); i += 1
    return ''.join(out)


def candidate(t):
    if 'ゾ' in t or '{c:' in t:
        return False
    body = re.sub(r'\{[^}]*\}|\\n', ' ', t)
    longest = max((len(m) for m in re.findall(r'[぀-ヿ一-鿿゛゜ー]+', body)), default=0)
    return longest >= 2 or bool(re.fullmatch(r'\s*[一-鿿]\s*', body))


def nameent_rows(L):
    ptr = lambda o: struct.unpack_from('>I', L, o)[0] - nameent.LOAD_BASE
    tabs = ((0xFB94, 5), (0xFBA8, 5), (0xFBBC, 5), (0xFBD0, nameent.KANJI_ROWS))
    return [(ptr(base + 4 * i), nameent.row_end(L, ptr(base + 4 * i))) for base, n in tabs for i in range(n)]


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    old = json.load(open(os.path.join(ROOT, 'work', 'ovl.json'), encoding='utf-8'))
    occ = []
    for f in FILES:
        p = os.path.join(ROOT, 'work', 'disc', f)
        if not os.path.exists(p):
            continue
        b = open(p, 'rb').read()
        ex = [(o['start'], o['end']) for o in old if o['file'] == f] + SKIP.get(f, [])
        if f == 'LOAD.BIN':
            ex += nameent_rows(b)
        for i, e, cs in runs(b):
            if not any(a <= i < z for a, z in REGIONS.get(f, [])) or any(a < e and i < z for a, z in ex):
                continue
            t = decode(b, i, e)
            if candidate(t):
                occ.append({'file': f, 'start': i, 'end': e, 'term': b[e], 'text': t, 'n': len(cs)})
    uniq, order = {}, []
    for o in occ:
        if o['text'] not in uniq:
            uniq[o['text']] = []; order.append(o['text'])
        uniq[o['text']].append(o)
    rows = []
    for k, t in enumerate(order, 1):
        os_ = uniq[t]; rid = 'W%05d' % k
        for x in os_:
            x['id'] = rid
        budget = min(x['end'] - x['start'] for x in os_)
        rows.append('\t'.join([rid, '%s:%X' % (os_[0]['file'], os_[0]['start']), '메뉴:%dB' % budget, str(len(os_)), t, '']))
    json.dump(occ, open(os.path.join(ROOT, 'work', 'ovl2.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    head = 'ID\t위치\t구분\t공유\t원문\t번역\n'
    open(os.path.join(ROOT, 'work', 'text', 'ovl2.tsv'), 'w', encoding='utf-8', newline='\n').write(head + '\n'.join(rows) + '\n')
    per = collections.Counter(o['file'] for o in occ)
    print('출현 %d · 고유 %d · 파일별 %s' % (len(occ), len(order), dict(per)))


if __name__ == '__main__':
    main()
