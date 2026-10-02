# -*- coding: utf-8 -*-
r"""타이틀 로고 한글화 시안 (2026-10-02 사용자 «타이틀화면도 한글로 한번 바꿔봐»)
  타이틀 그림 = LOAD.BIN 0x4B544 압축 블록(머리 0x34) → 640×480 8bpp(색 번호). 팔레트는 아직 못 찾음 →
  팔레트 = LOAD.BIN 0x90798(RGB555 BE). 스크린샷 인수는 이제 안 씀(옛 추정 palette() 는 참고용).
  1) 로고 범위 안에만 몰린 색 번호 = 로고 → 지우고 주변 색으로 메움  2) 「선굴활룡대전」(빨강·노랑 테두리) ·
  「카오스 시드」(원본 가타카나 줄별 색 그라데이션 + 검은 테두리) — BlackHanSans  3) 게임 팔레트 256색으로 줄임(넣으면 이 모습)
  CHAOS SEED(영문)·저작권 줄은 그대로.
  python tools/title_logo.py SCREENSHOT OUT.png
"""
import os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import lz

BLK = 0x4B544
FONT = r'C:\claude\utils\font\logo\BlackHanSans.ttf'
BOX = (24, -52, 1709, 1337)
LOGO = (40, 62, 604, 214)          # 한자 줄 + 가타카나(640×480 좌표) — 그 아래 CHAOS SEED 는 둠
KANJI = (150, 62, 500, 112)
KATA = (40, 108, 604, 206)


def load():
    L = open(os.path.join(ROOT, 'work', 'disc', 'LOAD.BIN'), 'rb').read()
    return np.frombuffer(lz.decompress(L, BLK + 1)[0], dtype=np.uint8).reshape(480, 640).copy()


def palette(u, shot):
    sc = np.asarray(Image.open(shot).convert('RGB').crop(BOX).resize((640, 480), Image.NEAREST)).astype(int)
    ok = np.ones(u.shape, bool); ok[300:400] = False; ok[:30] = False; ok[455:] = False
    pal = np.zeros((256, 3), int)
    for i in range(256):
        m = (u == i) & ok
        if m.any():
            pal[i] = np.median(sc[m], 0)
    return pal


PAL = 0x90798      # ★진짜 팔레트: LOAD.BIN 0x90798, RGB555 BE 256색(디스크 전수 대조 — 스샷 색과 오차 최소)


def real_palette():
    L = open(os.path.join(ROOT, 'work', 'disc', 'LOAD.BIN'), 'rb').read()
    b = np.frombuffer(L[PAL:PAL + 512], dtype='>u2').astype(int)
    return np.stack([(b & 31) << 3, ((b >> 5) & 31) << 3, ((b >> 10) & 31) << 3], -1)


def logo_mask(u):
    x0, y0, x1, y1 = LOGO
    inb = np.zeros(u.shape, bool); inb[y0:y1, x0:x1] = True
    tot = np.bincount(u.ravel(), minlength=256); ins = np.bincount(u[inb], minlength=256)
    logo_idx = (ins > 0) & (ins >= tot * 0.85)
    m = logo_idx[u] & inb
    img = Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(13))
    return (np.asarray(img) > 0) & inb, logo_idx


def fill(rgb, mask):
    """주변 색으로 안쪽까지 번져 메움(양파 껍질)"""
    rgb = rgb.astype(float).copy()
    sat = rgb.max(-1) - rgb.min(-1)
    known = ~mask & (sat < 70) & (rgb.sum(-1) > 90)                                   # 재료 = 채도 낮은 배경색만(CHAOS SEED 금색이 번지지 않게) · 메우는 곳 = mask 만
    todo = mask.copy()
    while todo.any():
        acc = np.zeros_like(rgb); n = np.zeros(mask.shape)
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)):
            k = np.roll(np.roll(known, dy, 0), dx, 1); c = np.roll(np.roll(rgb, dy, 0), dx, 1)
            acc += c * k[..., None]; n += k
        new = todo & (n > 0)
        if not new.any():
            break
        rgb[new] = acc[new] / n[new][:, None]; known = known | new; todo &= ~new
    return rgb


def text_mask(text, box, font_px):
    x0, y0, x1, y1 = box
    f = ImageFont.truetype(FONT, font_px)
    l, t, r, b = f.getbbox(text)
    im = Image.new('L', (r - l, b - t), 0); ImageDraw.Draw(im).text((-l, -t), text, font=f, fill=255)
    h = y1 - y0; w = min(x1 - x0, round(im.width * h / im.height * 1.15))   # 높이 맞춤, 가로는 조금만 넓힘
    im = im.resize((w, h), Image.LANCZOS)
    full = Image.new('L', (x1 - x0, h), 0); full.paste(im, ((x1 - x0 - w) // 2, 0))
    return np.asarray(full) > 110


def grow(m, r):
    return np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(2 * r + 1))) > 0


