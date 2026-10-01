# -*- coding: utf-8 -*-
r"""1bpp 글꼴 후보 훑기(후보 생성용) — python tools/fontscan.py
  칸(w×h, 행당 w/8 바이트)마다 «잉크 밀도 8‥50%, 비어 있지 않음» 이 연속 N칸 이상인 구간을 보고.
  ★글꼴 확정은 그림으로 눈 확인 + 그리는 코드로.
"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHAPES = [(16, 16), (12, 12), (16, 12), (8, 16), (8, 8), (16, 14), (24, 24)]


def files():
    for base in ('disc', 'unpack'):
        top = os.path.join(ROOT, 'work', base)
        for dp, _, fs in os.walk(top):
            for f in fs:
                p = os.path.join(dp, f)
                if f.endswith('.AVI'):
                    continue
                yield os.path.relpath(p, top), p


POP = [bin(i).count('1') for i in range(256)]


def scan(d, w, h, minrun=64):
    bpr = (w + 7) // 8; cs = bpr * h; out = []
    for ph in range(0, cs, 2):
        run = 0; st = ph
        for o in range(ph, len(d) - cs, cs):
            c = d[o:o + cs]
            ink = sum(POP[x] for x in c)
            ok = 0 < ink and 0.06 * w * h <= ink <= 0.5 * w * h and c[-bpr:] != c[:bpr] * 1 or False
            # 1bpp 글자: 모든 바이트가 0xFF/0x00 만이면 그림 조각일 가능성 — 0xFF 비율 제한
            if ok and c.count(0xFF) > cs // 3:
                ok = False
            if ok:
                if run == 0:
                    st = o
                run += 1
            else:
                if run >= minrun:
                    out.append((st, run))
                run = 0
        if run >= minrun:
            out.append((st, run))
    # 같은 구간 다른 위상 중복 제거
    out.sort(key=lambda x: -x[1])
    keep = []
    for s, r in out:
        if all(not (s < k + rr * cs and k < s + r * cs) for k, rr in keep):
            keep.append((s, r))
    return keep


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    for name, p in files():
        d = open(p, 'rb').read()
        if len(d) > 3_000_000:
            continue
        for w, h in SHAPES:
            for s, r in scan(d, w, h):
                print('%-28s %2dx%-2d  %8X  %5d칸' % (name, w, h, s, r))


if __name__ == '__main__':
    main()
