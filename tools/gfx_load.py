# -*- coding: utf-8 -*-
r"""LOAD.BIN 그림 글자(제목 RAM 선택·저장 화면·시나리오 선택 간판) 한글화 (2026-10-02 실기 «미번역»)
  글자 그림 = LOAD.BIN 안 압축 블록(머리 0x34, tools/lz.py)의 16×16 4bpp 칸(128 B). 게임이 칸을 한 글자씩 스프라이트로 찍는다
  (같은 칸을 여러 자리에서 돌려 씀 — 그래서 «칸 = 한 음절» 로 바꾸고 배치는 원래 그대로).
    0x13916 저장 화면: 0‥4 空いてます(획 1) · 40‥44 굵은 空いてます(획 1+그림자 3) · 64‥79 回終シナリオ選択つづき消去はいえ(획 1+그림자 3)
    0x155AB 시나리오 선택 간판: 10‥15 シナリオ選択(획 15+그림자 1)
    0x166F4 제목 메뉴: 11‥16 カーﾄﾘｯｼﾞ · 17‥21 を使用する · 22‥23 本体 (획 F/아래 E, 그림자 C, 테두리 B)
  새 블록은 lz.compress 로 다시 묶어 원래 압축 길이 안에(블록이 붙어 있음 — 넘치면 빌드 실패).
  python tools/gfx_load.py   → work/gfx_load_preview.png (확인용)
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, r'C:\claude\project\anearth-kr-patch\tools')
import bdf, lz

G = r'C:\claude\utils\font\Galmuri-v2.40.3'
_F = {}

# (블록, 칸, 글자, 스타일, 글꼴)  — ''=빈칸
SAVE = [(0x13916, 0, '비', 'p1', 'Galmuri11-Bold.bdf'), (0x13916, 1, '어', 'p1', 'Galmuri11-Bold.bdf'),
        (0x13916, 2, '있', 'p1', 'Galmuri11-Bold.bdf'), (0x13916, 3, '요', 'p1', 'Galmuri11-Bold.bdf'),
        (0x13916, 4, '', 'p1', None),
        (0x13916, 40, '비', 's13', 'Galmuri11-Bold.bdf'), (0x13916, 41, '어', 's13', 'Galmuri11-Bold.bdf'),
        (0x13916, 42, '있', 's13', 'Galmuri11-Bold.bdf'), (0x13916, 43, '요', 's13', 'Galmuri11-Bold.bdf'),
        (0x13916, 44, '', 's13', None)]
MENU = [(64, '회'), (65, '차'), (66, '시'), (67, '나'), (68, '리'), (69, '오'), (70, '선'), (71, '택'),
        (72, '이'), (73, '어'), (74, '서'), (75, '삭'), (76, '제'), (77, '예'), (78, ''), (79, '아니')]
SIGN = [(10, '시'), (11, '나'), (12, '리'), (13, '오'), (14, '선'), (15, '택')]
TITLE = [(11, ''), (12, '카'), (13, '트'), (14, '리'), (15, '지'), (16, ''),
         (17, '을'), (18, '사'), (19, '용'), (20, '하'), (21, '기'), (22, '본'), (23, '체')]


def font(name):
    if name not in _F:
        _F[name] = bdf.Font(os.path.join(G, name))
    return _F[name]


def mask(text, fname, w=16, h=16, dy=0):
    """글자 잉크 좌표 집합(가운데 맞춤). 두 자면 8칸씩 나눠 Galmuri7"""
    if not text:
        return set()
    if len(text) == 2:
        a = mask(text[0], 'Galmuri7.bdf', 8, h, dy); b = mask(text[1], 'Galmuri7.bdf', 8, h, dy)
        return a | {(x + 8, y) for x, y in b}
    pts, _ = font(fname).draw(text, 0, 0)
    xs = [x for x, _ in pts]; ys = [y for _, y in pts]
    iw, ih = max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
    ox = (w - 1 - iw) // 2 - min(xs); oy = (h - 1 - ih) // 2 - min(ys) + dy
    return {(x + ox, y + oy) for x, y in pts if 0 <= x + ox < w and 0 <= y + oy < h}


def grid(ink, style):
    g = [[0] * 16 for _ in range(16)]
    inb = lambda x, y: 0 <= x < 16 and 0 <= y < 16
    if style == 'p1':
        for x, y in ink:
            g[y][x] = 1
        return g
    if style in ('s13', 'sign'):
        fg, sh = (1, 3) if style == 's13' else (15, 1)
        for x, y in ink:
            if inb(x + 1, y + 1) and (x + 1, y + 1) not in ink:
                g[y + 1][x + 1] = sh
        for x, y in ink:
            g[y][x] = fg
        return g
    if style == 'title':                                     # 획 F(아래쪽 E) · 그림자 C(+1,+1) · 테두리 B
        shadow = {(x + 1, y + 1) for x, y in ink if inb(x + 1, y + 1)} - ink
        body = ink | shadow
        for x, y in body:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if inb(x + dx, y + dy) and (x + dx, y + dy) not in body:
                        g[y + dy][x + dx] = 11
        for x, y in shadow:
            g[y][x] = 12
        for x, y in ink:
            g[y][x] = 14 if y >= 11 else 15
        return g
    raise ValueError(style)


def put(u, t, g):
    for y in range(16):
        for x in range(0, 16, 2):
            u[t * 128 + y * 8 + x // 2] = (g[y][x] << 4) | g[y][x + 1]


def jobs():
    out = {}
    for blk, t, ch, st, fn in SAVE:
        out.setdefault(blk, []).append((t, ch, st, fn))
    for t, ch in MENU:
        out.setdefault(0x13916, []).append((t, ch, 's13', 'Galmuri11.bdf'))
    for t, ch in SIGN:
        out.setdefault(0x155AB, []).append((t, ch, 'sign', 'Galmuri11-Bold.bdf'))
    for t, ch in TITLE:
        out.setdefault(0x166F4, []).append((t, ch, 'title', 'Galmuri11-Bold.bdf'))
    return out


def apply(L):
    """LOAD.BIN(bytearray) 의 세 블록을 고쳐 제자리에 — 새 압축 ≤ 원래"""
    done = {}
    for blk, js in jobs().items():
        u, e = lz.decompress(L, blk + 1)
        u = bytearray(u)
        for t, ch, st, fn in js:
            put(u, t, grid(mask(ch, fn), st))
        if blk == 0x13916:                                      # 굵은 空 의 지붕(宀)은 39번 칸 아래 4줄을 따로 찍는다 → 지움(실기 «비 자 깨짐»)
            u[39 * 128 + 12 * 8:40 * 128] = bytes(4 * 8)
        c = lz.compress(bytes(u))
        room = e - (blk + 1)
        if len(c) > room:
            raise SystemExit('⛔LOAD 그림 블록 %X 압축 %d > 원래 %d' % (blk, len(c), room))
        L[blk + 1:blk + 1 + len(c)] = c
        done[blk] = (len(c), room, bytes(u))
    return done


def preview(done, path):
    from PIL import Image
    pal = {0: (20, 20, 20), 1: (240, 240, 240), 3: (90, 90, 160), 11: (40, 40, 120), 12: (90, 90, 90), 14: (250, 200, 80), 15: (255, 255, 200)}
    rows = []
    for blk, js in jobs().items():
        u = done[blk][2]
        rows.append([t for t, *_ in js])
    W = max(len(r) for r in rows) * 18; H = len(rows) * 18
    im = Image.new('RGB', (W, H), (60, 60, 60))
    for ri, (blk, js) in enumerate(jobs().items()):
        u = done[blk][2]
        for ci, (t, *_) in enumerate(js):
            for y in range(16):
                for x in range(16):
                    b = u[t * 128 + (y * 16 + x) // 2]; v = (b >> 4) if x % 2 == 0 else (b & 15)
                    im.putpixel((ci * 18 + x, ri * 18 + y), pal.get(v, (255, 0, 255)))
    im.resize((W * 4, H * 4), Image.NEAREST).save(path)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    L = bytearray(open(os.path.join(ROOT, 'work', 'disc', 'LOAD.BIN'), 'rb').read())
    done = apply(L)
    for blk, (n, room, _) in done.items():
        print('%X: %d B / %d B' % (blk, n, room))
    preview(done, os.path.join(ROOT, 'work', 'gfx_load_preview.png'))
