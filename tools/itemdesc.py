# -*- coding: utf-8 -*-
r"""아이템 설명 표 (0.BIN 0x72BE6‥0x749F0, 2026-10-02 실기 «미번역» 대응) — 데이터로 형식 확정(참조 1,079개 정렬 검산)
  구조: u16 BE 오프셋 256개(표 시작 기준, 0x200 = 빈 항목) + 항목들. 항목 = 토큰 … FF(끝).
    · 글자: 1바이트 0x20‥0xFE / 2바이트 0x18‥0x1D + lo
    · 01 = 줄바꿈
    · 짧은 참조 02‥16 dd      : (op+1)바이트(3‥23)를 «op 위치 − dd» 에서
    · 먼 참조   17 XY dd      : (X+4)바이트(4‥19)를 «op 위치 − (Y<<8 | dd)» 에서(≤ 0xFFF)
    (저장 바이트열 기준 — 원본 구간 안의 참조도 다시 풀린다(재귀). 원본·끝은 토큰 경계)
  항목 첫 줄 = 아이템 이름 읽기(히라가나).
  python tools/itemdesc.py   → work/text/itemdesc.tsv (ID I000‥I255 · 원문)
  build(raws) → 표 바이트(같은 항목 오프셋 공유 · 탐욕 LZ: 먼 참조/짧은 참조 중 바이트 절약 큰 것)
"""
import os, re, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import tbl

START, END = 0x72BE6, 0x749F0
N = 256


def tok_len(c):
    if c == 0x17:
        return 3
    if 0x18 <= c <= 0x1D or 2 <= c <= 0x16:
        return 2
    return 1


def ref(b, p):
    """p 의 참조 → (원본 위치, 길이) 또는 None"""
    c = b[p]
    if 2 <= c <= 0x16:
        return p - b[p + 1], c + 1
    if c == 0x17:
        return p - (((b[p + 1] & 15) << 8) | b[p + 2]), (b[p + 1] >> 4) + 4
    return None


def expand(b, a, n, depth=0):
    out, i = bytearray(), a
    while i < a + n:
        r = ref(b, i)
        if r:
            if depth > 16:
                raise ValueError('참조 깊이')
            out += expand(b, r[0], r[1], depth + 1)
        else:
            out += b[i:i + tok_len(b[i])]
        i += tok_len(b[i])
    return bytes(out)


def entry(b, a):
    out, i = bytearray(), a
    while b[i] != 0xFF:
        r = ref(b, i)
        out += expand(b, r[0], r[1]) if r else b[i:i + tok_len(b[i])]
        i += tok_len(b[i])
    return bytes(out)


def decode(b):
    offs = [struct.unpack_from('>H', b, START + 2 * k)[0] for k in range(N)]
    return offs, [entry(b, START + o) for o in offs]


def to_text(raw):
    out, i = [], 0
    while i < len(raw):
        c = raw[i]
        if 0x18 <= c <= 0x1D:
            v = (c - 0x17) << 8 | raw[i + 1]; out.append(tbl.DEC.get(v, '{c:%03X}' % v)); i += 2
        elif c == 1:
            out.append('\\n'); i += 1
        elif c >= 0x20:
            out.append(tbl.DEC.get(c, '{c:%03X}' % c)); i += 1
        else:
            out.append('{%02X}' % c); i += 1
    return ''.join(out)


