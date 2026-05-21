"""Generate readable README demo assets."""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "docs" / "demo" / "assets"


def _windows_font_dir() -> Path:
    windir = os.environ.get("WINDIR")
    if not windir:
        raise RuntimeError("WINDIR is required to locate Windows fonts.")

    font_dir = Path(windir) / "Fonts"
    if not font_dir.is_dir():
        raise RuntimeError(f"Windows font directory not found: {font_dir}")

    return font_dir


FONT_DIR = _windows_font_dir()


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_DIR / name), size)


def _card(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    title: str,
    hint: str,
    color: str,
) -> None:
    x, y = xy
    draw.rounded_rectangle(
        (x, y, x + 210, y + 205), radius=6, fill="#f8f8f8", outline="#cfcfcf"
    )
    draw.rectangle((x + 12, y + 12, x + 198, y + 116), fill=color)
    draw.rectangle((x + 12, y + 82, x + 198, y + 116), fill="#202020")
    draw.text(
        (x + 24, y + 91),
        "karaoke backing track",
        fill="#ffffff",
        font=_font("segoeui.ttf", 12),
    )
    draw.text((x + 14, y + 130), title, fill="#151515", font=_font("segoeuib.ttf", 16))
    draw.text((x + 14, y + 158), hint, fill="#666666", font=_font("segoeui.ttf", 13))


def _home_image(path: Path) -> None:
    image = Image.new("RGB", (900, 640), "#f1f1f1")
    draw = ImageDraw.Draw(image)
    draw.text((330, 32), "KaraokeBuddy", fill="#111111", font=_font("segoeuib.ttf", 34))
    draw.rounded_rectangle(
        (24, 92, 442, 148), radius=5, fill="#ffffff", outline="#b8b8b8"
    )
    draw.rounded_rectangle(
        (458, 92, 876, 148), radius=5, fill="#ffffff", outline="#b8b8b8"
    )
    draw.text(
        (162, 111), "Open a video file", fill="#111111", font=_font("segoeui.ttf", 18)
    )
    draw.text(
        (594, 111), "Paste YouTube link", fill="#111111", font=_font("segoeui.ttf", 18)
    )
    draw.text(
        (30, 184), "Recent videos", fill="#111111", font=_font("segoeuib.ttf", 18)
    )
    _card(draw, (198, 230), "Neon Night", "Lower by 2 keys", "#814a7a")
    _card(draw, (492, 230), "High Note Practice", "Higher by 3 keys", "#145c7a")
    image.save(path)


def _slider(
    draw: ImageDraw.ImageDraw,
    y: int,
    label: str,
    left: str,
    right: str,
    value_x: int,
    status: str,
) -> None:
    draw.text((56, y), label, fill="#dddddd", font=_font("segoeuib.ttf", 16))
    track_y = y + 48
    draw.text((56, track_y - 9), left, fill="#dddddd", font=_font("segoeui.ttf", 13))
    draw.line((128, track_y, 760, track_y), fill="#8a8a8a", width=6)
    draw.ellipse(
        (value_x - 10, track_y - 10, value_x + 10, track_y + 10),
        fill="#e9e9e9",
        outline="#bbbbbb",
    )
    draw.text((786, track_y - 9), right, fill="#dddddd", font=_font("segoeui.ttf", 13))
    draw.text(
        (360, track_y + 20), status, fill="#aaaaaa", font=_font("segoeui.ttf", 14)
    )


def _player_image(path: Path) -> None:
    image = Image.new("RGB", (900, 640), "#111111")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 900, 300), fill="#050505")
    draw.text(
        (330, 124), "Video preview", fill="#d8d8d8", font=_font("segoeuib.ttf", 32)
    )
    draw.rectangle((0, 300, 900, 640), fill="#1e1e1e")
    draw.text((18, 326), "0:42", fill="#dddddd", font=_font("segoeui.ttf", 14))
    draw.line((72, 335, 810, 335), fill="#777777", width=5)
    draw.ellipse((226, 326, 244, 344), fill="#f0f0f0")
    draw.text((828, 326), "3:04", fill="#dddddd", font=_font("segoeui.ttf", 14))
    draw.rounded_rectangle((56, 368, 156, 410), radius=5, fill="#f7f7f7")
    draw.text((82, 379), "Pause", fill="#111111", font=_font("segoeui.ttf", 15))
    _slider(draw, 438, "Song key", "Lower", "Higher", 260, "Lower by 2 keys")
    _slider(
        draw, 532, "Silence the singer", "Off", "Full", 570, "Guide vocals: 35% audible"
    )
    draw.rounded_rectangle((56, 590, 228, 626), radius=5, fill="#f7f7f7")
    draw.text(
        (84, 599), "Save this version", fill="#111111", font=_font("segoeui.ttf", 14)
    )
    draw.text(
        (738, 599), "Back to library", fill="#aaaaaa", font=_font("segoeui.ttf", 14)
    )
    image.save(path)


def _compose_demo_gif(home_path: Path, player_path: Path, gif_path: Path) -> None:
    captions = [
        (home_path, "Open a local video or paste a YouTube link"),
        (player_path, "Shift key live, reduce guide vocals, save MP4"),
    ]
    frames = []
    for source, caption in captions:
        image = Image.open(source).convert("RGB")
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, image.width, 48), fill="#121212")
        draw.text((18, 14), caption, fill="#ffffff", font=_font("segoeui.ttf", 18))
        frames.extend([image] * 2)
    frames[0].save(
        gif_path,
        save_all=True,
        append_images=frames[1:],
        duration=900,
        loop=0,
    )


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    home_path = ASSETS / "home-library.png"
    player_path = ASSETS / "playing-controls.png"
    _home_image(home_path)
    _player_image(player_path)
    _compose_demo_gif(home_path, player_path, ASSETS / "readme-demo.gif")


if __name__ == "__main__":
    main()
