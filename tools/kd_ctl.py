# -*- coding: utf-8 -*-
r"""조작설명·특수조작설명 화면 한글화 (2026-10-02 사용자 «이거 찾아서 한글로 바꿔줄래»)
  그림 = KD00.BIN 비압축 640×480 8bpp(VDP2 NBG0 비트맵, 640 인터레이스) + 바로 뒤 팔레트 256×RGB555 BE(0x800 칸)
    조작설명 0x2B9800 / 팔레트 0x304800 · 특수조작설명 0x305000 / 팔레트 0x350000 (상태 VRAM 과 480줄 전부 일치 확인)
  방법: 칸마다 밝은 무채색 글자 + 오른쪽 아래 그림자를 지움 → 다른 화면 같은 자리(거기 글자 없으면)로 메움 → 남는 곳은 주변 평균
        → 원본에서 잰 글자색·그림자색으로 한글(나눔고딕 ExtraBold) → 그 화면 팔레트의 가장 가까운 색 번호로.
  제목 상자(操作説明·特殊操作説明)는 파란 바탕 단색으로 지우고 크림색 + 그림자.
  python tools/kd_ctl.py   → 미리보기 work/kd_preview_ctl.png · work/kd_preview_sp.png (원본|한글)
  build() → {'KD00.BIN': bytes}
"""
import os, struct, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
FONT = r'C:\claude\utils\font\nanum-gothic\NanumGothicBold.ttf'
TFONT = r'C:\claude\utils\font\nanum-gothic\NanumGothicExtraBold.ttf'
PAGES = {'ctl': (0x2B9800, 0x304800), 'sp': (0x305000, 0x350000)}
W, H = 640, 480
# (지울 상자 x0,y0,x1,y1, 한글, 글자 크기, 쓰는 x(None=상자 왼쪽), 종류)
LABELS = {
    'ctl': [
        ((93, 72, 146, 98), '정보', 21, None, 't'),
        ((263, 72, 360, 98), '방향 고정', 21, None, 'full'),
        ((368, 122, 590, 147), '창 열기', 21, None, 't'),
        ((368, 148, 610, 173), '오기 상관도／선술 발동', 21, None, 't'),
        ((368, 174, 445, 199), '대공격', 21, None, 't'),
        ((394, 229, 580, 255), '결정／대시', 21, None, 't'),
        ((394, 255, 604, 281), '취소／공격', 21, None, 't'),
        ((394, 281, 580, 306), '결정／위치 고정', 21, None, 't'),
        ((139, 357, 254, 382), '스타트', 21, None, 't'),
        ((361, 356, 581, 398), '조작 설명', 32, None, 'title'),
    ],
    'sp': [
        ((355, 42, 472, 66), '시간 빨리 감기', 21, None, 't'),
        ((355, 67, 612, 92), '선굴 간이 맵 표시 전환', 21, None, 't'),
        ((353, 118, 612, 144), '선술 선택(역방향)', 21, None, 't'),
        ((353, 144, 612, 170), '선술 선택(순방향)', 21, None, 't'),
        ((353, 202, 608, 226), '스매시(간격 길게)', 21, None, 't'),
        ((353, 228, 560, 252), '킥(간격 짧게)', 21, None, 't'),
        ((353, 254, 520, 278), '슈퍼킥', 21, None, 'full'),
        ((428, 280, 550, 304), '(간격 최단)', 21, None, 't'),
        ((28, 306, 150, 330), '기본 이름', 21, None, 't'),
        ((28, 332, 150, 357), '선택', 21, None, 't'),
        ((40, 357, 186, 383), '(선수 소환 시)', 21, None, 't'),
        ((400, 332, 498, 358), '중공격', 21, None, 't'),
        ((400, 358, 498, 385), '대공격', 21, None, 't'),
        ((100, 411, 297, 439), '격자 맵 표시', 21, None, 't'),
        ((316, 398, 578, 440), '특수 조작 설명', 30, None, 'title'),
    ],
}


def load(nm, K):
    st, pa = PAGES[nm]
    idx = np.frombuffer(K[st:st + W * H], np.uint8).reshape(H, W)
    pal = np.array([[(c & 31) << 3, (c >> 5 & 31) << 3, (c >> 10 & 31) << 3]
                    for c in struct.unpack('>256H', K[pa:pa + 512])], np.int32)
    return idx, pal


