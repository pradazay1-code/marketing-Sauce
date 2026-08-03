#!/usr/bin/env python3
"""
Content Visual Generator — Aventis Marketing

Generates branded Instagram visuals (carousel slides, post images, reel covers,
story frames) using Pillow. Reads content JSON from generate_instagram.py and
produces ready-to-post images.

Optionally fetches stock photos from Unsplash or generates AI images via DALL-E.

Usage:
  python generate_content_visuals.py --client akira-real-estate --input instagram_calendar.json
  python generate_content_visuals.py --client akira-real-estate --input instagram_calendar.json --use-unsplash
  python generate_content_visuals.py --client akira-real-estate --input instagram_calendar.json --use-dalle
"""

import argparse
import json
import math
import os
import re
import sys
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# Default brand palette (overridden by client config)
# ---------------------------------------------------------------------------
DEFAULT_BRAND = {
    "name": "Client",
    "owner": "Owner",
    "primary": "#1a1a2e",
    "secondary": "#16213e",
    "accent": "#e2b04a",
    "text_light": "#ffffff",
    "text_muted": "#b0b0b0",
    "card_bg": "#0f3460",
    "gradient_start": "#1a1a2e",
    "gradient_end": "#0f3460",
}

AKIRA_BRAND = {
    "name": "Akira Real Estate",
    "owner": "Kunal Patel",
    "primary": "#1a1a2e",
    "secondary": "#16213e",
    "accent": "#e2b04a",
    "text_light": "#ffffff",
    "text_muted": "#a0a0b0",
    "card_bg": "#0f3460",
    "gradient_start": "#1a1a2e",
    "gradient_end": "#0f3460",
}

CLIENT_BRANDS = {
    "akira-real-estate": AKIRA_BRAND,
}

POST_SIZE = (1080, 1080)
STORY_SIZE = (1080, 1920)
REEL_COVER_SIZE = (1080, 1920)

# ---------------------------------------------------------------------------
# Font loading
# ---------------------------------------------------------------------------
FONT_PATHS = [
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
]


def _find_font(bold=False):
    keyword = "Bold" if bold else "Regular"
    for fp in FONT_PATHS:
        if keyword.lower() in fp.lower() and os.path.exists(fp):
            return fp
    for fp in FONT_PATHS:
        if os.path.exists(fp):
            return fp
    return None


def load_font(size, bold=False):
    path = _find_font(bold)
    if path:
        return ImageFont.truetype(path, size)
    return ImageFont.load_default()


FONT_TITLE = lambda sz=56: load_font(sz, bold=True)
FONT_BODY = lambda sz=36: load_font(sz, bold=False)
FONT_SMALL = lambda sz=24: load_font(sz, bold=False)
FONT_ACCENT = lambda sz=28: load_font(sz, bold=True)

# ---------------------------------------------------------------------------
# Emoji stripping — system fonts don't render emoji
# ---------------------------------------------------------------------------

EMOJI_REPLACEMENTS = {
    "✅": ">",   # ✅ → bullet
    "❌": "X",   # ❌ → X mark
    "\U0001f4cd": "", # 📍
    "\U0001f4ca": "", # 📊
    "\U0001f4c8": "", # 📈
    "\U0001f4e6": "", # 📦
    "⏱️": "", "⏱": "", # ⏱️
    "\U0001f4b0": "", # 💰
    "\U0001f535": ">", # 🔵
    "\U0001f7e2": ">", # 🟢
    "\U0001f3e0": "", # 🏠
    "\U0001f3e1": "", # 🏡
    "\U0001f389": "", # 🎉
    "\U0001f4f1": "", # 📱
    "\U0001f37d️": "", "\U0001f37d": "", # 🍽️
    "\U0001f697": "", # 🚗
    "\U0001f3eb": "", # 🏫
    "\U0001f4ac": "", # 💬
    "\U0001f4cc": "", # 📌
    "\U0001f511": "", # 🔑
    "\U0001f4a1": "", # 💡
    "\U0001f525": "", # 🔥
    "\U0001f449": ">", # 👉
    "\U0001f447": "",  # 👇
    "\U0001f38a": "", # 🎊
    "\U0001f4f2": "", # 📲
    "\U0001f4dd": "", # 📝
}

_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F1E0-\U0001F1FF"
    "\U00002702-\U000027B0"
    "\U0000FE00-\U0000FE0F"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\U00002600-\U000026FF"
    "‍️"
    "]+", flags=re.UNICODE
)


