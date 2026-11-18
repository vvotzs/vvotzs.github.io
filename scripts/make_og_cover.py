#!/usr/bin/env python3
"""生成 1200×630 的社交分享封面 assets/og-cover.png。

一次性用途，但保留脚本方便以后改文案重新出图：
    python3 scripts/make_og_cover.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "og-cover.png"
FONT = "/usr/share/fonts/pickle-hwp/NotoSansCJKkr-Regular.otf"

W, H = 1200, 630
BG = (250, 249, 245)
INK = (24, 24, 27)
INK2 = (82, 82, 91)
INK3 = (138, 138, 147)
TERRA = (234, 88, 12)
AMBER_DEEP = (180, 83, 9)
MINT = (5, 150, 105)


def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT, size)


def text(draw: ImageDraw.ImageDraw, xy, s, size, fill, bold=0, anchor="la", spacing=0):
    draw.text(xy, s, font=font(size), fill=fill, anchor=anchor, stroke_width=bold, stroke_fill=fill)


def gradient_bg() -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / (H - 1)
        r = int(250 - 6 * t)
        g = int(249 - 9 * t)
        b = int(245 - 15 * t)
        d.line([(0, y), (W, y)], fill=(r, g, b))

    # 暖色光晕（左上琥珀、右下薄荷），用大模糊圆近似径向渐变
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([-260, -300, 560, 320], fill=(255, 214, 170))
    gd.ellipse([820, 300, 1420, 860], fill=(186, 240, 216))
    glow = glow.filter(ImageFilter.GaussianBlur(150))
    return Image.blend(img, glow, 0.16)


def rounded(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def mascot(img: Image.Image, cx: int, cy: int, scale: float = 1.0) -> None:
    """薄荷小怪兽：和站点 SVG 同一套配色。"""
    def s(v):
        return int(v * scale)

    # 身后的薄荷圆盘（柔和一层就够，别抢主体）
    halo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    hd = ImageDraw.Draw(halo)
    hd.ellipse([cx - s(205), cy - s(205), cx + s(205), cy + s(205)], fill=(236, 253, 245, 255))
    halo = halo.filter(ImageFilter.GaussianBlur(s(2)))
    img.alpha_composite(halo)

    # 身体：先在椭圆遮罩里铺一层由浅到深的薄荷渐变，避免出现「帽子」接缝
    body = [cx - s(120), cy - s(150), cx + s(120), cy + s(150)]
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).ellipse(body, fill=255)
    grad = Image.new("RGB", (W, H))
    gd = ImageDraw.Draw(grad)
    top, bottom = (186, 246, 219), (108, 221, 175)
    for yy in range(H):
        t = min(max((yy - body[1]) / (body[3] - body[1]), 0), 1)
        gd.line([(0, yy), (W, yy)], fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    img.paste(grad, (0, 0), mask)

    d = ImageDraw.Draw(img)
    # 脸
    d.ellipse([cx - s(92), cy - s(72), cx + s(92), cy + s(92)], fill=(243, 255, 249))
    # 眼睛
    for ex in (-38, 38):
        d.ellipse([cx + s(ex - 11), cy - s(30), cx + s(ex + 11), cy - s(8)], fill=(20, 83, 45))
        d.ellipse([cx + s(ex - 6), cy - s(26), cx + s(ex - 1), cy - s(21)], fill=(255, 255, 255))
    # 腮红
    d.ellipse([cx - s(78), cy + s(8), cx - s(44), cy + s(30)], fill=(252, 200, 200))
    d.ellipse([cx + s(44), cy + s(8), cx + s(78), cy + s(30)], fill=(252, 200, 200))
    # 微笑
    d.arc([cx - s(30), cy + s(2), cx + s(30), cy + s(52)], start=20, end=160, fill=(20, 83, 45), width=s(7))
    # 头顶小芽
    d.line([cx + s(4), cy - s(170), cx - s(2), cy - s(138)], fill=(52, 211, 153), width=s(8))
    d.ellipse([cx + s(2), cy - s(176), cx + s(40), cy - s(142)], fill=(52, 211, 153))


def main() -> None:
    img = gradient_bg().convert("RGBA")

    mascot(img, 946, 252, 1.12)

    # 右下角装饰卡（示意「一条优惠」），压在小怪兽前面制造层次
    deco = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dd = ImageDraw.Draw(deco)
    rounded(dd, [700, 424, 1128, 534], 26, (255, 255, 255, 240), (236, 238, 242, 255), 2)
    dd.ellipse([722, 452, 776, 506], fill=(254, 243, 199, 255))
    text(dd, (794, 452), "Binance 新手任务", 25, INK)
    text(dd, (794, 490), "最高 $1,100 手续费券 · 已核验", 19, INK3)
    rounded(dd, [1030, 446, 1108, 480], 17, (254, 243, 199, 255), (253, 230, 138, 255), 2)
    text(dd, (1069, 463), "$1,100", 19, (146, 64, 14), anchor="mm")
    img.alpha_composite(deco)

    d = ImageDraw.Draw(img)

    # 顶部品牌行
    d.ellipse([80, 84, 118, 122], fill=(209, 250, 229))
    d.ellipse([90, 94, 108, 112], fill=(127, 227, 184))
    text(d, (132, 103), "vvotzs.github.io", 22, INK3, anchor="lm")

    # 主标题
    text(d, (76, 176), "羊毛情报局", 104, INK, bold=3)
    text(d, (80, 316), "每日核验的全球优惠情报", 42, INK2)

    # 三个分类胶囊
    chips = ["AI 免费额度", "Crypto 奖励", "eSIM 流量", "云服务体验金"]
    x = 80
    for i, c in enumerate(chips):
        w = int(d.textlength(c, font=font(23))) + 44
        fill = [(255, 247, 237), (236, 253, 245), (239, 246, 255), (245, 243, 255)][i % 4]
        line = [(253, 186, 116), (187, 247, 208), (191, 219, 254), (221, 214, 254)][i % 4]
        ink = [AMBER_DEEP, MINT, (29, 78, 216), (109, 40, 217)][i % 4]
        rounded(d, [x, 392, x + w, 440], 24, fill, line, 2)
        text(d, (x + w // 2, 416), c, 23, ink, anchor="mm")
        x += w + 14

    # 底部一句
    text(d, (80, 512), "值多少 · 门槛 · 截止日，一眼看清后直达官方页面", 26, INK3)

    img.convert("RGB").save(OUT, "PNG", optimize=True)
    print(f"wrote {OUT} · {OUT.stat().st_size/1024:.1f} KB")


if __name__ == "__main__":
    main()
