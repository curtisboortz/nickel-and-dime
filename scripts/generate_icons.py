"""Generate app icons and OG card from scratch using Pillow.

Run once:  python scripts/generate_icons.py
Outputs to app/static/img/
"""

import os
import sys

from PIL import Image, ImageDraw, ImageFont

OUT = os.path.join(os.path.dirname(__file__), "..", "app", "static", "img")
os.makedirs(OUT, exist_ok=True)

BG = "#1a1a2e"
ACCENT = "#d4a017"
RING_OPACITY = 90  # 0-255

def _best_font(size):
    for name in [
        "arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf",
        "LiberationSans-Bold.ttf", "segoeui.ttf",
    ]:
        try:
            return ImageFont.truetype(name, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def make_icon(size, filename):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx, cy = size // 2, size // 2
    r = int(size * 0.46)

    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=BG)

    stroke_w = max(2, size // 32)
    draw.ellipse(
        [cx - r, cy - r, cx + r, cy + r],
        outline=ACCENT, width=stroke_w,
    )

    inner_r = int(size * 0.34)
    inner_stroke = max(1, size // 76)
    ring_color = (212, 160, 23, RING_OPACITY)
    draw.ellipse(
        [cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r],
        outline=ring_color, width=inner_stroke,
    )

    font_size = int(size * 0.30)
    font = _best_font(font_size)
    text = "ND"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = cx - tw // 2 - bbox[0]
    ty = cy - th // 2 - bbox[1]
    draw.text((tx, ty), text, fill=ACCENT, font=font)

    out_path = os.path.join(OUT, filename)
    if filename.endswith(".ico"):
        sizes_ico = [(16, 16), (32, 32), (48, 48)]
        imgs = [img.resize(s, Image.LANCZOS) for s in sizes_ico]
        imgs[0].save(out_path, format="ICO", sizes=sizes_ico, append_images=imgs[1:])
    else:
        img.save(out_path, "PNG")
    print(f"  -> {out_path} ({size}x{size})")


def make_og_card():
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    cx, cy = W // 2, H // 2 - 30
    r = 100
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=BG, outline=ACCENT, width=5)
    inner_r = 72
    draw.ellipse(
        [cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r],
        outline=(212, 160, 23, RING_OPACITY), width=2,
    )
    font_nd = _best_font(62)
    bbox = draw.textbbox((0, 0), "ND", font=font_nd)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((cx - tw // 2 - bbox[0], cy - th // 2 - bbox[1]), "ND", fill=ACCENT, font=font_nd)

    font_title = _best_font(36)
    title = "Nickel & Dime"
    bbox = draw.textbbox((0, 0), title, font=font_title)
    tw = bbox[2] - bbox[0]
    draw.text((cx - tw // 2 - bbox[0], cy + r + 30), title, fill="#e2e8f0", font=font_title)

    font_sub = _best_font(20)
    sub = "The macro investor's command center"
    bbox = draw.textbbox((0, 0), sub, font=font_sub)
    tw = bbox[2] - bbox[0]
    draw.text((cx - tw // 2 - bbox[0], cy + r + 80), sub, fill="#94a3b8", font=font_sub)

    out_path = os.path.join(OUT, "og-card.png")
    img.save(out_path, "PNG")
    print(f"  -> {out_path} (1200x630)")


if __name__ == "__main__":
    print("Generating icons...")
    make_icon(512, "icon-512.png")
    make_icon(192, "icon-192.png")
    make_icon(180, "apple-touch-icon.png")
    make_icon(64, "favicon.ico")
    make_og_card()
    print("Done!")
