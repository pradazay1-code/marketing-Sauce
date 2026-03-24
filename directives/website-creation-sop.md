# Website Creation SOP

## When to Use
Invoked whenever the user asks to build, design, create, or modify a website or any UI component, page, form, or dashboard for a client or for the agency itself.

## Tools Required
- HTML/CSS/JavaScript
- React or Next.js (for dynamic sites)
- Tailwind CSS (for styling)
- Component libraries (shadcn/ui, etc.)
- Image optimization tools
- SEO tools
- Hosting deployment knowledge (Vercel, Netlify, etc.)

## Step-by-Step Process

### Step 1: Gather Requirements
Ask the user for (or pull from client file in `memory/clients.md`):
- [ ] Business name and industry
- [ ] Brand colors, logo, fonts (if they have them)
- [ ] What pages they need (Home, About, Services, Contact, etc.)
- [ ] Reference websites they like
- [ ] Key messaging — what's their unique value proposition?
- [ ] Target audience
- [ ] Any existing content (photos, copy, testimonials)
- [ ] Special features needed (booking system, e-commerce, blog, forms)
- [ ] Domain name (existing or need one?)

### Step 2: Plan the Site Architecture
- Map out all pages and their hierarchy
- Define the user flow (how visitors move through the site)
- Identify key conversion points (contact form, call button, booking)
- Plan mobile responsiveness strategy

### Step 3: Design the Homepage
The homepage is the most critical page. Follow this structure:
1. **Hero Section** — Bold headline + subtext + CTA button + hero image/video
2. **Social Proof Bar** — Logos, "As seen in", or trust badges
3. **Services/Value Section** — 3-4 key services with icons and brief descriptions
4. **About/Story Section** — Brief brand story, build trust
5. **Testimonials** — 2-3 client testimonials with photos and names
6. **Results/Stats Section** — Numbers that prove value (clients served, results, etc.)
7. **CTA Section** — Strong call-to-action before footer
8. **Footer** — Contact info, social links, quick nav, legal links

### Step 4: Build Remaining Pages
- **About Page:** Team photos, story, mission, values
- **Services Page:** Detailed service descriptions with pricing (if applicable)
- **Contact Page:** Form, phone, email, map, business hours
- **Portfolio/Case Studies:** Past work and results (if applicable)
- **Blog:** If content marketing is part of the strategy

### Step 5: Optimize
- [ ] Mobile responsive (test all breakpoints)
- [ ] Page speed optimization (compress images, lazy load, minify)
- [ ] SEO basics (meta titles, descriptions, alt tags, sitemap)
- [ ] Accessibility (alt text, contrast ratios, keyboard navigation)
- [ ] Analytics setup (Google Analytics, conversion tracking)
- [ ] Contact forms tested and working
- [ ] All links working (no 404s)

### Step 6: Review and Deliver
- Present to user/client for feedback
- Make revisions based on feedback
- Prepare deployment instructions
- Document any custom features or CMS instructions for the client

## Design Principles
1. **Clean and modern** — Lots of whitespace, clear typography
2. **Mobile-first** — Design for phone screens first, then scale up
3. **Fast** — No unnecessary animations or heavy assets
4. **Conversion-focused** — Every page has a clear CTA
5. **On-brand** — Colors, fonts, imagery all match the client's brand
6. **Trust-building** — Testimonials, results, and social proof throughout

## Tech Stack Preferences
- **Simple sites:** HTML + Tailwind CSS (fastest to build and deploy)
- **Dynamic sites:** Next.js + Tailwind CSS + shadcn/ui
- **E-commerce:** Shopify or Next.js + Stripe
- **Hosting:** Vercel (preferred) or Netlify
- **Forms:** Formspree, or custom API endpoint
- **Analytics:** Google Analytics 4 + Hotjar (for heatmaps)

## Quality Checks
- [ ] Site looks professional on desktop, tablet, and mobile
- [ ] All forms submit correctly
- [ ] Page loads in under 3 seconds
- [ ] SEO meta tags are in place
- [ ] No placeholder content left (Lorem ipsum, etc.)
- [ ] Client brand guidelines are followed
- [ ] Legal pages exist (Privacy Policy, Terms of Service)

## Notes
- Always save completed websites as portfolio pieces
- Document the tech stack used for each client in `memory/clients.md`
- Keep a library of reusable components in `templates/`
- Take before/after screenshots for case studies
