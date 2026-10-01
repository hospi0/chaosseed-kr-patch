# -*- coding: utf-8 -*-
r"""평문 SJIS 문자열 훑기(후보 생성용 — 저장 구조 확정 아님)
  python tools/sjscan.py            → 파일별 후보 문자열 수·글자 수
  python tools/sjscan.py FILE [n]   → 그 파일 후보 앞 n개(오프셋·내용)
  후보 = 전각 SJIS(+반각 ASCII 허용) 연속 4자 이상, 가나 1자 이상(한자만 줄은 빠짐 — 하한)
"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DISC = os.path.join(ROOT, 'work', 'disc')


def lead(b):
    return 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xFC


def scan(d, minlen=4):
    out = []; i = 0; n = len(d)
    while i < n - 1:
        j = i; s = []; kana = 0
        while j < n - 1:
            b = d[j]
            if lead(b) and 0x40 <= d[j + 1] <= 0xFC and d[j + 1] != 0x7F:
                try:
                    c = d[j:j + 2].decode('cp932')
                except UnicodeDecodeError:
                    break
                if 'ぁ' <= c <= 'ヿ':
                    kana += 1
                s.append(c); j += 2
            elif 0x20 <= b < 0x7F and s:
                s.append(chr(b)); j += 1
            else:
                break
        full = sum(1 for c in s if ord(c) > 0x7F)
        if full >= minlen and kana:
            out.append((i, ''.join(s).rstrip()))
            i = j
        else:
            i += 1
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    if len(sys.argv) > 1:
        d = open(os.path.join(DISC, sys.argv[1]), 'rb').read()
        r = scan(d); n = int(sys.argv[2]) if len(sys.argv) > 2 else 60
        for o, s in r[:n]:
            print('%08X  %s' % (o, s))
        print('후보 %d개' % len(r))
        return
    tot = 0
    for f in sorted(os.listdir(DISC)):
        d = open(os.path.join(DISC, f), 'rb').read()
        r = scan(d)
        if r:
            ch = sum(len(s) for _, s in r); tot += ch
            print('%-14s %9d B  후보 %5d  글자 %7d' % (f, len(d), len(r), ch))
    print('합계 글자', tot)


if __name__ == '__main__':
    main()
