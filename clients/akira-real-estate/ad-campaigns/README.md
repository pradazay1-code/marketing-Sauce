# Akira Real Estate — Facebook Ad Campaign Assets

## Structure

```
ad-campaigns/
├── facebook-campaign-2026-q3.md   ← Full campaign brief (copy, targeting, budgets)
├── fb_ads_content.json             ← Content JSON that generates the visuals
├── visuals/                        ← Generated PNG assets ready for Meta Ads Manager
└── photos/                         ← Drop your own property photos here (optional)
```

## Using Your Own Property Photos

The visuals ship with photo-style procedural backgrounds (sunset skies, city skylines, warm interior lighting). But you can swap in real property photos for even better performance.

### Step 1 — Add your photos

Drop JPG/PNG photos into the `photos/` folder. Recommended:
- 1200x1200+ resolution
- High-quality exteriors, interiors, city shots
- Well-lit (avoid dark blurry phone pics)

### Step 2 — Edit `fb_ads_content.json`

Add a `background_image` field pointing to your photo. Example:

```json
{
  "content": {
    "type": "post",
    "pillar": "market_stats",
    "background_image": "clients/akira-real-estate/ad-campaigns/photos/luxury_kitchen.jpg",
    "hook": "Your home is worth more than you think.",
    ...
  }
}
```

### Step 3 — Regenerate

```bash
python execution/generate_content_visuals.py \
  --client akira-real-estate \
  --input clients/akira-real-estate/ad-campaigns/fb_ads_content.json \
  --output clients/akira-real-estate/ad-campaigns/visuals
```

The script will composite your photo as the background with a dark gradient overlay for text legibility.

## Free Photo Sources for Real Estate Ads

Since Meta's ad review is strict, use legally-licensed photos:

| Source | Cost | Notes |
|--------|------|-------|
| **Unsplash** (unsplash.com) | Free | Best quality, no attribution required |
| **Pexels** (pexels.com) | Free | Great for interiors and lifestyle |
| **Pixabay** (pixabay.com) | Free | Big library, good for real estate |
| **Your own photos** | Free | Best for authenticity — use listing photos |

Search terms that convert well for real estate ads:
- "modern home exterior"
- "luxury kitchen"
- "family home"
- "backyard patio"
- "keys new home"
- "for sale sign"
- "boston brownstone" (or your city)

## Procedural Background Styles

If you don't provide a photo, the script generates a photo-style background based on the `bg_style` field:

| Style | Best For |
|-------|----------|
| `sunset_home` | Warm evening skyline — listings, lifestyle |
| `city_dusk` | Blue-hour city view with lit buildings — market updates, neighborhoods |
| `warm_interior` | Golden glow — testimonials, "just sold" |
| `night_luxury` | Premium dark navy with accent lines — luxury listings, high-end |

Auto-selected by pillar if no `bg_style` is set:
- `listing` → sunset_home
- `market_stats` → night_luxury
- `education` → city_dusk
- `testimonial` → warm_interior
- `community` → sunset_home