def textmask(rgb, box):
    x0, y0, x1, y1 = box
    x0, y0, x1, y1 = max(0, x0 - 2), max(0, y0 - 6), min(W, x1 + 8), min(H, y1 + 3)   # 그림자·탁점이 상자 밖으로 삐짐
    sub = rgb[y0:y1, x0:x1]
    mn, mx = sub.min(2), sub.max(2)
    ink = (mn > 85) & (mx - mn < 64)                                # 무채색 글자 + 회색 가장자리
    m = np.zeros((H, W), bool); m[y0:y1, x0:x1] = ink
    # 그림자·가장자리까지(오른쪽 아래 3px, 둘레 1px)
    d = m.copy()
    for dy in range(-2, 6):
        for dx in range(-2, 6):
            d |= np.roll(np.roll(m, dy, 0), dx, 1)
    box_m = np.zeros((H, W), bool); box_m[y0:y1, x0:x1] = True
    return d & box_m, ink


def ink_colors(rgb, box):
    x0, y0, x1, y1 = box
    sub = rgb[y0:y1, x0:x1].reshape(-1, 3)
    mn, mx = sub.min(1), sub.max(1)
    ink = sub[(mn > 140) & (mx - mn < 50)]
    body = tuple(int(v) for v in np.median(ink, 0)) if len(ink) else (230, 230, 220)
    return body, (16, 20, 16)


def heal(rgb, mask, other, other_mask, noborrow=None):
    out = rgb.copy()
    om = other_mask.copy()                                       # 다른 화면 글자의 흐린 가장자리까지 피함(4px)
    for dy in range(-4, 5):
        for dx in range(-4, 5):
            om |= np.roll(np.roll(other_mask, dy, 0), dx, 1)
    other_mask = om
    agree = (np.abs(rgb - other).sum(2) < 24) & ~mask & ~other_mask
    known_n = (~mask & ~other_mask).astype(float)
    a_sum = np.zeros((H, W)); k_sum = np.zeros((H, W))
    for dy in range(-6, 7):
        for dx in range(-6, 7):
            a_sum += np.roll(np.roll(agree, dy, 0), dx, 1); k_sum += np.roll(np.roll(known_n, dy, 0), dx, 1)
    trust = (k_sum >= 12) & (a_sum >= 0.85 * np.maximum(k_sum, 1))
    use = mask & ~other_mask & trust
    if noborrow is not None:
        use &= ~noborrow                                         # 다른 화면 그 자리에 다른 글자(A＋R 등)가 있는 칸
        ys, xs = np.where(noborrow & mask)                       # → 같은 화면 바로 위 배경 문양을 내려 붙임(확산은 뭉개진 띠가 됨)
        if len(ys):
            dy = ys.max() - ys.min() + 2
            src = ys - dy
            ok = (src >= 0) & ~mask[np.clip(src, 0, H - 1), xs]
            out[ys[ok], xs[ok]] = rgb[src[ok], xs[ok]]
            mask = mask.copy(); mask[ys[ok], xs[ok]] = False
    out[use] = other[use]
    rest = mask & ~use                                           # 빌려 오지 못한 칸은 전부 주변값으로
    known = ~rest
    for _ in range(60):                                          # 남는 곳 = 주변 평균(확산)
        if not rest.any():
            break
        acc = np.zeros_like(out, dtype=np.float64); cnt = np.zeros((H, W))
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            k = np.roll(np.roll(known, dy, 0), dx, 1)
            acc += np.roll(np.roll(out, dy, 0), dx, 1) * k[..., None]; cnt += k
        fill = rest & (cnt > 0)
        out[fill] = (acc[fill] / cnt[fill][:, None]).astype(np.int32)
        known |= fill; rest &= ~fill
    return out


