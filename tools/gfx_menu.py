# -*- coding: utf-8 -*-
r"""메뉴 8×8 셀 묶음 라벨 한글화 (2026-10-01) — HELP.BIN 0x1E524(문자 0x2E00‥0x2EFF, 4bpp, 팔레트 30)
  색: 바탕 e · 글자 b · 그림자 d(글자 오른쪽·아래) — 원래 라벨과 같은 꼴.
  1줄(8px×24px) 라벨은 갈무리7(사용자 «7×7 잘 읽힘»), 2줄(16px) 라벨은 갈무리11 / 콘덴스드.
  ★실제로 쓰이는 건 CSFR.DAT 0x1A6A9 압축 블록(apply_csfr) — HELP.BIN 사본(apply)은 화면에 안 나옴(2026-10-01 실기)
  from gfx_menu import apply, apply_csfr   ·   python tools/gfx_menu.py → work/gfx_menu.png 미리보기
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, r'C:\claude\project\anearth-kr-patch\tools')
import bdf

BASE = 0x1E524
G = r'C:\claude\utils\font\Galmuri-v2.40.3'
BG, FG, SH = 0xE, 0xB, 0xD
# (첫 셀, 셀 폭, 줄 수, 글, 글꼴)
LABELS = [(0x63, 3, 1, '에너지', 'Galmuri7.bdf'), (0x66, 3, 1, '선단', 'Galmuri7.bdf'),
          (0x73, 3, 1, '속도', 'Galmuri7.bdf'), (0x76, 3, 1, '지력', 'Galmuri7.bdf'),
          (0x83, 3, 1, '수복', 'Galmuri7.bdf'),
          (0x69, 3, 2, '턴', 'Galmuri11.bdf'), (0x89, 3, 2, '도움말', 'Galmuri11-Condensed.bdf'),
          # 상태 창 «エネルギ운반»·«仙丹운반» 앞 라벨(3×2칸) — 2026-10-02 스테이트 NBG2 패턴 이름으로 찾음(문자 0x2EED·0x2E0A)
          (0xED, 3, 2, '에너지', 'Galmuri11-Condensed.bdf'), (0x0A, 3, 2, '선단', 'Galmuri11.bdf')]
_F = {}


def font(name):
    if name not in _F:
        _F[name] = bdf.Font(os.path.join(G, name))
    return _F[name]


def render(text, fname, w, h):
    """→ h×w 색 번호 격자(가운데 맞춤, 잉크 위 모서리를 칸 위로)"""
    pts, _ = font(fname).draw(text, 0, 0)
    xs = [x for x, _ in pts]; ys = [y for _, y in pts]
    iw, ih = max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
    ox = (w - 1 - iw) // 2 - min(xs); oy = max(0, (h - 1 - ih) // 2) - min(ys)
    ink = {(x + ox, y + oy) for x, y in pts if 0 <= x + ox < w and 0 <= y + oy < h}
    g = [[BG] * w for _ in range(h)]
    for x, y in ink:
        for sx, sy in ((x + 1, y), (x, y + 1), (x + 1, y + 1)):
            if 0 <= sx < w and 0 <= sy < h and (sx, sy) not in ink:
                g[sy][sx] = SH
    for x, y in ink:
        g[y][x] = FG
    return g


def put(buf, cell, g, cw, rows):
    for r in range(rows):
        for c in range(cw):
            a = BASE + (cell + r * 16 + c) * 0x20
            for y in range(8):
                for x in range(0, 8, 2):
                    p0, p1 = g[r * 8 + y][c * 8 + x], g[r * 8 + y][c * 8 + x + 1]
                    buf[a + y * 4 + x // 2] = (p0 << 4) | p1


def apply(buf, base=BASE):
    global_base = globals()['BASE']
    globals()['BASE'] = base
    try:
        for cell, cw, rows, text, fname in LABELS:
            put(buf, cell, render(text, fname, cw * 8, rows * 8), cw, rows)
        for cell, n, text in HUD:                              # HUD·상태 창 흰 라벨 — ★HELP.BIN 사본(0x1D524+셀×32)이 실제로 쓰임(2026-10-02 실기 CSFR 만 고쳐선 안 바뀜)
            put_hud(buf, cell, n, text, base - 0x1000)
    finally:
        globals()['BASE'] = global_base
    return buf


CSFR_BLOB = 0x1A6A9          # ★게임이 실제로 VRAM 에 올리는 사본: CSFR.DAT 안 압축 블록(0x34, 풀면 12,288 B, 셀 0x2E00 = 블록 안 0x1000)


def put8(buf, code, ch, base):
    """8×8 셀 한 칸(문자 0x2E00 + code)에 한글 한 자 — 갈무리7"""
    globals()['BASE'], keep = base, globals()['BASE']
    try:
        put(buf, code, render(ch, 'Galmuri7.bdf', 8, 8), 1, 1)
    finally:
        globals()['BASE'] = keep


# CSFR 셀 블록 앞쪽(셀 번호 = 블록 안 32B 단위) 흰 라벨: 바탕 7 · 글자 F · 그림자 A(+1,+1). 32‥36 エネルギー · 37‥38 仙丹
HUD = [(32, 5, '에너지'), (37, 2, '선단')]


def put_hud(u, cell, n, text, org=0):
    pts, _ = font('Galmuri7.bdf').draw(text, 0, 0)
    xs = [x for x, _ in pts]; ys = [y for _, y in pts]
    ink = {(x - min(xs), y - min(ys)) for x, y in pts}
    w = n * 8
    g = [[7] * w for _ in range(8)]
    for x, y in ink:
        if x + 1 < w and y + 1 < 8 and (x + 1, y + 1) not in ink:
            g[y + 1][x + 1] = 0xA
    for x, y in ink:
        if x < w and y < 8:
            g[y][x] = 0xF
    for c in range(n):
        for y in range(8):
            for x in range(0, 8, 2):
                u[org + (cell + c) * 32 + y * 4 + x // 2] = (g[y][c * 8 + x] << 4) | g[y][c * 8 + x + 1]


# 화면 아래 HUD «仙丹»(3×2칸) = 문자 0x2F0A‥0x2F0C/0x2F1A‥0x2F1C — 셀 묶음 2: CSFR.DAT 0x1B8CA 압축 블록(문자 0x2F00 = 블록 0) ·
#   HELP.BIN 0x20524 날 사본 · 색 바탕 0(투명)·글자 8·그림자 A(오른쪽·아래) — 2026-10-02 스테이트 NBG2 패턴 이름으로 찾음
HUD2_BLOB = 0x1B8CA
HUD2_HELP = 0x20524
HUD2 = [(0x0A, 3, 2, '선단', 'Galmuri11.bdf')]


def put_hud2(buf, org):
    for cell, cw, rows, text, fname in HUD2:
        w, h = cw * 8, rows * 8
        pts, _ = font(fname).draw(text, 0, 0)
        xs = [x for x, _ in pts]; ys = [y for _, y in pts]
        iw, ih = max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
        ox = (w - 1 - iw) // 2 - min(xs); oy = (h - 1 - ih) // 2 - min(ys)
        ink = {(x + ox, y + oy) for x, y in pts if 0 <= x + ox < w and 0 <= y + oy < h}
        g = [[0] * w for _ in range(h)]
        for x, y in ink:
            for sx, sy in ((x + 1, y), (x, y + 1), (x + 1, y + 1)):
                if sx < w and sy < h and (sx, sy) not in ink:
                    g[sy][sx] = 0xA
        for x, y in ink:
            g[y][x] = 8
        for r in range(rows):
            for c in range(cw):
                a = org + (cell + r * 16 + c) * 32
                for y in range(8):
                    for x in range(0, 8, 2):
                        buf[a + y * 4 + x // 2] = (g[r * 8 + y][c * 8 + x] << 4) | g[r * 8 + y][c * 8 + x + 1]


def apply_hud2_csfr(d):
    sys.path.insert(0, HERE)
    import lz
    u, e = lz.decompress(d, HUD2_BLOB + 1)
    u = bytearray(u); put_hud2(u, 0)
    c = lz.compress(bytes(u))
    if len(c) > e - (HUD2_BLOB + 1):
        raise SystemExit('⛔CSFR 셀 묶음 2 압축 %d > 원래 %d' % (len(c), e - HUD2_BLOB - 1))
    d[HUD2_BLOB + 1:HUD2_BLOB + 1 + len(c)] = c
    return d


def apply_csfr(d, extra=None):
    """CSFR.DAT(bytearray) 의 셀 묶음 압축 블록을 고쳐 제자리에(새 압축 ≤ 원래 — 뒤는 안 읽힘)"""
    sys.path.insert(0, HERE)
    import lz
    u, e = lz.decompress(d, CSFR_BLOB + 1)
    u = bytearray(u); apply(u, 0x1000)
    for cell, n, text in HUD:                                  # HUD·상태 창 흰 라벨(셀 32‥38, 실기 «에너지 선단»)
        put_hud(u, cell, n, text)
    for code, ch in (extra or {}).items():                     # 선수 이름용 8×8 한글(nameent.SEON — 코드 = 칸 번호)
        put8(u, code, ch, 0x1000)
    c = lz.compress(bytes(u))
    if len(c) > e - (CSFR_BLOB + 1):
        raise SystemExit('⛔CSFR 셀 블록 압축 %d > 원래 %d' % (len(c), e - CSFR_BLOB - 1))
    d[CSFR_BLOB + 1:CSFR_BLOB + 1 + len(c)] = c
    return d


if __name__ == '__main__':
    sys.path.insert(0, HERE)
    import nbg
    from PIL import Image
    v, cram = nbg.load('m2')
    d = apply(bytearray(open(os.path.join(ROOT, 'work', 'disc', 'HELP.BIN'), 'rb').read()))
    S = 6; im = Image.new('RGB', (16 * 8 * S, 6 * 8 * S))
    for r in range(5, 11):
        for c in range(16):
            a = BASE + (r * 16 + c) * 0x20
            for y in range(8):
                for x in range(8):
                    b = d[a + y * 4 + x // 2]; p = b >> 4 if x % 2 == 0 else b & 15
                    col = nbg.color(cram, 30 * 16 + p)
                    for i in range(S):
                        for j in range(S):
                            im.putpixel(((c * 8 + x) * S + i, ((r - 5) * 8 + y) * S + j), col)
    im.save(os.path.join(ROOT, 'work', 'gfx_menu.png'))
