# -*- coding: utf-8 -*-
r"""글꼴(0.BIN 0x78F66, 실행 중 Low RAM 0x0020D616) — 글자당 21바이트 12×14 1bpp.
  3바이트(b0,b1,b2)마다 두 줄: 윗줄 = (b2&15)<<8|b0, 아랫줄 = (b2>>4)<<8|b1, 비트 11 = 왼쪽 끝.
  글자 번호 = 코드 − 0x20. 코드: 0x20‥0xFF 1바이트, 0x18‥0x1F + 둘째 바이트 → ((hi−0x18+1)<<8)|lo.
  렌더러 0x06063804. python tools/font.py [png]  → work/font_sheet.png
"""
import os, sys
from PIL import Image
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OFF = 0x78F66
N = 0x900 - 0x20


def load():
    return open(os.path.join(ROOT, 'work', 'disc', '0.BIN'), 'rb').read()


def rows(d, idx):
    o = OFF + idx * 21; out = []
    for i in range(7):
        b0, b1, b2 = d[o + i * 3:o + i * 3 + 3]
        out += [((b2 & 15) << 8) | b0, ((b2 >> 4) << 8) | b1]
    return out


if __name__ == '__main__':
    d = load(); n = min(N, (len(d) - OFF) // 21)
    cols = 32; S = 2
    im = Image.new('L', (cols * 14 * S, ((n + cols - 1) // cols) * 16 * S), 255)
    px = im.load()
    for i in range(n):
        gx, gy = i % cols * 14, i // cols * 16
        for y, r in enumerate(rows(d, i)):
            for x in range(12):
                if r >> (11 - x) & 1:
                    for a in range(S):
                        for b in range(S): px[(gx + x) * S + a, (gy + y) * S + b] = 0
    im.save(os.path.join(ROOT, 'work', 'font_sheet.png')); print(n, im.size)
