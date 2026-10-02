# -*- coding: utf-8 -*-
r"""이름 입력판 한글화 (2026-10-01)
  ① 주인공·히로인 입력판 = LOAD.BIN(적재 0x0602D000) — 행마다 포인터: 히라가나 5행 0xFB94 · 가타카나 5행 0xFBA8 · 영숫자 5행 0xFBBC
     · 한자 130행 0xFBD0(★뒤 포인터는 다른 표). 행 = 정확히 14칸 + 00(2바이트 글자 둘째 바이트가 00 일 수 있어 00 찾기로 끊으면 안 됨). 행 = 14칸(1·2바이트 글자, 빈칸 0x20) + 00. 행들 사이에 다른 데이터(옵션 화면 문구 등)가 섞여 있으므로 «원래 행 바이트 범위»에만 다시 채운다.
     → 히라가나 탭 «한글1»(ㅏㅓㅗㅜㅣ 줄 70자) · 가타카나 탭 «한글2»(= SEON 56자 — 호칭은 8×8 로 찍힘) · 영숫자 그대로 · 한자 탭 «전체»(글자표의 모든 한글 음절, 초성별, 첫 칸 = 초성)
  ② 선수(召喚獣·竜) 이름판 = NAMEENT.BIN(적재 0x060EC000) — 가타카나 5행(0x2B0D, 행 14 B 고정) → SEON 56자(가·고·구·기 줄 × 14)
     이름은 상태 창 등에서 8×8 셀(문자 0x2E00 + 1바이트 코드)로도 찍히므로 SEON 은 1바이트 코드 0xA5‥0xDC 에 고정하고,
     12px 글꼴과 8×8 셀(CSFR.DAT 블록, gfx_menu) 양쪽에 그린다.
  ③ 탭·버튼 문구(두 파일 모두 제자리): ひらがな→한글1 · カタカナ→한글2 · 英数字→영숫자 · 漢字→전체 · 前がめん→앞화면 · もどす→지움 · スペース→띄움 · 決定→결정
"""
import struct

# ★8×8 로 찍히는 이름(주인공 호칭·선수 이름) = 1바이트 코드 0xA5‥0xDC 56칸뿐 → 그 56자(ㅏ·ㅣ·ㅡ·ㅜ 줄 × 14자음, 사용자 «하스피» 2026-10-01)
# ★2026-10-02 실기(HUD 적 이름 깨짐): 8×8 이름 음절 칸이 HUD(셀 묶음 2)와 겹쳐 모자람 → 사용자 «한글2 탭 12자 교체»:
#   가·티·그·느·드·므·으·흐·두·수·주·푸 를 빼고 적 이름 음절 헤·레·코·로·도·토·샤·류·오·와·노·소 (기본·무작위 이름은 푸→후 등으로 고침)
SEON = list('헤나다라마바사아자차카타파하기니디리미비시이지치키레피히코로도르토브스샤즈츠크트프류구누오루무부와우노추쿠투소후')
SEON_CODE = {ch: 0xA5 + i for i, ch in enumerate(SEON)}            # 0xA5‥0xDC
FAV1 = list('가나다라마바사아자차카타파하거너더러머버서어저처커터퍼허고노도로모보소오조초코토포호구누두루무부수우주추쿠투푸후'
            '기니디리미비시이지치키티피히')                         # 한글1(이름 — 12px 라 2바이트 글자도 됨)
FAV2 = SEON                                                          # 한글2(호칭 — 8×8 이라 SEON 만)
CHO = 'ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ'
COMMON = list('가강건경고광구국규균근기길김나남노다대덕도동두라란래려련령로룡류리린림마만명모목무문미민박배백범보복봉부빈'
              '사산상서석선설성세소송수숙순슬승시식신실아안애양어언엄여연영예오옥온완용우욱운원월위유윤율은을음의이인일임'
              '자장재전정제조종주준중지진찬창채천철청초춘충치태택하한해혁현형혜호홍화환효훈휘희')
LOAD_BASE, NAME_BASE = 0x0602D000, 0x060EC000
UI = {'ひらがな': '한글1', 'カタカナ': '한글2', '英数字': '영숫자', '漢字': '전체', '前がめん': '앞화면', 'もどす': '지움',
      'スペース': '띄움', '決定': '결정', '主人公の名前': '주인공 이름', '主人公の呼び名': '주인공 호칭', 'ヒロインの名前': '히로인 이름',
      'ヒロインの呼び名': '히로인 호칭', '召喚獣の呼び名': '소환수 이름', '竜の呼び名': '용 이름'}


PUNCT_ROW = bytes([0x21, 0x22, 0x23, 0x24, 0x29, 0x2A, 0x28, 0x2E, 0x2F]) + b' ' * 5 + bytes(1)   # ! ? 。 、 ( ) + : / (1바이트)


