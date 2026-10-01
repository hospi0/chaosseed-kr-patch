# -*- coding: utf-8 -*-
r"""번역 삽입·빌드 (2026-10-01)
  입력: work/ko/*.tsv «번역» 열(빈 줄 = 원문 그대로) · 출현 위치 work/extract.json(tools/extract.py)
  ① 글자표: 번역에 쓰인 한글 음절을 쓰임 바이트 수(글자 수 × 출현 수) 순으로
     1바이트 칸(가나 0x6E‥0xFF + 한자 0x5D‥0x67 = 157칸) → 나머지는 2바이트 칸(0x100‥0x10F·0x11A‥0x68D, 0x2FF 전각 공백 제외).
     ⛔가나·한자 칸은 전부 한글로 덮어쓴다(안 남긴다) — 글리프 = 갈무리11(몸 x 0‥10 · y 1‥11), 0.BIN 글꼴 0x78F66.
  ② 문장 교체(오프셋 안 건드림): 새 바이트(01 + 글 + 끝 00|02)가 원래와 길이가 같으면 제자리,
     다르면 원래 자리 첫 3바이트를 «63 u16»(점프 → 항목 끝에 붙인 새 문장)으로 바꾸고 새 문장 뒤에 «63 u16(원래 끝+1)» 로 돌아옴.
     → 다른 점프·진입점 표는 하나도 안 움직인다(해석기가 못 닿은 구역이 있어도 안전).
  ③ 항목 재압축(lz.compress) → lz.replace_item. ⛔풀린 항목 ≤ 9,220 B(RAM 버퍼 0x060D877C‥0x060DAB80) 검사.
  ③′ 오버레이 문자열(work/ovl.json, ID V…, tools/ovl_extract.py): 제자리·원래 바이트 이하(
 = 05), 남는 곳 00|공백.
  ④ iso.patch(0.BIN + 바뀐 SSS*.ADT; 커진 파일은 디스크 끝으로 옮김) → work/out/…(Track 1).bin
  python tools/insert.py [--ko 폴더] [--install]
"""
import argparse, collections, glob, json, os, re, shutil, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, r'C:\claude\project\anearth-kr-patch\tools')
import bdf
sys.path.insert(0, HERE)
import disc, font, lz, tbl, iso, vm

GAL = r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri11.bdf'
OUT = os.path.join(ROOT, 'work', 'out', os.path.basename(disc.ROM))
F_DIR = r'F:\hospi\roms\ss roms\Senkutsu Katsuryu Taisen - Chaos Seed (Japan) (Disc 1) (Game Disc) (Rev B) (21M)'
BUF = 0x060DAB80 - 0x060D877C
ONE = list(range(0x6E, 0xFF)) + list(range(0x5D, 0x68))   # ★0xFF 제외 = 아이템 설명 표(itemdesc)의 끝 표시(원래 ゾ — 글로 안 쓰임)
KEEP = {0x2FF, 0x2DE, 0x2DF, 0x5F7, 0x248, 0x249, 0x24A, 0x66A, 0x66B, 0x66C, 0x66D}   # 전각 공백·「」·○·반각 조각 그림·㎝㎏♂♀(도움말 선수 소개)
TWO = list(range(0x100, 0x110)) + [c for c in range(0x11A, tbl.LAST + 1) if c not in KEEP]
# 한글 밖 글자 → 원래 글꼴 코드
PUN = {' ': 0x20, '　': 0x2FF, '!': 0x21, '！': 0x21, '?': 0x22, '？': 0x22, '。': 0x23, '、': 0x24, ',': 0x110, '，': 0x110,
       '.': 0x111, '．': 0x111, '・': 0x112, '&': 0x113, '＆': 0x113, '%': 0x114, '％': 0x114, '々': 0x115, 'ー': 0x116,
       '-': 0x116, '‥': 0x117, '…': 0x117, '~': 0x118, '～': 0x118, '〜': 0x118, '♡': 0x119, '♥': 0x119, '―': 0x27,
       '+': 0x28, '＋': 0x28, '(': 0x29, '（': 0x29, ')': 0x2A, '）': 0x2A, '『': 0x2B, '』': 0x2C, ':': 0x2E, '：': 0x2E,
       '/': 0x2F, '／': 0x2F, '「': 0x2DE, '」': 0x2DF, '○': 0x5F7, '゛': 0x25, '゜': 0x26, '◀': 0x68, '▶': 0x69, '■': 0x6C,
       '㎝': 0x66A, '㎏': 0x66B, '♂': 0x66C, '♀': 0x66D}