def build():
    """→ (새 색 번호 480×640, 새 팔레트 256×3, 원본 RGB) — 빌더(insert.py)와 미리보기가 같이 씀"""
    u = load(); pal = real_palette()
    orig = pal[u].astype(np.uint8)
    mask, logo_idx = logo_mask(u)
    P = pal[u]
    x0, y0, x1, y1 = LOGO
    inb = np.zeros(u.shape, bool); inb[y0:y1, x0:x1] = True
    chaos = np.zeros(u.shape, bool); chaos[198:260, 172:478] = (P[198:260, 172:478, 1] > 110) & (P[198:260, 172:478, 1] > P[198:260, 172:478, 2] + 40)   # CHAOS SEED 글자 범위(x 180‥469)
    below = np.zeros(u.shape, bool); below[y1:y1 + 14, x0:x1] = True        # 상자 밑으로 삐진 로고 밑동
    mask |= below & logo_idx[u]
    gold = (P[..., 1] > 90) & (P[..., 1] > P[..., 2] + 30)                # 가타카나 금색 밑동(CHAOS SEED 와 같은 색 번호)
    mask |= (inb | below) & grow(gold, 1)
    mask |= inb & (P.sum(-1) < 150) & grow(logo_idx[u] & inb, 10)   # 원본 로고 검은 테두리(배경과 같은 색 번호라 빠짐)
    mask &= ~grow(chaos, 2)                                      # CHAOS SEED 글자는 지키기
    rgb = fill(pal[u], mask)

    # 원본 색 뽑기: 한자 줄 = 가장 흔한 로고 색(빨강)·두 번째(테두리), 가타카나 = 줄별 가장 밝은 쪽 로고 색
    def common(box, pick):
        x0, y0, x1, y1 = box; sub = u[y0:y1, x0:x1]; sub = sub[logo_idx[sub]]
        cs = pal[sub]; return pick(cs)
    br = lambda c: c.sum(-1)
    red = common(KANJI, lambda cs: np.median(cs[(cs[:, 0] > 140) & (cs[:, 1] < 90)], 0))
    yel = np.array([250, 220, 60])
    # 그라데이션 = 원본에서 안 눌린 왼쪽 글자(カ, x 56‥110 · 100‥205줄)의 줄별 색 → 높이 0‥1 에 대응
    TOP, BOT, DIP = 100, 205, 36                                  # 원본 실측: 양 끝 위 100줄 · 가운데 약 138줄 · 아래 205줄
    grad = []
    for y in range(TOP, BOT):
        row = u[y, 56:110]; row = row[logo_idx[row]]
        cs = pal[row]; cs = cs[(br(cs) > 120) & (br(cs) < 700)] if len(cs) else cs
        grad.append(np.median(cs, 0) if len(cs) else None)
    for i in range(len(grad)):
        if grad[i] is None:
            grad[i] = next((g for g in grad[i:] + grad[::-1] if g is not None), np.array([60, 60, 160]))
    G = np.array(grad, float)
    k = 6; G = np.array([G[max(0, i - k):i + k + 1].mean(0) for i in range(len(G))])

    canvas = rgb.copy()
    # 큰 글 «카오스 시드» — 아래·양옆은 직선, 위 라인만 활처럼(가운데가 DIP 줄 눌림)
    kb = (KATA[0] + 6, TOP, KATA[2] - 6, BOT)
    H = BOT - TOP
    flat_m = text_mask('카오스 시드', kb, 160)
    m = np.zeros(u.shape, bool)
    cx = (kb[0] + kb[2]) / 2; hw = (kb[2] - kb[0]) / 2
    sx = np.zeros(640)
    for x in range(kb[0], kb[2]):
        s_ = DIP * (1 - ((x - cx) / hw) ** 2); sx[x] = s_
        col = flat_m[:, x - kb[0]]
        for y in range(TOP + int(round(s_)), BOT):
            src = int((y - TOP - s_) * H / (H - s_))
            m[y, x] = col[min(H - 1, src)]
    # 테두리 = 원본 실측: 글자 바로 바깥 노랑 3px(248,232,56) · 아래쪽은 금색(224,192,112) · 그 바깥 검정 1px
    ring = grow(m, 3) & ~m
    canvas[grow(m, 4)] = [0, 0, 0]
    ry, rx = np.where(ring)
    below = np.array([m[max(0, y - 4):y, x].any() and not m[y + 1:min(480, y + 5), x].any() for y, x in zip(ry, rx)])
    canvas[ry, rx] = [248, 232, 56]
    canvas[ry[below], rx[below]] = [224, 192, 112]
    ys, xs = np.where(m)
    v = (ys - TOP - sx[xs]) / (H - sx[xs])
    # 사용자 지시(2026-10-02): 위 파랑 → 가운데 살짝 밝은 띠 → 아래 진한 남색
    KEYS = [(0.0, (8, 48, 120)), (0.25, (16, 48, 112)), (0.45, (40, 56, 112)), (0.56, (80, 88, 128)), (0.64, (40, 48, 96)), (0.75, (16, 24, 72)), (1.0, (0, 8, 40))]   # 원본 カ 기둥 실측(진짜 팔레트) — 위 청남·가운데 옅은 띠·아래 짙은 남색
    kv = np.array([k for k, _ in KEYS]); kc = np.array([c for _, c in KEYS], float)
    canvas[ys, xs] = np.stack([np.interp(v, kv, kc[:, i]) for i in range(3)], -1)
    # 위 줄 «선굴활룡대전»
    tb = (KANJI[0] - 10, KANJI[1] - 4, KANJI[2] + 10, KANJI[3] - 8)          # 사용자 «조금 키우고»
    m2 = np.zeros(u.shape, bool)
    m2[tb[1]:tb[3], tb[0]:tb[2]] = text_mask('선굴활룡대전', tb, 120)
    canvas[grow(m2, 4)] = [10, 10, 10]; canvas[grow(m2, 2)] = yel; canvas[m2] = [170, 15, 20]   # 진한 빨강(사용자)

    # 게임 팔레트로 줄임(가장 가까운 색 번호)
    flat = canvas.reshape(-1, 3)
    idx = np.empty(len(flat), np.uint8)
    for a in range(0, len(flat), 20000):
        d = ((flat[a:a + 20000, None, :] - pal[None, :, :]) ** 2).sum(-1); idx[a:a + 20000] = d.argmin(1)
    newu = idx.reshape(480, 640)
    # 메운 자리는 로고 둘레 배경에 실제로 쓰인 색 번호 안에서만(아니면 회청 평균이 갈색으로 잡힘)
    ring = grow(mask, 18) & ~mask & ~grow(chaos, 3); ring[:, :20] = False
    bgset = np.unique(u[ring & ~logo_idx[u]])
    bp = pal[bgset].astype(float)
    ys_, xs_ = np.where(mask)
    d = ((canvas[ys_, xs_][:, None, :] - bp[None]) ** 2).sum(-1)
    newu[ys_, xs_] = bgset[d.argmin(1)]
    # ★새 로고 색: 원본 로고에만 쓰이던 색 번호(이제 남음)를 새 색으로 다시 정의 — 팔레트(LOAD.BIN 0x90798)도 같이 고친다
    letters = grow(m, 4) | grow(m2, 4)
    used = set(np.unique(newu[~letters]).tolist())
    free = [i for i in range(256) if i not in used]
    lp = canvas[letters].astype(np.uint8)
    q = Image.fromarray(lp.reshape(1, -1, 3)).quantize(colors=len(free), method=Image.Quantize.MEDIANCUT)
    qp = np.array(q.getpalette()[:3 * len(free)]).reshape(-1, 3)
    qp = (qp // 8) * 8                                            # RGB555
    newpal = pal.copy()
    for k, i in enumerate(free):
        newpal[i] = qp[k]
    lab = np.asarray(q).ravel()
    newu[letters] = np.array(free)[lab]
    pal = newpal
    print('남는 색 번호 %d개 → 새 로고 색' % len(free))
    np.save(os.path.join(ROOT, 'work', 'title_ko_pal.npy'), newpal)
    np.save(os.path.join(ROOT, 'work', 'title_ko_idx.npy'), newu)
    return newu, pal, orig


def apply(L):
    """LOAD.BIN(bytearray) 의 타이틀 그림 블록(0x4B544)과 팔레트(0x90798)를 바꿈 — 새 압축 ≤ 원래"""
    newu, pal, _ = build()
    _, e = lz.decompress(L, BLK + 1)
    c = lz.compress(newu.tobytes())
    room = e - (BLK + 1)
    if len(c) > room:
        raise SystemExit('⛔타이틀 그림 압축 %d > 원래 %d' % (len(c), room))
    L[BLK + 1:BLK + 1 + len(c)] = c
    w = ((pal[:, 2] >> 3) << 10) | ((pal[:, 1] >> 3) << 5) | (pal[:, 0] >> 3)
    L[PAL:PAL + 512] = b''.join(int(v).to_bytes(2, 'big') for v in w)
    return len(c), room


def main():
    out = sys.argv[-1]
    newu, pal, orig = build()
    new = pal[newu].astype(np.uint8)
    both = Image.new('RGB', (640, 960 + 10), (0, 0, 0))
    both.paste(Image.fromarray(orig), (0, 0)); both.paste(Image.fromarray(new), (0, 490))
    both.save(out); print('→', out)


if __name__ == '__main__':
    main()
