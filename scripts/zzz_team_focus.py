"""Design where ZZZ agents sit horizontally in team cards' images, in
hoyo-buddy-assets/assets/zzz-team-card/focus.yaml.

The team card's image is narrower than both the agents' static team art (a landscape bust) and
their animations (cropped to the build card's art area, see spine.yaml), so it shows a slice of
them, centered unless focus.yaml says otherwise. Focus is in percent like CSS's object-position,
0 keeps the art's left edge.

Workflow (run from the repo root):
    1. uv run --with "opencv-python-headless<5" scripts/zzz_team_focus.py --suggest
       Adds agents missing from focus.yaml, centering the face an anime face detector
       (lbpcascade_animeface) finds, or the art when it finds none, and lists those. Then renders
       the contact sheets.
    2. uv run scripts/zzz_team_focus.py [KEY ...]
       Renders each agent's static art and animation at their focus on contact sheets in
       scripts/output/zzz_team_focus/, with a line at the image's center. Fix focus.yaml by hand
       and render again.

Keys are agent IDs, or agent and outfit IDs for outfits' static art, e.g. 1051_3110511.
"""

from __future__ import annotations

import argparse
import asyncio
import io
import sys
from pathlib import Path
from typing import TYPE_CHECKING

# Parse our own args before any hoyo_buddy imports, because hoyo_buddy.config uses
# pydantic-settings with cli_parse_args=True which would hijack sys.argv.
_parser = argparse.ArgumentParser(description="Design ZZZ team card focus data")
_parser.add_argument("keys", nargs="*", help="Keys to render, e.g. 1051 1051_3110511")
_parser.add_argument(
    "--suggest", action="store_true", help="Add missing agents with a detected focus"
)
_args = _parser.parse_args()
sys.argv = sys.argv[:1]

import aiohttp
import numpy as np
import yaml
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent.parent))

from hoyo_buddy.constants import ZZZ_TEAM_IMAGE_OVERRIDES
from hoyo_buddy.draw.card_data import ASSET_PATH, ZZZ_DATA, ZZZ_SPINE_DATA, ZZZ_TEAM_FOCUS
from hoyo_buddy.draw.drawer import Drawer
from hoyo_buddy.draw.static import ZZZ_V2_GAME_RECORD

if TYPE_CHECKING:
    from typing import Any

OUTPUT_DIR = Path("scripts/output/zzz_team_focus")
MASK = ASSET_PATH / "zzz-team-card/chara_img.png"
CASCADE_URL = (
    "https://raw.githubusercontent.com/nagadomi/lbpcascade_animeface/master/"
    "lbpcascade_animeface.xml"
)
TILES_PER_SHEET = 24
SHEET_COLUMNS = 6


def get_static_url(key: str) -> str:
    """The agent's default team art, like get_default_art(is_team=True)."""
    agent_id = key.split("_", maxsplit=1)[0]
    default = str(ZZZ_V2_GAME_RECORD / f"role_vertical_painting/role_vertical_painting_{key}.png")
    return ZZZ_TEAM_IMAGE_OVERRIDES.get(key, ZZZ_TEAM_IMAGE_OVERRIDES.get(agent_id, default))


async def download_static(session: aiohttp.ClientSession, key: str) -> Path | None:
    path = OUTPUT_DIR / "static" / f"{key}.png"
    if not path.exists():
        async with session.get(get_static_url(key)) as resp:
            if resp.status != 200:
                print(f"{key}: no static team art ({resp.status})")
                return None
            path.write_bytes(await resp.read())
    return path


def _first_webp_frame(data: bytes) -> Image.Image | None:
    """Decode the first frame of a possibly truncated animated WEBP, None if it's cut off."""
    pos = 12  # After the RIFF header
    while pos + 8 <= len(data):
        size = int.from_bytes(data[pos + 4 : pos + 8], "little")
        if data[pos : pos + 4] == b"ANMF":
            payload = data[pos + 8 : pos + 8 + size]
            if len(payload) < size:
                return None
            # Rewrap the frame's bitstream as a still WEBP with an alpha channel
            canvas = payload[6:12]  # Width - 1 and height - 1
            vp8x = b"VP8X" + (10).to_bytes(4, "little") + b"\x10\x00\x00\x00" + canvas
            body = b"WEBP" + vp8x + payload[16:]
            riff = b"RIFF" + len(body).to_bytes(4, "little") + body
            return Image.open(io.BytesIO(riff)).convert("RGBA")
        pos += 8 + size + (size & 1)
    return None


async def download_animation(session: aiohttp.ClientSession, key: str, url: str) -> Path:
    """Download the animation's first frame, with range requests since animations are large."""
    path = OUTPUT_DIR / "animation" / f"{key}.png"
    length = 2 * 1024 * 1024
    while not path.exists():
        async with session.get(url, headers={"Range": f"bytes=0-{length - 1}"}) as resp:
            resp.raise_for_status()
            frame = _first_webp_frame(await resp.read())
        if frame is None:
            length *= 2
        else:
            frame.save(path)
    return path


async def download_cascade(session: aiohttp.ClientSession) -> Path:
    path = OUTPUT_DIR / "lbpcascade_animeface.xml"
    if not path.exists():
        async with session.get(CASCADE_URL) as resp:
            resp.raise_for_status()
            path.write_bytes(await resp.read())
    return path


