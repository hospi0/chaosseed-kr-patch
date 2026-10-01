# -*- coding: utf-8 -*-
r"""PoC (2026-10-01) — 세이브스테이트 장면(SSS0.ADT 항목 002, 0x22B) «それでは、試練の場に行くぞ！» 를 같은 18바이트 한국어로.
  «그럼、시련의 장으로 가자!» = 1바이트 칸 6자(가나 칸 0xC0‥0xC5 덮음) + 2바이트 칸 4자(한자 칸 0x680‥0x683 → 1D 80‥83)
  + 、(0x24) ·공백(0x20) ·!(0x21) 원래 글꼴. 길이가 같으니 점프·진입점 표는 그대로.
  글리프: 갈무리11 → 12×14 1bpp(글꼴 0.BIN 0x78F66, 21 B/자, tools/font.py 형식), 몸 x 0‥10 · y 1‥11.
  ⚠ PoC 전용: 덮은 가나 칸(フヘホマミム)은 다른 대사에서 한글로 보인다.
  python tools/poc.py → work/out/…(Track 1).bin  (원본 트랙 2·cue 는 그대로 쓰면 됨)
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, r'C:\claude\project\anearth-kr-patch\tools')
import bdf, disc, font, lz
sys.path.insert(0, HERE)
import iso

GAL = r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri11.bdf'
OUT = os.path.join(ROOT, 'work', 'out', os.path.basename(disc.ROM))
ITEM, AT = 2, 0x22B
OLD = bytes.fromhex('7c97ea87 2419d9 19bf86 1862 83 1872 75e6 21'.replace(' ', ''))
TEXT = [('그', 0xC0), ('럼', 0xC1), ('、', 0x24), ('시', 0x680), ('련', 0x681), ('의', 0x682), (' ', 0x20),
        ('장', 0x683), ('으', 0xC2), ('로', 0xC3), (' ', 0x20), ('가', 0xC4), ('자', 0xC5), ('!', 0x21)]


def code_bytes(c):
    return bytes([c]) if c < 0x100 else bytes([0x18 + (c >> 8) - 1, c & 0xFF])


def glyph(F, ch):
    pts, _ = F.draw(ch, 0, 0)
    rows = [0] * 14
    for x, y in pts:
        Y = y - 2                       # 갈무리11 몸이 3‥13행 → 1‥11행(원래 가나 1‥13행에 맞춤)
        if 0 <= x < 12 and 0 <= Y < 14:
            rows[Y] |= 0x800 >> x
    out = bytearray()
    for i in range(7):
        a, b = rows[2 * i], rows[2 * i + 1]
        out += bytes([a & 0xFF, b & 0xFF, (a >> 8) | ((b >> 8) << 4)])
    return bytes(out)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    F = bdf.Font(GAL)
    # ① 글꼴
    exe = bytearray(open(os.path.join(ROOT, 'work', 'disc', '0.BIN'), 'rb').read())
    for ch, c in TEXT:
        if '가' <= ch <= '힣':
            o = font.OFF + (c - 0x20) * 21
            exe[o:o + 21] = glyph(F, ch)
    # ② 대사
    new = b''.join(code_bytes(c) for _, c in TEXT)
    assert len(new) == len(OLD), (len(new), len(OLD))
    adt = open(os.path.join(ROOT, 'work', 'disc', 'SSS0.ADT'), 'rb').read()
    offs = lz.archive(adt)
    items = [adt[a:b] for a, b in zip(offs, offs[1:])]
    u, _ = lz.decompress(items[ITEM], 1)
    assert u[AT:AT + len(OLD)] == OLD, u[AT:AT + 20].hex()
    u2 = u[:AT] + new + u[AT + len(OLD):]
    items[ITEM] = b'\x34' + lz.compress(u2)
    adt2 = lz.replace_item(adt, ITEM, items[ITEM])
    o2 = lz.archive(adt2)
    for k, (a, b) in enumerate(zip(o2, o2[1:])):                 # 전 항목 검산: 2번은 새 내용, 나머지는 원본과 같아야
        if b <= a or adt2[a] != 0x34:
            continue
        x, _ = lz.decompress(adt2, a + 1)
        y = u2 if k == ITEM else lz.decompress(adt, offs[k] + 1)[0]
        assert x == y, k
    print('SSS0.ADT %d → %d B (항목 %d: %d → %d B)' % (len(adt), len(adt2), ITEM, offs[ITEM + 1] - offs[ITEM], len(items[ITEM])))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    iso.patch(disc.ROM, OUT, {'0.BIN': bytes(exe), 'SSS0.ADT': adt2})
    print('→', OUT)


if __name__ == '__main__':
    main()
