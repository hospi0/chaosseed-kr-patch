# -*- coding: utf-8 -*-
r"""동영상 자막 굽기 — work/text/movie_sub.tsv → work/kr/<이름>.AVI (2026-10-03)
  Duck TrueMotion 1 AVI 의 영상 덩어리(00dc·00db)만 다시 짜고 소리(01wb)·순서는 그대로, idx1·★iddx(movi 앞 사본)·크기 갱신.
  덩어리 크기는 원본 avih 권장 버퍼 이하(넘으면 띠 허용 오차를 키워 다시 짠다).
  화면 = 원본 디코드(tools/tm1.py) + 자막 → 아래 띠(BAND 줄)만 tools/tm1band.py 로 다시 부호화, 위는 원본 델타 그대로(tools/tm1enc.py).
  자막이 바뀌는 순간이 NOP·빈 덩어리면 그 덩어리를 «위쪽 전부 그대로 + 띠만 다시» 인 인터 프레임으로 바꾼다.
  글씨: 나눔고딕 Bold 14px 흰색 + 검은 1px 테두리, 화면 아래 가운데, 두 줄까지(줄 간격 17px) — 블루 브레이커와 같음.
  python tools/moviesub.py check            → 줄 폭 검사만
  python tools/moviesub.py HELP01 [끝프레임] → work/kr/HELP01.AVI (+ work/movie/sub/HELP01_kr.mp4 미리보기)
  python tools/moviesub.py all              → 자막 있는 영상 전부(오래 걸림 — 순수 파이썬)
"""
import copy, os, re, struct, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import tm1, tm1enc, tm1band
from PIL import Image, ImageDraw, ImageFont

FONT = r'C:\claude\utils\font\nanum-gothic\NanumGothicBold.ttf'
PX = 14
BAND = 36                       # 두 줄(17px 간격) + 여백 — 4의 배수
LINE = 17
BUF_MAX = 41090                 # 원본 29편 avih dwSuggestedBufferSize 최대(HELP08) — 덩어리 크기 상한
AVI_DIR = os.path.join(ROOT, 'work', 'movie', 'avi')
OUT_DIR = os.path.join(ROOT, 'work', 'kr')
PUNCT = ',.!?:;)]}\'"~、。，．！？：；）］｝」』】〉》”’…‥・·～〜♪♥'


def squeeze(s):
    return re.sub('([' + re.escape(PUNCT) + ']) (?! )', r'\1', s)


def load_subs():
    subs = {}
    for l in open(os.path.join(ROOT, 'work', 'text', 'movie_sub.tsv'), encoding='utf-8').read().split('\n')[1:]:
        c = l.split('\t')
        if len(c) >= 5 and c[4].strip():
            subs.setdefault(c[0], []).append((float(c[1]), float(c[2]), squeeze(c[4].strip()).split('\\n')))
    return subs


def geometry(name):
    fr = tm1.avi_frames(os.path.join(AVI_DIR, name + '.AVI'))
    h0 = tm1.header(next(b for _, b in fr if len(b) >= 2))
    b16 = tm1.COMP[h0['compression']][0] in (1, 2)
    w = h0['xsize'] if b16 else h0['xsize'] >> 1
    disp = h0['xsize']                     # 표시 폭(24비트는 화소 2배)
    return fr, h0, b16, w, h0['ysize'], disp


def check():
    F = ImageFont.truetype(FONT, PX); d = ImageDraw.Draw(Image.new('RGB', (8, 8)))
    bad = 0
    for name, ss in load_subs().items():
        _, _, _, _, hgt, disp = geometry(name)
        for a, b, lines in ss:
            if len(lines) > 2:
                print('⛔%s %.1f 줄 %d개' % (name, a, len(lines))); bad += 1
            for ln in lines:
                wpx = d.textlength(ln, font=F)
                if wpx > disp - 12:
                    print('⛔%s %.1f 폭 %dpx > %d: %s' % (name, a, wpx, disp - 12, ln)); bad += 1
    print('줄 폭 검사 오류 %d' % bad)
    return bad