def strip_emoji(text):
    for char, repl in EMOJI_REPLACEMENTS.items():
        text = text.replace(char, repl)
    text = re.sub(r"[\d]️?⃣", "", text)
    text = _EMOJI_PATTERN.sub("", text)
    text = text.replace("$XXX,000", "$499,000")
    text = text.replace("$xxx,000", "$499,000")
    text = re.sub(r"  +", " ", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Color utilities
# ---------------------------------------------------------------------------

def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def lerp_color(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def draw_gradient(draw, width, height, color_start, color_end, direction="vertical"):
    c1, c2 = hex_to_rgb(color_start), hex_to_rgb(color_end)
    if direction == "vertical":
        for y in range(height):
            c = lerp_color(c1, c2, y / max(height - 1, 1))
            draw.line([(0, y), (width, y)], fill=c)
    else:
        for x in range(width):
            c = lerp_color(c1, c2, x / max(width - 1, 1))
            draw.line([(x, 0), (x, height)], fill=c)


def draw_rounded_rect(draw, xy, fill, radius=20):
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill)


# ---------------------------------------------------------------------------
# Decorative elements
# ---------------------------------------------------------------------------

def draw_corner_accents(draw, width, height, color, margin=50, length=70, thickness=3,
                        skip_bottom=False):
    c = hex_to_rgb(color) if isinstance(color, str) else color
    draw.rectangle([margin, margin, margin + length, margin + thickness], fill=c)
    draw.rectangle([margin, margin, margin + thickness, margin + length], fill=c)
    draw.rectangle([width - margin - length, margin, width - margin, margin + thickness], fill=c)
    draw.rectangle([width - margin - thickness, margin, width - margin, margin + length], fill=c)
    if not skip_bottom:
        bm = height - margin
        draw.rectangle([margin, bm - thickness, margin + length, bm], fill=c)
        draw.rectangle([margin, bm - length, margin + thickness, bm], fill=c)
        draw.rectangle([width - margin - length, bm - thickness, width - margin, bm], fill=c)
        draw.rectangle([width - margin - thickness, bm - length, width - margin, bm], fill=c)


def draw_diamond_separator(draw, y, width, color, size=8):
    c = hex_to_rgb(color) if isinstance(color, str) else color
    cx = width // 2
    draw.polygon([(cx, y - size), (cx + size, y), (cx, y + size), (cx - size, y)], fill=c)
    line_w = 80
    draw.rectangle([cx - line_w - 20, y - 1, cx - size - 10, y + 1], fill=c)
    draw.rectangle([cx + size + 10, y - 1, cx + line_w + 20, y + 1], fill=c)


def draw_pill_badge(draw, text, center_x, y, font, text_color, bg_color, pad_x=24, pad_y=8):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x0 = center_x - tw // 2 - pad_x
    x1 = center_x + tw // 2 + pad_x
    y0 = y
    y1 = y + th + pad_y * 2
    radius = (y1 - y0) // 2
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=bg_color)
    draw.text((center_x - tw // 2, y + pad_y), text, font=font, fill=text_color)
    return y1


def draw_accent_bar(draw, y, width, color, height=4, bar_fraction=0.3):
    c = hex_to_rgb(color) if isinstance(color, str) else color
    bar_w = int(width * bar_fraction)
    x0 = (width - bar_w) // 2
    draw.rectangle([x0, y, x0 + bar_w, y + height], fill=c)


def draw_left_accent_bar(draw, x, y, color, bar_width=120, height=4):
    c = hex_to_rgb(color) if isinstance(color, str) else color
    draw.rectangle([x, y, x + bar_width, y + height], fill=c)


# ---------------------------------------------------------------------------
# Text utilities
# ---------------------------------------------------------------------------

def wrap_text(text, font, max_width, draw):
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_centered_text(draw, text, y, font, fill, width):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    x = (width - tw) // 2
    draw.text((x, y), text, font=font, fill=fill)
    return bbox[3] - bbox[1]


def text_height(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[3] - bbox[1]


# ---------------------------------------------------------------------------
# Branding elements
# ---------------------------------------------------------------------------

def load_background_photo(photo_path, size):
    """Load a local photo and resize/crop to fit target size (cover behavior)."""
    if not photo_path or not os.path.exists(photo_path):
        return None
    try:
        img = Image.open(photo_path).convert("RGB")
        target_w, target_h = size
        src_w, src_h = img.size
        scale = max(target_w / src_w, target_h / src_h)
        new_w, new_h = int(src_w * scale), int(src_h * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - target_w) // 2
        top = (new_h - target_h) // 2
        return img.crop((left, top, left + target_w, top + target_h))
    except Exception as e:
        print(f"  [BG] Failed to load {photo_path}: {e}")
        return None


def generate_procedural_background(size, style="sunset_home", brand=None):
    """Generate a photo-style architectural background using PIL primitives.
    Styles: sunset_home, city_dusk, warm_interior, night_luxury."""
    import random
    w, h = size
    img = Image.new("RGB", size)
    draw = ImageDraw.Draw(img)

    if style == "sunset_home":
        for y in range(h):
            t = y / h
            if t < 0.55:
                r = int(20 + (255 - 20) * (t / 0.55) * 0.85)
                g = int(30 + (140 - 30) * (t / 0.55) * 0.75)
                b = int(60 + (90 - 60) * (t / 0.55) * 0.5)
            else:
                lt = (t - 0.55) / 0.45
                r = int(217 * (1 - lt) + 25 * lt)
                g = int(105 * (1 - lt) + 30 * lt)
                b = int(75 * (1 - lt) + 55 * lt)
            draw.line([(0, y), (w, y)], fill=(r, g, b))
        sun_y = int(h * 0.48)
        for r in range(120, 0, -2):
            alpha = 1 - (r / 120)
            fill = (int(255 * alpha + 220 * (1 - alpha)),
                    int(210 * alpha + 130 * (1 - alpha)),
                    int(150 * alpha + 90 * (1 - alpha)))
            draw.ellipse([w // 2 - r, sun_y - r, w // 2 + r, sun_y + r], fill=fill)
        skyline_y = int(h * 0.62)
        base_dark = (18, 22, 35)
        random.seed(42)
        x = 0
        while x < w:
            bw = random.randint(40, 90)
            bh = random.randint(60, 180)
            draw.rectangle([x, skyline_y - bh, x + bw, h], fill=base_dark)
            wy = skyline_y - bh + 12
            while wy < skyline_y - 8:
                wx = x + 6
                while wx < x + bw - 10:
                    if random.random() > 0.4:
                        draw.rectangle([wx, wy, wx + 6, wy + 8],
                                       fill=(240, 200, 120))
                    wx += 12
                wy += 14
            x += bw

    elif style == "city_dusk":
        for y in range(h):
            t = y / h
            r = int(15 + (60 - 15) * t)
            g = int(20 + (85 - 20) * t)
            b = int(50 + (140 - 50) * t)
            draw.line([(0, y), (w, y)], fill=(r, g, b))
        random.seed(7)
        for _ in range(30):
            sx = random.randint(0, w)
            sy = random.randint(0, int(h * 0.5))
            sr = random.randint(1, 3)
            draw.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=(255, 245, 220))
        skyline_y = int(h * 0.55)
        x = 0
        while x < w:
            bw = random.randint(50, 120)
            bh = random.randint(80, 240)
            base = (10, 15, 30)
            draw.rectangle([x, skyline_y - bh, x + bw, h], fill=base)
            wy = skyline_y - bh + 10
            while wy < skyline_y:
                wx = x + 4
                while wx < x + bw - 8:
                    if random.random() > 0.35:
                        c = (255, 210, 130) if random.random() > 0.3 else (200, 220, 255)
                        draw.rectangle([wx, wy, wx + 5, wy + 7], fill=c)
                    wx += 10
                wy += 12
            x += bw

    elif style == "warm_interior":
        for y in range(h):
            t = y / h
            r = int(45 + (95 - 45) * (1 - abs(t - 0.5) * 1.4))
            g = int(30 + (65 - 30) * (1 - abs(t - 0.5) * 1.4))
            b = int(25 + (50 - 25) * (1 - abs(t - 0.5) * 1.4))
            draw.line([(0, y), (w, y)], fill=(max(r, 20), max(g, 15), max(b, 15)))
        cx, cy = w // 2, int(h * 0.35)
        for r in range(int(w * 0.7), 0, -8):
            alpha = 1 - (r / (w * 0.7))
            alpha = alpha ** 2
            fill = (int(255 * alpha + 45 * (1 - alpha)),
                    int(190 * alpha + 30 * (1 - alpha)),
                    int(110 * alpha + 25 * (1 - alpha)))
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)

    elif style == "night_luxury":
        for y in range(h):
            t = y / h
            r = int(8 + (28 - 8) * t)
            g = int(12 + (35 - 12) * t)
            b = int(28 + (55 - 28) * t)
            draw.line([(0, y), (w, y)], fill=(r, g, b))
        accent = hex_to_rgb(brand["accent"]) if brand else (226, 176, 74)
        for i in range(20):
            y_line = int(h * (0.3 + i * 0.03))
            alpha = max(0.05, 0.3 - i * 0.015)
            c = tuple(int(accent[j] * alpha + 20 * (1 - alpha)) for j in range(3))
            draw.line([(0, y_line), (w, y_line)], fill=c, width=1)

    else:
        c_start = hex_to_rgb(brand["gradient_start"]) if brand else (26, 26, 46)
        c_end = hex_to_rgb(brand["gradient_end"]) if brand else (15, 52, 96)
        for y in range(h):
            t = y / (h - 1)
            c = lerp_color(c_start, c_end, t)
            draw.line([(0, y), (w, y)], fill=c)

    return img


def apply_dark_overlay(img, opacity_top=0.55, opacity_bottom=0.85, gradient=True):
    """Apply a dark gradient overlay to make text legible over photos."""
    w, h = img.size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    if gradient:
        for y in range(h):
            t = y / (h - 1)
            alpha = int(255 * (opacity_top + (opacity_bottom - opacity_top) * t))
            draw.line([(0, y), (w, y)], fill=(10, 12, 25, alpha))
    else:
        alpha = int(255 * opacity_top)
        draw.rectangle([0, 0, w, h], fill=(10, 12, 25, alpha))
    base = img.convert("RGBA")
    combined = Image.alpha_composite(base, overlay)
    return combined.convert("RGB")


def build_background(size, content, brand):
    """Build the background layer for a post/reel — photo, procedural, or gradient."""
    bg_photo = content.get("background_image") or content.get("bg_photo")
    if bg_photo:
        photo = load_background_photo(bg_photo, size)
        if photo:
            return apply_dark_overlay(photo, 0.55, 0.85)
    style = content.get("bg_style")
    if not style:
        pillar = content.get("pillar", "education")
        style_map = {
            "listing": "sunset_home",
            "market_stats": "night_luxury",
            "education": "city_dusk",
            "testimonial": "warm_interior",
            "community": "sunset_home",
            "behind_the_scenes": "night_luxury",
        }
        style = style_map.get(pillar, "night_luxury")
    procedural = generate_procedural_background(size, style, brand)
    return apply_dark_overlay(procedural, 0.4, 0.75)


# ---------------------------------------------------------------------------
# Original branding elements
# ---------------------------------------------------------------------------

def draw_branding_footer(draw, width, height, brand, fade_from=None):
    footer_h = 100
    fade_h = 40
    y_start = height - footer_h
    if fade_from:
        c_from = hex_to_rgb(fade_from) if isinstance(fade_from, str) else fade_from
    else:
        c_from = hex_to_rgb(brand["gradient_end"])
    c_to = hex_to_rgb(brand["primary"])
    for fy in range(fade_h):
        t = fy / max(fade_h - 1, 1)
        c = lerp_color(c_from, c_to, t)
        draw.line([(0, y_start - fade_h + fy), (width, y_start - fade_h + fy)], fill=c)
    draw.rectangle([0, y_start, width, height], fill=hex_to_rgb(brand["primary"]))
    draw.rectangle([0, y_start, width, y_start + 3], fill=hex_to_rgb(brand["accent"]))
    name_font = load_font(24, bold=True)
    name = brand.get("name", "")
    draw_centered_text(draw, name, y_start + 22, name_font,
                       hex_to_rgb(brand["accent"]), width)
    owner_font = load_font(18, bold=False)
    owner = brand.get("owner", "")
    draw_centered_text(draw, owner, y_start + 54, owner_font,
                       hex_to_rgb(brand["text_muted"]), width)


def draw_slide_number(draw, num, total, width, brand):
    font = load_font(22, bold=True)
    text = f"{num}/{total}"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    pad = 12
    x = width - tw - 50
    y = 35
    draw_rounded_rect(draw, (x - pad, y - 6, x + tw + pad, y + bbox[3] - bbox[1] + 6),
                      hex_to_rgb(brand["secondary"]), radius=10)
    draw.text((x, y), text, font=font, fill=hex_to_rgb(brand["accent"]))


PILLAR_DISPLAY = {
    "listing": "LISTING",
    "education": "EDUCATION",
    "community": "COMMUNITY",
    "behind_the_scenes": "BTS",
    "testimonial": "SUCCESS STORY",
    "market_stats": "MARKET DATA",
}


# ---------------------------------------------------------------------------
# CAROUSEL SLIDE GENERATORS
# ---------------------------------------------------------------------------

def generate_carousel_title_slide(title, brand, slide_num=1, total_slides=8, pillar="education"):
    img = Image.new("RGB", POST_SIZE)
    draw = ImageDraw.Draw(img)
    draw_gradient(draw, *POST_SIZE, brand["gradient_start"], brand["gradient_end"])

    accent = hex_to_rgb(brand["accent"])
    draw_corner_accents(draw, *POST_SIZE, accent, margin=45, length=65, thickness=3,
                        skip_bottom=True)

    badge_font = load_font(16, bold=True)
    badge_text = PILLAR_DISPLAY.get(pillar, "CONTENT")
    draw_pill_badge(draw, badge_text, POST_SIZE[0] // 2, 110, badge_font,
                    hex_to_rgb(brand["primary"]), accent, pad_x=20, pad_y=6)

    title = strip_emoji(title)
    font = FONT_TITLE(52)
    lines = wrap_text(title, font, 860, draw)
    block_h = sum(text_height(draw, l, font) + 16 for l in lines)
    y = (POST_SIZE[1] // 2) - (block_h // 2) - 20
    for line in lines:
        h = draw_centered_text(draw, line, y, font, hex_to_rgb(brand["text_light"]), POST_SIZE[0])
        y += h + 16

    y += 30
    draw_diamond_separator(draw, y, POST_SIZE[0], accent)

    y += 35
    swipe_font = load_font(24, bold=False)
    draw_centered_text(draw, "Swipe to learn more  >", y, swipe_font,
                       hex_to_rgb(brand["text_muted"]), POST_SIZE[0])

    draw_branding_footer(draw, *POST_SIZE, brand)
    draw_slide_number(draw, slide_num, total_slides, POST_SIZE[0], brand)
    return img


def generate_carousel_content_slide(number, heading, body_text, brand, slide_num, total_slides):
    img = Image.new("RGB", POST_SIZE)
    draw = ImageDraw.Draw(img)
    draw_gradient(draw, *POST_SIZE, brand["gradient_start"], brand["secondary"])

    accent = hex_to_rgb(brand["accent"])

    card_margin = 65
    card_top = 80
    card_bottom = POST_SIZE[1] - 120
    draw_rounded_rect(draw, (card_margin, card_top, POST_SIZE[0] - card_margin, card_bottom),
                      hex_to_rgb(brand["card_bg"]), radius=24)

    inner_x = card_margin + 40
    inner_w = POST_SIZE[0] - card_margin * 2 - 80

    circle_r = 32
    circle_x = inner_x + circle_r
    circle_y = card_top + 50 + circle_r
    draw.ellipse([circle_x - circle_r, circle_y - circle_r,
                  circle_x + circle_r, circle_y + circle_r],
                 fill=accent)
    num_font = load_font(36, bold=True)
    num_str = str(number)
    nbbox = draw.textbbox((0, 0), num_str, font=num_font)
    nw = nbbox[2] - nbbox[0]
    nh = nbbox[3] - nbbox[1]
    draw.text((circle_x - nw // 2, circle_y - nh // 2 - 2), num_str, font=num_font,
              fill=hex_to_rgb(brand["primary"]))

    heading = strip_emoji(heading)
    heading = re.sub(r"^[Xx>]\s+", "", heading)
    head_font = FONT_TITLE(38)
    head_lines = wrap_text(heading, head_font, inner_w, draw)
    y = card_top + 130
    for line in head_lines:
        draw.text((inner_x, y), line, font=head_font, fill=hex_to_rgb(brand["text_light"]))
        hh = draw.textbbox((0, 0), line, font=head_font)
        y += (hh[3] - hh[1]) + 10

    y += 14
    draw_left_accent_bar(draw, inner_x, y, accent, bar_width=100, height=3)
    y += 22

    body_text = strip_emoji(body_text)
    if body_text:
        body_font = FONT_BODY(28)
        body_lines = wrap_text(body_text, body_font, inner_w, draw)
        for line in body_lines[:8]:
            draw.text((inner_x, y), line, font=body_font, fill=hex_to_rgb(brand["text_muted"]))
            bh = draw.textbbox((0, 0), line, font=body_font)
            y += (bh[3] - bh[1]) + 10

    draw_branding_footer(draw, *POST_SIZE, brand, fade_from=brand["card_bg"])
    draw_slide_number(draw, slide_num, total_slides, POST_SIZE[0], brand)
    return img


def generate_carousel_cta_slide(cta_text, brand, owner, slide_num, total_slides):
    img = Image.new("RGB", POST_SIZE)
    draw = ImageDraw.Draw(img)
    draw_gradient(draw, *POST_SIZE, brand["gradient_end"], brand["gradient_start"])

    accent = hex_to_rgb(brand["accent"])
    draw_corner_accents(draw, *POST_SIZE, accent, margin=45, length=65, thickness=3,
                        skip_bottom=True)

    cta_text = strip_emoji(cta_text)
    cta_font = FONT_TITLE(44)
    cta_lines = wrap_text(cta_text, cta_font, 820, draw)
    block_h = sum(text_height(draw, l, cta_font) + 14 for l in cta_lines)
    total_block = block_h + 130
    y = (POST_SIZE[1] // 2) - (total_block // 2) - 30

    draw_accent_bar(draw, y - 20, POST_SIZE[0], accent, height=3, bar_fraction=0.4)

    y += 10
    for line in cta_lines:
        h = draw_centered_text(draw, line, y, cta_font,
                               hex_to_rgb(brand["text_light"]), POST_SIZE[0])
        y += h + 14

    y += 30
    draw_diamond_separator(draw, y, POST_SIZE[0], accent)

    y += 35
    owner_font = load_font(30, bold=True)
    draw_centered_text(draw, f"-- {owner}", y, owner_font, accent, POST_SIZE[0])
    y += 45
    brand_font = load_font(22, bold=False)
    draw_centered_text(draw, brand["name"], y, brand_font,
                       hex_to_rgb(brand["text_muted"]), POST_SIZE[0])

    draw_branding_footer(draw, *POST_SIZE, brand)
    draw_slide_number(draw, slide_num, total_slides, POST_SIZE[0], brand)
    return img


def generate_carousel_images(content, brand):
    slides = content.get("slides", [])
    title = content.get("title", "")
    pillar = content.get("pillar", "education")
    total = len(slides) + 2
    images = []

    images.append(("slide_01_title",
                    generate_carousel_title_slide(title, brand, 1, total, pillar)))

    for i, slide in enumerate(slides):
        slide_text = slide if isinstance(slide, str) else slide.get("text", str(slide))
        parts = slide_text.split("\n", 1)
        heading = parts[0].strip().lstrip("0123456789. ")
        body = parts[1].strip() if len(parts) > 1 else ""
        img = generate_carousel_content_slide(i + 1, heading, body, brand, i + 2, total)
        images.append((f"slide_{i+2:02d}", img))

    cta = content.get("cta", "DM me to get started.")
    owner = brand.get("owner", "")
    images.append((f"slide_{total:02d}_cta",
                    generate_carousel_cta_slide(cta, brand, owner, total, total)))

    return images


# ---------------------------------------------------------------------------
# POST IMAGE GENERATORS
# ---------------------------------------------------------------------------

def generate_post_image(content, brand):
    img = build_background(POST_SIZE, content, brand)
    draw = ImageDraw.Draw(img)
    pillar = content.get("pillar", "education")
    accent = hex_to_rgb(brand["accent"])

    if pillar == "listing":
        pass  # background already applied
        draw.rectangle([0, 0, POST_SIZE[0], 5], fill=accent)
        draw.rectangle([0, POST_SIZE[1] - 105, POST_SIZE[0], POST_SIZE[1] - 102], fill=accent)

        tag_font = load_font(18, bold=True)
        draw_pill_badge(draw, "JUST LISTED", 540, 55, tag_font,
                        hex_to_rgb(brand["primary"]), accent, pad_x=22, pad_y=8)

        hook = strip_emoji(content.get("hook", ""))
        if hook:
            hook_font = FONT_TITLE(40)
            hook_lines = wrap_text(hook, hook_font, 900, draw)
            y = 120
            for line in hook_lines:
                draw.text((80, y), line, font=hook_font, fill=hex_to_rgb(brand["text_light"]))
                h = draw.textbbox((0, 0), line, font=hook_font)
                y += (h[3] - h[1]) + 10
            y += 12
            draw_left_accent_bar(draw, 80, y, accent, bar_width=100, height=3)
            y += 24
        else:
            font = FONT_TITLE(44)
            draw.text((80, 100), "JUST LISTED", font=font, fill=accent)
            y = 180
            draw_left_accent_bar(draw, 80, y, accent, bar_width=100, height=3)
            y += 30

        caption = strip_emoji(content.get("caption", ""))
        caption_lines = caption.split("\n")
        if hook and caption_lines:
            hook_clean = hook.replace("$XXX,000", "$499,000")
            caption_lines = [l for l in caption_lines
                             if l.strip() and l.strip() != hook_clean.strip()]
        body_font = FONT_BODY(28)
        line_count = 0
        for bl in caption_lines[:15]:
            if not bl.strip():
                y += 10
                continue
            is_bullet = bl.strip().startswith(">")
            wrapped = wrap_text(bl, body_font, 880, draw)
            for wl in wrapped:
                c = hex_to_rgb(brand["text_light"]) if is_bullet else hex_to_rgb(brand["text_muted"])
                draw.text((80, y), wl, font=body_font, fill=c)
                h = draw.textbbox((0, 0), wl, font=body_font)
                y += (h[3] - h[1]) + 7
                line_count += 1
                if line_count > 16:
                    break
            if line_count > 16:
                break

    elif pillar in ("market_stats", "education"):
        card_m = 50
        card_overlay = Image.new("RGBA", POST_SIZE, (0, 0, 0, 0))
        card_draw = ImageDraw.Draw(card_overlay)
        card_c = hex_to_rgb(brand["secondary"])
        card_draw.rounded_rectangle(
            (card_m, card_m, POST_SIZE[0] - card_m, POST_SIZE[1] - 115),
            radius=28, fill=(card_c[0], card_c[1], card_c[2], 235))
        img = Image.alpha_composite(img.convert("RGBA"), card_overlay).convert("RGB")
        draw = ImageDraw.Draw(img)

        inner_x = card_m + 40
        inner_w = POST_SIZE[0] - card_m * 2 - 80

        badge_text = PILLAR_DISPLAY.get(pillar, "CONTENT")
        badge_font = load_font(14, bold=True)
        draw_pill_badge(draw, badge_text, POST_SIZE[0] // 2, card_m + 25, badge_font,
                        hex_to_rgb(brand["primary"]), accent, pad_x=18, pad_y=5)

        hook = strip_emoji(content.get("hook", content.get("caption", "")[:80]))
        font = FONT_TITLE(42)
        lines = wrap_text(hook, font, inner_w, draw)
        y = card_m + 85
        for line in lines:
            draw.text((inner_x, y), line, font=font, fill=hex_to_rgb(brand["text_light"]))
            h = draw.textbbox((0, 0), line, font=font)
            y += (h[3] - h[1]) + 10
        y += 14
        draw_left_accent_bar(draw, inner_x, y, accent, bar_width=100, height=3)
        y += 22

        caption = strip_emoji(content.get("caption", ""))
        body_font = FONT_BODY(26)
        line_count = 0
        for bl in caption.split("\n"):
            if not bl.strip():
                y += 10
                continue
            wrapped = wrap_text(bl, body_font, inner_w, draw)
            for wl in wrapped:
                if y > POST_SIZE[1] - 160:
                    break
                draw.text((inner_x, y), wl, font=body_font, fill=hex_to_rgb(brand["text_muted"]))
                h = draw.textbbox((0, 0), wl, font=body_font)
                y += (h[3] - h[1]) + 7
                line_count += 1
            if y > POST_SIZE[1] - 160:
                break

    elif pillar == "testimonial":
        draw_corner_accents(draw, *POST_SIZE, accent, margin=40, length=60, thickness=3,
                            skip_bottom=True)

        badge_font = load_font(14, bold=True)
        draw_pill_badge(draw, "SUCCESS STORY", POST_SIZE[0] // 2, 90, badge_font,
                        hex_to_rgb(brand["primary"]), accent, pad_x=18, pad_y=5)

        quote_font = FONT_TITLE(60)
        draw_centered_text(draw, "\"", 160, quote_font, accent, POST_SIZE[0])

        hook = strip_emoji(content.get("hook", content.get("caption", "")[:100]))
        font = FONT_TITLE(40)
        lines = wrap_text(hook, font, 860, draw)
        y = 230
        for line in lines:
            h = draw_centered_text(draw, line, y, font,
                                   hex_to_rgb(brand["text_light"]), POST_SIZE[0])
            y += h + 12

        y += 25
        draw_diamond_separator(draw, y, POST_SIZE[0], accent)
        y += 30

        caption = strip_emoji(content.get("caption", ""))
        body_font = FONT_BODY(26)
        line_count = 0
        for bl in caption.split("\n"):
            if not bl.strip():
                y += 8
                continue
            wrapped = wrap_text(bl, body_font, 860, draw)
            for wl in wrapped:
                if y > POST_SIZE[1] - 150:
                    break
                h = draw_centered_text(draw, wl, y, body_font,
                                       hex_to_rgb(brand["text_muted"]), POST_SIZE[0])
                y += h + 7
                line_count += 1
            if y > POST_SIZE[1] - 150:
                break

    elif pillar == "behind_the_scenes":
        pass  # background already applied

        badge_font = load_font(14, bold=True)
        draw_pill_badge(draw, "BEHIND THE SCENES", POST_SIZE[0] // 2, 65, badge_font,
                        hex_to_rgb(brand["primary"]), accent, pad_x=18, pad_y=5)

        hook = strip_emoji(content.get("hook", "A day in real estate"))
        font = FONT_TITLE(40)
        lines = wrap_text(hook, font, 900, draw)
        y = 130
        for line in lines:
            h = draw_centered_text(draw, line, y, font,
                                   hex_to_rgb(brand["text_light"]), POST_SIZE[0])
            y += h + 10
        y += 12
        draw_accent_bar(draw, y, POST_SIZE[0], accent, height=3, bar_fraction=0.25)
        y += 28

        caption = strip_emoji(content.get("caption", ""))
        body_font = FONT_BODY(26)
        for bl in caption.split("\n"):
            if not bl.strip():
                y += 8
                continue
            wrapped = wrap_text(bl, body_font, 880, draw)
            for wl in wrapped:
                if y > POST_SIZE[1] - 140:
                    break
                is_time = re.match(r"^\d{1,2}:\d{2}", wl.strip())
                c = hex_to_rgb(brand["text_light"]) if is_time else hex_to_rgb(brand["text_muted"])
                draw.text((90, y), wl, font=body_font, fill=c)
                h = draw.textbbox((0, 0), wl, font=body_font)
                y += (h[3] - h[1]) + 7
            if y > POST_SIZE[1] - 140:
                break

    else:
        draw_corner_accents(draw, *POST_SIZE, accent, margin=40, length=60, thickness=3,
                            skip_bottom=True)
        hook = strip_emoji(content.get("hook", content.get("caption", "")[:100]))
        font = FONT_TITLE(46)
        lines = wrap_text(hook, font, 860, draw)
        block_h = sum(text_height(draw, l, font) + 14 for l in lines)
        y = (POST_SIZE[1] // 2) - (block_h // 2) - 40
        for line in lines:
            h = draw_centered_text(draw, line, y, font,
                                   hex_to_rgb(brand["text_light"]), POST_SIZE[0])
            y += h + 14

        y += 30
        draw_diamond_separator(draw, y, POST_SIZE[0], accent)

    draw_branding_footer(draw, *POST_SIZE, brand)
    return [("post", img)]


# ---------------------------------------------------------------------------
# REEL COVER GENERATOR
# ---------------------------------------------------------------------------

def generate_reel_cover(content, brand):
    img = build_background(REEL_COVER_SIZE, content, brand)
    draw = ImageDraw.Draw(img)
    w, h = REEL_COVER_SIZE
    accent = hex_to_rgb(brand["accent"])

    draw_corner_accents(draw, w, h, accent, margin=50, length=80, thickness=3, skip_bottom=True)

    badge_font = load_font(16, bold=True)
    draw_pill_badge(draw, "REEL", w // 2, 110, badge_font,
                    hex_to_rgb(brand["primary"]), accent, pad_x=28, pad_y=8)

    play_y = 480
    outer_r = 55
    inner_r = 48
    cx = w // 2
    draw.ellipse([cx - outer_r, play_y - outer_r, cx + outer_r, play_y + outer_r],
                 outline=accent, width=4)
    draw.ellipse([cx - inner_r, play_y - inner_r, cx + inner_r, play_y + inner_r],
                 fill=None, outline=accent, width=2)
    tri = [(cx - 16, play_y - 24), (cx - 16, play_y + 24), (cx + 24, play_y)]
    draw.polygon(tri, fill=accent)

    title = strip_emoji(content.get("title", content.get("hook", "")))
    font = FONT_TITLE(50)
    lines = wrap_text(title, font, 880, draw)
    y = 600
    for line in lines:
        lh = draw_centered_text(draw, line, y, font, hex_to_rgb(brand["text_light"]), w)
        y += lh + 12

    y += 16
    draw_accent_bar(draw, y, w, accent, height=3, bar_fraction=0.2)
    y += 24

    hook = strip_emoji(content.get("hook", ""))
    if hook and hook != title:
        hook_font = FONT_BODY(30)
        hlines = wrap_text(hook, hook_font, 840, draw)
        for hl in hlines[:3]:
            lh = draw_centered_text(draw, hl, y, hook_font,
                                    hex_to_rgb(brand["text_muted"]), w)
            y += lh + 8

    scenes = content.get("scenes", [])
    if scenes:
        y += 30
        scene_font = load_font(22, bold=False)
        header_font = load_font(20, bold=True)
        draw_centered_text(draw, "SCENE BREAKDOWN", y, header_font, accent, w)
        y += 32
        for scene in scenes[:4]:
            scene_text = strip_emoji(scene.get("text", ""))
            if scene_text:
                time_str = scene.get("time", "")
                line = f"[{time_str}]  {scene_text}" if time_str else scene_text
                slines = wrap_text(line, scene_font, 800, draw)
                for sl in slines[:2]:
                    lh = draw_centered_text(draw, sl, y, scene_font,
                                            hex_to_rgb(brand["text_muted"]), w)
                    y += lh + 6
                y += 4

    duration = content.get("duration", "")
    if duration:
        dur_font = load_font(20, bold=True)
        dur_text = f"> {duration}"
        dbbox = draw.textbbox((0, 0), dur_text, font=dur_font)
        dtw = dbbox[2] - dbbox[0]
        dth = dbbox[3] - dbbox[1]
        dx = w // 2 - dtw // 2 - 16
        dur_y = h - 240
        draw_rounded_rect(draw, (dx, dur_y, dx + dtw + 32, dur_y + dth + 16),
                          hex_to_rgb(brand["secondary"]), radius=12)
        draw.text((dx + 16, dur_y + 8), dur_text, font=dur_font, fill=accent)

    bar_y = h - 180
    draw.rectangle([0, bar_y, w, bar_y + 3], fill=accent)
    owner_font = load_font(28, bold=True)
    draw_centered_text(draw, f"-- {brand['owner']}", bar_y + 28, owner_font, accent, w)
    brand_font = load_font(22, bold=False)
    draw_centered_text(draw, brand["name"], bar_y + 65, brand_font,
                       hex_to_rgb(brand["text_muted"]), w)

    return [("reel_cover", img)]


# ---------------------------------------------------------------------------
# STORY FRAME GENERATOR
# ---------------------------------------------------------------------------

def generate_story_frames(content, brand):
    frames = content.get("frames", [])
    images = []

    for i, frame in enumerate(frames):
        img = Image.new("RGB", STORY_SIZE)
        draw = ImageDraw.Draw(img)
        w, h = STORY_SIZE

        t = i / max(len(frames) - 1, 1)
        start = lerp_color(hex_to_rgb(brand["gradient_start"]),
                           hex_to_rgb(brand["accent"]), t * 0.25)
        end = hex_to_rgb(brand["gradient_end"])
        for y_px in range(h):
            c = lerp_color(start, end, y_px / (h - 1))
            draw.line([(0, y_px), (w, y_px)], fill=c)

        accent = hex_to_rgb(brand["accent"])
        frame_type = frame.get("type", "text")
        frame_content = strip_emoji(frame.get("content", ""))

        progress_y = 30
        bar_total_w = w - 120
        segment_w = bar_total_w // max(len(frames), 1)
        for si in range(len(frames)):
            sx = 60 + si * segment_w + 3
            sw = segment_w - 6
            bar_color = accent if si <= i else hex_to_rgb(brand["secondary"])
            draw_rounded_rect(draw, (sx, progress_y, sx + sw, progress_y + 4),
                              bar_color, radius=2)

        if frame_type == "text":
            font = FONT_TITLE(46)
            lines = wrap_text(frame_content, font, 880, draw)
            block_h = sum(text_height(draw, l, font) + 14 for l in lines)
            y = (h // 2) - (block_h // 2) - 20
            for line in lines:
                lh = draw_centered_text(draw, line, y, font,
                                        hex_to_rgb(brand["text_light"]), w)
                y += lh + 14

            sticker = frame.get("sticker", "")
            if sticker and sticker not in ("poll", "question_box"):
                st_text = strip_emoji(sticker)
                if st_text:
                    st_font = load_font(20, bold=False)
                    draw_centered_text(draw, st_text, h - 280, st_font, accent, w)

        elif frame_type == "poll":
            q_font = FONT_TITLE(40)
            q_lines = wrap_text(frame_content, q_font, 840, draw)
            y = 420
            for line in q_lines:
                lh = draw_centered_text(draw, line, y, q_font,
                                        hex_to_rgb(brand["text_light"]), w)
                y += lh + 12

            y += 50
            if " vs. " in frame_content:
                options = [o.strip() for o in frame_content.split(" vs. ")]
            elif " vs " in frame_content:
                options = [o.strip() for o in frame_content.split(" vs ")]
            else:
                options = [frame_content, ""]

            opt_font = FONT_BODY(28)
            for idx, opt in enumerate(options[:2]):
                opt = strip_emoji(opt)
                if not opt:
                    continue
                btn_x0, btn_x1 = 120, w - 120
                btn_y0, btn_y1 = y, y + 80
                draw_rounded_rect(draw, (btn_x0, btn_y0, btn_x1, btn_y1),
                                  hex_to_rgb(brand["secondary"]), radius=16)
                draw.rounded_rectangle([btn_x0, btn_y0, btn_x1, btn_y1],
                                       radius=16, outline=accent, width=2)
                bbox = draw.textbbox((0, 0), opt, font=opt_font)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]
                draw.text(((w - tw) // 2, y + (80 - th) // 2), opt, font=opt_font,
                          fill=hex_to_rgb(brand["text_light"]))
                label_font = load_font(16, bold=True)
                label = "A" if idx == 0 else "B"
                draw.text((btn_x0 + 20, y + 28), label, font=label_font, fill=accent)
                y += 100

        elif frame_type in ("question", "slider"):
            q_font = FONT_TITLE(40)
            q_lines = wrap_text(frame_content, q_font, 840, draw)
            y = 520
            for line in q_lines:
                lh = draw_centered_text(draw, line, y, q_font,
                                        hex_to_rgb(brand["text_light"]), w)
                y += lh + 12

            y += 40
            box_x0, box_x1 = 120, w - 120
            box_y0, box_y1 = y, y + 70
            draw_rounded_rect(draw, (box_x0, box_y0, box_x1, box_y1),
                              hex_to_rgb(brand["secondary"]), radius=14)
            draw.rounded_rectangle([box_x0, box_y0, box_x1, box_y1],
                                   radius=14, outline=accent, width=2)
            ph_font = FONT_BODY(24)
            draw.text((box_x0 + 24, box_y0 + 22), "Type your answer...",
                      font=ph_font, fill=hex_to_rgb(brand["text_muted"]))

        brand_font = load_font(20, bold=True)
        draw_centered_text(draw, brand["name"], h - 130, brand_font, accent, w)
        owner_font = load_font(16, bold=False)
        draw_centered_text(draw, brand["owner"], h - 104, owner_font,
                           hex_to_rgb(brand["text_muted"]), w)

        images.append((f"story_frame_{i+1:02d}", img))

    return images


# ---------------------------------------------------------------------------
# STOCK PHOTO FETCHER (Unsplash)
# ---------------------------------------------------------------------------

UNSPLASH_QUERIES = {
    "listing": "real estate house exterior modern",
    "education": "home buying mortgage planning",
    "community": "massachusetts neighborhood downtown",
    "behind_the_scenes": "real estate agent working office",
    "testimonial": "happy family new home keys",
    "market_stats": "real estate market data graph",
}


def fetch_unsplash_photo(pillar, city="", save_path=None):
    if not HAS_REQUESTS:
        print("[VISUAL] requests not installed, skipping Unsplash fetch")
        return None

    query = UNSPLASH_QUERIES.get(pillar, "real estate")
    if city:
        query += f" {city}"

    url = f"https://source.unsplash.com/1080x1080/?{query.replace(' ', ',')}"
    try:
        resp = requests.get(url, timeout=15, allow_redirects=True, headers={
            "User-Agent": "AventisMarketing/1.0"
        })
        if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("image"):
            if save_path:
                with open(save_path, "wb") as f:
                    f.write(resp.content)
                print(f"  [PHOTO] Saved stock photo: {save_path}")
                return save_path
    except Exception as e:
        print(f"  [PHOTO] Unsplash fetch failed: {e}")
    return None


# ---------------------------------------------------------------------------
# DALL-E IMAGE GENERATOR (optional)
# ---------------------------------------------------------------------------

def generate_dalle_image(visual_description, save_path, size="1024x1024"):
    if not HAS_OPENAI:
        print("[VISUAL] openai not installed, skipping DALL-E generation")
        return None

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("[VISUAL] OPENAI_API_KEY not set, skipping DALL-E generation")
        return None

    try:
        client = OpenAI(api_key=api_key)
        prompt = (
            f"Professional Instagram social media image for a real estate agent. "
            f"{visual_description}. "
            f"Clean, modern aesthetic. High quality photography style. No text overlay."
        )
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt[:4000],
            size=size,
            quality="standard",
            n=1,
        )
        image_url = response.data[0].url
        img_resp = requests.get(image_url, timeout=30)
        if img_resp.status_code == 200:
            with open(save_path, "wb") as f:
                f.write(img_resp.content)
            print(f"  [DALL-E] Generated image: {save_path}")
            return save_path
    except Exception as e:
        print(f"  [DALL-E] Generation failed: {e}")
    return None


# ---------------------------------------------------------------------------
# MAIN PIPELINE
# ---------------------------------------------------------------------------

def get_brand(client_name):
    if client_name in CLIENT_BRANDS:
        return CLIENT_BRANDS[client_name]
    summary_path = os.path.join(BASE_DIR, "clients", client_name, "CLIENT_SUMMARY.md")
    brand = dict(DEFAULT_BRAND)
    if os.path.exists(summary_path):
        with open(summary_path) as f:
            text = f.read()
        name_match = re.search(r"\*\*Name:\*\*\s*(.+)", text)
        if name_match:
            brand["name"] = name_match.group(1).strip()
        owner_match = re.search(r"\*\*Owner:\*\*\s*(.+)", text)
        if owner_match:
            brand["owner"] = owner_match.group(1).strip()
    return brand


def process_content_item(item, brand, output_dir, use_unsplash=False, use_dalle=False):
    content_type = item.get("type", item.get("content_type", "post")).lower()
    day_label = item.get("date", item.get("day", ""))
    pillar = item.get("pillar", "education")

    content = item.get("content", item)
    if isinstance(content, dict) and "pillar" not in content:
        content["pillar"] = pillar

    safe_label = re.sub(r"[^a-zA-Z0-9]", "_", str(day_label))[:20]
    item_dir = os.path.join(output_dir, f"{safe_label}_{content_type}_{pillar}")
    os.makedirs(item_dir, exist_ok=True)

    generated_files = []

    if content_type == "carousel":
        images = generate_carousel_images(content, brand)
        for name, im in images:
            path = os.path.join(item_dir, f"{name}.png")
            im.save(path, "PNG", quality=95)
            generated_files.append(path)
            print(f"  [CAROUSEL] {path}")

    elif content_type == "reel":
        images = generate_reel_cover(content, brand)
        for name, im in images:
            path = os.path.join(item_dir, f"{name}.png")
            im.save(path, "PNG", quality=95)
            generated_files.append(path)
            print(f"  [REEL] {path}")

    elif content_type == "story":
        images = generate_story_frames(content, brand)
        for name, im in images:
            path = os.path.join(item_dir, f"{name}.png")
            im.save(path, "PNG", quality=95)
            generated_files.append(path)
            print(f"  [STORY] {path}")

    else:
        images = generate_post_image(content, brand)
        for name, im in images:
            path = os.path.join(item_dir, f"{name}.png")
            im.save(path, "PNG", quality=95)
            generated_files.append(path)
            print(f"  [POST] {path}")

    if use_unsplash and content_type in ("post", "carousel"):
        city = content.get("city", "")
        photo_path = os.path.join(item_dir, "stock_photo.jpg")
        fetch_unsplash_photo(pillar, city, photo_path)

    if use_dalle and content_type in ("post",):
        visual_desc = content.get("suggested_visual", "")
        if visual_desc:
            dalle_path = os.path.join(item_dir, "ai_generated.png")
            generate_dalle_image(visual_desc, dalle_path)

    meta = {
        "type": content_type,
        "pillar": pillar,
        "date": day_label,
        "files": generated_files,
        "caption": content.get("caption", ""),
        "hashtags": content.get("hashtags", []),
    }
    meta_path = os.path.join(item_dir, "metadata.json")
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    return generated_files


def process_calendar(calendar_data, brand, output_dir, use_unsplash=False, use_dalle=False):
    all_files = []
    items = calendar_data if isinstance(calendar_data, list) else calendar_data.get("calendar", [])

    for i, item in enumerate(items):
        print(f"\n--- Day {i+1} ---")
        files = process_content_item(item, brand, output_dir, use_unsplash, use_dalle)
        all_files.extend(files)

    return all_files


def main():
    parser = argparse.ArgumentParser(description="Generate branded Instagram visuals")
    parser.add_argument("--client", required=True, help="Client folder name (e.g. akira-real-estate)")
    parser.add_argument("--input", required=True, help="Input JSON file (content calendar or single post)")
    parser.add_argument("--output", help="Output directory (default: clients/{client}/content/visuals/)")
    parser.add_argument("--use-unsplash", action="store_true", help="Fetch stock photos from Unsplash")
    parser.add_argument("--use-dalle", action="store_true", help="Generate AI images via DALL-E 3")
    args = parser.parse_args()

    brand = get_brand(args.client)

    input_path = args.input
    if not os.path.isabs(input_path):
        input_path = os.path.join(BASE_DIR, "clients", args.client, "content", input_path)

    if not os.path.exists(input_path):
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)

    with open(input_path) as f:
        data = json.load(f)

    output_dir = args.output or os.path.join(BASE_DIR, "clients", args.client, "content", "visuals")
    os.makedirs(output_dir, exist_ok=True)

    print(f"Brand: {brand['name']}")
    print(f"Input: {input_path}")
    print(f"Output: {output_dir}")
    print(f"Unsplash: {'ON' if args.use_unsplash else 'OFF'}")
    print(f"DALL-E: {'ON' if args.use_dalle else 'OFF'}")

    if isinstance(data, list):
        files = process_calendar(data, brand, output_dir, args.use_unsplash, args.use_dalle)
    elif "calendar" in data:
        files = process_calendar(data["calendar"], brand, output_dir, args.use_unsplash, args.use_dalle)
    else:
        files = process_content_item(data, brand, output_dir, args.use_unsplash, args.use_dalle)

    print(f"\n{'='*50}")
    print(f"Generated {len(files)} images in {output_dir}")


if __name__ == "__main__":
    main()
