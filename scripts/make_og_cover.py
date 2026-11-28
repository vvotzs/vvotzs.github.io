#!/usr/bin/env python3
"""生成 1200×630 的社交分享封面。

    python3 scripts/make_og_cover.py        # 中英两张都重出
    python3 scripts/make_og_cover.py en     # 只出英文 assets/og-cover-en.png
    python3 scripts/make_og_cover.py zh     # 只出中文 assets/og-cover.png

中文页用 assets/og-cover.png（build_site.py 的 OG_IMAGE），
英文页用 assets/og-cover-en.png（OG_IMAGE_EN），两页共用同一套暖米白 + 橙金礼券版式，
只有文案不同——分享到 X / Dev.to 时，英文卡片不再是中文字。

素材：assets/favicon-512.png（Ur.io 终版橙金礼券图标，透明底）。
旧版薄荷绿小怪兽（mascot）已彻底移除。
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT_ZH = ROOT / "assets" / "og-cover.png"
OUT_EN = ROOT / "assets" / "og-cover-en.png"
ICON = ROOT / "assets" / "favicon-512.png"
FONT = "/usr/share/fonts/pickle-hwp/NotoSansCJKkr-Regular.otf"
FONT_EN = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
FONT_EN_BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"

W, H = 1200, 630
BG_TOP = (252, 249, 243)
BG_BOTTOM = (246, 240, 230)
INK = (28, 25, 23)
INK2 = (87, 76, 66)
INK3 = (140, 128, 116)
GOLD = (234, 150, 20)
AMBER_DEEP = (154, 52, 18)


def font(size: int, en: bool = False, bold: bool = False) -> ImageFont.FreeTypeFont:
    if en:
        return ImageFont.truetype(FONT_EN_BOLD if bold else FONT_EN, size)
    return ImageFont.truetype(FONT, size)


def text(draw: ImageDraw.ImageDraw, xy, s, size, fill, bold=0, anchor="la", en=False):
    draw.text(xy, s, font=font(size, en=en, bold=bool(bold) and en), fill=fill,
              anchor=anchor, stroke_width=bold, stroke_fill=fill)


def fit_size(draw: ImageDraw.ImageDraw, s: str, size: int, max_w: float, en: bool) -> int:
    """英文句子比中文长：从给定字号往下收，直到整句塞得进 max_w。"""
    while size > 16 and draw.textlength(s, font=font(size, en=en)) > max_w:
        size -= 1
    return size


def soft_glow(color: tuple[int, int, int], shapes, blur: float) -> Image.Image:
    """柔光层：先在 L 遮罩上画形状再模糊，最后用纯色填充，避免 RGB 被模糊拖向黑色（发灰）。"""
    mask = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(mask)
    for box, a in shapes:
        md.ellipse(box, fill=a)
    mask = mask.filter(ImageFilter.GaussianBlur(blur))
    layer = Image.new("RGBA", (W, H), color + (0,))
    layer.putalpha(mask)
    return layer


def gradient_bg() -> Image.Image:
    img = Image.new("RGB", (W, H), BG_TOP)
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / (H - 1)
        d.line([(0, y), (W, y)],
               fill=tuple(int(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * t) for i in range(3)))

    # 暖橙光晕：左上、右中（托住礼券图标）、左下各一团，大模糊近似径向渐变。
    glow1 = soft_glow((255, 206, 150), [((-300, -340, 520, 300), 120)], 150)
    glow2 = soft_glow((255, 198, 132), [((700, -140, 1400, 520), 110)], 150)
    glow3 = soft_glow((255, 216, 170), [((-180, 420, 460, 940), 95)], 150)
    out = img.convert("RGBA")
    out = Image.alpha_composite(out, glow1)
    out = Image.alpha_composite(out, glow2)
    out = Image.alpha_composite(out, glow3)
    return out.convert("RGB")


def rounded(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def coupon_icon(img: Image.Image, cx: int, cy: int, size: int) -> None:
    """右侧主视觉：橙金礼券图标（透明底），带暖色光晕与柔和投影。"""
    r = int(size * 0.72)
    img.alpha_composite(
        soft_glow((255, 208, 150), [((cx - r, cy - r, cx + r, cy + r), 105)], int(size * 0.22))
    )

    icon = Image.open(ICON).convert("RGBA").resize((size, size), Image.LANCZOS)
    # 投影：同样先做 alpha 遮罩再模糊，颜色保持暖棕而不是发灰
    smask = Image.new("L", (W, H), 0)
    smask.paste(icon.split()[3].point(lambda a: int(a * 0.26)),
                (cx - size // 2, cy - size // 2 + int(size * 0.07)))
    smask = smask.filter(ImageFilter.GaussianBlur(int(size * 0.045)))
    shadow = Image.new("RGBA", (W, H), (150, 74, 12, 0))
    shadow.putalpha(smask)
    img.alpha_composite(shadow)

    img.alpha_composite(icon, (cx - size // 2, cy - size // 2))

    # 三颗小星，制造礼券「拆开有惊喜」的感觉（只用暖金色，不引入其它色系）
    d = ImageDraw.Draw(img)
    for (sx, sy, sr, col) in ((cx - int(size * 0.62), cy - int(size * 0.46), 9, (250, 190, 90)),
                              (cx + int(size * 0.60), cy - int(size * 0.20), 7, (247, 170, 70)),
                              (cx + int(size * 0.46), cy + int(size * 0.52), 6, (252, 208, 140))):
        d.polygon([(sx, sy - sr * 2), (sx + sr, sy), (sx, sy + sr * 2), (sx - sr, sy)], fill=col)


def brand_row(img: Image.Image, d: ImageDraw.ImageDraw, en: bool = False) -> None:
    icon = Image.open(ICON).convert("RGBA").resize((30, 30), Image.LANCZOS)
    img.alpha_composite(icon, (78, 82))
    text(d, (118, 97), "vvotzs.github.io", 21, INK3, anchor="lm", en=en)


def chips(d: ImageDraw.ImageDraw, items: list[str], y: int = 392, en: bool = False,
          x0: int = 80, max_w: int = 1040, size: int = 22) -> None:
    """底部一排分类胶囊：统一暖金/琥珀配色循环，宽度按实际文字算。"""
    fills = [(255, 247, 237), (254, 240, 186), (255, 235, 210), (253, 244, 224), (255, 239, 219)]
    lines = [(251, 176, 100), (246, 210, 100), (252, 200, 152), (238, 208, 150), (250, 190, 140)]
    inks = [(154, 52, 18), (140, 78, 10), (180, 83, 9), (150, 104, 40), (161, 60, 20)]

    def total(sz: int) -> float:
        return sum(d.textlength(c, font=font(sz, en=en)) + 40 for c in items) + 12 * (len(items) - 1)

    while size > 15 and total(size) > max_w:
        size -= 1

    x = x0
    for i, c in enumerate(items):
        w = int(d.textlength(c, font=font(size, en=en)) + 40)
        rounded(d, [x, y, x + w, y + 46], 23, fills[i % 5], lines[i % 5], 2)
        text(d, (x + w // 2, y + 23), c, size, inks[i % 5], anchor="mm", en=en)
        x += w + 12


def compose_zh() -> Image.Image:
    img = gradient_bg().convert("RGBA")
    coupon_icon(img, 938, 232, 290)
    d = ImageDraw.Draw(img)
    brand_row(img, d)
    d = ImageDraw.Draw(img)

    # 主标题
    text(d, (74, 158), "羊毛情报局", 104, INK, bold=2)
    text(d, (80, 300), "全球免费资源与优惠情报", 40, INK2)

    # 五个分类胶囊（Ur.io 最新文案，勿改字序）
    chips(d, ["AI免费额度", "Crypto 空投", "eSIM 流量", "云服务体验金", "返现奖励"], y=392)

    # 底部一句
    d.line([(80, 480), (1120, 480)], fill=(232, 212, 186), width=2)
    text(d, (80, 508), "值多少 · 门槛 · 截止日，一眼看清后直达官方页面", 26, INK3)

    return img


def compose_en() -> Image.Image:
    img = gradient_bg().convert("RGBA")
    coupon_icon(img, 938, 232, 290)
    d = ImageDraw.Draw(img)
    brand_row(img, d, en=True)
    d = ImageDraw.Draw(img)

    title = "Deal Hunter"
    t_size = fit_size(d, title, 100, 660, en=True)
    text(d, (74, 144), title, t_size, INK, bold=3, en=True)

    line1 = "Verified free credits, eSIM trials"
    line2 = "& bank bonuses · Updated every 2h"
    s_size = min(fit_size(d, line1, 36, 660, en=True), fit_size(d, line2, 36, 660, en=True))
    text(d, (80, 282), line1, s_size, INK2, en=True)
    text(d, (80, 282 + s_size + 12), line2, s_size, INK2, en=True)

    chips(d, ["AI credits", "Crypto airdrops", "eSIM data", "Cloud credits", "Cashback"],
          y=392, en=True)

    d.line([(80, 480), (1120, 480)], fill=(232, 212, 186), width=2)
    text(d, (80, 508), "Value, requirements & deadline — at a glance", 26, INK3, en=True)

    return img


def main(argv: list[str]) -> None:
    which = (argv[1].lower() if len(argv) > 1 else "both")
    if which in ("zh", "both"):
        img = compose_zh()
        img.convert("RGB").save(OUT_ZH, "PNG", optimize=True)
        print(f"wrote {OUT_ZH} · {OUT_ZH.stat().st_size/1024:.1f} KB")
    if which in ("en", "both"):
        img = compose_en()
        img.convert("RGB").save(OUT_EN, "PNG", optimize=True)
        print(f"wrote {OUT_EN} · {OUT_EN.stat().st_size/1024:.1f} KB")


if __name__ == "__main__":
    main(sys.argv)
