#!/bin/bash
# ============================================
# North Atlantic Tattoo — Image Setup Script
# ============================================
# Run this on your LOCAL machine (where your OneDrive is)
# It finds the 4 most recent image files and copies them in.
#
# Usage: bash setup-images.sh
# ============================================

IMAGES_DIR="$(dirname "$0")/images"
mkdir -p "$IMAGES_DIR"

# Try common OneDrive paths
ONEDRIVE=""
for dir in \
    "$HOME/OneDrive" \
    "$HOME/OneDrive - Personal" \
    "/mnt/c/Users/$USER/OneDrive" \
    "/mnt/c/Users/*/OneDrive" \
    "$HOME/Desktop" \
    "$HOME/Downloads" \
    "$HOME/Pictures"; do
    if [ -d "$dir" ]; then
        ONEDRIVE="$dir"
        break
    fi
done

if [ -z "$ONEDRIVE" ]; then
    echo "Could not find OneDrive/Downloads/Pictures folder."
    echo "Please drag and drop your images into: $IMAGES_DIR"
    echo ""
    echo "Expected files:"
    echo "  logo.png         — The circular NA Tattoo logo"
    echo "  portfolio-1.jpg  — Color realism collage (Iron Maiden)"
    echo "  portfolio-2.jpg  — Japanese foo dog sleeve"
    echo "  portfolio-3.jpg  — Dark landscape/Ghost piece"
    exit 1
fi

echo "Searching $ONEDRIVE for recent images..."

# Find the 4 most recent image files
mapfile -t RECENT < <(find "$ONEDRIVE" -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" \) -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -4 | awk '{print $2}')

if [ ${#RECENT[@]} -lt 3 ]; then
    echo "Found fewer than 3 images. Please add them manually to: $IMAGES_DIR"
    exit 1
fi

echo "Found ${#RECENT[@]} recent images:"
for i in "${!RECENT[@]}"; do
    echo "  [$i] ${RECENT[$i]}"
done

# Copy them (logo first if it's a PNG, then portfolio)
LOGO_DONE=false
PORT_NUM=1
for f in "${RECENT[@]}"; do
    fname=$(basename "$f" | tr '[:upper:]' '[:lower:]')
    if [[ "$fname" == *"logo"* ]] || { [[ "$fname" == *.png ]] && [ "$LOGO_DONE" = false ]; }; then
        cp "$f" "$IMAGES_DIR/logo.png"
        echo "Copied logo: $f"
        LOGO_DONE=true
    else
        cp "$f" "$IMAGES_DIR/portfolio-${PORT_NUM}.jpg"
        echo "Copied portfolio-${PORT_NUM}: $f"
        ((PORT_NUM++))
    fi
done

echo ""
echo "Done! Open index.html in your browser to see the site."
