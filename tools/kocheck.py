# -*- coding: utf-8 -*-
r"""번역 검사 — python tools/kocheck.py [파일 …]   (없으면 work/ko/*.tsv)
  열: ID · 위치 · 구분 · 공유 · 원문 · 번역. «번역» 이 빈 줄은 건너뜀(미번역).
  ⛔오류(빌드 불가):
    · 제어 토큰이 원문과 다름 — {p} · {03:nn} · {04:nn} · {05:nn} · {07}‥{0A} · {c:XXX} · 끝의 {00} (순서까지 같아야)
    · \n 개수가 원문과 다름(줄바꿈은 원문 자리 그대로 — 대사는 엔진이 알아서 접는다)
    · 가나·한자가 남음 / 글꼴에 없는 글자(라틴 소문자 등 — 글꼴엔 숫자·대문자 A‥Z 뿐)
  ⚠경고: 번역 글자 수가 원문의 2배 초과 · 오버레이(ovl_*.tsv «메뉴:NB») 제자리 예산 초과 추정
  ⛔«번역금지» 줄(이름 입력판 한자 표)에 번역을 넣으면 오류
"""
import glob, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOK = re.compile(r'\{(?:p|(?:07|0D|10|11):[0-9A-F]{2}:[0-9A-F]{2}|17:[0-9A-F]{2}|1[0-7]|0[345]:[0-9A-F]{2}|0[0-9A-F]|c:[0-9A-F]{3}|[A-Z0-9]{1,3})\}')
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
        if c[2] in ('영문', '번역금지'):
            if c[2] == '번역금지':
                print('%s:%d %s ⛔번역금지 줄' % (os.path.basename(path), ln, rid)); err += 1
            continue
        msgs = []
        if toks(src) != toks(ko):
            msgs.append('⛔토큰 %s ≠ 원문 %s' % (toks(ko), toks(src)))
        if c[2].startswith('대사'):
            # ★말풍선은 엔진이 접지 않는다(실기 2026-10-02 C00038 25칸 → 화면 밖) — 줄 수는 자유, 한 줄 ≤ 22칸(tools/bubblefit.py)
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import bubblefit
            for seg in re.split(r'\\n|\{p\}|\{0[6789A]\}', ko):
                if bubblefit.w(seg) > bubblefit.LIMIT:
                    msgs.append('⛔말풍선 줄 %d칸 > %d: %s' % (bubblefit.w(seg), bubblefit.LIMIT, seg))
        elif src.count('\\n') != ko.count('\\n'):
            msgs.append('⛔\\n %d개 ≠ 원문 %d개' % (ko.count('\\n'), src.count('\\n')))
        body = TOK.sub('', ko).replace('\\n', '')
        if KANA_KANJI.search(body):
            msgs.append('⛔가나·한자 남음: %s' % ''.join(sorted(set(KANA_KANJI.findall(body)))))
        bad = sorted({ch for ch in body if not ('가' <= ch <= '힣' or '0' <= ch <= '9' or 'A' <= ch <= 'Z'
                                                 or '０' <= ch <= '９' or 'Ａ' <= ch <= 'Ｚ' or ch in OK_SYM)
                      and not KANA_KANJI.match(ch)})
        if bad:
            msgs.append('⛔글꼴에 없는 글자: %s' % ''.join(bad))
        m = re.match(r'(?:메뉴|잡음\?):(\d+)B', c[2])
        if m:                                      # 오버레이 문자열은 제자리 — 한글 2바이트로 쳐서 예산 넘으면 경고
            est = sum(2 if '가' <= ch <= '힣' else 1 for ch in body) + ko.count('\\n') + 2 * len(re.findall(r'\{0[34]:', ko))
            if est > int(m.group(1)):
                msgs.append('⚠메뉴 예산 %dB < 추정 %dB(자주 쓰는 음절은 1바이트라 실제론 줄 수 있음 — 짧게 줄일 것)' % (int(m.group(1)), est))
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
