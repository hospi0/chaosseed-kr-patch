# -*- coding: utf-8 -*-
r"""메뉴 8×8 셀 묶음 라벨 한글화 (2026-10-01) — HELP.BIN 0x1E524(문자 0x2E00‥0x2EFF, 4bpp, 팔레트 30)
  색: 바탕 e · 글자 b · 그림자 d(글자 오른쪽·아래) — 원래 라벨과 같은 꼴.
  1줄(8px×24px) 라벨은 갈무리7(사용자 «7×7 잘 읽힘»), 2줄(16px) 라벨은 갈무리11 / 콘덴스드.
  from gfx_menu import apply; apply(help_bin_bytearray)   ·   python tools/gfx_menu.py → work/gfx_menu.png 미리보기
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
          (0x69, 3, 2, '턴', 'Galmuri11.bdf'), (0x89, 3, 2, '도움말', 'Galmuri11-Condensed.bdf')]
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


def apply(buf):
    for cell, cw, rows, text, fname in LABELS:
        put(buf, cell, render(text, fname, cw * 8, rows * 8), cw, rows)
    return buf


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
