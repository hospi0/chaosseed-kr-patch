# -*- coding: utf-8 -*-
r"""모르는 인코딩 찾기 — 알려진 문장의 «같은 글자 = 같은 코드, 다른 글자 = 다른 코드» 무늬로 훑기
  python tools/patfind.py 파일 "문장" [단위 1|2|2le]
"""
import sys


def find(d, text, unit):
    n = len(text); w = 1 if unit == '1' else 2
    order = 'big' if unit != '2le' else 'little'
    codes = [int.from_bytes(d[i:i + w], order) for i in range(0, len(d) - w + 1, 1)]
    hits = []
    for st in range(0, len(d) - n * w):
        m = {}; inv = {}; ok = True
        for k, ch in enumerate(text):
            c = codes[st + k * w]
            if m.setdefault(ch, c) != c or inv.setdefault(c, ch) != ch:
                ok = False; break
        if ok:
            hits.append((st, m))
    return hits


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    d = open(sys.argv[1], 'rb').read(); t = sys.argv[2]; u = sys.argv[3] if len(sys.argv) > 3 else '2'
    for st, m in find(d, t, u)[:20]:
        print('%08X' % st, ' '.join('%s=%X' % (k, v) for k, v in m.items()))
