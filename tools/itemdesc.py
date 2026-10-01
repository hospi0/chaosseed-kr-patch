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


def run(b, a, limit=None, depth=0):
    """저장 바이트열 b 의 a 부터 풀기. 저장 쪽은 토큰 단위(글자 1·2바이트 / 참조 02‥16·17), 참조는 «풀린 바이트» 기준 길이로 복사
       (2바이트 글자가 복사 경계에 걸칠 수 있다 — 풀린 바이트열에서 이어 붙으면 맞는다). limit 없으면 FF 까지."""
    if depth > 24:
        raise ValueError('참조 깊이')
    out, i = bytearray(), a
    while limit is None or len(out) < limit:
        c = b[i]
        if limit is None and c == 0xFF:
            break
        r = ref(b, i)
        out += run(b, r[0], r[1], depth + 1) if r else b[i:i + tok_len(c)]
        i += tok_len(c)
    return bytes(out[:limit]) if limit is not None else bytes(out)


def lead_pending(out):
    i = 0
    while i < len(out):
        if 0x18 <= out[i] <= 0x1D:
            if i + 1 >= len(out):
                return True
            i += 2
        else:
            i += 1
    return False


def expand(b, a, n, depth=0):
    return run(b, a, n, depth)


def entry(b, a):
    return run(b, a)


# 같은 형식의 표 — (시작, 끝, ID 머리, 한 줄 폭, 번역 파일). 선수 설명 표는 26개 뒤 오프셋이 FFFF(없음)·마지막 항목은 00 으로 끝남
END_U = 0x700B1        # 강화 설명 표 데이터 끝(뒤 = 강화 이름 오프셋 표)
TABLES = [(0x72BE6, 0x749F0, 'I', 12, 'itemdesc.tsv'), (0x77B6C, 0x782C8, 'M', 18, 'mondesc.tsv'),
          (0x6FD50, END_U, 'U', 24, 'upgdesc.tsv')]   # U = 강화 항목 설명(192칸)


def decode(b, start=START):
    n = struct.unpack_from('>H', b, start)[0] // 2                # 첫 오프셋 = 항목 수 × 2(표 바로 뒤가 첫 항목)
    offs = [struct.unpack_from('>H', b, start + 2 * k)[0] for k in range(n)]
    res = []
    for o in offs:
        if o == 0xFFFF:
            res.append(None); continue
        raw = entry_upto0(b, start + o) if start != START else entry(b, start + o)
        res.append(raw)
    return offs, res


def entry_upto0(b, a):
    """FF 또는 00 에서 끝(선수 설명 표 마지막 항목은 00)"""
    out, i = bytearray(), a
    while b[i] not in (0xFF, 0x00):
        c = b[i]; r = ref(b, i)
        out += run(b, r[0], r[1]) if r else b[i:i + tok_len(c)]
        i += tok_len(c)
    return bytes(out)


def to_text(raw):
    out, i = [], 0
    while i < len(raw):
        c = raw[i]
        if 0x18 <= c <= 0x1D:
            if i + 1 >= len(raw):
                out.append("{%02X}" % c); i += 1; continue
            v = (c - 0x17) << 8 | raw[i + 1]; out.append(tbl.DEC.get(v, "{c:%03X}" % v)); i += 2
        elif c == 1:
            out.append('\\n'); i += 1
        elif c >= 0x20:
            out.append(tbl.DEC.get(c, '{c:%03X}' % c)); i += 1
        else:
            out.append('{%02X}' % c); i += 1
    return ''.join(out)


def build(raws):
    """raws: 256개(01 줄바꿈, FF 없음, 글자만) → 표 바이트"""
    base = 2 * len(raws)
    body = bytearray(); offs = []; seen = {}
    starts = []                                                  # body 안 토큰 시작 위치(참조 원본 후보)
    for raw in raws:
        if raw is None:
            offs.append(0xFFFF); continue
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
    """원문 TSV(work/text/itemdesc.tsv · mondesc.tsv) + 원문 그대로 재부호화 검산"""
    sys.stdout.reconfigure(encoding='utf-8')
    b = open(os.path.join(ROOT, 'work', 'disc', '0.BIN'), 'rb').read()
    for start, end, pre, width, fn in TABLES:
        offs, res = decode(b, start)
        t = build(res)
        bb = bytearray(b); bb[start:start + len(t)] = t
        _, res2 = decode(bytes(bb), start)
        print('%s 항목 %d · 재부호화 %d B (칸 %d B) · 풀기 일치 %s' % (pre, sum(r is not None for r in res), len(t), end - start, res2 == res))
        rows = ['ID\t구분\t원문\t번역']
        for k, r in enumerate(res):
            if r is not None:
                rows.append('%s%03d\t설명\t%s\t' % (pre, k, to_text(r)))
        open(os.path.join(ROOT, 'work', 'text', fn), 'w', encoding='utf-8', newline='\n').write('\n'.join(rows) + '\n')


if __name__ == '__main__':
    main()


def load_ko():
    tr = {}
    for *_, fn in TABLES:
        p = os.path.join(ROOT, 'work', 'ko', fn)
        if not os.path.exists(p):
            continue
        for l in open(p, encoding='utf-8').read().split('\n')[1:]:
            if '\t' in l:
                k, t = l.split('\t', 1)
                if t.strip():
                    tr[k] = t
    return tr


def apply(exe, tr, cmap, encode):
    """exe(bytearray, 0.BIN) 의 설명 표들을 번역(tr 'I###'·'M###')으로 다시 짠다 — 원문 줄 수 이하·한 줄 폭 검사"""
    sizes = []
    for start, end, pre, width, _ in TABLES:
        _, orig = decode(bytes(exe), start)
        raws, errs = [], []
        for k in range(len(orig)):
            if orig[k] is None:
                raws.append(None); continue
            t = tr.get('%s%03d' % (pre, k))
            if not t:
                raws.append(orig[k]); continue
            lines = t.split(chr(92) + 'n')
            olines = to_text(orig[k]).split(chr(92) + 'n')
            for ln in lines:
                w = len(re.sub(r'\{[^}]*\}', '', ln))
                if w > width:
                    errs.append('%s%03d 폭 %d > %d: %s' % (pre, k, w, width, ln))
            if len(lines) > max(len(olines), 1):
                errs.append('%s%03d 줄 %d > 원문 %d' % (pre, k, len(lines), len(olines)))
            raws.append(encode(t, cmap, nl=1))
        if errs:
            raise SystemExit('⛔설명 표 %s\n' % pre + '\n'.join(errs))
        t = build(raws)
        if len(t) > end - start:
            raise SystemExit('⛔설명 표 %s %d B > 칸 %d B' % (pre, len(t), end - start))
        exe[start:end] = t + bytes(end - start - len(t))
        _, chk = decode(bytes(exe), start)
        assert chk == raws, '설명 표 %s 재부호화 검산 실패' % pre
        sizes.append((pre, len(t), end - start))
    return sizes
