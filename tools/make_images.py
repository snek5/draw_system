"""Generate the A6 draw system images in fallback/static/img.

    python tools/make_images.py fallback/static/img

Needs Pillow and the Inter font (Fedora: `dnf install rsms-inter-fonts`;
set FONT_BOLD / FONT_SEMI below if it lives elsewhere).
"""
import sys
from PIL import Image, ImageDraw, ImageFont

out = sys.argv[1] if len(sys.argv) > 1 else "fallback/static/img"
PURPLE = (136, 24, 97)        # #881861, matches --bibd-purple in app.css
YELLOW = (234, 202, 60)       # #EACA3C
FONT_BOLD = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"
FONT_SEMI = "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"
S = 2  # draw at 2x so the logo stays crisp on high-DPI screens


def badge(size, radius, font_size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=PURPLE)
    font = ImageFont.truetype(FONT_BOLD, font_size)
    d.text((size / 2, size / 2), "A6", font=font, fill="white", anchor="mm")
    # small yellow accent bar under the text
    bar_w, bar_h = size * 0.34, max(2, size * 0.05)
    y = size * 0.79
    d.rounded_rectangle([size / 2 - bar_w / 2, y, size / 2 + bar_w / 2, y + bar_h],
                        radius=bar_h / 2, fill=YELLOW)
    return img


# Logo: badge + "Draw System", 292x113 display size (same as the old logo)
W, H = 292 * S, 113 * S
logo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
b = badge(96 * S, 22 * S, 50 * S)
logo.paste(b, (6 * S, (H - b.height) // 2), b)
d = ImageDraw.Draw(logo)
x = 6 * S + b.width + 16 * S
d.text((x, H / 2 - 2 * S), "Draw", font=ImageFont.truetype(FONT_BOLD, 34 * S), fill=PURPLE, anchor="ls")
d.text((x, H / 2 + 30 * S), "System", font=ImageFont.truetype(FONT_SEMI, 30 * S), fill=PURPLE, anchor="ls")
logo = logo.crop(logo.getbbox())
pad = 4 * S
framed = Image.new("RGBA", (logo.width + 2 * pad, logo.height + 2 * pad), (0, 0, 0, 0))
framed.paste(logo, (pad, pad), logo)
framed.save(f"{out}/a6_logo.png", optimize=True)

# Favicon
badge(64, 14, 32).save(f"{out}/a6_icon.png", optimize=True)

# Background: white at the top fading to warm yellow, like the old one
BW, BH = 1920, 1080
bg = Image.new("RGB", (BW, BH))
px = bg.load()
top, bottom = (255, 255, 255), (255, 214, 10)
for y in range(BH):
    t = (y / (BH - 1)) ** 1.6
    row = tuple(round(a + (c - a) * t) for a, c in zip(top, bottom))
    for xx in range(BW):
        px[xx, y] = row
bg.save(f"{out}/a6_bg.png", optimize=True)
print(framed.size)
