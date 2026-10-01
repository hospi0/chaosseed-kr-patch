# -*- coding: utf-8 -*-
r"""오버레이 번역 병합·줄 접기·예산 검사 (2026-10-02) — work/ko/ovl2.tsv(W…) · work/ko/ovl.tsv(V… 고칠 때)
  배치 파일: «ID<TAB>번역» 줄들(# 주석). 번역이 «~» 로 시작하면 자동 접기:
    · 원문의 앞 토큰 덩어리({10:02:05} 등)·뒤 토큰 덩어리({04:00}{09} 등)는 그대로 붙인다
    · 줄바꿈 토큰은 원문 것(\n = 05 또는 {06}) · 폭 W = 원문 줄의 최대 칸 수(글자 1칸 — 이 글꼴은 공백도 한 칸)
      «~25~본문» 이면 W=25 로 지정 · «¶» = 강제 줄바꿈
    · 낱말 단위로 접고(⛔낱말 한복판 자르기 금지 — 한 낱말이 W 보다 길 때만), 줄 수가 원문보다 많으면 오류
  문장부호 뒤 공백 1칸은 접기 전에 지운다(insert.load_ko 와 같은 규칙).
  끝에 실제 글자표(insert.charmap)로 인코딩해 «원래 바이트» 예산 초과·글꼴에 없는 글자를 보고한다.
  python tools/trw.py 배치.tsv [...]      (배치 없이 실행하면 검사만)
"""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import insert

TOKS = re.compile(r'\{[^}]*\}')


def load(path):
    lines = open(path, encoding='utf-8').read().split('\n')
    return lines[0], [l.split('\t') for l in lines[1:] if l]


def save(path, head, rows):
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(head + '\n' + ''.join('\t'.join(r) + '\n' for r in rows))


def nl_of(src):
    return '\\n' if '\\n' in src else ('{06}' if '{06}' in src else None)


def width(s):
    return len(TOKS.sub('', s))


def wrap(src, text):
    m = re.match(r'~(\d+)~', text)
    text = text[m.end():] if m else text[1:]
    nl = nl_of(src)
    pre = re.match(r'(\{[^}]*\})*', src).group()
    suf = re.search(r'(\{[^}]*\})*$', src).group()
    body_src = src[len(pre):len(src) - len(suf)] if suf else src[len(pre):]
    olines = body_src.split(nl) if nl else [body_src]
    W = int(m.group(1)) if m else max(width(l) for l in olines)
    text = insert.PUNCT_SP.sub(r'\1', text)
    out = []
    for para in text.split('¶'):
        cur = ''
        for w in para.split(' '):
            if not w:
                continue
            cand = (cur + ' ' + w) if cur else w
            if width(cand) <= W:
                cur = cand; continue
            if cur:
                out.append(cur)
            while width(w) > W:                                # 낱말이 줄보다 길 때만 자름
                out.append(w[:W]); w = w[W:]
            cur = w
        out.append(cur)
    if nl is None and len(out) > 1:
        raise ValueError('줄바꿈 없는 원문인데 %d줄 (W=%d): %s' % (len(out), W, out))
    if len(out) > len(olines):
        raise ValueError('줄 %d > 원문 %d (W=%d): %s' % (len(out), len(olines), W, ' / '.join(out)))
    return pre + (nl or '').join(out) + suf


def main(args):
    sys.stdout.reconfigure(encoding='utf-8')
    p2 = os.path.join(ROOT, 'work', 'ko', 'ovl2.tsv')
    if not os.path.exists(p2):
        head, rows = load(os.path.join(ROOT, 'work', 'text', 'ovl2.tsv')); save(p2, head, rows)
    p1 = os.path.join(ROOT, 'work', 'ko', 'ovl.tsv')
    tabs = {p: load(p) for p in (p1, p2)}
    idx = {r[0]: r for p in tabs for r in tabs[p][1]}
    err = []
    for fn in args:
        for ln, l in enumerate(open(fn, encoding='utf-8'), 1):
            l = l.rstrip('\n')
            if not l.strip() or l.startswith('#'):
                continue
            rid, t = l.split('\t', 1)
            if rid not in idx:
                err.append('%s:%d 없는 ID %s' % (fn, ln, rid)); continue
            src = idx[rid][4]
            auto = t.startswith('~')
            try:
                t = wrap(src, t) if auto else t
            except ValueError as e:
                err.append('%s %s' % (rid, e)); continue
            # 번역에 남긴 가나·한자 = 모르는 제어의 인자(원문 그대로 둔 것) → 원래 코드 {c:XXX} 로(원문 쪽도 같은 글자만 같은 꼴로 비교)
            jp = sorted({ch for ch in TOKS.sub('', t) if re.match(r'[぀-ヿ一-鿿]', ch) and ch not in insert.PUN})
            for ch in jp:
                codes = [k for k, v in insert.tbl.DEC.items() if v == ch]
                if len(codes) != 1:
                    err.append('%s 글자 %s 코드가 %d개' % (rid, ch, len(codes))); break
                t = t.replace(ch, '{c:%03X}' % codes[0]); src = src.replace(ch, '{c:%03X}' % codes[0])
            nl = nl_of(src) if auto else None                   # 자동 접기는 줄 수가 원문보다 적을 수 있다 → 줄바꿈 토큰은 비교에서 뺌
            if [x for x in TOKS.findall(src) if x != nl] != [x for x in TOKS.findall(t) if x != nl] and not t == '':
                err.append('%s 토큰 %s ≠ 원문 %s' % (rid, TOKS.findall(t), TOKS.findall(src))); continue
            if (src.count('\\n') != t.count('\\n')) and nl_of(src) == '\\n' and not t.startswith('~'):
                pass                                            # 메뉴 목록은 \n 개수 자유(줄 수 ≤ 원문은 아래 예산이 막음)
            idx[rid][5] = t
    for p, (head, rows) in tabs.items():
        save(p, head, rows)
    # 예산 검사 — 실제 빌드 글자표
    occ = json.load(open(os.path.join(ROOT, 'work', 'extract.json'), encoding='utf-8'))
    tr = insert.load_ko(os.path.join(ROOT, 'work', 'ko'))
    import itemdesc
    tr.update(itemdesc.load_ko())
    cmap = insert.charmap(tr, occ)
    room = {}; in8 = set()
    for f in ('ovl.json', 'ovl2.json'):
        for o in json.load(open(os.path.join(ROOT, 'work', f), encoding='utf-8')):
            room[o['id']] = min(room.get(o['id'], 1 << 30), o['end'] - o['start'])
            if any(o['file'] == nf and a <= o['start'] < z for nf, a, z in insert.NAME8):
                in8.add(o['id'])
    cmap8 = insert.cmap8_of([tr[i] for i in in8 if i in tr])
    over = []
    for rid, r in idx.items():
        if rid not in tr or rid not in room:
            continue
        try:
            n = len(insert.encode(tr[rid], cmap8 if rid in in8 else cmap, nl=5))
        except SystemExit as e:
            err.append('%s %s' % (rid, e)); continue
        if n > room[rid]:
            over.append('%s 예산 %d < %d  %s' % (rid, room[rid], n, tr[rid]))
    done = sum(1 for r in tabs[p2][1] if r[5])
    print('W 번역 %d/%d · 한글 %d자' % (done, len(tabs[p2][1]), len(cmap)))
    for e in err:
        print('⛔', e)
    for o in over:
        print('⚠예산', o)
    return 1 if err or over else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
