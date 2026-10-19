"""Design ZZZ build card data (templates 1 and 2) for new agents by rendering variants.

Workflow (run from the repo root):
    1. uv run scripts/zzz_card_variants.py init 1641
       Fetches the agent's art from nanoka and writes scripts/output/zzz_variants/1641/variants.yaml
       with one card per art: template 1 default art + each skin, and template 2 M6 cinema art.
       Each card's `base` starts from the latest agent in agent_data*.yaml (image rescaled to the
       new art's aspect ratio), and `palette` lists colors extracted from the art. Design each
       skin card like a separate agent: its own color, image size/position, level position and
       zzz_text, rather than copying the default skin's.
    2. Add named entries under each card's `variants`. A variant overrides any keys of `base`
       (color, image_x, level_x, zzz_text, ...). If a variant overrides only one of image_w or
       image_h, the other is derived from the art's aspect ratio.
    3. uv run scripts/zzz_card_variants.py render 1641 [CARD_ID ...]
       Renders each variant to scripts/output/zzz_variants/1641/<card_id>/<variant>.png and a
       labelled contact sheet of all variants to scripts/output/zzz_variants/1641/<card_id>.png.
       Each variant's label also shows how much of the level text covers the art (level_stroke
       should be on only when it does) and where the art's head/shoulders land horizontally.
    4. uv run scripts/zzz_card_variants.py apply 1641 t1_1641 <variant>
       Writes the chosen variant into agent_data.yaml (template 1) or agent_data_temp2.yaml.

Cards are drawn with a sample agent's stats stored in scripts/data/zzz_sample_agent.json, so Enka
doesn't need to be up. Refresh it with:
    uv run scripts/zzz_card_variants.py fetch-sample [--uid UID]
"""

from __future__ import annotations

import argparse
import asyncio
import colorsys
import io
import json
import math
import sys
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

_apply_parser = _subparsers.add_parser("apply", help="Write a variant into the card data yaml")
_apply_parser.add_argument("agent_id", type=int)
_apply_parser.add_argument("card_id", help="e.g. t1_1641, t1_1641_3116411, t2_1641")
_apply_parser.add_argument("variant")

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

from hoyo_buddy.draw.drawer import Drawer
from hoyo_buddy.draw.fonts import NUNITO_SANS_BLACK_ITALIC
from hoyo_buddy.draw.funcs.hoyo.zzz import ZZZAgentCard
from hoyo_buddy.draw.static import download_images
from hoyo_buddy.enums import Locale
from hoyo_buddy.hoyo.clients.gpy import GenshinClient
from hoyo_buddy.models import AgentNameData, ZZZEnkaCharacter
from hoyo_buddy.models.draw import ZZZTemp1CardData, ZZZTemp2CardData

NANOKA_URL = "https://static.nanoka.cc"
SAMPLE_PATH = Path("scripts/data/zzz_sample_agent.json")
OUTPUT_DIR = Path("scripts/output/zzz_variants")
CARD_DATA_PATHS = {
    1: Path("hoyo-buddy-assets/assets/zzz-build-card/agent_data.yaml"),
    2: Path("hoyo-buddy-assets/assets/zzz-build-card/agent_data_temp2.yaml"),
}
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
# Middle of the open area between the left equip panel and the right stats panel
OPEN_AREA_CENTER_X = 1822


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


def _make_base(template: int, key: str, aspect: float) -> dict[str, Any]:
    """Copy the key's existing card data, or the latest agent's with the image rescaled to the
    new art's aspect ratio.
    """
    card_data = _load_card_data(template)
    if key in card_data:
        return dict(card_data[key])
    latest_key = next(k for k in reversed(card_data) if "_" not in k)
    base = dict(card_data[latest_key])
    base["image_w"] = round(base["image_h"] * aspect)
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
        "base": _make_base(template, key, image.width / image.height),
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


def measure_layout(
    agent: ZZZEnkaCharacter,
    *,
    card_data: ZZZTemp1CardData,
    art: Image.Image,
    card_size: tuple[int, int],
) -> str:
    """Describe how much of the level text covers the art, and where the art's focus lands."""
    art = Drawer.resize_crop(art.convert("RGBA"), (card_data.image_w, card_data.image_h))
    if card_data.flip:
        art = art.transpose(Transpose.FLIP_LEFT_RIGHT)
    mask = Image.new("L", card_size)
    mask.paste(art.getchannel("A"), (card_data.image_x, card_data.image_y))
    opaque = np.asarray(mask) > 128

    # Mirrors how ZZZAgentCard draws the level text and the mindscape rank below it
    font = ImageFont.truetype(NUNITO_SANS_BLACK_ITALIC, 250)
    left, top, right, bottom = font.getbbox(f"Lv.{agent.level}")
    x, y = card_data.level_x, card_data.level_y
    rank = Drawer.open_image(f"hoyo-buddy-assets/assets/zzz-build-card/rank/M{agent.rank}.png")
    rank_x = x + right - left - rank.width if card_data.level_flip else x
    level_cover = opaque[y + top : y + bottom, x + left : x + right].mean()
    rank_cover = opaque[y + 260 : y + 260 + rank.height, rank_x : rank_x + rank.width].mean()

    stroke = card_data.level_stroke
    overlaps = max(level_cover, rank_cover) > 0.01
    hint = " (turn stroke ON)" if overlaps and not stroke else ""
    hint = " (stroke not needed)" if not overlaps and stroke else hint

    # Alpha-weighted x of the head/shoulders (top 30% of the art); long hair can skew it
    alpha = np.asarray(art.getchannel("A"), dtype=float)
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
            layout = measure_layout(agent, card_data=card_data, art=art, card_size=image.size)
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


async def main() -> None:
    match _args.command:
        case "fetch-sample":
            await fetch_sample(_args.uid)
        case "init":
            await init(_args.agent_id, version=_args.version, force=_args.force)
        case "render":
            await render(_args.agent_id, _args.cards)
        case "apply":
            await apply(_args.agent_id, _args.card_id, _args.variant)


if __name__ == "__main__":
    asyncio.run(main())
