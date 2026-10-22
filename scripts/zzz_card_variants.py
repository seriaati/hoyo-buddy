"""Design ZZZ build card data (templates 1 and 2) for new agents by rendering variants.

Workflow (run from the repo root):
    1. uv run scripts/zzz_card_variants.py init 1641
       Fetches the agent's art from nanoka and writes scripts/output/zzz_variants/1641/variants.yaml
       with one card per art: template 1 default art + each skin, and template 2 M6 cinema art.
       Each card's `base` starts from the latest agent in agent_data*.yaml (template 1 image
       rescaled to the new art's aspect ratio; template 2 image fitted so the solid art's top and
       bottom touch the card's, centered), and `palette` lists colors extracted from the art.
       Design each skin card like a separate agent: its own color, image size/position, level
       position and zzz_text, rather than copying the default skin's.
    2. Add named entries under each card's `variants`. A variant overrides any keys of `base`
       (color, image_x, level_x, zzz_text, ...). If a variant overrides only one of image_w or
       image_h, the other is derived from the art's aspect ratio.
    3. uv run scripts/zzz_card_variants.py render 1641 [CARD_ID ...]
       Renders each variant to scripts/output/zzz_variants/1641/<card_id>/<variant>.png and a
       labelled contact sheet of all variants to scripts/output/zzz_variants/1641/<card_id>.png.
       Each variant's label also shows how much of the level text covers the art (level_stroke
       should be on only when it does) and where the art's head/shoulders land horizontally.
       uv run scripts/zzz_card_variants.py holes 1641 t2_1641 [VARIANT]
       Lists level text positions with the least art under them for a variant's image placement.
    4. uv run scripts/zzz_card_variants.py apply 1641 t1_1641 <variant>
       Writes the chosen variant into agent_data.yaml (template 1) or agent_data_temp2.yaml.

Animated images (see scripts/render_zzz_spine.py) are framed separately, by their x, y and height
in spine.yaml:
    1. uv run scripts/zzz_card_variants.py spine-init [AGENT_ID ...] [--force]
       Writes scripts/output/zzz_variants/spine/variants.yaml with a framing suggested from each
       agent's static template 1 art as its `base`. Add `variants` overriding x, y or height.
    2. uv run scripts/zzz_card_variants.py spine [AGENT_ID ...]
       Draws each agent's static card next to the first frame of each variant's animated card on
       contact sheets in scripts/output/zzz_variants/spine/.
    3. uv run scripts/zzz_card_variants.py spine-apply 1511 1501:higher ...
       Writes the variants (default: base) into spine.yaml. Then re-render them with
       scripts/render_zzz_spine.py, since the uploaded animations are cropped to their framing.

Cards are drawn with a sample agent's stats stored in scripts/data/zzz_sample_agent.json, so Enka
doesn't need to be up. Refresh it with:
    uv run scripts/zzz_card_variants.py fetch-sample [--uid UID]
"""

from __future__ import annotations

import argparse
import asyncio
import colorsys
import functools
import io
import json
import math
import sys
import tempfile
from pathlib import Path
from typing import Any, cast

# Parse our own args before any hoyo_buddy imports, because hoyo_buddy.config uses
# pydantic-settings with cli_parse_args=True which would hijack sys.argv.
_parser = argparse.ArgumentParser(description="Design ZZZ build card data by rendering variants")
_subparsers = _parser.add_subparsers(dest="command", required=True)

_fetch_parser = _subparsers.add_parser("fetch-sample", help="Store a sample agent from Enka")
_fetch_parser.add_argument("--uid", type=int, default=10000827, help="ZZZ UID with a showcase")

_init_parser = _subparsers.add_parser("init", help="Create a variants file for an agent")
_init_parser.add_argument("agent_id", type=int)
_init_parser.add_argument("--version", default=None, help="nanoka data version (default: latest)")
_init_parser.add_argument("--force", action="store_true", help="Overwrite an existing file")

_render_parser = _subparsers.add_parser("render", help="Render all variants of an agent")
_render_parser.add_argument("agent_id", type=int)
_render_parser.add_argument("cards", nargs="*", help="Only render these card IDs (e.g. t1_1641)")

_holes_parser = _subparsers.add_parser("holes", help="Find level positions with the least art")
_holes_parser.add_argument("agent_id", type=int)
_holes_parser.add_argument("card_id", help="e.g. t2_1641")
_holes_parser.add_argument("variant", nargs="?", help="Variant to use (default: the first one)")
_holes_parser.add_argument("--count", type=int, default=6, help="Number of positions to list")

_apply_parser = _subparsers.add_parser("apply", help="Write a variant into the card data yaml")
_apply_parser.add_argument("agent_id", type=int)
_apply_parser.add_argument("card_id", help="e.g. t1_1641, t1_1641_3116411, t2_1641")
_apply_parser.add_argument("variant")

