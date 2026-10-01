# -*- coding: utf-8 -*-
r"""카오스 시드 압축(항목 머리 0x34) 풀기 — 0.BIN 0x0601FE84 를 그대로 옮김(2026-10-01)
  src = 0x34 다음(크기 필드)부터. 형식:
    u32 LE 풀린 크기, 플래그 바이트(비트는 LSB 부터, 8개 다 쓰면 «즉시» 다음 바이트를 플래그로 읽음)
    바이트 b 를 읽는다:
      b < 0x80            → 리터럴(플래그 안 씀)
      b >= 0x80, 플래그 0 → 리터럴 b
      플래그 1, 다음 플래그 0 → c 읽음: 거리 = (s8(b) << 4 | c >> 4)(음수), 길이 = (c & 15) + 3
      플래그 1, 다음 플래그 1 → c, n 읽음: 거리 = s8(b) << 8 | c(음수), 길이 = n + 4
  아카이브(.ADT 등): u24 LE 오프셋 표, 첫 오프셋 = 표 크기, 마지막 = 파일 끝. 항목 시작 바이트 0x34 = 압축.
  python tools/lz.py FILE            → 항목별 검산(입력 소비량·크기)
  python tools/lz.py FILE OUTDIR     → 항목을 풀어서 OUTDIR/<번호>.bin
"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def s8(x):
    return x - 256 if x & 0x80 else x


def decompress(src, pos=0):
    """반환 (풀린 바이트, 소비한 끝 위치)"""
    size = int.from_bytes(src[pos:pos + 4], 'little'); i = pos + 4
    out = bytearray(); cnt = 8; flags = src[i]; i += 1

    def bit():
        nonlocal flags, cnt, i
        b = flags & 1; flags >>= 1; cnt -= 1
        if cnt == 0:
            flags = src[i]; i += 1; cnt = 8
        return b

    while len(out) < size:
        b = src[i]; i += 1
        if b < 0x80:
            out.append(b); continue
        # 원본: 리터럴 경로는 SHLR 후 쓰고 나서 DT·재적재, 참조 경로는 DT·재적재 후 다음 SHLR — 순서는 같다
        if not bit():
            out.append(b); continue
        if bit():
            c = src[i]; n = src[i + 1]; i += 2
            dist = (s8(b) << 8) | c; ln = n + 4
        else:
            c = src[i]; i += 1
            dist = (s8(b) << 4) | (c >> 4); ln = (c & 15) + 3
        p = len(out) + dist
        if p < 0:
            raise ValueError('거리 범위 밖 %d' % p)
        for k in range(ln):
            if len(out) >= size:
                break
            out.append(out[p + k])
    return bytes(out), i


def compress(data):
    """decompress 의 역(탐욕 일치). 반환 = u32 크기부터(항목에 넣을 땐 앞에 0x34).
       짧은 참조: 거리 −2048‥−1 · 길이 3‥18 (b=거리>>4, c=(거리&15)<<4|길이−3) / 긴 참조: 거리 −32768‥−1 · 길이 4‥259 (b, c, n)
       플래그 비트는 토큰 첫 바이트 b 뒤에서 소비 — 8개 다 차면 그 자리에 새 플래그 바이트(원본 «즉시 읽기»와 같은 순서)"""
    out = bytearray(len(data).to_bytes(4, 'little')); fpos = len(out); out.append(0); nb = 0

    def bit(v):
        nonlocal fpos, nb
        out[fpos] |= v << nb; nb += 1
        if nb == 8:
            fpos = len(out); out.append(0); nb = 0

    heads = {}; i = 0; n = len(data)
    while i < n:
        best_l, best_d = 0, 0
        if i + 3 <= n:
            for j in reversed(heads.get(data[i:i + 3], [])[-64:]):
                d = j - i
                if d < -32768:
                    break
                l = 0
                while i + l < n and l < 259 and data[j + l] == data[i + l]:
                    l += 1
                if l > best_l and (l >= 4 or d >= -2048):
                    best_l, best_d = l, d
                    if l == 259:
                        break
        if best_l >= 3 and not (best_l == 3 and best_d < -2048):
            if best_d >= -2048 and best_l <= 18:
                out.append((best_d >> 4) & 0xFF); bit(1); bit(0); out.append(((best_d & 15) << 4) | (best_l - 3))
            else:
                if best_l < 4:
                    best_l = 0
                else:
                    out.append((best_d >> 8) & 0xFF); bit(1); bit(1); out += bytes([best_d & 0xFF, best_l - 4])
            if best_l:
                for k in range(best_l):
                    heads.setdefault(data[i + k:i + k + 3], []).append(i + k)
                i += best_l; continue
        b = data[i]
        out.append(b)
        if b >= 0x80:
            bit(0)
        heads.setdefault(data[i:i + 3], []).append(i); i += 1
    return bytes(out)


def replace_item(d, k, new):
    """아카이브 d 의 k 번 항목만 new 로 바꾸고 그 뒤를 차이만큼 민다(표에 빈·역순·공유 항목이 있어 통째로 다시 묶으면 안 됨)"""
    offs = archive(d); a, b = offs[k], offs[k + 1]; delta = len(new) - (b - a)
    n = len(offs); out = bytearray(d[:a] + new + d[b:])
    for i, o in enumerate(offs):
        if o >= b and not (i == k + 1 and False):
            o += delta
        out[3 * i:3 * i + 3] = o.to_bytes(3, 'little')
    return bytes(out)


def pack_archive(items):
    """items = 항목 바이트 목록(머리 0x34/0x40 포함) → u24 오프셋 표 + 이어 붙임"""
    n = len(items) + 1; pos = 3 * n; offs = []
    for it in items:
        offs.append(pos); pos += len(it)
    offs.append(pos)
    return b''.join(o.to_bytes(3, 'little') for o in offs) + b''.join(items)


def archive(d):
    n = (d[0] | d[1] << 8 | d[2] << 16) // 3
    return [d[3 * k] | d[3 * k + 1] << 8 | d[3 * k + 2] << 16 for k in range(n)]


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    f = sys.argv[1]; d = open(os.path.join(ROOT, 'work', 'disc', f), 'rb').read()
    offs = archive(d); bad = 0; outdir = sys.argv[2] if len(sys.argv) > 2 else None
    if outdir:
        os.makedirs(outdir, exist_ok=True)
    for k, (a, b) in enumerate(zip(offs, offs[1:])):
        if b <= a:
            print('%3d  빈 항목/역순 %X %X' % (k, a, b)); continue
        if d[a] != 0x34:
            print('%3d  비압축(머리 %02X) %d B' % (k, d[a], b - a))
            if outdir:
                open(os.path.join(outdir, '%03d.bin' % k), 'wb').write(d[a:b])
            continue
        try:
            u, e = decompress(d, a + 1)
        except (IndexError, ValueError) as ex:
            print('%3d  실패 %s' % (k, ex)); bad += 1; continue
        ok = b - 4 < e <= b + 1   # 마지막 플래그 «즉시 읽기»가 다음 항목 첫 바이트를 미리 읽을 수 있다(원본도 같음)
        bad += not ok
        if not ok or not outdir:
            print('%3d  %6d → %6d  소비 끝 %X / 다음 %X %s' % (k, b - a, len(u), e, b, '' if ok else '✗'))
        if outdir:
            open(os.path.join(outdir, '%03d.bin' % k), 'wb').write(u)
    print('항목 %d · 불일치 %d' % (len(offs) - 1, bad))


if __name__ == '__main__':
    main()
