#!/usr/bin/env python3
"""
SEO Audit Script for Marketing Sauce
Analyzes a client's HTML file for SEO best practices.

Usage:
    python execution/seo_audit.py <path-to-html> [--output <output-path>]

Example:
    python execution/seo_audit.py clients/north-atlantic-tattoo/index.html
"""

import sys
import os
import re
import argparse
from datetime import date

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("ERROR: beautifulsoup4 required. Run: pip install beautifulsoup4")
    sys.exit(1)


def audit(html_path):
    """Run SEO audit on an HTML file. Returns dict of results."""
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "html.parser")
    results = []

    # 1. Title tag
    title = soup.find("title")
    if not title or not title.string:
        results.append(("Title Tag", "FAIL", "No <title> tag found"))
    else:
        tlen = len(title.string.strip())
        if 50 <= tlen <= 60:
            results.append(("Title Tag", "PASS", f'"{title.string.strip()}" ({tlen} chars)'))
        else:
            results.append(("Title Tag", "WARNING", f'Length is {tlen} chars (ideal: 50-60)'))

    # 2. Meta description
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if not meta_desc or not meta_desc.get("content"):
        results.append(("Meta Description", "FAIL", "No meta description found"))
    else:
        dlen = len(meta_desc["content"])
        if 150 <= dlen <= 160:
            results.append(("Meta Description", "PASS", f"{dlen} chars"))
        else:
            results.append(("Meta Description", "WARNING", f"Length is {dlen} chars (ideal: 150-160)"))

    # 3. H1 tag
    h1s = soup.find_all("h1")
    if len(h1s) == 0:
        results.append(("H1 Tag", "FAIL", "No H1 tag found"))
    elif len(h1s) == 1:
        results.append(("H1 Tag", "PASS", f'"{h1s[0].get_text(strip=True)[:50]}"'))
    else:
        results.append(("H1 Tag", "WARNING", f"Found {len(h1s)} H1 tags (should be exactly 1)"))

    # 4. Heading hierarchy
    headings = soup.find_all(re.compile(r"^h[1-6]$"))
    levels = [int(h.name[1]) for h in headings]
    skips = any(levels[i + 1] - levels[i] > 1 for i in range(len(levels) - 1))
    if not headings:
        results.append(("Heading Hierarchy", "FAIL", "No headings found"))
    elif skips:
        results.append(("Heading Hierarchy", "WARNING", "Heading levels skip (e.g., H1 to H3)"))
    else:
        results.append(("Heading Hierarchy", "PASS", f"{len(headings)} headings, proper nesting"))

    # 5. Image alt tags
    images = soup.find_all("img")
    missing_alt = [img.get("src", "unknown") for img in images if not img.get("alt")]
    if not images:
        results.append(("Image Alt Tags", "PASS", "No images found"))
    elif missing_alt:
        results.append(("Image Alt Tags", "FAIL", f"{len(missing_alt)} images missing alt text"))
    else:
        results.append(("Image Alt Tags", "PASS", f"All {len(images)} images have alt text"))

    # 6. Viewport meta
    viewport = soup.find("meta", attrs={"name": "viewport"})
    if viewport:
        results.append(("Mobile Viewport", "PASS", "Viewport meta tag present"))
    else:
        results.append(("Mobile Viewport", "FAIL", "No viewport meta tag"))

    # 7. Open Graph tags
    og_tags = ["og:title", "og:description", "og:image"]
    found_og = [t for t in og_tags if soup.find("meta", property=t)]
    missing_og = [t for t in og_tags if t not in [f"og:{x.split(':')[1]}" if ":" in x else x for x in found_og]]
    # Simpler check
    missing_og = [t for t in og_tags if not soup.find("meta", property=t)]
    if not missing_og:
        results.append(("Open Graph Tags", "PASS", "All OG tags present"))
    else:
        results.append(("Open Graph Tags", "FAIL", f"Missing: {', '.join(missing_og)}"))

    # 8. Canonical URL
    canonical = soup.find("link", rel="canonical")
    if canonical:
        results.append(("Canonical URL", "PASS", canonical.get("href", "")))
    else:
        results.append(("Canonical URL", "WARNING", "No canonical URL set"))

    # 9. Schema markup
    schema = soup.find("script", type="application/ld+json")
    if schema:
        results.append(("Schema Markup", "PASS", "JSON-LD schema found"))
    else:
        results.append(("Schema Markup", "FAIL", "No structured data found"))

    # 10. Semantic HTML
    semantic_tags = ["header", "main", "section", "footer", "nav"]
    found_semantic = [t for t in semantic_tags if soup.find(t)]
    if len(found_semantic) >= 3:
        results.append(("Semantic HTML", "PASS", f"Found: {', '.join(found_semantic)}"))
    else:
        results.append(("Semantic HTML", "WARNING", f"Only found: {', '.join(found_semantic) or 'none'}"))

    # 11. Links
    links = soup.find_all("a", href=True)
    external = [a for a in links if a["href"].startswith("http")]
    internal = [a for a in links if not a["href"].startswith("http") and not a["href"].startswith("#")]
    results.append(("Link Structure", "PASS", f"{len(internal)} internal, {len(external)} external, {len(links)} total"))

    # 12. Page size
    size_kb = len(html.encode("utf-8")) / 1024
    if size_kb < 500:
        results.append(("Page Size", "PASS", f"{size_kb:.0f} KB"))
    else:
        results.append(("Page Size", "WARNING", f"{size_kb:.0f} KB (consider optimizing)"))

    return results


def generate_report(results, html_path):
    """Generate markdown report from audit results."""
    passed = sum(1 for _, status, _ in results if status == "PASS")
    total = len(results)

    report = f"# SEO Audit Report\n\n"
    report += f"**File:** `{html_path}`\n"
    report += f"**Date:** {date.today()}\n"
    report += f"**Score:** {passed}/{total} checks passed\n\n"
    report += "## Results\n\n"
    report += "| Check | Status | Details |\n"
    report += "|-------|--------|---------|\n"

    for check, status, details in results:
        icon = {"PASS": "PASS", "FAIL": "FAIL", "WARNING": "WARN"}[status]
        report += f"| {check} | {icon} | {details} |\n"

    # Recommendations
    failures = [(c, d) for c, s, d in results if s == "FAIL"]
    warnings = [(c, d) for c, s, d in results if s == "WARNING"]

    if failures or warnings:
        report += "\n## Recommendations\n\n"
        for check, detail in failures:
            report += f"- **{check}:** {detail}\n"
        for check, detail in warnings:
            report += f"- **{check}:** {detail}\n"

    report += f"\n---\n*Generated by Marketing Sauce SEO Audit on {date.today()}*\n"
    return report


def main():
    parser = argparse.ArgumentParser(description="SEO Audit Tool")
    parser.add_argument("html_path", help="Path to the HTML file to audit")
    parser.add_argument("--output", "-o", help="Output path for the report")
    args = parser.parse_args()

    if not os.path.exists(args.html_path):
        print(f"ERROR: File not found: {args.html_path}")
        sys.exit(1)

    results = audit(args.html_path)
    report = generate_report(results, args.html_path)

    if args.output:
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        with open(args.output, "w") as f:
            f.write(report)
        print(f"Report saved to {args.output}")
    else:
        print(report)


if __name__ == "__main__":
    main()
