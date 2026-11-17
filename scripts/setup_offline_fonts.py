"""Fetch and bundle Latin woff2 web fonts for 100% offline desktop experience."""

import re
import urllib.request
from pathlib import Path

fonts_dir = Path("optiforge/app/static/fonts")
fonts_dir.mkdir(parents=True, exist_ok=True)

# Clean out any old temporary font files
for f in fonts_dir.glob("font_*.woff2"):
    f.unlink()

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

url = "https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,400;6..72,500;6..72,600&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap"
req = urllib.request.Request(url, headers=headers)

with urllib.request.urlopen(req, timeout=15) as resp:
    css_content = resp.read().decode("utf-8")

blocks = css_content.split("@font-face")
local_rules = []
downloaded = set()

for block in blocks:
    if "/* latin */" not in block and "U+0000-00FF" not in block:
        continue

    family_m = re.search(r"font-family:\s*['\"]([^'\"]+)['\"]", block)
    weight_m = re.search(r"font-weight:\s*([^;]+);", block)
    style_m = re.search(r"font-style:\s*([^;]+);", block)
    url_m = re.search(r"url\((https://[^)]+\.woff2)\)", block)

    if family_m and weight_m and url_m:
        raw_family = family_m.group(1)
        family_slug = raw_family.replace(" ", "-").lower()
        weight = weight_m.group(1).strip()
        style = style_m.group(1).strip() if style_m else "normal"
        remote_url = url_m.group(1)

        fname = f"{family_slug}-{weight}-{style}.woff2"
        if fname in downloaded:
            continue
        downloaded.add(fname)

        dest_file = fonts_dir / fname
        urllib.request.urlretrieve(remote_url, dest_file)
        print(f"✓ Saved {fname} ({dest_file.stat().st_size} bytes)")

        rule = f"""@font-face {{
  font-family: '{raw_family}';
  font-style: {style};
  font-weight: {weight};
  font-display: swap;
  src: url('fonts/{fname}') format('woff2');
}}"""
        local_rules.append(rule)

fonts_css = Path("optiforge/app/static/fonts.css")
fonts_css.write_text("\n\n".join(local_rules), encoding="utf-8")
print(f"✓ Successfully bundled {len(downloaded)} offline font files and created optiforge/app/static/fonts.css")
