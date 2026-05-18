# Directive: Instagram Content Creator (Full Pipeline)

## Goal
Generate Instagram-ready content AND visuals for clients — captions, hashtags, carousel text, reel scripts, story ideas, full content calendars, AND branded images (carousel slides, post graphics, reel covers, story frames). Fully operational content agent.

## Inputs
- Client name (loads profile from `clients/{client}/CLIENT_SUMMARY.md`)
- Content type: `post`, `carousel`, `reel`, `story`, `calendar`
- Topic or theme (optional — auto-generates if not specified)
- Number of posts to generate (default: 7 for a week)
- Tone override (optional)
- Image mode: `branded` (default, Pillow graphics), `unsplash` (stock photos), `dalle` (AI-generated, needs API key)

## Process
1. Read client profile from `clients/{client}/CLIENT_SUMMARY.md`
2. Generate text: `python execution/generate_instagram.py --client <name> --type <type> [options] --save`
3. Generate visuals: `python execution/generate_content_visuals.py --client <name> --input instagram_calendar.json`
4. Review generated content + images with user
5. Save approved content to `clients/{client}/content/`

## Full Pipeline Command
```bash
# Step 1: Text content
python execution/generate_instagram.py --client akira-real-estate --type calendar --count 7 --save

# Step 2: Branded visuals
python execution/generate_content_visuals.py --client akira-real-estate --input instagram_calendar.json

# Step 2 (with stock photos): 
python execution/generate_content_visuals.py --client akira-real-estate --input instagram_calendar.json --use-unsplash

# Step 2 (with AI images):
python execution/generate_content_visuals.py --client akira-real-estate --input instagram_calendar.json --use-dalle
```

## Content Types

### Single Post (`--type post`)
Generates a caption + hashtag set for a single Instagram feed post.
- Hook line (first line that shows before "...more")
- Body (2-4 short paragraphs)
- CTA (call to action)
- 20-30 hashtags (mix of broad + niche)
- Suggested image/visual description

### Carousel (`--type carousel`)
Generates slide-by-slide text for a carousel post (up to 10 slides).
- Slide 1: Hook/title (attention-grabbing)
- Slides 2-9: Content (one idea per slide, short text)
- Final slide: CTA + contact info
- Caption for the post
- Hashtags

### Reel Script (`--type reel`)
Generates a short-form video script.
- Hook (first 3 seconds)
- Scene-by-scene breakdown
- Text overlay suggestions
- Audio/music mood suggestion
- Caption + hashtags

### Story (`--type story`)
Generates a multi-frame story sequence.
- 3-7 story frames
- Text overlay for each frame
- Sticker/poll/question suggestions
- Swipe-up CTA (if applicable)

### Content Calendar (`--type calendar`)
Generates a full week or month of content.
- Date, content type, topic, caption preview
- Balanced mix across content pillars
- Seasonal/timely hooks included
- Output as JSON + formatted Markdown

## Content Pillars (Real Estate)
1. Listings & Market Updates
2. Buyer/Seller Education
3. Community Spotlights
4. Behind the Scenes
5. Client Success Stories
6. Market Authority & Stats

## Rules
- NEVER use generic/overused phrases ("dream home", "keys to your future")
- Keep captions under 2200 characters (Instagram limit)
- First line must be a scroll-stopping hook
- Use line breaks for readability
- Mix hashtag sizes: 5 big (500K+), 10 medium (10K-500K), 10 niche (<10K)
- Include 1 CTA per post (DM, link in bio, comment, save)
- Carousel slides: max 30 words per slide
- Reels: keep scripts under 60 seconds
- Stories: design for vertical (9:16)
- Always match client's brand voice from CLIENT_SUMMARY.md

## Output Format
All content saved to `clients/{client}/content/` as:
- `instagram_posts.json` — structured content data
- `instagram_calendar.md` — readable content calendar
- `visuals/` — generated images organized by day:
  - `day1_carousel_education/slide_01_title.png` ... `slide_08_cta.png`
  - `day2_post_listing/post.png` + `stock_photo.jpg`
  - `day3_reel_community/reel_cover.png`
  - `day7_story_market_stats/story_frame_01.png` ... `story_frame_06.png`
  - Each folder has `metadata.json` with caption, hashtags, and file list

## Visual Design System
- **1080x1080** for posts and carousel slides
- **1080x1920** for stories and reel covers
- Gradient backgrounds from client brand colors
- Gold/accent bar separators and branded footers
- Slide numbering on carousels (e.g., 3/8)
- CTA slides with owner name and brand
- Poll/question mockups on story frames
- Typography: Title (52px bold) → Body (30px) → Small (24px)

## Image Generation Options
| Mode | Flag | Cost | Quality |
|------|------|------|---------|
| Branded graphics | (default) | Free | Professional text-based graphics |
| Stock photos | `--use-unsplash` | Free | Real photography from Unsplash |
| AI-generated | `--use-dalle` | ~$0.04/image | Custom AI photos via DALL-E 3 |

## Tools
- `python execution/generate_instagram.py` — Generate text content
- `python execution/generate_content_visuals.py` — Generate branded visuals
- Client profiles in `clients/{client}/CLIENT_SUMMARY.md`

## Dependencies
- `Pillow` — Image generation (required for visuals)
- `requests` — Stock photos from Unsplash (optional)
- `openai` — DALL-E AI images (optional, needs OPENAI_API_KEY env var)