def required():
    """글자표에 꼭 들어가야 할 글자(이름판용) — SEON 은 코드 고정"""
    ui = {ch for v in UI.values() for ch in v if '가' <= ch <= '힣'}
    return set(SEON) | set(FAV1) | set(FAV2) | set(COMMON) | set(CHO) | ui


def cho_of(ch):
    return (ord(ch) - 0xAC00) // 588


def row_bytes(cells, enc1):
    cells = (cells + [' '] * 14)[:14]
    return b''.join(enc1(c) for c in cells) + b'\x00'


KANJI_ROWS = 130        # ★한자 탭 = 포인터 0xFBD0 부터 130개(뒤는 다른 표: 0x130‥ 잡데이터 · なぞ窟 설명 · 제목 — 2026-10-01 크래시 원인)


def row_end(L, o):
    """행 = 14칸(0x18‥0x1D 는 2바이트 — 둘째 바이트가 00 일 수 있음) + 00 → 끝(다음 바이트) 위치"""
    n = 0
    while n < 14:
        o += 2 if 0x18 <= L[o] <= 0x1D else 1
        n += 1
    assert L[o] == 0, ('행 끝이 00 아님', hex(o))
    return o + 1


def patch_load(L, cmap, code_bytes, enc_ui):
    """LOAD.BIN(bytearray) 이름판 표·탭 문구 — ★원래 행들이 차지한 바이트 범위에만 다시 채움(사이에 다른 데이터가 섞여 있다)"""
    def enc1(ch):
        if ch == ' ':
            return b' '
        return code_bytes(cmap[ch])
    ptr = lambda o: struct.unpack_from('>I', L, o)[0] - LOAD_BASE
    tabs = ((0xFB94, 5), (0xFBA8, 5), (0xFBBC, 5), (0xFBD0, KANJI_ROWS))
    spans = sorted({(ptr(base + 4 * i), row_end(L, ptr(base + 4 * i))) for base, n in tabs for i in range(n)})
    blocks = []                                              # 이어진 범위 합치기
    for a, b in spans:
        if blocks and a <= blocks[-1][1]:
            blocks[-1][1] = max(blocks[-1][1], b)
        else:
            blocks.append([a, b])
    alnum = [bytes(L[ptr(0xFBBC + 4 * i):row_end(L, ptr(0xFBBC + 4 * i))]) for i in range(5)]
    rows_fav1 = [row_bytes(FAV1[i * 14:(i + 1) * 14], enc1) for i in range(5)]
    rows_fav2 = [row_bytes(FAV2[i * 14:(i + 1) * 14], enc1) for i in range(4)] + [PUNCT_ROW]
    assert all(cmap[ch] == SEON_CODE[ch] for ch in FAV2)
    hang = sorted(ch for ch in cmap if '가' <= ch <= '힣')
    big = []
    for k in range(19):
        grp = [ch for ch in hang if cho_of(ch) == k]
        for i in range(0, len(grp), 13):
            big.append(row_bytes([CHO[k] if i == 0 else ' '] + grp[i:i + 13], enc1))
    if len(big) > KANJI_ROWS:
        raise SystemExit('⛔이름판 전체 탭 %d행 > %d' % (len(big), KANJI_ROWS))
    big += [row_bytes([], enc1)] * (KANJI_ROWS - len(big))
    old = {(a, b): bytes(L[a:b]) for a, b in blocks}
    for a, b in blocks:                                      # 원래 행 범위만 비움(00 — 아무 행도 안 가리킴)
        L[a:b] = bytes(b - a)
    bi, cur = 0, blocks[0][0]
    offs = {}
    for name, rows in (('fav1', rows_fav1), ('fav2', rows_fav2), ('alnum', alnum), ('big', big)):
        offs[name] = []
        for r in rows:
            while cur + len(r) > blocks[bi][1]:
                bi += 1
                if bi >= len(blocks):
                    raise SystemExit('⛔이름판 표가 원래 자리(%d B)를 넘음' % sum(b - a for a, b in blocks))
                cur = blocks[bi][0]
            L[cur:cur + len(r)] = r; offs[name].append(cur); cur += len(r)
    for (base, n), name in zip(tabs, ('fav1', 'fav2', 'alnum', 'big')):
        for i, o in enumerate(offs[name]):
            struct.pack_into('>I', L, base + 4 * i, LOAD_BASE + o)
    n = enc_ui(L, 0x10DF0, 0x10E7F)              # 탭·버튼·이름판 제목(…ヒロインの呼び名·召喚獣の呼び名·竜の呼び名) — 0x10E7F 부터는 백업 경고문
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
            N[o:o + 14] = PUNCT_ROW[:14]
    return enc_ui(N, 0x2AC8, 0x2B0D)
