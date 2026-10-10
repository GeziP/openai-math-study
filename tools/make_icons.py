# -*- coding: utf-8 -*-
"""生成 assets/apple-touch-icon.png（180×180）。图案与 assets/favicon.svg 一致：渐变圆角方块 + 白色 ∑ 折线。

需要 Pillow（只在改图标时才需要，构建站点不依赖它）：  pip install pillow
用法：python tools/make_icons.py
"""
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "assets", "apple-touch-icon.png")
SIZE, SS = 180, 4                       # 目标尺寸；超采样倍数（先画大图再缩小，边缘更平滑）
N = SIZE * SS


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def main():
    c1, c2 = (0x6F, 0x7B, 0xFF), (0xB3, 0x6B, 0xFF)
    grad = Image.new("RGB", (N, N))
    px = grad.load()
    for yy in range(N):
        for xx in range(N):
            px[xx, yy] = lerp(c1, c2, (xx + yy) / (2.0 * (N - 1)))
    mask = Image.new("L", (N, N), 0)
    # iOS 会自己再套圆角，所以这里只留一点点圆角（和 favicon 的比例相同）
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, N - 1, N - 1], radius=int(N * 15 / 64), fill=255)
    img = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    img.paste(grad, (0, 0), mask)

    k = N / 64.0                         # favicon 的坐标系是 64×64
    pts = [(45, 17), (21, 17), (35, 32), (21, 47), (45, 47)]
    pts = [(x * k, y * k) for x, y in pts]
    d = ImageDraw.Draw(img)
    w = int(5.5 * k)
    d.line(pts, fill=(255, 255, 255, 255), width=w, joint="curve")
    r = w / 2.0                          # 线头和拐点补圆，等价于 round cap / round join
    for x, y in pts:
        d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, 255))
    img = img.resize((SIZE, SIZE), Image.LANCZOS)
    img.save(OUT, optimize=True)
    print("写出", os.path.abspath(OUT), img.size)


if __name__ == "__main__":
    main()
