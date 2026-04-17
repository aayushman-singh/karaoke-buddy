"""Utility to generate a minimal icon.ico for KaraokeBuddy.

Requires Pillow:  pip install Pillow

Run once during development or as part of the build:
    python src/karaoke_buddy/resources/generate_icon.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ICON_PATH = Path(__file__).parent / "icon.ico"


def main() -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont  # noqa: PLC0415
    except ImportError:
        print("Pillow not installed. Run: pip install Pillow", file=sys.stderr)
        sys.exit(1)

    sizes = [16, 32, 48, 64, 128, 256]
    images = []

    for size in sizes:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Purple circle background
        margin = size // 8
        draw.ellipse(
            [margin, margin, size - margin, size - margin],
            fill=(123, 31, 162, 255),
        )

        # Microphone emoji-style character
        font_size = max(8, size // 2)
        try:
            font = ImageFont.truetype("seguiemj.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()

        text = "🎤"
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        x = (size - tw) // 2
        y = (size - th) // 2
        draw.text((x, y), text, font=font, embedded_color=True)

        images.append(img)

    images[0].save(
        ICON_PATH,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[1:],
    )
    print(f"Icon written to {ICON_PATH}")


if __name__ == "__main__":
    main()
