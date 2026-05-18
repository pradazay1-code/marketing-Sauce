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

# Instagram dimensions
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
# Color utilities
# ---------------------------------------------------------------------------

def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def lerp_color(c1, c2, t):
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
# Text wrapping
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

# ---------------------------------------------------------------------------
# Branding elements
# ---------------------------------------------------------------------------

def draw_accent_bar(draw, y, width, color, height=4):
    bar_w = int(width * 0.3)
    x0 = (width - bar_w) // 2
    draw.rectangle([x0, y, x0 + bar_w, y + height], fill=hex_to_rgb(color))


def draw_branding_footer(draw, width, height, brand):
    footer_h = 80
    y = height - footer_h
    draw.rectangle([0, y, width, height], fill=hex_to_rgb(brand["primary"]))
    draw_accent_bar(draw, y, width, brand["accent"], height=3)
    font = load_font(22, bold=True)
    name = brand.get("name", "")
    bbox = draw.textbbox((0, 0), name, font=font)
    tw = bbox[2] - bbox[0]
    draw.text(((width - tw) // 2, y + 25), name, font=font, fill=hex_to_rgb(brand["accent"]))


def draw_slide_number(draw, num, total, width, brand):
    font = load_font(20, bold=False)
    text = f"{num}/{total}"
    bbox = draw.textbbox((0, 0), text, font=font)
    draw.text((width - bbox[2] + bbox[0] - 40, 30), text, font=font,
              fill=hex_to_rgb(brand["text_muted"]))

# ---------------------------------------------------------------------------
# CAROUSEL SLIDE GENERATORS
# ---------------------------------------------------------------------------

def generate_carousel_title_slide(title, brand, slide_num=1, total_slides=8):
    img = Image.new("RGB", POST_SIZE)
    draw = ImageDraw.Draw(img)
    draw_gradient(draw, *POST_SIZE, brand["gradient_start"], brand["gradient_end"])

    accent = hex_to_rgb(brand["accent"])
    draw.rectangle([80, 80, 1000, 84], fill=accent)

    font = FONT_TITLE(52)
    lines = wrap_text(title, font, 900, draw)
    y = POST_SIZE[1] // 2 - len(lines) * 35
    for line in lines:
        h = draw_centered_text(draw, line, y, font, hex_to_rgb(brand["text_light"]), POST_SIZE[0])
        y += h + 16

    y += 30
    swipe_font = load_font(26, bold=False)
    draw_centered_text(draw, "Swipe to learn more →", y, swipe_font, hex_to_rgb(brand["text_muted"]), POST_SIZE[0])

    draw_branding_footer(draw, *POST_SIZE, brand)
    draw_slide_number(draw, slide_num, total_slides, POST_SIZE[0], brand)
    return img


def generate_carousel_content_slide(number, heading, body_text, brand, slide_num, total_slides):
    img = Image.new("RGB", POST_SIZE)
    draw = ImageDraw.Draw(img)
    draw_gradient(draw, *POST_SIZE, brand["gradient_start"], brand["secondary"])

    accent = hex_to_rgb(brand["accent"])

    num_font = FONT_TITLE(72)
    num_str = str(number)
    draw.text((80, 70), num_str, font=num_font, fill=accent)

    bbox = draw.textbbox((0, 0), num_str, font=num_font)
    num_w = bbox[2] - bbox[0]
    draw.rectangle([80, 160, 80 + num_w, 164], fill=accent)

    head_font = FONT_TITLE(40)
    head_lines = wrap_text(heading, head_font, 880, draw)
    y = 200
    for line in head_lines:
        draw.text((80, y), line, font=head_font, fill=hex_to_rgb(brand["text_light"]))
        hh = draw.textbbox((0, 0), line, font=head_font)
        y += (hh[3] - hh[1]) + 12

    y += 30

    body_font = FONT_BODY(30)
    body_lines = wrap_text(body_text, body_font, 880, draw)
    for line in body_lines:
        draw.text((80, y), line, font=body_font, fill=hex_to_rgb(brand["text_muted"]))
        bh = draw.textbbox((0, 0), line, font=body_font)
        y += (bh[3] - bh[1]) + 10

    draw_branding_footer(draw, *POST_SIZE, brand)
    draw_slide_number(draw, slide_num, total_slides, POST_SIZE[0], brand)
    return img


def generate_carousel_cta_slide(cta_text, brand, owner, slide_num, total_slides):
    img = Image.new("RGB", POST_SIZE)
    draw = ImageDraw.Draw(img)
    draw_gradient(draw, *POST_SIZE, brand["gradient_end"], brand["gradient_start"])

    accent = hex_to_rgb(brand["accent"])
    y = POST_SIZE[1] // 2 - 120

    draw_accent_bar(draw, y - 40, POST_SIZE[0], brand["accent"])

    cta_font = FONT_TITLE(44)
    cta_lines = wrap_text(cta_text, cta_font, 850, draw)
    for line in cta_lines:
        h = draw_centered_text(draw, line, y, cta_font, hex_to_rgb(brand["text_light"]), POST_SIZE[0])
        y += h + 14

    y += 40
    owner_font = load_font(28, bold=True)
    draw_centered_text(draw, f"— {owner}", y, owner_font, accent, POST_SIZE[0])
    y += 45
    brand_font = load_font(24, bold=False)
    draw_centered_text(draw, brand["name"], y, brand_font, hex_to_rgb(brand["text_muted"]), POST_SIZE[0])

    draw_branding_footer(draw, *POST_SIZE, brand)
    draw_slide_number(draw, slide_num, total_slides, POST_SIZE[0], brand)
    return img


def generate_carousel_images(content, brand):
    slides = content.get("slides", [])
    title = content.get("title", "")
    total = len(slides) + 2
    images = []

    images.append(("slide_01_title", generate_carousel_title_slide(title, brand, 1, total)))

    for i, slide in enumerate(slides):
        slide_text = slide if isinstance(slide, str) else slide.get("text", str(slide))
        parts = slide_text.split("\n", 1)
        heading = parts[0].strip().lstrip("0123456789. ")
        body = parts[1].strip() if len(parts) > 1 else ""
        img = generate_carousel_content_slide(i + 1, heading, body, brand, i + 2, total)
        images.append((f"slide_{i+2:02d}", img))

    cta = content.get("cta", "DM me to get started.")
    owner = brand.get("owner", "")
    images.append((f"slide_{total:02d}_cta", generate_carousel_cta_slide(cta, brand, owner, total, total)))

    return images

# ---------------------------------------------------------------------------
# POST IMAGE GENERATORS
# ---------------------------------------------------------------------------

def generate_post_image(content, brand):
    img = Image.new("RGB", POST_SIZE)
    draw = ImageDraw.Draw(img)

    pillar = content.get("pillar", "education")

    if pillar in ("market_stats", "education"):
        draw_gradient(draw, *POST_SIZE, brand["primary"], brand["card_bg"])
        accent = hex_to_rgb(brand["accent"])
        draw_rounded_rect(draw, (60, 60, 1020, 920), hex_to_rgb(brand["secondary"]), radius=30)

        hook = content.get("hook", content.get("caption", "")[:80])
        font = FONT_TITLE(48)
        lines = wrap_text(hook, font, 850, draw)
        y = 120
        for line in lines:
            draw.text((110, y), line, font=font, fill=hex_to_rgb(brand["text_light"]))
            h = draw.textbbox((0, 0), line, font=font)
            y += (h[3] - h[1]) + 14
        y += 20
        draw.rectangle([110, y, 400, y + 4], fill=accent)

        caption = content.get("caption", "")
        body_lines = caption.split("\n")
        body_font = FONT_BODY(28)
        y += 30
        line_count = 0
        for bl in body_lines:
            if not bl.strip():
                y += 14
                continue
            wrapped = wrap_text(bl, body_font, 820, draw)
            for wl in wrapped:
                draw.text((110, y), wl, font=body_font, fill=hex_to_rgb(brand["text_muted"]))
                h = draw.textbbox((0, 0), wl, font=body_font)
                y += (h[3] - h[1]) + 8
                line_count += 1
                if line_count > 14:
                    break
            if line_count > 14:
                break

    elif pillar == "listing":
        draw_gradient(draw, *POST_SIZE, "#0a0a14", brand["primary"])
        accent = hex_to_rgb(brand["accent"])
        draw.rectangle([0, 0, POST_SIZE[0], 6], fill=accent)

        font = FONT_TITLE(44)
        draw.text((80, 60), "JUST LISTED", font=font, fill=accent)
        y = 140
        draw.rectangle([80, y, 400, y + 3], fill=accent)
        y += 30

        caption = content.get("caption", "")
        body_font = FONT_BODY(30)
        for line in caption.split("\n")[:12]:
            if not line.strip():
                y += 12
                continue
            wrapped = wrap_text(line, body_font, 900, draw)
            for wl in wrapped:
                is_check = wl.strip().startswith("✅")
                c = hex_to_rgb(brand["text_light"]) if is_check else hex_to_rgb(brand["text_muted"])
                draw.text((80, y), wl, font=body_font, fill=c)
                h = draw.textbbox((0, 0), wl, font=body_font)
                y += (h[3] - h[1]) + 8

    else:
        draw_gradient(draw, *POST_SIZE, brand["gradient_start"], brand["gradient_end"])
        hook = content.get("hook", content.get("caption", "")[:100])
        font = FONT_TITLE(48)
        lines = wrap_text(hook, font, 900, draw)
        y = POST_SIZE[1] // 2 - len(lines) * 30
        for line in lines:
            h = draw_centered_text(draw, line, y, font, hex_to_rgb(brand["text_light"]), POST_SIZE[0])
            y += h + 14

        y += 40
        draw_accent_bar(draw, y, POST_SIZE[0], brand["accent"])

    draw_branding_footer(draw, *POST_SIZE, brand)
    return [("post", img)]

# ---------------------------------------------------------------------------
# REEL COVER GENERATOR
# ---------------------------------------------------------------------------

def generate_reel_cover(content, brand):
    img = Image.new("RGB", REEL_COVER_SIZE)
    draw = ImageDraw.Draw(img)

    draw_gradient(draw, *REEL_COVER_SIZE, brand["gradient_start"], brand["gradient_end"], "vertical")
    accent = hex_to_rgb(brand["accent"])

    play_y = 500
    play_r = 60
    cx, cy = REEL_COVER_SIZE[0] // 2, play_y
    draw.ellipse([cx - play_r, cy - play_r, cx + play_r, cy + play_r], outline=accent, width=4)
    tri_pts = [(cx - 20, cy - 30), (cx - 20, cy + 30), (cx + 30, cy)]
    draw.polygon(tri_pts, fill=accent)

    title = content.get("title", content.get("hook", ""))
    font = FONT_TITLE(54)
    lines = wrap_text(title, font, 900, draw)
    y = 650
    for line in lines:
        h = draw_centered_text(draw, line, y, font, hex_to_rgb(brand["text_light"]), REEL_COVER_SIZE[0])
        y += h + 14

    y += 30
    hook = content.get("hook", "")
    if hook and hook != title:
        hook_font = FONT_BODY(32)
        hlines = wrap_text(hook, hook_font, 850, draw)
        for hl in hlines[:3]:
            h = draw_centered_text(draw, hl, y, hook_font, hex_to_rgb(brand["text_muted"]), REEL_COVER_SIZE[0])
            y += h + 8

    duration = content.get("duration", "")
    if duration:
        dur_font = load_font(22, bold=False)
        draw_centered_text(draw, f"▶ {duration}", y + 30, dur_font, accent, REEL_COVER_SIZE[0])

    bar_y = REEL_COVER_SIZE[1] - 200
    draw.rectangle([0, bar_y, REEL_COVER_SIZE[0], bar_y + 3], fill=accent)
    owner_font = load_font(30, bold=True)
    draw_centered_text(draw, f"— {brand['owner']}", bar_y + 30, owner_font, accent, REEL_COVER_SIZE[0])
    brand_font = load_font(24, bold=False)
    draw_centered_text(draw, brand["name"], bar_y + 70, brand_font, hex_to_rgb(brand["text_muted"]), REEL_COVER_SIZE[0])

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

        t = i / max(len(frames) - 1, 1)
        start = lerp_color(hex_to_rgb(brand["gradient_start"]), hex_to_rgb(brand["accent"]), t * 0.3)
        end = hex_to_rgb(brand["gradient_end"])
        for y_px in range(STORY_SIZE[1]):
            c = lerp_color(start, end, y_px / (STORY_SIZE[1] - 1))
            draw.line([(0, y_px), (STORY_SIZE[0], y_px)], fill=c)

        accent = hex_to_rgb(brand["accent"])
        frame_type = frame.get("type", "text")
        frame_content = frame.get("content", "")

        if frame_type == "text":
            font = FONT_TITLE(48)
            lines = wrap_text(frame_content, font, 900, draw)
            y = STORY_SIZE[1] // 2 - len(lines) * 35
            for line in lines:
                h = draw_centered_text(draw, line, y, font, hex_to_rgb(brand["text_light"]), STORY_SIZE[0])
                y += h + 14

        elif frame_type == "poll":
            q_font = FONT_TITLE(42)
            q_lines = wrap_text(frame_content, q_font, 850, draw)
            y = 500
            for line in q_lines:
                h = draw_centered_text(draw, line, y, q_font, hex_to_rgb(brand["text_light"]), STORY_SIZE[0])
                y += h + 12

            y += 60
            options = frame.get("sticker", "").split(" vs. ") if " vs. " in frame.get("sticker", "") else ["Option A", "Option B"]
            for opt in options[:2]:
                draw_rounded_rect(draw, (140, y, 940, y + 80), hex_to_rgb(brand["secondary"]), radius=16)
                opt_font = FONT_BODY(30)
                bbox = draw.textbbox((0, 0), opt, font=opt_font)
                tw = bbox[2] - bbox[0]
                draw.text(((STORY_SIZE[0] - tw) // 2, y + 22), opt, font=opt_font, fill=hex_to_rgb(brand["text_light"]))
                y += 110

        elif frame_type in ("question", "slider"):
            font = FONT_TITLE(44)
            lines = wrap_text(frame_content, font, 850, draw)
            y = 600
            for line in lines:
                h = draw_centered_text(draw, line, y, font, hex_to_rgb(brand["text_light"]), STORY_SIZE[0])
                y += h + 12
            y += 50
            draw_rounded_rect(draw, (140, y, 940, y + 70), hex_to_rgb(brand["secondary"]), radius=14)
            ph_font = FONT_BODY(26)
            draw.text((180, y + 20), "Type your answer...", font=ph_font, fill=hex_to_rgb(brand["text_muted"]))

        sticker = frame.get("sticker", "")
        if sticker and frame_type == "text":
            st_font = load_font(22, bold=False)
            draw_centered_text(draw, sticker, STORY_SIZE[1] - 300, st_font, accent, STORY_SIZE[0])

        owner_font = load_font(22, bold=True)
        draw_centered_text(draw, brand["name"], STORY_SIZE[1] - 120, owner_font, accent, STORY_SIZE[0])

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

    safe_label = re.sub(r"[^a-zA-Z0-9]", "_", str(day_label))[:20]
    item_dir = os.path.join(output_dir, f"{safe_label}_{content_type}_{pillar}")
    os.makedirs(item_dir, exist_ok=True)

    generated_files = []

    if content_type == "carousel":
        images = generate_carousel_images(content, brand)
        for name, img in images:
            path = os.path.join(item_dir, f"{name}.png")
            img.save(path, "PNG", quality=95)
            generated_files.append(path)
            print(f"  [CAROUSEL] {path}")

    elif content_type == "reel":
        images = generate_reel_cover(content, brand)
        for name, img in images:
            path = os.path.join(item_dir, f"{name}.png")
            img.save(path, "PNG", quality=95)
            generated_files.append(path)
            print(f"  [REEL] {path}")

    elif content_type == "story":
        images = generate_story_frames(content, brand)
        for name, img in images:
            path = os.path.join(item_dir, f"{name}.png")
            img.save(path, "PNG", quality=95)
            generated_files.append(path)
            print(f"  [STORY] {path}")

    else:
        images = generate_post_image(content, brand)
        for name, img in images:
            path = os.path.join(item_dir, f"{name}.png")
            img.save(path, "PNG", quality=95)
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
