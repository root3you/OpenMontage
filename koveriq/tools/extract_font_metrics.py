"""Regenerate koveriq/font_metrics.json from the fonts HyperFrames embeds.

HyperFrames resolves a fixed set of fonts by name from base64 WOFF2 data
embedded in its CLI bundle (no network at render time). The KoverIQ templates
only use those fonts and weights, so text can be fitted from their real glyph
advance widths instead of guesses.

Dev-only. Needs `fonttools` and `brotli` (not runtime dependencies):

    python koveriq/tools/extract_font_metrics.py <path to hyperframes dist dir>

The output holds advance widths (em fractions) only, not font data.
"""

from __future__ import annotations

import base64
import io
import json
import re
import sys
from pathlib import Path

from fontTools.ttLib import TTFont

FACES = {
    "Montserrat": ("montserrat", [400, 700, 900]),
    "Playfair Display": ("playfair-display", [400, 700, 900]),
    "Archivo Black": ("archivo-black", [400]),
}
CHARS = (
    [chr(c) for c in range(0x20, 0x7F)]
    + [chr(c) for c in range(0xA0, 0x100)]
    + list("‘’“”–—…•€™")
)


def _embedded_fonts(dist_dir: Path) -> dict[str, str]:
    pattern = re.compile(r'\["(@fontsource/[a-z0-9-]+:\d+:normal)", "data:font/woff2;base64,([A-Za-z0-9+/=]+)"\]')
    found: dict[str, str] = {}
    for js in dist_dir.glob("chunk-*.js"):
        text = js.read_text(encoding="utf-8", errors="ignore")
        if "@fontsource/" not in text:
            continue
        for key, data in pattern.findall(text):
            found[key] = data
    return found


def main(dist_dir: Path, out_path: Path) -> None:
    embedded = _embedded_fonts(dist_dir)
    faces: dict[str, dict[str, dict]] = {}
    for family, (slug, weights) in FACES.items():
        for weight in weights:
            key = f"@fontsource/{slug}:{weight}:normal"
            if key not in embedded:
                raise SystemExit(f"{key} is not embedded in {dist_dir}")
            font = TTFont(io.BytesIO(base64.b64decode(embedded[key])))
            upm = font["head"].unitsPerEm
            cmap = font.getBestCmap()
            hmtx = font["hmtx"]
            widths = {}
            for ch in CHARS:
                glyph = cmap.get(ord(ch))
                if glyph is not None:
                    widths[ch] = round(hmtx[glyph][0] / upm, 4)
            fallback = round(sum(widths.values()) / len(widths), 4)
            faces.setdefault(family, {})[str(weight)] = {"default": fallback, "widths": widths}
    out = {
        "source": "Advance widths (em) of the fonts embedded in the hyperframes CLI (@fontsource builds).",
        "faces": faces,
    }
    out_path.write_text(json.dumps(out, ensure_ascii=False, sort_keys=True, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    dist = Path(sys.argv[1])
    target = Path(__file__).resolve().parents[1] / "font_metrics.json"
    main(dist, target)
    print(f"wrote {target}")