for i, ch in enumerate('0123456789'):
    PUN[ch] = 0x30 + i; PUN[chr(0xFF10 + i)] = 0x30 + i
for i in range(26):
    PUN[chr(0x41 + i)] = 0x3A + i; PUN[chr(0xFF21 + i)] = 0x3A + i
SPECIAL = {'{A}': 0x54, '{B}': 0x55, '{X}': 0x56, '{Y}': 0x57, '{58}': 0x58, '{59}': 0x59, '{5A}': 0x5A, '{5B}': 0x5B,
           '{LV}': 0x5C, '{6A}': 0x6A, '{6B}': 0x6B, '{248}': 0x248, '{249}': 0x249, '{24A}': 0x24A}
TOK = re.compile(r'\\n|\{p\}|\{(?:07|0D|10|11):[0-9A-F]{2}:[0-9A-F]{2}\}|\{17:[0-9A-F]{2}\}|\{0[345]:[0-9A-F]{2}\}|\{0[0-9A-F]\}|\{c:[0-9A-F]{3}\}|\{[A-Z0-9]{1,3}\}')
PUNCT_SP = re.compile(r'([,.!?:;)\]\'"~、。，．！？：；）］｝」』】〉》”’…‥・·～〜♪♥]) (?! )')   # «}» 는 토큰 닫는 괄호라 뺌({05:00} 뒤 띄어쓰기 보존)


def load_ko(kodir):
    tr = {}
    for p in sorted(glob.glob(os.path.join(kodir, '*.tsv'))):
        for i, line in enumerate(open(p, encoding='utf-8')):
            c = line.rstrip('\n').split('\t')
            if i == 0 or len(c) < 6 or not c[5].strip() or c[2] == '영문':
                continue
            ko = c[5]
            if ko.endswith('{00}') and c[4].endswith('{00}'):
                ko = ko[:-4]
            tr[c[0]] = PUNCT_SP.sub(r'\1', ko)
    return tr


def pieces(t):
    """번역 → [('tok', str) | ('ch', 글자)]"""
    out, i = [], 0
    for m in TOK.finditer(t):
        out += [('ch', ch) for ch in t[i:m.start()]]; out.append(('tok', m.group())); i = m.end()
    return out + [('ch', ch) for ch in t[i:]]


def code_bytes(c):
    return bytes([c]) if c < 0x100 else bytes([0x18 + (c >> 8) - 1, c & 0xFF])


def encode(t, cmap, nl=6):
    out = bytearray()
    for kind, s in pieces(t):
        if kind == 'tok':
            if s == '\\n':
                out.append(nl)
            elif s == '{p}':
                out.append(1)
            elif s in SPECIAL:
                out += code_bytes(SPECIAL[s])
            elif s.startswith('{c:'):
                out += code_bytes(int(s[3:6], 16))
            elif ':' in s:
                out += bytes(int(x, 16) for x in s[1:-1].split(':'))
            else:
                out.append(int(s[1:3], 16))
        elif is_ko(s):
            out += code_bytes(cmap[s])
        elif s in PUN:
            out += code_bytes(PUN[s])
        else:
            raise SystemExit('⛔글꼴에 없는 글자 %r in %r' % (s, t))
    return bytes(out)