def render(base_rgb, w, hgt, disp, lines, F):
    """base_rgb(화소 w×hgt) 위에 자막 → 같은 크기 RGB 이미지(24비트는 2배 폭으로 그려 가로 평균)"""
    img = Image.frombytes('RGB', (w, hgt), base_rgb)
    if not lines:
        return img
    big = img.resize((disp, hgt), Image.NEAREST) if disp != w else img
    d = ImageDraw.Draw(big)
    y = hgt - BAND // 2 - (len(lines) - 1) * LINE // 2
    for ln in lines:
        d.text((disp / 2, y), ln, font=F, anchor='mm', fill=(255, 255, 255), stroke_width=1, stroke_fill=(0, 0, 0)); y += LINE
    return big.resize((w, hgt), Image.BOX) if disp != w else big


def target_from(img, b16, nw, hgt):
    px = img.load(); tg = []
    for y in range(hgt):
        row = []
        for x in range(nw):
            if b16:
                p0, p1 = px[2 * x, y], px[2 * x + 1, y]
                row.append(([p0[0] >> 3, p1[0] >> 3], [p0[1] >> 3, p1[1] >> 3], [p0[2] >> 3, p1[2] >> 3]))
            else:
                p = px[x, y]; row.append(([p[0]], [p[1]], [p[2]]))
        tg.append(row)
    return tg


def make_inter(template, comp):
    """NOP·빈 덩어리 자리에 넣을 인터 프레임용 Frame(위쪽 블록 전부 «그대로», 연산 없음)"""
    h = tm1.header(template)
    fr = tm1enc.Frame(); fr.h = dict(h); fr.nop = False
    alg, bw, bh, bt = tm1.COMP[comp]
    fr.b16 = alg in (1, 2); ws = 0 if fr.b16 else 1
    fr.w, fr.hgt = h['xsize'] >> ws, h['ysize']; fr.nw = fr.w >> 1 if fr.b16 else fr.w
    fr.rowsize = ((fr.w >> (2 - ws)) + 7) >> 3; fr.key = 0; fr.bw, fr.bt = bw, bt
    nblk = fr.nw >> 1
    full = bytes([0xFF] * (nblk >> 3)) + (bytes([(1 << (nblk & 7)) - 1]) if nblk & 7 else b'')
    full = full + bytes(fr.rowsize - len(full))
    fr.cbits = [full] * (fr.hgt >> 2)
    fr.rows = [[] for _ in range(fr.hgt)]
    # 머리: 템플릿 복호 머리에서 압축 번호·인터 깃발만 바꿔 다시 암호화
    hs = h['size']; hb = bytearray(template[i] ^ template[i + 1] for i in range(1, hs))
    hb[0] = comp; hb[11] = (hb[11] | tm1.FLAG_INTERFRAME) & ~tm1.FLAG_KEYFRAME & 0xFF
    fr.buf = bytes([template[0]]) + bytes(hs)          # rebuild 가 hb 를 buf 에서 다시 읽으므로 암호화된 꼴로 채운다
    b = tm1enc.enc_header(bytes(hb), hs, 0)
    fr.buf = bytes([template[0]] + b[1:hs]) + bytes([0])
    return fr