def build(raws):
    """raws: 256개(01 줄바꿈, FF 없음, 글자만) → 표 바이트"""
    base = 2 * N
    body = bytearray(); offs = []; seen = {}
    starts = []                                                  # body 안 토큰 시작 위치(참조 원본 후보)
    for raw in raws:
        if raw in seen:
            offs.append(seen[raw]); continue
        offs.append(base + len(body)); seen[raw] = base + len(body)
        toks, i = [], 0
        while i < len(raw):
            w = 2 if 0x18 <= raw[i] <= 0x1D else 1
            toks.append(raw[i:i + w]); i += w
        # 지금까지의 body 를 «풀린 바이트열» 로 보고 같은 글을 찾는다: 원본 후보 = 토큰 시작이면서 거기서 n바이트가 토큰 경계로 끝나는 곳
        j = 0
        while j < len(toks):
            here = len(body)
            best = None                                          # (절약, 길이 토큰수, op 바이트들)
            want = b''
            for L in range(1, min(23, len(toks) - j) + 1):
                want = b''.join(toks[j:j + L])
                if len(want) > 23:
                    break
                if len(want) < 3:
                    continue
                for s in reversed(starts):
                    d = here - s
                    if d > 0xFFF:
                        break
                    if lit_at(body, s, len(want)) == want:
                        n = len(want)
                        if d <= 255 and 3 <= n <= 23:
                            cand = (n - 2, L, bytes([n - 1, d]))
                        elif 4 <= n <= 19:
                            cand = (n - 3, L, bytes([0x17, ((n - 4) << 4) | (d >> 8), d & 0xFF]))
                        else:
                            continue
                        if best is None or cand[0] > best[0]:
                            best = cand
                        break
            if best and best[0] > 0:
                starts.append(len(body)); body += best[2]; j += best[1]
            else:
                starts.append(len(body)); body += toks[j]; j += 1
        body.append(0xFF)
    return b''.join(struct.pack('>H', o) for o in offs) + bytes(body)


def lit_at(body, s, n):
    """body[s:] 가 «글자 토큰만» 으로 n 바이트 이어지면 그 바이트, 아니면 None(참조·줄끝을 원본으로 안 씀 — 단순·안전)"""
    out, i = bytearray(), s
    while len(out) < n and i < len(body):
        c = body[i]
        if c == 0xFF or 2 <= c <= 0x17:
            return None
        w = 2 if 0x18 <= c <= 0x1D else 1
        out += body[i:i + w]; i += w
    return bytes(out) if len(out) == n else None


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    b = open(os.path.join(ROOT, 'work', 'disc', '0.BIN'), 'rb').read()
    offs, res = decode(b)
    t = build(res)
    bb = bytearray(b); bb[START:START + len(t)] = t
    _, res2 = decode(bytes(bb))
    print('항목 %d · 원본 표 끝 %X · 재부호화 %d B (칸 %d B) · 풀기 일치 %s' % (len(res), END, len(t), END - START, res2 == res))
    rows = ['ID\t구분\t원문\t번역']
    for k, r in enumerate(res):
        rows.append('I%03d\t설명\t%s\t' % (k, to_text(r)))
    open(os.path.join(ROOT, 'work', 'text', 'itemdesc.tsv'), 'w', encoding='utf-8', newline='\n').write('\n'.join(rows) + '\n')


if __name__ == '__main__':
    main()


def load_ko():
    p = os.path.join(ROOT, 'work', 'ko', 'itemdesc.tsv')
    tr = {}
    for l in open(p, encoding='utf-8').read().split('\n')[1:]:
        if '\t' in l:
            k, t = l.split('\t', 1)
            if t.strip():
                tr[k] = t
    return tr


def apply(exe, tr, cmap, encode, width=12):
    """exe(bytearray, 0.BIN) 의 설명 표를 번역(tr 'I###')으로 다시 짠다 — 원문 줄 수 이하·한 줄 폭 ≤ width 검사"""
    _, orig = decode(bytes(exe))
    raws, errs = [], []
    for k in range(N):
        t = tr.get('I%03d' % k)
        if not t:
            raws.append(orig[k]); continue
        lines = t.split(chr(92) + 'n')
        olines = to_text(orig[k]).split(chr(92) + 'n')
        for ln in lines:
            w = len(re.sub(r'\{[^}]*\}', '', ln))
            if w > width:
                errs.append('I%03d 폭 %d > %d: %s' % (k, w, width, ln))
        if len(lines) > max(len(olines), 1):
            errs.append('I%03d 줄 %d > 원문 %d' % (k, len(lines), len(olines)))
        raws.append(encode(t, cmap, nl=1))
    if errs:
        raise SystemExit('⛔아이템 설명\n' + '\n'.join(errs))
    t = build(raws)
    if len(t) > END - START:
        raise SystemExit('⛔아이템 설명 표 %d B > 칸 %d B' % (len(t), END - START))
    exe[START:END] = t + bytes(END - START - len(t))
    _, chk = decode(bytes(exe))
    assert chk == raws, '아이템 설명 재부호화 검산 실패'
    return len(t)
