# -*- coding: utf-8 -*-
r"""대사 추출 — SSS0‥13.ADT 풀린 항목(work/unpack/SSS*.ADT/*.bin)의 스크립트 글.
  1차: tools/vm.py 로 진입점·점프를 따라가며 «명령 01(글 모드) … 00|02» 를 모은다(명령 경계가 정확).
  2차(보충): 따라가기가 못 닿은 구역에서만, 엄격한 글자 검사를 통과한 «01 … 00|02» 를 «검증필요» 로 붙인다.
  글 모드 안: 0x20↑ 글자(0x18‥0x1F 는 2바이트) · 03/04/05 + 1바이트 · 06 줄바꿈 · 01 페이지 · 07‥0A.
  토큰: \n = 06 · {p} = 안쪽 01 · {03:nn} 대기 · {05:nn} 이름 변수 · {04:nn} · {07}‥{0A} · {c:XXX} 표 밖 코드
        끝이 00(출력 후 메시지 닫기)이면 원문 끝에 {00} 을 붙인다(02 는 표시 안 함).
  python tools/extract.py  → work/text/chaosseed.tsv(저장소용, 한 파일) + my files/tsv/chaosseed_NNN.tsv(사용자용, 29KB 단위) + work/extract.json
  번역은 work/text 를 work/ko 로 복사해 «번역» 열을 채운다(tools/kocheck.py 로 검사).
"""
import os, sys, glob, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tbl, vm

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUSPECT = (set(range(0x25, 0x2D)) - {0x29, 0x2A, 0x2B, 0x2C}) | {0x2E, 0x2F} | (set(range(0x54, 0x6E)) - {0x5C, 0x68, 0x69})
CHUNK = 29 * 1024


def body(b, j):
    """j = 01 다음. 반환 (끝 위치(00|02), 글자 코드 목록) 또는 (None, …)"""
    cs = []
    while j < len(b):
        c = b[j]
        if c in (0, 2):
            return j, cs
        if 0x18 <= c <= 0x1F:
            if j + 1 >= len(b):
                return None, cs
            cs.append(((c - 0x18 + 1) << 8) | b[j + 1]); j += 2
        elif c >= 0x20:
            cs.append(c); j += 1
        elif c in (3, 4, 5):
            j += 2
        elif c in (1, 6, 7, 8, 9, 10):
            j += 1
        else:
            return None, cs
    return None, cs


def decode(b, i, end):
    out = []
    while i < end:
        c = b[i]
        if 0x18 <= c <= 0x1F:
            v = ((c - 0x18 + 1) << 8) | b[i + 1]
            out.append(tbl.DEC.get(v, '{c:%03X}' % v)); i += 2
        elif c >= 0x20:
            out.append(tbl.DEC.get(c, '{c:%03X}' % c)); i += 1
        elif c in (3, 4, 5):
            out.append('{%02X:%02X}' % (c, b[i + 1])); i += 2
        elif c == 6:
            out.append('\\n'); i += 1
        elif c == 1:
            out.append('{p}'); i += 1
        else:
            out.append('{%02X}' % c); i += 1
    return ''.join(out)


def strict(cs):
    """보충용 엄격 검사: 4글자↑, 가나·한자 70%↑, 의심 기호 없음"""
    if len(cs) < 4:
        return False
    real = sum(1 for c in cs if 0x6E <= c <= tbl.LAST and c != 0x2FF)
    return real / len(cs) > 0.7 and not any(c in SUSPECT or c > tbl.LAST for c in cs)


def kind(b, i):
    if i >= 2 and b[i - 2] == 0x65:
        return '대사:%02X' % b[i - 1]
    if i >= 2 and b[i - 2] == 0x30:
        return '안내:%02X' % b[i - 1]
    return '글'


def scan(b):
    i = 0
    while True:
        i = b.find(b'\x01', i)
        if i < 0:
            return
        e, cs = body(b, i + 1)
        if e is not None and cs:
            yield i, e, cs
            i = e + 1
        else:
            i += 1


