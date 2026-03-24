# Website Engine — Execution Layer

## Purpose
The actual execution logic for building client websites.

## Build Process

### 1. Project Setup
```bash
# For simple HTML/Tailwind sites:
mkdir client-[name]-site
cd client-[name]-site
# Create index.html, styles, assets folders

# For Next.js sites:
npx create-next-app@latest client-[name]-site
cd client-[name]-site
npm install tailwindcss @tailwindcss/typography
```

### 2. File Structure (Simple Site)
```
client-[name]-site/
├── index.html          → Homepage
├── about.html          → About page
├── services.html       → Services page
├── contact.html        → Contact page
├── css/
│   └── styles.css      → Custom styles (Tailwind)
├── js/
│   └── main.js         → Interactions, form handling
├── assets/
│   ├── images/         → Optimized images
│   └── fonts/          → Custom fonts (if any)
└── README.md           → Client documentation
```

### 3. File Structure (Next.js Site)
```
client-[name]-site/
├── app/
│   ├── layout.tsx      → Root layout
│   ├── page.tsx        → Homepage
│   ├── about/page.tsx  → About page
│   ├── services/page.tsx
│   ├── contact/page.tsx
│   └── globals.css
├── components/
│   ├── Header.tsx
│   ├── Footer.tsx
│   ├── Hero.tsx
│   ├── Services.tsx
│   ├── Testimonials.tsx
│   └── ContactForm.tsx
├── public/
│   └── images/
├── tailwind.config.ts
└── package.json
```

### 4. Homepage Sections (Build Order)
1. Navigation bar (sticky, responsive)
2. Hero section (headline, subtext, CTA, image)
3. Social proof bar (trust badges, logos)
4. Services section (3-4 cards)
5. About section (brief story)
6. Testimonials (2-3 testimonials)
7. Results/stats section
8. CTA section
9. Footer

### 5. Responsive Breakpoints
- Mobile: 320px - 768px
- Tablet: 768px - 1024px
- Desktop: 1024px+
- Always design mobile-first

### 6. SEO Checklist
- [ ] Meta title (50-60 chars)
- [ ] Meta description (150-160 chars)
- [ ] H1 tag on every page (only one per page)
- [ ] Alt text on all images
- [ ] Sitemap.xml
- [ ] Robots.txt
- [ ] Open Graph tags for social sharing
- [ ] Schema markup for local business

### 7. Performance Checklist
- [ ] Images compressed (WebP format preferred)
- [ ] CSS/JS minified
- [ ] Lazy loading on images below the fold
- [ ] No render-blocking resources
- [ ] Target: < 3 second load time

### 8. Deployment
- Build the production version
- Deploy to Vercel or Netlify
- Set up custom domain (if client has one)
- Configure SSL
- Test all pages and forms after deployment
