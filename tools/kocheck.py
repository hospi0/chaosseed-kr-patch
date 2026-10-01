# -*- coding: utf-8 -*-
r"""번역 검사 — python tools/kocheck.py [파일 …]   (없으면 work/ko/*.tsv)
  열: ID · 위치 · 구분 · 공유 · 원문 · 번역. «번역» 이 빈 줄은 건너뜀(미번역).
  ⛔오류(빌드 불가):
    · 제어 토큰이 원문과 다름 — {p} · {03:nn} · {04:nn} · {05:nn} · {07}‥{0A} · {c:XXX} · 끝의 {00} (순서까지 같아야)
    · \n 개수가 원문과 다름(줄바꿈은 원문 자리 그대로 — 대사는 엔진이 알아서 접는다)
    · 가나·한자가 남음 / 글꼴에 없는 글자(라틴 소문자 등 — 글꼴엔 숫자·대문자 A‥Z 뿐)
  ⚠경고: 부호 뒤 공백(빌더가 지운다 — 무시해도 됨) · 번역 글자 수가 원문의 2배 초과
"""
import glob, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOK = re.compile(r'\{(?:p|0[345]:[0-9A-F]{2}|0[0-9A-F]|c:[0-9A-F]{3}|[A-Z0-9]{1,3})\}')
OK_SYM = set(' 　!?。、゛゜―＋（）『』「」ー：／，．・＆％々‥～♡○◀▶■！？()~-+:/.,&%')
KANA_KANJI = re.compile(r'[぀-ヿ一-鿿]')


def toks(s):
    return TOK.findall(s)


def check(path):
    err = warn = done = 0
    for ln, line in enumerate(open(path, encoding='utf-8'), 1):
        c = line.rstrip('\n').split('\t')
        if ln == 1 or len(c) < 6 or not c[5].strip():
            continue
        rid, src, ko = c[0], c[4], c[5]; done += 1
        if c[2] == '영문':
            continue
        msgs = []
        if toks(src) != toks(ko):
            msgs.append('⛔토큰 %s ≠ 원문 %s' % (toks(ko), toks(src)))
        if src.count('\\n') != ko.count('\\n'):
            msgs.append('⛔\\n %d개 ≠ 원문 %d개' % (ko.count('\\n'), src.count('\\n')))
        body = TOK.sub('', ko).replace('\\n', '')
        if KANA_KANJI.search(body):
            msgs.append('⛔가나·한자 남음: %s' % ''.join(sorted(set(KANA_KANJI.findall(body)))))
        bad = sorted({ch for ch in body if not ('가' <= ch <= '힣' or '0' <= ch <= '9' or 'A' <= ch <= 'Z'
                                                 or '０' <= ch <= '９' or 'Ａ' <= ch <= 'Ｚ' or ch in OK_SYM)
                      and not KANA_KANJI.match(ch)})
        if bad:
            msgs.append('⛔글꼴에 없는 글자: %s' % ''.join(bad))
        n_src = len(TOK.sub('', src).replace('\\n', ''))
        if n_src and len(body) > 2 * n_src + 4:
            msgs.append('⚠원문 %d자 → %d자' % (n_src, len(body)))
        for m in msgs:
            if m.startswith('⛔'):
                err += 1
            else:
                warn += 1
            print('%s:%d %s %s' % (os.path.basename(path), ln, rid, m))
    return err, warn, done


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    files = sys.argv[1:] or sorted(glob.glob(os.path.join(ROOT, 'work', 'ko', '*.tsv')))
    E = W = D = 0
    for f in files:
        e, w, d = check(f); E += e; W += w; D += d
    print('검사 %d줄 · 오류 %d · 경고 %d' % (D, E, W))
    sys.exit(1 if E else 0)


if __name__ == '__main__':
    main()
