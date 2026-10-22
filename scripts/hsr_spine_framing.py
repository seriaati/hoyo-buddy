"""Review the framings of HSR animated build cards (see scripts/render_hsr_spine.py).

Workflow (run from the repo root), for template 1 unless --template 2 is passed:
    1. uv run scripts/hsr_spine_framing.py init [CHARACTER_ID ...] [--force] [--min-size 0.3]
       Writes scripts/output/hsr_spine/hsr1/variants.yaml with a framing suggested from each
       character's static art as its `base`. Add `variants` overriding x, y or height. When a
       suggestion zooms into a tiny patch of the animation, redo it with --force and a higher
       --min-size, e.g. 0.25-0.35.
    2. uv run scripts/hsr_spine_framing.py preview [CHARACTER_ID ...]
       Draws each character's static art next to the first frame of each variant in the art area,
       on contact sheets in scripts/output/hsr_spine/hsr1/.
    3. uv run scripts/hsr_spine_framing.py apply 1310 1005:higher ...
       Writes the variants (default: base) into the template's spine.yaml. Then re-render them with
       scripts/render_hsr_spine.py, since the uploaded animations are cropped to their framing.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import tempfile
from pathlib import Path
from typing import Any

_parser = argparse.ArgumentParser(description="Review the framings of HSR animated build cards")
_parser.add_argument("--template", type=int, choices=(1, 2), default=1)
_subparsers = _parser.add_subparsers(dest="command", required=True)

_init_parser = _subparsers.add_parser("init", help="Suggest framings")
_init_parser.add_argument("character_ids", nargs="*", help="Only these characters (default: all)")
_init_parser.add_argument("--force", action="store_true", help="Replace existing entries")
_init_parser.add_argument(
    "--min-size",
    type=float,
    default=0.1,
    help="Smallest share of the animation's height the static art may cover, raise it when the "
    "suggestion zooms into a tiny patch",
)

_preview_parser = _subparsers.add_parser("preview", help="Render framing variants")
_preview_parser.add_argument(
    "character_ids", nargs="*", help="Only these characters (default: all)"
)

_apply_parser = _subparsers.add_parser("apply", help="Write framings to spine.yaml")
_apply_parser.add_argument("picks", nargs="+", help="CHARACTER_ID or CHARACTER_ID:VARIANT")

_args = _parser.parse_args()

# Clear argv so pydantic-settings doesn't try to parse our flags as bot config.
sys.argv = sys.argv[:1]

import aiohttp
import yaml
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent.parent))

from hoyo_buddy.constants import ANIMATED_CARD_SCALE
from hoyo_buddy.draw.drawer import Drawer
from scripts import render_hsr_spine
from scripts.spine_common import Framing, download_image, download_spine, render_card_frames

TARGET = render_hsr_spine.TARGETS[_args.template]
MASK_PATH = render_hsr_spine.MASKS[_args.template]
OUTPUT_DIR = Path("scripts/output/hsr_spine") / TARGET.name
SPEC_PATH = OUTPUT_DIR / "variants.yaml"
FILES_DIR = Path("scripts/output/hsr_spine/files")
SHEET_SIZE = 6
"""Characters per contact sheet."""
JOBS = 6
"""Number of characters to render at once."""
BACKGROUND = (60, 60, 60)


def _load_spec() -> dict[str, dict[str, Any]]:
    if not SPEC_PATH.exists():
        msg = f"{SPEC_PATH} doesn't exist, run `init` first"
        raise SystemExit(msg)
    return yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))


def _framing(entry: dict[str, Any], variant: str) -> Framing:
    return Framing(**{**entry["base"], **(entry["variants"][variant] or {})})


async def _get_spine_files(
    session: aiohttp.ClientSession, character_id: str, base_url: str, spine: str
) -> tuple[Path, Path]:
    """Download a character's Spine files once, they don't change between versions.

    They're kept by character since characters may share Spine file names, e.g. Blade's.
    """
    folder = FILES_DIR / character_id
    skel, atlas = folder / f"{spine}.skel", folder / f"{spine}.atlas"
    if skel.exists():
        return skel, atlas
    folder.mkdir(parents=True, exist_ok=True)
    return await download_spine(session, base_url, spine, folder)


async def init(character_ids: list[str], *, force: bool, min_size: float) -> None:
    spec: dict[str, dict[str, Any]] = (
        yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8")) if SPEC_PATH.exists() else {}
    )
    semaphore = asyncio.Semaphore(JOBS)

    async def suggest(
        session: aiohttp.ClientSession,
        character_id: str,
        character: render_hsr_spine.SpineCharacter,
    ) -> None:
        async with semaphore:
            skel, atlas = await _get_spine_files(
                session, character_id, character.base_url, character.spine
            )
            with tempfile.TemporaryDirectory() as tmp:
                framing = await render_hsr_spine.suggest_framing(
                    skel,
                    atlas,
                    Path(tmp),
                    spine=character.spine,
                    static_art=await download_image(session, str(character.image)),
                    area=TARGET.area,
                    min_size=min_size,
                )
        spec[character_id] = {
            "name": character.name,
            "base_url": character.base_url,
            "spine": character.spine,
            "image": character.image,
            "base": framing._asdict(),
            "variants": {"base": {}},
        }
        print(f"{character.name} ({character_id}): {framing}")

    async with aiohttp.ClientSession() as session:
        characters = await render_hsr_spine.fetch_spine_characters(session, character_ids or None)
        await asyncio.gather(
            *(suggest(session, k, v) for k, v in characters.items() if force or k not in spec)
        )

    SPEC_PATH.parent.mkdir(parents=True, exist_ok=True)
    SPEC_PATH.write_text(
        yaml.safe_dump(dict(sorted(spec.items())), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    print(f"Wrote {SPEC_PATH}")


def _in_area(image: Image.Image, pos: tuple[int, int], mask: Image.Image) -> Image.Image:
    """Draw an image in the art area like the card does."""
    area = Image.new("RGBA", mask.size, BACKGROUND)
    area.alpha_composite(image, pos)
    return Drawer.mask_image_with_image(area, mask)


def _draw_tiles(
    entry: dict[str, Any], static: Image.Image, previews: dict[str, Image.Image], mask: Image.Image
) -> list[tuple[str, Image.Image]]:
    """Draw the static art and each variant's first animated frame in the art area."""
    static = Drawer.resize_crop(static.convert("RGBA"), mask.size)
    tiles = [(f"{entry['name']} static", _in_area(static, (0, 0), mask))]
    for variant, frame in previews.items():
        framing = _framing(entry, variant)
        # The frame is at ANIMATED_CARD_SCALE and cropped to the art area
        size = (round(frame.width / ANIMATED_CARD_SCALE), round(frame.height / ANIMATED_CARD_SCALE))
        frame = frame.resize(size, Image.Resampling.LANCZOS)
        pos = (max(framing.x, 0), max(framing.y, 0))
        overrides = entry["variants"][variant] or {}
        changes = ", ".join(f"{k}={v}" for k, v in overrides.items()) or "base"
        tiles.append((f"{variant}: {changes}", _in_area(frame, pos, mask)))
    return tiles


