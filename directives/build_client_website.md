# Directive: Build Client Website

## Goal
Create a professional, self-contained website for a marketing client. Deploy it live and generate all tracking documentation.

## Inputs
- Client name
- Business type / industry
- Location (if applicable)
- Brand colors, fonts, style preferences
- Content: About text, services, team/staff info, contact info
- Images: User will provide separately (or scraped if URLs given)

## Process

### Step 1: Setup
1. Create client folder: `clients/{client-name}/`
2. Create `images/` subfolder for assets
3. Gather all client info (ask if anything is missing)

### Step 2: Build Website
1. Build a **single self-contained HTML file** (`index.html`) with all CSS/JS inline
2. Use `<img src="images/...">` for portfolio/photo images
3. Ensure mobile-responsive design (test at 320px, 768px, 1200px)
4. Include SEO meta tags (title, description, Open Graph)
5. Follow the Wix compatibility rules below

### Step 3: Create Standalone Version
1. Convert all images to base64
2. Generate `index-standalone.html` with embedded images
3. This version works anywhere — no external dependencies

### Step 4: Deploy to GitHub Pages
1. Create or update the `gh-pages` branch
2. Place the standalone HTML at `clients/{client-name}/index.html` on `gh-pages`
3. Push to `gh-pages` branch
4. Live URL: `https://pradazay1-code.github.io/marketing-Sauce/clients/{client-name}/`

### Step 5: Generate Client Summary
1. Run `execution/generate_client_summary.py` to create a Markdown summary
2. Summary includes: client name, site URL, GitHub Pages URL, date, services delivered
3. Output saved to `clients/{client-name}/CLIENT_SUMMARY.md`

### Step 6: Wix Deployment (Manual Step)
1. User pastes the HTML into Wix using the embed/custom code widget
2. Or user imports via Wix Velo if full-page custom code is needed
3. See Wix compatibility notes below

## Wix Compatibility Rules
All HTML output MUST follow these rules to work inside Wix:
- **No external CSS/JS CDN links** — everything inline
- **No `<html>`, `<head>`, `<body>` tags** when embedding via Wix HTML embed widget (the standalone version keeps them for direct browser use)
- **Use inline styles or `<style>` blocks** — no `<link rel="stylesheet">`
- **Base64 encode all images** — Wix embed widgets can't load relative paths
- **Avoid `position: fixed`** inside Wix embeds (navbar should use `position: sticky` or be `absolute`)
- **Set explicit height** on the embed container in Wix (Wix iframes need it)
- **Use `window.parent.postMessage`** if you need the embed to communicate height to Wix
- **Google Fonts**: Use `@import` inside a `<style>` block instead of `<link>` tags
- **Forms**: Use a third-party form handler (Formspree, Getform) since Wix embeds can't process form submissions natively
- **Max recommended embed size**: Keep total HTML under 500KB for performance

## Outputs
- `clients/{client-name}/index.html` — development version (relative image paths)
- `clients/{client-name}/index-standalone.html` — self-contained version (base64 images)
- `clients/{client-name}/index-wix.html` — Wix-optimized version (no html/head/body, sticky nav, base64 images)
- `clients/{client-name}/CLIENT_SUMMARY.md` — client tracking document
- GitHub Pages live URL
- Full HTML code output in chat

## Edge Cases
- If client has no logo yet, use text-based logo with their initials
- If no brand colors specified, propose a palette based on industry
- Always ask before assuming content
- If images exceed 500KB total base64, compress them first using `execution/compress_images.py`
- If GitHub Pages deploy fails, retry with exponential backoff (2s, 4s, 8s, 16s)

## Client Tracking
Each client summary gets appended to `clients/CLIENT_TRACKER.md` — a master list of all clients, their URLs, and delivery status.