def glyph(F, ch):
    pts, _ = F.draw(ch, 0, 0)
    rows = [0] * 14
    for x, y in pts:
        Y = y - 2
        if 0 <= x < 12 and 0 <= Y < 14:
            rows[Y] |= 0x800 >> x
    out = bytearray()
    for i in range(7):
        a, b = rows[2 * i], rows[2 * i + 1]
        out += bytes([a & 0xFF, b & 0xFF, (a >> 8) | ((b >> 8) << 4)])
    return bytes(out)


# 1바이트 칸 우선 음절 — 오버레이 제자리 예산이 1~2바이트 모자란 줄(빌드가 «예산 초과»로 알려 주면 여기 보탠다)
PREFER1 = set('케브레스메이혼아레크린클릭') | set('다음턴엔뭔가일어날듯')
# 8×8 글자(셀 0x2E00 + 1바이트 코드 — CSFR.DAT)로 찍히는 이름표(0.BIN 0x778EF‥, 원문은 탁점 분리 가나 1자 = 1바이트)용 음절
#   = 선(SEON 56, 코드 고정) + ㅗ·ㅓ·ㅔ 줄 42 + 받침 23 → 1바이트 칸 우선 · gfx_menu.apply_csfr 가 이 코드들의 8×8 셀을 그린다(2026-10-02)
_CON = 'ㄱㄴㄷㄹㅁㅂㅅㅇㅈㅊㅋㅌㅍㅎ'
EIGHT = ([chr(0xAC00 + 'ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ'.index(c) * 588 + 'ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ'.index(v) * 28)
          for v in 'ㅗㅓㅔ' for c in _CON] + list('칸왕란몬류젠텐첸샤유탄워펜적인헌위닌본료와야교'))
# ★2026-10-02 고침: EIGHT 를 본문 1바이트 칸에 올리면 대사 바이트가 늘어 SSS1/323 이 RAM 버퍼를 넘음
#   → 8×8 전용 이름표(NAME8 구역)는 «8×8 전용 코드표»(cmap8)로 따로 인코딩: 선 56자는 고정 코드, 나머지는 POOL8 코드에
#     8×8 셀만 그린다(본문 12px 글꼴의 같은 코드 글자와 무관 — 이 표는 8×8 로만 찍힌다).
#   12px·8×8 양쪽에 찍히는 선수 이름(기본·무작위 이름)은 선 56자로만 쓴다.
NAME8 = [('0.BIN', 0x778EF, 0x77B73)]
POOL8 = [c for c in range(0x6E, 0x100) if not 0xA5 <= c <= 0xDC]


def cmap8_of(texts):
    import nameent
    need = sorted({ch for t in texts for ch in t if is_ko(ch) and ch not in nameent.SEON_CODE})
    if len(need) > len(POOL8):
        raise SystemExit('⛔8×8 이름표 음절 %d > 칸 %d' % (len(need), len(POOL8)))
    m = dict(nameent.SEON_CODE)
    m.update({ch: POOL8[i] for i, ch in enumerate(need)})
    return m


def is_ko(ch):
    return '가' <= ch <= '힣' or 'ㄱ' <= ch <= 'ㅎ'


def charmap(tr, occ):
    """쓰임 바이트순 → 1바이트 칸부터. ★이름판(nameent): SEON 56자는 1바이트 0xA5‥0xDC 고정(8×8 셀과 같은 번호), 이름판 필수 음절·초성 자모도 넣음"""
    import nameent
    weight = collections.Counter()
    nocc = collections.Counter(o['id'] for o in occ)
    for rid, t in tr.items():
        for kind, s in pieces(t):
            if kind == 'ch' and is_ko(s):
                weight[s] += nocc.get(rid, 1)
    for ch in nameent.required():
        weight[ch] += 0                                          # 없으면 0 으로 들어감(맨 뒤)
    for ch in PREFER1:                                           # 제자리 예산이 빠듯한 오버레이 문자열(인물 이름 표 등) → 1바이트 칸 우선
        weight[ch] += 10 ** 8
    for v in nameent.UI.values():                                # 이름판 문구는 원래 자리(짧음)에 들어가야 → 1바이트 칸 우선
        for ch in v:
            if is_ko(ch):
                weight[ch] += 10 ** 9
    fixed = dict(nameent.SEON_CODE)
    order = [ch for ch, _ in sorted(weight.items(), key=lambda kv: -kv[1]) if ch not in fixed]
    slots = [c for c in ONE if c not in fixed.values()] + TWO
    if len(order) > len(slots):
        raise SystemExit('⛔한글 음절 %d > 칸 %d' % (len(order) + len(fixed), len(slots) + len(fixed)))
    cmap = {ch: slots[i] for i, ch in enumerate(order)}
    cmap.update(fixed)
    return cmap


