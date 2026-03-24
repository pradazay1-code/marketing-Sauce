# Directive: Build Client Website

## Goal
Create a professional, self-contained website for a marketing client.

## Inputs
- Client name
- Business type / industry
- Location (if applicable)
- Brand colors, fonts, style preferences
- Content: About text, services, contact info
- Images: User will provide separately

## Process
1. Create client folder: `clients/{client-name}/`
2. Create `images/` subfolder for assets
3. Build a single self-contained HTML file with all CSS/JS inline
4. Use `<img src="images/...">` for portfolio/photo images
5. Ensure mobile-responsive design
6. Include SEO meta tags

## Outputs
- `clients/{client-name}/index.html` — the complete website
- Full HTML code output in chat for copy-paste

## Edge Cases
- If client has no logo yet, use text-based logo
- If no brand colors specified, propose a palette based on industry
- Always ask before assuming content
