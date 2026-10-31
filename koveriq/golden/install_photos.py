"""Synthetic before/after photos for the install-showcase goldens.

KoverIQ-original artwork (licence ``koveriq_original``): drawn here from
rectangles and lines, so it holds no photograph, no person, no house number
and no third-party work, and may be committed and used in any test. 2560x1920
so that no format upscales it past koveriq.kinds.UPSCALE_WARNING, and so that
the worker's brief stage (MAX_LONG_SIDE 2560) never downscales it.
Deterministic: the same code always draws the same pixels.

    python -m koveriq.golden.install_photos [--out DIR]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent / "install-showcase" / "assets"
SIZE = (2560, 1920)
WALL = (232, 226, 214)
SKIRTING = (246, 244, 238)
FLOOR = (176, 146, 112)
FRAME = (250, 250, 248)
GLASS = (168, 196, 220)
GARDEN = (122, 158, 104)
LOUVRE = (246, 244, 238)
SHADOW = (206, 202, 192)

# name -> (window box, louvres per panel; 0 = a bare window)
PHOTOS: dict[str, tuple[tuple[int, int, int, int], int]] = {
    "a-before-1": ((672, 320, 1888, 1440), 0),
    "a-after-1": ((672, 320, 1888, 1440), 12),
    "a-after-2": ((896, 416, 1664, 1376), 9),
}


def _room(draw: ImageDraw.ImageDraw) -> None:
    width, height = SIZE
    draw.rectangle((0, 0, width, height), fill=WALL)
    draw.rectangle((0, int(height * 0.80), width, int(height * 0.82)), fill=SKIRTING)
    draw.rectangle((0, int(height * 0.82), width, height), fill=FLOOR)


def _window(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=FRAME)
    inner = (x0 + 38, y0 + 38, x1 - 38, y1 - 38)
    draw.rectangle(inner, fill=GLASS)
    garden_top = int(inner[3] - (inner[3] - inner[1]) * 0.3)
    draw.rectangle((inner[0], garden_top, inner[2], inner[3]), fill=GARDEN)
    return inner


def _shutters(draw: ImageDraw.ImageDraw, inner: tuple[int, int, int, int], louvres: int) -> None:
    x0, y0, x1, y1 = inner
    draw.rectangle(inner, fill=LOUVRE)
    middle = (x0 + x1) // 2
    draw.line((middle, y0, middle, y1), fill=SHADOW, width=13)
    step = (y1 - y0) / louvres
    for index in range(1, louvres):
        y = int(y0 + index * step)
        draw.line((x0, y, x1, y), fill=SHADOW, width=10)


def draw(name: str) -> Image.Image:
    box, louvres = PHOTOS[name]
    image = Image.new("RGB", SIZE, WALL)
    canvas = ImageDraw.Draw(image)
    _room(canvas)
    inner = _window(canvas, box)
    if louvres:
        _shutters(canvas, inner, louvres)
    return image


def write(out: Path = OUT) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for name in PHOTOS:
        path = out / f"{name}.png"
        draw(name).save(path, "PNG")
        paths.append(path)
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m koveriq.golden.install_photos")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args(argv)
    for path in write(args.out):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
