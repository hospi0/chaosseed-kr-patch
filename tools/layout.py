# -*- coding: utf-8 -*-
r"""제어 명령 «절대 위치 고정» 채움 (2026-10-02 실기 «강화 누르자 크래시»)
  0D(조건부 건너뛰기)가 든 메뉴 문자열은 항목·명령 위치가 원본과 같아야 한다 — 남는 자리를 끝·첫 줄에 몰면
  건너뛰기 착지점이 어긋나 VM 이 글자 바이트를 명령으로 실행 → 창 크기 0 → 줄 칠하기 루프 폭주 → 코드 덮어쓰기(크래시).
  방법: 원본·새 바이트의 제어 명령을 순서대로 짝지어, 각 명령 앞 글 조각을 원래 길이로 채운다.
        채움 = 그 줄 머리 색 명령 {04:cc} 되풀이(2바이트, 효과 없음) + 홀수 1바이트만 공백 — 색 명령이 없으면 공백.
  exact(new, A, s, e) → room 길이 bytes, 못 맞추면 (None, 사유)
"""
from skipcheck import walk


def upgrade(b, k, up, elig=None, base=0):
    """b(인코딩된 바이트) 안 1바이트 글자를 «같은 글자의 2바이트 사본 칸»(up: 1바이트 코드 → 2바이트)으로 끝에서부터 k개 바꿈
       — 화면은 그대로, 길이만 +1씩(★공백 채움은 칸을 먹어 줄이 길어진다 → 창 밖 베이지 띠·뒤 줄이 덮어씀, 실기 2026-10-02).
       elig = 바꿔도 되는 «절대 위치» 집합(번역문 글자에서 나온 바이트 — {c:} 원래 바이트·명령 인자 제외), base = b[0] 의 절대 위치.
       → (새 바이트, 못 채운 수)"""
    if not up or k <= 0:
        return b, k
    pos = [j for j, c in enumerate(b) if c in up and (elig is None or base + j in elig)]
    if elig is None:                                             # elig 가 없으면 명령 문법으로 글자 바이트만 추림
        from skipcheck import ARG1, ARG2, ARG3
        ok = set(); i = 0
        while i < len(b):
            c = b[i]
            if 0x18 <= c <= 0x1F:
                i += 2; continue
            if c >= 0x20:
                ok.add(i); i += 1; continue
            i += 1 + (1 if c in ARG1 else 2 if c in ARG2 else 3 if c in ARG3 else 0)
        pos = [j for j in pos if j in ok]
    pick = set(pos[::-1][:k])
    out = bytearray()
    for j, c in enumerate(b):
        out += up[c] if j in pick else bytes([c])
    return bytes(out), k - len(pick)


def exact(new, A, s, e, up=None, elig=None):
    room = e - s
    ca = walk(A, s, e)
    cb = walk(new, 0, len(new))
    if [(c, len(a)) for _, c, a in ca] != [(c, len(a)) for _, c, a in cb]:
        return None, '제어 명령 순서가 원본과 다름'
    out = bytearray(); prev_b = 0; color = None
    for (pa, c, a), (pb, _, _) in zip(ca, cb):
        seg = new[prev_b:pb]
        k = (pa - s) - len(out) - len(seg)
        if k < 0:
            return None, '명령 %02X 앞 글이 원본보다 %d바이트 김' % (c, -k)
        seg, k = upgrade(seg, k, up, elig, prev_b)               # 먼저 2바이트 사본 칸으로(보이는 변화 없음)
        out += seg
        out += fill(k, color)
        out += new[pb:pb + 1 + len(a)]
        if c == 0x04:
            color = bytes([0x04]) + bytes(a)
        elif c in (0x05, 0x06, 0x01, 0x02):
            color = None                                         # 줄이 바뀌면 그 줄 머리 색을 다시 본다
        prev_b = pb + 1 + len(a)
    seg = new[prev_b:]
    k = room - len(out) - len(seg)
    if k < 0:
        return None, '끝 글이 원본보다 %d바이트 김' % -k
    seg, k = upgrade(seg, k, up, elig, prev_b)
    out += seg
    out += fill(k, color)
    return bytes(out), None


def fill(k, color):
    if k <= 0:
        return b''
    if color:
        return color * (k // 2) + b' ' * (k % 2)
    return b' ' * k