def render(img, box, text, size, kind, body, shadow):
    x0, y0, x1, y1 = box
    im = Image.fromarray(img.astype(np.uint8)); d = ImageDraw.Draw(im)
    F = ImageFont.truetype(TFONT if kind == 'title' else FONT, size)
    tw = d.textlength(text, font=F)
    if kind == 'title':
        x = (x0 + x1 - tw) / 2
    else:
        x = x0 + 2
    assert x + tw <= (x1 if kind == 'title' else W - 4), ('글이 칸을 넘음', text, x + tw, x1)
    y = (y0 + y1) / 2
    off = 2 if kind == 'title' else 1
    d.text((x + off, y + off), text, font=F, fill=shadow, anchor='lm')
    d.text((x + off + 1, y + off + 1), text, font=F, fill=shadow, anchor='lm')
    d.text((x, y), text, font=F, fill=body, anchor='lm')
    return np.array(im).astype(np.int32)


def nearest(rgb, pal):
    flat = rgb.reshape(-1, 3)
    out = np.empty(len(flat), np.uint8)
    for i in range(0, len(flat), 20000):
        c = flat[i:i + 20000]
        out[i:i + 20000] = ((c[:, None, :] - pal[None, :, :]) ** 2).sum(2).argmin(1)
    return out.reshape(H, W)


def make(K):
    pages = {nm: load(nm, K) for nm in PAGES}
    rgbs = {nm: pal[idx] for nm, (idx, pal) in pages.items()}
    masks = {}; nobs = {}
    for nm in PAGES:
        m = np.zeros((H, W), bool)
        for box, _t, _s, _x, kind in LABELS[nm]:
            if kind == 'full':                                  # ★획이 어두워 밝기로 안 잡히는 칸 — 상자 전체를 지움(向き固定·スーパーキック)
                x0, y0, x1, y1 = box
                m[max(0, y0 - 3):min(H, y1 + 3), max(0, x0 - 2):min(W, x1 + 8)] = True
            elif kind != 'title':
                m |= textmask(rgbs[nm], box)[0]
        masks[nm] = m
        nob = np.zeros((H, W), bool)
        for box, _t, _s, _x, kind in LABELS[nm]:
            if kind == 'full':
                x0, y0, x1, y1 = box
                nob[max(0, y0 - 3):min(H, y1 + 3), max(0, x0 - 2):min(W, x1 + 8)] = True
        nobs[nm] = nob
    res = {}
    for nm in PAGES:
        other = 'sp' if nm == 'ctl' else 'ctl'
        idx, pal = pages[nm]; rgb = rgbs[nm]
        out = heal(rgb, masks[nm], rgbs[other], masks[other], nobs[nm])   # 글 칸 전부 먼저 지우고 메움
        for box, text, size, _, kind in LABELS[nm]:
            body, shadow = ink_colors(rgb, box)
            if kind == 'title':                                 # 파란 상자: 상자 안 최빈색으로 칠함
                x0, y0, x1, y1 = box
                sub = rgb[y0:y1, x0:x1].reshape(-1, 3)
                vals, cnt = np.unique(sub, axis=0, return_counts=True)
                out[y0:y1, x0:x1] = vals[cnt.argmax()]
                body = (248, 232, 176)
            out = render(out, box, text, size, kind, body, shadow)
        new = nearest(out, pal)
        changed = (out != rgb).any(2)
        res[nm] = np.where(changed, new, idx).astype(np.uint8)
    return res, pages


def build():
    K = bytearray(open(os.path.join(ROOT, 'work', 'disc', 'KD00.BIN'), 'rb').read())
    res, _ = make(bytes(K))
    for nm, (st, pa) in PAGES.items():
        K[st:st + W * H] = res[nm].tobytes()
    return {'KD00.BIN': bytes(K)}


def preview():
    K = open(os.path.join(ROOT, 'work', 'disc', 'KD00.BIN'), 'rb').read()
    res, pages = make(K)
    for nm, (idx, pal) in pages.items():
        a = pal[idx].astype(np.uint8); b = pal[res[nm]].astype(np.uint8)
        im = Image.new('RGB', (W * 2 + 8, H)); im.paste(Image.fromarray(a), (0, 0)); im.paste(Image.fromarray(b), (W + 8, 0))
        p = os.path.join(ROOT, 'work', 'kd_preview_%s.png' % nm); im.save(p); print('→', p)


if __name__ == '__main__':
    preview()