def burn(name, last=None, log=print):
    subs = load_subs().get(name, [])
    fr_all, h0, b16, w, hgt, disp = geometry(name)
    F = ImageFont.truetype(FONT, PX)
    A, B = (tm1.Decoder(), tm1.Decoder()) if b16 else (tm1.GDecoder(), tm1.GDecoder())   # ★24비트 = 게임 모델(좌우 화소)
    out = []; t0 = time.time()
    od = open(os.path.join(AVI_DIR, name + '.AVI'), 'rb').read()
    limit = BUF_MAX     # ★게임은 avih 를 읽어 버퍼를 잡는다(RAM 0x060EF7F8 에 avih 사본) → 원본 중 최대(HELP08) 이하면 안전, write_avi 가 avih·strh 를 새 최대로
    comp = h0['compression'] if tm1.COMP[h0['compression']][0] else next(tm1.header(b)['compression'] for _, b in fr_all if len(b) >= 2 and tm1.COMP[tm1.header(b)['compression']][0])
    template = next(b for _, b in fr_all if len(b) >= 2 and tm1.COMP[tm1.header(b)['compression']][0])
    prev_lines = None; prevB = None; prevBd = None
    n = len(fr_all) if last is None else min(last, len(fr_all))
    for k in range(n):
        off, b = fr_all[k]
        t = k / 15.0
        lines = next((ln for a, e, ln in subs if a <= t < e), None)
        if len(b) >= 2 and tm1.COMP[tm1.header(b)['compression']][0]:
            # ★자막 없는 프레임: 띠 상태가 원본과 같으면(또는 키 프레임 — 띠 전부 새로 그림) 원본 덩어리 그대로 → 화면도 원본과 같다
            #   (다시 짜면 색 오차가 생긴다, 2026-10-03 OPENING 800번대 파란 블록)
            if lines is None and A.frame is not None and B.frame is not None:
                same = B.frame == A.frame and getattr(B, 'dframe', None) == getattr(A, 'dframe', None)
                if same or tm1.header(b)['kflags'] & tm1.FLAG_KEYFRAME:
                    A.decode(b); B.decode(b); out.append(b); prev_lines = lines
                    continue
            prevB = copy.deepcopy(B.frame) if B.frame else None
            prevBd = copy.deepcopy(getattr(B, 'dframe', None)) if B.frame else None
            fr = tm1enc.trace(A, b)
            if lines is None and prev_lines is None and B.frame is not None and False:
                pass
        else:
            # NOP·빈 덩어리: 자막이 그대로면 원본 유지, 바뀌면 인터 프레임으로
            if lines == prev_lines or A.frame is None:
                out.append(b);
                if len(b) >= 2:
                    A.decode(b); B.decode(b)
                continue
            prevB = copy.deepcopy(B.frame); prevBd = copy.deepcopy(getattr(B, 'dframe', None))
            fr = make_inter(template, comp)
        nw = len(A.frame[0])
        y0 = hgt - BAND
        if b16:
            base = tm1.to_rgb(A.frame, b16)
            tg = target_from(render(base, w, hgt, disp, lines, F), b16, nw, hgt)
        else:                                        # 게임 화면(304폭) 그대로 위에 그리고 화소 2개씩 목표로
            img = render(tm1.game_rgb(A.frame, A.dframe), disp, hgt, disp, lines, F); px = img.load()
            tg = [[(px[2 * x, y], px[2 * x + 1, y]) for x in range(nw)] for y in range(hgt)]
            curd = [list(r) for r in A.dframe]
        cur = [list(r) for r in A.frame]
        if prevB is None:
            prevB = [[0] * nw for _ in range(hgt)]; prevBd = [[0] * nw for _ in range(hgt)]
        tol = None; coarse = 0
        while True:                                  # ★덩어리 크기 ≤ 원본 avih 권장 버퍼(게임 버퍼 넘침 방지) — 넘으면 띠 허용 오차·거칠기를 키워 다시
            if b16:
                E = tm1band.BandEnc(A.tab, A.key[0], b16, fr.bw, fr.bt, y0, tol, coarse)
                bops, bcb = E.encode(cur, prevB, tg, fr.key)
            else:
                E = tm1band.BandEnc24G(A.tab, A.key[0], b16, fr.bw, fr.bt, y0, tol, coarse)
                bops, bcb = E.encode_game([list(r) for r in cur], [list(r) for r in curd], prevB, prevBd, tg, fr.key)
            rows = fr.rows[:y0] + bops
            cbits = [] if fr.key else fr.cbits[:y0 >> 2] + bcb
            nb = tm1enc.rebuild(fr, rows, cbits, E.cdict)
            if len(nb) <= limit:
                break
            if E.tol < 16:
                tol = E.tol * 2
            else:
                assert coarse < 8, (name, k, len(nb), limit)
                coarse += 1
        B.decode(nb)
        assert B.frame[:y0] == A.frame[:y0] or all((B.frame[y][x] ^ A.frame[y][x]) & 0x7FFFFFFF == 0 for y in range(y0) for x in range(nw)), (name, k, '위쪽 불일치')
        out.append(nb); prev_lines = lines
        if k % 100 == 0:
            log('  %s %d/%d  %.0fs' % (name, k, n, time.time() - t0))
    out += [b for _, b in fr_all[n:]]
    return out


