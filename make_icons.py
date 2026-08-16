#!/usr/bin/env python3
"""홈 화면 아이콘(PNG) 생성기.

외부 이미지 라이브러리 없이 zlib만으로 PNG를 인코딩한다.
디자인: 브랜드 그라디언트 배경 + 흰색 지도 핀 (헤더 로고와 동일한 형태).
iOS는 아이콘 모서리를 자동으로 둥글게 마스킹하므로 full-bleed 정사각형으로 그린다.
"""
import math
import os
import struct
import sys
import zlib

# --color-primary / --color-primary-light (index.html의 디자인 토큰과 동일)
C_DARK = (0xFF, 0x4B, 0x2B)
C_LIGHT = (0xFF, 0x6B, 0x4A)


def write_png(path, size, pixels):
    """pixels: bytearray of RGBA, size*size*4"""
    stride = size * 4
    raw = bytearray()
    for y in range(size):
        raw.append(0)  # filter type 0 (None)
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
    """지도 핀 아이콘을 렌더링한다. scale은 핀 크기 배율(maskable 여백용)."""
    cx = size / 2.0
    cy0 = size * (0.5 - 0.085 * scale)          # 핀 머리 중심
    R = size * 0.185 * scale                     # 핀 머리 반지름
    tip_y = cy0 + size * 0.36 * scale            # 핀 끝점
    hole_r = R * 0.42                            # 가운데 구멍

    # 핀 끝점에서 원에 그은 두 접선의 접점
    d = tip_y - cy0
    cos_a = R / d
    sin_a = math.sqrt(max(0.0, 1.0 - cos_a * cos_a))
    tx = R * sin_a
    ty = cy0 + R * cos_a
    tri = ((cx, tip_y), (cx + tx, ty), (cx - tx, ty))

    def in_triangle(px, py):
        (ax, ay), (bx, by), (cx2, cy2) = tri
        d1 = (px - bx) * (ay - by) - (ax - bx) * (py - by)
        d2 = (px - cx2) * (by - cy2) - (bx - cx2) * (py - cy2)
        d3 = (px - ax) * (cy2 - ay) - (cx2 - ax) * (py - ay)
        has_neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
        has_pos = (d1 > 0) or (d2 > 0) or (d3 > 0)
        return not (has_neg and has_pos)

    def pin_coverage(px, py):
        """서브픽셀 샘플 한 점이 핀 내부면 1.0"""
        dx, dy = px - cx, py - cy0
        dist2 = dx * dx + dy * dy
        if dist2 <= hole_r * hole_r:
            return 0.0  # 구멍
        if dist2 <= R * R:
            return 1.0
        return 1.0 if in_triangle(px, py) else 0.0

    buf = bytearray(size * size * 4)
    inv = 1.0 / samples
    denom = float(samples * samples)
    # 핀이 존재할 수 있는 경계 상자 (밖은 배경만 계산해 속도를 아낀다)
    bx0, bx1 = int(cx - tx - 2), int(cx + tx + 2)
    by0, by1 = int(cy0 - R - 2), int(tip_y + 2)

    for y in range(size):
        # 대각선 그라디언트 (좌상 밝음 → 우하 진함)
        row = y * size * 4
        for x in range(size):
            t = (x / (size - 1) + y / (size - 1)) / 2.0
            bg = (
                round(C_LIGHT[0] + (C_DARK[0] - C_LIGHT[0]) * t),
                round(C_LIGHT[1] + (C_DARK[1] - C_LIGHT[1]) * t),
                round(C_LIGHT[2] + (C_DARK[2] - C_LIGHT[2]) * t),
            )
            cov = 0.0
            if bx0 <= x <= bx1 and by0 <= y <= by1:
                acc = 0.0
                for sy in range(samples):
                    py = y + (sy + 0.5) * inv
                    for sx in range(samples):
                        acc += pin_coverage(x + (sx + 0.5) * inv, py)
                cov = acc / denom

            i = row + x * 4
            if cov <= 0.0:
                buf[i] = bg[0]; buf[i + 1] = bg[1]; buf[i + 2] = bg[2]
            else:
                buf[i] = round(bg[0] + (255 - bg[0]) * cov)
                buf[i + 1] = round(bg[1] + (255 - bg[1]) * cov)
                buf[i + 2] = round(bg[2] + (255 - bg[2]) * cov)
            buf[i + 3] = 255  # iOS 아이콘은 불투명이어야 한다
    return buf


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "icons"
    os.makedirs(out_dir, exist_ok=True)
    targets = [
        ("icon-180.png", 180, 1.0),   # apple-touch-icon
        ("icon-192.png", 192, 1.0),
        ("icon-512.png", 512, 1.0),
        ("icon-maskable-512.png", 512, 0.78),  # 안전 영역 여백 확보
    ]
    for name, size, scale in targets:
        path = os.path.join(out_dir, name)
        write_png(path, size, render(size, scale))
        print(f"{path}  {size}x{size}  {os.path.getsize(path):,} bytes")


if __name__ == "__main__":
    main()
