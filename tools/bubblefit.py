# -*- coding: utf-8 -*-
r"""말풍선 줄 다시 접기 (2026-10-02 실기 «길이넘침» — C00038 25칸 줄이 화면 왼쪽 밖으로)
  ★엔진은 말풍선을 자동으로 접지 않는다(줄 폭대로 풍선이 커져 화면 밖으로 나감).
    원문 줄 폭 분포: 18칸에서 벼랑(실기 한계는 23칸)(125 → 23), 최대 21 · 쪽({p}·{06}‥{0A} 사이)당 줄 1‥3(4는 3건).
  규칙: «대사:*» 줄 중 쪽 안에 LIMIT(20)칸 넘는 줄이 있으면 그 쪽을 공백에서 다시 접는다 — 목표 TARGET(18)칸, 줄 수 최소·가장 긴 줄 최소.
        폭 = 토큰 뺀 글자 수(공백도 1칸 — 이 글꼴은 공백이 전각 폭), 빌더처럼 문장부호 뒤 공백은 빼고 잰다.
        줄을 이을 때 다음 줄이 조사로 시작하면(«」\n를») 붙이고, 아니면 공백.
  python tools/bubblefit.py [--write]   (없으면 바뀔 줄만 보여 줌) — work/ko/chaosseed.tsv
"""
import os, re, shutil, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TSV = os.path.join(ROOT, 'work', 'ko', 'chaosseed.tsv')
LIMIT, TARGET, MAXL = 22, 20, 3   # 실기 기준(2026-10-02): 24칸 «소환 방에서 강화 가능한 능력은 이것이니라!» 살짝 넘침 → 23 한계, 여유 1
NL = chr(92) + 'n'
TOK = re.compile(r'\{[^}]*\}')
PG = re.compile(r'(\{p\}|\{0[6789A]\})')
PUNCT_SP = re.compile(r'([,.!?:;)\]\'"~、。，．！？：；）］｝」』】〉》”’…‥・·～〜♪♥]) (?! )')
PARTICLE = tuple('를을는은이가의에로와과도만께라하')
BOUND = tuple('수것거줄데뿐듯')


def w(s):
    s = PUNCT_SP.sub(r'\1', s)
    return len(TOK.sub('', s)) + 4 * len(re.findall(r'\{05:[0-9A-F]{2}\}', s))   # {05:xx} = 인물 이름(4칸 안팎)


def wrap(words, n):
    """words 를 n 줄 이하로, 가장 긴 줄 최소 — DP"""
    m = len(words)
    best = {}

    def f(i, k):
        if i == m:
            return (0, [])
        if k == 0:
            return None
        if (i, k) in best:
            return best[i, k]
        res = None
        for j in range(i + 1, m + 1):
            line = ' '.join(words[i:j])
            lw = w(line)
            if lw > TARGET and j > i + 1:
                break
            r = f(j, k - 1)
            if r is None:
                continue
            cost = max(lw, r[0])
            if res is None or cost < res[0]:
                res = (cost, [line] + r[1])
        best[i, k] = res
        return res
    return f(0, n)


def fit_page(pg):
    lines = pg.split(NL)
    if max(w(l) for l in lines) <= LIMIT:
        return None
    joined = lines[0]
    for l in lines[1:]:
        joined += ('' if l.startswith(PARTICLE) or joined.endswith(('「', '『', '(')) else ' ') + l
    words = []                                                   # 의존명사(수·것·줄·데·뿐·듯) 앞에선 안 끊는다 — 앞말과 한 낱말로
    for x in joined.split(' '):
        if words and x.startswith(BOUND) and (len(x) == 1 or not ('가' <= x[1] <= '힣') or x[1] in '도는를가에밖'):
            words[-1] += ' ' + x
        else:
            words.append(x)
    for n in range(1, MAXL + 2):
        r = wrap(words, n)
        if r and r[0] <= TARGET:
            return NL.join(r[1]), n
    r = wrap(words, MAXL)
    return (NL.join(r[1]), MAXL) if r else (pg, -1)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    rows = [l.rstrip('\n').split('\t') for l in open(TSV, encoding='utf-8')]
    nchg = 0; warn = []
    for c in rows[1:]:
        if len(c) < 6 or not c[5] or not c[2].startswith('대사'):
            continue
        parts = PG.split(c[5]); changed = False
        for i in range(0, len(parts), 2):
            r = fit_page(parts[i])
            if r:
                new, n = r
                if n < 0 or n > MAXL or max(w(l) for l in new.split(NL)) > LIMIT:
                    warn.append((c[0], parts[i], new))
                parts[i] = new; changed = True
        if changed:
            new = ''.join(parts)
            print('%s\n  - %s\n  + %s' % (c[0], c[5], new))
            c[5] = new; nchg += 1
    print('바뀐 줄 %d · 확인 필요 %d' % (nchg, len(warn)))
    for x in warn:
        print('⚠', x)
    if '--write' in sys.argv:
        shutil.copyfile(TSV, TSV + '.bak_bubblefit')
        open(TSV, 'w', encoding='utf-8').write(''.join('\t'.join(c) + '\n' for c in rows))
        print('→', TSV)


if __name__ == '__main__':
    main()
