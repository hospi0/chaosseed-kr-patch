# -*- coding: utf-8 -*-
r"""지도·방 종류 그림 라벨 (2026-10-02 실기 «일본어»·«한자») — CSST.DAT 0x11921 압축 블록(0x34, 풀면 2,112 B)
  ★블록은 VDP1 VRAM 0x7800 에 그대로 올라간다(상태 «미추출그래픽» 검산) → 블록 오프셋 = 텍스처 주소 − 0x7800.
  라벨 = 24×16(16×16 한 장 + 8×8 위·아래 두 장, «掘削»만 8×8 두 장이 왼쪽) · «現在地» = 32×16(16×16 두 장).
  위·아래 8×8 은 잉크 줄로 가름(라벨 잉크는 4‥15줄 — 위 칸은 4줄부터, 아래 칸은 0줄부터 참).
  찾은 법: 상태 VDP1 명령표(조각 위치·텍스처 주소) → 남는 칸은 원본 그림을 이어 붙여 확인(work/csst_pairs.png).
  양식: 몸통 = 원본 색(現在地 5 · 방 종류 15) · 테두리 1(8방향 1px) · 바탕 0, 갈무리9.
  python tools/gfx_map.py   → 미리보기 work/gfx_map_preview.png(원본|한글 ×6)
  apply(d) : CSST.DAT(bytearray) 제자리(새 압축 ≤ 원래)
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import lz, gfx_menu

BLOB = 0x11921
FONT = 'Galmuri9.bdf'
BODY, EDGE = 5, 1
# (한글, 폭, [(블록 오프셋, x, y, 크기)])
LABELS = [
    ('현위치', 32, [(0x680, 0, 0, 16), (0x700, 16, 0, 16)]),
    ('생산', 24, [(0x000, 0, 0, 16), (0x080, 16, 0, 8), (0x340, 16, 8, 8)]),
    ('공격', 24, [(0x140, 0, 0, 16), (0x1C0, 16, 0, 8), (0x380, 16, 8, 8)]),
    ('연단', 24, [(0x1E0, 0, 0, 16), (0x260, 16, 0, 8), (0x3A0, 16, 8, 8)]),
    ('소환', 24, [(0x280, 0, 0, 16), (0x300, 16, 0, 8), (0x3C0, 16, 8, 8)]),
    ('굴삭', 24, [(0x320, 0, 0, 8), (0x3E0, 0, 8, 8), (0x400, 8, 0, 16)]),
    ('색적', 24, [(0x480, 0, 0, 16), (0x500, 16, 0, 8), (0x780, 16, 8, 8)]),
    ('창고', 24, [(0x0A0, 0, 0, 16), (0x120, 16, 0, 8), (0x360, 16, 8, 8)]),
    ('전송', 24, [(0x520, 0, 0, 16), (0x5A0, 16, 0, 8), (0x7A0, 16, 8, 8)]),
    ('계단', 24, [(0x5C0, 0, 0, 16), (0x640, 16, 0, 8), (0x7C0, 16, 8, 8)]),
]


def draw(text, w, body=BODY, font=FONT, top=4, rows=12):
    pts, _ = gfx_menu.font(font).draw(text, 0, 0)
    xs = [x for x, _ in pts]; ys = [y for _, y in pts]
    iw, ih = max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
    assert iw + 2 <= w and ih + 2 <= rows + 1, ('라벨이 칸보다 큼', text, iw, ih)
    ox = (w - iw) // 2 - min(xs); oy = top + (rows - ih) // 2 - min(ys)
    ink = {(x + ox, y + oy) for x, y in pts}
    g = [[0] * w for _ in range(16)]
    for x, y in ink:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if 0 <= x + dx < w and 0 <= y + dy < 16 and (x + dx, y + dy) not in ink:
                    g[y + dy][x + dx] = EDGE
    for x, y in ink:
        g[y][x] = body
    return g


def piece(g, x0, y0, n):
    b = bytearray()
    for y in range(n):
        for x in range(0, n, 2):
            b.append(g[y0 + y][x0 + x] << 4 | g[y0 + y][x0 + x + 1])
    return bytes(b)


# ★필드(방 위) 라벨 — CSST.DAT 0x14D3A 블록(풀면 8,736 B, 역시 VDP1 0x7800 에 올라감). 16줄 꽉 찬 24×16, 몸통 10 · 테두리 1.
#   위 8×8 은 16×16 바로 뒤(+0x80), 아래 8×8 은 따로 차례대로(생산 0x1620 · 창고 0x1640 · 공격 0x1660 · 연단 0x1680 /
#   소환 0x1A60 · 굴삭 0x1A80 · 색적 0x1AA0 · 전송 0x1AC0 · 계단 0x1AE0) — 상태 «방한자» 5장 VDP1 명령표로 확인(2026-10-02)
FIELD = [(t, 24, [(a, 0, 0, 16), (a + 0x80, 16, 0, 8), (b, 16, 8, 8)]) for t, a, b in (
    ('생산', 0x1320, 0x1620), ('창고', 0x13C0, 0x1640), ('공격', 0x1460, 0x1660), ('연단', 0x1500, 0x1680),
    ('소환', 0x1720, 0x1A60), ('굴삭', 0x17C0, 0x1A80), ('색적', 0x1860, 0x1AA0), ('전송', 0x1900, 0x1AC0),
    ('계단', 0x19A0, 0x1AE0))]
BLOCKS = [(BLOB, LABELS, FONT, 4, 12), (0x14D3A, FIELD, 'Galmuri11-Condensed.bdf', 1, 14)]


def apply(d):
    for blob, labels, font, top, rows in BLOCKS:
        u, e = lz.decompress(d, blob + 1)
        u = bytearray(u)
        for text, w, ps in labels:
            old = compose(u, w, ps)                              # ★몸통 색 = 원본 라벨에서 0·테두리(1) 아닌 번호 중 최대(現在地 5 · 지도 방 15 · 필드 10)
            body = max({v for r in old for v in r} - {0, EDGE})
            g = draw(text, w, body, font, top, rows)
            for off, x, y, n in ps:
                u[off:off + n * n // 2] = piece(g, x, y, n)
        c = lz.compress(bytes(u))
        if len(c) > e - (blob + 1):
            raise SystemExit('⛔CSST 라벨 블록 %X 압축 %d > 원래 %d' % (blob, len(c), e - blob - 1))
        d[blob + 1:blob + 1 + len(c)] = c
        assert lz.decompress(d, blob + 1)[0] == bytes(u)
    return d


def compose(u, w, ps):
    g = [[0] * w for _ in range(16)]
    for off, x0, y0, n in ps:
        for y in range(n):
            for x in range(n):
                g[y0 + y][x0 + x] = (u[off + y * (n // 2) + x // 2] >> (4 if x % 2 == 0 else 0)) & 15
    return g


def preview():
    from PIL import Image
    d = open(os.path.join(ROOT, 'work', 'disc', 'CSST.DAT'), 'rb').read()
    d2 = apply(bytearray(d))
    pal = {0: (40, 60, 40), 1: (20, 20, 20), 5: (230, 230, 230), 9: (150, 150, 150), 10: (235, 235, 235), 15: (255, 255, 255)}
    allrows = [(blob, l) for blob, labels, *_ in BLOCKS for l in labels]
    im = Image.new('RGB', (2 * 36, len(allrows) * 18), (90, 0, 0))
    for i, (blob, (text, w, ps)) in enumerate(allrows):
        for j, src in enumerate((d, d2)):
            u, _ = lz.decompress(src, blob + 1)
            g = compose(u, w, ps)
            for y in range(16):
                for x in range(w):
                    im.putpixel((j * 36 + x, i * 18 + y), pal.get(g[y][x], (255, 0, 255)))
    im = im.resize((im.width * 6, im.height * 6), Image.NEAREST)
    p = os.path.join(ROOT, 'work', 'gfx_map_preview.png'); im.save(p); print('→', p)


if __name__ == '__main__':
    preview()
