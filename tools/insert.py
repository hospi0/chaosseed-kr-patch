# -*- coding: utf-8 -*-
r"""번역 삽입·빌드 (2026-10-01)
  입력: work/ko/*.tsv «번역» 열(빈 줄 = 원문 그대로) · 출현 위치 work/extract.json(tools/extract.py)
  ① 글자표: 번역에 쓰인 한글 음절을 쓰임 바이트 수(글자 수 × 출현 수) 순으로
     1바이트 칸(가나 0x6E‥0xFF + 한자 0x5D‥0x67 = 157칸) → 나머지는 2바이트 칸(0x100‥0x10F·0x11A‥0x68D, 0x2FF «…» 제외).
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
BLANK = ' '   # 빈 2바이트 칸(반각 공백과 같은 12px) — build() 가 남는 2바이트 칸 하나를 비워 PUN 에 넣는다
# ★0x2FF 는 «전각 공백»이 아니라 «…»(원문 «ひてん　せき» = 비천…석) — 공백 대신 쓰면 «함정…설치»(실기 2026-10-02)
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
TOK = re.compile(r'\\n|\{p\}|\{(?:07|0D|10|11):[0-9A-F]{2}:[0-9A-F]{2}\}|\{17:[0-9A-F]{2}\}|\{0[345]:[0-9A-F]{2}\}|\{0[0-9A-F]\}|\{c:[0-9A-F]{3}\}|\{[A-Z0-9]{1,3}\}|\{2:[가-힣]\}')
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
            elif s.startswith('{2:'):                                 # 같은 글자의 2바이트 사본 칸(ALIAS2 — 건너뛰기 바이트 수 맞춤용)
                out += code_bytes(cmap[s])
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
PREFER1 = set('케브레스메이혼아레크린클릭') | set('다음턴엔뭔가일어날듯') | set('술함') | set('느')   # 느: 옵션 «느림» 3 B(한글2 탭에서 빠져 2바이트가 됨, 2026-10-02) · 술·함(W00451 함정 설치): 필드 메뉴 «선술»이 3바이트면 남는 자리가 홀수 → 공백 1칸이 줄을 넓혀 틀 밖으로 삐짐(2026-10-02 실기)
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
# ★추출에서 빠진 CS.BIN 오버레이 문구(앞 {10:xx:yy} 뒤 01 에 막힘 — 실기 2026-10-03 «란그용테겠정공?»·«LR겠데프−뭐돼겠») — (위치, 원문 바이트, 번역), 원래 길이 그대로
MISSED = [(0x7D3BA, '9398796fea7a7322', ('할까요?', '하시겠어요?', '좋습니까?', '괜찮을까요?')),          # 아이템 버리기 «よろしいですか?»
          (0x7D7CC, '9398796fea7a7322', ('할까요?', '하시겠어요?', '좋습니까?', '괜찮을까요?')),          # 굴삭 중지
          (0x7E85B, '9398796fea7a7322', ('할까요?', '하시겠어요?', '좋습니까?', '괜찮을까요?')),
          (0x7D95E, '454beaf8cd2d180c1883193e', ('LR로 그룹 변경', 'LR로 그룹 바꾸기', 'LR 그룹 변경', 'LR로 그룹변경')),   # 시점 고르기 아래 안내
          (0x7BEE9, '1a8d1947', ('확률', '명중'))]   # 함정 설치 목록 «確率»(W00473 은 앞 66 1B 01 오독으로 잡음 처리 — 실기 «덩떨»)
SKILLS = ['호구회전', '대화염', '천뢰파', '폭축파', '사석광', '백련천궁', '대호읍', '여의', '봉황천무', '연축연탄', '천지호뢰',
          '강구회천', '열화포', '암뢰파', '화염탄', '사석효', '백려천궁', '대절규', '돌봉', '공작연무', '염습연탄', '천신강래', '멸시선']
#   ↑ 豪球回転·大火炎·天雷破·爆縮破·邪石光·百連天弓·大号泣·如意·鳳凰天舞·練縮連弾·天地豪雷·剛球回天·烈火砲·闇雷破·火炎弾·蛇石効·白麗天弓·大絶叫·突棒·孔雀連舞·炎襲連弾·天神降来·滅視線
NUMCMD = re.compile(r'\{1[12]:[0-9A-F]{2}:[0-9A-F]{2}\}')     # 숫자 명령(인자 3개 — 토큰은 2개만 보여 뒤 토큰이 어긋남)
PADLOG = []                                                       # 남는 자리 채움 방식 전수(빌드 때 work/padlog.tsv)
# ★u16 오프셋 표로 찾는 이름 구역 — NUL 을 세지 않으므로 남는 자리는 00(공백이면 «만두  가 있어»처럼 빈칸이 낀다)
#   아이템 이름 0x749F0‥0x752AF ← 오프셋 표 0x747F0(256개, 함수 0x0605A06C · 2026-10-02 실기 «보물상자엔 가 있어»)
OFFNAMES = [('0.BIN', 0x749F0, 0x752B0),   # 아이템 이름 ← 오프셋 표 0x747F0
            ('0.BIN', 0x70232, 0x7088D)]   # 강화 이름 148개 ← 오프셋 표 0x700B2(192개, FFFF 없음) — 공백 채움이 창 밖 베이지 띠(실기 2026-10-02 «선단생산력LV1»)
POOL8 = [0x93, 0xF1, 0xF2, 0xF3, 0xF4, 0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFB, 0xFC, 0x6F, 0x92, 0x95, 0x96, 0x97, 0x98]
# ★2026-10-02 실기(HUD 적 이름 «마▼스크»): 이름은 HUD 에서 셀 묶음 2(0x2F00+코드)로도 찍힌다 → 묶음 1·2 둘 다 빈 칸만(안전 순).
#   묶음 2 의 0x6C‥0xA4 는 창 테두리 고리 그림, 0xF0 은 HUD 이름 줄 공백(«테테테») — 제외. 0x6F·0x92·0x95‥ 는 묶음 2 그림이지만 스테이트에서 안 쓰임(위험 칸 — 빈도 낮은 음절부터).
# ★CSFR 8×8 셀 0x60‥0xFF 중 «완전히 빈» 칸 37개만(나머지는 에너지·仙丹·速さ·知力·修復·EXP·ヘルプ·HP 등 UI 그림 — 2026-10-02 실기에서 덮어써 깨짐)


POOL8_ONE = [c for c in POOL8 if c in ONE]                     # 8×8 빈 셀이면서 본문 1바이트 칸(35)


def name8_pins(tr):
    """★8×8 이름표 음절(선 56 밖)을 본문 글자표에서도 «같은 코드»에 고정 → 12px·8×8 어디서 찍혀도 같은 글자
       (실기 2026-10-02: 상태 창 «노사» 의 «노» 가 8×8 전용 코드 = 12px 글꼴의 ■ 로 찍힘)"""
    import nameent
    ovl = json.load(open(os.path.join(ROOT, 'work', 'ovl.json'), encoding='utf-8'))
    ovl += json.load(open(os.path.join(ROOT, 'work', 'ovl2.json'), encoding='utf-8'))
    texts = [tr[o['id']] for o in ovl if o['id'] in tr and any(o['file'] == nf and a <= o['start'] < z for nf, a, z in NAME8)]
    from collections import Counter
    cnt = Counter(ch for t in texts for ch in t if is_ko(ch) and ch not in nameent.SEON_CODE)
    need = sorted(cnt, key=lambda ch: (-cnt[ch], ch))                 # 자주 쓰는 음절 = 안전한 칸(POOL8 앞쪽)
    if len(need) > len(POOL8_ONE):
        raise SystemExit('⛔8×8 이름표 음절 %d > 칸 %d' % (len(need), len(POOL8_ONE)))
    return {ch: POOL8_ONE[i] for i, ch in enumerate(need)}


def cmap8_of(pins):
    import nameent
    m = dict(nameent.SEON_CODE)
    m.update(pins)
    return m


def alias_text(t, k, cmap):
    """번역문의 1바이트 한글 음절을 끝에서부터 k개 «{2:글자}»(같은 글자의 2바이트 사본 칸)로 → (새 글, 못 채운 수).
       토큰({c:} 원래 바이트·명령 인자) 안은 건드리지 않는다."""
    ps = pieces(t)
    one = set(ONE)
    idx = [i for i, (kind, s) in enumerate(ps) if kind == 'ch' and ((is_ko(s) and cmap.get(s) in one and '{2:%s}' % s in cmap) or s == ' ')]
    #   ★이미 있는 반각 공백(0x20, 이 글꼴에선 12px 한 칸)도 전각 공백(2바이트, 같은 한 칸)으로 — 화면 변화 없음
    pick = set(idx[::-1][:k])
    out = ''.join(((BLANK if s == ' ' else '{2:%s}' % s) if i in pick else s) for i, (kind, s) in enumerate(ps))
    return out, k - len(pick)


def encode_elig(t, cmap):
    """번역 → (바이트, 사본 칸으로 바꿔도 되는 바이트 위치 집합) — 1바이트 한글 음절·반각 공백(번역문 글자)만, 토큰 바이트는 제외"""
    out = bytearray(); elig = set(); one = set(ONE)
    for kind, s in pieces(t):
        b = encode(s, cmap, nl=5)
        if kind == 'ch' and len(b) == 1 and ((is_ko(s) and cmap.get(s) in one) or s == ' '):
            elig.add(len(out))
        out += b
    return bytes(out), elig


def fill_text(t, k, cmap):
    """남는 k바이트를 «화면에 칸을 안 먹는» 것만으로: 사본 칸(1B, 1바이트 음절 수만큼) + 같은 위치 명령 되풀이(3B) + 같은 색 명령 되풀이(2B).
       되풀이는 그 명령 바로 앞에 붙여 효과 없음. 공백 없이 못 맞추면 None."""
    _, avail = alias_text(t, 10 ** 6, cmap)
    avail = 10 ** 6 - avail
    p10 = re.search(r'\{10:[0-9A-F]{2}:[0-9A-F]{2}\}', t)
    p04 = list(re.finditer(r'\{04:[0-9A-F]{2}\}', t))
    for r3 in range(0, (k // 3 + 1) if p10 else 1):
        for r2 in range(0, ((k - 3 * r3) // 2 + 1) if p04 else 1):
            a1 = k - 3 * r3 - 2 * r2
            if 0 <= a1 <= avail:
                t2, krem = alias_text(t, a1, cmap)
                assert krem == 0
                if r2:                                           # 마지막 색 명령 앞에(같은 색을 연달아 — 효과 없음)
                    m = list(re.finditer(r'\{04:[0-9A-F]{2}\}', t2))[-1]
                    t2 = t2[:m.start()] + m.group() * r2 + t2[m.start():]
                if r3:
                    m = re.search(r'\{10:[0-9A-F]{2}:[0-9A-F]{2}\}', t2)
                    t2 = t2[:m.start()] + m.group() * r3 + t2[m.start():]
                return t2
    return None


def is_ko(ch):
    return '가' <= ch <= '힣' or 'ㄱ' <= ch <= 'ㅎ'


def charmap(tr, occ, pins=None):
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
    for ch in sorted(PREFER1):                                           # 제자리 예산이 빠듯한 오버레이 문자열(인물 이름 표 등) → 1바이트 칸 우선
        weight[ch] += 10 ** 8
    for v in nameent.UI.values():                                # 이름판 문구는 원래 자리(짧음)에 들어가야 → 1바이트 칸 우선
        for ch in v:
            if is_ko(ch):
                weight[ch] += 10 ** 9
    fixed = dict(nameent.SEON_CODE)
    fixed.update(pins or {})
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
    tr.update({'SK%02d' % i: n for i, n in enumerate(SKILLS)})   # 기술 이름(직접 패치) — 글자표에 포함
    tr.update({'MS%02d' % i: m[2][0] for i, m in enumerate(MISSED)})
    pins = name8_pins(tr)
    cmap = charmap(tr, occ, pins)
    print('번역 %d줄 · 글자표 한글 %d자(칸 %d)' % (len(tr), len(cmap), len(ONE) + len(TWO)))
    # ① 글꼴: 가나·한자 칸 전부 → 쓰는 칸은 한글, 안 쓰는 칸은 빈칸
    exe = bytearray(open(os.path.join(ROOT, 'work', 'disc', '0.BIN'), 'rb').read())
    F = bdf.Font(GAL)
    # ★{2:글자} = 같은 글자의 2바이트 사본 칸 — {0D:xx:yy}(조건부 건너뛰기, 바이트 수) 구간의 길이를 원문과 맞출 때
    #   (실기 2026-10-02: 6항목 필드 메뉴 «謎窟» 3B → «미굴» 2B 라 잠긴 줄을 1B 더 건너뛰어 «기타»가 «타»)
    free2 = [c for c in TWO if c not in set(cmap.values())]
    PUN[BLANK] = blank2 = free2.pop()                            # 빈 글자 칸(글리프 0) — 반각 공백의 2바이트판
    for t in sorted({m for v in tr.values() for m in re.findall(r'\{2:[가-힣]\}', v)}):
        cmap[t] = free2.pop()
    # ★모든 1바이트 음절에 2바이트 사본 칸 — 남는 자리 채움을 공백 대신 «글자를 2바이트로»(화면 변화 없음, layout.upgrade)
    #   공백은 베이지 칸으로 칠해져 창 밖 띠·잔재가 됐다(실기 2026-10-02 여러 화면)
    UP = {}
    one_set = set(ONE)
    for ch in sorted(ch for ch in list(cmap) if len(ch) == 1 and is_ko(ch) and cmap[ch] in one_set):
        t = '{2:%s}' % ch
        if t not in cmap:
            if not free2:
                break
            cmap[t] = free2.pop()
        UP[cmap[ch]] = code_bytes(cmap[t])
    UP[0x20] = code_bytes(blank2)                                   # 반각 공백 → 빈 2바이트 칸(같은 12px 한 칸, +1바이트)
    print('2바이트 사본 칸 %d개(남는 2바이트 칸 %d)' % (len(UP), len(free2)))
    inv = {c: (ch[3] if ch.startswith('{2:') else ch) for ch, c in cmap.items()}
    for c in ONE + TWO:
        o = font.OFF + (c - 0x20) * 21
        if c in inv:
            exe[o:o + 21] = glyph(F, inv[c])
        elif not keep:
            exe[o:o + 21] = bytes(21)                      # --keep(시험용)이면 안 쓰는 칸은 원래 글자 유지
    ob = font.OFF + (blank2 - 0x20) * 21; exe[ob:ob + 21] = bytes(21)
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
    cmap8 = cmap8_of(pins)
    # ★기본·무작위 선수 이름(12px·8×8 양쪽에 찍힘)은 8×8 코드표 음절만 — 아니면 HUD·상태 창에서 깨진다
    bad8 = ['%s %s' % (i, tr[i]) for i in tr if re.fullmatch(r'W\d{5}', i)
            and (427 <= int(i[1:]) <= 449 or 1124 <= int(i[1:]) <= 1289) and any(is_ko(ch) and ch not in cmap8 for ch in tr[i])]
    if bad8:
        raise SystemExit('⛔8×8 로 못 찍는 음절이 든 선수 이름 %d개\n' % len(bad8) + '\n'.join(bad8))
    # ★NUL 로 이어진 짧은 문자열 목록(설정값 説明/会話/警告 · 速い/普通/遅い 등)은 게임이 NUL 을 세어 N번째를 찾는다
    #   → 남는 자리를 00 으로 채우면 빈 항목이 끼어 값이 사라짐(실기 2026-10-02 옵션 화면) — 이런 칸은 공백으로 채움
    _st = {(o['file'], o['start']) for o in ovl_all}
    _en = {(o['file'], o['end']) for o in ovl_all}
    _orig = {}
    import layout
    EXACT = set()                                                # 0D 가 든 문자열 + 바로 뒤(간격 ≤ 4 B) 문자열 = 건너뛰기 착지 구역
    for f in {o['file'] for o in ovl_all}:
        es = sorted((o for o in ovl_all if o['file'] == f), key=lambda o: o['start'])
        for i, o in enumerate(es):
            if '{0D:' in o['text']:
                EXACT.add((f, o['start']))
                if i + 1 < len(es) and es[i + 1]['start'] - o['end'] <= 4:
                    EXACT.add((f, es[i + 1]['start']))
    # ★«ー» 는 원문에서 1바이트 0x2D(빼기 기호)와 2바이트 0x116(장음) 둘 다 — 표가 둘 다 «ー» 로 풀어 빌더가 전부 0x116 으로 썼다.
    #   숫자 기호 명령 {13} 뒤의 2바이트 글자는 그리기를 끊어 강화 창 비교 칸(−·가로줄·화살표·숫자)과 예/아니오가 통째로 사라졌다(실기 2026-10-02, W00523).
    #   → 원문 바이트에 0x116 이 없는 오버레이 문자열의 «ー» 는 0x2D 로.
    n2d = 0
    for o in ovl_all:
        if o['id'] in tr and 'ー' in tr[o['id']] and 'ー' in o['text']:
            ob = _orig.setdefault(o['file'], open(os.path.join(ROOT, 'work', 'disc', o['file']), 'rb').read())[o['start']:o['end']]
            if b'\x2d' in ob and b'\x18\x16' not in ob:
                tr[o['id']] = tr[o['id']].replace('ー', '{c:02D}'); n2d += 1
    print('«ー» → 1바이트 0x2D: %d줄' % n2d)
    for o in ovl_all:
        if o['file'] == '0.BIN' and any(a <= o['start'] < z for a, z, *_ in itemdesc.TABLES):
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
        offnamed0 = any(f == nf and a <= o['start'] < z for nf, a, z in OFFNAMES)
        if not in8 and not offnamed0:
            # ★기본 = 제어 명령을 원래 절대 위치에 고정(tools/layout.py) — 조각마다 2바이트 사본 칸 → 색 명령 되풀이 → 공백 순
            #   (실기 2026-10-02: 남는 자리를 몰면 강화 크래시(0D)·풍수 창 «금은/1단» 깨짐·창 밖 베이지 띠)
            if f not in _orig:
                _orig[f] = open(os.path.join(ROOT, 'work', 'disc', f), 'rb').read()
            new_e, elig = encode_elig(tr[o['id']], cmap)            # 번역문 글자에서 나온 바이트만 늘림({c:} 원래 바이트·인자 보호)
            assert new_e == new, (o['id'], '조각별 인코딩 불일치')
            res, why = layout.exact(new, _orig[f], o['start'], o['end'], UP, elig)
            nsp = (res.count(b' ') - new.count(b' ')) if res is not None else 0
            if res is not None and nsp <= 0:
                bins[f][o['start']:o['end']] = res; nov += 1
                PADLOG.append((o['id'], '명령 위치 고정'))
                continue
            if (f, o['start']) not in EXACT and len(new) < room:
                # ★조각별로 못 채우면(공백이 들면) 문자열 전체의 1바이트 음절을 사본 칸으로 — 공백은 «칸»을 먹어 줄이 길어지고
                #   뒤에 그린 줄이 그 칸을 덮는다(실기 2026-10-02 탭 «풍수»→«풍적부»: «방» 조각 공백 2칸) · 베이지 띠도 공백 탓
                t_up = fill_text(tr[o['id']], room - len(new), cmap)
                if t_up is not None:
                    up_b = encode(t_up, cmap, nl=5)
                    assert len(up_b) == room, (o['id'], len(up_b), room)
                    bins[f][o['start']:o['end']] = up_b; nov += 1
                    PADLOG.append((o['id'], '사본칸·명령 되풀이 %d(명령 위치는 원본과 다를 수 있음)' % (room - len(new))))
                    continue
            if res is not None:
                bins[f][o['start']:o['end']] = res; nov += 1
                PADLOG.append((o['id'], '명령 위치 고정 ⚠공백 %d' % nsp))
                continue
            if (f, o['start']) in EXACT:
                over.append('%s %s:%X 위치 고정 실패: %s  %s' % (o['id'], f, o['start'], why, tr[o['id']])); continue
            PADLOG.append((o['id'], '⚠위치 고정 못 함(%s) — 아래 방식' % why))
        if len(new) < room and not in8 and not offnamed0:
            t_up, krem = alias_text(tr[o['id']], room - len(new), cmap)
            if krem == 0:                                        # ★남는 자리 전부를 2바이트 사본 칸으로 — 공백·명령 되풀이 없이 끝
                up_b = encode(t_up, cmap, nl=5)
                assert len(up_b) == room, (o['id'], len(up_b), room)
                bins[f][o['start']:o['end']] = up_b; nov += 1
                PADLOG.append((o['id'], '사본칸×%d' % (room - len(new))))
                continue
            PADLOG.append((o['id'], '⚠사본칸 모자람 %d — 아래 방식' % krem))
        if o['term'] != 0 and len(new) < room:
            # ★끝이 01/02(다음 문자열로 이어짐)면 남는 자리를 끝에 채우면 그 공백이 이어진 줄에 찍힌다(실기: 필드 메뉴 빈 줄)
            #   → 첫 줄 끝(줄바꿈 앞)에 공백을 넣어 안 보이게, 줄바꿈이 없으면 끝 토큰들 앞에
            t = tr[o['id']]; pad = ' ' * (room - len(new))
            m4 = re.search(r'(?:^|\\n)(\{04:[0-9A-Fa-f]{2}\})', t)   # ★줄 머리의 {04:xx}(메뉴 항목 색)만 — 줄 안쪽 04 는 11/12 숫자 명령(3인자: 11 02 80 04)의 꼬리일 수 있음(실기 2026-10-02 상태 창 숫자 사라짐)
            m = re.search(r'(\{[^}]*\})*$', t)
            p10 = list(re.finditer(r'\{10:[0-9A-F]{2}:[0-9A-F]{2}\}', t))
            if p10 and not m4 and not NUMCMD.search(t):
                # ★위치 명령으로 칸을 놓는 화면(W00593 용혈로 창 등): 공백은 베이지 칸으로 칠해져 창 밖·면 끝을 넘어 왼쪽까지 띠가 생김
                #   (실기 2026-10-02) → 첫 {10:x:y} 를 그 앞에 되풀이(3바이트, 효과 없음), 나머지 1‥2바이트만 둘째 위치 명령 앞 공백
                k = room - len(new); a = p10[0]
                t = t[:a.start()] + a.group() * (k // 3) + t[a.start():]
                if k % 3:
                    p10 = list(re.finditer(r'\{10:[0-9A-F]{2}:[0-9A-F]{2}\}', t))
                    b = p10[k // 3 + 1] if len(p10) > k // 3 + 1 else None
                    at = b.start() if b else m.start()
                    t = t[:at] + ' ' * (k % 3) + t[at:]
                new = encode(t, cmap8 if in8 else cmap, nl=5)
                assert len(new) == room, (o['id'], len(new), room)
                PADLOG.append((o['id'], '위치명령×%d+공백%d' % (k // 3, k % 3)))
                bins[f][o['start']:o['end']] = new; nov += 1
                continue
            PADLOG.append((o['id'], ('색×%d' % ((room - len(new)) // 2)) if m4 else '공백%d' % (room - len(new))))
            if m4:                                               # ★메뉴 항목(«仙術{04:00}{09}»): 공백은 선택 막대에 칠해져 틀 밖으로 삐짐(실기 2026-10-02) → 같은 {04:xx} 를 되풀이(2바이트씩), 홀수만 공백 1
                # ★{04:xx} = 글자 색. 되풀이는 «원래 그 {04:xx} 바로 앞»에 — 첫 줄 끝에 넣으면 색이 일찍 바뀐다
                #   (실기 2026-10-02: 상태 창 W01312 «체력» 뒤 {04:80}×5 → 기력부터 노란 글자·투명 바탕, 숫자 검정)
                k = room - len(new)
                t = t[:m4.start(1)] + m4.group(1) * (k // 2) + t[m4.start(1):]
                pad = ' ' * (k % 2)
                if k % 2:
                    print('⚠️홀수 채움(공백 1칸) %s %s:%X — 줄이 넓어질 수 있음' % (o['id'], f, o['start']))
                m = re.search(r'(\{[^}]*\})*$', t)
            # ★«{15}\n» = 색 명령 15 + 인자 05(회색) — 줄바꿈이 아니다. 그 사이에 공백을 넣으면 색 인자가 공백이 되고
            #   05 가 진짜 줄바꿈이 된다(실기 2026-10-02 W00607 결정/중지 선택지: «결정»이 한 줄 아래로)
            nl = re.search(r'(?<!\{15\})\\n', t)
            t2 = t[:nl.start()] + pad + t[nl.start():] if nl else t[:m.start()] + pad + t[m.start():]
            new = encode(t2, cmap8 if in8 else cmap, nl=5)
            assert len(new) == room, (o['id'], len(new), room)
        fill = bytes(1)
        # ★원문에서 끝 NUL 바로 뒤가 0 이 아니면(값 목록·코드 속 문자열) 공백으로 — 00 채움은 NUL 세기·명령 위치를 밀어냄(실기 2026-10-02 옵션 값 사라짐)
        #   뒤가 0 이면(원래도 00 여백) 00 그대로 — 공백은 베이지 칸으로 칠해져 화면 밖까지 띠가 생김(실기 2026-10-02 W00695)
        if f not in _orig:
            _orig[f] = open(os.path.join(ROOT, 'work', 'disc', f), 'rb').read()
        offnamed = any(f == nf and a <= o['start'] < z for nf, a, z in OFFNAMES)
        if o['term'] == 0 and not in8 and not offnamed and o['end'] + 1 < len(_orig[f]) and _orig[f][o['end'] + 1] != 0:
            fill = b' '
            # ★끝이 위치 명령({10:xx:yy})이면 그건 «다음 문자열»의 자리 — 공백을 그 뒤에 두면 다음 글이 밀린다
            #   (실기 2026-10-02 W00598 «…사용{10:0F:11}» + 공백 4 → 선택지 «방»이 밀려 «통로»와 겹침) → 끝 토큰들 앞에 채움
            mt = re.search(r'(\{[^}]*\})*$', tr[o['id']])
            if NUMCMD.search(tr[o['id']]) and len(new) < room:
                # ★숫자 명령 11/12(인자 3개)의 셋째 인자·뒤 05·00 을 추출기가 «{10:05:00}» 같은 토큰으로 읽는다 — 끝 토큰은 믿을 수 없다
                #   (실기 2026-10-02 W00633 풍수 창: 끝 NUL 뒤 공백 4 → 명령으로 실행돼 «-1» 찌꺼기) → 첫 줄 끝(창 안쪽)에만 채움
                t = tr[o['id']]; k = room - len(new)
                nl1 = re.search(r'(?<!\{15\})\\n', t)
                at = nl1.start() if nl1 else NUMCMD.search(t).start()   # 한 줄짜리면 첫 숫자 명령 앞(숫자가 k칸 밀림 — ⚠목록)
                t = t[:at] + ' ' * k + t[at:]
                new = encode(t, cmap, nl=5); assert len(new) == room, (o['id'], len(new), room)
                PADLOG.append((o['id'], ('숫자명령 문자열 첫줄끝공백%d' if nl1 else '⚠숫자명령 한 줄 — 숫자 앞 공백%d') % k))
            elif mt.start() < len(tr[o['id']]) and len(new) < room:
                t = tr[o['id']]; k = room - len(new)
                l10 = list(re.finditer(r'\{10:[0-9A-F]{2}:[0-9A-F]{2}\}', t[mt.start():]))
                if l10:                                          # 끝 위치 명령을 되풀이(3바이트, 효과 없음) + 나머지만 공백
                    a = l10[-1]; at = mt.start() + a.start()
                    t = t[:at] + ' ' * (k % 3) + a.group() * (k // 3) + t[at:]
                    PADLOG.append((o['id'], '끝위치명령×%d+공백%d' % (k // 3, k % 3)))
                else:
                    t = t[:mt.start()] + ' ' * k + t[mt.start():]
                    PADLOG.append((o['id'], '끝토큰앞공백%d' % k))
                new = encode(t, cmap, nl=5)
                assert len(new) == room, (o['id'], len(new), room)
        if len(new) < room:
            PADLOG.append((o['id'], ('끝공백%d' if fill == b' ' else '끝00 %d') % (room - len(new))))
        bins[f][o['start']:o['end']] = new + fill * (room - len(new)); nov += 1
    import skipcheck                                             # ★0D(건너뛰기) 명령은 원래 자리·바이트 그대로여야 — 아니면 빌드 실패
    for o in ovl_all:
        f = o['file']
        if f not in bins or (f, o['start']) not in EXACT:
            continue
        A = _orig.setdefault(f, open(os.path.join(ROOT, 'work', 'disc', f), 'rb').read())
        for pa, c, a in skipcheck.walk(A, o['start'], o['end']):
            if c == 0x0D and bytes(bins[f][pa:pa + 3]) != A[pa:pa + 3]:
                over.append('%s %s:%X 0D 명령이 자리에서 밀림' % (o['id'], f, pa))
    with open(os.path.join(ROOT, 'work', 'padlog.tsv'), 'w', encoding='utf-8') as fp:
        fp.write(''.join('%s\t%s\t%s\n' % (i, how, tr.get(i, '')) for i, how in PADLOG))
    if over:
        raise SystemExit('⛔오버레이 문자열 예산 초과 %d곳 — 줄일 것\n' % len(over) + '\n'.join(sorted(set(over))))
    # ★제목 메뉴 2자 항목(한자+반각 공백+한자, 5 B) — 추출기가 놓침(실기 2026-10-02 «열 깊 / 냥 잎»)
    if 'LOAD.BIN' not in bins:
        bins['LOAD.BIN'] = bytearray(open(os.path.join(ROOT, 'work', 'disc', 'LOAD.BIN'), 'rb').read())
    for off, orig, ko in ((0x11E5C, '18e6201a53', '삭 제'), (0x11E62, '1920201b52', '신 규')):
        assert bytes(_orig.setdefault('LOAD.BIN', open(os.path.join(ROOT, 'work', 'disc', 'LOAD.BIN'), 'rb').read())[off:off + 6]) == bytes.fromhex(orig) + b'\0', hex(off)
        new = encode(ko, cmap, nl=5)
        assert len(new) <= 5, (ko, len(new))
        bins['LOAD.BIN'][off:off + 5] = new + b' ' * (5 - len(new))
    # ★방 정보 줄(CS.BIN 0x7C6A5, W00502 — 숫자 명령 11 이 인자 3개라 추출 토큰이 엉켜 번역 칸을 비워 둠): 라벨 6개 = 2바이트 글자 2개(4 B) 고정 자리
    #   → 그 4 B 만 같은 2바이트 한글로(1바이트 음절은 {2:} 사본 칸). 안 고치면 한자 칸 자리의 한글이 찍혀 «꾀좁·열남·병끓·덕쁘»(실기 2026-10-02)
    def two(ch):
        c = cmap['{2:%s}' % ch] if cmap[ch] < 0x100 else cmap[ch]
        return code_bytes(c)
    cs0 = _orig.setdefault('CS.BIN', open(os.path.join(ROOT, 'work', 'disc', 'CS.BIN'), 'rb').read())
    if 'CS.BIN' not in bins:
        bins['CS.BIN'] = bytearray(cs0)
    for off, orig, ko in ((0x7C6A5, '1a841a85', '축적'), (0x7C6B2, '18c0188e', '생산'), (0x7C6C0, '18e61a43', '소비'),
                          (0x7C6CE, '19cd19ce', '내구'), (0x7C6DF, '1a841a85', '축적'), (0x7C6EB, '18c0188e', '생산')):
        assert bytes(cs0[off:off + 4]) == bytes.fromhex(orig) and bytes(bins['CS.BIN'][off:off + 4]) == bytes.fromhex(orig), hex(off)
        bins['CS.BIN'][off:off + 4] = two(ko[0]) + two(ko[1])
    # ★소환 화면 선수 정보 라벨 «技»(CS.BIN 0x7AC30, W01308 «0D 01 | 19 4F 技 | 05 武器 | 05 防具») — 추출이 0D 를 인자 2개로 읽어 19 를 먹고 4F 를 «V» 로 남김
    #   → 19 4F 가 그대로 남아 한글 글자표의 0x24F(«밑»)가 찍힘(실기 2026-10-03). 2 B 자리에 «기술»(1바이트 음절 둘, 아니면 2바이트 한 칸 «기»)
    sk = encode('기술', cmap)
    if len(sk) != 2:
        sk = two('기')
    assert bytes(cs0[0x7AC2E:0x7AC32]) == bytes.fromhex('0d01194f') and bytes(bins['CS.BIN'][0x7AC30:0x7AC32]) == b'\x19\x4f'
    bins['CS.BIN'][0x7AC30:0x7AC32] = sk
    # ★LOAD.BIN 0x105D8‥0x105F0 = 타이틀 옵션 포인터 표(W00729 앞부분, «レクチャー» 앞) — 1바이트라도 밀리면 옵션 진입 크래시(실기 2026-10-03)
    assert bytes(bins['LOAD.BIN'][0x105D8:0x105F0]) == _orig.setdefault('LOAD.BIN', open(os.path.join(ROOT, 'work', 'disc', 'LOAD.BIN'), 'rb').read())[0x105D8:0x105F0], 'LOAD 포인터 표 0x105D8 바뀜'
    for off, orig, cands in MISSED:                              # 빠진 문구 — 원래 길이 그대로(후보 중 1바이트 음절 {2:} 사본 칸·빈 2바이트 칸으로 «정확히» 맞는 첫 것)
        room = len(orig) // 2
        assert bytes(cs0[off:off + room]) == bytes.fromhex(orig) and bytes(bins['CS.BIN'][off:off + room]) == bytes.fromhex(orig), hex(off)
        for ko in cands:
            if any(ch not in cmap for ch in ko if is_ko(ch)):
                continue
            new = encode(ko, cmap, nl=5)
            if len(new) < room:
                t2, rem = alias_text(ko, room - len(new), cmap)
                new = encode(t2, cmap, nl=5)
            while len(new) + 2 <= room:
                new += code_bytes(PUN[BLANK])
            if len(new) == room:
                break
        assert len(new) == room, ('빠진 문구 길이', cands, len(new), room)
        print('빠진 문구 %X: %s' % (off, ko))
        bins['CS.BIN'][off:off + room] = new
    # ★기술 이름 23개(0.BIN 0x78D05‥, «없음» 0x78D02 다음부터 NUL 로 이어진 목록 — 포인터 없이 순번으로 찾음, 추출에서 빠졌었다)
    #   상태 창 «기 쾌둿작멀»(실기 2026-10-02) → 한자음. 각 항목 원래 바이트 그대로(1바이트 음절은 {2:} 사본 칸, 그래도 남으면 빈 2바이트 칸)
    o0 = _orig.setdefault('0.BIN', open(os.path.join(ROOT, 'work', 'disc', '0.BIN'), 'rb').read())
    q = 0x78D05
    for ko in SKILLS:
        e = o0.index(b'\0', q); room = e - q
        new = encode(ko, cmap, nl=5)
        if len(new) < room:
            t2, rem = alias_text(ko, room - len(new), cmap)
            new = encode(t2, cmap, nl=5)
        while len(new) + 2 <= room:
            new += code_bytes(PUN[BLANK])
        assert len(new) == room, ('기술 이름 길이', ko, len(new), room)
        bins['0.BIN'][q:e] = new
        q = e + 1
    assert o0[q - 1] == 0 and q == 0x78DB6, hex(q)
    for pre, n, room in itemdesc.apply(bins['0.BIN'], tr, cmap, encode):   # 아이템(I)·선수(M) 설명 표 통째로 다시 짜기
        print('설명 표 %s %d B / 칸 %d B' % (pre, n, room))
    # ④ 메뉴 8×8 셀 라벨(tools/gfx_menu.py — HELP.BIN 0x1E524)
    import gfx_menu, nameent
    if 'HELP.BIN' not in bins:
        bins['HELP.BIN'] = bytearray(open(os.path.join(ROOT, 'work', 'disc', 'HELP.BIN'), 'rb').read())
    gfx_menu.apply(bins['HELP.BIN'])
    gfx_menu.put_hud2(bins['HELP.BIN'], gfx_menu.HUD2_HELP)          # HUD «仙丹» 날 사본
    gfx_menu.put_names_hud2(bins['HELP.BIN'], gfx_menu.HUD2_HELP, {c: ch for ch, c in cmap8.items()})   # HUD 이름 줄 8×8(셀 묶음 2)
    bins['CSFR.DAT'] = gfx_menu.apply_csfr(bytearray(open(os.path.join(ROOT, 'work', 'disc', 'CSFR.DAT'), 'rb').read()),
                                           extra={c: ch for ch, c in cmap8.items()})  # 선 56 + 8×8 이름표 전용 셀
    gfx_menu.apply_hud2_csfr(bins['CSFR.DAT'], {c: ch for ch, c in cmap8.items()})                   # HUD «仙丹»(셀 묶음 2, 0x1B8CA 압축 블록)
    import kd_ctl                                                # 조작설명·특수조작설명 화면(KD00.BIN 비압축 640×480 8bpp — tools/kd_ctl.py)
    bins.update({k: bytearray(v) for k, v in kd_ctl.build().items()})
    import gfx_map                                               # 지도 «現在地»·방 종류 라벨 10개(CSST.DAT 0x11921 블록 — tools/gfx_map.py)
    bins['CSST.DAT'] = gfx_map.apply(bytearray(open(os.path.join(ROOT, 'work', 'disc', 'CSST.DAT'), 'rb').read()))
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
    import title_logo                                            # 타이틀 로고 한글(LOAD.BIN 0x4B544 그림 + 0x90798 팔레트)
    n, room = title_logo.apply(bins['LOAD.BIN'])
    print('타이틀 그림: %d B / %d B' % (n, room))
    # 본문 글꼴 두 칸(24×14) 아이콘: 0x58·0x59 = 필드 메뉴 ヘルプ → 「도움말」 · 0x5A·0x5B = 상태 창 エネルギ → 「에너지」(갈무리7, 8px 세 자)
    G7 = bdf.Font(os.path.join(os.path.dirname(GAL), 'Galmuri7.bdf'))
    for word, c0 in (('도움말', 0x58), ('에너지', 0x5A)):
        rows = [0] * 14
        for k, ch in enumerate(word):
            pts, _ = G7.draw(ch, 0, 0)
            y0 = min(y for _, y in pts); h = max(y for _, y in pts) - y0 + 1
            for x, y in pts:
                X, Y = k * 8 + x, y - y0 + (14 - h) // 2
                if 0 <= X < 24 and 0 <= Y < 14:
                    rows[Y] |= 1 << (23 - X)
        for half, c in ((0, c0), (1, c0 + 1)):
            rr = [(r >> (12 * (1 - half))) & 0xFFF for r in rows]
            o = font.OFF + (c - 0x20) * 21
            exe[o:o + 21] = b''.join(bytes([rr[2 * i] & 0xFF, rr[2 * i + 1] & 0xFF, (rr[2 * i] >> 8) | ((rr[2 * i + 1] >> 8) << 4)]) for i in range(7))
    # 소환 목록 등급 표시(한 칸 12×14에 두 글자 위아래): 0x6A 太仙 → 태/선 · 0x6B 小仙 → 소/선(갈무리7, 위 0‥6줄·아래 7‥13줄, 가로 가운데)
    for word, c in (('태선', 0x6A), ('소선', 0x6B)):
        rows = [0] * 14
        for k, ch in enumerate(word):
            pts, _ = G7.draw(ch, 0, 0)
            y1 = max(y for _, y in pts); w = max(x for x, _ in pts) + 1
            for x, y in pts:
                X, Y = x + (11 - w + 1) // 2, y - y1 + 6 + 7 * k
                if 0 <= X < 12 and 0 <= Y < 14:
                    rows[Y] |= 0x800 >> X
        o = font.OFF + (c - 0x20) * 21
        exe[o:o + 21] = b''.join(bytes([rows[2 * i] & 0xFF, rows[2 * i + 1] & 0xFF, (rows[2 * i] >> 8) | ((rows[2 * i + 1] >> 8) << 4)]) for i in range(7))
    # 상태 화면 「技 なし」 등 오버레이 추출에서 빠진 なし(2바이트 82 79) → 없음
    nashi = encode('없음', cmap)
    if len(nashi) != 2:
        nashi = encode('무', cmap) + b' '
    for f, a in (('CS.BIN', 0x7F032), ('0.BIN', 0x78D02)):
        if f not in bins:
            bins[f] = bytearray(open(os.path.join(ROOT, 'work', 'disc', f), 'rb').read())
        if bytes(bins[f][a:a + 2]) == bytes([0x82, 0x79]):
            bins[f][a:a + 2] = nashi
        else:
            print('⚠️なし 자리 %s:%X 이미 바뀜 — 건너뜀' % (f, a))
    print('이름판: 전체 탭 %d행 · 문구 %d+%d' % (nb, nu, nu2))
    print('오버레이 문자열 %d자리 · 메뉴 라벨 %d · 바뀐 파일 %s' % (nov, len(gfx_menu.LABELS), sorted(bins)))
    files = {f: bytes(b) for f, b in bins.items()}
    files.update({a + '.ADT': d for a, d in arcs.items()})
    # ★0.BIN 시나리오 파일 표(12B: 파일 번호·크기·적재 함수 0x060243BC) — 게임은 이 «크기»만큼 Low RAM 힙(0x06011AFC, 쌓기식)에서 잡는다.
    #   커진 SSS*.ADT 를 원래 크기 버퍼에 읽어 뒤 블록·힙 머리를 덮음 → 도움말 등에서 할당 중 주소 오류(2026-10-02 실기 크래시)
    osz = {e[0]: e[2] for e in disc.Disc().walk() if e[0] in files}
    nfix = 0
    for a in range(0x16B00, 0x16D00, 4):
        if exe[a + 8:a + 12] != bytes.fromhex('060243BC'):
            continue
        size = struct.unpack_from('>I', exe, a + 4)[0]
        for f, n0 in osz.items():
            if f.startswith('SSS') and n0 == size and len(files[f]) != n0:
                struct.pack_into('>I', exe, a + 4, len(files[f])); nfix += 1
                break
    grow = max(len(files[f]) - n0 for f, n0 in osz.items() if f.startswith('SSS'))
    print('SSS 크기 표 %d칸 고침 · 최대 증가 %d B (필드 힙 여유 약 91,000 B)' % (nfix, grow))
    if grow > 60000:
        raise SystemExit('⛔SSS 파일 증가 %d B — 힙 여유를 넘을 수 있음' % grow)
    files['0.BIN'] = bytes(exe)
    import glob                                                  # 동영상 자막(tools/moviesub.py → work/kr/*.AVI, TrueMotion 1 다시 부호화 — 커지면 iso.patch 가 끝으로 옮김)
    for p in sorted(glob.glob(os.path.join(ROOT, 'work', 'kr', '*.AVI'))):
        files[os.path.basename(p)] = open(p, 'rb').read()
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
