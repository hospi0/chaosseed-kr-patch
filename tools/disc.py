# -*- coding: utf-8 -*-
r"""선굴활룡대전 카오스 시드 — 디스크(트랙 1, MODE1/2352) ISO9660 읽기(하위 디렉터리 포함)
  python tools/disc.py ls                 → 파일 목록(경로 LBA 크기)
  python tools/disc.py get [경로…]        → work/disc/ 에 뽑기(없으면 1MB 이하 전부)
"""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
_D = 'C:/claude/roms/ss/Senkutsu Katsuryu Taisen - Chaos Seed (Japan) (Disc 1) (Game Disc) (Rev B) (21M)'
ROM = '\\\\?\\' + os.path.join(_D, os.path.basename(_D) + ' (Track 1).bin').replace('/', os.sep)   # 경로 260자 초과 대비 \\?\
if not os.path.exists(ROM):                                   # 2026-10-03 사용자가 roms/ss/완료/ 로 옮김
    _D2 = os.path.join(os.path.dirname(_D), '완료', os.path.basename(_D))
    ROM = '\\\\?\\' + os.path.join(_D2, os.path.basename(_D) + ' (Track 1).bin').replace('/', os.sep)
if not os.path.exists(ROM):                                   # 예전 두 겹 폴더(2026-10-02 사용자가 한 겹으로 정리)
    ROM = '\\\\?\\' + os.path.join(_D, os.path.basename(_D), os.path.basename(_D) + ' (Track 1).bin').replace('/', os.sep)
OUT = os.path.join(ROOT, 'work', 'disc')


class Disc:
    def __init__(self, path=ROM):
        self.f = open(path, 'rb')

    def sec(self, l, n=1):
        out = bytearray()
        for i in range(n):
            self.f.seek((l + i) * 2352 + 16); out += self.f.read(2048)
        return bytes(out)

    def read(self, lba, size):
        return self.sec(lba, (size + 2047) // 2048)[:size]

    def walk(self, lba=None, size=None, base=''):
        if lba is None:
            pvd = self.sec(16)
            lba, size = struct.unpack_from('<I', pvd, 156 + 2)[0], struct.unpack_from('<I', pvd, 156 + 10)[0]
        d = self.read(lba, size); p = 0; out = []
        while p < len(d):
            L = d[p]
            if L == 0:
                p = (p // 2048 + 1) * 2048; continue
            el, sz, fl = struct.unpack_from('<I', d, p + 2)[0], struct.unpack_from('<I', d, p + 10)[0], d[p + 25]
            nm = d[p + 33:p + 33 + d[p + 32]]
            if nm not in (b'\0', b'\1'):
                name = nm.decode('ascii', 'replace').split(';')[0]
                if fl & 2:
                    out += self.walk(el, sz, base + name + '/')
                else:
                    out.append((base + name, el, sz))
            p += L
        return out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    dsk = Disc(); fs = dsk.walk()
    if sys.argv[1] == 'ls':
        for n, l, s in sorted(fs, key=lambda x: x[1]):
            print('%-32s %8d %10d' % (n, l, s))
        print('파일 %d개 · 합계 %d B' % (len(fs), sum(s for _, _, s in fs)))
    elif sys.argv[1] == 'get':
        want = set(sys.argv[2:])
        for n, l, s in fs:
            if (want and n in want) or (not want and s <= 1 << 20):
                p = os.path.join(OUT, n); os.makedirs(os.path.dirname(p), exist_ok=True)
                open(p, 'wb').write(dsk.read(l, s))
        print('→', OUT)


if __name__ == '__main__':
    main()
