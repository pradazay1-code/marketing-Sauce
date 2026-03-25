#!/usr/bin/env python3
"""
Convert a standalone HTML file into a Wix-compatible version.
Strips <html>, <head>, <body> wrappers; converts fixed positioning to sticky;
converts <link> font imports to @import; adds height messaging for Wix iframes.

Usage: python build_wix_version.py --input path/to/index-standalone.html --output path/to/index-wix.html
"""
import argparse
import re


def convert_to_wix(html: str) -> str:
    """Transform standalone HTML into Wix-embeddable HTML."""

    # Extract content between <style> tags and <body> content
    styles = re.findall(r'<style>(.*?)</style>', html, re.DOTALL)
    scripts = re.findall(r'<script>(.*?)</script>', html, re.DOTALL)

    # Extract body content
    body_match = re.search(r'<body[^>]*>(.*)</body>', html, re.DOTALL)
    body_content = body_match.group(1) if body_match else html

    # Convert Google Fonts <link> to @import
    font_links = re.findall(r'href="(https://fonts\.googleapis\.com[^"]+)"', html)
    font_imports = "\n".join(f'@import url("{url}");' for url in font_links)

    # Convert position: fixed to position: sticky in styles
    converted_styles = []
    for style in styles:
        style = style.replace('position: fixed', 'position: sticky')
        style = style.replace('position:fixed', 'position:sticky')
        converted_styles.append(style)

    # Build Wix-compatible HTML
    wix_html = f"""<style>
{font_imports}
{"".join(converted_styles)}

/* Wix iframe height communication */
html, body {{ margin: 0; padding: 0; overflow-x: hidden; }}
</style>

{body_content.strip()}

<script>
{"".join(scripts)}

// Communicate height to Wix parent iframe
function sendHeight() {{
    const height = document.documentElement.scrollHeight;
    window.parent.postMessage({{ type: 'setHeight', height: height }}, '*');
}}
window.addEventListener('load', sendHeight);
window.addEventListener('resize', sendHeight);
new MutationObserver(sendHeight).observe(document.body, {{ childList: true, subtree: true }});
</script>
"""
    return wix_html


def main():
    parser = argparse.ArgumentParser(description="Convert HTML to Wix-compatible version")
    parser.add_argument("--input", required=True, help="Path to standalone HTML file")
    parser.add_argument("--output", required=True, help="Output path for Wix version")
    args = parser.parse_args()

    with open(args.input, "r") as f:
        html = f.read()

    wix_html = convert_to_wix(html)

    with open(args.output, "w") as f:
        f.write(wix_html)

    print(f"Wix-compatible HTML saved to: {args.output}")
    print(f"Size: {len(wix_html):,} bytes")


if __name__ == "__main__":
    main()
