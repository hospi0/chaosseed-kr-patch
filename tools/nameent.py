# -*- coding: utf-8 -*-
r"""이름 입력판 한글화 (2026-10-01)
  ① 주인공·히로인 입력판 = LOAD.BIN(적재 0x0602D000) — 행마다 포인터: 히라가나 5행 0xFB94 · 가타카나 5행 0xFBA8 · 영숫자 5행 0xFBBC
     · 한자 198행 0xFBD0. 행 = 14칸(1·2바이트 글자, 빈칸 0x20) + 00. 표 몸통 0x11074‥ (앞 0x11000‥0x11073 은 탁점 변환표 — 그대로).
     → 히라가나 탭 «자주1»(가~히 70자) · 가타카나 탭 «자주2»(70자) · 영숫자 그대로 · 한자 탭 «전체»(글자표의 모든 한글 음절, 초성별, 첫 칸 = 초성)
  ② 선수(召喚獣·竜) 이름판 = NAMEENT.BIN(적재 0x060EC000) — 가타카나 5행(0x2B0D, 행 14 B 고정) → SEON 56자(가·고·구·기 줄 × 14)
     이름은 상태 창 등에서 8×8 셀(문자 0x2E00 + 1바이트 코드)로도 찍히므로 SEON 은 1바이트 코드 0xA5‥0xDC 에 고정하고,
     12px 글꼴과 8×8 셀(CSFR.DAT 블록, gfx_menu) 양쪽에 그린다.
  ③ 탭·버튼 문구(두 파일 모두 제자리): ひらがな→자주1 · カタカナ→자주2 · 英数字→영숫자 · 漢字→전체 · 前がめん→앞화면 · もどす→지움 · スペース→띄움 · 決定→결정
"""
import struct

SEON = list('가나다라마바사아자차카타파하고노도로모보소오조초코토포호구누두루무부수우주추쿠투푸후기니디리미비시이지치키티피히')
SEON_CODE = {ch: 0xA5 + i for i, ch in enumerate(SEON)}            # 0xA5‥0xDC
FAV1 = SEON[:14] + list('거너더러머버서어저처커터퍼허') + SEON[14:28] + SEON[28:42] + SEON[42:56]
FAV2 = list('개내대래매배새애재채캐태패해게네데레메베세에제체케테페헤그느드르므브스으즈츠크트프흐강난단란만반산안잔찬칸탄판한'
            '경영명성정준진현혜희민빈린윤')
CHO = 'ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ'
COMMON = list('가강건경고광구국규균근기길김나남노다대덕도동두라란래려련령로룡류리린림마만명모목무문미민박배백범보복봉부빈'
              '사산상서석선설성세소송수숙순슬승시식신실아안애양어언엄여연영예오옥온완용우욱운원월위유윤율은을음의이인일임'
              '자장재전정제조종주준중지진찬창채천철청초춘충치태택하한해혁현형혜호홍화환효훈휘희')
LOAD_BASE, NAME_BASE = 0x0602D000, 0x060EC000
UI = {'ひらがな': '자주1', 'カタカナ': '자주2', '英数字': '영숫자', '漢字': '전체', '前がめん': '앞화면', 'もどす': '지움',
      'スペース': '띄움', '決定': '결정', '主人公の名前': '주인공 이름', '主人公の呼び名': '주인공 호칭', 'ヒロインの名前': '히로인 이름',
      'ヒロインの呼び名': '히로인 호칭', '召喚獣の呼び名': '소환수 이름', '竜の呼び名': '용 이름'}


def required():
    """글자표에 꼭 들어가야 할 글자(이름판용) — SEON 은 코드 고정"""
    ui = {ch for v in UI.values() for ch in v if '가' <= ch <= '힣'}
    return set(SEON) | set(FAV1) | set(FAV2) | set(COMMON) | set(CHO) | ui


def cho_of(ch):
    return (ord(ch) - 0xAC00) // 588


def row_bytes(cells, enc1):
    cells = (cells + [' '] * 14)[:14]
    return b''.join(enc1(c) for c in cells) + b'\x00'


def patch_load(L, cmap, code_bytes, enc_ui):
    """LOAD.BIN(bytearray) 이름판 표·탭 문구"""
    def enc1(ch):
        if ch == ' ':
            return b' '
        return code_bytes(cmap[ch])
    lo = 0x11074
    ptr = lambda o: struct.unpack_from('>I', L, o)[0] - LOAD_BASE
    kanji = [ptr(0xFBD0 + 4 * i) for i in range(198)]
    hi = max(kanji); hi = L.index(b'\x00', hi) + 1                      # 표 몸통 끝
    alnum = [L[ptr(0xFBBC + 4 * i):L.index(b'\x00', ptr(0xFBBC + 4 * i)) + 1] for i in range(5)]
    rows_fav1 = [row_bytes(FAV1[i * 14:(i + 1) * 14], enc1) for i in range(5)]
    rows_fav2 = [row_bytes(FAV2[i * 14:(i + 1) * 14], enc1) for i in range(5)]
    hang = sorted(ch for ch in cmap if '가' <= ch <= '힣')
    big = []
    for k in range(19):
        grp = [ch for ch in hang if cho_of(ch) == k]
        for i in range(0, len(grp), 13):
            big.append(row_bytes([CHO[k] if i == 0 else ' '] + grp[i:i + 13], enc1))
    if len(big) > 198:
        raise SystemExit('⛔이름판 전체 탭 %d행 > 198' % len(big))
    big += [row_bytes([], enc1)] * (198 - len(big))
    body = bytearray(); offs = {}
    for name, rows in (('fav1', rows_fav1), ('fav2', rows_fav2), ('alnum', alnum), ('big', big)):
        offs[name] = []
        for r in rows:
            offs[name].append(lo + len(body)); body += r
    if lo + len(body) > hi:
        raise SystemExit('⛔이름판 표 %d B > 자리 %d B' % (len(body), hi - lo))
    L[lo:hi] = body + bytes(hi - lo - len(body))
    for base, name in ((0xFB94, 'fav1'), (0xFBA8, 'fav2'), (0xFBBC, 'alnum'), (0xFBD0, 'big')):
        for i, o in enumerate(offs[name]):
            struct.pack_into('>I', L, base + 4 * i, LOAD_BASE + o)
    n = enc_ui(L, 0x10DF0, 0x10E54)
    return len([r for r in big if r.strip(b' \x00')]), n


def patch_nameent(N, code_bytes, enc_ui):
    """NAMEENT.BIN(bytearray) 가타카나 5행 → SEON(코드 0xA5‥0xDC 고정) + 부호 줄"""
    ptr = lambda o: struct.unpack_from('>I', N, o)[0] - NAME_BASE
    rows = [SEON[i * 14:(i + 1) * 14] for i in range(4)]
    for i in range(5):
        o = ptr(0x2648 + 4 * i)
        if i < 4:
            N[o:o + 14] = bytes(SEON_CODE[ch] for ch in rows[i])
        else:
            N[o:o + 14] = bytes([0x21, 0x22, 0x23, 0x24, 0x29, 0x2A, 0x28, 0x2E, 0x2F]) + b' ' * 5   # ! ? 。 、 ( ) + : /
    return enc_ui(N, 0x2AC8, 0x2B0D)
