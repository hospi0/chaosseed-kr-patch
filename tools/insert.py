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
import disc, font, lz, tbl, iso

GAL = r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri11.bdf'
OUT = os.path.join(ROOT, 'work', 'out', os.path.basename(disc.ROM))
F_DIR = r'F:\hospi\roms\ss roms\Senkutsu Katsuryu Taisen - Chaos Seed (Japan) (Disc 1) (Game Disc) (Rev B) (21M)'
BUF = 0x060DAB80 - 0x060D877C
ONE = list(range(0x6E, 0x100)) + list(range(0x5D, 0x68))
KEEP = {0x2FF, 0x2DE, 0x2DF, 0x5F7, 0x248, 0x249, 0x24A}            # 전각 공백·「」·○·반각 조각 그림
TWO = list(range(0x100, 0x110)) + [c for c in range(0x11A, tbl.LAST + 1) if c not in KEEP]
# 한글 밖 글자 → 원래 글꼴 코드
PUN = {' ': 0x20, '　': 0x2FF, '!': 0x21, '！': 0x21, '?': 0x22, '？': 0x22, '。': 0x23, '、': 0x24, ',': 0x110, '，': 0x110,
       '.': 0x111, '．': 0x111, '・': 0x112, '&': 0x113, '＆': 0x113, '%': 0x114, '％': 0x114, '々': 0x115, 'ー': 0x116,
       '-': 0x116, '‥': 0x117, '…': 0x117, '~': 0x118, '～': 0x118, '〜': 0x118, '♡': 0x119, '♥': 0x119, '―': 0x27,
       '+': 0x28, '＋': 0x28, '(': 0x29, '（': 0x29, ')': 0x2A, '）': 0x2A, '『': 0x2B, '』': 0x2C, ':': 0x2E, '：': 0x2E,
       '/': 0x2F, '／': 0x2F, '「': 0x2DE, '」': 0x2DF, '○': 0x5F7, '゛': 0x25, '゜': 0x26, '◀': 0x68, '▶': 0x69, '■': 0x6C}
for i, ch in enumerate('0123456789'):
    PUN[ch] = 0x30 + i; PUN[chr(0xFF10 + i)] = 0x30 + i
for i in range(26):
    PUN[chr(0x41 + i)] = 0x3A + i; PUN[chr(0xFF21 + i)] = 0x3A + i
SPECIAL = {'{A}': 0x54, '{B}': 0x55, '{X}': 0x56, '{Y}': 0x57, '{58}': 0x58, '{59}': 0x59, '{5A}': 0x5A, '{5B}': 0x5B,
           '{LV}': 0x5C, '{6A}': 0x6A, '{6B}': 0x6B, '{248}': 0x248, '{249}': 0x249, '{24A}': 0x24A}
TOK = re.compile(r'\\n|\{p\}|\{0[345]:[0-9A-F]{2}\}|\{0[0-9A-F]\}|\{c:[0-9A-F]{3}\}|\{[A-Z0-9]{1,3}\}')
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
                out += bytes([int(s[1:3], 16), int(s[4:6], 16)])
            else:
                out.append(int(s[1:3], 16))
        elif '가' <= s <= '힣':
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


def charmap(tr, occ):
    weight = collections.Counter()
    nocc = collections.Counter(o['id'] for o in occ)
    for rid, t in tr.items():
        for kind, s in pieces(t):
            if kind == 'ch' and '가' <= s <= '힣':
                weight[s] += nocc.get(rid, 1)
    order = [ch for ch, _ in weight.most_common()]
    if len(order) > len(ONE) + len(TWO):
        raise SystemExit('⛔한글 음절 %d > 칸 %d' % (len(order), len(ONE) + len(TWO)))
    slots = ONE + TWO
    return {ch: slots[i] for i, ch in enumerate(order)}


def build(kodir, install=False, keep=False):
    sys.stdout.reconfigure(encoding='utf-8')
    occ = json.load(open(os.path.join(ROOT, 'work', 'extract.json'), encoding='utf-8'))
    tr = load_ko(kodir)
    cmap = charmap(tr, occ)
    print('번역 %d줄 · 한글 음절 %d (1바이트 %d)' % (len(tr), len(cmap), min(len(cmap), len(ONE))))
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
        u = bytearray(lz.decompress(d, offs[item] + 1)[0]) if d[offs[item]] == 0x34 else bytearray(d[offs[item] + 1:offs[item + 1]])
        tail = bytearray()
        for o in sorted(os_, key=lambda x: x['start']):
            a, e = o['start'], o['end']
            new = b'\x01' + encode(tr[o['id']], cmap) + bytes([o['term']])
            if len(new) == e - a + 1:
                u[a:e + 1] = new; nin += 1
            else:
                at = len(u) + len(tail)
                u[a:a + 3] = b'\x63' + struct.pack('<H', at)
                tail += new + b'\x63' + struct.pack('<H', e + 1); nmv += 1
        u += tail
        if len(u) > BUF:
            raise SystemExit('⛔%s/%03d 풀린 크기 %d > 버퍼 %d' % (arc, item, len(u), BUF))
        if d[offs[item]] == 0x34:
            new_item = b'\x34' + lz.compress(bytes(u))
        else:
            new_item = d[offs[item]:offs[item] + 1] + bytes(u)
        arcs[arc] = lz.replace_item(d, item, new_item)
        chk = lz.archive(arcs[arc])
        assert (lz.decompress(arcs[arc], chk[item] + 1)[0] if new_item[0] == 0x34 else arcs[arc][chk[item] + 1:chk[item + 1]]) == bytes(u)
    print('문장 제자리 %d · 끝으로 옮김 %d · 바뀐 묶음 %s' % (nin, nmv, sorted(arcs)))
    # ③ 오버레이 문자열(work/ovl.json, ID V…) — 제자리·원래 바이트 이하, 남는 곳은 끝이 00 이면 00, 아니면 공백(0x20)
    bins = {'0.BIN': exe}; nov = 0
    for o in json.load(open(os.path.join(ROOT, 'work', 'ovl.json'), encoding='utf-8')):
        if o['id'] not in tr:
            continue
        f = o['file']
        if f not in bins:
            bins[f] = bytearray(open(os.path.join(ROOT, 'work', 'disc', f), 'rb').read())
        new = encode(tr[o['id']], cmap, nl=5)
        room = o['end'] - o['start']
        if len(new) > room:
            raise SystemExit('⛔%s %s:%X 예산 %d B < %d B — 줄일 것' % (o['id'], f, o['start'], room, len(new)))
        bins[f][o['start']:o['end']] = new + bytes([0 if o['term'] == 0 else 0x20]) * (room - len(new)); nov += 1
    # ④ 메뉴 8×8 셀 라벨(tools/gfx_menu.py — HELP.BIN 0x1E524)
    import gfx_menu
    if 'HELP.BIN' not in bins:
        bins['HELP.BIN'] = bytearray(open(os.path.join(ROOT, 'work', 'disc', 'HELP.BIN'), 'rb').read())
    gfx_menu.apply(bins['HELP.BIN'])
    bins['CSFR.DAT'] = gfx_menu.apply_csfr(bytearray(open(os.path.join(ROOT, 'work', 'disc', 'CSFR.DAT'), 'rb').read()))
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
