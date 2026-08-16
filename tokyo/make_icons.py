#!/usr/bin/env python3
"""도쿄 산보 앱 아이콘 생성기 — 외부 라이브러리 없이 zlib으로 PNG를 직접 인코딩한다.

디자인: 남색 그라디언트 위에 흰 도리이(鳥居). iOS가 모서리를 자동으로 둥글게
마스킹하므로 full-bleed 정사각형으로 그린다.
"""
import math
import os
import struct
import sys
import zlib

BG_TOP = (0x2B, 0x3A, 0x67)     # 짙은 남색
BG_BOTTOM = (0x16, 0x1F, 0x3A)
ACCENT = (0xE0, 0x3E, 0x3E)     # 도리이 붉은색


def write_png(path, size, pixels):
    stride = size * 4
    raw = bytearray()
    for y in range(size):
        raw.append(0)
        raw += pixels[y * stride:(y + 1) * stride]

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)


def render(size, scale=1.0, samples=3):
    S = size
    cx = S / 2.0

    # 도리이 비율 (전체 높이의 scale 배)
    h = S * 0.56 * scale
    top = (S - h) / 2.0 + S * 0.02
    bot = top + h

    kasagi_y0 = top                      # 맨 위 가로대(카사기)
    kasagi_h = h * 0.11
    kasagi_hw = S * 0.34 * scale         # 반너비

    nuki_y0 = top + h * 0.26             # 두 번째 가로대(누키)
    nuki_h = h * 0.085
    nuki_hw = S * 0.285 * scale

    gakuzuka_hw = S * 0.022 * scale      # 가운데 짧은 기둥

    pillar_w = S * 0.052 * scale
    pillar_top = kasagi_y0 + kasagi_h
    pillar_off = S * 0.205 * scale       # 중심에서 기둥 중심까지

    def inside(px, py):
        # 카사기: 위로 살짝 휘어 올라간 사다리꼴
        if kasagi_y0 <= py <= kasagi_y0 + kasagi_h:
            curve = ((px - cx) / kasagi_hw) ** 2 * (kasagi_h * 0.55)
            if abs(px - cx) <= kasagi_hw and py >= kasagi_y0 + curve * 0.0:
                if py <= kasagi_y0 + kasagi_h - curve * 0.0:
                    # 양 끝이 아래로 처지도록 위쪽 경계를 곡선 처리
                    if py >= kasagi_y0 - curve + (kasagi_h * 0.0):
                        return True
        # 누키
        if nuki_y0 <= py <= nuki_y0 + nuki_h and abs(px - cx) <= nuki_hw:
            return True
        # 가쿠즈카 (카사기와 누키 사이 가운데 기둥)
        if kasagi_y0 + kasagi_h <= py <= nuki_y0 and abs(px - cx) <= gakuzuka_hw:
            return True
        # 좌우 기둥 (아래로 갈수록 살짝 벌어짐)
        if pillar_top <= py <= bot:
            t = (py - pillar_top) / max(1e-6, bot - pillar_top)
            off = pillar_off + t * S * 0.018 * scale
            w = pillar_w * (1.0 + t * 0.12)
            if abs(abs(px - cx) - off) <= w / 2.0:
                return True
        return False

    buf = bytearray(S * S * 4)
    inv = 1.0 / samples
    denom = float(samples * samples)

    for y in range(S):
        t = y / (S - 1)
        bg = (
            round(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * t),
            round(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * t),
            round(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * t),
        )
        row = y * S * 4
        for x in range(S):
            acc = 0.0
            if top - 2 <= y <= bot + 2:
                for sy in range(samples):
                    py = y + (sy + 0.5) * inv
                    for sx in range(samples):
                        if inside(x + (sx + 0.5) * inv, py):
                            acc += 1.0
            cov = acc / denom
            i = row + x * 4
            if cov <= 0.0:
                buf[i], buf[i + 1], buf[i + 2] = bg
            else:
                # 도리이는 흰색, 아래쪽으로 갈수록 붉은 기가 살짝 돈다
                mix = 0.25 * (y - top) / max(1e-6, bot - top)
                fg = (
                    round(255 + (ACCENT[0] - 255) * mix),
                    round(255 + (ACCENT[1] - 255) * mix),
                    round(255 + (ACCENT[2] - 255) * mix),
                )
                buf[i] = round(bg[0] + (fg[0] - bg[0]) * cov)
                buf[i + 1] = round(bg[1] + (fg[1] - bg[1]) * cov)
                buf[i + 2] = round(bg[2] + (fg[2] - bg[2]) * cov)
            buf[i + 3] = 255
    return buf


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "icons")
    os.makedirs(out, exist_ok=True)
    for name, size, scale in [
        ("icon-180.png", 180, 1.0),
        ("icon-192.png", 192, 1.0),
        ("icon-512.png", 512, 1.0),
        ("icon-maskable-512.png", 512, 0.78),
    ]:
        p = os.path.join(out, name)
        write_png(p, size, render(size, scale))
        print(f"{p}  {size}x{size}  {os.path.getsize(p):,} bytes")


if __name__ == "__main__":
    main()
