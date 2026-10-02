# -*- coding: utf-8 -*-
r"""오버레이 «0D xx yy»(yy 바이트 건너뛰기) 착지점 검사 (2026-10-02 실기 «강화 누르자 크래시»)
  추출된 오버레이 문자열 안의 0D 명령마다 착지점(명령 뒤 + yy)을 구해, 원본과 새 파일의 착지점 뒤 바이트가 같은지 본다.
  다르면 VM 이 글자·공백 바이트를 명령으로 실행한다(창 크기 0 → 줄 칠하기 루프 폭주 → 코드 덮어쓰기).
  python tools/skipcheck.py [새 파일 폴더(기본 work/new)]
"""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARG1 = {0x03, 0x04, 0x17}
ARG2 = {0x07, 0x0D, 0x10}
ARG3 = {0x11, 0x12}


def walk(b, s, e):
    """[s,e) 를 토큰으로 → (위치, 명령) 목록"""
    out = []; i = s
    while i < e:
        c = b[i]
        if 0x18 <= c <= 0x1F:
            i += 2; continue
        if c >= 0x20:
            i += 1; continue
        n = 1 + (1 if c in ARG1 else 2 if c in ARG2 else 3 if c in ARG3 else 0)
        out.append((i, c, b[i + 1:i + n]))
        i += n
    return out


def check(newdir):
    occ = json.load(open(os.path.join(ROOT, 'work', 'ovl.json'), encoding='utf-8'))
    occ += json.load(open(os.path.join(ROOT, 'work', 'ovl2.json'), encoding='utf-8'))
    bad = []; n = 0
    cache = {}
    for o in occ:
        f = o['file']
        if f not in cache:
            p = os.path.join(newdir, f)
            cache[f] = (open(os.path.join(ROOT, 'work', 'disc', f), 'rb').read(), open(p, 'rb').read() if os.path.exists(p) else None)
        A, B = cache[f]
        if B is None:
            continue
        for pos, c, arg in walk(A, o['start'], o['end']):
            if c != 0x0D:
                continue
            n += 1
            tgt = pos + 3 + arg[1]
            if A[tgt:tgt + 6] != B[tgt:tgt + 6] or A[pos:pos + 3] != B[pos:pos + 3]:
                bad.append((o['id'], f, hex(pos), hex(tgt), A[pos:pos + 3].hex(), B[pos:pos + 3].hex(), A[tgt:tgt + 6].hex(), B[tgt:tgt + 6].hex()))
    return n, bad


def fix(bins, occ, orig):
    """빌더용: bins[f](새 바이트, bytearray) 안의 0D 건너뛰기 거리를 새 배치에 맞게 다시 쓴다.
       원본·새 문자열의 제어 명령 순서를 짝지어 «원본 위치 → 새 위치» 표를 만들고(명령 시작·끝·문자열 시작·끝),
       0D 착지점을 그 표로 옮긴다. 못 옮기면 SystemExit."""
    errs = []; nfix = 0
    for f in sorted({o['file'] for o in occ}):
        if f not in bins:
            continue
        A, B = orig[f], bins[f]
        ents = sorted((o for o in occ if o['file'] == f), key=lambda o: o['start'])
        pmap = {}
        for o in ents:
            ca, cb = walk(A, o['start'], o['end']), walk(B, o['start'], o['end'])
            pmap[o['start']] = o['start']; pmap[o['end']] = o['end']
            if [(c, len(a)) for _, c, a in ca] != [(c, len(a)) for _, c, a in cb]:
                if any(c == 0x0D for _, c, _ in ca):
                    errs.append('%s %s:%X 제어 명령 순서가 원본과 다름(0D 포함)' % (o['id'], f, o['start']))
                continue
            for (pa, c, a), (pb, _, _) in zip(ca, cb):
                pmap[pa] = pb; pmap[pa + 1 + len(a)] = pb + 1 + len(a)
        for o in ents:
            for pa, c, a in walk(A, o['start'], o['end']):
                if c != 0x0D:
                    continue
                if pa not in pmap:
                    continue                                    # 위 오류에 이미 들어감
                tgt = pa + 3 + a[1]
                if tgt not in pmap and not any(e['start'] < tgt < e['end'] for e in ents):
                    pmap[tgt] = tgt                             # 문자열 밖(그대로인 바이트) — 위치 그대로
                if tgt not in pmap:
                    errs.append('%s %s:%X 0D 착지점 %X 를 새 배치에서 못 찾음' % (o['id'], f, pa, tgt)); continue
                pb = pmap[pa]; nt = pmap[tgt] - (pb + 3)
                if not 0 <= nt <= 0xFF:
                    errs.append('%s %s:%X 0D 새 거리 %d 범위 밖' % (o['id'], f, pa, nt)); continue
                assert B[pb] == 0x0D, (o['id'], hex(pb))
                if B[pb + 2] != nt:
                    B[pb + 2] = nt; nfix += 1
    if errs:
        raise SystemExit('⛔0D 건너뛰기 착지점\n' + '\n'.join(errs))
    return nfix


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    n, bad = check(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'work', 'new'))
    print('0D 명령 %d개 · 착지점 어긋남 %d' % (n, len(bad)))
    for x in bad:
        print('  ', *x)
