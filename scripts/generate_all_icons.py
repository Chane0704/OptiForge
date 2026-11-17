"""Generates multi-resolution icons (16, 24, 32, 48, 64, 128, 256), PNG, and SVG for OptiForge.

Matches the Warm Editorial brand: terracotta copper anvil emblem with ivory spark
on warm charcoal umber squircle. Highly legible at 16px and 32px.
"""

from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent

def draw_artisan_mark(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    s = size / 256.0

    # 1. Squircle Background: Deep Warm Charcoal Umber (#1c1917)
    pad = max(1, int(10 * s))
    radius = max(3, int(54 * s))
    border_w = max(1, int(4 * s))
    draw.rounded_rectangle(
        [pad, pad, size - pad, size - pad],
        radius=radius,
        fill=(28, 25, 23, 255),
        outline=(194, 87, 56, 220), # Warm terracotta border
        width=border_w
    )

    # 2. For 16px and 24px: High-contrast pixel-aligned geometry
    if size <= 24:
        # Simplified crisp anvil base + face for extreme low-res legibility
        b_pad = max(2, int(size * 0.2))
        draw.rectangle([b_pad, int(size * 0.65), size - b_pad, int(size * 0.82)], fill=(194, 87, 56, 255))
        draw.rectangle([b_pad + 1, int(size * 0.45), size - b_pad - 1, int(size * 0.62)], fill=(224, 108, 76, 255))
        # Center spark point
        cx = size // 2
        draw.point((cx, int(size * 0.25)), fill=(245, 243, 239, 255))
        draw.point((cx, int(size * 0.32)), fill=(245, 243, 239, 255))
        return img

    # 3. For 32px and above: Detailed geometric craft anvil + precision spark
    # Inner subtle hairline
    if size >= 48:
        in_pad = int(22 * s)
        draw.rounded_rectangle(
            [in_pad, in_pad, size - in_pad, size - in_pad],
            radius=int(42 * s),
            outline=(245, 243, 239, 30),
            width=max(1, int(1.5 * s))
        )

    # Anvil Base (#c25738)
    anvil_base = [
        (int(64 * s), int(185 * s)),
        (int(192 * s), int(185 * s)),
        (int(174 * s), int(160 * s)),
        (int(82 * s), int(160 * s))
    ]
    draw.polygon(anvil_base, fill=(194, 87, 56, 255))

    # Anvil Waist / Body (#a8472c)
    anvil_body = [
        (int(92 * s), int(160 * s)),
        (int(164 * s), int(160 * s)),
        (int(156 * s), int(134 * s)),
        (int(100 * s), int(134 * s))
    ]
    draw.polygon(anvil_body, fill=(168, 71, 44, 255))

    # Anvil Horn & Top Face (#e06c4c)
    anvil_top = [
        (int(52 * s), int(134 * s)),
        (int(188 * s), int(134 * s)),
        (int(204 * s), int(116 * s)),
        (int(178 * s), int(110 * s)),
        (int(68 * s), int(110 * s))
    ]
    draw.polygon(anvil_top, fill=(224, 108, 76, 255))

    # Precision Craft Spark (#faf8f5 ivory outer, #c25738 core)
    spark_outer = [
        (int(128 * s), int(42 * s)),
        (int(148 * s), int(78 * s)),
        (int(140 * s), int(104 * s)),
        (int(128 * s), int(96 * s)),
        (int(116 * s), int(104 * s)),
        (int(108 * s), int(78 * s))
    ]
    draw.polygon(spark_outer, fill=(245, 243, 239, 255))

    spark_inner = [
        (int(128 * s), int(56 * s)),
        (int(138 * s), int(80 * s)),
        (int(128 * s), int(92 * s)),
        (int(118 * s), int(80 * s))
    ]
    draw.polygon(spark_inner, fill=(194, 87, 56, 255))

    return img


def main():
    sizes = [256, 128, 64, 48, 32, 24, 16]
    images = [draw_artisan_mark(s) for s in sizes]

    # Save multi-res optiforge.ico
    ico_dest = ROOT / "optiforge.ico"
    images[0].save(
        str(ico_dest),
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[1:]
    )
    print(f"✓ Saved multi-resolution {ico_dest} (Sizes: {sizes})")

    # Save 256x256 PNG
    png_dest = ROOT / "optiforge.png"
    images[0].save(str(png_dest), format="PNG")
    print(f"✓ Saved 256x256 PNG: {png_dest}")

    # Also copy to static folder for favicon and web
    static_ico = ROOT / "optiforge" / "app" / "static" / "optiforge.ico"
    static_png = ROOT / "optiforge" / "app" / "static" / "optiforge.png"
    images[0].save(str(static_ico), format="ICO", sizes=[(s, s) for s in sizes], append_images=images[1:])
    images[0].save(str(static_png), format="PNG")
    print("✓ Copied icon and PNG to static assets directory.")

    # Save SVG version
    svg_content = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256">
  <rect x="10" y="10" width="236" height="236" rx="54" fill="#1c1917" stroke="#c25738" stroke-width="4"/>
  <rect x="22" y="22" width="212" height="212" rx="42" fill="none" stroke="#f5f3ef" stroke-width="1.5" stroke-opacity="0.12"/>
  <polygon points="64,185 192,185 174,160 82,160" fill="#c25738"/>
  <polygon points="92,160 164,160 156,134 100,134" fill="#a8472c"/>
  <polygon points="52,134 188,134 204,116 178,110 68,110" fill="#e06c4c"/>
  <polygon points="128,42 148,78 140,104 128,96 116,104 108,78" fill="#f5f3ef"/>
  <polygon points="128,56 138,80 128,92 118,80" fill="#c25738"/>
</svg>'''
    svg_dest = ROOT / "optiforge.svg"
    svg_dest.write_text(svg_content, encoding="utf-8")
    print(f"✓ Saved vector SVG: {svg_dest}")


if __name__ == "__main__":
    main()
