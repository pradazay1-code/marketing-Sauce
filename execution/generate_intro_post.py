#!/usr/bin/env python3
"""Generate an Instagram introduction post for Akira Real Estate."""

import os
import sys
from PIL import Image, ImageDraw, ImageFont

SIZE = (1080, 1080)

# Colors matched from the actual Akira Real Estate logo
NAVY = (21, 43, 94)       # Dark navy - "Akira" text
TEAL = (74, 164, 204)     # Light blue/teal - "REAL ESTATE", roof
GOLD = (242, 200, 61)     # Gold/yellow - window accent
WHITE = (255, 255, 255)
OFF_WHITE = (245, 247, 250)
DARK_BG = (16, 24, 48)    # Very dark navy for background
MID_BG = (22, 36, 72)     # Mid navy
MUTED = (140, 160, 190)   # Muted text

FONT_PATHS = [
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

LOGO_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "clients", "akira-real-estate", "logo.png"
)


def find_font(bold=False):
    keyword = "Bold" if bold else "Regular"
    for fp in FONT_PATHS:
        if keyword.lower() in fp.lower() and os.path.exists(fp):
            return fp
    for fp in FONT_PATHS:
        if os.path.exists(fp):
            return fp
    return None


def ft(size, bold=False):
    path = find_font(bold)
    if path:
        return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def lerp(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def center(draw, text, y, fnt, fill, w):
    bbox = draw.textbbox((0, 0), text, font=fnt)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text(((w - tw) // 2, y), text, font=fnt, fill=fill)
    return th


def diamond(draw, cx, y, color, sz=7):
    draw.polygon([(cx, y-sz), (cx+sz, y), (cx, y+sz), (cx-sz, y)], fill=color)
    lw = 70
    draw.rectangle([cx-lw-18, y-1, cx-sz-8, y+1], fill=color)
    draw.rectangle([cx+sz+8, y-1, cx+lw+18, y+1], fill=color)


def corners(draw, w, h, color, m=40, l=70, t=3):
    for (x0, y0, dx, dy) in [
        (m, m, 1, 1), (w-m, m, -1, 1), (m, h-m, 1, -1), (w-m, h-m, -1, -1)
    ]:
        xe = x0 + dx * l
        ye = y0 + dy * l
        hx = min(x0, xe)
        hy = min(y0, ye)
        draw.rectangle([hx, min(y0, y0+dy*t), hx+abs(xe-x0), min(y0, y0+dy*t)+t], fill=color)
        draw.rectangle([min(x0, x0+dx*t), hy, min(x0, x0+dx*t)+t, hy+abs(ye-y0)], fill=color)


def place_logo(img, draw, w, y_start):
    """Place the logo image if it exists, otherwise render text logo."""
    if os.path.exists(LOGO_PATH):
        logo = Image.open(LOGO_PATH).convert("RGBA")
        max_w, max_h = 500, 220
        logo.thumbnail((max_w, max_h), Image.LANCZOS)

        # White background card for logo
        card_pad = 30
        lw, lh = logo.size
        card_w = lw + card_pad * 2
        card_h = lh + card_pad * 2
        cx = (w - card_w) // 2
        cy = y_start
        draw.rounded_rectangle([cx, cy, cx + card_w, cy + card_h],
                               radius=16, fill=WHITE)
        paste_x = cx + card_pad
        paste_y = cy + card_pad
        img.paste(logo, (paste_x, paste_y), logo)
        return cy + card_h + 20
    else:
        return render_text_logo(draw, w, y_start)


def render_text_logo(draw, w, y):
    """Render a text-based logo matching the Akira brand."""
    # Horizontal bar
    bar_w = 200
    draw.rectangle([(w-bar_w)//2, y, (w+bar_w)//2, y+2], fill=TEAL)
    y += 18

    # "Akira" in large navy
    logo_f = ft(68, bold=True)
    th = center(draw, "Akira", y, logo_f, NAVY, w)

    # Small house roof above the "i" — approximate position
    bbox = draw.textbbox((0, 0), "Akira", font=logo_f)
    text_w = bbox[2] - bbox[0]
    text_x = (w - text_w) // 2
    # "i" is roughly at 57% of "Akira" width
    i_x = text_x + int(text_w * 0.57)
    roof_top = y - 8
    roof_span = 28
    draw.line([(i_x - roof_span, y + 8), (i_x, roof_top), (i_x + roof_span, y + 8)],
              fill=TEAL, width=4)
    # Gold window dot
    draw.rectangle([i_x - 4, y + 2, i_x + 4, y + 10], fill=GOLD)

    y += th + 8

    # "REAL ESTATE" letter-spaced in teal
    spaced = "R E A L   E S T A T E"
    center(draw, spaced, y, ft(18, bold=True), TEAL, w)
    y += 28

    # Horizontal bar
    draw.rectangle([(w-bar_w)//2, y, (w+bar_w)//2, y+2], fill=TEAL)
    y += 30
    return y


def main():
    img = Image.new("RGB", SIZE)
    draw = ImageDraw.Draw(img)
    w, h = SIZE

    # Gradient background
    for py in range(h):
        c = lerp(DARK_BG, MID_BG, py / (h - 1))
        draw.line([(0, py), (w, py)], fill=c)

    # Top accent bar
    draw.rectangle([0, 0, w, 4], fill=TEAL)

    # Corner accents
    corners(draw, w, h, TEAL, m=38, l=65, t=3)

    # --- Logo ---
    y = place_logo(img, draw, w, 70)
    y += 16

    # --- "Meet Your Agent" badge ---
    badge_f = ft(15, bold=True)
    badge_text = "MEET YOUR AGENT"
    bb = draw.textbbox((0, 0), badge_text, font=badge_f)
    btw, bth = bb[2]-bb[0], bb[3]-bb[1]
    bx = (w - btw) // 2 - 20
    draw.rounded_rectangle([bx, y, bx + btw + 40, y + bth + 16],
                           radius=(bth+16)//2, fill=TEAL)
    draw.text((bx + 20, y + 8), badge_text, font=badge_f, fill=WHITE)
    y += bth + 52

    # --- Owner name ---
    name_f = ft(54, bold=True)
    th = center(draw, "Kunal Patel", y, name_f, WHITE, w)
    y += th + 16

    # Title
    center(draw, "Licensed Real Estate Agent  |  Massachusetts", y, ft(21, bold=False), MUTED, w)
    y += 48

    # Diamond separator
    diamond(draw, w//2, y, TEAL)
    y += 50

    # --- Services ---
    services = [
        "Residential Buying & Selling",
        "First-Time Homebuyers",
        "Investment Properties",
        "Luxury Listings",
    ]
    svc_f = ft(28, bold=False)
    bullet_f = ft(28, bold=True)
    for svc in services:
        full = f">  {svc}"
        bb = draw.textbbox((0, 0), full, font=svc_f)
        tw = bb[2] - bb[0]
        th = bb[3] - bb[1]
        sx = (w - tw) // 2
        draw.text((sx, y), ">", font=bullet_f, fill=GOLD)
        arrow_w = draw.textbbox((0, 0), ">  ", font=svc_f)[2]
        draw.text((sx + arrow_w, y), svc, font=svc_f, fill=WHITE)
        y += th + 22

    y += 28
    diamond(draw, w//2, y, TEAL)
    y += 44

    # --- Service areas ---
    center(draw, "SERVING ALL OF MASSACHUSETTS", y, ft(16, bold=True), TEAL, w)
    y += 36

    areas = "Boston  |  Worcester  |  Springfield  |  South Shore"
    center(draw, areas, y, ft(19, bold=False), MUTED, w)
    y += 50

    # --- CTA ---
    cta_pad = 18
    cta_f = ft(28, bold=True)
    cta_text = "Ready to make a move?"
    cbb = draw.textbbox((0, 0), cta_text, font=cta_f)
    ctw, cth = cbb[2]-cbb[0], cbb[3]-cbb[1]
    cx0 = (w - ctw) // 2 - 32
    draw.rounded_rectangle([cx0, y - 8, cx0 + ctw + 64, y + cth + cta_pad + 8],
                           radius=14, outline=TEAL, width=2)
    center(draw, cta_text, y + cta_pad // 2, cta_f, WHITE, w)
    y += cth + cta_pad + 32

    center(draw, "DM me or visit akirarealestateagency.com", y, ft(21, bold=False), TEAL, w)

    # --- Footer ---
    footer_h = 85
    fy = h - footer_h
    for fi in range(30):
        t = fi / 29
        c = lerp(MID_BG, DARK_BG, t)
        draw.line([(0, fy-30+fi), (w, fy-30+fi)], fill=c)
    draw.rectangle([0, fy, w, h], fill=DARK_BG)
    draw.rectangle([0, fy, w, fy+3], fill=TEAL)
    center(draw, "Akira Real Estate", fy + 20, ft(22, bold=True), TEAL, w)
    center(draw, "Kunal Patel  |  akirarealestateagency.com", fy + 48, ft(15, bold=False), MUTED, w)
    draw.rectangle([0, h-4, w, h], fill=TEAL)

    # Save
    out_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "clients", "akira-real-estate", "content", "visuals", "intro_post"
    )
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "intro_post.png")
    img.save(out_path, "PNG", quality=95)
    print(f"Saved: {out_path}")

    caption = """Meet your Massachusetts real estate expert.

Hi, I'm Kunal Patel -- licensed real estate agent and founder of Akira Real Estate.

Whether you're buying your first home, selling a property, or looking for your next investment -- I'm here to guide you every step of the way.

What I do:
> Residential Buying & Selling
> First-Time Homebuyer Guidance
> Investment Properties
> Luxury Listings

Serving all of Massachusetts -- Boston, Worcester, Springfield, South Shore, Metro West, and beyond.

Ready to make a move? Let's connect.
DM me or visit akirarealestateagency.com

-- Kunal Patel
Akira Real Estate

#realestate #realestateagent #massachusettsrealestate #marealestate #bostonrealestate #firsttimehomebuyer #homebuyertips #realtor #homebuying #investmentproperty #luxuryrealestate #masshomes #newenglandrealestate #realtorlife #realestatelife #homebuyersguide #sellingyourhome #housingmarket #dreamhome #househunting #southshorema #metrowestma #bostonhomes #newhome #property"""

    caption_path = os.path.join(out_dir, "caption.txt")
    with open(caption_path, "w") as f:
        f.write(caption)
    print(f"Saved: {caption_path}")


if __name__ == "__main__":
    main()
