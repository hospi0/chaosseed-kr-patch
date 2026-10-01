# -*- coding: utf-8 -*-
r"""가나 이름 → 선(SEON 56자: ㅏ·ㅣ·ㅡ·ㅜ × 14자음, 받침 없음) 근사 음역 (2026-10-02)
  12px·8×8 양쪽에 찍히는 선수 이름(기본 이름 CS.BIN · 무작위 이름 NAMEENT.BIN)은 두 글꼴 코드가 같은 선 56자만 쓸 수 있다.
  규칙: 자음은 거센소리(か=ㅋ·た=ㅌ·つ=ㅊ), 모음 a→ㅏ i→ㅣ u→ㅜ(す·つ·ず→ㅡ) e→ㅣ o→ㅜ, 작은 ゃゅょ→ㅏ·ㅜ·ㅜ,
        ッ·ー·ン 은 뺀다(근사). 탁점 분리 표기(ケフ゛)는 앞 글자와 합친다.
  python tools/kana2seon.py W00427-W00449 W01124-W01289 > work/ko_batch/w08_seon_names.tsv
"""
import os, sys, unicodedata
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import nameent

CON = {'': 'ㅇ', 'k': 'ㅋ', 'g': 'ㄱ', 's': 'ㅅ', 'z': 'ㅈ', 'j': 'ㅈ', 't': 'ㅌ', 'd': 'ㄷ', 'c': 'ㅊ', 'n': 'ㄴ', 'h': 'ㅎ',
       'f': 'ㅍ', 'b': 'ㅂ', 'p': 'ㅍ', 'm': 'ㅁ', 'y': 'ㅇ', 'r': 'ㄹ', 'w': 'ㅇ'}
VOW = {'a': 'ㅏ', 'i': 'ㅣ', 'u': 'ㅜ', 'e': 'ㅣ', 'o': 'ㅜ'}
ROM = {}
for row, cons in (('アイウエオ', ''), ('カキクケコ', 'k'), ('サシスセソ', 's'), ('タチツテト', 't'), ('ナニヌネノ', 'n'),
                  ('ハヒフヘホ', 'h'), ('マミムメモ', 'm'), ('ラリルレロ', 'r'), ('ガギグゲゴ', 'g'), ('ザジズゼゾ', 'z'),
                  ('ダヂヅデド', 'd'), ('バビブベボ', 'b'), ('パピプペポ', 'p')):
    for ch, v in zip(row, 'aiueo'):
        c = cons
        if ch == 'チ': c = 'c'
        if ch == 'ツ': c = 'c'
        if ch == 'フ': c = 'f'
        if ch in 'ジヂ': c = 'j'
        ROM[ch] = (c, v)
ROM.update({'ヤ': ('y', 'a'), 'ユ': ('y', 'u'), 'ヨ': ('y', 'o'), 'ワ': ('w', 'a'), 'ヲ': ('w', 'o'), 'ヴ': ('b', 'u')})
SMALL = {'ャ': 'a', 'ュ': 'u', 'ョ': 'o', 'ァ': 'a', 'ィ': 'i', 'ゥ': 'u', 'ェ': 'e', 'ォ': 'o'}
CHO = 'ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ'
JUNG = 'ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ'


def syl(c, v):
    return chr(0xAC00 + CHO.index(c) * 588 + JUNG.index(v) * 28)


def conv(s):
    s = unicodedata.normalize('NFKC', s.replace('゛', '゙').replace('゜', '゚'))
    s = ''.join(chr(ord(c) + 0x60) if 'ぁ' <= c <= 'ゖ' else c for c in s)       # 히라가나 → 가타카나
    out = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch in ROM:
            c, v = ROM[ch]
            if i + 1 < len(s) and s[i + 1] in SMALL:
                v = SMALL[s[i + 1]]; i += 1
                if c == '' : c = ''
            vv = VOW[v]
            if v == 'u' and c in ('s', 'c', 'z'):
                vv = 'ㅡ'
            out.append(syl(CON[c], vv))
        i += 1
    r = ''.join(out)
    assert all(x in nameent.SEON_CODE for x in r), (s, r)
    return r


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    rows = {l.split('\t')[0]: l.split('\t') for l in open(os.path.join(ROOT, 'work', 'text', 'ovl2.tsv'), encoding='utf-8').read().split('\n')[1:] if l}
    print('# 선수 이름(12px·8×8 공용) — 선 56자 근사 음역(tools/kana2seon.py)')
    for rng in sys.argv[1:]:
        a, b = (int(x[1:]) for x in rng.split('-'))
        for n in range(a, b + 1):
            r = rows.get('W%05d' % n)
            if not r:
                continue
            k = conv(r[4])
            budget = int(r[2].split(':')[1][:-1])
            print('W%05d\t%s' % (n, k[:budget] if k else ''))


if __name__ == '__main__':
    main()
