# Directive: Instagram Content Creator

## Goal
Generate Instagram-ready content for clients — captions, hashtags, carousel text, reel scripts, story ideas, and full content calendars. Mimics GHL Content AI functionality.

## Inputs
- Client name (loads profile from `clients/{client}/CLIENT_SUMMARY.md`)
- Content type: `post`, `carousel`, `reel`, `story`, `calendar`
- Topic or theme (optional — auto-generates if not specified)
- Number of posts to generate (default: 7 for a week)
- Tone override (optional)

## Process
1. Read client profile from `clients/{client}/CLIENT_SUMMARY.md`
2. Run: `python execution/generate_instagram.py --client <name> --type <type> [options]`
3. Review generated content with user
4. Save approved content to `clients/{client}/content/`

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
- Individual post files if requested

## Tools
- `python execution/generate_instagram.py` — Generate content
- Client profiles in `clients/{client}/CLIENT_SUMMARY.md`
