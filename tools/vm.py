# -*- coding: utf-8 -*-
r"""SSS 스크립트 해석기 모델(0.BIN/CS 해석기 0x0604420C, 분기표 0x06044294) — 명령 길이·점프 오프셋.
  비글 모드: 0x20↑ 명령은 표, 0x00‥0x1F 는 제어. 01 = 글 모드 시작 → 글자/제어 … 00|02 에서 끝.
  점프 대상 = 항목 시작 + u16(LE). 점프 들어있는 명령: 63(u16) · 4A‥4D(플래그, u16) · 52(조건식 … FF u16)
  · 42/DE(n, u16×n) · 6A(비트마스크 u16, 켜진 비트마다 u16) · 7A(변수, n, u16×n).
  길이표 = work/oplen.txt(정적 분석) + 아래 규칙. 그래도 모르는 명령은 «뒤가 이어지는 길이» 탐색(log 로 보고).
"""
import struct, ast, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T70 = [0, 0, 0, 0, 0, 2, 2, 2, 1, 2, 0, 2, 1, 1, 2, 0, 4]   # 0x06094734 (형식 0‥16) — 명령 70·8B
T71 = [1, 3, 2, 3, 2, 1]                                     # 0x06094778 (형식 0‥5) — 명령 71
ESUB = [2, 3, 3, 3, 0, 3, 6, 6, 6, 6, 5, 5, 5, 8, 8, 8]                    # E8‥EA 하위 명령 0x06046C74
L = {}
for line in open(os.path.join(ROOT, 'work', 'oplen.txt')):
    k, a, r = line.split(' ', 2); r = ast.literal_eval(r.strip()); k = int(k, 16)
    if k < 0x20 or len(r) != 1:
        continue
    x = r[0]
    if x.startswith("('rts'"):
        L[k] = 1 + int(x.split(',')[1].strip(' )'))
    elif x.lstrip('-').isdigit():
        L[k] = 1 + int(x)
for k in (0x42, 0xDE, 0x52, 0x7B, 0x7D, 0xF2, 0x6A, 0x70, 0x8B, 0xE8, 0xE9, 0xEA, 0xD0, 0x63, 0x4A, 0x4B, 0x4C, 0x4D):
    L.pop(k, None)
UNK = {0x71, 0xA2, 0xD9, 0x7A, 0x69}   # 전부 아래 규칙으로 처리
for k in UNK:
    L.pop(k, None)


def u16(b, p):
    return struct.unpack_from('<H', b, p)[0]


def text_end(b, j):
    """j = 01 다음. 00|02 위치 반환(그 바이트 포함 안 함)"""
    while j < len(b):
        c = b[j]
        if c in (0, 2):
            return j
        j += 2 if (0x18 <= c <= 0x1F or c in (3, 4, 5)) else 1
    return None