_spine_init_parser = _subparsers.add_parser("spine-init", help="Suggest animated image framings")
_spine_init_parser.add_argument("agent_ids", nargs="*", help="Only these agents (default: all)")
_spine_init_parser.add_argument("--force", action="store_true", help="Replace existing entries")

_spine_parser = _subparsers.add_parser("spine", help="Render animated image framing variants")
_spine_parser.add_argument("agent_ids", nargs="*", help="Only these agents (default: all)")

_spine_apply_parser = _subparsers.add_parser("spine-apply", help="Write framings to spine.yaml")
_spine_apply_parser.add_argument("picks", nargs="+", help="AGENT_ID or AGENT_ID:VARIANT")

_args = _parser.parse_args()

# Clear argv so pydantic-settings doesn't try to parse our flags as bot config.
sys.argv = sys.argv[:1]

import aiohttp
import enka
import hb_data
import numpy as np
import yaml
from PIL import Image, ImageDraw, ImageFont
from PIL.Image import Transpose

sys.path.insert(0, str(Path(__file__).parent.parent))

from hoyo_buddy.constants import ZZZ_ANIMATED_CARD_SCALE
from hoyo_buddy.draw.drawer import Drawer
from hoyo_buddy.draw.fonts import NUNITO_SANS_BLACK_ITALIC
from hoyo_buddy.draw.funcs.hoyo.zzz import ZZZAgentCard
from hoyo_buddy.draw.static import download_images
from hoyo_buddy.enums import Locale
from hoyo_buddy.hoyo.clients.gpy import GenshinClient
from hoyo_buddy.models import AgentNameData, ZZZEnkaCharacter
from hoyo_buddy.models.draw import ZZZTemp1CardData, ZZZTemp2CardData
from scripts import render_zzz_spine

NANOKA_URL = "https://static.nanoka.cc"
SAMPLE_PATH = Path("scripts/data/zzz_sample_agent.json")
OUTPUT_DIR = Path("scripts/output/zzz_variants")
CARD_DATA_PATHS = {
    1: Path("hoyo-buddy-assets/assets/zzz-build-card/agent_data.yaml"),
    2: Path("hoyo-buddy-assets/assets/zzz-build-card/agent_data_temp2.yaml"),
}
SPINE_DIR = OUTPUT_DIR / "spine"
SPINE_SPEC_PATH = SPINE_DIR / "variants.yaml"
SPINE_SHEET_SIZE = 4
"""Agents per spine contact sheet."""
SPINE_JOBS = 6
"""Number of previews to render at once."""
FIELD_ORDER = (
    "color",
    "flip",
    "full_name",
    "image_x",
    "image_y",
    "image_w",
    "image_h",
    "level_flip",
    "level_stroke",
    "level_x",
    "level_y",
    "name_x",
    "name_y",
    "zzz_text",
)
UNKNOWN_TEXT = "..."  # nanoka's placeholder for untranslated text of unreleased content
CARD_SIZE = (3324, 1286)
# Middle of the open area between the left equip panel and the right stats panel
OPEN_AREA_CENTER_X = 1822
# Where template 2 cinema art is centered, and how far its solid area overshoots the card's edges
TEMPLATE2_CENTER_X = 1700
TEMPLATE2_OVERSHOOT = 7


def _spec_path(agent_id: int) -> Path:
    return OUTPUT_DIR / str(agent_id) / "variants.yaml"


def _load_spec(agent_id: int) -> dict[str, Any]:
    path = _spec_path(agent_id)
    if not path.exists():
        msg = f"{path} doesn't exist, run `init {agent_id}` first"
        raise SystemExit(msg)
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_card_data(template: int) -> dict[str, dict[str, Any]]:
    return yaml.safe_load(CARD_DATA_PATHS[template].read_text(encoding="utf-8"))


def _hex(rgb: tuple[float, float, float]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*(round(c * 255) for c in rgb))


def extract_palette(image: Image.Image, *, count: int = 6) -> dict[str, list[str]]:
    """Extract the dominant colors of an image, plus softer versions suited for card accents."""
    image = image.convert("RGBA")
    image.thumbnail((256, 256))
    rgba_pixels = cast("list[tuple[int, int, int, int]]", image.get_flattened_data())
    pixels = [p[:3] for p in rgba_pixels if p[3] > 200]
    strip = Image.new("RGB", (len(pixels), 1))
    strip.putdata(pixels)
    quantized = strip.quantize(colors=16, method=Image.Quantize.MEDIANCUT)
    palette = quantized.getpalette() or []

    dominant: list[str] = []
    soft: list[str] = []
    colors = cast("list[tuple[int, int]]", quantized.getcolors() or [])
    for _, index in sorted(colors, reverse=True):
        r, g, b = (c / 255 for c in palette[index * 3 : index * 3 + 3])
        h, l, s = colorsys.rgb_to_hls(r, g, b)
        # Skip near black, near white and greys, they don't make good accent colors
        if l < 0.15 or l > 0.9 or s < 0.15:
            continue
        dominant.append(_hex((r, g, b)))
        soft.append(_hex(colorsys.hls_to_rgb(h, min(max(l, 0.55), 0.75), min(s, 0.45))))
        if len(dominant) == count:
            break
    return {"dominant": dominant, "soft": soft}


