"""Generates multi-resolution icons (16, 20, 24, 32, 40, 48, 64, 128, 256), PNG, and SVG for OptiForge.

Uses the beloved 8-spoke radial sunburst / loading-wheel emblem:
Terracotta copper rays (#c25738 / #e06c4c) with rounded caps on a dark warm charcoal umber squircle (#1c1917).
Ultra-crisp at all resolutions from 16px taskbar to 256px desktop.
"""

import math
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent

TERRACOTTA = (224, 108, 76, 255)       # #e06c4c vibrant terracotta
TERRACOTTA_DEEP = (194, 87, 56, 255)  # #c25738 deep copper
BG_COLOR = (26, 23, 21, 255)          # #1a1715 deep charcoal umber
BORDER_COLOR = (194, 87, 56, 180)     # Subtle copper rim

def render_radial_wheel(size: int) -> Image.Image:
    # Render at 4x supersampling for buttery smooth anti-aliased rounded line caps
    supersample = 4
    canvas_size = size * supersample
    img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    s = canvas_size / 256.0

    # 1. Dark squircle background
    pad = int(12 * s)
    radius = int(52 * s)
    border_w = max(1, int(3.5 * s))

    draw.rounded_rectangle(
        [pad, pad, canvas_size - pad, canvas_size - pad],
        radius=radius,
        fill=BG_COLOR,
        outline=BORDER_COLOR,
        width=border_w
    )

    # 2. Draw 8 radial tick spokes (The loading-wheel sunburst emblem)
    center = canvas_size / 2.0
    r_inner = 38.0 * s
    r_outer = 82.0 * s
    line_width = max(2, int(15.0 * s))

    # For 16px / 24px: optimize thickness so spokes don't blend together
    if size <= 24:
        r_inner = 34.0 * s
        r_outer = 86.0 * s
        line_width = max(supersample * 2, int(18.0 * s))

    # 8 spokes at 0, 45, 90, 135, 180, 225, 270, 315 degrees
    # Slight top-down subtle gradient: top spokes slightly brighter terracotta
    for angle_deg in range(0, 360, 45):
        rad = math.radians(angle_deg)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)

        x1 = center + r_inner * cos_a
        y1 = center + r_inner * sin_a
        x2 = center + r_outer * cos_a
        y2 = center + r_outer * sin_a

        # Top rays have a warm highlight, bottom have deep copper tone
        t = (math.sin(rad) + 1.0) / 2.0  # 0 at top, 1 at bottom
        r_col = int(230 - 20 * t)
        g_col = int(115 - 25 * t)
        b_col = int(82 - 20 * t)
        color = (r_col, g_col, b_col, 255)

        # Draw spoke line with rounded ends
        draw.line([(x1, y1), (x2, y2)], fill=color, width=line_width)

        # Draw rounded caps
        cap_r = line_width / 2.0
        draw.ellipse([x1 - cap_r, y1 - cap_r, x1 + cap_r, y1 + cap_r], fill=color)
        draw.ellipse([x2 - cap_r, y2 - cap_r, x2 + cap_r, y2 + cap_r], fill=color)

    # Downsample with high-quality Lanczos resampling
    final = img.resize((size, size), Image.Resampling.LANCZOS)
    return final


def generate_svg() -> str:
    """Produces the exact vector SVG matching the loading wheel icon."""
    return '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256">
  <rect width="232" height="232" x="12" y="12" rx="52" fill="#1a1715" stroke="#c25738" stroke-width="3" stroke-opacity="0.7"/>
  <g transform="translate(128, 128)" stroke="#e06c4c" stroke-width="15" stroke-linecap="round">
    <!-- 8 Radial Spokes -->
    <line x1="0" y1="-38" x2="0" y2="-82" stroke="#e87856"/>
    <line x1="26.87" y1="-26.87" x2="57.98" y2="-57.98" stroke="#e47150"/>
    <line x1="38" y1="0" x2="82" y2="0" stroke="#de6846"/>
    <line x1="26.87" y1="26.87" x2="57.98" y2="57.98" stroke="#d65f3e"/>
    <line x1="0" y1="38" x2="0" y2="82" stroke="#ce5838"/>
    <line x1="-26.87" y1="26.87" x2="-57.98" y2="57.98" stroke="#d65f3e"/>
    <line x1="-38" y1="0" x2="-82" y2="0" stroke="#de6846"/>
    <line x1="-26.87" y1="-26.87" x2="-57.98" y2="-57.98" stroke="#e47150"/>
  </g>
</svg>
'''


def main():
    print("🎨 Generating OptiForge loading-wheel radial icons...")

    # Resolutions for Windows ICO
    sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
    images = [render_radial_wheel(s) for s in sizes]

    # 1. Master PNG (256x256)
    master_png = images[-1]
    master_png.save(ROOT / "optiforge.png", "PNG")
    static_png = ROOT / "optiforge" / "app" / "static" / "optiforge.png"
    static_png.parent.mkdir(parents=True, exist_ok=True)
    master_png.save(static_png, "PNG")
    print(f"✓ Saved {ROOT / 'optiforge.png'}")

    # 2. Multi-Resolution Windows ICO
    ico_destinations = [
        ROOT / "optiforge.ico",
        ROOT / "optiforge" / "app" / "static" / "optiforge.ico",
    ]
    for dest in ico_destinations:
        images[-1].save(
            dest,
            format="ICO",
            sizes=[(s, s) for s in sizes],
            append_images=images[:-1]
        )
        print(f"✓ Saved {dest} (sizes: {sizes})")

    # 3. Vector SVG
    svg_content = generate_svg()
    (ROOT / "optiforge.svg").write_text(svg_content, encoding="utf-8")
    (ROOT / "optiforge" / "app" / "static" / "optiforge.svg").write_text(svg_content, encoding="utf-8")
    print(f"✓ Saved SVG at {ROOT / 'optiforge.svg'}")

    print("\n🎉 Loading-wheel icons generated successfully!")


if __name__ == "__main__":
    main()