def step(b, p):
    """명령 하나: (다음 위치 or None(흐름 끝), [점프 오프셋 위치들], 글(시작,끝) or None). 모르면 예외"""
    op = b[p]
    if op == 1:
        e = text_end(b, p + 1)
        if e is None:
            raise ValueError('text')
        return e + 1, [], (p, e)
    if op in (0, 2, 6, 7, 8, 9, 10):
        return p + 1, [], None
    if op in (3, 4, 5) or 0x18 <= op <= 0x1F:
        return p + 2, [], None
    if op < 0x20 or op == 0xFF:
        raise ValueError('ctl %02X' % op)
    if op in (0x42, 0xDE):
        n = b[p + 1]
        return p + 2 + 2 * n, [p + 2 + 2 * k for k in range(n)], None
    if op == 0x63:
        return None, [p + 1], None
    if op in (0x4A, 0x4B, 0x4C, 0x4D):
        return p + 4, [p + 2], None
    if op == 0x52:
        q = p + 1
        while b[q] not in (0xFE, 0xFF):
            q += 2 if (b[q] & 0xF0) in (0x00, 0x10) else 3
        if b[q] == 0xFF:
            return q + 3, [q + 1], None
        return q + 2, [], None
    if op in (0x7B, 0x7D):
        q = b.index(b'\xff', p + 1)
        return q + 1, [], None
    if op == 0xF2:
        return p + (2 if b[p + 1] == 0xFF else 3), [], None
    if op == 0x6A:
        m = u16(b, p + 1); q = p + 3; js = []
        for k in range(16):
            if m >> k & 1:
                js.append(q); q += 2
        return q, js, None
    if op in (0x70, 0x8B):
        t = b[p + 1]
        if t >= len(T70):
            raise ValueError('t70')
        return p + 5 + T70[t], [], None
    if op == 0x7A:                              # 변수, n, u16×n 점프표(0x060458BA)
        n = b[p + 2]
        return p + 3 + 2 * n, [p + 3 + 2 * k for k in range(n)], None
    if op == 0x69:
        return p + 1, [], None
    if op == 0xD9:                              # 예: d9 01 01 | aa 46
        return p + 3, [], None
    if op == 0xA2:                              # 예: a2 00 | 5c 69 | 53 3c
        return p + 2, [], None
    if op in (0x9D, 0x9E):                      # R8 을 0x06048920 에 넘김: 머리 5 + 모드(0:4, 1:3)
        return p + 6 + {0: 4, 1: 3}.get(b[p + 2], 0), [], None
    if op == 0xFC:                              # R8 += 5 후 1바이트 (0x06046F2C)
        return p + 7, [], None
    if op == 0xAA:
        return p + 2, [], None
    if op == 0xBA:                              # 형식 + 2바이트 + T70[형식] (0x060465A8)
        t = b[p + 1]
        if t >= len(T70):
            raise ValueError('t70')
        return p + 4 + T70[t], [], None
    if op == 0x71:
        t = b[p + 1]
        if t >= len(T71):
            raise ValueError('t71')
        return p + (3 if t == 0 else 4) + T71[t], [], None
    if op in (0xE8, 0xE9, 0xEA):
        q = p + {0xE8: 2, 0xE9: 2, 0xEA: 1}[op] + 2     # E8: +1 · E9: 물체 1 · EA: 없음 → dx dy → 하위 명령
        s = b[q]
        if s >= len(ESUB):
            raise ValueError('esub')
        return q + 1 + ESUB[s], [], None
    if op == 0xD0:
        f = b[p + 1]
        return p + 7 + (7 if f & 0x10 else 0) + (7 if f & 0x20 else 0), [], None
    if op in L:
        return p + L[op], [], None
    raise KeyError(op)


def probe(b, p, depth=24):
    """p 에서 몇 명령이 오류 없이 이어지나"""
    n = 0
    try:
        while n < depth and p is not None and p < len(b):
            p, _, _ = step(b, p); n += 1
    except (KeyError, ValueError, IndexError):
        return n
    return depth


def entries(b):
    offs = struct.unpack_from('<8H', b, 0); es = []
    for o in offs:
        j = o
        while j < len(b) and b[j] != 0xFF:
            es.append((j + 1, u16(b, j + 1))); j += 3
    return es


def walk(b, log=None):
    """모든 진입점·점프를 따라 도달 가능한 명령을 훑는다 → (글 목록, 점프 오프셋 위치들, 막힌 곳)"""
    seen = set(); texts = []; jumps = set(); stops = []
    work = [t for _, t in entries(b)]
    while work:
        p = work.pop()
        while p is not None and 0 <= p < len(b) and p not in seen:
            seen.add(p)
            try:
                nxt, js, tx = step(b, p)
            except KeyError as e:
                op = b[p]; best = None
                for ln in range(1, 13):
                    if probe(b, p + ln) >= 24:
                        best = ln; break
                if best is None:
                    stops.append((p, 'unk %02X' % op)); break
                if log is not None:
                    log.append((op, best))
                nxt, js, tx = p + best, [], None
            except (ValueError, IndexError) as e:
                stops.append((p, str(e))); break
            for j in js:
                jumps.add(j); work.append(u16(b, j))
            if tx:
                texts.append(tx)
            p = nxt
    return texts, jumps, stops