def build(kodir, install=False, keep=False):
    sys.stdout.reconfigure(encoding='utf-8')
    occ = json.load(open(os.path.join(ROOT, 'work', 'extract.json'), encoding='utf-8'))
    tr = load_ko(kodir)
    import itemdesc
    tr.update(itemdesc.load_ko())                                # 아이템 설명(I###, tools/itemdesc.py) — 글자표에 포함
    cmap = charmap(tr, occ)
    print('번역 %d줄 · 글자표 한글 %d자(칸 %d)' % (len(tr), len(cmap), len(ONE) + len(TWO)))
    # ① 글꼴: 가나·한자 칸 전부 → 쓰는 칸은 한글, 안 쓰는 칸은 빈칸
    exe = bytearray(open(os.path.join(ROOT, 'work', 'disc', '0.BIN'), 'rb').read())
    F = bdf.Font(GAL)
    inv = {c: ch for ch, c in cmap.items()}
    for c in ONE + TWO:
        o = font.OFF + (c - 0x20) * 21
        if c in inv:
            exe[o:o + 21] = glyph(F, inv[c])
        elif not keep:
            exe[o:o + 21] = bytes(21)                      # --keep(시험용)이면 안 쓰는 칸은 원래 글자 유지
    # ② 문장
    by_item = collections.defaultdict(list)
    for o in occ:
        if o['id'] in tr:
            by_item[(o['arc'], o['item'])].append(o)
    arcs = {}
    nin = nmv = 0
    for (arc, item), os_ in sorted(by_item.items()):
        if arc not in arcs:
            arcs[arc] = open(os.path.join(ROOT, 'work', 'disc', arc + '.ADT'), 'rb').read()
        d = arcs[arc]; offs = lz.archive(d)
        ia, ib = lz.item_span(d, item)
        u = bytearray(lz.decompress(d, ia + 1)[0]) if d[ia] == 0x34 else bytearray(d[ia + 1:ib])
        # 점프 대상·진입점(옛 문장 자리 재활용 때 이 주소가 든 구간은 쓰지 않음)
        tx_, js_, _ = vm.walk(bytes(u))
        targets = {t for _, t in vm.entries(bytes(u))} | {vm.u16(u, j) for j in js_}
        free, pend = [], []                                      # free = 재활용 가능 [s, t) · pend = 옮길 (점프 위치, 새 바이트, 돌아갈 곳)
        for o in sorted(os_, key=lambda x: x['start']):
            a, e = o['start'], o['end']
            new = b'\x01' + encode(tr[o['id']], cmap) + bytes([o['term']])
            old = e - a + 1
            if len(new) == old:
                u[a:e + 1] = new; nin += 1
            elif len(new) + 3 <= old:                            # 짧아짐: 제자리 + 남는 곳 건너뛰기
                u[a:a + len(new)] = new
                u[a + len(new):a + len(new) + 3] = b'\x63' + struct.pack('<H', e + 1)
                free.append([a + len(new) + 3, e + 1]); nin += 1
            else:
                pend.append((a, new, e + 1)); free.append([a + 3, e + 1]); nmv += 1
        cut = []
        for s, t in free:                                        # 점프 대상이 든 구간은 그 앞까지만
            for x in sorted(targets):
                if s <= x < t:
                    t = x; break
            if t - s >= 4:
                cut.append([s, t])
        tail = bytearray()
        for a, new, back in sorted(pend, key=lambda p: -len(p[1])):
            need = len(new) + 3
            fit = [r for r in cut if r[1] - r[0] >= need]
            if fit:
                r = min(fit, key=lambda r: r[1] - r[0]); at = r[0]
                u[at:at + need] = new + b'\x63' + struct.pack('<H', back); r[0] += need
            else:
                at = len(u) + len(tail)
                tail += new + b'\x63' + struct.pack('<H', back)
            u[a:a + 3] = b'\x63' + struct.pack('<H', at)
        u += tail
        if len(u) > BUF:
            raise SystemExit('⛔%s/%03d 풀린 크기 %d > 버퍼 %d' % (arc, item, len(u), BUF))
        if d[ia] == 0x34:
            new_item = b'\x34' + lz.compress(bytes(u))
        else:
            new_item = d[ia:ia + 1] + bytes(u)
        arcs[arc] = lz.replace_item(d, item, new_item)
        chk = lz.archive(arcs[arc])
        na, nb = lz.item_span(arcs[arc], item)
        back_ = lz.decompress(arcs[arc], na + 1)[0] if new_item[0] == 0x34 else arcs[arc][na + 1:nb]
        if back_ != bytes(u):
            k_ = next((i for i in range(min(len(back_), len(u))) if back_[i] != u[i]), min(len(back_), len(u)))
            plain = lz.decompress(new_item + b'\0\0', 1)[0] if new_item[0] == 0x34 else None
            raise SystemExit('⛔%s/%03d 재압축 검산 불일치 @%X (길이 %d/%d, 단독 풀기 일치=%s, 표 %X‥%X)'
                             % (arc, item, k_, len(back_), len(u), plain == bytes(u), chk[item], chk[item + 1]))
    print('문장 제자리 %d · 끝으로 옮김 %d · 바뀐 묶음 %s' % (nin, nmv, sorted(arcs)))
    # ③ 오버레이 문자열(work/ovl.json, ID V…) — 제자리·원래 바이트 이하, 남는 곳은 끝이 00 이면 00, 아니면 공백(0x20)
    bins = {'0.BIN': exe}; nov = 0; over = []
    ovl_all = json.load(open(os.path.join(ROOT, 'work', 'ovl.json'), encoding='utf-8'))
    ovl_all += json.load(open(os.path.join(ROOT, 'work', 'ovl2.json'), encoding='utf-8'))   # W… 보충(tools/ovl2_extract.py)
    cmap8 = cmap8_of([tr[o['id']] for o in ovl_all if o['id'] in tr
                      and any(o['file'] == nf and a <= o['start'] < z for nf, a, z in NAME8)])
    for o in ovl_all:
        if o['file'] == '0.BIN' and itemdesc.START <= o['start'] < itemdesc.END:
            continue                                             # 아이템 설명 표(압축) 안 조각 — 표를 통째로 다시 짠다
        if o['id'] not in tr:
            continue
        f = o['file']
        if f not in bins:
            bins[f] = bytearray(open(os.path.join(ROOT, 'work', 'disc', f), 'rb').read())
        in8 = any(f == nf and a <= o['start'] < z for nf, a, z in NAME8)
        new = encode(tr[o['id']], cmap8 if in8 else cmap, nl=5)
        room = o['end'] - o['start']
        if len(new) > room:
            over.append('%s %s:%X 예산 %d B < %d B  %s' % (o['id'], f, o['start'], room, len(new), tr[o['id']])); continue
        bins[f][o['start']:o['end']] = new + bytes([0 if o['term'] == 0 else 0x20]) * (room - len(new)); nov += 1
    if over:
        raise SystemExit('⛔오버레이 문자열 예산 초과 %d곳 — 줄일 것\n' % len(over) + '\n'.join(sorted(set(over))))
    nd = itemdesc.apply(bins['0.BIN'], tr, cmap, encode)          # 아이템 설명 표(0.BIN 0x72BE6‥) 통째로 다시 짜기
    print('아이템 설명 표 %d B / 칸 %d B' % (nd, itemdesc.END - itemdesc.START))
    # ④ 메뉴 8×8 셀 라벨(tools/gfx_menu.py — HELP.BIN 0x1E524)
    import gfx_menu, nameent
    if 'HELP.BIN' not in bins:
        bins['HELP.BIN'] = bytearray(open(os.path.join(ROOT, 'work', 'disc', 'HELP.BIN'), 'rb').read())
    gfx_menu.apply(bins['HELP.BIN'])
    bins['CSFR.DAT'] = gfx_menu.apply_csfr(bytearray(open(os.path.join(ROOT, 'work', 'disc', 'CSFR.DAT'), 'rb').read()),
                                           extra={c: ch for ch, c in cmap8.items()})  # 선 56 + 8×8 이름표 전용 셀
    # ⑤ 이름 입력판(tools/nameent.py)
    for f in ('LOAD.BIN', 'NAMEENT.BIN'):
        if f not in bins:
            bins[f] = bytearray(open(os.path.join(ROOT, 'work', 'disc', f), 'rb').read())

    FIRST = {}
    for k, v in sorted(tbl.DEC.items()):
        FIRST.setdefault(v, k)

    def enc_ui(buf, a, b):
        n = 0
        for jp, ko in nameent.UI.items():
            src = b''.join(tbl.code_bytes(FIRST[ch]) for ch in jp) + b'\x00'   # ★같은 글자가 표에 둘이면 «앞 코드»(ー = 0x2D)
            new_b = encode(ko, cmap)
            i = buf.find(src, a, b)
            while i >= 0:
                if len(new_b) > len(src) - 1:
                    raise SystemExit('⛔이름판 문구 %s → %s 길이 %d > %d' % (jp, ko, len(new_b), len(src) - 1))
                buf[i:i + len(src)] = new_b + bytes(len(src) - len(new_b)); n += 1
                i = buf.find(src, i + 1, b)
        return n
    nb, nu = nameent.patch_load(bins['LOAD.BIN'], cmap, code_bytes, enc_ui)
    nu2 = nameent.patch_nameent(bins['NAMEENT.BIN'], code_bytes, enc_ui)
    import gfx_load                                              # 그림 글자(제목 RAM 선택·저장 화면·시나리오 간판) — LOAD.BIN 압축 블록 3개
    for blk, (n, room, _) in gfx_load.apply(bins['LOAD.BIN']).items():
        print('LOAD 그림 블록 %X: %d B / %d B' % (blk, n, room))
    print('이름판: 전체 탭 %d행 · 문구 %d+%d' % (nb, nu, nu2))
    print('오버레이 문자열 %d자리 · 메뉴 라벨 %d · 바뀐 파일 %s' % (nov, len(gfx_menu.LABELS), sorted(bins)))
    files = {f: bytes(b) for f, b in bins.items()}
    files.update({a + '.ADT': d for a, d in arcs.items()})
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    iso.patch(disc.ROM, OUT, files)
    open(os.path.join(ROOT, 'work', 'out', 'charmap.tsv'), 'w', encoding='utf-8').write(
        ''.join('%s\t%03X\n' % (ch, c) for ch, c in cmap.items()))
    print('→', OUT)
    if install:
        shutil.copyfile(OUT, os.path.join(F_DIR, os.path.basename(OUT)))
        print('F: 설치', F_DIR)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--ko', default=os.path.join(ROOT, 'work', 'ko'))
    ap.add_argument('--install', action='store_true')
    ap.add_argument('--keep', action='store_true', help='시험용: 안 쓰는 가나·한자 칸을 비우지 않음(번역 안 된 일본어가 보임)')
    a = ap.parse_args()
    build(a.ko, a.install, a.keep)
