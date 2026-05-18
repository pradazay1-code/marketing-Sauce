# Skill: Content Creator — Full Pipeline

## What It Does
End-to-end content creation for clients: generates Instagram text (captions, hashtags, CTAs) AND branded visuals (carousel slides, post images, reel covers, story frames). Outputs ready-to-post packages organized per day.

## Pipeline
```
Client Profile → Text Generation → Visual Generation → Ready-to-Post Package
```

## How to Run

### Step 1: Generate Text Content (Calendar)
```bash
python execution/generate_instagram.py \
  --client akira-real-estate \
  --type calendar \
  --count 7 \
  --save
```
Output: `clients/{client}/content/instagram_calendar.json` + `.md`

### Step 2: Generate Visuals for the Calendar
```bash
python execution/generate_content_visuals.py \
  --client akira-real-estate \
  --input instagram_calendar.json
```
Output: `clients/{client}/content/visuals/` with folders per day containing:
- PNG images (carousel slides, post graphics, reel covers, story frames)
- `metadata.json` with caption, hashtags, and file list

### Optional: Add Stock Photos
```bash
python execution/generate_content_visuals.py \
  --client akira-real-estate \
  --input instagram_calendar.json \
  --use-unsplash
```

### Optional: Add AI-Generated Images (requires OPENAI_API_KEY)
```bash
python execution/generate_content_visuals.py \
  --client akira-real-estate \
  --input instagram_calendar.json \
  --use-dalle
```

### Single Post Generation
```bash
# Text
python execution/generate_instagram.py --client akira-real-estate --type post --pillar listing --city "Boston"

# Carousel
python execution/generate_instagram.py --client akira-real-estate --type carousel --pillar education --save
```

## Content Types Generated

| Type | Text Output | Visual Output |
|------|-------------|---------------|
| **Post** | Caption + hashtags + CTA | Branded graphic (1080x1080) |
| **Carousel** | Slide text + caption + hashtags | Individual slide PNGs (1080x1080) |
| **Reel** | Scene script + caption + hashtags | Cover thumbnail (1080x1920) |
| **Story** | Frame text + sticker suggestions | Frame PNGs (1080x1920) with polls/questions |
| **Calendar** | 7-30 days of mixed content | All visuals for every day |

## Visual Design System
- Gradient backgrounds using client brand colors
- Accent bars and branded footer on every image
- Slide numbering for carousels
- Typography hierarchy: Title (52px bold) → Body (30px) → Small (24px)
- CTA slides with owner attribution
- Poll/question mockups for stories

## Output Structure
```
clients/{client}/content/
├── instagram_calendar.json      # Text content
├── instagram_calendar.md        # Human-readable calendar
└── visuals/
    ├── day1_carousel_education/
    │   ├── slide_01_title.png
    │   ├── slide_02.png
    │   ├── ...
    │   ├── slide_08_cta.png
    │   └── metadata.json
    ├── day2_post_listing/
    │   ├── post.png
    │   ├── stock_photo.jpg       # (if --use-unsplash)
    │   └── metadata.json
    └── day3_reel_community/
        ├── reel_cover.png
        └── metadata.json
```

## Brand Configuration
Client brands are auto-loaded from `clients/{client}/CLIENT_SUMMARY.md`. To customize colors, add entries to `CLIENT_BRANDS` dict in `generate_content_visuals.py`.

## Dependencies
- `Pillow` — Image generation (required)
- `requests` — Stock photos from Unsplash (optional)
- `openai` — DALL-E image generation (optional, needs API key)