def collect(b):
    """→ [(시작, 끝, 확실?)]"""
    texts, _, _ = vm.walk(b)
    out = [(a, e, True) for a, e in texts]
    cov = set()
    for a, e in texts:
        cov.update(range(a, e + 1))
    for i, e, cs in scan(b):
        if not any(x in cov for x in range(i, e + 1)) and strict(cs):
            out.append((i, e, False))
    return sorted(out)


def main():
    occ = []
    files = sorted(glob.glob(os.path.join(ROOT, 'work', 'unpack', 'SSS*.ADT', '*.bin')),
                   key=lambda p: (int(os.path.basename(os.path.dirname(p))[3:-4]), p))
    for f in files:
        b = open(f, 'rb').read()
        arc = os.path.basename(os.path.dirname(f))[:-4]; item = int(os.path.basename(f)[:-4])
        for a, e, sure in collect(b):
            _, cs = body(b, a + 1)
            txt = decode(b, a + 1, e)
            if not txt.replace('　', '').replace(' ', '').replace('\\n', '').replace('{p}', ''):
                continue                                  # 공백뿐인 글은 번역 대상 아님
            occ.append({'arc': arc, 'item': item, 'start': a, 'end': e, 'term': b[e], 'sure': sure,
                        'kind': kind(b, a) if sure else '검증필요', 'text': txt, 'n': len(cs)})
    uniq = {}; order = []
    for o in occ:
        key = (o['text'], o['term'])
        if key not in uniq:
            uniq[key] = []; order.append(key)
        uniq[key].append(o)
    rows = []
    for k, key in enumerate(order, 1):
        os_ = uniq[key]; o = os_[0]
        rid = 'C%05d' % k
        for x in os_:
            x['id'] = rid
        knd = o['kind'] if any(x['sure'] for x in os_) else '검증필요'
        if all(ord(ch) < 0x80 for ch in o['text'].replace('\\n', '')):
            knd = '영문'
        txt = o['text'] + ('{00}' if o['term'] == 0 else '')
        rows.append('\t'.join([rid, '%s/%03d:%X' % (o['arc'], o['item'], o['start']), knd, str(len(os_)), txt, '']))
    json.dump(occ, open(os.path.join(ROOT, 'work', 'extract.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    head = 'ID\t위치\t구분\t공유\t원문\t번역\n'
    parts = []; cur = []; size = 0
    for r in rows:
        s = len((r + '\n').encode('utf-8'))
        if cur and size + s > CHUNK:
            parts.append(cur); cur = []; size = 0
        cur.append(r); size += s
    if cur:
        if parts and size < CHUNK // 3:
            parts[-1] += cur
        else:
            parts.append(cur)
    # 저장소(work/text)는 한 파일 통째로, 사용자에게 주는 my files/tsv 사본만 29KB 단위로 나눔(사용자 지시 2026-10-01)
    txt = os.path.join(ROOT, 'work', 'text'); os.makedirs(txt, exist_ok=True)
    for p in glob.glob(os.path.join(txt, 'chaosseed_*.tsv')):
        os.remove(p)
    open(os.path.join(txt, 'chaosseed.tsv'), 'w', encoding='utf-8', newline='\n').write(head + '\n'.join(rows) + '\n')
    out = os.path.join(ROOT, 'my files', 'tsv'); os.makedirs(out, exist_ok=True)
    for p in glob.glob(os.path.join(out, 'chaosseed_*.tsv')):
        os.remove(p)
    for n, p in enumerate(parts, 1):
        open(os.path.join(out, 'chaosseed_%03d.tsv' % n), 'w', encoding='utf-8', newline='\n').write(head + '\n'.join(p) + '\n')
    chars = sum(uniq[k][0]['n'] for k in order)
    unsure = sum(1 for key in order if not any(x['sure'] for x in uniq[key]))
    print('출현 %d · 고유 %d(검증필요 %d) · 고유 글자 %d · 파일 %d개' % (len(occ), len(order), unsure, chars, len(parts)))


if __name__ == '__main__':
    main()