def write_avi(name, frames_new, dst):
    """원본 AVI 의 영상 덩어리를 차례로 바꿔 쓴다(00dc/00db 순서·꼬리표 그대로, 소리 그대로) + idx1·RIFF·movi 크기"""
    d = open(os.path.join(AVI_DIR, name + '.AVI'), 'rb').read()
    mv = d.find(b'movi'); lst = mv - 8                    # 'LIST' size 'movi'
    i = mv + 4; body = bytearray(); vi = 0; idx = []
    end_movi = lst + 8 + struct.unpack_from('<I', d, lst + 4)[0]
    while i + 8 <= end_movi:
        tag = d[i:i + 4]; n = struct.unpack_from('<I', d, i + 4)[0]
        if tag == b'LIST':
            body += d[i:i + 12]; i += 12; continue
        data = d[i + 8:i + 8 + n]
        if tag[2:] in (b'dc', b'db'):
            data = frames_new[vi]; vi += 1
        idx.append((tag, len(body) + 4, len(data)))      # idx1 오프셋 = 'movi' 기준
        body += tag + struct.pack('<I', len(data)) + data + (b'\0' if len(data) & 1 else b'')
        i += 8 + n + (n & 1)
    assert vi == len(frames_new), (vi, len(frames_new))
    head = bytearray(d[:lst])
    movi = b'LIST' + struct.pack('<I', len(body) + 4) + b'movi' + bytes(body)
    # 원본 idx1 의 깃발을 순서대로 가져온다
    oi = d.find(b'idx1', end_movi - 8)
    flags = []
    if oi >= 0:
        on = struct.unpack_from('<I', d, oi + 4)[0]
        for q in range(oi + 8, oi + 8 + on, 16):
            flags.append(struct.unpack_from('<I', d, q + 4)[0])
    ib = bytearray()
    for j, (tag, o, n) in enumerate(idx):
        ib += tag + struct.pack('<III', flags[j] if j < len(flags) else 0, o, n)
    tail = b'idx1' + struct.pack('<I', len(ib)) + bytes(ib)
    # ★movi 앞 «iddx» = idx1 사본(게임은 이걸로 덩어리 위치·크기를 읽는다 — 안 고치면 옛 크기로 읽어 띠가 깨지고 크래시, 2026-10-03 실기)
    xi = head.find(b'iddx')
    assert xi >= 0 and struct.unpack_from('<I', head, xi + 4)[0] == len(ib), (name, 'iddx')
    head[xi + 8:xi + 8 + len(ib)] = ib
    # avih·영상 strh 의 dwSuggestedBufferSize = 새 최대 영상 덩어리(원본보다 작아지진 않게)
    vmax = max(n for tag, o, n in idx if tag[2:] in (b'dc', b'db'))
    ai = head.find(b'avih') + 8
    struct.pack_into('<I', head, ai + 28, max(vmax, struct.unpack_from('<I', head, ai + 28)[0]))
    si = head.find(b'strh') + 8
    assert head[si:si + 4] == b'vids', name
    struct.pack_into('<I', head, si + 36, max(vmax, struct.unpack_from('<I', head, si + 36)[0]))
    out = head + movi + tail
    struct.pack_into('<I', out, 4, len(out) - 8)
    # avih dwMaxBytesPerSec 등은 그대로(재생기는 안 쓰는 듯) — 실기 확인
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    open(dst, 'wb').write(out)
    return len(d), len(out)


def preview(avi, mp4):
    tm1.to_mp4(avi, mp4)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    arg = sys.argv[1]
    if arg == 'check':
        sys.exit(1 if check() else 0)
    if check():
        sys.exit('⛔줄 폭 먼저 고칠 것')
    names = sorted(load_subs()) if arg == 'all' else [arg]
    last = int(sys.argv[2]) if len(sys.argv) > 2 and arg != 'all' else None
    for nm in names:
        fs = burn(nm, last)
        dst = os.path.join(OUT_DIR, nm + '.AVI')
        a, b = write_avi(nm, fs, dst)
        print('%s %d → %d B (%.1f%%) → %s' % (nm, a, b, 100.0 * b / a, dst), flush=True)
        os.makedirs(os.path.join(ROOT, 'work', 'movie', 'sub'), exist_ok=True)
        preview(dst, os.path.join(ROOT, 'work', 'movie', 'sub', nm + '_kr.mp4'))