def _make_contact_sheet(rows: list[list[tuple[str, Image.Image]]]) -> Image.Image:
    pad, label_h, thumb_h = 16, 40, 480
    first = rows[0][0][1]
    thumb_w = round(first.width * thumb_h / first.height)
    cols = max(len(row) for row in rows)
    sheet = Image.new(
        "RGB",
        (pad + cols * (thumb_w + pad), pad + len(rows) * (label_h + thumb_h + pad)),
        (30, 30, 30),
    )
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=24)
    for r, row in enumerate(rows):
        for c, (label, image) in enumerate(row):
            x = pad + c * (thumb_w + pad)
            y = pad + r * (label_h + thumb_h + pad)
            draw.text((x, y), label, font=font, fill=(255, 255, 255))
            thumb = image.convert("RGB").resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
            sheet.paste(thumb, (x, y + label_h))
    return sheet


async def preview(character_ids: list[str]) -> None:
    spec = _load_spec()
    if unknown := set(character_ids) - set(spec):
        msg = f"Not in {SPEC_PATH}: {', '.join(unknown)}"
        raise SystemExit(msg)
    keys = character_ids or list(spec)
    semaphore = asyncio.Semaphore(JOBS)

    async def render(session: aiohttp.ClientSession, key: str, variant: str) -> Image.Image:
        entry = spec[key]
        async with semaphore:
            skel, atlas = await _get_spine_files(session, key, entry["base_url"], entry["spine"])
            with tempfile.TemporaryDirectory() as tmp:
                frames = await render_card_frames(
                    skel,
                    atlas,
                    Path(tmp),
                    spine=entry["spine"],
                    framing=_framing(entry, variant),
                    area=TARGET.area,
                    frames=1,
                )
            return frames[0]

    async with aiohttp.ClientSession() as session:
        statics = await asyncio.gather(*(download_image(session, spec[k]["image"]) for k in keys))
        jobs = [(k, v) for k in keys for v in spec[k]["variants"]]
        frames = await asyncio.gather(*(render(session, k, v) for k, v in jobs))

    previews: dict[str, dict[str, Image.Image]] = {}
    for (key, variant), frame in zip(jobs, frames, strict=True):
        previews.setdefault(key, {})[variant] = frame

    mask = Drawer.open_image(str(MASK_PATH))
    rows = [
        _draw_tiles(spec[key], static, previews[key], mask)
        for key, static in zip(keys, statics, strict=True)
    ]
    for i in range(0, len(keys), SHEET_SIZE):
        sheet_keys = keys[i : i + SHEET_SIZE]
        sheet_path = OUTPUT_DIR / f"{sheet_keys[0]}-{sheet_keys[-1]}.png"
        _make_contact_sheet(rows[i : i + SHEET_SIZE]).save(sheet_path)
        print(f"Contact sheet: {sheet_path}")


def apply(picks: list[str]) -> None:
    spec = _load_spec()
    manifest: dict[str, dict[str, Any]] = yaml.safe_load(
        TARGET.manifest.read_text(encoding="utf-8")
    )
    for pick in picks:
        character_id, _, variant = pick.partition(":")
        variant = variant or "base"
        if character_id not in manifest:
            msg = f"{character_id} isn't in {TARGET.manifest}, render it first"
            raise SystemExit(msg)
        if variant not in spec.get(character_id, {}).get("variants", {}):
            msg = f"{character_id} has no variant {variant!r} in {SPEC_PATH}"
            raise SystemExit(msg)
        manifest[character_id].update(_framing(spec[character_id], variant)._asdict())
        print(f"{spec[character_id]['name']} ({character_id}): {variant}")

    TARGET.manifest.write_text(yaml.safe_dump(manifest, allow_unicode=True), encoding="utf-8")
    character_ids = " ".join(pick.partition(":")[0] for pick in picks)
    template = _args.template
    print(
        f"Re-render them: uv run scripts/render_hsr_spine.py {character_ids} --template {template}"
    )


async def main() -> None:
    match _args.command:
        case "init":
            await init(_args.character_ids, force=_args.force, min_size=_args.min_size)
        case "preview":
            await preview(_args.character_ids)
        case "apply":
            apply(_args.picks)


if __name__ == "__main__":
    asyncio.run(main())