def resolve_variant(card: dict[str, Any], variant: str, aspect: float) -> dict[str, Any]:
    """Merge a variant's overrides into the card's base config."""
    overrides: dict[str, Any] = card["variants"][variant] or {}
    config = {**card["base"], **overrides}
    if "image_w" in overrides and "image_h" not in overrides:
        config["image_h"] = round(config["image_w"] / aspect)
    elif "image_h" in overrides and "image_w" not in overrides:
        config["image_w"] = round(config["image_h"] * aspect)
    return config


async def _get_json(session: aiohttp.ClientSession, url: str) -> Any:
    async with session.get(url) as resp:
        resp.raise_for_status()
        return await resp.json(content_type=None)


async def _get_image(session: aiohttp.ClientSession, url: str) -> Image.Image | None:
    async with session.get(url) as resp:
        if resp.status != 200:
            return None
        return Image.open(io.BytesIO(await resp.read()))


async def fetch_sample(uid: int) -> None:
    async with enka.ZZZClient(enka.zzz.Language.ENGLISH) as client:
        await client.update_assets()
        raw = await client.fetch_showcase(uid, raw=True)
        showcase = client.parse_showcase(raw)
    if not showcase.agents:
        msg = f"UID {uid} has no agents in their showcase"
        raise SystemExit(msg)

    async with hb_data.ZZZClient() as data_client:
        drive_disc_icons = {disc.id: disc.icon for disc in data_client.get_drive_discs()}
    agent = showcase.agents[0]
    disc_icons = {d.id: drive_disc_icons[d.id] for d in agent.discs if d.id in drive_disc_icons}

    SAMPLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SAMPLE_PATH.write_text(
        json.dumps({"uid": uid, "showcase": raw, "disc_icons": disc_icons}, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Saved {agent.name} (Lv.{agent.level}, M{agent.mindscape}) to {SAMPLE_PATH}")


async def _load_sample() -> tuple[ZZZEnkaCharacter, dict[int, str]]:
    if not SAMPLE_PATH.exists():
        msg = f"{SAMPLE_PATH} doesn't exist, run `fetch-sample` first"
        raise SystemExit(msg)
    data = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
    async with enka.ZZZClient(enka.zzz.Language.ENGLISH) as client:
        showcase = client.parse_showcase(data["showcase"])
    agent = GenshinClient.convert_zzz_character(showcase.agents[0])
    return agent, {int(k): v for k, v in data["disc_icons"].items()}


def fit_template2(image: Image.Image) -> dict[str, int]:
    """Size cinema art by its solid area so its top and bottom touch the card's, centered.

    The images have transparent strips above and below the art, and the bottom edge is often a
    soft or slanted cut, so the bottom is where the middle columns' solid pixels usually end.
    """
    solid = np.asarray(image.convert("RGBA").getchannel("A")) > 250
    rows = np.flatnonzero(solid.any(axis=1))
    cols = np.flatnonzero(solid.any(axis=0))
    top, left, right = rows[0], cols[0], cols[-1] + 1

    margin = (right - left) // 5
    middle = solid[:, left + margin : right - margin]
    ends = middle.shape[0] - np.argmax(middle[::-1], axis=0)
    ends = ends[middle.any(axis=0) & (ends >= rows[-1] - 0.1 * solid.shape[0])]
    bottom = float(np.median(ends))

    scale = (CARD_SIZE[1] + 2 * TEMPLATE2_OVERSHOOT) / (bottom - top)
    return {
        "image_w": round(image.width * scale),
        "image_h": round(image.height * scale),
        "image_x": round(TEMPLATE2_CENTER_X - (left + right) / 2 * scale),
        "image_y": round(-TEMPLATE2_OVERSHOOT - top * scale),
    }


def _make_base(template: int, key: str, image: Image.Image) -> dict[str, Any]:
    """Copy the key's existing card data, or the latest agent's with the image fitted to the new
    art.
    """
    card_data = _load_card_data(template)
    if key in card_data:
        return dict(card_data[key])
    latest_key = next(k for k in reversed(card_data) if "_" not in k)
    base = dict(card_data[latest_key])
    base["flip"] = False  # Art is drawn from a specific perspective, flipping looks wrong
    if template == 2:
        base.update(fit_template2(image))
    else:
        base["image_w"] = round(base["image_h"] * image.width / image.height)
    return base


async def _make_card(
    session: aiohttp.ClientSession, *, template: int, key: str, label: str, image_url: str
) -> dict[str, Any] | None:
    image = await _get_image(session, image_url)
    if image is None:
        return None
    return {
        "template": template,
        "key": key,
        "label": label,
        "image": image_url,
        "palette": extract_palette(image),
        "base": _make_base(template, key, image),
        "variants": {"base": {}},
    }


async def init(agent_id: int, *, version: str | None, force: bool) -> None:
    path = _spec_path(agent_id)
    if path.exists() and not force:
        msg = f"{path} already exists, pass --force to overwrite it"
        raise SystemExit(msg)

    async with aiohttp.ClientSession() as session:
        if version is None:
            version = (await _get_json(session, f"{NANOKA_URL}/manifest.json"))["zzz"]["latest"]
        char = await _get_json(session, f"{NANOKA_URL}/zzz/{version}/en/character/{agent_id}.json")
        name: str = char["name"]
        full_name: str = char["partner_info"]["full_name"]

        cards: dict[str, dict[str, Any]] = {}
        for i, (skin_id, skin) in enumerate(char["skin"].items()):
            key = str(agent_id) if i == 0 else f"{agent_id}_{skin_id}"
            card = await _make_card(
                session,
                template=1,
                key=key,
                label=name if i == 0 else f"{name}: {skin['name']}",
                image_url=f"{NANOKA_URL}/assets/zzz/{skin['image']}.webp",
            )
            if card is None:
                print(f"Skipping t1_{key}: art {skin['image']} isn't available yet")
                continue
            cards[f"t1_{key}"] = card

        image_url = f"{NANOKA_URL}/assets/zzz/Mindscape_{agent_id}_3.webp"
        card = await _make_card(
            session, template=2, key=str(agent_id), label=name, image_url=image_url
        )
        if card is None:
            print(f"Skipping t2_{agent_id}: M6 cinema art isn't available yet")
        else:
            cards[f"t2_{agent_id}"] = card

    spec = {
        "agent_id": agent_id,
        "version": version,
        "name": name,
        "full_name": name if full_name == UNKNOWN_TEXT else full_name,
        "cards": cards,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(spec, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(f"Wrote {len(cards)} card(s) to {path}: {', '.join(cards)}")


def _get_fallback_color(spec: dict[str, Any]) -> str | None:
    """Get the color template 2 falls back to when it doesn't set its own."""
    key = str(spec["agent_id"])
    if (entry := _load_card_data(1).get(key)) is not None:
        return entry["color"]
    if (card := spec["cards"].get(f"t1_{key}")) is not None:
        return card["base"]["color"]
    return None


def _place_art(card_data: ZZZTemp1CardData, art: Image.Image) -> Image.Image:
    art = Drawer.resize_crop(art.convert("RGBA"), (card_data.image_w, card_data.image_h))
    if card_data.flip:
        art = art.transpose(Transpose.FLIP_LEFT_RIGHT)
    return art


def _art_mask(card_data: ZZZTemp1CardData, art: Image.Image) -> np.ndarray:
    """Get which pixels of the card the placed art covers."""
    mask = Image.new("L", CARD_SIZE)
    mask.paste(_place_art(card_data, art).getchannel("A"), (card_data.image_x, card_data.image_y))
    return np.asarray(mask) > 128


Box = tuple[int, int, int, int]


@functools.cache
def _level_metrics(level: int, rank: int) -> tuple[Box, tuple[int, int]]:
    font = ImageFont.truetype(NUNITO_SANS_BLACK_ITALIC, 250)
    left, top, right, bottom = (int(v) for v in font.getbbox(f"Lv.{level}"))
    rank_image = Drawer.open_image(f"hoyo-buddy-assets/assets/zzz-build-card/rank/M{rank}.png")
    return (left, top, right, bottom), rank_image.size


def _level_boxes(agent: ZZZEnkaCharacter, *, x: int, y: int, flip: bool) -> tuple[Box, Box]:
    """Get the boxes of the level text and the mindscape rank below it, as ZZZAgentCard draws."""
    (left, top, right, bottom), (rank_w, rank_h) = _level_metrics(agent.level, agent.rank)
    rank_x = x + right - left - rank_w if flip else x
    return (
        (x + left, y + top, x + right, y + bottom),
        (rank_x, y + 260, rank_x + rank_w, y + 260 + rank_h),
    )


def _coverage(opaque: np.ndarray, box: Box) -> float:
    return float(opaque[box[1] : box[3], box[0] : box[2]].mean())


def measure_layout(
    agent: ZZZEnkaCharacter, *, card_data: ZZZTemp1CardData, art: Image.Image
) -> str:
    """Describe how much of the level text covers the art, and where the art's focus lands."""
    opaque = _art_mask(card_data, art)
    level_box, rank_box = _level_boxes(
        agent, x=card_data.level_x, y=card_data.level_y, flip=card_data.level_flip
    )
    level_cover = _coverage(opaque, level_box)
    rank_cover = _coverage(opaque, rank_box)

    stroke = card_data.level_stroke
    overlaps = max(level_cover, rank_cover) > 0.01
    hint = " (turn stroke ON)" if overlaps and not stroke else ""
    hint = " (stroke not needed)" if not overlaps and stroke else hint

    # Alpha-weighted x of the head/shoulders (top 30% of the art); long hair can skew it
    alpha = np.asarray(_place_art(card_data, art).getchannel("A"), dtype=float)
    first_row = int(np.argmax(alpha.max(axis=1) > 128))
    head = alpha[first_row : first_row + int(alpha.shape[0] * 0.3)]
    focus_x = card_data.image_x + (head.sum(axis=0) * np.arange(alpha.shape[1])).sum() / head.sum()

    return (
        f"art under Lv {level_cover:.0%}, under rank {rank_cover:.0%}, "
        f"stroke {'on' if stroke else 'off'}{hint} | "
        f"focus x {focus_x:.0f} (center {OPEN_AREA_CENTER_X})"
    )


def _make_contact_sheet(tiles: list[tuple[str, str, Image.Image]]) -> Image.Image:
    cols, pad, label_h, thumb_w = 2, 24, 100, 1108
    thumb_h = round(tiles[0][2].height * thumb_w / tiles[0][2].width)
    cols = min(cols, len(tiles))
    rows = math.ceil(len(tiles) / cols)
    sheet = Image.new(
        "RGB", (pad + cols * (thumb_w + pad), pad + rows * (label_h + thumb_h + pad)), (30, 30, 30)
    )
    draw = ImageDraw.Draw(sheet)
    title_font = ImageFont.load_default(size=32)
    desc_font = ImageFont.load_default(size=20)

    for i, (name, desc, image) in enumerate(tiles):
        x = pad + (i % cols) * (thumb_w + pad)
        y = pad + (i // cols) * (label_h + thumb_h + pad)
        draw.text((x, y), name, font=title_font, fill=(255, 255, 255))
        draw.multiline_text((x, y + 40), desc, font=desc_font, fill=(170, 170, 170))
        thumb = image.convert("RGB").resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
        sheet.paste(thumb, (x, y + label_h))
    return sheet


def _draw_variant(
    agent: ZZZEnkaCharacter,
    *,
    card: dict[str, Any],
    card_data: ZZZTemp1CardData,
    name_data: AgentNameData,
    disc_icons: dict[int, str],
) -> Image.Image:
    result = ZZZAgentCard(
        agent,
        locale=Locale.american_english.value,
        image_url=card["image"],
        card_data=card_data,
        disc_icons=disc_icons,
        name_data=name_data,
        color=None,
        template=card["template"],
        show_substat_rolls=True,
        agent_special_stats=[],
        hl_substats=[],
        hl_special_stats=False,
    ).draw()
    return Image.open(result)


async def render(agent_id: int, card_ids: list[str]) -> None:
    spec = _load_spec(agent_id)
    cards: dict[str, dict[str, Any]] = spec["cards"]
    if unknown := set(card_ids) - set(cards):
        msg = f"Unknown card ID(s): {', '.join(unknown)}, available: {', '.join(cards)}"
        raise SystemExit(msg)

    agent, disc_icons = await _load_sample()
    name_data = AgentNameData(short_name=spec["name"], full_name=spec["full_name"])
    fallback_color = _get_fallback_color(spec)

    urls = [card["image"] for card in cards.values()] + list(disc_icons.values())
    if agent.w_engine is not None:
        urls.append(agent.w_engine.icon)
    async with aiohttp.ClientSession() as session:
        await download_images(urls, session)

    for card_id, card in cards.items():
        if card_ids and card_id not in card_ids:
            continue

        art = Drawer.open_static(card["image"])
        out_dir = OUTPUT_DIR / str(agent_id) / card_id
        out_dir.mkdir(parents=True, exist_ok=True)
        tiles: list[tuple[str, str, Image.Image]] = []

        for variant, overrides in card["variants"].items():
            config = resolve_variant(card, variant, art.width / art.height)
            config["color"] = config.get("color") or fallback_color
            model = ZZZTemp2CardData if card["template"] == 2 else ZZZTemp1CardData
            card_data = model.model_validate(config)
            image = _draw_variant(
                agent, card=card, card_data=card_data, name_data=name_data, disc_icons=disc_icons
            )
            image.save(out_dir / f"{variant}.png")
            layout = measure_layout(agent, card_data=card_data, art=art)
            desc = ", ".join(f"{k}={v}" for k, v in (overrides or {}).items()) or "base"
            tiles.append((variant, f"{desc}\n{layout}", image))
            print(f"Rendered {card_id}/{variant}: {layout}")

        sheet_path = OUTPUT_DIR / str(agent_id) / f"{card_id}.png"
        _make_contact_sheet(tiles).save(sheet_path)
        print(f"Contact sheet: {sheet_path}")


def _format_entry(key: str, label: str, config: dict[str, Any]) -> list[str]:
    lines = [f'"{key}":', f"  # {label}"]
    for field in FIELD_ORDER:
        value = config.get(field)
        if value is None:
            continue
        if isinstance(value, bool):
            value = str(value).lower()
        elif isinstance(value, str):
            value = f'"{value}"'
        lines.append(f"  {field}: {value}")
    return lines


async def apply(agent_id: int, card_id: str, variant: str) -> None:
    spec = _load_spec(agent_id)
    card = spec["cards"].get(card_id)
    if card is None:
        msg = f"Unknown card ID {card_id}, available: {', '.join(spec['cards'])}"
        raise SystemExit(msg)
    if variant not in card["variants"]:
        msg = f"Unknown variant {variant}, available: {', '.join(card['variants'])}"
        raise SystemExit(msg)

    async with aiohttp.ClientSession() as session:
        await download_images([card["image"]], session)
    art = Drawer.open_static(card["image"])
    config = resolve_variant(card, variant, art.width / art.height)
    # Validate before writing so a broken variant never lands in the data file
    model = ZZZTemp2CardData if card["template"] == 2 else ZZZTemp1CardData
    model.model_validate({**config, "color": config.get("color") or "#000000"})

    path = CARD_DATA_PATHS[card["template"]]
    lines = path.read_text(encoding="utf-8").splitlines()
    entry = _format_entry(card["key"], card["label"], config)
    header = f'"{card["key"]}":'

    if header in lines:
        start = lines.index(header)
        end = next(
            (i for i in range(start + 1, len(lines)) if lines[i].startswith('"')), len(lines)
        )
        lines[start:end] = entry
        action = "Replaced"
    else:
        lines.extend(entry)
        action = "Added"

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{action} {card['key']} in {path} with variant {variant}:")
    print("\n".join(entry))


def _is_valid_level_spot(level_box: Box, rank_box: Box, *, zzz_text: bool) -> bool:
    """Check that the level text stays clear of the card's panels, big name and ZENLESS text."""
    left, top, right, bottom = level_box
    min_left = 880 if bottom <= 360 else 960  # The equip panel is narrower above the discs
    if left < min_left or right > 2660 or rank_box[3] > CARD_SIZE[1] - 10:
        return False
    if top < 430 and right > 2230:  # Big name
        return False
    return not (zzz_text and left < 1450 and top < 420)


async def holes(agent_id: int, card_id: str, variant: str | None, *, count: int) -> None:
    spec = _load_spec(agent_id)
    card = spec["cards"].get(card_id)
    if card is None:
        msg = f"Unknown card ID {card_id}, available: {', '.join(spec['cards'])}"
        raise SystemExit(msg)
    variant = variant or next(iter(card["variants"]))

    async with aiohttp.ClientSession() as session:
        await download_images([card["image"]], session)
    art = Drawer.open_static(card["image"])
    config = resolve_variant(card, variant, art.width / art.height)
    model = ZZZTemp2CardData if card["template"] == 2 else ZZZTemp1CardData
    card_data = model.model_validate({**config, "color": config.get("color") or "#000000"})
    agent, _ = await _load_sample()
    opaque = _art_mask(card_data, art)

    spots: list[tuple[float, int, int]] = []
    for y in range(20, CARD_SIZE[1], 20):
        for x in range(880, 2100, 20):
            level_box, rank_box = _level_boxes(agent, x=x, y=y, flip=card_data.level_flip)
            if _is_valid_level_spot(level_box, rank_box, zzz_text=card_data.zzz_text):
                cover = max(_coverage(opaque, level_box), _coverage(opaque, rank_box))
                spots.append((cover, x, y))

    # List distinct spots rather than many near-identical neighbours of the best one
    picked: list[tuple[float, int, int]] = []
    for spot in sorted(spots):
        if all(abs(spot[1] - p[1]) > 150 or abs(spot[2] - p[2]) > 150 for p in picked):
            picked.append(spot)
        if len(picked) == count:
            break

    print(f"Level positions for {card_id}/{variant} (least art under Lv/rank first):")
    for cover, x, y in picked:
        print(
            f"  level_x {x}, level_y {y}: {cover:.0%} art -> stroke {'on' if cover > 0.01 else 'off'}"
        )


def _load_spine_spec() -> dict[str, dict[str, Any]]:
    if not SPINE_SPEC_PATH.exists():
        msg = f"{SPINE_SPEC_PATH} doesn't exist, run `spine-init` first"
        raise SystemExit(msg)
    return yaml.safe_load(SPINE_SPEC_PATH.read_text(encoding="utf-8"))


def _spine_framing(entry: dict[str, Any], variant: str) -> render_zzz_spine.Framing:
    return render_zzz_spine.Framing(**{**entry["base"], **(entry["variants"][variant] or {})})


async def _get_spine_files(session: aiohttp.ClientSession, spine: str) -> tuple[Path, Path]:
    """Download an agent's Spine files once, they don't change between versions."""
    folder = SPINE_DIR / "files" / spine
    skel, atlas = folder / f"{spine}.skel", folder / f"{spine}.atlas"
    if skel.exists():
        return skel, atlas
    folder.mkdir(parents=True, exist_ok=True)
    return await render_zzz_spine.download_spine(session, spine, folder)


async def spine_init(agent_ids: list[str], *, force: bool) -> None:
    spec: dict[str, dict[str, Any]] = (
        yaml.safe_load(SPINE_SPEC_PATH.read_text(encoding="utf-8"))
        if SPINE_SPEC_PATH.exists()
        else {}
    )
    card_data = _load_card_data(1)

    async with aiohttp.ClientSession() as session:
        agents = await render_zzz_spine.fetch_spine_agents(session, agent_ids or None)
        for agent_id, agent in agents.items():
            if agent_id in spec and not force:
                continue
            if agent_id not in card_data:
                print(f"Skipping {agent.name} ({agent_id}): no template 1 card data")
                continue

            skel, atlas = await _get_spine_files(session, agent.spine)
            with tempfile.TemporaryDirectory() as tmp:
                framing = await render_zzz_spine.suggest_framing(
                    skel,
                    atlas,
                    Path(tmp),
                    spine=agent.spine,
                    static_art=await render_zzz_spine.download_image(session, agent.image),
                    card_data=card_data[agent_id],
                )
            spec[agent_id] = {
                "name": agent.name,
                "spine": agent.spine,
                "image": agent.image,
                "base": framing._asdict(),
                "variants": {"base": {}},
            }
            print(f"{agent.name} ({agent_id}): {framing}")

    SPINE_SPEC_PATH.parent.mkdir(parents=True, exist_ok=True)
    SPINE_SPEC_PATH.write_text(
        yaml.safe_dump(spec, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    print(f"Wrote {SPINE_SPEC_PATH}")


def _describe_on_card(art: Image.Image, *, x: float, y: float, scale: float) -> str:
    """Describe whether the card's top edge cuts the art and where its head lands.

    Args:
        art: The art, as placed on the card (cropped to it for animations).
        x: The art's left on the static-scale card.
        y: The art's top on the static-scale card.
        scale: Pixels on the static-scale card per pixel of the art.
    """
    alpha = np.asarray(art.getchannel("A"))
    top, _, focus_x = render_zzz_spine.art_extent(alpha)
    edge_row = round(-y / scale)  # The art's row at the card's top edge
    cut = float((alpha[edge_row] > 128).mean()) if 0 <= edge_row < alpha.shape[0] else 0.0
    art_top = y + top * scale
    return f"art top y {art_top:.0f}, {cut:.0%} of top edge cut | focus x {x + focus_x * scale:.0f}"


def _make_spine_card(
    agent: ZZZEnkaCharacter,
    *,
    entry: dict[str, Any],
    card_data: ZZZTemp1CardData,
    disc_icons: dict[int, str],
) -> ZZZAgentCard:
    name_data = AgentNameData(short_name=entry["name"], full_name=entry["name"])
    return ZZZAgentCard(
        agent,
        locale=Locale.american_english.value,
        image_url=entry["image"],
        card_data=card_data,
        disc_icons=disc_icons,
        name_data=name_data,
        color=None,
        template=1,
        show_substat_rolls=True,
        agent_special_stats=[],
        hl_substats=[],
        hl_special_stats=False,
    )


def _draw_spine_tiles(
    card: ZZZAgentCard,
    *,
    entry: dict[str, Any],
    card_data: ZZZTemp1CardData,
    previews: dict[str, Image.Image],
) -> list[tuple[str, str, Image.Image]]:
    """Draw the static card and each variant's first animated frame on the card."""
    art = _place_art(card_data, Drawer.open_static(entry["image"]))
    static_desc = _describe_on_card(art, x=card_data.image_x, y=card_data.image_y, scale=1)
    tiles: list[tuple[str, str, Image.Image]] = [
        (f"{entry['name']} static", static_desc, Image.open(card.draw()))
    ]

    for variant, frame in previews.items():
        framing = _spine_framing(entry, variant)
        with tempfile.TemporaryDirectory() as tmp:
            frame_path = Path(tmp) / "frame.webp"
            frame.save(frame_path, lossless=True)
            image = Image.open(card.draw_animated(frame_path, (framing.x, framing.y)))
            image.load()
        desc = _describe_on_card(
            frame, x=max(framing.x, 0), y=max(framing.y, 0), scale=1 / ZZZ_ANIMATED_CARD_SCALE
        )
        overrides = entry["variants"][variant] or {}
        changes = ", ".join(f"{k}={v}" for k, v in overrides.items()) or "base"
        tiles.append((f"{variant}: {framing}", f"{changes}\n{desc}", image))
    return tiles


async def spine(agent_ids: list[str]) -> None:
    spec = _load_spine_spec()
    if unknown := set(agent_ids) - set(spec):
        msg = f"Not in {SPINE_SPEC_PATH}: {', '.join(unknown)}"
        raise SystemExit(msg)
    keys = agent_ids or list(spec)
    card_data = {k: ZZZTemp1CardData.model_validate(v) for k, v in _load_card_data(1).items()}
    agent, disc_icons = await _load_sample()
    semaphore = asyncio.Semaphore(SPINE_JOBS)

    async def preview(
        session: aiohttp.ClientSession, key: str, variant: str
    ) -> tuple[str, str, Image.Image]:
        async with semaphore:
            skel, atlas = await _get_spine_files(session, spec[key]["spine"])
            with tempfile.TemporaryDirectory() as tmp:
                frames = await render_zzz_spine.render_card_frames(
                    skel,
                    atlas,
                    Path(tmp),
                    spine=spec[key]["spine"],
                    framing=_spine_framing(spec[key], variant),
                    frames=1,
                )
            return key, variant, frames[0]

    async with aiohttp.ClientSession() as session:
        urls = [spec[k]["image"] for k in keys] + list(disc_icons.values())
        if agent.w_engine is not None:
            urls.append(agent.w_engine.icon)
        await download_images(urls, session)
        results = await asyncio.gather(
            *(preview(session, k, v) for k in keys for v in spec[k]["variants"])
        )

    previews: dict[str, dict[str, Image.Image]] = {}
    for key, variant, frame in results:
        previews.setdefault(key, {})[variant] = frame

    SPINE_DIR.mkdir(parents=True, exist_ok=True)
    for i in range(0, len(keys), SPINE_SHEET_SIZE):
        sheet_keys = keys[i : i + SPINE_SHEET_SIZE]
        tiles: list[tuple[str, str, Image.Image]] = []
        for key in sheet_keys:
            card = _make_spine_card(
                agent, entry=spec[key], card_data=card_data[key], disc_icons=disc_icons
            )
            pair = _draw_spine_tiles(
                card, entry=spec[key], card_data=card_data[key], previews=previews[key]
            )
            for name, desc, _ in pair:
                print(f"{key} {name}: {desc.replace(chr(10), ' | ')}")
            tiles.extend(pair)

        sheet_path = SPINE_DIR / f"{sheet_keys[0]}-{sheet_keys[-1]}.png"
        _make_contact_sheet(tiles).save(sheet_path)
        print(f"Contact sheet: {sheet_path}")


def spine_apply(picks: list[str]) -> None:
    spec = _load_spine_spec()
    manifest: dict[str, dict[str, Any]] = yaml.safe_load(
        render_zzz_spine.MANIFEST_PATH.read_text(encoding="utf-8")
    )
    for pick in picks:
        agent_id, _, variant = pick.partition(":")
        variant = variant or "base"
        if agent_id not in manifest:
            msg = f"{agent_id} isn't in {render_zzz_spine.MANIFEST_PATH}, render it first"
            raise SystemExit(msg)
        if variant not in spec.get(agent_id, {}).get("variants", {}):
            msg = f"{agent_id} has no variant {variant!r} in {SPINE_SPEC_PATH}"
            raise SystemExit(msg)
        manifest[agent_id].update(_spine_framing(spec[agent_id], variant)._asdict())
        print(f"{spec[agent_id]['name']} ({agent_id}): {variant}")

    render_zzz_spine.MANIFEST_PATH.write_text(
        yaml.safe_dump(manifest, allow_unicode=True), encoding="utf-8"
    )
    agent_ids = " ".join(pick.partition(":")[0] for pick in picks)
    print(f"Re-render them: uv run scripts/render_zzz_spine.py {agent_ids}")


async def main() -> None:
    match _args.command:
        case "fetch-sample":
            await fetch_sample(_args.uid)
        case "init":
            await init(_args.agent_id, version=_args.version, force=_args.force)
        case "render":
            await render(_args.agent_id, _args.cards)
        case "holes":
            await holes(_args.agent_id, _args.card_id, _args.variant, count=_args.count)
        case "apply":
            await apply(_args.agent_id, _args.card_id, _args.variant)
        case "spine-init":
            await spine_init(_args.agent_ids, force=_args.force)
        case "spine":
            await spine(_args.agent_ids)
        case "spine-apply":
            spine_apply(_args.picks)


if __name__ == "__main__":
    asyncio.run(main())