def find_face_x(image: Image.Image, cascade: Path) -> float | None:
    """Find the horizontal center of the art's largest face."""
    import cv2  # ruff:ignore[import-outside-top-level] # pyright: ignore[reportMissingImports]

    if not hasattr(cv2, "CascadeClassifier"):
        msg = 'OpenCV 5 dropped cascade classifiers, run with --with "opencv-python-headless<5"'
        raise SystemExit(msg)

    rgb = Image.new("RGB", image.size, (255, 255, 255))
    rgb.paste(image, mask=image.getchannel("A"))
    gray = cv2.equalizeHist(cv2.cvtColor(np.asarray(rgb), cv2.COLOR_RGB2GRAY))
    faces = cv2.CascadeClassifier(str(cascade)).detectMultiScale(
        gray, scaleFactor=1.05, minNeighbors=4, minSize=(48, 48)
    )
    if len(faces) == 0:
        return None
    x, _, w, _ = max(faces, key=lambda face: face[2] * face[3])
    return x + w / 2


def get_focus(size: tuple[int, int], area: tuple[int, int], center_x: float) -> int:
    """The focus that puts center_x at the area's center, see Drawer.resize_crop."""
    ratio = min(size[0] / area[0], size[1] / area[1])
    overflow = size[0] / ratio - area[0]
    if overflow <= 0:
        return 50
    left = center_x / ratio - area[0] / 2
    return round(min(max(left / overflow, 0), 1) * 100)


def draw_tile(image: Image.Image | None, focus: int, mask: Image.Image) -> Image.Image:
    tile = Image.new("RGBA", mask.size, (200, 200, 200, 255))
    if image is not None:
        tile.alpha_composite(Drawer.resize_crop(image, mask.size, focus_x=focus))
    tile.putalpha(mask.getchannel("A"))
    ImageDraw.Draw(tile).line(
        (mask.width // 2, 0, mask.width // 2, mask.height), fill=(255, 0, 0, 128)
    )
    return tile


def render_sheets(
    keys: list[str], focus: dict[str, dict[str, int]], paths: dict[tuple[str, str], Path]
) -> None:
    mask = Image.open(MASK)
    tiles: list[Image.Image] = []
    for key in keys:
        entry = focus.get(key, {})
        tile = Image.new("RGBA", (mask.width * 2 + 4, mask.height + 16), "white")
        label = f"{key}  image {entry.get('image', 50)}"
        for i, kind in enumerate(("image", "animation")):
            path = paths.get((kind, key))
            if path is None:
                continue
            if kind == "animation":
                label += f"  anim {entry.get('animation', 50)}"
            image = Image.open(path).convert("RGBA")
            tile.alpha_composite(
                draw_tile(image, entry.get(kind, 50), mask), (i * (mask.width + 4), 16)
            )
        ImageDraw.Draw(tile).text((2, 2), label, fill="black")
        tiles.append(tile)

    for old in OUTPUT_DIR.glob("sheet_*.png"):
        old.unlink()
    for start in range(0, len(tiles), TILES_PER_SHEET):
        chunk = tiles[start : start + TILES_PER_SHEET]
        width, height = chunk[0].width + 12, chunk[0].height + 12
        rows = -(-len(chunk) // SHEET_COLUMNS)
        sheet = Image.new("RGBA", (SHEET_COLUMNS * width, rows * height), "white")
        for i, tile in enumerate(chunk):
            sheet.alpha_composite(
                tile, ((i % SHEET_COLUMNS) * width, (i // SHEET_COLUMNS) * height)
            )
        path = OUTPUT_DIR / f"sheet_{start // TILES_PER_SHEET + 1}.png"
        sheet.save(path)
        print(f"Saved {path}")


def suggest(
    keys: list[str],
    focus: dict[str, dict[str, int]],
    paths: dict[tuple[str, str], Path],
    cascade: Path,
) -> list[str]:
    """Add the missing agents' focus, returning the keys and kinds without a face found."""
    area = Image.open(MASK).size
    misses: list[str] = []
    for key in keys:
        entry: dict[str, int] = focus.get(key, {})
        for kind in ("image", "animation"):
            path = paths.get((kind, key))
            if path is None or kind in entry:
                continue
            image = Image.open(path).convert("RGBA")
            face_x = find_face_x(image, cascade)
            if face_x is None:
                misses.append(f"{key} {kind}")
                entry[kind] = 50
            else:
                entry[kind] = get_focus(image.size, area, face_x)
        if entry:
            focus[key] = entry
    return misses


async def main() -> None:
    for folder in ("static", "animation"):
        (OUTPUT_DIR / folder).mkdir(parents=True, exist_ok=True)

    static_keys: list[str] = list(yaml.safe_load(ZZZ_DATA.read_text("utf-8")))
    spine: dict[str, Any] = yaml.safe_load(ZZZ_SPINE_DATA.read_text("utf-8"))
    focus: dict[str, dict[str, int]] = (
        yaml.safe_load(ZZZ_TEAM_FOCUS.read_text("utf-8")) or {} if ZZZ_TEAM_FOCUS.exists() else {}
    )
    keys = sorted(set(static_keys) | set(spine))
    if _args.keys:
        keys = [key for key in keys if key in _args.keys]

    paths: dict[tuple[str, str], Path] = {}
    async with aiohttp.ClientSession() as session:
        for key in keys:
            if key in static_keys and (path := await download_static(session, key)) is not None:
                paths["image", key] = path
            if key in spine:
                paths["animation", key] = await download_animation(session, key, spine[key]["url"])

        if _args.suggest:
            misses = suggest(keys, focus, paths, await download_cascade(session))
            ZZZ_TEAM_FOCUS.write_text(yaml.safe_dump(dict(sorted(focus.items()))), "utf-8")
            print(f"Wrote {ZZZ_TEAM_FOCUS}")
            if misses:
                print("No face found, centered:", ", ".join(misses))

    render_sheets(keys, focus, paths)


if __name__ == "__main__":
    asyncio.run(main())
